"""FastAPI dependency injection utilities."""

from hmac import compare_digest

from fastapi import HTTPException, Request

from kitkat.config import get_settings
from kitkat.database import get_db_session


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


__all__ = ["get_db_session", "verify_webhook_token"]
