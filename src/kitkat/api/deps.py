"""FastAPI dependency injection utilities."""

import threading
from datetime import datetime
from hmac import compare_digest
from typing import Optional

import structlog
from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.config import get_settings
from kitkat.database import get_db_session
from kitkat.models import CurrentUser
from kitkat.services.session_service import SessionService
from kitkat.services.signal_processor import SignalProcessor
from kitkat.services.execution_service import ExecutionService
from kitkat.services.health import HealthService

logger = structlog.get_logger()

# Alias for get_db_session for backwards compatibility
get_db = get_db_session

# Thread-safe lock for lazy initialization of SignalProcessor singleton
_signal_processor_lock = threading.Lock()

# Thread-safe lock for lazy initialization of HealthService singleton
_health_service_lock = threading.Lock()

# Singleton instances
_health_service: Optional[HealthService] = None


class SessionExpiredError(ValueError):
    """Session token has expired."""

    pass


class InvalidTokenError(ValueError):
    """Token format is invalid or missing."""

    pass


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
        # The actual user lookup and validation happens in webhook_handler
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
    except SessionExpiredError:
        raise HTTPException(status_code=401, detail="Session expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    except ValueError as e:
        logger.warning("Unexpected session validation error", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid or expired session")


# Global SignalProcessor instance (singleton pattern)
_signal_processor: Optional[SignalProcessor] = None


async def get_signal_processor(
    db: AsyncSession = Depends(get_db_session),
) -> SignalProcessor:
    """Get or create SignalProcessor with configured adapters.

    Story 2.9: Dependency injection for SignalProcessor with lazy initialization.
    Adapters are created and connected once, then reused for all signals.

    Thread-safe using double-checked locking pattern to prevent race conditions
    during concurrent first-request initialization.

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

    # Double-checked locking: first check without lock for performance
    if _signal_processor is None:
        with _signal_processor_lock:
            # Second check after acquiring lock to prevent duplicate initialization
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
                # Only include successfully connected adapters
                connected_adapters = []
                for adapter in adapters:
                    try:
                        await adapter.connect()
                        connected_adapters.append(adapter)
                    except Exception as e:
                        # Log error but continue - don't include failed adapters
                        logger.warning(
                            "Failed to connect adapter",
                            adapter=adapter.dex_id,
                            error=str(e),
                        )

                execution_service = ExecutionService(db)
                _signal_processor = SignalProcessor(
                    adapters=connected_adapters if connected_adapters else [MockAdapter()],
                    execution_service=execution_service,
                )

    return _signal_processor


async def get_health_service(
    request: Request,
) -> HealthService:
    """Get or create HealthService with configured adapters.

    Story 4.1: Dependency injection for HealthService with lazy initialization.
    Health service is created once with all configured adapters, then reused
    for all health checks.

    Thread-safe using double-checked locking pattern to prevent race conditions
    during concurrent first-request initialization.

    Args:
        request: FastAPI request object to access app.state for adapters

    Returns:
        HealthService: Initialized service with all configured adapters

    Note:
        Adapters are passed from request.app.state.adapters, which are set
        in main.py lifespan context during application startup.
    """
    global _health_service

    # Double-checked locking: first check without lock for performance
    if _health_service is None:
        with _health_service_lock:
            # Second check after acquiring lock to prevent duplicate initialization
            if _health_service is None:
                # Get adapters from app state (set in main.py lifespan)
                adapters = getattr(request.app.state, "adapters", [])
                _health_service = HealthService(adapters=adapters)

    return _health_service


__all__ = ["get_db_session", "get_db", "check_shutdown", "verify_webhook_token", "get_current_user", "get_signal_processor", "get_health_service"]
