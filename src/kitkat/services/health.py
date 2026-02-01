"""Health service for aggregating DEX adapter status (Story 4.1).

This module provides the HealthService that orchestrates health checks across
all configured DEX adapters and aggregates their status into an overall system
health snapshot.

Key responsibilities:
- Query each adapter's health_check() method in parallel
- Track errors over a 5-minute rolling window
- Aggregate per-DEX status with latency and error counts
- Determine overall system status (healthy/degraded/offline)
- Provide uptime tracking since service startup
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

from kitkat.adapters.base import DEXAdapter
from kitkat.models import DEXHealth, SystemHealth

logger = structlog.get_logger()


class HealthService:
    """Aggregates health status from all DEX adapters.

    Maintains error tracking with a 5-minute rolling window and provides
    real-time health snapshots of all configured adapters and the overall
    system health.

    Story 4.1: Health Service & DEX Status
    - AC#1: Health service aggregates status from all adapters
    - AC#3: Queries each adapter via health_check() and aggregates
    - AC#5: Implements status aggregation logic
    """

    def __init__(self, adapters: list[DEXAdapter]):
        """Initialize health service with list of adapters to monitor.

        Args:
            adapters: List of DEX adapters (e.g., [ExtendedAdapter, MockAdapter])
        """
        self._adapters = adapters
        self._error_tracker: dict[str, list[tuple[datetime, str]]] = {}
        self._start_time = datetime.now(timezone.utc)
        self._log = logger.bind(service="health")

    async def get_system_health(self) -> SystemHealth:
        """Get aggregated health status from all adapters.

        Queries each adapter's health_check() method in parallel and aggregates
        results into per-DEX status objects with error counts.

        Returns:
            SystemHealth: Overall system health with per-DEX status and timestamp

        Status Logic (AC#5):
        - healthy: All DEXs healthy OR no DEXs configured
        - degraded: At least one healthy AND at least one unhealthy
        - offline: All DEXs offline OR no adapters
        """
        dex_statuses: dict[str, DEXHealth] = {}

        # Query each adapter in parallel (AC#3)
        if not self._adapters:
            overall_status = "healthy"
        else:
            tasks = [adapter.health_check() for adapter in self._adapters]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for adapter, result in zip(self._adapters, results):
                if isinstance(result, Exception):
                    # Health check failed - track error (AC#3)
                    error_message = str(result)
                    self._track_error(adapter.dex_id, "health_check_failed")
                    self._log.warning(
                        "Health check failed",
                        dex_id=adapter.dex_id,
                        error=error_message,
                    )
                    dex_statuses[adapter.dex_id] = DEXHealth(
                        dex_id=adapter.dex_id,
                        status="offline",
                        latency_ms=None,
                        last_successful=None,
                        error_count=self._get_error_count(adapter.dex_id),
                        error_message=error_message,
                    )
                else:
                    # Success - reset error count (AC#3)
                    self._clear_errors(adapter.dex_id)
                    dex_statuses[adapter.dex_id] = DEXHealth(
                        dex_id=adapter.dex_id,
                        status=result.status,
                        latency_ms=result.latency_ms,
                        last_successful=datetime.now(timezone.utc),
                        error_count=0,
                        error_message=None,
                    )

            # Aggregate overall status (AC#5)
            overall_status = self._aggregate_status(dex_statuses)

        return SystemHealth(
            status=overall_status,
            components=dex_statuses,
            timestamp=datetime.now(timezone.utc),
        )

    def _aggregate_status(self, dex_statuses: dict[str, DEXHealth]) -> str:
        """Determine overall status from DEX statuses (AC#5).

        Status Logic:
        - healthy: All DEXs healthy OR no DEXs configured
        - degraded: At least one healthy AND at least one unhealthy
        - offline: All DEXs offline OR no adapters

        Args:
            dex_statuses: Dict mapping dex_id to DEXHealth status

        Returns:
            str: Overall status (healthy, degraded, or offline)
        """
        if not dex_statuses:
            return "healthy"

        statuses = [dex.status for dex in dex_statuses.values()]

        if all(s == "healthy" for s in statuses):
            return "healthy"
        elif all(s == "offline" for s in statuses):
            return "offline"
        else:
            return "degraded"

    def _track_error(self, dex_id: str, error_code: str) -> None:
        """Track error with timestamp for 5-minute rolling window (AC#3).

        Args:
            dex_id: DEX identifier
            error_code: Error code for categorization
        """
        if dex_id not in self._error_tracker:
            self._error_tracker[dex_id] = []

        now = datetime.now(timezone.utc)
        self._error_tracker[dex_id].append((now, error_code))
        self._cleanup_old_errors(dex_id)

    def _cleanup_old_errors(self, dex_id: str) -> None:
        """Remove errors older than 5 minutes (AC#3).

        Args:
            dex_id: DEX identifier
        """
        now = datetime.now(timezone.utc)
        five_minutes_ago = now - timedelta(minutes=5)

        if dex_id in self._error_tracker:
            self._error_tracker[dex_id] = [
                (ts, code)
                for ts, code in self._error_tracker[dex_id]
                if ts > five_minutes_ago
            ]

    def _get_error_count(self, dex_id: str) -> int:
        """Get count of errors in last 5 minutes (AC#3).

        Args:
            dex_id: DEX identifier

        Returns:
            int: Number of errors in last 5 minutes
        """
        self._cleanup_old_errors(dex_id)
        return len(self._error_tracker.get(dex_id, []))

    def _clear_errors(self, dex_id: str) -> None:
        """Clear error tracker on successful health check.

        Args:
            dex_id: DEX identifier
        """
        self._error_tracker[dex_id] = []

    @property
    def uptime_seconds(self) -> int:
        """Get seconds since service started.

        Returns:
            int: Uptime in seconds
        """
        elapsed = datetime.now(timezone.utc) - self._start_time
        return int(elapsed.total_seconds())
