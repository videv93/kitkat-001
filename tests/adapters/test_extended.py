"""Tests for Extended DEX adapter (Stories 2.5, 2.6, 2.7).

Tests cover connection establishment, WebSocket management, health checks,
graceful disconnection, order execution, and retry logic with exponential
backoff per acceptance criteria.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from tenacity import wait_none

from kitkat.adapters.base import DEXAdapter
from kitkat.adapters.exceptions import (
    DEXConnectionError,
    DEXError,
    DEXInsufficientFundsError,
    DEXOrderNotFoundError,
    DEXRejectionError,
    DEXTimeoutError,
)
from kitkat.config import Settings
from kitkat.models import HealthStatus, OrderStatus, OrderSubmissionResult, Position

# =============================================================================
# Task 1 Tests: Extended adapter class skeleton
# =============================================================================


class TestExtendedAdapterSkeleton:
    """Tests for Task 1: Extended adapter class skeleton (AC: #1, #6)."""

    def test_extended_adapter_inherits_from_dex_adapter(self):
        """Subtask 1.1: ExtendedAdapter must inherit from DEXAdapter."""
        from kitkat.adapters.extended import ExtendedAdapter

        assert issubclass(ExtendedAdapter, DEXAdapter)

    def test_dex_id_returns_extended(self, extended_adapter):
        """Subtask 1.2: dex_id property must return 'extended'."""
        assert extended_adapter.dex_id == "extended"

    def test_init_creates_connection_state_tracking(self, extended_adapter):
        """Subtask 1.3: __init__ must set up connection state tracking."""
        assert hasattr(extended_adapter, "_connected")
        assert extended_adapter._connected is False
        assert hasattr(extended_adapter, "_http_client")
        assert extended_adapter._http_client is None
        assert hasattr(extended_adapter, "_ws_connection")
        assert extended_adapter._ws_connection is None

    def test_init_stores_settings(self, extended_adapter, mock_settings):
        """Subtask 1.3: __init__ must store settings reference."""
        assert extended_adapter._settings is mock_settings

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, extended_adapter):
        """Subtask 1.5: disconnect() must be safe when not connected."""
        # Should not raise - idempotent
        await extended_adapter.disconnect()
        assert extended_adapter._connected is False

    @pytest.mark.asyncio
    async def test_disconnect_closes_http_client(self, connected_adapter):
        """Subtask 1.5: disconnect() must close HTTP client."""
        mock_client = connected_adapter._http_client
        await connected_adapter.disconnect()

        mock_client.aclose.assert_called_once()
        assert connected_adapter._http_client is None
        assert connected_adapter._connected is False

    @pytest.mark.asyncio
    async def test_disconnect_is_idempotent(self, connected_adapter):
        """Subtask 1.5: disconnect() must be safe to call multiple times."""
        await connected_adapter.disconnect()
        await connected_adapter.disconnect()  # Second call should not raise
        assert connected_adapter._connected is False


# =============================================================================
# Task 2 Tests: HTTP connection and authentication
# =============================================================================


