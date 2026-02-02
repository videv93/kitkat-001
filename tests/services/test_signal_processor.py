"""Tests for SignalProcessor service."""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.adapters.base import DEXAdapter
from kitkat.models import (
    DEXExecutionResult,
    OrderSubmissionResult,
    SignalPayload,
    SignalProcessorResponse,
)
from kitkat.services.execution_service import ExecutionService
from kitkat.services.signal_processor import SignalProcessor


class MockDEXAdapter(DEXAdapter):
    """Mock DEX adapter for testing."""

    def __init__(self, dex_id: str = "mock", delay_ms: int = 10, fail: bool = False):
        self.dex_id_val = dex_id
        self._connected = True
        self.delay_ms = delay_ms
        self.fail = fail
        self.execute_order_calls = []

    @property
    def dex_id(self) -> str:
        return self.dex_id_val

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self, params=None) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def execute_order(self, symbol: str, side: str, size: Decimal) -> OrderSubmissionResult:
        """Execute order with optional delay and failure."""
        # Record call for assertion
        self.execute_order_calls.append({
            "symbol": symbol,
            "side": side,
            "size": size,
        })

        # Simulate latency
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)

        if self.fail:
            raise RuntimeError(f"DEX {self.dex_id} execution failed")

        return OrderSubmissionResult(
            order_id=f"{self.dex_id}-order-123",
            status="submitted",
            submitted_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            filled_amount=Decimal("0"),  # No fill yet - comes from WebSocket updates
            dex_response={"status": "ok"},
        )

    async def get_order_status(self, order_id: str):
        raise NotImplementedError()

    async def get_position(self, symbol: str):
        raise NotImplementedError()

    async def cancel_order(self, order_id: str) -> None:
        raise NotImplementedError()

    async def get_health_status(self):
        raise NotImplementedError()


class MockExecutionService:
    """Mock ExecutionService for testing."""

    def __init__(self):
        self.log_calls = []

    async def log_execution(
        self,
        signal_id: str,
        dex_id: str,
        order_id: str | None,
        status: str,
        result_data: dict,
        latency_ms: int | None = None,
    ):
        self.log_calls.append({
            "signal_id": signal_id,
            "dex_id": dex_id,
            "order_id": order_id,
            "status": status,
            "result_data": result_data,
            "latency_ms": latency_ms,
        })
        return MagicMock()


@pytest.mark.asyncio
async def test_process_signal_single_adapter_success():
    """Test processing signal with single adapter success."""
    adapter = MockDEXAdapter("extended", delay_ms=10)
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.5"))
    response = await processor.process_signal(signal, "signal-123")

    assert response.signal_id == "signal-123"
    assert response.overall_status == "success"
    assert len(response.results) == 1
    assert response.results[0].dex_id == "extended"
    assert response.results[0].status == "filled"
    assert response.results[0].order_id == "extended-order-123"
    assert response.total_dex_count == 1
    assert response.successful_count == 1
    assert response.failed_count == 0


@pytest.mark.asyncio
async def test_process_signal_multiple_adapters_all_success():
    """Test processing signal with multiple adapters all succeeding."""
    adapter1 = MockDEXAdapter("extended", delay_ms=10)
    adapter2 = MockDEXAdapter("mock", delay_ms=5)
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter1, adapter2], exec_service)

    signal = SignalPayload(symbol="BTC/USD", side="sell", size=Decimal("0.5"))
    response = await processor.process_signal(signal, "signal-456")

    assert response.signal_id == "signal-456"
    assert response.overall_status == "success"
    assert len(response.results) == 2
    assert response.total_dex_count == 2
    assert response.successful_count == 2
    assert response.failed_count == 0

    # Verify both adapters were called
    assert len(adapter1.execute_order_calls) == 1
    assert len(adapter2.execute_order_calls) == 1


