"""Error log viewer API endpoint (Story 4.5).

Provides GET /api/errors endpoint for viewing error log entries.

AC#1: Default 50 entry retrieval
AC#2: Limit parameter (max 100)
AC#3: Hours parameter filtering
AC#4: Error log entry format
AC#7: Empty response handling
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import get_current_user, get_db_session
from kitkat.models import CurrentUser, ErrorLogResponse
from kitkat.services.error_log import ErrorLogService

router = APIRouter(prefix="/api", tags=["errors"])


@router.get("/errors", response_model=ErrorLogResponse)
async def get_errors(
    limit: int = Query(
        default=50,
        ge=1,
        description="Max entries to return (default 50, capped at 100)",
    ),
    hours: Optional[int] = Query(
        default=None,
        ge=1,
        description="Filter to last N hours",
    ),
    db: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ErrorLogResponse:
    """Get recent error log entries (Story 4.5: AC#1-3, AC#7).

    Returns error logs ordered by timestamp descending (most recent first).
    Default returns last 50 entries. Max 100 entries per request.
    Optional `hours` parameter filters to recent timeframe.

    Requires authentication via Bearer token.

    Args:
        limit: Maximum entries to return (1-100, default 50)
        hours: Optional filter for errors in last N hours (1-168)
        db: Database session (injected)
        current_user: Authenticated user context (injected)

    Returns:
        ErrorLogResponse: List of error entries with count
    """
    service = ErrorLogService(db)
    entries = await service.get_errors(limit=limit, hours=hours)
    return ErrorLogResponse(errors=entries, count=len(entries))
