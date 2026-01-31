"""Execution logging and partial fill handling service."""

from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.database import ExecutionModel
from kitkat.models import Execution

logger = structlog.get_logger()


class ExecutionService:
    """Service for logging and querying order executions."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db
        self._log = logger.bind(service="execution")

    async def log_execution(
        self,
        signal_id: str,
        dex_id: str,
        order_id: str | None,
        status: str,
        result_data: dict,
        latency_ms: int | None = None,
    ) -> Execution:
        """Log an execution attempt with full context.

        Args:
            signal_id: Signal hash for correlation
            dex_id: DEX identifier
            order_id: DEX-assigned order ID (None on failure)
            status: Execution status ("pending", "filled", "partial", "failed")
            result_data: Full DEX response data
            latency_ms: Execution latency in milliseconds

        Returns:
            Execution: The persisted execution record

        Raises:
            ValueError: If status is invalid
        """
        # Validate status
        valid_statuses = {"pending", "filled", "partial", "failed"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Expected one of {valid_statuses}")

        # Check for partial fill
        is_partial = self.detect_partial_fill(result_data)
        if is_partial:
            status = "partial"

        execution = ExecutionModel(
            signal_id=signal_id,
            dex_id=dex_id,
            order_id=order_id,
            status=status,
            result_data=self._serialize_result_data(result_data),
            latency_ms=latency_ms,
        )
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)

        self._log.info(
            "Execution recorded",
            signal_id=signal_id,
            dex_id=dex_id,
            order_id=order_id,
            status=status,
            latency_ms=latency_ms,
        )

        # Create dict with deserialized result_data for Pydantic validation
        exec_dict = {
            "id": execution.id,
            "signal_id": execution.signal_id,
            "dex_id": execution.dex_id,
            "order_id": execution.order_id,
            "status": execution.status,
            "latency_ms": execution.latency_ms,
            "created_at": execution.created_at,
            "result_data": self._deserialize_result_data(execution.result_data),
        }
        return Execution.model_validate(exec_dict)

    async def get_execution(self, execution_id: int) -> Execution | None:
        """Get execution by ID.

        Args:
            execution_id: The execution ID to retrieve

        Returns:
            Execution: The execution record if found, None otherwise
        """
        stmt = select(ExecutionModel).where(ExecutionModel.id == execution_id)
        result = await self.db.execute(stmt)
        execution = result.scalar_one_or_none()
        if execution:
            exec_dict = {
                "id": execution.id,
                "signal_id": execution.signal_id,
                "dex_id": execution.dex_id,
                "order_id": execution.order_id,
                "status": execution.status,
                "latency_ms": execution.latency_ms,
                "created_at": execution.created_at,
                "result_data": self._deserialize_result_data(execution.result_data),
            }
            return Execution.model_validate(exec_dict)
        return None

    async def list_executions(
        self,
        signal_id: str | None = None,
        dex_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Execution]:
        """List executions with optional filters.

        Args:
            signal_id: Filter by signal ID
            dex_id: Filter by DEX ID
            status: Filter by status
            limit: Maximum number of records to return

        Returns:
            list[Execution]: List of execution records
        """
        stmt = select(ExecutionModel)

        if signal_id:
            stmt = stmt.where(ExecutionModel.signal_id == signal_id)
        if dex_id:
            stmt = stmt.where(ExecutionModel.dex_id == dex_id)
        if status:
            stmt = stmt.where(ExecutionModel.status == status)

        stmt = stmt.order_by(ExecutionModel.created_at.desc()).limit(limit)

        result = await self.db.execute(stmt)
        executions = result.scalars().all()
        exec_list = []
        for e in executions:
            exec_dict = {
                "id": e.id,
                "signal_id": e.signal_id,
                "dex_id": e.dex_id,
                "order_id": e.order_id,
                "status": e.status,
                "latency_ms": e.latency_ms,
                "created_at": e.created_at,
                "result_data": self._deserialize_result_data(e.result_data),
            }
            exec_list.append(Execution.model_validate(exec_dict))
        return exec_list

    def detect_partial_fill(self, result_data: dict) -> bool:
        """Check if result_data indicates a partial fill.

        A partial fill is when both filled_amount > 0 AND remaining_amount > 0.

        Args:
            result_data: DEX response data

        Returns:
            bool: True if partial fill detected
        """
        if "filled_amount" not in result_data or "remaining_amount" not in result_data:
            return False

        try:
            filled = Decimal(str(result_data.get("filled_amount", 0)))
            remaining = Decimal(str(result_data.get("remaining_amount", 0)))
            return filled > 0 and remaining > 0
        except (ValueError, TypeError):
            return False

    async def queue_partial_fill_alert(
        self,
        signal_id: str,
        dex_id: str,
        order_id: str,
        symbol: str,
        filled_amount: Decimal,
        remaining_amount: Decimal,
    ) -> None:
        """Queue alert for partial fill.

        Currently logs alert details. Epic 4 will add Telegram integration.

        Args:
            signal_id: Signal hash
            dex_id: DEX identifier
            order_id: Order ID
            symbol: Trading symbol
            filled_amount: Amount filled
            remaining_amount: Amount remaining
        """
        self._log.warning(
            "Partial fill detected",
            signal_id=signal_id,
            dex_id=dex_id,
            order_id=order_id,
            symbol=symbol,
            filled_amount=str(filled_amount),
            remaining_amount=str(remaining_amount),
        )

    def _serialize_result_data(self, result_data: dict) -> str:
        """Serialize result_data dict to JSON string.

        Args:
            result_data: Dictionary to serialize

        Returns:
            str: JSON string representation
        """
        import json

        return json.dumps(result_data, default=str)

    def _deserialize_result_data(self, result_data_str: str) -> dict:
        """Deserialize result_data JSON string back to dict.

        Args:
            result_data_str: JSON string

        Returns:
            dict: Deserialized dictionary
        """
        import json

        try:
            return json.loads(result_data_str)
        except (ValueError, TypeError):
            return {}