@pytest.mark.asyncio
async def test_process_signal_partial_failure():
    """Test graceful degradation when one DEX fails."""
    adapter1 = MockDEXAdapter("extended", delay_ms=10, fail=False)
    adapter2 = MockDEXAdapter("paradex", delay_ms=10, fail=True)
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter1, adapter2], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("2.0"))
    response = await processor.process_signal(signal, "signal-789")

    assert response.overall_status == "partial"
    assert response.total_dex_count == 2
    assert response.successful_count == 1
    assert response.failed_count == 1

    # Verify results
    results_by_dex = {r.dex_id: r for r in response.results}
    assert results_by_dex["extended"].status == "filled"
    assert results_by_dex["paradex"].status == "error"


@pytest.mark.asyncio
async def test_process_signal_all_fail():
    """Test when all adapters fail."""
    adapter1 = MockDEXAdapter("extended", fail=True)
    adapter2 = MockDEXAdapter("mock", fail=True)
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter1, adapter2], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "signal-999")

    assert response.overall_status == "failed"
    assert response.total_dex_count == 2
    assert response.successful_count == 0
    assert response.failed_count == 2


@pytest.mark.asyncio
async def test_process_signal_no_active_adapters():
    """Test handling when no adapters are active/connected."""
    adapter = MockDEXAdapter("extended")
    adapter._connected = False  # Mark as disconnected
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "signal-empty")

    assert response.overall_status == "failed"
    assert len(response.results) == 0
    assert response.total_dex_count == 0
    assert response.successful_count == 0
    assert response.failed_count == 0


@pytest.mark.asyncio
async def test_get_active_adapters_filters_disconnected():
    """Test that get_active_adapters only returns connected adapters."""
    adapter1 = MockDEXAdapter("extended")
    adapter2 = MockDEXAdapter("mock")
    adapter1._connected = True
    adapter2._connected = False

    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter1, adapter2], exec_service)

    active = processor.get_active_adapters()
    assert len(active) == 1
    assert active[0].dex_id == "extended"


@pytest.mark.asyncio
async def test_parallel_execution_timing():
    """Verify that gather executes in parallel (not sequential)."""
    # Two adapters with 50ms latency each
    # If sequential: total ~100ms
    # If parallel: total ~50ms
    adapter1 = MockDEXAdapter("extended", delay_ms=50)
    adapter2 = MockDEXAdapter("mock", delay_ms=50)
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter1, adapter2], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))

    import time
    start = time.perf_counter()
    response = await processor.process_signal(signal, "signal-timing")
    elapsed = (time.perf_counter() - start) * 1000  # ms

    # Should be closer to 50ms than 100ms (allow 20ms variance)
    # This proves parallel execution
    assert elapsed < 100, f"Execution took {elapsed}ms, expected <100ms (parallel)"


@pytest.mark.asyncio
async def test_exception_handling_in_gather():
    """Test that exceptions from gather are properly handled."""
    # Create adapter that raises immediately without latency
    adapter = MockDEXAdapter("extended", fail=True, delay_ms=0)
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "signal-exc")

    assert response.overall_status == "failed"
    assert response.results[0].status == "error"
    assert response.results[0].error_message is not None


@pytest.mark.asyncio
async def test_latency_measurement_accuracy():
    """Verify that latency is measured accurately."""
    adapter = MockDEXAdapter("extended", delay_ms=50)
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "signal-latency")

    # Latency should be approximately 50ms (allow +/- 20ms variance)
    result_latency = response.results[0].latency_ms
    assert 30 <= result_latency <= 70, f"Latency {result_latency}ms not in expected range [30, 70]"


@pytest.mark.asyncio
async def test_execution_service_called_for_each_result():
    """Verify that ExecutionService.log_execution is called for each result."""
    adapter1 = MockDEXAdapter("extended")
    adapter2 = MockDEXAdapter("mock")
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter1, adapter2], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "signal-log")

    # Should have logged once for each adapter
    assert len(exec_service.log_calls) == 2

    # Check log call contents
    log1, log2 = exec_service.log_calls
    assert log1["signal_id"] == "signal-log"
    assert log2["signal_id"] == "signal-log"
    assert log1["dex_id"] in ("extended", "mock")
    assert log2["dex_id"] in ("extended", "mock")
    assert log1["status"] == "filled"
    assert log2["status"] == "filled"


