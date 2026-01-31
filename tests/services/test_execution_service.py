"""Tests for ExecutionService."""

from decimal import Decimal
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.models import Execution
from kitkat.services.execution_service import ExecutionService


@pytest.mark.asyncio
async def test_log_execution_success(test_db_session: AsyncSession):
    """Test logging a successful execution."""
    service = ExecutionService(test_db_session)

    execution = await service.log_execution(
        signal_id="abc123def456",
        dex_id="extended",
        order_id="order-001",
        status="filled",
        result_data={"filled_amount": Decimal("1.5"), "remaining_amount": Decimal("0")},
        latency_ms=150,
    )

    assert execution.signal_id == "abc123def456"
    assert execution.dex_id == "extended"
    assert execution.order_id == "order-001"
    assert execution.status == "filled"
    assert execution.latency_ms == 150
    assert execution.id is not None


@pytest.mark.asyncio
async def test_log_execution_with_partial_fill(test_db_session: AsyncSession):
    """Test logging execution with partial fill detection."""
    service = ExecutionService(test_db_session)

    execution = await service.log_execution(
        signal_id="abc123def456",
        dex_id="extended",
        order_id="order-001",
        status="pending",  # Will be changed to "partial"
        result_data={
            "filled_amount": Decimal("1.5"),
            "remaining_amount": Decimal("0.5"),
        },
        latency_ms=150,
    )

    assert execution.status == "partial"


@pytest.mark.asyncio
async def test_log_execution_failure(test_db_session: AsyncSession):
    """Test logging a failed execution."""
    service = ExecutionService(test_db_session)

    execution = await service.log_execution(
        signal_id="abc123def456",
        dex_id="extended",
        order_id=None,
        status="failed",
        result_data={"error": "Insufficient funds"},
        latency_ms=500,
    )

    assert execution.status == "failed"
    assert execution.order_id is None


