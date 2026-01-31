"""Mock DEX adapter for testing and development.

Implements DEXAdapter interface with minimal latency for fast testing
and development without connecting to real DEX systems.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

import structlog

from kitkat.adapters.base import DEXAdapter
from kitkat.models import (
    ConnectParams,
    HealthStatus,
    OrderStatus,
    OrderSubmissionResult,
    Position,
)

logger = structlog.get_logger(__name__)


class MockAdapter(DEXAdapter):
    """Mock DEX adapter for testing and development.

    Simulates a DEX without making real API calls. All orders succeed with
    minimal latency, making it suitable for development, integration testing,
    and test mode deployments.

    Features:
    - Instant order submission with mock order IDs
    - No real network calls
    - No authentication required
    - Perfect for CI/CD and testing workflows
    """

    def __init__(self):
        """Initialize Mock adapter."""
        self._connected = False
        self._order_counter = 0
        self._log = structlog.get_logger().bind(dex_id=self.dex_id)

    @property
    def dex_id(self) -> str:
        """Return unique identifier for Mock DEX."""
        return "mock"

    @property
    def is_connected(self) -> bool:
        """Check if adapter is currently connected."""
        return self._connected

    async def connect(self, params: Optional[ConnectParams] = None) -> None:
        """Connect to Mock DEX (no-op, always succeeds)."""
        self._connected = True
        self._log.info("Connected to Mock DEX")

    async def disconnect(self) -> None:
        """Disconnect from Mock DEX (no-op)."""
        self._connected = False
        self._log.info("Disconnected from Mock DEX")

    async def execute_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        size: Decimal,
    ) -> OrderSubmissionResult:
        """Submit a mock order (always succeeds).

        Args:
            symbol: Trading pair (e.g., "ETH/USD")
            side: "buy" (long) or "sell" (short)
            size: Amount to trade (must be positive)

        Returns:
            OrderSubmissionResult with mock order ID and no initial fill
            (fill amount comes from WebSocket updates, like real DEX behavior)
        """
        self._order_counter += 1
        order_id = f"mock-order-{self._order_counter:06d}"

        self._log.info(
            "Mock order submitted",
            order_id=order_id,
            symbol=symbol,
            side=side,
            size=str(size),
        )

        return OrderSubmissionResult(
            order_id=order_id,
            status="submitted",
            submitted_at=datetime.now(timezone.utc),
            filled_amount=Decimal("0"),  # No fill yet - will come from WebSocket updates
            dex_response={
                "order_id": order_id,
                "status": "submitted",
                "symbol": symbol,
                "side": side,
                "size": str(size),
            },
        )

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get status of a mock order (always filled)."""
        return OrderStatus(
            order_id=order_id,
            status="filled",
            filled_amount=Decimal("0"),  # Mock doesn't track amounts
            remaining_amount=Decimal("0"),
            average_price=Decimal("0"),
            last_updated=datetime.now(timezone.utc),
        )

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol (always None for mock)."""
        return None

    async def cancel_order(self, order_id: str) -> None:
        """Cancel a mock order (no-op)."""
        self._log.info("Mock order cancelled", order_id=order_id)

    async def get_health_status(self) -> HealthStatus:
        """Get health status (always healthy for mock)."""
        return HealthStatus(
            dex_id=self.dex_id,
            status="healthy" if self._connected else "offline",
            connected=self._connected,
            latency_ms=1,  # Mock has minimal latency
            last_check=datetime.now(timezone.utc),
            error_message=None,
        )
