"""FastAPI dependency injection utilities."""

from hmac import compare_digest

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.config import get_settings
from kitkat.database import get_db_session
from kitkat.models import CurrentUser
from kitkat.services.session_service import SessionService


async def verify_webhook_token(request: Request) -> str:
    """Verify webhook token from X-Webhook-Token header.

    Raises:
        HTTPException: 401 if token invalid or missing.
    """
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


__all__ = ["get_db_session", "verify_webhook_token", "get_current_user"]
