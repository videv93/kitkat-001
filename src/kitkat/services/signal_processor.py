"""Signal Processor service for parallel fan-out execution to DEX adapters (Story 2.9).

This module orchestrates signal execution across all configured DEX adapters in parallel.
Each signal is executed on all active (connected) adapters simultaneously, with results
collected and logged individually.
"""

import asyncio
import time
from decimal import Decimal
from datetime import datetime, timezone

import structlog

from kitkat.adapters.base import DEXAdapter
from kitkat.models import DEXExecutionResult, SignalPayload, SignalProcessorResponse
from kitkat.services.execution_service import ExecutionService

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
    ):
        """Initialize SignalProcessor with adapters and execution service.

        Args:
            adapters: List of configured DEX adapters (Extended, Mock, etc.)
            execution_service: Service for logging execution attempts
        """
        self._adapters = adapters
        self._execution_service = execution_service
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
    ) -> SignalProcessorResponse:
        """Process signal by executing on all active adapters in parallel.

        Uses asyncio.gather() with return_exceptions=True to execute all
        adapter calls concurrently. If one adapter fails or times out, others
        continue executing (graceful degradation).

        Args:
            signal: Validated signal payload (symbol, side, size)
            signal_id: Unique hash for deduplication/correlation

        Returns:
            SignalProcessorResponse with per-DEX results and overall status
        """
        log = self._log.bind(signal_id=signal_id)
        log.info("Processing signal", symbol=signal.symbol, side=signal.side)

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
                total_latency_ms=0,
                timestamp=datetime.now(timezone.utc),
            )

        # Create execution tasks for all active adapters
        tasks = [
            self._execute_on_adapter(adapter, signal, signal_id)
            for adapter in active_adapters
        ]

        # Execute in parallel with exception handling and timeout protection
        # 30 second timeout per signal to prevent indefinite hangs
        start_time = time.perf_counter()
        try:
            raw_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            log.error("Signal processing timeout - some adapters did not complete in time")
            total_latency = int((time.perf_counter() - start_time) * 1000)
            return SignalProcessorResponse(
                signal_id=signal_id,
                overall_status="failed",
                results=[],
                total_dex_count=len(active_adapters),
                successful_count=0,
                failed_count=len(active_adapters),
                total_latency_ms=total_latency,
                timestamp=datetime.now(timezone.utc),
            )

        total_latency = int((time.perf_counter() - start_time) * 1000)

        # Process results and log to ExecutionService
        processed_results = []
        for adapter, result in zip(active_adapters, raw_results):
            processed = await self._process_result(result, signal_id, adapter.dex_id)
            processed_results.append(processed)

        # Calculate overall status
        successful = sum(1 for r in processed_results if r.status in ("filled", "partial"))
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
            latency_ms=total_latency,
        )

        return SignalProcessorResponse(
            signal_id=signal_id,
            overall_status=overall_status,
            results=processed_results,
            total_dex_count=len(active_adapters),
            successful_count=successful,
            failed_count=failed,
            total_latency_ms=total_latency,
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
        log.info("Executing on DEX", symbol=signal.symbol, side=signal.side, size=str(signal.size))

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
                status="filled",
                order_id=result.order_id,
                filled_amount=result.filled_amount,
                error_message=None,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            log.error("DEX execution failed", error=str(e), latency_ms=latency_ms)

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
    ) -> DEXExecutionResult:
        """Process individual result, log to ExecutionService, handle exceptions.

        Converts exceptions from gather into error results and logs all
        outcomes to ExecutionService for audit trail.

        Args:
            result: Result from _execute_on_adapter (DEXExecutionResult or Exception)
            signal_id: Signal hash for correlation
            dex_id: DEX identifier for context

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

        # Log to ExecutionService
        await self._execution_service.log_execution(
            signal_id=signal_id,
            dex_id=result.dex_id,
            order_id=result.order_id,
            status=result.status,
            result_data={
                "filled_amount": str(result.filled_amount),
                "error_message": result.error_message,
            },
            latency_ms=result.latency_ms,
        )

        return result
