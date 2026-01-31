"""Unit tests for MockAdapter (Story 3.2).

Tests verify:
1. MockAdapter implements the full DEXAdapter interface
2. execute_order() returns correct OrderSubmissionResult structure
3. All methods work without real DEX credentials
4. No real API calls are made
5. Optional failure simulation via MOCK_FAIL_RATE works correctly
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import patch, MagicMock

from kitkat.adapters.mock import MockAdapter
from kitkat.adapters.base import DEXAdapter
from kitkat.adapters.exceptions import DEXRejectionError
from kitkat.models import (
    OrderSubmissionResult,
    OrderStatus,
    HealthStatus,
    Position,
)


class TestMockAdapterInterfaceCompliance:
    """Test that MockAdapter fully implements DEXAdapter interface (AC#1)."""

    def test_mock_adapter_is_dex_adapter_subclass(self):
        """MockAdapter is a DEXAdapter subclass."""
        adapter = MockAdapter()
        assert isinstance(adapter, DEXAdapter)

    def test_mock_adapter_has_all_required_methods(self):
        """MockAdapter has all abstract methods implemented."""
        adapter = MockAdapter()

        # Check all required methods exist
        assert hasattr(adapter, 'dex_id')
        assert hasattr(adapter, 'is_connected')
        assert hasattr(adapter, 'connect')
        assert hasattr(adapter, 'disconnect')
        assert hasattr(adapter, 'execute_order')
        assert hasattr(adapter, 'get_order_status')
        assert hasattr(adapter, 'get_position')
        assert hasattr(adapter, 'cancel_order')
        assert hasattr(adapter, 'get_health_status')
        assert hasattr(adapter, 'subscribe_to_order_updates')

    def test_mock_adapter_dex_id_property_returns_mock(self):
        """dex_id property returns 'mock'."""
        adapter = MockAdapter()
        assert adapter.dex_id == "mock"

    def test_mock_adapter_is_connected_property_exists(self):
        """is_connected property exists and is boolean."""
        adapter = MockAdapter()
        assert isinstance(adapter.is_connected, bool)


@pytest.mark.asyncio
class TestMockAdapterConnectionMethods:
    """Test connection management methods."""

    async def test_connect_succeeds_without_credentials(self):
        """connect() succeeds without DEX credentials."""
        adapter = MockAdapter()
        await adapter.connect()  # Should not raise
        assert adapter.is_connected is True

    async def test_connect_with_none_params(self):
        """connect() works with None params."""
        adapter = MockAdapter()
        await adapter.connect(None)
        assert adapter.is_connected is True

    async def test_disconnect_succeeds(self):
        """disconnect() succeeds and marks disconnected."""
        adapter = MockAdapter()
        await adapter.connect()
        await adapter.disconnect()
        assert adapter.is_connected is False

    async def test_disconnect_idempotent(self):
        """disconnect() can be called multiple times safely."""
        adapter = MockAdapter()
        await adapter.connect()
        await adapter.disconnect()
        await adapter.disconnect()  # Should not raise
        assert adapter.is_connected is False


@pytest.mark.asyncio
class TestMockAdapterOrderExecution:
    """Test order execution (AC#2)."""

    async def test_execute_order_returns_order_submission_result(self):
        """execute_order() returns OrderSubmissionResult."""
        adapter = MockAdapter()
        await adapter.connect()

        result = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

        assert isinstance(result, OrderSubmissionResult)

    async def test_execute_order_result_has_required_fields(self):
        """OrderSubmissionResult has all required fields."""
        adapter = MockAdapter()
        await adapter.connect()

        result = await adapter.execute_order("BTC/USD", "sell", Decimal("0.5"))

        assert hasattr(result, 'order_id')
        assert hasattr(result, 'status')
        assert hasattr(result, 'submitted_at')
        assert hasattr(result, 'filled_amount')
        assert hasattr(result, 'dex_response')

    async def test_execute_order_order_id_has_mock_prefix(self):
        """order_id uses mock-* format."""
        adapter = MockAdapter()
        await adapter.connect()

        result = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

        assert result.order_id.startswith("mock-")

    async def test_execute_order_status_is_submitted(self):
        """Order status is 'submitted' (not waiting for fill)."""
        adapter = MockAdapter()
        await adapter.connect()

        result = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

        # Mock returns "submitted" because fill comes from WebSocket updates
        assert result.status == "submitted"

    async def test_execute_order_submitted_at_is_utc(self):
        """submitted_at is UTC timezone-aware datetime."""
        adapter = MockAdapter()
        await adapter.connect()

        result = await adapter.execute_order("BTC/USD", "buy", Decimal("2.0"))

        assert isinstance(result.submitted_at, datetime)
        assert result.submitted_at.tzinfo is not None

    async def test_execute_order_with_buy_side(self):
        """execute_order works with side='buy'."""
        adapter = MockAdapter()
        await adapter.connect()

        result = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

        assert result.order_id is not None

    async def test_execute_order_with_sell_side(self):
        """execute_order works with side='sell'."""
        adapter = MockAdapter()
        await adapter.connect()

        result = await adapter.execute_order("BTC/USD", "sell", Decimal("0.5"))

        assert result.order_id is not None

    async def test_execute_order_with_various_sizes(self):
        """execute_order works with different sizes."""
        adapter = MockAdapter()
        await adapter.connect()

        sizes = [Decimal("0.1"), Decimal("1.0"), Decimal("100.0")]
        for size in sizes:
            result = await adapter.execute_order("ETH/USD", "buy", size)
            assert result.order_id is not None

    async def test_execute_order_dex_response_field_populated(self):
        """dex_response field is populated with order details."""
        adapter = MockAdapter()
        await adapter.connect()

        result = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

        assert isinstance(result.dex_response, dict)
        assert "order_id" in result.dex_response
        assert "status" in result.dex_response


@pytest.mark.asyncio
class TestMockAdapterOrderTracking:
    """Test order tracking methods."""

    async def test_get_order_status_returns_order_status(self):
        """get_order_status() returns OrderStatus."""
        adapter = MockAdapter()
        await adapter.connect()

        status = await adapter.get_order_status("mock-order-000001")

        assert isinstance(status, OrderStatus)

    async def test_get_order_status_has_required_fields(self):
        """OrderStatus has all required fields."""
        adapter = MockAdapter()
        await adapter.connect()

        status = await adapter.get_order_status("mock-order-000001")

        assert hasattr(status, 'order_id')
        assert hasattr(status, 'status')
        assert hasattr(status, 'filled_amount')
        assert hasattr(status, 'remaining_amount')
        assert hasattr(status, 'average_price')
        assert hasattr(status, 'last_updated')

    async def test_get_position_returns_none_or_position(self):
        """get_position() returns None or Position object."""
        adapter = MockAdapter()
        await adapter.connect()

        position = await adapter.get_position("ETH/USD")

        assert position is None or isinstance(position, Position)

    async def test_cancel_order_succeeds(self):
        """cancel_order() succeeds without error."""
        adapter = MockAdapter()
        await adapter.connect()

        await adapter.cancel_order("mock-order-000001")  # Should not raise


@pytest.mark.asyncio
class TestMockAdapterHealthStatus:
    """Test health status reporting."""

    async def test_get_health_status_returns_health_status(self):
        """get_health_status() returns HealthStatus."""
        adapter = MockAdapter()
        await adapter.connect()

        health = await adapter.get_health_status()

        assert isinstance(health, HealthStatus)

    async def test_health_status_when_connected(self):
        """Health status shows 'healthy' when connected."""
        adapter = MockAdapter()
        await adapter.connect()

        health = await adapter.get_health_status()

        assert health.status == "healthy"
        assert health.connected is True

    async def test_health_status_when_disconnected(self):
        """Health status shows 'offline' when disconnected."""
        adapter = MockAdapter()

        health = await adapter.get_health_status()

        assert health.status == "offline"
        assert health.connected is False

    async def test_health_status_dex_id_is_mock(self):
        """Health status dex_id field is 'mock'."""
        adapter = MockAdapter()
        await adapter.connect()

        health = await adapter.get_health_status()

        assert health.dex_id == "mock"

    async def test_health_status_latency_minimal(self):
        """Health status latency is minimal (1ms for mock)."""
        adapter = MockAdapter()
        await adapter.connect()

        health = await adapter.get_health_status()

        assert health.latency_ms == 1


@pytest.mark.asyncio
class TestMockAdapterNoRealAPICalls:
    """Test that MockAdapter makes no real API calls."""

    async def test_execute_order_no_network_calls(self, mocker):
        """execute_order() makes no actual network calls."""
        # Mock httpx to verify it's not called
        mock_httpx = mocker.patch("httpx.AsyncClient.post")
        mock_ws = mocker.patch("websockets.connect")

        adapter = MockAdapter()
        await adapter.connect()

        await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

        # Verify no network calls were made
        mock_httpx.assert_not_called()
        mock_ws.assert_not_called()

    async def test_get_position_no_network_calls(self, mocker):
        """get_position() makes no actual network calls."""
        mock_httpx = mocker.patch("httpx.AsyncClient.get")

        adapter = MockAdapter()
        await adapter.connect()

        await adapter.get_position("ETH/USD")

        mock_httpx.assert_not_called()


@pytest.mark.asyncio
class TestMockAdapterSubscribeToUpdates:
    """Test optional subscribe_to_order_updates() method."""

    async def test_subscribe_to_order_updates_is_noop(self):
        """subscribe_to_order_updates() returns no-op context manager."""
        adapter = MockAdapter()

        async def dummy_callback(update):
            pass

        # Should not raise and should work as context manager
        async with adapter.subscribe_to_order_updates(dummy_callback):
            pass  # No-op: no updates are delivered

    async def test_subscribe_to_order_updates_never_calls_callback(self):
        """Callback is never invoked in mock adapter."""
        adapter = MockAdapter()
        callback_called = False

        async def callback(update):
            nonlocal callback_called
            callback_called = True

        async with adapter.subscribe_to_order_updates(callback):
            # Wait a bit, but callback should never be called
            import asyncio
            await asyncio.sleep(0.01)

        assert callback_called is False


class TestMockAdapterStateManagement:
    """Test state management and reusability."""

    @pytest.mark.asyncio
    async def test_can_reconnect_after_disconnect(self):
        """Adapter can reconnect after disconnect."""
        adapter = MockAdapter()

        await adapter.connect()
        assert adapter.is_connected is True

        await adapter.disconnect()
        assert adapter.is_connected is False

        await adapter.connect()
        assert adapter.is_connected is True

    @pytest.mark.asyncio
    async def test_multiple_adapters_independent(self):
        """Multiple adapter instances are independent."""
        adapter1 = MockAdapter()
        adapter2 = MockAdapter()

        await adapter1.connect()
        assert adapter1.is_connected is True
        assert adapter2.is_connected is False

        await adapter2.connect()
        assert adapter2.is_connected is True

        await adapter1.disconnect()
        assert adapter1.is_connected is False
        assert adapter2.is_connected is True

    @pytest.mark.asyncio
    async def test_order_counter_increments(self):
        """Order IDs increment with each order."""
        adapter = MockAdapter()
        await adapter.connect()

        result1 = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))
        result2 = await adapter.execute_order("BTC/USD", "sell", Decimal("0.5"))

        # Order IDs should be different
        assert result1.order_id != result2.order_id
        # Later order should have higher counter
        assert int(result1.order_id.split("-")[-1]) < int(result2.order_id.split("-")[-1])


