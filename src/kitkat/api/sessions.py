"""Session management API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.database import get_db_session
from kitkat.models import Session, SessionCreate
from kitkat.services.session_service import SessionService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Session)
async def create_session(
    session_create: SessionCreate,
    db: AsyncSession = Depends(get_db_session),
) -> Session:
    """Create a new session for a user.

    Args:
        session_create: Session creation request.
        db: Database session.

    Returns:
        Session: Created session model.

    Raises:
        HTTPException: 404 if wallet_address not found.
    """
    service = SessionService(db)
    try:
        session = await service.create_session(session_create.wallet_address)
        return session
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
