"""Unit tests for DEX adapter interface contract (Story 2.1).

Tests verify:
1. DEXAdapter is abstract and cannot be instantiated
2. Subclasses must implement all abstract methods
3. Exception hierarchy is correct
4. Optional methods have working defaults
5. Type models validate correctly
"""

import pytest
from datetime import datetime
from decimal import Decimal

from kitkat.adapters.base import DEXAdapter
from kitkat.adapters.exceptions import (
    DEXError,
    DEXTimeoutError,
    DEXConnectionError,
    DEXRejectionError,
    DEXInsufficientFundsError,
    DEXNonceError,
    DEXSignatureError,
    DEXOrderNotFoundError,
)
from kitkat.models import (
    OrderSubmissionResult,
    OrderStatus,
    HealthStatus,
    Position,
    OrderUpdate,
    ConnectParams,
)


class TestAbstractClassEnforcement:
    """Test that DEXAdapter enforces abstract method implementation."""

    def test_cannot_instantiate_abstract_directly(self):
        """DEXAdapter is abstract and cannot be instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DEXAdapter()

    def test_subclass_missing_dex_id_property(self):
        """Subclass missing dex_id property cannot be instantiated."""

        class PartialAdapter(DEXAdapter):
            async def connect(self, params=None):
                pass

            async def disconnect(self):
                pass

            async def execute_order(self, symbol, side, size):
                pass

            async def get_order_status(self, order_id):
                pass

            async def get_position(self, symbol):
                return None

            async def cancel_order(self, order_id):
                pass

            async def get_health_status(self):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PartialAdapter()

    def test_subclass_missing_connect_method(self):
        """Subclass missing connect() cannot be instantiated."""

        class PartialAdapter(DEXAdapter):
            @property
            def dex_id(self):
                return "partial"

            async def disconnect(self):
                pass

            async def execute_order(self, symbol, side, size):
                pass

            async def get_order_status(self, order_id):
                pass

            async def get_position(self, symbol):
                return None

            async def cancel_order(self, order_id):
                pass

            async def get_health_status(self):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PartialAdapter()

    def test_subclass_missing_disconnect_method(self):
        """Subclass missing disconnect() cannot be instantiated."""

        class PartialAdapter(DEXAdapter):
            @property
            def dex_id(self):
                return "partial"

            async def connect(self, params=None):
                pass

            async def execute_order(self, symbol, side, size):
                pass

            async def get_order_status(self, order_id):
                pass

            async def get_position(self, symbol):
                return None

            async def cancel_order(self, order_id):
                pass

            async def get_health_status(self):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PartialAdapter()


class TestValidSubclass:
    """Test that properly implemented subclass can be instantiated."""

    @pytest.fixture
    def minimal_adapter_class(self):
        """Create minimal valid adapter implementation."""

        class MinimalAdapter(DEXAdapter):
            @property
            def dex_id(self):
                return "minimal"

            async def connect(self, params=None):
                pass

            async def disconnect(self):
                pass

            async def execute_order(self, symbol, side, size):
                return OrderSubmissionResult(
                    order_id="min-123",
                    status="submitted",
                    submitted_at=datetime.now(),
                    filled_amount=Decimal("0"),
                    dex_response={},
                )

            async def get_order_status(self, order_id):
                return OrderStatus(
                    order_id=order_id,
                    status="pending",
                    filled_amount=Decimal("0"),
                    remaining_amount=Decimal("1"),
                    average_price=Decimal("100"),
                    last_updated=datetime.now(),
                )

            async def get_position(self, symbol):
                return None

            async def cancel_order(self, order_id):
                pass

            async def get_health_status(self):
                return HealthStatus(
                    dex_id=self.dex_id,
                    status="healthy",
                    connected=True,
                    latency_ms=50,
                    last_check=datetime.now(),
                )

        return MinimalAdapter

    def test_valid_subclass_instantiates(self, minimal_adapter_class):
        """Properly implemented subclass can be instantiated."""
        adapter = minimal_adapter_class()
        assert isinstance(adapter, DEXAdapter)
        assert adapter.dex_id == "minimal"

    @pytest.mark.asyncio
    async def test_valid_subclass_execute_order(self, minimal_adapter_class):
        """Valid subclass execute_order returns OrderSubmissionResult."""
        adapter = minimal_adapter_class()
        result = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

        assert isinstance(result, OrderSubmissionResult)
        assert result.order_id == "min-123"
        assert result.status == "submitted"
        assert result.filled_amount == Decimal("0")

    @pytest.mark.asyncio
    async def test_valid_subclass_get_order_status(self, minimal_adapter_class):
        """Valid subclass get_order_status returns OrderStatus."""
        adapter = minimal_adapter_class()
        status = await adapter.get_order_status("min-123")

        assert isinstance(status, OrderStatus)
        assert status.order_id == "min-123"
        assert status.status == "pending"

    @pytest.mark.asyncio
    async def test_valid_subclass_get_position(self, minimal_adapter_class):
        """Valid subclass get_position can return None or Position."""
        adapter = minimal_adapter_class()
        position = await adapter.get_position("ETH/USD")
        assert position is None

    @pytest.mark.asyncio
    async def test_valid_subclass_get_health_status(self, minimal_adapter_class):
        """Valid subclass get_health_status returns HealthStatus."""
        adapter = minimal_adapter_class()
        health = await adapter.get_health_status()

        assert isinstance(health, HealthStatus)
        assert health.dex_id == "minimal"
        assert health.status == "healthy"
        assert health.connected is True

    @pytest.mark.asyncio
    async def test_optional_subscribe_has_default(self, minimal_adapter_class):
        """subscribe_to_order_updates has working default implementation."""
        adapter = minimal_adapter_class()

        # Define proper async callback (matching Callable[[OrderUpdate], Awaitable[None]])
        async def async_callback(update):
            pass

        # Default subscribe should work (no-op context manager)
        async with adapter.subscribe_to_order_updates(async_callback):
            pass  # Context manager works


class TestExceptionHierarchy:
    """Test exception class inheritance and semantics."""

    def test_dex_timeout_error_inherits_from_dex_error(self):
        """DEXTimeoutError is subclass of DEXError."""
        assert issubclass(DEXTimeoutError, DEXError)

    def test_dex_connection_error_inherits_from_dex_error(self):
        """DEXConnectionError is subclass of DEXError."""
        assert issubclass(DEXConnectionError, DEXError)

    def test_dex_rejection_error_inherits_from_dex_error(self):
        """DEXRejectionError is subclass of DEXError."""
        assert issubclass(DEXRejectionError, DEXError)

    def test_specific_rejection_errors_inherit_from_rejection_error(self):
        """Specific rejection errors inherit from DEXRejectionError."""
        assert issubclass(DEXInsufficientFundsError, DEXRejectionError)
        assert issubclass(DEXNonceError, DEXRejectionError)
        assert issubclass(DEXOrderNotFoundError, DEXRejectionError)

    def test_dex_signature_error_inherits_from_connection_error(self):
        """DEXSignatureError inherits from DEXConnectionError (retryable)."""
        assert issubclass(DEXSignatureError, DEXConnectionError)

    def test_exception_instantiation(self):
        """All exception classes can be instantiated with message."""
        msg = "Test error"

        errors = [
            DEXError(msg),
            DEXTimeoutError(msg),
            DEXConnectionError(msg),
            DEXRejectionError(msg),
            DEXInsufficientFundsError(msg),
            DEXNonceError(msg),
            DEXSignatureError(msg),
            DEXOrderNotFoundError(msg),
        ]

        for error in errors:
            assert isinstance(error, DEXError)
            assert str(error) == msg


class TestTypeModelValidation:
    """Test that type models validate correctly."""

    def test_order_submission_result_valid(self):
        """OrderSubmissionResult validates valid data."""
        result = OrderSubmissionResult(
            order_id="test-123",
            status="submitted",
            submitted_at=datetime.now(),
            filled_amount=Decimal("0.5"),
            dex_response={"raw": "data"},
        )
        assert result.order_id == "test-123"
        assert result.status == "submitted"
        assert result.filled_amount == Decimal("0.5")

    def test_order_submission_result_default_filled_amount(self):
        """OrderSubmissionResult has default filled_amount of 0."""
        result = OrderSubmissionResult(
            order_id="test-123",
            status="submitted",
            submitted_at=datetime.now(),
            dex_response={},
        )
        assert result.filled_amount == Decimal("0")

    def test_order_status_valid(self):
        """OrderStatus validates valid data."""
        status = OrderStatus(
            order_id="test-123",
            status="pending",
            filled_amount=Decimal("0"),
            remaining_amount=Decimal("1.0"),
            average_price=Decimal("100.50"),
            last_updated=datetime.now(),
        )
        assert status.order_id == "test-123"
        assert status.status == "pending"

    def test_health_status_valid(self):
        """HealthStatus validates valid data."""
        health = HealthStatus(
            dex_id="extended",
            status="healthy",
            connected=True,
            latency_ms=50,
            last_check=datetime.now(),
        )
        assert health.dex_id == "extended"
        assert health.status == "healthy"

    def test_health_status_with_error_message(self):
        """HealthStatus can include error message for degraded/offline status."""
        health = HealthStatus(
            dex_id="extended",
            status="offline",
            connected=False,
            latency_ms=5000,
            last_check=datetime.now(),
            error_message="WebSocket connection lost",
        )
        assert health.error_message == "WebSocket connection lost"

    def test_position_valid(self):
        """Position validates valid data."""
        position = Position(
            symbol="ETH/USD",
            size=Decimal("1.5"),
            entry_price=Decimal("2000"),
            current_price=Decimal("2100"),
            unrealized_pnl=Decimal("75"),
        )
        assert position.symbol == "ETH/USD"
        assert position.size == Decimal("1.5")

    def test_position_no_position_zero_size(self):
        """Position with size 0 represents no position."""
        position = Position(
            symbol="ETH/USD",
            size=Decimal("0"),
            entry_price=Decimal("2000"),
            current_price=Decimal("2100"),
            unrealized_pnl=Decimal("0"),
        )
        assert position.size == Decimal("0")

    def test_order_update_creation(self):
        """OrderUpdate dataclass can be created."""
        update = OrderUpdate(
            order_id="test-123",
            status="filled",
            filled_amount=Decimal("1.0"),
            remaining_amount=Decimal("0"),
            timestamp=datetime.now(),
        )
        assert update.order_id == "test-123"
        assert update.status == "filled"

    def test_connect_params_base_valid(self):
        """ConnectParams base class can be instantiated."""
        params = ConnectParams()
        assert isinstance(params, ConnectParams)


class TestPydanticModelFieldValidation:
    """Test Pydantic field validation and constraints."""

    def test_order_submission_result_filled_amount_non_negative(self):
        """OrderSubmissionResult filled_amount must be non-negative."""
        # Valid: 0
        result = OrderSubmissionResult(
            order_id="test",
            status="submitted",
            submitted_at=datetime.now(),
            filled_amount=Decimal("0"),
            dex_response={},
        )
        assert result.filled_amount == Decimal("0")

        # Valid: positive
        result = OrderSubmissionResult(
            order_id="test",
            status="submitted",
            submitted_at=datetime.now(),
            filled_amount=Decimal("0.5"),
            dex_response={},
        )
        assert result.filled_amount == Decimal("0.5")

        # Invalid: negative
        with pytest.raises(ValueError):
            OrderSubmissionResult(
                order_id="test",
                status="submitted",
                submitted_at=datetime.now(),
                filled_amount=Decimal("-1"),
                dex_response={},
            )

    def test_order_status_amounts_non_negative(self):
        """OrderStatus amounts must be non-negative."""
        # Both can be 0
        status = OrderStatus(
            order_id="test",
            status="filled",
            filled_amount=Decimal("0"),
            remaining_amount=Decimal("0"),
            average_price=Decimal("100"),
            last_updated=datetime.now(),
        )
        assert status.filled_amount == Decimal("0")
        assert status.remaining_amount == Decimal("0")

        # Negative filled_amount should fail
        with pytest.raises(ValueError):
            OrderStatus(
                order_id="test",
                status="filled",
                filled_amount=Decimal("-1"),
                remaining_amount=Decimal("0"),
                average_price=Decimal("100"),
                last_updated=datetime.now(),
            )

    def test_average_price_non_negative(self):
        """Average price must be non-negative (>= 0)."""
        # Valid: positive price
        status = OrderStatus(
            order_id="test",
            status="filled",
            filled_amount=Decimal("1"),
            remaining_amount=Decimal("0"),
            average_price=Decimal("100.50"),
            last_updated=datetime.now(),
        )
        assert status.average_price == Decimal("100.50")

        # Valid: zero price for pending orders with no fills
        status = OrderStatus(
            order_id="test",
            status="pending",
            filled_amount=Decimal("0"),
            remaining_amount=Decimal("1"),
            average_price=Decimal("0"),
            last_updated=datetime.now(),
        )
        assert status.average_price == Decimal("0")

    def test_position_size_non_negative(self):
        """Position size must be non-negative (0 or positive)."""
        # Size 0 (no position)
        position = Position(
            symbol="ETH",
            size=Decimal("0"),
            entry_price=Decimal("100"),
            current_price=Decimal("105"),
            unrealized_pnl=Decimal("0"),
        )
        assert position.size == Decimal("0")

        # Negative size should fail
        with pytest.raises(ValueError):
            Position(
                symbol="ETH",
                size=Decimal("-1"),
                entry_price=Decimal("100"),
                current_price=Decimal("105"),
                unrealized_pnl=Decimal("0"),
            )

    def test_health_status_latency_non_negative(self):
        """Health status latency must be non-negative."""
        # Zero latency
        health = HealthStatus(
            dex_id="test",
            status="healthy",
            connected=True,
            latency_ms=0,
            last_check=datetime.now(),
        )
        assert health.latency_ms == 0

        # Negative latency should fail
        with pytest.raises(ValueError):
            HealthStatus(
                dex_id="test",
                status="healthy",
                connected=True,
                latency_ms=-1,
                last_check=datetime.now(),
            )
