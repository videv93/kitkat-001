"""User management API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.database import get_db_session
from kitkat.models import User, UserCreate
from kitkat.services.user_service import UserService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=User)
async def create_user(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Create a new user with webhook token and default configuration.

    Args:
        user_create: User creation request.
        db: Database session.

    Returns:
        User: Created user model.

    Raises:
        HTTPException: 409 if wallet_address already exists.
    """
    service = UserService(db)
    try:
        user = await service.create_user(user_create.wallet_address)
        return user
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Wallet address already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