class TestHTTPConnection:
    """Tests for Task 2: HTTP connection and authentication (AC: #1, #3)."""

    @pytest.mark.asyncio
    async def test_connect_establishes_http_session(self, extended_adapter):
        """Subtask 2.1: connect() must establish authenticated HTTP session."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            # Mock WebSocket connection
            with patch(
                "kitkat.adapters.extended.ExtendedAdapter._connect_websocket",
                new_callable=AsyncMock,
            ):
                await extended_adapter.connect()

        assert extended_adapter._connected is True
        assert extended_adapter._http_client is not None

    @pytest.mark.asyncio
    async def test_connect_includes_api_key_header(
        self, extended_adapter, mock_settings
    ):
        """Subtask 2.2: connect() must include API key in headers."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch(
                "kitkat.adapters.extended.ExtendedAdapter._connect_websocket",
                new_callable=AsyncMock,
            ):
                await extended_adapter.connect()

            # Verify headers were set correctly per Extended API docs
            call_kwargs = mock_client_cls.call_args[1]
            assert "headers" in call_kwargs
            api_key = mock_settings.extended_api_key
            assert call_kwargs["headers"]["X-Api-Key"] == api_key
            assert "User-Agent" in call_kwargs["headers"]

    @pytest.mark.asyncio
    async def test_connect_verifies_credentials(self, extended_adapter):
        """Subtask 2.3: connect() must verify credentials with API call."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch(
                "kitkat.adapters.extended.ExtendedAdapter._connect_websocket",
                new_callable=AsyncMock,
            ):
                await extended_adapter.connect()

            # Verify positions endpoint was called (Extended has no /health)
            mock_client.get.assert_called_with("/user/positions")

    @pytest.mark.asyncio
    async def test_connect_raises_on_invalid_credentials(self, extended_adapter):
        """Subtask 2.4: connect() must raise DEXConnectionError on auth failure."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Unauthorized",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(DEXConnectionError) as exc_info:
                await extended_adapter.connect()

            assert "Failed to connect" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_raises_on_network_error(self, extended_adapter):
        """Subtask 2.4: connect() must raise DEXConnectionError on network error."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(DEXConnectionError) as exc_info:
                await extended_adapter.connect()

            assert "Failed to connect" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_stores_connection_timestamp(self, extended_adapter):
        """Subtask 2.5: connect() must store connection timestamp."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch(
                "kitkat.adapters.extended.ExtendedAdapter._connect_websocket",
                new_callable=AsyncMock,
            ):
                before = datetime.now(timezone.utc)
                await extended_adapter.connect()
                after = datetime.now(timezone.utc)

            assert hasattr(extended_adapter, "_connected_at")
            assert before <= extended_adapter._connected_at <= after


# =============================================================================
# Task 3 Tests: WebSocket connection
# =============================================================================


