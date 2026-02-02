"""Error log retrieval service (Story 4.5).

Provides error log retrieval and cleanup functionality for the error log viewer.
Works with ErrorLogModel database records created by ErrorLogger.

AC#1: Default 50 entry retrieval
AC#2: Limit parameter (max 100)
AC#3: Hours parameter filtering
AC#4: Error log entry format
AC#6: 90 day retention cleanup
AC#7: Empty response handling
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.database import ErrorLogModel
from kitkat.models import ErrorLogEntry

logger = structlog.get_logger()

# Constants for error log configuration
DEFAULT_LIMIT = 50
MAX_LIMIT = 100
RETENTION_DAYS = 90


class ErrorLogService:
    """Service for retrieving and managing error logs (Story 4.5).

    Provides methods to:
    - Retrieve errors with pagination and filtering
    - Persist new errors to database
    - Clean up old errors based on retention policy
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            db: AsyncSession for database operations
        """
        self._db = db
        self._log = logger.bind(service="error_log")

    async def get_errors(
        self,
        limit: int = DEFAULT_LIMIT,
        hours: Optional[int] = None,
    ) -> list[ErrorLogEntry]:
        """Get recent error log entries (AC#1, AC#2, AC#3).

        Args:
            limit: Maximum entries to return (default 50, max 100)
            hours: Optional filter for errors in last N hours

        Returns:
            List of ErrorLogEntry models sorted by timestamp descending
        """
        # Enforce max limit (AC#2)
        effective_limit = min(limit, MAX_LIMIT)

        # Build query
        query = select(ErrorLogModel).order_by(ErrorLogModel.created_at.desc())

        # Apply hours filter if provided (AC#3)
        if hours is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            query = query.where(ErrorLogModel.created_at >= cutoff)

        # Apply limit
        query = query.limit(effective_limit)

        result = await self._db.execute(query)
        records = result.scalars().all()

        # Convert to ErrorLogEntry models (AC#4)
        return [self._to_entry(record) for record in records]

    async def persist_error(
        self,
        level: str,
        error_type: str,
        message: str,
        context: dict,
    ) -> None:
        """Persist error to database (AC#5).

        Args:
            level: Log level ("error" or "warning")
            error_type: Categorized error code
            message: Human-readable error description
            context: Additional context dictionary
        """
        record = ErrorLogModel(
            level=level,
            error_type=error_type,
            message=message,
            context_data=json.dumps(context),
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(record)
        await self._db.commit()

    async def cleanup_old_errors(self) -> int:
        """Delete errors older than retention period (AC#6).

        Returns:
            Number of deleted records
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

        # Delete old records
        stmt = delete(ErrorLogModel).where(ErrorLogModel.created_at < cutoff)
        result = await self._db.execute(stmt)
        await self._db.commit()

        deleted_count = result.rowcount
        if deleted_count > 0:
            self._log.info(
                "Cleaned up old error logs",
                deleted_count=deleted_count,
                retention_days=RETENTION_DAYS,
            )

        return deleted_count

    async def get_recent_error_count(self, hours: int = 1) -> int:
        """Get count of errors in last N hours (for dashboard).

        Args:
            hours: Time window in hours (default 1)

        Returns:
            Count of errors in the time window
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = select(func.count()).select_from(ErrorLogModel).where(
            ErrorLogModel.created_at >= cutoff
        )
        result = await self._db.execute(query)
        return result.scalar() or 0

    def _to_entry(self, record: ErrorLogModel) -> ErrorLogEntry:
        """Convert database record to API response model (AC#4).

        Args:
            record: ErrorLogModel from database

        Returns:
            ErrorLogEntry formatted for API response
        """
        # Parse context_data JSON
        try:
            context = json.loads(record.context_data) if record.context_data else {}
        except (json.JSONDecodeError, TypeError):
            context = {}

        return ErrorLogEntry(
            id=f"err-{record.id}",
            timestamp=record.created_at,
            level=record.level,
            error_type=record.error_type,
            message=record.message,
            context=context,
        )
