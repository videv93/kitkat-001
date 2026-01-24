"""DEX adapter custom exception hierarchy (Story 2.1).

All DEX operations should raise exceptions from this module to provide
clear semantics about whether errors are retryable or not.
"""


class DEXError(Exception):
    """Base exception for all DEX-related errors."""

    pass


class DEXTimeoutError(DEXError):
    """DEX API did not respond within timeout (retryable).

    Use case: Network timeout, slow response, temporary service delay.
    Action: Retry with exponential backoff.
    """

    pass


class DEXConnectionError(DEXError):
    """Connection to DEX failed or WebSocket error (retryable).

    Use cases:
    - Network connection refused
    - WebSocket connection dropped
    - TLS/SSL handshake failure
    - DNS resolution failure

    Action: Retry with exponential backoff.
    """

    pass


class DEXRejectionError(DEXError):
    """DEX rejected the order or operation (non-retryable).

    Base class for business errors where DEX explicitly rejected the request.
    Subclasses provide more specific rejection types.

    Use case: Invalid order, validation failure, business rule violation.
    Action: Fail immediately, do not retry.
    """

    pass


class DEXInsufficientFundsError(DEXRejectionError):
    """Order rejected due to insufficient balance (non-retryable).

    Use case: User doesn't have enough collateral/balance to place order.
    Action: Fail immediately, user must deposit more funds.
    """

    pass


class DEXNonceError(DEXRejectionError):
    """Invalid or stale nonce (non-retryable, DEX-specific).

    Use case: Nonce validation failed on Starknet-based DEX (Extended).
    Nonce must be between 1 and 2^31, and must be unique per order.

    Action: Fail immediately, next order will use fresh nonce.
    """

    pass


class DEXSignatureError(DEXConnectionError):
    """Signature verification failed (retryable).

    Use cases:
    - SNIP12 signature invalid
    - Stark signature verification failure
    - Signature parameter mismatch

    Note: Extends DEXConnectionError to mark as retryable
    (could be temporary state issue).
    """

    pass


class DEXOrderNotFoundError(DEXRejectionError):
    """Order ID not found on DEX (non-retryable).

    Use case: Attempting to cancel/query order that doesn't exist or already filled.
    Action: Fail immediately, order may have already executed.
    """

    pass