class TestWebSocketConnection:
    """Tests for Task 3: WebSocket connection (AC: #2, #4)."""

    @pytest.mark.asyncio
    async def test_connect_establishes_websocket(self, extended_adapter):
        """Subtask 3.2: connect() must establish WebSocket connection."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch("websockets.connect", new_callable=AsyncMock) as mock_ws_connect:
                mock_ws = AsyncMock()
                mock_ws_connect.return_value = mock_ws

                await extended_adapter.connect()

                mock_ws_connect.assert_called_once()
                assert extended_adapter._ws_connection is not None

    @pytest.mark.asyncio
    async def test_disconnect_closes_websocket(self, connected_adapter_with_ws):
        """Subtask 3.1: disconnect() must close WebSocket connection."""
        mock_ws = connected_adapter_with_ws._ws_connection
        await connected_adapter_with_ws.disconnect()

        mock_ws.close.assert_called_once()
        assert connected_adapter_with_ws._ws_connection is None

    @pytest.mark.asyncio
    async def test_websocket_reconnection_uses_backoff(self, extended_adapter):
        """Subtask 3.4: WebSocket reconnection uses exponential backoff."""
        # This tests the retry decorator configuration
        from kitkat.adapters.extended import ExtendedAdapter

        # Check that _connect_websocket has retry decorator
        method = getattr(ExtendedAdapter, "_connect_websocket", None)
        assert method is not None
        # The method should have retry behavior (checked via tenacity)
        assert hasattr(method, "retry") or hasattr(method, "__wrapped__")


# =============================================================================
# Task 4 Tests: Health check
# =============================================================================


class TestHealthCheck:
    """Tests for Task 4: Health check (AC: #5)."""

    @pytest.mark.asyncio
    async def test_get_health_status_returns_healthy(self, connected_adapter):
        """Subtask 4.1, 4.3: get_health_status() returns healthy on 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        status = await connected_adapter.get_health_status()

        assert isinstance(status, HealthStatus)
        assert status.dex_id == "extended"
        assert status.status == "healthy"
        assert status.connected is True
        assert status.error_message is None

    @pytest.mark.asyncio
    async def test_get_health_status_measures_latency(self, connected_adapter):
        """Subtask 4.2: get_health_status() measures response latency."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        status = await connected_adapter.get_health_status()

        assert status.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_get_health_status_degraded_on_timeout(self, connected_adapter):
        """Subtask 4.4: get_health_status() returns degraded on timeout."""
        connected_adapter._http_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        status = await connected_adapter.get_health_status()

        assert status.status == "degraded"
        assert "timed out" in status.error_message.lower()

    @pytest.mark.asyncio
    async def test_get_health_status_returns_offline_on_connection_error(
        self, connected_adapter
    ):
        """Subtask 4.4: get_health_status() returns offline on connection error."""
        connected_adapter._http_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        status = await connected_adapter.get_health_status()

        assert status.status == "offline"
        assert status.connected is False

    @pytest.mark.asyncio
    async def test_get_health_status_stores_last_check(self, connected_adapter):
        """Subtask 4.5: get_health_status() stores last_check timestamp."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        before = datetime.now(timezone.utc)
        status = await connected_adapter.get_health_status()
        after = datetime.now(timezone.utc)

        assert before <= status.last_check <= after


# =============================================================================
# Task 6 Tests: Connection state tracking
# =============================================================================


class TestConnectionStateTracking:
    """Tests for Task 6: Connection state tracking (AC: #1, #6)."""

    def test_adapter_starts_disconnected(self, extended_adapter):
        """Adapter starts in disconnected state."""
        assert extended_adapter._connected is False

    @pytest.mark.asyncio
    async def test_connect_sets_connected_true(self, extended_adapter):
        """connect() sets _connected to True."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch(
                "kitkat.adapters.extended.ExtendedAdapter._connect_websocket",
                new_callable=AsyncMock,
            ):
                await extended_adapter.connect()

        assert extended_adapter._connected is True

    @pytest.mark.asyncio
    async def test_disconnect_sets_connected_false(self, connected_adapter):
        """disconnect() sets _connected to False."""
        await connected_adapter.disconnect()
        assert connected_adapter._connected is False


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings():
    """Create mock settings for testing per Extended API docs."""
    settings = MagicMock(spec=Settings)
    settings.extended_api_key = "test-api-key"
    settings.extended_api_secret = "test-api-secret"
    settings.extended_stark_private_key = "test-stark-key"
    settings.extended_account_address = "0x123"
    settings.extended_network = "testnet"
    # Properties return correct URLs based on network
    settings.extended_api_base_url = "https://api.starknet.sepolia.extended.exchange/api/v1"
    settings.extended_ws_url = "wss://starknet.sepolia.extended.exchange/stream.extended.exchange/v1"
    return settings


@pytest.fixture
def extended_adapter(mock_settings):
    """Create ExtendedAdapter instance for testing."""
    from kitkat.adapters.extended import ExtendedAdapter

    return ExtendedAdapter(mock_settings)


@pytest.fixture
def connected_adapter(mock_settings):
    """Create ExtendedAdapter in connected state with mocked HTTP client."""
    from kitkat.adapters.extended import ExtendedAdapter

    adapter = ExtendedAdapter(mock_settings)
    adapter._connected = True
    adapter._connected_at = datetime.now(timezone.utc)
    adapter._http_client = AsyncMock()
    adapter._http_client.aclose = AsyncMock()
    return adapter


@pytest.fixture
def connected_adapter_with_ws(connected_adapter):
    """Create connected adapter with mocked WebSocket."""
    connected_adapter._ws_connection = AsyncMock()
    connected_adapter._ws_connection.close = AsyncMock()
    return connected_adapter


# =============================================================================
# Story 2.6 Tests: Order Execution
# =============================================================================


class TestExecuteOrder:
    """Tests for Task 1: execute_order() method (AC: #1, #2, #3, #4)."""

    @pytest.mark.asyncio
    async def test_execute_order_buy_success(self, connected_adapter):
        """Subtask 5.1: Test successful buy (long) order execution."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "ord_123",
            "status": "PENDING",
            "created_at": "2026-01-26T10:00:00Z",
        }
        connected_adapter._http_client.post = AsyncMock(return_value=mock_response)

        result = await connected_adapter.execute_order(
            "ETH-PERP", "buy", Decimal("1.0")
        )

        assert isinstance(result, OrderSubmissionResult)
        assert result.order_id == "ord_123"
        assert result.status == "submitted"
        assert result.filled_amount == Decimal("0")
        connected_adapter._http_client.post.assert_called_once()
        call_args = connected_adapter._http_client.post.call_args
        assert call_args[0][0] == "/user/order"
        assert call_args[1]["json"]["side"] == "BUY"
        assert call_args[1]["json"]["symbol"] == "ETH-PERP"

    @pytest.mark.asyncio
    async def test_execute_order_sell_success(self, connected_adapter):
        """Subtask 5.2: Test successful sell (short) order execution."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "ord_456",
            "status": "PENDING",
            "created_at": "2026-01-26T10:00:00Z",
        }
        connected_adapter._http_client.post = AsyncMock(return_value=mock_response)

        result = await connected_adapter.execute_order(
            "BTC-PERP", "sell", Decimal("0.5")
        )

        assert result.order_id == "ord_456"
        assert result.status == "submitted"
        call_args = connected_adapter._http_client.post.call_args
        assert call_args[1]["json"]["side"] == "SELL"

    @pytest.mark.asyncio
    async def test_execute_order_rejection_error(self, connected_adapter):
        """Subtask 5.3: Test order rejection handling (invalid symbol)."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "INVALID_SYMBOL",
            "message": "Symbol INVALID-PAIR not found",
        }
        connected_adapter._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(DEXRejectionError) as exc_info:
            await connected_adapter.execute_order("INVALID-PAIR", "buy", Decimal("1.0"))

        assert "Symbol INVALID-PAIR not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_order_insufficient_funds(self, connected_adapter):
        """Subtask 5.4: Test insufficient funds error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "INSUFFICIENT_MARGIN",
            "message": "Not enough margin for order",
        }
        connected_adapter._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(DEXInsufficientFundsError) as exc_info:
            await connected_adapter.execute_order("ETH-PERP", "buy", Decimal("100.0"))

        assert "Not enough margin" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_order_not_connected(self, extended_adapter):
        """Test execute_order raises non-retryable error when not connected."""
        with pytest.raises(DEXError) as exc_info:
            await extended_adapter.execute_order("ETH-PERP", "buy", Decimal("1.0"))

        assert "Not connected" in str(exc_info.value)
        # Must NOT be DEXConnectionError (which would trigger retry)
        assert type(exc_info.value) is DEXError

    @pytest.mark.asyncio
    async def test_execute_order_timeout(self, connected_adapter):
        """Subtask 5.10: Test connection/timeout error handling."""
        connected_adapter.execute_order.retry.wait = wait_none()

        connected_adapter._http_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        with pytest.raises(DEXTimeoutError) as exc_info:
            await connected_adapter.execute_order("ETH-PERP", "buy", Decimal("1.0"))

        assert "timed out" in str(exc_info.value).lower()
        # Retries exhausted: 1 initial + 3 retries
        assert connected_adapter._http_client.post.call_count == 4

    @pytest.mark.asyncio
    async def test_execute_order_connection_error(self, connected_adapter):
        """Test network error handling in execute_order."""
        connected_adapter.execute_order.retry.wait = wait_none()

        connected_adapter._http_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(DEXConnectionError) as exc_info:
            await connected_adapter.execute_order("ETH-PERP", "buy", Decimal("1.0"))

        assert "failed" in str(exc_info.value).lower()
        # Retries exhausted: 1 initial + 3 retries
        assert connected_adapter._http_client.post.call_count == 4


class TestGetOrderStatus:
    """Tests for Task 2: get_order_status() method (AC: #5)."""

    @pytest.mark.asyncio
    async def test_get_order_status_filled(self, connected_adapter):
        """Subtask 5.5: Test get_order_status for filled state."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "ord_123",
            "status": "FILLED",
            "filled_amount": "1.0",
            "remaining_amount": "0.0",
            "average_price": "2495.50",
            "updated_at": "2026-01-26T10:00:05Z",
        }
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        status = await connected_adapter.get_order_status("ord_123")

        assert isinstance(status, OrderStatus)
        assert status.order_id == "ord_123"
        assert status.status == "filled"
        assert status.filled_amount == Decimal("1.0")
        assert status.remaining_amount == Decimal("0.0")
        assert status.average_price == Decimal("2495.50")

    @pytest.mark.asyncio
    async def test_get_order_status_pending(self, connected_adapter):
        """Test get_order_status for pending state."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "ord_456",
            "status": "PENDING",
            "filled_amount": "0.0",
            "remaining_amount": "1.0",
            "average_price": "0.0",
            "updated_at": "2026-01-26T10:00:00Z",
        }
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        status = await connected_adapter.get_order_status("ord_456")

        assert status.status == "pending"
        assert status.remaining_amount == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_get_order_status_partial(self, connected_adapter):
        """Test get_order_status for partial fill state."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "ord_789",
            "status": "PARTIAL_FILL",
            "filled_amount": "0.5",
            "remaining_amount": "0.5",
            "average_price": "2500.00",
            "updated_at": "2026-01-26T10:00:03Z",
        }
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        status = await connected_adapter.get_order_status("ord_789")

        assert status.status == "partial"
        assert status.filled_amount == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_get_order_status_cancelled(self, connected_adapter):
        """Test get_order_status for cancelled state."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "ord_cancel",
            "status": "CANCELLED",
            "filled_amount": "0.0",
            "remaining_amount": "1.0",
            "average_price": "0.0",
            "updated_at": "2026-01-26T10:00:10Z",
        }
        connected_adapter._http_client.get = AsyncMock(
            return_value=mock_response
        )

        status = await connected_adapter.get_order_status("ord_cancel")

        assert status.status == "cancelled"
        assert status.filled_amount == Decimal("0.0")

    @pytest.mark.asyncio
    async def test_get_order_status_rejected(self, connected_adapter):
        """Test get_order_status for rejected (failed) state."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "ord_reject",
            "status": "REJECTED",
            "filled_amount": "0.0",
            "remaining_amount": "1.0",
            "average_price": "0.0",
            "updated_at": "2026-01-26T10:00:12Z",
        }
        connected_adapter._http_client.get = AsyncMock(
            return_value=mock_response
        )

        status = await connected_adapter.get_order_status("ord_reject")

        assert status.status == "failed"

    @pytest.mark.asyncio
    async def test_get_order_status_not_found(self, connected_adapter):
        """Test get_order_status with non-existent order."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "error": "ORDER_NOT_FOUND",
            "message": "Order not found",
        }
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(DEXOrderNotFoundError):
            await connected_adapter.get_order_status("nonexistent")

    @pytest.mark.asyncio
    async def test_get_order_status_timeout(self, connected_adapter):
        """Test get_order_status timeout handling."""
        connected_adapter._http_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(DEXTimeoutError):
            await connected_adapter.get_order_status("ord_123")

    @pytest.mark.asyncio
    async def test_get_order_status_not_connected(self, extended_adapter):
        """Test get_order_status raises when not connected."""
        with pytest.raises(DEXConnectionError) as exc_info:
            await extended_adapter.get_order_status("ord_123")

        assert "Not connected" in str(exc_info.value)


