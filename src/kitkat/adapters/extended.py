"""Extended DEX adapter implementation (Story 2.5).

Implements DEXAdapter interface for Extended DEX with HTTP REST API
and WebSocket connections for real-time updates.

API Documentation: https://api.docs.extended.exchange/
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Awaitable, Callable, Literal, Optional

import httpx
import structlog
import websockets
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from kitkat.adapters.base import DEXAdapter
from kitkat.adapters.exceptions import DEXConnectionError
from kitkat.config import Settings
from kitkat.models import (
    ConnectParams,
    HealthStatus,
    OrderStatus,
    OrderSubmissionResult,
    OrderUpdate,
    Position,
)

logger = structlog.get_logger(__name__)

# Extended API constants
USER_AGENT = "kitkat/1.0"


class ExtendedAdapter(DEXAdapter):
    """Extended DEX adapter implementation.

    Connects to Extended DEX via HTTP REST API and WebSocket for real-time
    order updates. Implements all DEXAdapter interface methods.

    API Base URLs:
    - Mainnet: https://api.starknet.extended.exchange/api/v1
    - Testnet: https://api.starknet.sepolia.extended.exchange/api/v1

    WebSocket URLs:
    - Mainnet: wss://api.starknet.extended.exchange/stream.extended.exchange/v1
    - Testnet: wss://starknet.sepolia.extended.exchange/stream.extended.exchange/v1

    Authentication:
    - HTTP: X-Api-Key header + User-Agent (required)
    - Orders: Additional StarkKey signature (SNIP12 standard) for order endpoints

    Rate Limits:
    - Standard: 1,000 requests/minute
    - Market Makers: 60,000 requests/5 minutes

    Connection workflow:
    1. connect() establishes HTTP session with API key authentication
    2. connect() verifies credentials with API call
    3. connect() establishes WebSocket for real-time updates
    4. disconnect() closes all connections gracefully
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize Extended adapter with settings.

        Args:
            settings: Application settings containing Extended API credentials
        """
        self._settings = settings
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self._connected: bool = False
        self._connected_at: Optional[datetime] = None
        self._last_health_check: Optional[datetime] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._log = logger.bind(dex_id=self.dex_id)

    @property
    def dex_id(self) -> str:
        """Return unique identifier for Extended DEX."""
        return "extended"

    async def connect(self, params: Optional[ConnectParams] = None) -> None:
        """Establish connection to Extended DEX.

        Creates HTTP client with API key authentication, verifies credentials
        by calling an API endpoint, and establishes WebSocket connection.

        Args:
            params: Optional connection params (not used - credentials from settings)

        Raises:
            DEXConnectionError: If connection or authentication fails
        """
        self._log.info(
            "Connecting to Extended DEX",
            network=self._settings.extended_network,
        )

        # Create HTTP client with authentication headers per Extended API docs
        # Required: X-Api-Key and User-Agent headers
        self._http_client = httpx.AsyncClient(
            base_url=self._settings.extended_api_base_url,
            headers={
                "X-Api-Key": self._settings.extended_api_key,
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(10.0),
        )

        # Verify credentials by fetching positions (requires valid API key)
        # Extended API doesn't have explicit /health - use /user/positions
        try:
            response = await self._http_client.get("/user/positions")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            await self._cleanup_http_client()
            self._log.error(
                "Authentication failed",
                status_code=e.response.status_code,
            )
            status_code = e.response.status_code
            raise DEXConnectionError(
                f"Failed to connect to Extended DEX: auth failed ({status_code})"
            ) from e
        except httpx.HTTPError as e:
            await self._cleanup_http_client()
            self._log.error("Connection failed", error=str(e))
            raise DEXConnectionError(
                f"Failed to connect to Extended DEX: {e}"
            ) from e

        # Establish WebSocket connection
        try:
            await self._connect_websocket()
        except (RetryError, Exception) as e:
            await self._cleanup_http_client()
            self._log.error("WebSocket connection failed", error=str(e))
            raise DEXConnectionError(
                f"Failed to establish WebSocket connection: {e}"
            ) from e

        self._connected = True
        self._connected_at = datetime.now(timezone.utc)
        self._log.info(
            "Connected to Extended DEX",
            network=self._settings.extended_network,
            connected_at=self._connected_at.isoformat(),
        )

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
        retry=retry_if_exception_type((ConnectionError, OSError)),
        reraise=True,
    )
    async def _connect_websocket(self) -> None:
        """Establish WebSocket connection with auto-retry.

        Uses exponential backoff with jitter for reconnection attempts.
        WebSocket URL from Extended API docs:
        - Mainnet: wss://api.starknet.extended.exchange/stream.extended.exchange/v1
        - Testnet: wss://starknet.sepolia.extended.exchange/stream.extended.exchange/v1
        """
        ws_url = self._settings.extended_ws_url
        self._log.debug("Connecting to WebSocket", url=ws_url)

        # Extended WebSocket requires User-Agent header
        extra_headers = {
            "User-Agent": USER_AGENT,
            "X-Api-Key": self._settings.extended_api_key,
        }

        self._ws_connection = await websockets.connect(
            ws_url,
            additional_headers=extra_headers,
            ping_interval=20,
            ping_timeout=10,
        )

        self._log.debug("WebSocket connected")

    async def _cleanup_http_client(self) -> None:
        """Clean up HTTP client resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def _cleanup_websocket(self) -> None:
        """Clean up WebSocket resources."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None

    async def disconnect(self) -> None:
        """Disconnect from Extended DEX.

        Closes HTTP client, WebSocket connection, and cancels background tasks.
        Idempotent - safe to call multiple times.
        """
        self._log.info("Disconnecting from Extended DEX")

        await self._cleanup_websocket()
        await self._cleanup_http_client()

        self._connected = False
        self._connected_at = None
        self._log.info("Disconnected from Extended DEX")

    async def get_health_status(self) -> HealthStatus:
        """Get Extended DEX connection health status.

        Pings the positions endpoint and measures response latency.
        Extended API doesn't have explicit /health endpoint.

        Returns:
            HealthStatus with connection info and latency
        """
        start = time.monotonic()
        now = datetime.now(timezone.utc)

        if not self._http_client:
            return HealthStatus(
                dex_id=self.dex_id,
                status="offline",
                connected=False,
                latency_ms=0,
                last_check=now,
                error_message="Not connected",
            )

        try:
            # Use positions endpoint as health check (requires valid API key)
            response = await self._http_client.get(
                "/user/positions",
                timeout=5.0,
            )
            latency = int((time.monotonic() - start) * 1000)

            if response.status_code == 200:
                status = "healthy"
                error_message = None
            elif response.status_code == 429:
                # Rate limited
                status = "degraded"
                error_message = "Rate limited (429)"
            elif response.status_code < 500:
                status = "degraded"
                error_message = f"Unexpected status code: {response.status_code}"
            else:
                status = "offline"
                error_message = f"Server error: {response.status_code}"

            self._last_health_check = now
            return HealthStatus(
                dex_id=self.dex_id,
                status=status,
                connected=self._connected,
                latency_ms=latency,
                last_check=now,
                error_message=error_message,
            )

        except httpx.TimeoutException:
            self._last_health_check = now
            return HealthStatus(
                dex_id=self.dex_id,
                status="degraded",
                connected=self._connected,
                latency_ms=5000,
                last_check=now,
                error_message="Health check timed out",
            )

        except httpx.HTTPError as e:
            self._last_health_check = now
            return HealthStatus(
                dex_id=self.dex_id,
                status="offline",
                connected=False,
                latency_ms=0,
                last_check=now,
                error_message=str(e),
            )

    # =========================================================================
    # Placeholder stubs for Story 2.6 (Order Execution)
    # =========================================================================

    async def execute_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        size: Decimal,
    ) -> OrderSubmissionResult:
        """Submit an order to Extended DEX.

        Not implemented - will be added in Story 2.6.

        Extended API endpoint: POST /user/order
        Requires StarkKey signature (SNIP12 standard) for order submission.

        Raises:
            NotImplementedError: Always (stub for Story 2.6)
        """
        raise NotImplementedError("execute_order will be implemented in Story 2.6")

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get order status from Extended DEX.

        Not implemented - will be added in Story 2.6.

        Extended API endpoint: GET /user/orders/{id}

        Raises:
            NotImplementedError: Always (stub for Story 2.6)
        """
        raise NotImplementedError("get_order_status will be implemented in Story 2.6")

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol from Extended DEX.

        Not implemented - will be added in Story 2.6.

        Extended API endpoint: GET /user/positions

        Raises:
            NotImplementedError: Always (stub for Story 2.6)
        """
        raise NotImplementedError("get_position will be implemented in Story 2.6")

    async def cancel_order(self, order_id: str) -> None:
        """Cancel an order on Extended DEX.

        Not implemented - will be added in Story 2.6.

        Raises:
            NotImplementedError: Always (stub for Story 2.6)
        """
        raise NotImplementedError("cancel_order will be implemented in Story 2.6")

    def subscribe_to_order_updates(
        self,
        callback: Callable[[OrderUpdate], Awaitable[None]],
    ):
        """Subscribe to real-time order updates via WebSocket.

        Not fully implemented - will be completed in Story 2.6.
        Returns no-op context manager (inherits from base class).

        Extended WebSocket provides Account Updates Stream for order
        confirmations, cancellations, rejections, and position changes.
        """
        # Use base class no-op implementation for now
        # Will be overridden with real WebSocket subscription in Story 2.6
        return super().subscribe_to_order_updates(callback)
