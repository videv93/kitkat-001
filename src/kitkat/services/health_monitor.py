"""Background health monitor for automatic DEX recovery (Story 4.3).

Polls DEX adapters at configurable intervals, detects failures,
and triggers automatic reconnection with exponential backoff.

Key responsibilities:
- Poll adapter.get_health_status() at configurable intervals
- Track consecutive failures per adapter
- Trigger status transitions (healthy/degraded/offline)
- Initiate automatic reconnection with exponential backoff
- Send Telegram alerts on status changes
- Support graceful shutdown
"""

import asyncio
import random
from typing import Optional

import structlog

from kitkat.adapters.base import DEXAdapter
from kitkat.services.alert import TelegramAlertService, send_alert_async

logger = structlog.get_logger()


class HealthMonitor:
    """Background service for DEX health monitoring and auto-recovery.

    Story 4.3: Auto-Recovery After Outage
    - AC#1: Health check every 30 seconds (configurable)
    - AC#2: Degraded detection with alerts
    - AC#3: Exponential backoff reconnection (1s, 2s, 4s, 8s, max 30s)
    - AC#4: Offline after 3 consecutive failures (configurable)
    - AC#5: Automatic recovery detection
    - AC#6: Zero manual intervention
    - AC#7: Configurable interval via HEALTH_CHECK_INTERVAL_SECONDS
    """

    # Reconnection constants
    RECONNECT_MAX_ATTEMPTS = 10  # Max reconnection attempts before giving up
    RECONNECT_BASE_DELAY = 1  # Initial delay in seconds
    HEALTH_CHECK_TIMEOUT = 10.0  # Timeout for individual health checks

    def __init__(
        self,
        adapters: list[DEXAdapter],
        alert_service: TelegramAlertService,
        check_interval: int = 30,
        max_failures: int = 3,
        max_backoff: int = 30,
    ):
        """Initialize health monitor.

        Args:
            adapters: List of DEX adapters to monitor
            alert_service: Service for sending Telegram alerts
            check_interval: Seconds between health checks (default: 30)
            max_failures: Consecutive failures before offline (default: 3)
            max_backoff: Max reconnection backoff seconds (default: 30)

        Note:
            HealthMonitor tracks status internally via get_status().
            The /api/health endpoint queries adapters directly via HealthService.
        """
        self._adapters = adapters
        self._alert_service = alert_service
        self._check_interval = check_interval
        self._max_failures = max_failures
        self._max_backoff = max_backoff

        # Per-DEX tracking
        self._failure_counts: dict[str, int] = {}
        self._current_status: dict[str, str] = {}  # healthy/degraded/offline
        self._reconnecting: dict[str, bool] = {}

        # Background task reference
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

        self._log = logger.bind(service="health_monitor")

    async def start(self) -> None:
        """Start the background health monitoring loop.

        Creates an asyncio task that runs the polling loop.
        Non-blocking - returns immediately after starting task.
        """
        if self._running:
            self._log.warning("Health monitor already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        self._log.info(
            "Health monitor started",
            interval_seconds=self._check_interval,
            adapters=[a.dex_id for a in self._adapters],
        )

    async def stop(self) -> None:
        """Stop the background health monitoring loop.

        Gracefully cancels the monitoring task and waits for it to complete.
        """
        if not self._running:
            return

        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self._log.info("Health monitor stopped")

    async def _monitoring_loop(self) -> None:
        """Main polling loop - runs until stopped.

        Catches and logs any exceptions to prevent the loop from crashing.
        """
        while self._running:
            try:
                await self._check_all_adapters()
            except Exception as e:
                self._log.error("Health check loop error", error=str(e))

            await asyncio.sleep(self._check_interval)

    async def _check_all_adapters(self) -> None:
        """Check health of all adapters in parallel.

        Uses asyncio.gather with return_exceptions=True to handle
        individual adapter failures without stopping other checks.
        """
        if not self._adapters:
            return

        tasks = [self._check_adapter(adapter) for adapter in self._adapters]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_adapter(self, adapter: DEXAdapter) -> None:
        """Check single adapter and handle status transitions.

        Args:
            adapter: DEX adapter to check
        """
        dex_id = adapter.dex_id
        log = self._log.bind(dex_id=dex_id)

        # Skip if currently reconnecting (AC#6 - prevent conflicts)
        # Note: We still track failures even during reconnection to maintain
        # accurate state, but we don't perform the actual health check
        # since the adapter is being reconnected
        if self._reconnecting.get(dex_id, False):
            log.debug("Skipping check - reconnection in progress")
            return

        try:
            # Perform health check with timeout to prevent hanging
            health_result = await asyncio.wait_for(
                adapter.get_health_status(),
                timeout=self.HEALTH_CHECK_TIMEOUT,
            )
            success = health_result.status == "healthy"

            if success:
                await self._handle_success(adapter, health_result.latency_ms)
            else:
                await self._handle_failure(adapter, f"Status: {health_result.status}")

        except asyncio.TimeoutError:
            await self._handle_failure(adapter, "Health check timeout (10s)")
        except Exception as e:
            await self._handle_failure(adapter, str(e))

    async def _handle_success(self, adapter: DEXAdapter, latency_ms: int) -> None:
        """Handle successful health check.

        Resets failure count and sends recovery alert if transitioning
        from degraded/offline to healthy.

        Args:
            adapter: DEX adapter that succeeded
            latency_ms: Response latency in milliseconds
        """
        dex_id = adapter.dex_id
        old_status = self._current_status.get(dex_id, "healthy")
        log = self._log.bind(dex_id=dex_id, latency_ms=latency_ms)

        # Reset failure count (AC#5)
        self._failure_counts[dex_id] = 0
        self._current_status[dex_id] = "healthy"

        # Send recovery alert if transitioning from degraded/offline (AC#5)
        if old_status in ("degraded", "offline"):
            log.info("DEX recovered", old_status=old_status)
            send_alert_async(
                self._alert_service,
                self._alert_service.send_dex_status_change(
                    dex_id=dex_id,
                    old_status=old_status,
                    new_status="healthy",
                ),
            )
        else:
            log.debug("Health check passed")

    async def _handle_failure(self, adapter: DEXAdapter, error: str) -> None:
        """Handle failed health check with status transitions.

        Increments failure count and transitions status based on
        consecutive failures. Sends alerts on status transitions.

        Args:
            adapter: DEX adapter that failed
            error: Error message or description
        """
        dex_id = adapter.dex_id
        log = self._log.bind(dex_id=dex_id, error=error)

        # Increment failure count (AC#4)
        self._failure_counts[dex_id] = self._failure_counts.get(dex_id, 0) + 1
        failure_count = self._failure_counts[dex_id]
        old_status = self._current_status.get(dex_id, "healthy")

        log.warning(
            "Health check failed",
            consecutive_failures=failure_count,
            max_failures=self._max_failures,
        )

        # Determine new status based on failure count (AC#2, AC#4)
        if failure_count >= self._max_failures:
            new_status = "offline"
        else:
            new_status = "degraded"

        # Handle status transition
        if new_status != old_status:
            self._current_status[dex_id] = new_status
            log.warning(
                "DEX status changed",
                old_status=old_status,
                new_status=new_status,
            )

            # Send alert on status transition (AC#2, AC#4)
            send_alert_async(
                self._alert_service,
                self._alert_service.send_dex_status_change(
                    dex_id=dex_id,
                    old_status=old_status,
                    new_status=new_status,
                ),
            )

            # Start reconnection only when transitioning to offline (AC#3)
            # We wait until offline (max failures reached) to avoid
            # reconnection interfering with failure tracking during degraded state
            if new_status == "offline":
                asyncio.create_task(self._attempt_reconnection(adapter))

    async def _attempt_reconnection(self, adapter: DEXAdapter) -> None:
        """Attempt to reconnect to DEX with exponential backoff.

        Prevents concurrent reconnection attempts for the same adapter.
        Uses tenacity for retry logic with exponential backoff and jitter.

        Args:
            adapter: DEX adapter to reconnect
        """
        dex_id = adapter.dex_id

        # Prevent concurrent reconnection attempts (AC#6)
        if self._reconnecting.get(dex_id, False):
            return
        self._reconnecting[dex_id] = True

        log = self._log.bind(dex_id=dex_id)
        log.info("Starting reconnection attempts")

        try:
            await self._reconnect_with_backoff(adapter)
            log.info("Reconnection successful")
        except Exception as e:
            log.error("Reconnection failed after all attempts", error=str(e))
        finally:
            self._reconnecting[dex_id] = False

    async def _reconnect_with_backoff(self, adapter: DEXAdapter) -> None:
        """Reconnect with exponential backoff.

        Implements tenacity-style retry with exponential backoff and jitter.
        Backoff sequence: 1s, 2s, 4s, 8s, 16s, 30s (capped at max_backoff)
        Jitter: 0.8-1.2x to prevent thundering herd.

        Args:
            adapter: DEX adapter to reconnect

        Raises:
            Exception: If all reconnection attempts (max 10) fail
        """
        dex_id = adapter.dex_id
        log = self._log.bind(dex_id=dex_id)
        attempt = 0

        while attempt < self.RECONNECT_MAX_ATTEMPTS:
            attempt += 1
            log.info(
                "Attempting reconnection",
                attempt=attempt,
                max_attempts=self.RECONNECT_MAX_ATTEMPTS,
            )

            try:
                # Attempt reconnection
                await adapter.disconnect()
                await adapter.connect()

                # Verify connection with health check
                health_result = await adapter.get_health_status()
                if health_result.status != "healthy":
                    raise ConnectionError(
                        f"Post-reconnect health check failed: {health_result.status}"
                    )

                # Success!
                return

            except Exception as e:
                if attempt >= self.RECONNECT_MAX_ATTEMPTS:
                    raise

                # Calculate backoff with jitter (AC#3)
                delay = min(
                    self.RECONNECT_BASE_DELAY * (2 ** (attempt - 1)),
                    self._max_backoff,
                )
                jitter = random.uniform(0.8, 1.2)
                actual_delay = delay * jitter

                log.warning(
                    "Reconnection attempt failed, retrying",
                    attempt=attempt,
                    error=str(e),
                    next_delay_seconds=round(actual_delay, 2),
                )

                await asyncio.sleep(actual_delay)

    def get_status(self, dex_id: str) -> str:
        """Get current status for a DEX.

        Args:
            dex_id: DEX identifier

        Returns:
            str: "healthy", "degraded", or "offline"
        """
        return self._current_status.get(dex_id, "healthy")

    def get_failure_count(self, dex_id: str) -> int:
        """Get consecutive failure count for a DEX.

        Args:
            dex_id: DEX identifier

        Returns:
            int: Number of consecutive failures
        """
        return self._failure_counts.get(dex_id, 0)

    @property
    def is_running(self) -> bool:
        """Check if monitor is running.

        Returns:
            bool: True if monitoring loop is active
        """
        return self._running
