"""Extended DEX adapter implementation (Story 2.5).

Implements DEXAdapter interface for Extended DEX with HTTP REST API
and WebSocket connections for real-time updates.

API Documentation: https://api.docs.extended.exchange/
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Awaitable, Callable, Literal, Optional

import httpx
import structlog
import websockets
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

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
from kitkat.logging import ErrorType
from kitkat.services.error_logger import get_error_logger
from kitkat.models import (
    ConnectParams,
    HealthStatus,
    OrderStatus,
    OrderSubmissionResult,
    OrderUpdate,
    Position,
)

logger = structlog.get_logger(__name__)

# Standard logger for tenacity before_sleep_log (requires stdlib logger)
_tenacity_logger = logging.getLogger("kitkat.adapters.extended.retry")

# Extended API constants
USER_AGENT = "kitkat/1.0"

# Nonce counter for order uniqueness (simple in-memory, thread-safe with asyncio)
_nonce_counter = 0


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

    @property
    def is_connected(self) -> bool:
        """Check if adapter is currently connected."""
        return self._connected

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
            # Story 4.4: Log DEX connection error with full context
            get_error_logger().log_dex_error(
                dex_id=self.dex_id,
                error_type=ErrorType.DEX_CONNECTION_FAILED,
                error_message=f"Authentication failed ({e.response.status_code})",
                request_method="GET",
                request_url=str(self._settings.extended_api_base_url) + "/user/positions",
                response_status=e.response.status_code,
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
    # Order Execution Methods (Story 2.6)
    # =========================================================================

    def _generate_nonce(self) -> int:
        """Generate unique nonce for order submission.

        Uses microsecond timestamp combined with a monotonic counter
        to ensure uniqueness even across server restarts.

        Returns:
            Unique integer nonce for order identification.
        """
        global _nonce_counter
        _nonce_counter += 1
        # Microsecond timestamp avoids collisions across restarts
        timestamp_us = int(time.time() * 1_000_000)
        return (timestamp_us << 16) | (_nonce_counter & 0xFFFF)

    def _create_order_signature(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        nonce: int,
    ) -> str:
        """Create SNIP12 signature for order submission.

        Extended DEX requires typed data signatures per SNIP12 standard.
        This creates a deterministic signature based on order parameters.

        For production use with real Starknet signing, this would use
        the starknet.py library with the stark_private_key.

        Args:
            symbol: Trading pair symbol
            side: Order side (BUY/SELL)
            size: Order size
            nonce: Unique order nonce

        Returns:
            Hex-encoded signature string
        """
        # Create deterministic signature payload
        # In production, this would use proper SNIP12 typed data signing
        account = self._settings.extended_account_address
        message = f"{symbol}:{side}:{size}:{nonce}:{account}"
        signature_bytes = hashlib.sha256(message.encode()).hexdigest()
        return f"0x{signature_bytes}"

    @retry(
        stop=stop_after_attempt(4),  # 1 initial + 3 retries
        wait=wait_exponential_jitter(initial=1, max=8, jitter=2),
        retry=retry_if_exception_type((DEXConnectionError, DEXTimeoutError)),
        reraise=True,
        before_sleep=before_sleep_log(_tenacity_logger, logging.WARNING),
    )
    async def execute_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        size: Decimal,
    ) -> OrderSubmissionResult:
        """Submit an order to Extended DEX.

        Submits a market order to Extended DEX and returns immediately with
        the order ID. Use get_order_status() or subscribe_to_order_updates()
        to track actual fill status.

        Args:
            symbol: Trading pair (e.g., "ETH-PERP", "BTC-PERP")
            side: "buy" (long) or "sell" (short)
            size: Amount to trade (must be positive)

        Returns:
            OrderSubmissionResult with order_id and submission status

        Raises:
            DEXConnectionError: Not connected or network error
            DEXTimeoutError: Request timed out
            DEXRejectionError: Order rejected by DEX
            DEXInsufficientFundsError: Not enough margin/balance
        """
        # Validate order size before attempting submission
        # Must be positive - NaN, Infinity, or zero values should fail early
        if not size or size <= 0:
            raise ValueError(f"Order size must be positive, got: {size}")

        if not self._connected or not self._http_client:
            # Use DEXError (not DEXConnectionError) to prevent retry on disconnected adapter.
            # Tenacity decorator only retries DEXConnectionError and DEXTimeoutError.
            # If adapter is not connected, retrying won't help - user must reconnect first.
            raise DEXError("Not connected to Extended DEX")

        log = self._log.bind(symbol=symbol, side=side, size=str(size))
        log.info("Submitting order")

        # Generate unique nonce for this order
        nonce = self._generate_nonce()

        # Create SNIP12 signature
        signature = self._create_order_signature(symbol, side.upper(), size, nonce)

        # Build request payload per Extended API
        payload = {
            "symbol": symbol,
            "side": side.upper(),  # Extended uses uppercase
            "type": "MARKET",  # Market orders for signal execution
            "size": str(size),
            "signature": signature,
            "nonce": nonce,
        }

        try:
            response = await self._http_client.post("/user/order", json=payload)

            if response.status_code == 200:
                data = response.json()
                log.info("Order submitted", order_id=data["order_id"])
                return OrderSubmissionResult(
                    order_id=data["order_id"],
                    status="submitted",
                    submitted_at=datetime.now(timezone.utc),
                    filled_amount=Decimal("0"),
                    dex_response=data,
                )

            # Handle rejection errors (400)
            if response.status_code == 400:
                try:
                    error_data = response.json()
                except json.JSONDecodeError:
                    raise DEXRejectionError(
                        "Order rejected (HTTP 400)"
                    )
                error_code = error_data.get("error", "UNKNOWN")
                error_msg = error_data.get(
                    "message", "Order rejected"
                )

                log.warning(
                    "Order rejected",
                    error=error_code,
                    message=error_msg,
                )

                if error_code == "INSUFFICIENT_MARGIN":
                    raise DEXInsufficientFundsError(error_msg)
                raise DEXRejectionError(error_msg)

            # Handle other HTTP errors
            response.raise_for_status()

            # Should not reach here, but handle unexpected success status
            data = response.json()
            return OrderSubmissionResult(
                order_id=data.get("order_id", "unknown"),
                status="submitted",
                submitted_at=datetime.now(timezone.utc),
                filled_amount=Decimal("0"),
                dex_response=data,
            )

        except httpx.TimeoutException as e:
            log.error("Order timeout", error=str(e))
            # Story 4.4: Log DEX timeout with request context
            get_error_logger().log_dex_error(
                dex_id=self.dex_id,
                error_type=ErrorType.DEX_TIMEOUT,
                error_message=f"Order submission timed out: {e}",
                request_method="POST",
                request_url=str(self._settings.extended_api_base_url) + "/user/order",
            )
            raise DEXTimeoutError(f"Order submission timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            log.error("Order HTTP error", status_code=e.response.status_code)
            # Story 4.4: Log DEX error with response context
            get_error_logger().log_dex_error(
                dex_id=self.dex_id,
                error_type=ErrorType.DEX_ERROR,
                error_message=f"Order submission failed: HTTP {e.response.status_code}",
                request_method="POST",
                request_url=str(self._settings.extended_api_base_url) + "/user/order",
                response_status=e.response.status_code,
                response_body=e.response.text,
            )
            raise DEXConnectionError(
                f"Order submission failed: HTTP {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            log.error("Order failed", error=str(e))
            # Story 4.4: Log DEX connection error
            get_error_logger().log_dex_error(
                dex_id=self.dex_id,
                error_type=ErrorType.DEX_CONNECTION_FAILED,
                error_message=f"Order submission failed: {e}",
                request_method="POST",
                request_url=str(self._settings.extended_api_base_url) + "/user/order",
            )
            raise DEXConnectionError(f"Order submission failed: {e}") from e

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get order status from Extended DEX.

        Retrieves the current status and fill information for a submitted order.

        Args:
            order_id: Order ID returned by execute_order()

        Returns:
            OrderStatus with current fill information

        Raises:
            DEXConnectionError: Not connected or network error
            DEXTimeoutError: Request timed out
            DEXOrderNotFoundError: Order ID not found
        """
        if not self._connected or not self._http_client:
            raise DEXConnectionError("Not connected to Extended DEX")

        log = self._log.bind(order_id=order_id)
        log.debug("Getting order status")

        try:
            response = await self._http_client.get(f"/user/orders/{order_id}")

            if response.status_code == 200:
                data = response.json()

                # Map Extended status to our enum
                status_map = {
                    "PENDING": "pending",
                    "FILLED": "filled",
                    "PARTIAL_FILL": "partial",
                    "CANCELLED": "cancelled",
                    "REJECTED": "failed",
                }
                status = status_map.get(data["status"], "pending")

                return OrderStatus(
                    order_id=data["order_id"],
                    status=status,
                    filled_amount=Decimal(data["filled_amount"]),
                    remaining_amount=Decimal(data["remaining_amount"]),
                    average_price=Decimal(data["average_price"]),
                    last_updated=datetime.fromisoformat(
                        data["updated_at"].replace("Z", "+00:00")
                    ),
                )

            # Handle not found (404)
            if response.status_code == 404:
                try:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "message", "Order not found"
                    )
                except json.JSONDecodeError:
                    error_msg = "Order not found"
                log.warning("Order not found", order_id=order_id)
                raise DEXOrderNotFoundError(error_msg)

            response.raise_for_status()

            # Should not reach here
            raise DEXConnectionError(f"Unexpected response: {response.status_code}")

        except httpx.TimeoutException as e:
            log.error("Order status timeout", error=str(e))
            raise DEXTimeoutError(f"Order status request timed out: {e}") from e
        except httpx.HTTPError as e:
            log.error("Order status failed", error=str(e))
            raise DEXConnectionError(f"Order status request failed: {e}") from e

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol from Extended DEX.

        Returns the user's open position in the given symbol, or None if
        no position exists.

        Args:
            symbol: Trading pair (e.g., "ETH-PERP")

        Returns:
            Position with size, entry price, current price, P&L, or None

        Raises:
            DEXConnectionError: Not connected or network error
            DEXTimeoutError: Request timed out
        """
        if not self._connected or not self._http_client:
            raise DEXConnectionError("Not connected to Extended DEX")

        log = self._log.bind(symbol=symbol)
        log.debug("Getting position")

        try:
            response = await self._http_client.get("/user/positions")

            if response.status_code == 200:
                data = response.json()
                positions = data.get("positions", [])

                # Find position for requested symbol
                for pos in positions:
                    if pos["symbol"] == symbol:
                        return Position(
                            symbol=pos["symbol"],
                            size=Decimal(pos["size"]),
                            entry_price=Decimal(pos["entry_price"]),
                            current_price=Decimal(pos["mark_price"]),
                            unrealized_pnl=Decimal(pos["unrealized_pnl"]),
                        )

                # No position found for this symbol
                log.debug("No position found", symbol=symbol)
                return None

            response.raise_for_status()
            return None

        except httpx.TimeoutException as e:
            log.error("Position request timeout", error=str(e))
            raise DEXTimeoutError(f"Position request timed out: {e}") from e
        except httpx.HTTPError as e:
            log.error("Position request failed", error=str(e))
            raise DEXConnectionError(f"Position request failed: {e}") from e

    async def cancel_order(self, order_id: str) -> None:
        """Cancel an open order on Extended DEX.

        Cancels a pending order. Raises exception if order is already
        filled, cancelled, or doesn't exist.

        Args:
            order_id: Order ID to cancel

        Raises:
            DEXConnectionError: Not connected or network error
            DEXTimeoutError: Request timed out
            DEXOrderNotFoundError: Order not found or already filled/cancelled
        """
        if not self._connected or not self._http_client:
            raise DEXConnectionError("Not connected to Extended DEX")

        log = self._log.bind(order_id=order_id)
        log.info("Cancelling order")

        try:
            response = await self._http_client.delete(f"/user/orders/{order_id}")

            if response.status_code == 200:
                log.info("Order cancelled", order_id=order_id)
                return

            # Handle not found (404)
            if response.status_code == 404:
                default_msg = "Order not found or already filled"
                try:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "message", default_msg
                    )
                except json.JSONDecodeError:
                    error_msg = default_msg
                log.warning(
                    "Cannot cancel order",
                    order_id=order_id,
                    reason=error_msg,
                )
                raise DEXOrderNotFoundError(error_msg)

            response.raise_for_status()

        except httpx.TimeoutException as e:
            log.error("Cancel order timeout", error=str(e))
            raise DEXTimeoutError(f"Cancel order request timed out: {e}") from e
        except httpx.HTTPError as e:
            log.error("Cancel order failed", error=str(e))
            raise DEXConnectionError(f"Cancel order request failed: {e}") from e

    def subscribe_to_order_updates(
        self,
        callback: Callable[[OrderUpdate], Awaitable[None]],
    ):
        """Subscribe to real-time order updates via WebSocket.

        Returns no-op context manager for now. Full WebSocket subscription
        will be enhanced in a future story.

        Extended WebSocket provides Account Updates Stream for order
        confirmations, cancellations, rejections, and position changes.

        Args:
            callback: Async function called with OrderUpdate on status changes

        Returns:
            AsyncContextManager that maintains subscription during context
        """
        # Use base class no-op implementation for now
        # Will be overridden with real WebSocket subscription in future story
        return super().subscribe_to_order_updates(callback)