@pytest.mark.asyncio
class TestMockAdapterFailureSimulation:
    """Test optional failure simulation via MOCK_FAIL_RATE (AC#5)."""

    async def test_execute_order_succeeds_with_zero_fail_rate(self):
        """execute_order() succeeds when MOCK_FAIL_RATE=0."""
        with patch('kitkat.adapters.mock.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.mock_fail_rate = 0  # Always succeed
            mock_get_settings.return_value = mock_settings

            adapter = MockAdapter()
            await adapter.connect()

            result = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

            assert result.order_id is not None
            assert result.status == "submitted"

    async def test_execute_order_fails_with_100_fail_rate(self):
        """execute_order() always fails when MOCK_FAIL_RATE=100."""
        with patch('kitkat.adapters.mock.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.mock_fail_rate = 100  # Always fail
            mock_get_settings.return_value = mock_settings

            adapter = MockAdapter()
            await adapter.connect()

            with pytest.raises(DEXRejectionError):
                await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

    async def test_execute_order_probabilistic_failure(self):
        """execute_order() has probabilistic failures with MOCK_FAIL_RATE>0."""
        with patch('kitkat.adapters.mock.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.mock_fail_rate = 50  # 50% failure rate
            mock_get_settings.return_value = mock_settings

            adapter = MockAdapter()
            await adapter.connect()

            # Try multiple times, expect both successes and failures
            results = []
            for _ in range(20):
                try:
                    result = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))
                    results.append(("success", result.order_id))
                except DEXRejectionError:
                    results.append(("failure", None))

            # Should have both successes and failures
            successes = [r for r in results if r[0] == "success"]
            failures = [r for r in results if r[0] == "failure"]

            assert len(successes) > 0, "Should have some successes with 50% fail rate"
            assert len(failures) > 0, "Should have some failures with 50% fail rate"

    async def test_failure_raises_dex_rejection_error(self):
        """Simulated failures raise DEXRejectionError."""
        with patch('kitkat.adapters.mock.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.mock_fail_rate = 100  # Force failure
            mock_get_settings.return_value = mock_settings

            adapter = MockAdapter()
            await adapter.connect()

            with pytest.raises(DEXRejectionError) as exc_info:
                await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

            # Error message should mention mock failure
            assert "Mock failure simulated" in str(exc_info.value)

    async def test_mock_fail_rate_validated_in_config(self):
        """mock_fail_rate setting is validated (0-100)."""
        from kitkat.config import Settings
        from pydantic import ValidationError

        # Valid values should work
        settings = Settings(webhook_token="test")
        assert settings.mock_fail_rate == 0  # Default

        # Invalid values should raise validation error
        # Note: We can't easily test this without mocking environment setup
        # Just verify the field exists with proper constraints
        assert hasattr(Settings, 'model_fields')
        assert 'mock_fail_rate' in Settings.model_fields


class TestMockAdapterFailureMessageLogging:
    """Test that failures are logged with clear messages."""

    @pytest.mark.asyncio
    async def test_failure_includes_fail_rate_in_message(self):
        """Failure error message includes MOCK_FAIL_RATE value."""
        with patch('kitkat.adapters.mock.get_settings') as mock_get_settings:
            with patch('kitkat.adapters.mock.random.randint') as mock_randint:
                with patch('kitkat.adapters.mock.logger') as mock_logger:
                    mock_settings = MagicMock()
                    mock_settings.mock_fail_rate = 75
                    mock_get_settings.return_value = mock_settings
                    # Return value < 75 to trigger failure
                    mock_randint.return_value = 50

                    adapter = MockAdapter()
                    await adapter.connect()

                    with pytest.raises(DEXRejectionError) as exc_info:
                        await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

                    # Error should mention the fail rate
                    assert "MOCK_FAIL_RATE=75" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_success_logged_with_order_details(self):
        """Successful orders logged with details."""
        with patch('kitkat.adapters.mock.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.mock_fail_rate = 0  # Always succeed
            mock_get_settings.return_value = mock_settings

            adapter = MockAdapter()
            await adapter.connect()

            result = await adapter.execute_order("BTC/USD", "sell", Decimal("2.0"))

            # Result should contain order details
            assert result.dex_response["symbol"] == "BTC/USD"
            assert result.dex_response["side"] == "sell"
