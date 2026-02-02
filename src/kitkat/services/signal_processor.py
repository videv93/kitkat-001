"""Signal Processor service for parallel fan-out execution to DEX adapters (Story 2.9).

This module orchestrates signal execution across all configured DEX adapters in parallel.
Each signal is executed on all active (connected) adapters simultaneously, with results
collected and logged individually.

Story 3.3: Logs is_test_mode flag in execution result_data for filtering test executions.
Story 4.2: Sends Telegram alerts on execution failures and partial fills.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import structlog

from kitkat.adapters.base import DEXAdapter
from kitkat.config import get_settings
from kitkat.logging import ErrorType
from kitkat.models import DEXExecutionResult, SignalPayload, SignalProcessorResponse
from kitkat.services.error_logger import get_error_logger
from kitkat.services.execution_service import ExecutionService

if TYPE_CHECKING:
    from kitkat.services.alert import TelegramAlertService

logger = structlog.get_logger()


class SignalProcessor:
    """Orchestrates signal execution across all configured DEX adapters.

    Core responsibilities:
    - Identify active (connected) adapters
    - Fan-out execution to all adapters in parallel
    - Collect results and log to ExecutionService
    - Return aggregated per-DEX status

    Uses asyncio.gather() for true parallel execution ensuring one slow DEX
    doesn't block others.
    """

    def __init__(
        self,
        adapters: list[DEXAdapter],
        execution_service: ExecutionService,
        alert_service: Optional["TelegramAlertService"] = None,
    ):
        """Initialize SignalProcessor with adapters and execution service.

        Args:
            adapters: List of configured DEX adapters (Extended, Mock, etc.)
            execution_service: Service for logging execution attempts
            alert_service: Optional Telegram alert service for failure notifications (Story 4.2)
        """
        self._adapters = adapters
        self._execution_service = execution_service
        self._alert_service = alert_service
        self._log = structlog.get_logger().bind(service="signal_processor")

    def get_active_adapters(self) -> list[DEXAdapter]:
        """Return only adapters that are currently connected.

        Returns:
            list[DEXAdapter]: Adapters that are currently connected
        """
        return [adapter for adapter in self._adapters if adapter.is_connected]

    async def process_signal(
        self,
        signal: SignalPayload,
        signal_id: str,
        max_position_size: Decimal | None = None,
    ) -> SignalProcessorResponse:
        """Process signal by executing on all active adapters in parallel.

        Uses asyncio.gather() with return_exceptions=True to execute all
        adapter calls concurrently. If one adapter fails or times out, others
        continue executing (graceful degradation).

        Story 5.6: If max_position_size is specified and signal.size exceeds it,
        the signal is rejected without executing on any DEX (AC#5).

        Args:
            signal: Validated signal payload (symbol, side, size)
            signal_id: Unique hash for deduplication/correlation
            max_position_size: Optional user-configured maximum position size.
                               If signal.size > max_position_size, signal is rejected.

        Returns:
            SignalProcessorResponse with per-DEX results and overall status
        """
        log = self._log.bind(signal_id=signal_id)
        log.info("Processing signal", symbol=signal.symbol, side=signal.side)

        # Story 5.6: Position size validation (AC#5)
        if max_position_size is not None and signal.size > max_position_size:
            log.warning(
                "Signal size exceeds configured maximum",
                signal_size=str(signal.size),
                max_allowed=str(max_position_size),
            )
            # Return rejection response - signal is logged but NOT executed
            return SignalProcessorResponse(
                signal_id=signal_id,
                overall_status="rejected",
                results=[
                    DEXExecutionResult(
                        dex_id="system",
                        status="rejected",
                        order_id=None,
                        filled_amount=Decimal("0"),
                        error_message=f"Position size {signal.size} exceeds configured maximum {max_position_size}",
                        latency_ms=0,
                    )
                ],
                total_dex_count=0,
                successful_count=0,
                failed_count=0,
                timestamp=datetime.now(timezone.utc),
            )

        active_adapters = self.get_active_adapters()
        if not active_adapters:
            log.warning("No active adapters available")
            return SignalProcessorResponse(
                signal_id=signal_id,
                overall_status="failed",
                results=[],
                total_dex_count=0,
                successful_count=0,
                failed_count=0,
                timestamp=datetime.now(timezone.utc),
            )

        # Create execution tasks for all active adapters
        tasks = [
            self._execute_on_adapter(adapter, signal, signal_id)
            for adapter in active_adapters
        ]

        # Execute in parallel with exception handling and timeout protection
        # 30 second timeout per signal to prevent indefinite hangs
        try:
            raw_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=30.0
            )
        except asyncio.TimeoutError:
            log.error(
                "Signal processing timeout - some adapters did not complete in time"
            )
            return SignalProcessorResponse(
                signal_id=signal_id,
                overall_status="failed",
                results=[],
                total_dex_count=len(active_adapters),
                successful_count=0,
                failed_count=len(active_adapters),
                timestamp=datetime.now(timezone.utc),
            )

        # Process results and log to ExecutionService
        processed_results = []
        for adapter, result in zip(active_adapters, raw_results):
            processed = await self._process_result(
                result, signal_id, adapter.dex_id, signal
            )
            processed_results.append(processed)

        # Calculate overall status
        successful = sum(
            1 for r in processed_results if r.status in ("filled", "partial")
        )
        failed = sum(1 for r in processed_results if r.status in ("failed", "error"))

        if successful == len(processed_results):
            overall_status = "success"
        elif successful > 0:
            overall_status = "partial"
        else:
            overall_status = "failed"

        log.info(
            "Signal processing complete",
            overall_status=overall_status,
            successful=successful,
            failed=failed,
        )

        return SignalProcessorResponse(
            signal_id=signal_id,
            overall_status=overall_status,
            results=processed_results,
            total_dex_count=len(active_adapters),
            successful_count=successful,
            failed_count=failed,
            timestamp=datetime.now(timezone.utc),
        )

    async def _execute_on_adapter(
        self,
        adapter: DEXAdapter,
        signal: SignalPayload,
        signal_id: str,
    ) -> DEXExecutionResult:
        """Execute signal on single adapter with timing and error handling.

        Args:
            adapter: DEX adapter to execute on
            signal: Signal payload (symbol, side, size)
            signal_id: Signal hash for correlation

        Returns:
            DEXExecutionResult with execution status and latency
        """
        log = self._log.bind(signal_id=signal_id, dex_id=adapter.dex_id)
        log.info(
            "Executing on DEX",
            symbol=signal.symbol,
            side=signal.side,
            size=str(signal.size),
        )

        start_time = time.perf_counter()
        try:
            result = await adapter.execute_order(
                symbol=signal.symbol,
                side=signal.side,
                size=signal.size,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            log.info(
                "DEX execution succeeded",
                order_id=result.order_id,
                latency_ms=latency_ms,
            )

            return DEXExecutionResult(
                dex_id=adapter.dex_id,
                status="filled",  # Order successfully submitted; fill status updated via WebSocket (Story 2.8)
                order_id=result.order_id,
                filled_amount=result.filled_amount,
                error_message=None,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            log.error("DEX execution failed", error=str(e), latency_ms=latency_ms)

            # Story 4.4: Log execution error with full context (AC#1, AC#2)
            get_error_logger().log_execution_error(
                signal_id=signal_id,
                dex_id=adapter.dex_id,
                error_type=ErrorType.EXECUTION_FAILED,
                error_message=str(e),
                symbol=signal.symbol,
                side=signal.side,
                size=str(signal.size),
                latency_ms=latency_ms,
            )

            return DEXExecutionResult(
                dex_id=adapter.dex_id,
                status="error",
                order_id=None,
                filled_amount=Decimal("0"),
                error_message=str(e),
                latency_ms=latency_ms,
            )

    async def _process_result(
        self,
        result: DEXExecutionResult | Exception,
        signal_id: str,
        dex_id: str,
        signal: Optional[SignalPayload] = None,
    ) -> DEXExecutionResult:
        """Process individual result, log to ExecutionService, handle exceptions.

        Converts exceptions from gather into error results and logs all
        outcomes to ExecutionService for audit trail.

        Story 3.3: Adds is_test_mode flag to result_data for database filtering.
        Story 4.2: Sends Telegram alerts on failures and partial fills (fire-and-forget).

        Args:
            result: Result from _execute_on_adapter (DEXExecutionResult or Exception)
            signal_id: Signal hash for correlation
            dex_id: DEX identifier for context
            signal: Original signal payload for partial fill context (Story 4.2)

        Returns:
            DEXExecutionResult (either original or converted from exception)
        """
        # Handle exceptions from gather
        if isinstance(result, Exception):
            result = DEXExecutionResult(
                dex_id=dex_id,
                status="error",
                order_id=None,
                filled_amount=Decimal("0"),
                error_message=str(result),
                latency_ms=0,
            )

        # Story 3.3: Get test_mode flag for execution logging (AC#4)
        settings = get_settings()

        # Log to ExecutionService with is_test_mode flag (Story 3.3: AC#4)
        await self._execution_service.log_execution(
            signal_id=signal_id,
            dex_id=result.dex_id,
            order_id=result.order_id,
            status=result.status,
            result_data={
                "filled_amount": str(result.filled_amount),
                "error_message": result.error_message,
                "is_test_mode": settings.test_mode,  # AC#4 - Add flag for filtering
            },
            latency_ms=result.latency_ms,
        )

        # Story 4.2: Send Telegram alerts on failures/errors (AC#3, AC#4)
        if self._alert_service and result.status in ("failed", "error"):
            asyncio.create_task(
                self._alert_service.send_execution_failure(
                    signal_id=signal_id,
                    dex_id=result.dex_id,
                    error_message=result.error_message or "Unknown error",
                )
            )

        # Story 4.2: Send Telegram alerts on partial fills (AC#5, AC#4)
        if self._alert_service and result.status == "partial" and signal:
            remaining = signal.size - result.filled_amount
            asyncio.create_task(
                self._alert_service.send_partial_fill(
                    symbol=signal.symbol,
                    filled_size=str(result.filled_amount),
                    remaining_size=str(remaining),
                    dex_id=result.dex_id,
                )
            )

        return result