@pytest.mark.asyncio
async def test_signal_payload_passed_correctly_to_adapter():
    """Verify that signal payload is passed correctly to each adapter."""
    adapter = MockDEXAdapter("extended")
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(symbol="BTC/USDT", side="sell", size=Decimal("0.123"))
    response = await processor.process_signal(signal, "signal-payload")

    # Check that adapter received correct payload
    assert len(adapter.execute_order_calls) == 1
    call = adapter.execute_order_calls[0]
    assert call["symbol"] == "BTC/USDT"
    assert call["side"] == "sell"
    assert call["size"] == Decimal("0.123")


@pytest.mark.asyncio
async def test_response_model_structure():
    """Verify that response has correct structure and types."""
    adapter = MockDEXAdapter("extended")
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "signal-struct")

    # Validate response structure
    assert isinstance(response, SignalProcessorResponse)
    assert isinstance(response.signal_id, str)
    assert response.overall_status in ("success", "partial", "failed")
    assert isinstance(response.results, list)
    assert isinstance(response.total_dex_count, int)
    assert isinstance(response.successful_count, int)
    assert isinstance(response.failed_count, int)

    # Validate each result
    for result in response.results:
        assert isinstance(result, DEXExecutionResult)
        assert isinstance(result.dex_id, str)
        assert result.status in ("filled", "partial", "failed", "error")
        assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_signal_id_preserved_in_logs():
    """Verify that signal_id is preserved and used in logging."""
    adapter = MockDEXAdapter("extended")
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "unique-signal-id-123")

    # Verify signal_id is in response
    assert response.signal_id == "unique-signal-id-123"

    # Verify signal_id was passed to execution service
    assert len(exec_service.log_calls) == 1
    assert exec_service.log_calls[0]["signal_id"] == "unique-signal-id-123"


@pytest.mark.asyncio
async def test_decimal_amounts_preserved():
    """Verify that Decimal amounts are preserved correctly."""
    adapter = MockDEXAdapter("extended")
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    # Test with various Decimal values
    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.23456789"))
    response = await processor.process_signal(signal, "signal-decimal")

    result = response.results[0]
    # Note: filled_amount is 0 at submission time - actual fills come via WebSocket (Story 2.8)
    # This test validates that Decimal handling works, not that fills happen immediately
    assert result.filled_amount == Decimal("0")
    # Verify the signal size was passed correctly to the adapter
    assert adapter.execute_order_calls[0]["size"] == Decimal("1.23456789")


@pytest.mark.asyncio
async def test_error_message_captured():
    """Verify that error messages are captured on failure."""
    adapter = MockDEXAdapter("extended", fail=True)
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "signal-error")

    result = response.results[0]
    assert result.status == "error"
    assert result.error_message is not None
    assert "DEX extended execution failed" in result.error_message
    assert result.order_id is None


# Story 4.2: Tests for TelegramAlertService integration
class MockAlertService:
    """Mock TelegramAlertService for testing."""

    def __init__(self):
        self.execution_failure_calls = []
        self.partial_fill_calls = []

    async def send_execution_failure(
        self, signal_id: str, dex_id: str, error_message: str, timestamp=None
    ):
        self.execution_failure_calls.append({
            "signal_id": signal_id,
            "dex_id": dex_id,
            "error_message": error_message,
        })

    async def send_partial_fill(
        self, symbol: str, filled_size: str, remaining_size: str, dex_id: str
    ):
        self.partial_fill_calls.append({
            "symbol": symbol,
            "filled_size": filled_size,
            "remaining_size": remaining_size,
            "dex_id": dex_id,
        })