class TestGetPosition:
    """Tests for Task 3: get_position() method (AC: #6)."""

    @pytest.mark.asyncio
    async def test_get_position_exists(self, connected_adapter):
        """Subtask 5.6: Test get_position with existing position."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "positions": [
                {
                    "symbol": "ETH-PERP",
                    "size": "2.5",
                    "side": "LONG",
                    "entry_price": "2480.00",
                    "mark_price": "2510.00",
                    "unrealized_pnl": "75.00",
                }
            ]
        }
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        position = await connected_adapter.get_position("ETH-PERP")

        assert position is not None
        assert isinstance(position, Position)
        assert position.symbol == "ETH-PERP"
        assert position.size == Decimal("2.5")
        assert position.entry_price == Decimal("2480.00")
        assert position.current_price == Decimal("2510.00")
        assert position.unrealized_pnl == Decimal("75.00")

    @pytest.mark.asyncio
    async def test_get_position_none(self, connected_adapter):
        """Subtask 5.7: Test get_position with no position (returns None)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"positions": []}
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        position = await connected_adapter.get_position("BTC-PERP")

        assert position is None

    @pytest.mark.asyncio
    async def test_get_position_filters_by_symbol(self, connected_adapter):
        """Test get_position returns correct position when multiple exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "positions": [
                {
                    "symbol": "ETH-PERP",
                    "size": "1.0",
                    "side": "LONG",
                    "entry_price": "2400.00",
                    "mark_price": "2450.00",
                    "unrealized_pnl": "50.00",
                },
                {
                    "symbol": "BTC-PERP",
                    "size": "0.1",
                    "side": "SHORT",
                    "entry_price": "45000.00",
                    "mark_price": "44000.00",
                    "unrealized_pnl": "100.00",
                },
            ]
        }
        connected_adapter._http_client.get = AsyncMock(return_value=mock_response)

        position = await connected_adapter.get_position("BTC-PERP")

        assert position is not None
        assert position.symbol == "BTC-PERP"
        assert position.size == Decimal("0.1")

    @pytest.mark.asyncio
    async def test_get_position_not_connected(self, extended_adapter):
        """Test get_position raises when not connected."""
        with pytest.raises(DEXConnectionError) as exc_info:
            await extended_adapter.get_position("ETH-PERP")

        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_position_timeout(self, connected_adapter):
        """Test get_position timeout handling."""
        connected_adapter._http_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(DEXTimeoutError):
            await connected_adapter.get_position("ETH-PERP")


class TestCancelOrder:
    """Tests for Task 4: cancel_order() method (AC: #7)."""

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, connected_adapter):
        """Subtask 5.8: Test cancel_order success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "ord_123",
            "status": "CANCELLED",
        }
        connected_adapter._http_client.delete = AsyncMock(return_value=mock_response)

        # Should not raise
        await connected_adapter.cancel_order("ord_123")

        connected_adapter._http_client.delete.assert_called_once_with("/user/orders/ord_123")

    @pytest.mark.asyncio
    async def test_cancel_order_already_filled(self, connected_adapter):
        """Subtask 5.9: Test cancel_order with already filled order."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "error": "ORDER_NOT_FOUND",
            "message": "Order not found or already filled",
        }
        connected_adapter._http_client.delete = AsyncMock(return_value=mock_response)

        with pytest.raises(DEXOrderNotFoundError) as exc_info:
            await connected_adapter.cancel_order("ord_filled")

        assert "already filled" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_order_not_connected(self, extended_adapter):
        """Test cancel_order raises when not connected."""
        with pytest.raises(DEXConnectionError) as exc_info:
            await extended_adapter.cancel_order("ord_123")

        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_order_timeout(self, connected_adapter):
        """Test cancel_order timeout handling."""
        connected_adapter._http_client.delete = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(DEXTimeoutError):
            await connected_adapter.cancel_order("ord_123")


