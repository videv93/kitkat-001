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
    assert result.filled_amount == Decimal("1.23456789")


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
