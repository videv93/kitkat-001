"""DEX adapter implementations.

This package defines the abstract DEXAdapter interface and all DEX-specific
implementations (Extended, Mock, etc.). It also exports all exception types
and type definitions needed for adapter development.

Story 2.1: DEX Adapter Interface - defines the contract all adapters must follow.
"""

from kitkat.adapters.base import DEXAdapter
from kitkat.adapters.extended import ExtendedAdapter
from kitkat.adapters.mock import MockAdapter
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
    ConnectParams,
    OrderSubmissionResult,
    OrderStatus,
    HealthStatus,
    Position,
    OrderUpdate,
)

__all__ = [
    # Base class
    "DEXAdapter",
    # Implementations
    "ExtendedAdapter",
    "MockAdapter",
    # Exceptions (all inherit from DEXError)
    "DEXError",
    "DEXTimeoutError",
    "DEXConnectionError",
    "DEXRejectionError",
    "DEXInsufficientFundsError",
    "DEXNonceError",
    "DEXSignatureError",
    "DEXOrderNotFoundError",
    # Type definitions
    "ConnectParams",
    "OrderSubmissionResult",
    "OrderStatus",
    "HealthStatus",
    "Position",
    "OrderUpdate",
]