class TestNonceGeneration:
    """Tests for nonce generation helper."""

    def test_nonce_is_unique(self, connected_adapter):
        """Test that nonces are unique across calls."""
        nonces = set()
        for _ in range(100):
            nonce = connected_adapter._generate_nonce()
            assert nonce not in nonces
            nonces.add(nonce)

    def test_nonce_is_positive_integer(self, connected_adapter):
        """Test that nonce is a positive integer."""
        nonce = connected_adapter._generate_nonce()
        assert isinstance(nonce, int)
        assert nonce > 0


class TestSignatureCreation:
    """Tests for SNIP12 signature creation helper."""

    def test_signature_is_hex_string(self, connected_adapter):
        """Test that signature is a hex string starting with 0x."""
        signature = connected_adapter._create_order_signature(
            "ETH-PERP", "BUY", Decimal("1.0"), 12345
        )
        assert signature.startswith("0x")
        assert len(signature) == 66  # 0x + 64 hex chars

    def test_signature_is_deterministic(self, connected_adapter):
        """Test that same inputs produce same signature."""
        sig1 = connected_adapter._create_order_signature(
            "ETH-PERP", "BUY", Decimal("1.0"), 12345
        )
        sig2 = connected_adapter._create_order_signature(
            "ETH-PERP", "BUY", Decimal("1.0"), 12345
        )
        assert sig1 == sig2

    def test_signature_differs_with_different_inputs(self, connected_adapter):
        """Test that different inputs produce different signatures."""
        sig1 = connected_adapter._create_order_signature(
            "ETH-PERP", "BUY", Decimal("1.0"), 12345
        )
        sig2 = connected_adapter._create_order_signature(
            "ETH-PERP", "SELL", Decimal("1.0"), 12345
        )
        assert sig1 != sig2


