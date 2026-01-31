"""Integration tests for signal processing flow (Story 2.9).

Tests the full signal processing pipeline from webhook reception through
parallel DEX adapter execution and result collection.
"""

from decimal import Decimal
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.adapters.mock import MockAdapter
from kitkat.models import SignalPayload
from kitkat.services.execution_service import ExecutionService
from kitkat.services.signal_processor import SignalProcessor


@pytest.mark.asyncio
async def test_signal_processor_with_mock_adapter(test_db_session: AsyncSession):
    """Test full signal processing with MockAdapter."""
    # Create processor with MockAdapter
    adapter = MockAdapter()
    await adapter.connect()

    execution_service = ExecutionService(test_db_session)
    processor = SignalProcessor([adapter], execution_service)

    # Process signal
    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "test-signal-001")

    # Verify response
    assert response.signal_id == "test-signal-001"
    assert response.overall_status == "success"
    assert len(response.results) == 1
    assert response.results[0].dex_id == "mock"
    assert response.results[0].status == "filled"

    # Verify execution was logged
    executions = await execution_service.list_executions(signal_id="test-signal-001")
    assert len(executions) == 1
    assert executions[0].dex_id == "mock"
    assert executions[0].status == "filled"


@pytest.mark.asyncio
async def test_signal_processor_multiple_adapters_integration(test_db_session: AsyncSession):
    """Test signal processing with multiple adapters."""
    # Create processor with two MockAdapters
    adapter1 = MockAdapter()
    adapter1._connected = True
    adapter1._order_counter = 100  # Different starting point

    adapter2 = MockAdapter()
    adapter2._connected = True
    adapter2._order_counter = 200

    execution_service = ExecutionService(test_db_session)
    processor = SignalProcessor([adapter1, adapter2], execution_service)

    # Process signal
    signal = SignalPayload(symbol="BTC/USD", side="sell", size=Decimal("0.5"))
    response = await processor.process_signal(signal, "test-signal-002")

    # Verify response
    assert response.overall_status == "success"
    assert response.total_dex_count == 2
    assert response.successful_count == 2
    assert response.failed_count == 0

    # Verify execution logging for both adapters
    executions = await execution_service.list_executions(signal_id="test-signal-002", limit=10)
    assert len(executions) == 2
    dex_ids = {e.dex_id for e in executions}
    assert dex_ids == {"mock"}


@pytest.mark.asyncio
async def test_execution_logging_integration(test_db_session: AsyncSession):
    """Test that execution service logs all signals correctly."""
    adapter = MockAdapter()
    adapter._connected = True

    execution_service = ExecutionService(test_db_session)
    processor = SignalProcessor([adapter], execution_service)

    # Process multiple signals
    signals = [
        (SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0")), "sig-001"),
        (SignalPayload(symbol="BTC/USD", side="sell", size=Decimal("0.5")), "sig-002"),
        (SignalPayload(symbol="XRP/USD", side="buy", size=Decimal("100.0")), "sig-003"),
    ]

    for signal, signal_id in signals:
        await processor.process_signal(signal, signal_id)

    # Verify all executions were logged
    all_executions = await execution_service.list_executions(limit=100)
    assert len(all_executions) == 3

    signal_ids = {e.signal_id for e in all_executions}
    assert signal_ids == {"sig-001", "sig-002", "sig-003"}


@pytest.mark.asyncio
async def test_signal_processor_response_serialization(test_db_session: AsyncSession):
    """Test that SignalProcessorResponse can be serialized to JSON."""
    adapter = MockAdapter()
    await adapter.connect()

    execution_service = ExecutionService(test_db_session)
    processor = SignalProcessor([adapter], execution_service)

    # Process signal
    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "test-serial")

    # Verify response can be converted to dict (for JSON serialization)
    response_dict = response.model_dump()
    assert response_dict["signal_id"] == "test-serial"
    assert response_dict["overall_status"] == "success"
    assert isinstance(response_dict["timestamp"], datetime)

    # Verify JSON serialization
    response_json = response.model_dump_json()
    assert isinstance(response_json, str)
    assert "test-serial" in response_json
    assert "success" in response_json


@pytest.mark.asyncio
async def test_adapter_independence_in_parallel_execution(test_db_session: AsyncSession):
    """Test that adapters execute independently in parallel."""
    # Create two MockAdapters
    adapter1 = MockAdapter()
    adapter1._connected = True

    adapter2 = MockAdapter()
    adapter2._connected = True

    execution_service = ExecutionService(test_db_session)
    processor = SignalProcessor([adapter1, adapter2], execution_service)

    # Process signal
    signal = SignalPayload(symbol="ETH/USD", side="buy", size=Decimal("1.0"))
    response = await processor.process_signal(signal, "test-indep")

    # Verify both adapters returned results
    assert len(response.results) == 2
    assert response.overall_status == "success"

    # Verify each adapter got the same signal data
    for result in response.results:
        assert result.dex_id == "mock"
        assert result.status == "filled"


@pytest.mark.asyncio
async def test_signal_processor_maintains_decimal_precision(test_db_session: AsyncSession):
    """Test that Decimal values are preserved through processing."""
    adapter = MockAdapter()
    await adapter.connect()

    execution_service = ExecutionService(test_db_session)
    processor = SignalProcessor([adapter], execution_service)

    # Test with precise Decimal
    precise_size = Decimal("1.23456789")
    signal = SignalPayload(symbol="ETH/USD", side="buy", size=precise_size)
    response = await processor.process_signal(signal, "test-decimal")

    # Verify precision is maintained
    assert response.results[0].filled_amount == precise_size

    # Verify in execution log
    execution = await execution_service.get_execution(
        (await execution_service.list_executions(signal_id="test-decimal", limit=1))[0].id
    )
    assert "1.23456789" in execution.result_data["filled_amount"]