@pytest.mark.asyncio
async def test_alert_sent_on_execution_failure():
    """Story 4.2: AC#3 - Alert sent on execution failure."""
    adapter = MockDEXAdapter("extended", fail=True)
    exec_service = MockExecutionService()
    alert_service = MockAlertService()
    processor = SignalProcessor([adapter], exec_service, alert_service=alert_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    await processor.process_signal(signal, "signal-fail-alert")

    # Allow time for asyncio.create_task to complete
    await asyncio.sleep(0.05)

    assert len(alert_service.execution_failure_calls) == 1
    call = alert_service.execution_failure_calls[0]
    assert call["signal_id"] == "signal-fail-alert"
    assert call["dex_id"] == "extended"
    assert "DEX extended execution failed" in call["error_message"]


@pytest.mark.asyncio
async def test_no_alert_on_success():
    """Story 4.2: No alert sent when execution succeeds."""
    adapter = MockDEXAdapter("extended", fail=False)
    exec_service = MockExecutionService()
    alert_service = MockAlertService()
    processor = SignalProcessor([adapter], exec_service, alert_service=alert_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    await processor.process_signal(signal, "signal-success")

    await asyncio.sleep(0.05)

    assert len(alert_service.execution_failure_calls) == 0
    assert len(alert_service.partial_fill_calls) == 0


@pytest.mark.asyncio
async def test_alert_per_failed_adapter():
    """Story 4.2: Each failed adapter triggers its own alert."""
    adapter1 = MockDEXAdapter("dex1", fail=True)
    adapter2 = MockDEXAdapter("dex2", fail=True)
    exec_service = MockExecutionService()
    alert_service = MockAlertService()
    processor = SignalProcessor([adapter1, adapter2], exec_service, alert_service=alert_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    await processor.process_signal(signal, "signal-multi-fail")

    await asyncio.sleep(0.05)

    assert len(alert_service.execution_failure_calls) == 2
    dex_ids = {call["dex_id"] for call in alert_service.execution_failure_calls}
    assert dex_ids == {"dex1", "dex2"}


@pytest.mark.asyncio
async def test_alert_service_optional():
    """Story 4.2: AC#7 - System works without alert service (graceful degradation)."""
    adapter = MockDEXAdapter("extended", fail=True)
    exec_service = MockExecutionService()
    # No alert_service provided
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    # Should not raise any errors
    response = await processor.process_signal(signal, "signal-no-alert")

    assert response.overall_status == "failed"
    assert response.failed_count == 1


@pytest.mark.asyncio
async def test_partial_fill_alert_sent():
    """Story 4.2: AC#5 - Alert sent on partial fill.

    Note: In production, partial status comes from WebSocket updates (Story 2.8).
    This test directly invokes _process_result with a partial status to verify
    the alert integration works correctly.
    """
    exec_service = MockExecutionService()
    alert_service = MockAlertService()
    processor = SignalProcessor([], exec_service, alert_service=alert_service)

    # Create a partial fill result directly
    partial_result = DEXExecutionResult(
        dex_id="extended",
        status="partial",
        order_id="order-123",
        filled_amount=Decimal("0.3"),
        error_message=None,
        latency_ms=50,
    )

    # Create signal for context
    signal = SignalPayload(symbol="ETH-PERP", side="buy", size=Decimal("1.0"))

    # Invoke _process_result directly to test the partial fill alert path
    await processor._process_result(partial_result, "signal-partial", "extended", signal)

    # Allow time for asyncio.create_task to complete
    await asyncio.sleep(0.05)

    # Verify partial fill alert was sent
    assert len(alert_service.partial_fill_calls) == 1
    call = alert_service.partial_fill_calls[0]
    assert call["symbol"] == "ETH-PERP"
    assert call["filled_size"] == "0.3"
    assert call["remaining_size"] == "0.7"  # 1.0 - 0.3 = 0.7
    assert call["dex_id"] == "extended"


@pytest.mark.asyncio
async def test_no_partial_fill_alert_without_signal():
    """Story 4.2: No partial fill alert if signal context is missing.

    The partial fill alert requires signal context to calculate remaining size.
    If signal is None, no alert should be sent.
    """
    exec_service = MockExecutionService()
    alert_service = MockAlertService()
    processor = SignalProcessor([], exec_service, alert_service=alert_service)

    # Create a partial fill result
    partial_result = DEXExecutionResult(
        dex_id="extended",
        status="partial",
        order_id="order-123",
        filled_amount=Decimal("0.3"),
        error_message=None,
        latency_ms=50,
    )

    # Invoke _process_result without signal context
    await processor._process_result(partial_result, "signal-partial", "extended", None)

    await asyncio.sleep(0.05)

    # No alert should be sent since signal is None
    assert len(alert_service.partial_fill_calls) == 0


# ============================================================================
# Story 5.6: Position Size Validation Tests (AC#5)
# ============================================================================


@pytest.mark.asyncio
async def test_signal_rejected_when_size_exceeds_max():
    """Story 5.6: AC#5 - Signal rejected if size > max_position_size."""
    adapter = MockDEXAdapter("extended", delay_ms=10)
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(
        symbol="ETH-PERP",
        side="buy",
        size=Decimal("15.0"),  # Exceeds limit of 5.0
    )

    # Process with max_position_size constraint
    response = await processor.process_signal(
        signal=signal,
        signal_id="signal-size-exceed",
        max_position_size=Decimal("5.0"),
    )

    # Should be rejected
    assert response.overall_status == "rejected"
    assert response.signal_id == "signal-size-exceed"

    # DEX adapter should NOT be called
    assert len(adapter.execute_order_calls) == 0


@pytest.mark.asyncio
async def test_signal_rejected_returns_correct_error_message():
    """Story 5.6: AC#5 - Rejected signal includes error message."""
    adapter = MockDEXAdapter("extended")
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(
        symbol="BTC-PERP",
        side="sell",
        size=Decimal("100.0"),  # Exceeds limit
    )

    response = await processor.process_signal(
        signal=signal,
        signal_id="signal-reject-msg",
        max_position_size=Decimal("10.0"),
    )

    assert response.overall_status == "rejected"
    # Check that rejection is logged in results
    assert len(response.results) == 1
    assert response.results[0].status == "rejected"
    assert "exceeds configured maximum" in response.results[0].error_message.lower()


@pytest.mark.asyncio
async def test_signal_rejected_logged_not_executed():
    """Story 5.6: AC#5 - Rejected signal is logged but NOT executed on DEX."""
    adapter1 = MockDEXAdapter("extended")
    adapter2 = MockDEXAdapter("mock")
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter1, adapter2], exec_service)

    signal = SignalPayload(
        symbol="ETH-PERP",
        side="buy",
        size=Decimal("50.0"),  # Exceeds limit
    )

    response = await processor.process_signal(
        signal=signal,
        signal_id="signal-no-exec",
        max_position_size=Decimal("10.0"),
    )

    # Rejection should be recorded
    assert response.overall_status == "rejected"

    # NO adapters should have been called
    assert len(adapter1.execute_order_calls) == 0
    assert len(adapter2.execute_order_calls) == 0

    # Execution service should NOT have logged normal executions
    # (only the rejection should be tracked)
    assert len(exec_service.log_calls) == 0


@pytest.mark.asyncio
async def test_signal_accepted_when_size_within_limit():
    """Story 5.6: Signal processed normally when size <= max_position_size."""
    adapter = MockDEXAdapter("extended")
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(
        symbol="ETH-PERP",
        side="buy",
        size=Decimal("5.0"),  # Exactly at limit
    )

    response = await processor.process_signal(
        signal=signal,
        signal_id="signal-within-limit",
        max_position_size=Decimal("5.0"),
    )

    # Should be processed normally
    assert response.overall_status == "success"

    # Adapter should have been called
    assert len(adapter.execute_order_calls) == 1


@pytest.mark.asyncio
async def test_signal_processed_without_max_position_size():
    """Story 5.6: Signal processed normally when no max_position_size specified."""
    adapter = MockDEXAdapter("extended")
    exec_service = MockExecutionService()
    processor = SignalProcessor([adapter], exec_service)

    signal = SignalPayload(
        symbol="ETH-PERP",
        side="buy",
        size=Decimal("1000.0"),  # Large size, no limit
    )

    # Process without max_position_size (backwards compatibility)
    response = await processor.process_signal(
        signal=signal,
        signal_id="signal-no-limit",
    )

    # Should be processed normally
    assert response.overall_status == "success"

    # Adapter should have been called
    assert len(adapter.execute_order_calls) == 1
