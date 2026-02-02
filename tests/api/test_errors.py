"""Tests for GET /api/errors endpoint (Story 4.5: AC#1-7).

Tests cover:
- Default 50 entry limit (AC#1)
- Custom limit parameter (AC#2)
- Hours parameter filtering (AC#3)
- Error log entry format (AC#4)
- Empty response format (AC#7)
- Authentication requirement
- Validation errors
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.database import ErrorLogModel


class TestGetErrorsAuthentication:
    """Tests for authentication requirement."""

    def test_requires_authentication(self, client: TestClient):
        """Should return 401 without authentication."""
        response = client.get("/api/errors")
        assert response.status_code == 401

    def test_requires_valid_token(self, client: TestClient):
        """Should return 401 with invalid token."""
        response = client.get(
            "/api/errors",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401


class TestGetErrorsBasic:
    """Tests for basic error retrieval."""

    @pytest.mark.asyncio
    async def test_returns_errors_default_limit(
        self,
        client: TestClient,
        test_user_session_headers: dict,
        db_session: AsyncSession,
    ):
        """Should return last 50 errors by default (AC#1)."""
        # Create 60 errors
        for i in range(60):
            error = ErrorLogModel(
                level="error",
                error_type="TEST_ERROR",
                message=f"Error {i}",
                context_data=json.dumps({}),
                created_at=datetime.now(timezone.utc) - timedelta(minutes=i),
            )
            db_session.add(error)
        await db_session.commit()

        response = client.get("/api/errors", headers=test_user_session_headers)

        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert "count" in data
        assert data["count"] == 50
        assert len(data["errors"]) == 50

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_errors(
        self,
        client: TestClient,
        test_user_session_headers: dict,
    ):
        """Should return empty array when no errors exist (AC#7)."""
        response = client.get("/api/errors", headers=test_user_session_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["errors"] == []
        assert data["count"] == 0


class TestGetErrorsLimitParameter:
    """Tests for limit parameter (AC#2)."""

    @pytest.mark.asyncio
    async def test_custom_limit(
        self,
        client: TestClient,
        test_user_session_headers: dict,
        db_session: AsyncSession,
    ):
        """Should return up to N entries with limit parameter."""
        # Create 20 errors
        for i in range(20):
            error = ErrorLogModel(
                level="error",
                error_type="TEST_ERROR",
                message=f"Error {i}",
                context_data=json.dumps({}),
                created_at=datetime.now(timezone.utc),
            )
            db_session.add(error)
        await db_session.commit()

        response = client.get(
            "/api/errors?limit=10",
            headers=test_user_session_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 10

    @pytest.mark.asyncio
    async def test_max_limit_enforced(
        self,
        client: TestClient,
        test_user_session_headers: dict,
        db_session: AsyncSession,
    ):
        """Should enforce max limit of 100."""
        # Create 150 errors
        for i in range(150):
            error = ErrorLogModel(
                level="error",
                error_type="TEST_ERROR",
                message=f"Error {i}",
                context_data=json.dumps({}),
                created_at=datetime.now(timezone.utc),
            )
            db_session.add(error)
        await db_session.commit()

        response = client.get(
            "/api/errors?limit=150",
            headers=test_user_session_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 100

    @pytest.mark.asyncio
    async def test_limit_validation_min(
        self,
        client: TestClient,
        test_user_session_headers: dict,
    ):
        """Should reject limit < 1."""
        response = client.get(
            "/api/errors?limit=0",
            headers=test_user_session_headers,
        )

        # App uses custom validation handler that returns 400
        assert response.status_code == 400


class TestGetErrorsHoursParameter:
    """Tests for hours parameter (AC#3)."""

    @pytest.mark.asyncio
    async def test_hours_filter(
        self,
        client: TestClient,
        test_user_session_headers: dict,
        db_session: AsyncSession,
    ):
        """Should filter to last N hours."""
        now = datetime.now(timezone.utc)

        # Create old errors (25 hours ago)
        for i in range(5):
            error = ErrorLogModel(
                level="error",
                error_type="OLD_ERROR",
                message=f"Old {i}",
                context_data=json.dumps({}),
                created_at=now - timedelta(hours=25),
            )
            db_session.add(error)

        # Create recent errors (1 hour ago)
        for i in range(3):
            error = ErrorLogModel(
                level="error",
                error_type="RECENT_ERROR",
                message=f"Recent {i}",
                context_data=json.dumps({}),
                created_at=now - timedelta(hours=1),
            )
            db_session.add(error)

        await db_session.commit()

        response = client.get(
            "/api/errors?hours=24",
            headers=test_user_session_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        for error in data["errors"]:
            assert error["error_type"] == "RECENT_ERROR"

    @pytest.mark.asyncio
    async def test_hours_validation_min(
        self,
        client: TestClient,
        test_user_session_headers: dict,
    ):
        """Should reject hours < 1."""
        response = client.get(
            "/api/errors?hours=0",
            headers=test_user_session_headers,
        )

        # App uses custom validation handler that returns 400
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_combined_limit_and_hours(
        self,
        client: TestClient,
        test_user_session_headers: dict,
        db_session: AsyncSession,
    ):
        """Should apply both limit and hours filters."""
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

        response = client.get(
            "/api/errors?limit=5&hours=6",
            headers=test_user_session_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Should return 5 (limited by limit param, even though 6 are in timeframe)
        assert data["count"] == 5


class TestGetErrorsFormat:
    """Tests for error log entry format (AC#4)."""

    @pytest.mark.asyncio
    async def test_entry_format(
        self,
        client: TestClient,
        test_user_session_headers: dict,
        db_session: AsyncSession,
    ):
        """Should return entries in correct format."""
        error = ErrorLogModel(
            level="error",
            error_type="DEX_TIMEOUT",
            message="Extended DEX timeout after 10s",
            context_data=json.dumps({
                "signal_id": "abc123",
                "dex_id": "extended",
                "latency_ms": 10000,
            }),
            created_at=datetime(2026, 1, 19, 10, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(error)
        await db_session.commit()

        response = client.get("/api/errors", headers=test_user_session_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) == 1

        entry = data["errors"][0]
        # Check format per AC#4
        assert entry["id"].startswith("err-")
        assert entry["level"] == "error"
        assert entry["error_type"] == "DEX_TIMEOUT"
        assert entry["message"] == "Extended DEX timeout after 10s"
        assert entry["context"]["signal_id"] == "abc123"
        assert entry["context"]["dex_id"] == "extended"
        assert entry["context"]["latency_ms"] == 10000
        assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_entries_sorted_descending(
        self,
        client: TestClient,
        test_user_session_headers: dict,
        db_session: AsyncSession,
    ):
        """Should return entries sorted by timestamp descending."""
        now = datetime.now(timezone.utc)

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

        response = client.get("/api/errors", headers=test_user_session_headers)

        assert response.status_code == 200
        data = response.json()

        # Most recent should be first (index 0)
        assert data["errors"][0]["context"]["index"] == 0
        assert data["errors"][-1]["context"]["index"] == 4
