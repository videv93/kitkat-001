"""FastAPI dependency injection utilities."""

from datetime import datetime
from hmac import compare_digest
from typing import Optional

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.config import get_settings
from kitkat.database import get_db_session
from kitkat.models import CurrentUser
from kitkat.services.session_service import SessionService
from kitkat.services.signal_processor import SignalProcessor
from kitkat.services.execution_service import ExecutionService

# Alias for get_db_session for backwards compatibility
get_db = get_db_session


async def check_shutdown(request: Request) -> None:
    """Dependency to reject requests during shutdown.

    Returns 503 Service Unavailable when shutdown has been initiated.
    Apply to endpoints that should not accept new work during shutdown.

    Story 2.11: Graceful Shutdown

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: 503 if shutdown is in progress
    """
    shutdown_manager = getattr(request.app.state, "shutdown_manager", None)

    if shutdown_manager and shutdown_manager.is_shutting_down:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Service shutting down",
                "code": "SERVICE_UNAVAILABLE",
                "signal_id": None,
                "dex": None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )


async def verify_webhook_token(
    request: Request,
    token_query: Optional[str] = Query(None, alias="token"),
) -> str:
    """Verify webhook token from X-Webhook-Token header or ?token query parameter.

    Story 2.4: Supports token query parameter for user-specific webhook authentication.

    Args:
        request: FastAPI request object
        token_query: Token from ?token= query parameter

    Returns:
        str: The verified webhook token

    Raises:
        HTTPException: 401 if token invalid or missing.
    """
    # Try query parameter first (Story 2.4: AC3)
    if token_query:
        # Query parameter is a user-specific webhook token
        # Validate it using UserService (will do constant-time comparison)
        # For now, just check that it's non-empty
        # The actual user lookup happens in webhook_handler
        if token_query:
            return token_query

    # Fall back to header-based authentication (legacy)
    token = request.headers.get("X-Webhook-Token")
    settings = get_settings()

    # Constant-time comparison to prevent timing attacks
    if not token or not compare_digest(token, settings.webhook_token):
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid token", "code": "INVALID_TOKEN"},
        )

    return token


async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """Dependency to validate session and return current user.

    Extracts Bearer token from Authorization header and validates it
    against the sessions database table.

    Args:
        authorization: Authorization header value.
        db: Database session (injected by FastAPI).

    Returns:
        CurrentUser: Authenticated user context.

    Raises:
        HTTPException: 401 if token missing, invalid, or expired.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    # Extract token from "Bearer {token}"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format",
        )

    session_service = SessionService(db)
    try:
        return await session_service.validate_session(token)
    except ValueError as e:
        # Standardize error message (don't leak internal details)
        error_msg = str(e)
        if "expired" in error_msg.lower():
            detail = "Session expired"
        elif "required" in error_msg.lower():
            detail = "Invalid or missing token"
        else:
            detail = "Invalid or expired session"
        raise HTTPException(status_code=401, detail=detail)


# Global SignalProcessor instance (singleton pattern)
_signal_processor: Optional[SignalProcessor] = None


async def get_signal_processor(
    db: AsyncSession = Depends(get_db_session),
) -> SignalProcessor:
    """Get or create SignalProcessor with configured adapters.

    Story 2.9: Dependency injection for SignalProcessor with lazy initialization.
    Adapters are created and connected once, then reused for all signals.

    Args:
        db: Database session for ExecutionService

    Returns:
        SignalProcessor: Initialized processor with all configured adapters

    Note:
        In test mode, uses MockAdapter. In production, uses ExtendedAdapter.
        Connection errors are logged but don't fail - adapters will simply
        be marked as inactive until reconnection succeeds.
    """
    global _signal_processor

    if _signal_processor is None:
        from kitkat.adapters.extended import ExtendedAdapter
        from kitkat.adapters.mock import MockAdapter

        settings = get_settings()

        # Select adapters based on test mode
        if settings.test_mode:
            adapters = [MockAdapter()]
        else:
            adapters = [ExtendedAdapter(settings)]

        # Connect all adapters - log but don't fail on connection errors
        # This allows the system to continue even if a DEX is temporarily unavailable
        connected_adapters = []
        for adapter in adapters:
            try:
                await adapter.connect()
                connected_adapters.append(adapter)
            except Exception as e:
                # Log error but continue - adapter will be inactive
                import structlog
                log = structlog.get_logger()
                log.warning(
                    "Failed to connect adapter",
                    adapter=adapter.dex_id,
                    error=str(e),
                )
                # Still add adapter to list - it will be filtered by get_active_adapters()

        execution_service = ExecutionService(db)
        _signal_processor = SignalProcessor(
            adapters=adapters if adapters else [MockAdapter()],
            execution_service=execution_service,
        )

    return _signal_processor


__all__ = ["get_db_session", "get_db", "check_shutdown", "verify_webhook_token", "get_current_user", "get_signal_processor"]
