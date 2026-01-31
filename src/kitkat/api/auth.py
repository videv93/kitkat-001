"""Authentication API endpoints (Story 2.3).

Provides user status and session management endpoints.
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import get_current_user
from kitkat.database import get_db_session
from kitkat.models import CurrentUser
from kitkat.services.user_service import UserService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserStatusResponse(BaseModel):
    """Response model for user status endpoint (Story 2.3 AC5)."""

    wallet_address: str = Field(..., description="Wallet address (abbreviated format)")
    status: str = Field(default="Connected", description="Connection status")


@router.get("/user/status", response_model=UserStatusResponse)
async def get_user_status(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserStatusResponse:
    """Get authenticated user's wallet connection status.

    AC5: When authenticated user queries their status:
    - Wallet address shown (abbreviated: `0x1234...5678`)
    - Connection status shows "Connected"

    Args:
        current_user: Authenticated user context (from session token).
        db: Database session (injected).

    Returns:
        Dictionary with wallet_address (abbreviated), full_address, and status.

    Raises:
        HTTPException: 401 if user session is invalid.
        HTTPException: 404 if user not found (shouldn't happen if auth is valid).
    """
    log = logger.bind(wallet_address=current_user.wallet_address[:10] + "...")

    # Get full user details
    user_service = UserService(db)
    user = await user_service.get_user(current_user.wallet_address)

    if not user:
        log.error("User not found despite valid session")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "User not found",
                "code": "USER_NOT_FOUND",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

    # Abbreviate address: 0x1234...5678 (AC5: Show abbreviated format only)
    abbreviated = f"{current_user.wallet_address[:6]}...{current_user.wallet_address[-4:]}"

    log.info("User status retrieved")

    return UserStatusResponse(
        wallet_address=abbreviated,
        status="Connected",
    )
