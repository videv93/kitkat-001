"""Abstract base class for DEX adapters (Story 2.1).

This module defines the DEXAdapter interface that all DEX implementations
must follow. It enables swappable DEX implementations and parallel fan-out
execution to multiple DEXs.
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, AsyncContextManager, Optional, Literal
from decimal import Decimal

from kitkat.models import (
    ConnectParams,
    OrderSubmissionResult,
    OrderStatus,
    HealthStatus,
    Position,
    OrderUpdate,
)
from kitkat.adapters.exceptions import (
    DEXConnectionError,
    DEXTimeoutError,
    DEXRejectionError,
    DEXInsufficientFundsError,
    DEXNonceError,
    DEXSignatureError,
    DEXOrderNotFoundError,
)


class DEXAdapter(ABC):
    """Abstract base class for all DEX adapter implementations.

    This interface separates order submission from order tracking:
    - execute_order() submits and returns immediately with order_id
    - get_order_status() or subscribe_to_order_updates() track actual fills

    All DEX implementations (Extended, Mock, Paradex, etc.) must inherit
    from this class and implement all 8 abstract methods.

    Typical usage:
        adapter = ExtendedAdapter()
        await adapter.connect(params)

        # Submit order (async, returns immediately)
        result = await adapter.execute_order("ETH/USD", "buy", Decimal("1.0"))

        # Track via polling
        status = await adapter.get_order_status(result.order_id)

        # OR track via WebSocket
        async with adapter.subscribe_to_order_updates(callback):
            await asyncio.sleep(60)  # Listen for updates

        await adapter.disconnect()
    """

    @property
    @abstractmethod
    def dex_id(self) -> str:
        """Unique identifier for this DEX.

        Returns:
            str: DEX identifier (e.g., "extended", "mock", "paradex")
        """

    @abstractmethod
    async def connect(self, params: Optional[ConnectParams] = None) -> None:
        """Establish connection to DEX with optional parameters.

        Args:
            params: DEX-specific connection parameters. Adapters define
                   their own ConnectParams subclass. Can be None if
                   credentials were provided at init time.

        Raises:
            DEXConnectionError: If connection fails (network, auth, etc)
            DEXSignatureError: If signature verification fails
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean disconnect from DEX.

        Idempotent - safe to call multiple times. Closes HTTP client,
        WebSocket connections, and cleans up resources.
        """

    @abstractmethod
    async def execute_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        size: Decimal,
    ) -> OrderSubmissionResult:
        """Submit an order (async - does not wait for fill).

        Returns immediately with order_id for tracking. Use get_order_status()
        or subscribe_to_order_updates() to track actual execution.

        Args:
            symbol: Trading pair (e.g., "ETH/USD", "BTC-PERP")
            side: "buy" (long) or "sell" (short)
            size: Amount to trade (must be positive)

        Returns:
            OrderSubmissionResult with order_id and immediate fill info if available

        Raises:
            DEXRejectionError: Order rejected (invalid symbol, insufficient balance)
            DEXInsufficientFundsError: Not enough balance (specific rejection type)
            DEXNonceError: Invalid nonce (Extended-specific)
            DEXConnectionError: Network/connection error (retryable)
            DEXTimeoutError: DEX didn't respond in time (retryable)
        """

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get current status of a submitted order.

        Polling approach to track order execution. Alternative to
        subscribe_to_order_updates() for non-real-time tracking.

        Args:
            order_id: Order ID returned by execute_order()

        Returns:
            OrderStatus with current fill information

        Raises:
            DEXOrderNotFoundError: Order ID not found on DEX
            DEXConnectionError: Network/connection error (retryable)
            DEXTimeoutError: DEX didn't respond in time (retryable)
        """

    def subscribe_to_order_updates(
        self,
        callback: Callable[[OrderUpdate], Awaitable[None]],
    ) -> AsyncContextManager:
        """Subscribe to real-time order updates (optional, can be overridden).

        Default implementation: returns no-op context manager. Callbacks are
        silently ignored - no updates are delivered. Intended for adapters
        that don't support real-time updates (e.g., Mock adapter for testing).

        Subclasses (Extended adapter) override this to provide WebSocket
        subscription for real-time order updates from the DEX.

        Real-time approach to track order execution as updates arrive.
        Alternative to get_order_status() for polling.

        Usage:
            async def on_update(update: OrderUpdate):
                logger.info(f"Order {update.order_id} status: {update.status}")

            async with adapter.subscribe_to_order_updates(on_update):
                # Callback invoked as order status changes (if adapter overrides)
                await asyncio.sleep(60)

        Args:
            callback: Async function called with OrderUpdate whenever status changes.
                     In default implementation, this callback is never invoked.

        Returns:
            AsyncContextManager that maintains subscription during context.
            Default returns no-op context manager.
        """
        @asynccontextmanager
        async def noop():
            yield

        return noop()

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for a symbol.

        Returns the user's open position (long/short) in the given symbol.
        Returns None if no position exists.

        Args:
            symbol: Trading pair

        Returns:
            Position object with size, entry price, current price, P&L,
            or None if no position

        Raises:
            DEXConnectionError: Network/connection error (retryable)
            DEXTimeoutError: DEX didn't respond in time (retryable)
        """

    @abstractmethod
    async def cancel_order(self, order_id: str) -> None:
        """Cancel an open order.

        Cancels a pending order. Raises exception if order is already
        filled, cancelled, or doesn't exist.

        Args:
            order_id: Order ID to cancel

        Raises:
            DEXOrderNotFoundError: Order not found (already filled/cancelled/doesn't exist)
            DEXConnectionError: Network/connection error (retryable)
            DEXTimeoutError: DEX didn't respond in time (retryable)
        """

    @abstractmethod
    async def get_health_status(self) -> HealthStatus:
        """Get DEX connection and health status.

        Returns current connection status, latency, and health information.
        Used for monitoring DEX availability and performance.

        Returns:
            HealthStatus with connection info and latency

        Raises:
            DEXConnectionError: Cannot reach DEX to check health
        """
