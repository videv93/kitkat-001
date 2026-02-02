"""Tests for ErrorLogService (Story 4.5: AC#1-7).

Tests cover:
- Error retrieval with default limit (50) - AC#1
- Custom limit parameter (max 100) - AC#2
- Hours parameter filtering - AC#3
- Error log entry format - AC#4
- Database persistence - AC#5
- Retention cleanup (90 days) - AC#6
- Empty response - AC#7
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.database import ErrorLogModel
from kitkat.models import ErrorLogEntry


class TestErrorLogServiceGetErrors:
    """Tests for get_errors() method."""

    @pytest.mark.asyncio
    async def test_get_errors_default_limit(self, db_session: AsyncSession):
        """Should return last 50 errors by default (AC#1)."""
        from kitkat.services.error_log import ErrorLogService

        # Create 60 error records
        for i in range(60):
            error = ErrorLogModel(
                level="error",
                error_type="TEST_ERROR",
                message=f"Test error {i}",
                context_data=json.dumps({"index": i}),
                created_at=datetime.now(timezone.utc) - timedelta(minutes=60 - i),
            )
            db_session.add(error)
        await db_session.commit()

        service = ErrorLogService(db_session)
        errors = await service.get_errors()

        # Should return 50 (default limit)
        assert len(errors) == 50

    @pytest.mark.asyncio
    async def test_get_errors_custom_limit(self, db_session: AsyncSession):
        """Should return up to N entries with limit parameter (AC#2)."""
        from kitkat.services.error_log import ErrorLogService

        # Create 20 error records
        for i in range(20):
            error = ErrorLogModel(
                level="error",
                error_type="TEST_ERROR",
                message=f"Test error {i}",
                context_data=json.dumps({}),
                created_at=datetime.now(timezone.utc),
            )
            db_session.add(error)
        await db_session.commit()

        service = ErrorLogService(db_session)
        errors = await service.get_errors(limit=10)

        assert len(errors) == 10

    @pytest.mark.asyncio
    async def test_get_errors_max_limit_enforced(self, db_session: AsyncSession):
        """Should enforce max limit of 100 entries (AC#2)."""
        from kitkat.services.error_log import ErrorLogService

        # Create 150 error records
        for i in range(150):
            error = ErrorLogModel(
                level="error",
                error_type="TEST_ERROR",
                message=f"Test error {i}",
                context_data=json.dumps({}),
                created_at=datetime.now(timezone.utc),
            )
            db_session.add(error)
        await db_session.commit()

        service = ErrorLogService(db_session)
        # Request 150, should get max 100
        errors = await service.get_errors(limit=150)

        assert len(errors) == 100

    @pytest.mark.asyncio
    async def test_get_errors_hours_filter(self, db_session: AsyncSession):
        """Should filter errors by hours parameter (AC#3)."""
        from kitkat.services.error_log import ErrorLogService

        now = datetime.now(timezone.utc)

        # Create old errors (25 hours ago)
        for i in range(5):
            error = ErrorLogModel(
                level="error",
                error_type="OLD_ERROR",
                message=f"Old error {i}",
                context_data=json.dumps({}),
                created_at=now - timedelta(hours=25),
            )
            db_session.add(error)

        # Create recent errors (1 hour ago)
        for i in range(3):
            error = ErrorLogModel(
                level="error",
                error_type="RECENT_ERROR",
                message=f"Recent error {i}",
                context_data=json.dumps({}),
                created_at=now - timedelta(hours=1),
            )
            db_session.add(error)

        await db_session.commit()

        service = ErrorLogService(db_session)
        errors = await service.get_errors(hours=24)

        # Should only return the 3 recent errors
        assert len(errors) == 3
        for error in errors:
            assert error.error_type == "RECENT_ERROR"

    @pytest.mark.asyncio
    async def test_get_errors_combined_limit_and_hours(self, db_session: AsyncSession):
        """Should apply both limit and hours filters (AC#2, AC#3)."""
        from kitkat.services.error_log import ErrorLogService

        now = datetime.now(timezone.utc)

        # Create 10 recent errors
        for i in range(10):
            error = ErrorLogModel(
                level="error",
                error_type="TEST_ERROR",
                message=f"Error {i}",
                context_data=json.dumps({}),
                created_at=now - timedelta(hours=i),
            )
            db_session.add(error)
        await db_session.commit()

        service = ErrorLogService(db_session)
        # Limit to 5, within 6 hours
        errors = await service.get_errors(limit=5, hours=6)

        # Should return 5 (limited) even though 6 are within timeframe
        assert len(errors) == 5

    @pytest.mark.asyncio
    async def test_get_errors_empty_result(self, db_session: AsyncSession):
        """Should return empty list when no errors exist (AC#7)."""
        from kitkat.services.error_log import ErrorLogService

        service = ErrorLogService(db_session)
        errors = await service.get_errors()

        assert errors == []

    @pytest.mark.asyncio
    async def test_get_errors_sorted_descending(self, db_session: AsyncSession):
        """Should return errors sorted by timestamp descending (most recent first)."""
        from kitkat.services.error_log import ErrorLogService

        now = datetime.now(timezone.utc)

        # Create errors with different timestamps
        for i in range(5):
            error = ErrorLogModel(
                level="error",
                error_type="TEST_ERROR",
                message=f"Error {i}",
                context_data=json.dumps({"index": i}),
                created_at=now - timedelta(minutes=i * 10),
            )
            db_session.add(error)
        await db_session.commit()

        service = ErrorLogService(db_session)
        errors = await service.get_errors()

        # Most recent should be first
        timestamps = [e.timestamp for e in errors]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_get_errors_entry_format(self, db_session: AsyncSession):
        """Should return errors in correct format (AC#4)."""
        from kitkat.services.error_log import ErrorLogService

        error = ErrorLogModel(
            level="error",
            error_type="DEX_TIMEOUT",
            message="Extended DEX timeout after 10s",
            context_data=json.dumps({
                "signal_id": "abc123",
                "dex_id": "extended",
                "latency_ms": 10000,
            }),
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(error)
        await db_session.commit()

        service = ErrorLogService(db_session)
        errors = await service.get_errors()

        assert len(errors) == 1
        entry = errors[0]

        # Check format per AC#4
        assert entry.id.startswith("err-")
        assert entry.level == "error"
        assert entry.error_type == "DEX_TIMEOUT"
        assert entry.message == "Extended DEX timeout after 10s"
        assert entry.context["signal_id"] == "abc123"
        assert entry.context["dex_id"] == "extended"
        assert entry.context["latency_ms"] == 10000
        assert isinstance(entry.timestamp, datetime)


class TestErrorLogServicePersist:
    """Tests for persist_error() method (AC#5)."""

    @pytest.mark.asyncio
    async def test_persist_error_creates_record(self, db_session: AsyncSession):
        """Should create database record when persisting error."""
        from kitkat.services.error_log import ErrorLogService

        service = ErrorLogService(db_session)
        await service.persist_error(
            level="error",
            error_type="TEST_ERROR",
            message="Test error message",
            context={"key": "value"},
        )

        # Verify record exists in database
        result = await db_session.execute(select(ErrorLogModel))
        records = result.scalars().all()

        assert len(records) == 1
        assert records[0].level == "error"
        assert records[0].error_type == "TEST_ERROR"
        assert records[0].message == "Test error message"
        assert json.loads(records[0].context_data) == {"key": "value"}

    @pytest.mark.asyncio
    async def test_persist_error_warning_level(self, db_session: AsyncSession):
        """Should persist warning level errors."""
        from kitkat.services.error_log import ErrorLogService

        service = ErrorLogService(db_session)
        await service.persist_error(
            level="warning",
            error_type="RATE_LIMITED",
            message="Rate limit exceeded",
            context={},
        )

        result = await db_session.execute(select(ErrorLogModel))
        record = result.scalar_one()

        assert record.level == "warning"

    @pytest.mark.asyncio
    async def test_persist_error_timestamp_set(self, db_session: AsyncSession):
        """Should set created_at timestamp automatically."""
        from kitkat.services.error_log import ErrorLogService

        service = ErrorLogService(db_session)
        before = datetime.now(timezone.utc)

        await service.persist_error(
            level="error",
            error_type="TEST_ERROR",
            message="Test",
            context={},
        )

        after = datetime.now(timezone.utc)

        result = await db_session.execute(select(ErrorLogModel))
        record = result.scalar_one()

        assert before <= record.created_at <= after


class TestErrorLogServiceCleanup:
    """Tests for cleanup_old_errors() method (AC#6)."""

    @pytest.mark.asyncio
    async def test_cleanup_deletes_old_errors(self, db_session: AsyncSession):
        """Should delete errors older than 90 days (AC#6)."""
        from kitkat.services.error_log import ErrorLogService

        now = datetime.now(timezone.utc)

        # Create old error (91 days)
        old_error = ErrorLogModel(
            level="error",
            error_type="OLD_ERROR",
            message="Old error",
            context_data=json.dumps({}),
            created_at=now - timedelta(days=91),
        )
        db_session.add(old_error)

        # Create recent error (89 days)
        recent_error = ErrorLogModel(
            level="error",
            error_type="RECENT_ERROR",
            message="Recent error",
            context_data=json.dumps({}),
            created_at=now - timedelta(days=89),
        )
        db_session.add(recent_error)

        await db_session.commit()

        service = ErrorLogService(db_session)
        deleted_count = await service.cleanup_old_errors()

        # Should delete 1 old error
        assert deleted_count == 1

        # Verify only recent error remains
        result = await db_session.execute(select(ErrorLogModel))
        records = result.scalars().all()
        assert len(records) == 1
        assert records[0].error_type == "RECENT_ERROR"

    @pytest.mark.asyncio
    async def test_cleanup_preserves_recent_errors(self, db_session: AsyncSession):
        """Should preserve errors within 90 days (AC#6)."""
        from kitkat.services.error_log import ErrorLogService

        now = datetime.now(timezone.utc)

        # Create errors at various ages within 90 days
        for i in range(5):
            error = ErrorLogModel(
                level="error",
                error_type="TEST_ERROR",
                message=f"Error {i}",
                context_data=json.dumps({}),
                created_at=now - timedelta(days=i * 10),
            )
            db_session.add(error)
        await db_session.commit()

        service = ErrorLogService(db_session)
        deleted_count = await service.cleanup_old_errors()

        # Should delete nothing
        assert deleted_count == 0

        # All records should remain
        result = await db_session.execute(select(ErrorLogModel))
        records = result.scalars().all()
        assert len(records) == 5

    @pytest.mark.asyncio
    async def test_cleanup_returns_deleted_count(self, db_session: AsyncSession):
        """Should return count of deleted errors."""
        from kitkat.services.error_log import ErrorLogService

        now = datetime.now(timezone.utc)

        # Create 3 old errors
        for i in range(3):
            error = ErrorLogModel(
                level="error",
                error_type="OLD_ERROR",
                message=f"Old {i}",
                context_data=json.dumps({}),
                created_at=now - timedelta(days=100),
            )
            db_session.add(error)
        await db_session.commit()

        service = ErrorLogService(db_session)
        deleted_count = await service.cleanup_old_errors()

        assert deleted_count == 3

    @pytest.mark.asyncio
    async def test_cleanup_exact_boundary(self, db_session: AsyncSession):
        """Should handle 90 day boundary correctly."""
        from kitkat.services.error_log import ErrorLogService

        now = datetime.now(timezone.utc)

        # Error at 89 days should be preserved (within retention)
        recent_error = ErrorLogModel(
            level="error",
            error_type="RECENT_ERROR",
            message="Within boundary",
            context_data=json.dumps({}),
            created_at=now - timedelta(days=89),
        )
        db_session.add(recent_error)

        # Error at 91 days should be deleted (past retention)
        old_error = ErrorLogModel(
            level="error",
            error_type="OLD_ERROR",
            message="Past boundary",
            context_data=json.dumps({}),
            created_at=now - timedelta(days=91),
        )
        db_session.add(old_error)

        await db_session.commit()

        service = ErrorLogService(db_session)
        deleted_count = await service.cleanup_old_errors()

        # Should delete only the one past the boundary
        assert deleted_count == 1

        result = await db_session.execute(select(ErrorLogModel))
        records = result.scalars().all()
        assert len(records) == 1
        assert records[0].error_type == "RECENT_ERROR"


class TestErrorLogServiceGetRecentCount:
    """Tests for get_recent_error_count() method (for dashboard)."""

    @pytest.mark.asyncio
    async def test_get_recent_error_count(self, db_session: AsyncSession):
        """Should return count of errors in last N hours."""
        from kitkat.services.error_log import ErrorLogService

        now = datetime.now(timezone.utc)

        # Create 3 errors in last hour
        for i in range(3):
            error = ErrorLogModel(
                level="error",
                error_type="RECENT",
                message=f"Recent {i}",
                context_data=json.dumps({}),
                created_at=now - timedelta(minutes=30),
            )
            db_session.add(error)

        # Create 2 errors 2 hours ago
        for i in range(2):
            error = ErrorLogModel(
                level="error",
                error_type="OLD",
                message=f"Old {i}",
                context_data=json.dumps({}),
                created_at=now - timedelta(hours=2),
            )
            db_session.add(error)

        await db_session.commit()

        service = ErrorLogService(db_session)
        count = await service.get_recent_error_count(hours=1)

        assert count == 3

    @pytest.mark.asyncio
    async def test_get_recent_error_count_empty(self, db_session: AsyncSession):
        """Should return 0 when no recent errors."""
        from kitkat.services.error_log import ErrorLogService

        service = ErrorLogService(db_session)
        count = await service.get_recent_error_count(hours=1)

        assert count == 0