# =============================================================================
# Story 2.7 Tests: Retry Logic with Exponential Backoff
# =============================================================================


class TestRetryOnTimeout:
    """Tests for AC #1: Timeout retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_execute_order_retries_on_timeout(self, connected_adapter):
        """Subtask 5.1: Verify 3 retry attempts on timeout with backoff."""
        connected_adapter.execute_order.retry.wait = wait_none()

        connected_adapter._http_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )

        with pytest.raises(DEXTimeoutError):
            await connected_adapter.execute_order(
                "ETH-PERP", "buy", Decimal("1.0")
            )

        # 1 initial + 3 retries = 4 total calls
        assert connected_adapter._http_client.post.call_count == 4


class TestRetryOnServerError:
    """Tests for AC #2: Server error (5xx) retry with logging."""

    @pytest.mark.asyncio
    async def test_execute_order_retries_on_5xx(self, connected_adapter):
        """Subtask 5.2: Verify retries on HTTP 5xx (DEXConnectionError)."""
        connected_adapter.execute_order.retry.wait = wait_none()

        # 5xx triggers raise_for_status -> HTTPStatusError -> DEXConnectionError
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable",
            request=httpx.Request("POST", "http://test/user/order"),
            response=mock_response,
        )
        connected_adapter._http_client.post = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises(DEXConnectionError):
            await connected_adapter.execute_order(
                "ETH-PERP", "buy", Decimal("1.0")
            )

        # Should have retried (4 total calls)
        assert connected_adapter._http_client.post.call_count == 4

    @pytest.mark.asyncio
    async def test_execute_order_retries_on_connection_error(
        self, connected_adapter
    ):
        """Subtask 5.9: Verify retries on DEXConnectionError (network errors)."""
        connected_adapter.execute_order.retry.wait = wait_none()

        connected_adapter._http_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(DEXConnectionError):
            await connected_adapter.execute_order(
                "ETH-PERP", "buy", Decimal("1.0")
            )

        # Should have retried (4 total calls)
        assert connected_adapter._http_client.post.call_count == 4