@pytest.mark.asyncio
async def test_get_execution_by_id(test_db_session: AsyncSession):
    """Test retrieving execution by ID."""
    service = ExecutionService(test_db_session)

    # Create execution
    created = await service.log_execution(
        signal_id="abc123def456",
        dex_id="extended",
        order_id="order-001",
        status="filled",
        result_data={"filled_amount": Decimal("1.5"), "remaining_amount": Decimal("0")},
    )

    # Retrieve it
    retrieved = await service.get_execution(created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.signal_id == "abc123def456"


@pytest.mark.asyncio
async def test_get_execution_not_found(test_db_session: AsyncSession):
    """Test retrieving non-existent execution."""
    service = ExecutionService(test_db_session)
    result = await service.get_execution(99999)
    assert result is None


@pytest.mark.asyncio
async def test_list_executions_no_filter(test_db_session: AsyncSession):
    """Test listing all executions."""
    service = ExecutionService(test_db_session)

    # Create multiple executions
    for i in range(3):
        await service.log_execution(
            signal_id=f"signal-{i}",
            dex_id="extended",
            order_id=f"order-{i}",
            status="filled",
            result_data={},
        )

    executions = await service.list_executions()
    assert len(executions) == 3


@pytest.mark.asyncio
async def test_list_executions_filter_by_signal_id(test_db_session: AsyncSession):
    """Test filtering executions by signal_id."""
    service = ExecutionService(test_db_session)

    signal_id = "abc123def456"
    await service.log_execution(
        signal_id=signal_id,
        dex_id="extended",
        order_id="order-001",
        status="filled",
        result_data={},
    )
    await service.log_execution(
        signal_id="other-signal",
        dex_id="extended",
        order_id="order-002",
        status="filled",
        result_data={},
    )

    executions = await service.list_executions(signal_id=signal_id)
    assert len(executions) == 1
    assert executions[0].signal_id == signal_id


@pytest.mark.asyncio
async def test_list_executions_filter_by_status(test_db_session: AsyncSession):
    """Test filtering executions by status."""
    service = ExecutionService(test_db_session)

    await service.log_execution(
        signal_id="signal-1",
        dex_id="extended",
        order_id="order-001",
        status="filled",
        result_data={},
    )
    await service.log_execution(
        signal_id="signal-2",
        dex_id="extended",
        order_id=None,
        status="failed",
        result_data={},
    )

    failed = await service.list_executions(status="failed")
    assert len(failed) == 1
    assert failed[0].status == "failed"


@pytest.mark.asyncio
async def test_detect_partial_fill_true(test_db_session: AsyncSession):
    """Test partial fill detection when both filled and remaining > 0."""
    service = ExecutionService(test_db_session)

    result = service.detect_partial_fill(
        {"filled_amount": Decimal("1.5"), "remaining_amount": Decimal("0.5")}
    )

    assert result is True


@pytest.mark.asyncio
async def test_detect_partial_fill_false_fully_filled(test_db_session: AsyncSession):
    """Test partial fill detection when fully filled."""
    service = ExecutionService(test_db_session)

    result = service.detect_partial_fill(
        {"filled_amount": Decimal("2.0"), "remaining_amount": Decimal("0")}
    )

    assert result is False


@pytest.mark.asyncio
async def test_detect_partial_fill_false_not_filled(test_db_session: AsyncSession):
    """Test partial fill detection when not filled."""
    service = ExecutionService(test_db_session)

    result = service.detect_partial_fill(
        {"filled_amount": Decimal("0"), "remaining_amount": Decimal("2.0")}
    )

    assert result is False


@pytest.mark.asyncio
async def test_detect_partial_fill_missing_fields(test_db_session: AsyncSession):
    """Test partial fill detection with missing fields."""
    service = ExecutionService(test_db_session)

    result = service.detect_partial_fill({"error": "Some error"})

    assert result is False


@pytest.mark.asyncio
async def test_queue_partial_fill_alert(test_db_session: AsyncSession, caplog):
    """Test queuing partial fill alert."""
    service = ExecutionService(test_db_session)

    await service.queue_partial_fill_alert(
        signal_id="abc123",
        dex_id="extended",
        order_id="order-001",
        symbol="ETH-PERP",
        filled_amount=Decimal("1.5"),
        remaining_amount=Decimal("0.5"),
    )

    # Verify logging occurred (structlog, so just verify no exception)


@pytest.mark.asyncio
async def test_log_execution_invalid_status(test_db_session: AsyncSession):
    """Test logging with invalid status raises error."""
    service = ExecutionService(test_db_session)

    with pytest.raises(ValueError):
        await service.log_execution(
            signal_id="abc123",
            dex_id="extended",
            order_id="order-001",
            status="invalid_status",
            result_data={},
        )


@pytest.mark.asyncio
async def test_execution_persists_to_database(test_db_session: AsyncSession):
    """Test that execution record is persisted to database."""
    service = ExecutionService(test_db_session)

    execution = await service.log_execution(
        signal_id="abc123def456",
        dex_id="extended",
        order_id="order-001",
        status="filled",
        result_data={"filled_amount": Decimal("1.5"), "remaining_amount": Decimal("0")},
        latency_ms=150,
    )

    # Retrieve by ID to verify persistence
    retrieved = await service.get_execution(execution.id)

    assert retrieved is not None
    assert retrieved.id == execution.id
    assert retrieved.signal_id == "abc123def456"
    assert retrieved.order_id == "order-001"


@pytest.mark.asyncio
async def test_multiple_executions_for_same_signal(test_db_session: AsyncSession):
    """Test multiple executions for the same signal (fan-out scenario)."""
    service = ExecutionService(test_db_session)

    signal_id = "abc123def456"

    # Log to two different DEXs
    exec1 = await service.log_execution(
        signal_id=signal_id,
        dex_id="extended",
        order_id="order-ext-001",
        status="filled",
        result_data={},
    )

    exec2 = await service.log_execution(
        signal_id=signal_id,
        dex_id="mock",
        order_id="order-mock-001",
        status="filled",
        result_data={},
    )

    # Retrieve all for this signal
    executions = await service.list_executions(signal_id=signal_id)

    assert len(executions) == 2
    dex_ids = {e.dex_id for e in executions}
    assert dex_ids == {"extended", "mock"}
