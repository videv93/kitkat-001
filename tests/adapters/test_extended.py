"""Tests for Extended DEX adapter (Story 2.5).

Tests cover connection establishment, WebSocket management, health checks,
and graceful disconnection per acceptance criteria.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from kitkat.adapters.base import DEXAdapter
from kitkat.adapters.exceptions import DEXConnectionError
from kitkat.config import Settings
from kitkat.models import HealthStatus

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
# Task 5 Tests: Placeholder stubs
# =============================================================================


class TestPlaceholderStubs:
    """Tests for Task 5: Placeholder stubs for Story 2.6 methods."""

    @pytest.mark.asyncio
    async def test_execute_order_raises_not_implemented(self, extended_adapter):
        """Subtask 5.1: execute_order() raises NotImplementedError."""
        from decimal import Decimal

        with pytest.raises(NotImplementedError):
            await extended_adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

    @pytest.mark.asyncio
    async def test_get_order_status_raises_not_implemented(self, extended_adapter):
        """Subtask 5.2: get_order_status() raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await extended_adapter.get_order_status("order-123")

    @pytest.mark.asyncio
    async def test_get_position_raises_not_implemented(self, extended_adapter):
        """Subtask 5.3: get_position() raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await extended_adapter.get_position("ETH/USD")

    @pytest.mark.asyncio
    async def test_cancel_order_raises_not_implemented(self, extended_adapter):
        """Subtask 5.4: cancel_order() raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await extended_adapter.cancel_order("order-123")


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
