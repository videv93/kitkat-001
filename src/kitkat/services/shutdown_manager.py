"""Shutdown coordination service for graceful order completion (Story 2.11)."""

import asyncio
from contextlib import asynccontextmanager
from typing import Set

import structlog

logger = structlog.get_logger()


class ShutdownManager:
    """Manages graceful shutdown with in-flight order tracking.

    Core responsibilities:
    - Track in-flight orders (signal processing in progress)
    - Coordinate shutdown by waiting for in-flight orders to complete
    - Provide shutdown state for request rejection
    - Log shutdown progress and order completion
    """

    def __init__(self, grace_period_seconds: int = 30):
        """Initialize ShutdownManager.

        Args:
            grace_period_seconds: Maximum time to wait for in-flight orders (default: 30)
        """
        self._is_shutting_down = False
        self._in_flight: Set[str] = set()  # signal_ids currently processing
        self._grace_period = grace_period_seconds
        self._shutdown_event = asyncio.Event()
        self._log = logger.bind(service="shutdown_manager")

    @property
    def is_shutting_down(self) -> bool:
        """Return True if shutdown has been initiated."""
        return self._is_shutting_down

    @property
    def in_flight_count(self) -> int:
        """Return count of currently processing orders."""
        return len(self._in_flight)

    @asynccontextmanager
    async def track_in_flight(self, signal_id: str):
        """Context manager to track in-flight signal processing.

        Usage:
            async with shutdown_manager.track_in_flight(signal_id):
                result = await signal_processor.process_signal(...)

        Args:
            signal_id: Unique signal identifier for tracking
        """
        self._in_flight.add(signal_id)
        self._log.debug("Order started", signal_id=signal_id, in_flight=len(self._in_flight))
        try:
            yield
        finally:
            self._in_flight.discard(signal_id)
            remaining = len(self._in_flight)

            if self._is_shutting_down:
                self._log.info(
                    "Order completed during shutdown",
                    signal_id=signal_id,
                    remaining=remaining,
                )
                # Signal completion for waiters
                if remaining == 0:
                    self._shutdown_event.set()

    def initiate_shutdown(self) -> None:
        """Mark shutdown as initiated - new requests will be rejected."""
        self._is_shutting_down = True
        self._log.info(
            "Shutdown initiated",
            in_flight_count=len(self._in_flight),
            grace_period_seconds=self._grace_period,
        )

    async def wait_for_completion(self) -> bool:
        """Wait for all in-flight orders to complete or timeout.

        Returns:
            bool: True if all orders completed, False if timeout occurred
        """
        if len(self._in_flight) == 0:
            self._log.info("No in-flight orders - immediate shutdown")
            return True

        self._log.info(
            "Waiting for in-flight orders",
            count=len(self._in_flight),
            signal_ids=list(self._in_flight),
            timeout_seconds=self._grace_period,
        )

        try:
            # Wait for either all orders to complete or timeout
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=self._grace_period,
            )
            self._log.info("All in-flight orders completed - clean shutdown")
            return True
        except asyncio.TimeoutError:
            self._log.warning(
                "Shutdown grace period expired",
                pending_count=len(self._in_flight),
                pending_signals=list(self._in_flight),
            )
            return False

    def get_in_flight_signals(self) -> list[str]:
        """Return list of currently in-flight signal IDs."""
        return list(self._in_flight)