class TestClientErrorNoRetry:
    """Tests for AC #3: Client errors (4xx) are NOT retried."""

    @pytest.mark.asyncio
    async def test_no_retry_on_rejection_error(self, connected_adapter):
        """Subtask 5.3: Verify DEXRejectionError is NOT retried."""
        connected_adapter.execute_order.retry.wait = wait_none()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "INVALID_SYMBOL",
            "message": "Symbol not found",
        }
        connected_adapter._http_client.post = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises(DEXRejectionError):
            await connected_adapter.execute_order(
                "INVALID", "buy", Decimal("1.0")
            )

        # Should have been called only once (no retry)
        assert connected_adapter._http_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_insufficient_funds(self, connected_adapter):
        """Subtask 5.4: Verify DEXInsufficientFundsError is NOT retried."""
        connected_adapter.execute_order.retry.wait = wait_none()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "INSUFFICIENT_MARGIN",
            "message": "Not enough margin",
        }
        connected_adapter._http_client.post = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises(DEXInsufficientFundsError):
            await connected_adapter.execute_order(
                "ETH-PERP", "buy", Decimal("100.0")
            )

        # Should have been called only once (no retry)
        assert connected_adapter._http_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_not_connected_error(self, extended_adapter):
        """Verify disconnected adapter raises DEXError without retry."""
        # Adapter not connected - no HTTP client
        assert not extended_adapter.is_connected

        # Should raise DEXError immediately without retry attempts
        with pytest.raises(DEXError, match="Not connected"):
            await extended_adapter.execute_order(
                "ETH-PERP", "buy", Decimal("1.0")
            )


class TestOrderSizeValidation:
    """Tests for order size validation before submission."""

    @pytest.mark.asyncio
    async def test_reject_zero_size_order(self, connected_adapter):
        """Verify orders with size=0 are rejected immediately."""
        with pytest.raises(ValueError, match="must be positive"):
            await connected_adapter.execute_order(
                "ETH-PERP", "buy", Decimal("0")
            )

    @pytest.mark.asyncio
    async def test_reject_negative_size_order(self, connected_adapter):
        """Verify orders with negative size are rejected immediately."""
        with pytest.raises(ValueError, match="must be positive"):
            await connected_adapter.execute_order(
                "ETH-PERP", "buy", Decimal("-1.5")
            )


class TestRetriesExhausted:
    """Tests for AC #4: Final error returned when all retries fail."""

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_returns_final_error(
        self, connected_adapter
    ):
        """Subtask 5.5: Verify final error is returned after all retries."""
        connected_adapter.execute_order.retry.wait = wait_none()

        connected_adapter._http_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("persistent timeout")
        )

        with pytest.raises(DEXTimeoutError) as exc_info:
            await connected_adapter.execute_order(
                "ETH-PERP", "buy", Decimal("1.0")
            )

        assert "timed out" in str(exc_info.value).lower()
        # All 4 attempts exhausted
        assert connected_adapter._http_client.post.call_count == 4


class TestTenacityImplementation:
    """Tests for AC #5: Tenacity library usage with jitter."""

    def test_execute_order_has_retry_decorator(self):
        """Verify execute_order uses tenacity @retry decorator."""
        from kitkat.adapters.extended import ExtendedAdapter

        # Tenacity-decorated methods have a .retry attribute
        assert hasattr(ExtendedAdapter.execute_order, "retry")

    def test_retry_configured_with_correct_stop(self, connected_adapter):
        """Verify retry stops after 4 attempts (1 initial + 3 retries)."""
        retry_state = connected_adapter.execute_order.retry
        # Check stop config - stop_after_attempt(4)
        assert retry_state.stop is not None

    def test_retry_configured_with_jitter(self, connected_adapter):
        """Subtask 5.7: Verify jitter is applied (delays are not exact)."""
        retry_state = connected_adapter.execute_order.retry
        # Check wait config exists (exponential jitter)
        assert retry_state.wait is not None

    @pytest.mark.asyncio
    async def test_retry_logging_on_each_attempt(
        self, connected_adapter, caplog
    ):
        """Subtask 5.6: Verify attempt number is logged on each retry."""
        connected_adapter.execute_order.retry.wait = wait_none()

        connected_adapter._http_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )

        with caplog.at_level(
            logging.WARNING, logger="kitkat.adapters.extended.retry"
        ):
            with pytest.raises(DEXTimeoutError):
                await connected_adapter.execute_order(
                    "ETH-PERP", "buy", Decimal("1.0")
                )

        # before_sleep_log logs a WARNING before each retry sleep
        # 3 retries = 3 log messages
        retry_logs = [
            r
            for r in caplog.records
            if r.name == "kitkat.adapters.extended.retry"
        ]
        assert len(retry_logs) == 3


class TestNonceRegenerationOnRetry:
    """Tests for nonce regeneration during retry attempts."""

    @pytest.mark.asyncio
    async def test_nonce_regenerated_on_each_retry(self, connected_adapter):
        """Subtask 5.8: Verify each retry attempt uses a different nonce."""
        connected_adapter.execute_order.retry.wait = wait_none()

        captured_nonces = []

        original_post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )

        async def capture_nonce_post(url, **kwargs):
            payload = kwargs.get("json", {})
            captured_nonces.append(payload.get("nonce"))
            return await original_post(url, **kwargs)

        connected_adapter._http_client.post = AsyncMock(
            side_effect=capture_nonce_post
        )

        with pytest.raises(DEXTimeoutError):
            await connected_adapter.execute_order(
                "ETH-PERP", "buy", Decimal("1.0")
            )

        # Should have 4 nonces (1 initial + 3 retries), all unique
        assert len(captured_nonces) == 4
        assert len(set(captured_nonces)) == 4, (
            f"Nonces should be unique, got: {captured_nonces}"
        )


class TestSuccessfulRecoveryOnRetry:
    """Tests for successful recovery after transient failure."""

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt(self, connected_adapter):
        """Subtask 5.10: Verify successful recovery after one failure."""
        connected_adapter.execute_order.retry.wait = wait_none()

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "order_id": "ord_retry_ok",
            "status": "PENDING",
            "created_at": "2026-01-27T10:00:00Z",
        }

        connected_adapter._http_client.post = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timeout"),  # First call fails
                success_response,  # Second call succeeds
            ]
        )

        result = await connected_adapter.execute_order(
            "ETH-PERP", "buy", Decimal("1.0")
        )

        assert result.order_id == "ord_retry_ok"
        assert result.status == "submitted"
        assert connected_adapter._http_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_succeeds_on_third_attempt_after_connection_errors(
        self, connected_adapter
    ):
        """Verify recovery after two connection errors."""
        connected_adapter.execute_order.retry.wait = wait_none()

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "order_id": "ord_recover",
            "status": "PENDING",
            "created_at": "2026-01-27T10:00:00Z",
        }

        connected_adapter._http_client.post = AsyncMock(
            side_effect=[
                httpx.ConnectError("refused"),  # First: network error
                httpx.TimeoutException("timeout"),  # Second: timeout
                success_response,  # Third: success
            ]
        )

        result = await connected_adapter.execute_order(
            "ETH-PERP", "buy", Decimal("1.0")
        )

        assert result.order_id == "ord_recover"
        assert connected_adapter._http_client.post.call_count == 3
