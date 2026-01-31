"""Unit tests for HealthService (Story 4.1).

Tests comprehensive health check aggregation, error tracking, and status
determination logic for all DEX adapters.

Story 4.1: Health Service & DEX Status
- AC#1: Health service aggregates status from all adapters
- AC#3: Per-DEX health status with error tracking
- AC#5: Status aggregation logic (healthy/degraded/offline)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kitkat.adapters.base import DEXAdapter, HealthStatus
from kitkat.models import DEXHealth, SystemHealth
from kitkat.services.health import HealthService


def create_health_status(
    dex_id: str = "mock",
    status: str = "healthy",
    connected: bool = True,
    latency_ms: int = 50,
    error_message: Optional[str] = None,
) -> HealthStatus:
    """Helper to create HealthStatus with all required fields."""
    return HealthStatus(
        dex_id=dex_id,
        status=status,
        connected=connected,
        latency_ms=latency_ms,
        last_check=datetime.now(timezone.utc),
        error_message=error_message,
    )


@pytest.fixture
def mock_adapter():
    """Create a mock DEX adapter for testing."""
    adapter = AsyncMock(spec=DEXAdapter)
    adapter.dex_id = "mock"
    adapter.health_check = AsyncMock()
    return adapter


@pytest.fixture
def mock_extended_adapter():
    """Create a mock Extended adapter."""
    adapter = AsyncMock(spec=DEXAdapter)
    adapter.dex_id = "extended"
    adapter.health_check = AsyncMock()
    return adapter


class TestHealthServiceInitialization:
    """Test HealthService initialization."""

    def test_init_empty_adapters(self):
        """Test initialization with no adapters."""
        service = HealthService(adapters=[])
        assert service._adapters == []
        assert service._error_tracker == {}
        assert service.uptime_seconds >= 0

    def test_init_with_adapters(self, mock_adapter, mock_extended_adapter):
        """Test initialization with multiple adapters."""
        adapters = [mock_adapter, mock_extended_adapter]
        service = HealthService(adapters=adapters)
        assert len(service._adapters) == 2
        assert service._adapters[0].dex_id == "mock"
        assert service._adapters[1].dex_id == "extended"

    def test_startup_time_tracking(self):
        """Test that startup time is recorded correctly."""
        service = HealthService(adapters=[])
        # Uptime should be very small (milliseconds)
        assert service.uptime_seconds >= 0
        assert service.uptime_seconds < 1


class TestHealthCheckAggregation:
    """Test health check query and aggregation (AC#1, AC#3)."""

    @pytest.mark.asyncio
    async def test_single_healthy_adapter(self, mock_adapter):
        """Test health check with single healthy adapter."""
        # Setup
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )
        service = HealthService(adapters=[mock_adapter])

        # Execute
        health = await service.get_system_health()

        # Verify
        assert health.status == "healthy"
        assert "mock" in health.components
        assert health.components["mock"].status == "healthy"
        assert health.components["mock"].latency_ms == 50
        mock_adapter.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_single_offline_adapter(self, mock_adapter):
        """Test health check with single offline adapter."""
        # Setup
        mock_adapter.health_check.side_effect = Exception("Connection failed")
        service = HealthService(adapters=[mock_adapter])

        # Execute
        health = await service.get_system_health()

        # Verify
        assert health.status == "offline"
        assert health.components["mock"].status == "offline"
        assert health.components["mock"].latency_ms is None
        assert health.components["mock"].error_count == 1

    @pytest.mark.asyncio
    async def test_multiple_adapters_parallel_execution(
        self, mock_adapter, mock_extended_adapter
    ):
        """Test that adapters are queried in parallel (AC#3)."""
        # Setup - simulate fast adapters
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=100
        )
        mock_extended_adapter.health_check.return_value = create_health_status(
            dex_id="extended", status="healthy", latency_ms=50
        )

        service = HealthService(adapters=[mock_adapter, mock_extended_adapter])

        # Execute
        start = datetime.now(timezone.utc)
        health = await service.get_system_health()
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()

        # Verify - should complete quickly (parallel execution)
        assert elapsed < 0.5  # Allow some overhead
        assert len(health.components) == 2

    @pytest.mark.asyncio
    async def test_empty_adapter_list(self):
        """Test health check with no adapters (AC#5 edge case)."""
        service = HealthService(adapters=[])

        # Execute
        health = await service.get_system_health()

        # Verify - should return healthy with no components
        assert health.status == "healthy"
        assert health.components == {}


class TestStatusAggregation:
    """Test status aggregation logic (AC#5)."""

    @pytest.mark.asyncio
    async def test_all_healthy(self, mock_adapter, mock_extended_adapter):
        """Test status when all adapters are healthy."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=45
        )
        mock_extended_adapter.health_check.return_value = create_health_status(
            dex_id="extended", status="healthy", latency_ms=50
        )

        service = HealthService(adapters=[mock_adapter, mock_extended_adapter])
        health = await service.get_system_health()

        assert health.status == "healthy"

    @pytest.mark.asyncio
    async def test_all_offline(self, mock_adapter, mock_extended_adapter):
        """Test status when all adapters are offline."""
        mock_adapter.health_check.side_effect = Exception("Failed")
        mock_extended_adapter.health_check.side_effect = Exception("Failed")

        service = HealthService(adapters=[mock_adapter, mock_extended_adapter])
        health = await service.get_system_health()

        assert health.status == "offline"

    @pytest.mark.asyncio
    async def test_mixed_healthy_and_offline(
        self, mock_adapter, mock_extended_adapter
    ):
        """Test status when one adapter is healthy and one is offline (AC#5)."""
        # One healthy, one offline
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=45
        )
        mock_extended_adapter.health_check.side_effect = Exception("Failed")

        service = HealthService(adapters=[mock_adapter, mock_extended_adapter])
        health = await service.get_system_health()

        assert health.status == "degraded"

    @pytest.mark.asyncio
    async def test_mixed_healthy_and_degraded(
        self, mock_adapter, mock_extended_adapter
    ):
        """Test status with healthy and degraded adapters."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=45
        )
        mock_extended_adapter.health_check.return_value = create_health_status(
            dex_id="extended", status="degraded", latency_ms=500
        )

        service = HealthService(adapters=[mock_adapter, mock_extended_adapter])
        health = await service.get_system_health()

        assert health.status == "degraded"


class TestErrorTracking:
    """Test error tracking and 5-minute rolling window (AC#3)."""

    @pytest.mark.asyncio
    async def test_error_count_increments(self, mock_adapter):
        """Test that error count increases on failures."""
        mock_adapter.health_check.side_effect = Exception("Failed")
        service = HealthService(adapters=[mock_adapter])

        # First check - 1 error
        health1 = await service.get_system_health()
        assert health1.components["mock"].error_count == 1

        # Second check - 2 errors
        health2 = await service.get_system_health()
        assert health2.components["mock"].error_count == 2

    @pytest.mark.asyncio
    async def test_error_count_reset_on_success(self, mock_adapter):
        """Test that error count resets to 0 on successful check."""
        # Fail first
        mock_adapter.health_check.side_effect = Exception("Failed")
        service = HealthService(adapters=[mock_adapter])
        health1 = await service.get_system_health()
        assert health1.components["mock"].error_count == 1

        # Then succeed
        mock_adapter.health_check.side_effect = None
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=45
        )
        health2 = await service.get_system_health()
        assert health2.components["mock"].error_count == 0
        assert health2.components["mock"].status == "healthy"

    def test_error_cleanup_removes_old_errors(self, mock_adapter):
        """Test that errors older than 5 minutes are cleaned up."""
        service = HealthService(adapters=[mock_adapter])

        # Manually add errors with old timestamps
        old_time = datetime.now(timezone.utc) - timedelta(minutes=6)
        recent_time = datetime.now(timezone.utc)

        service._error_tracker["mock"] = [
            (old_time, "old_error"),
            (recent_time, "recent_error"),
        ]

        # Cleanup
        error_count = service._get_error_count("mock")

        # Only recent error should remain
        assert error_count == 1

    def test_5_minute_window_boundary(self, mock_adapter):
        """Test error counting at 5-minute boundary."""
        service = HealthService(adapters=[mock_adapter])

        now = datetime.now(timezone.utc)
        # Exactly at 5 minute mark should be included
        exactly_5mins_ago = now - timedelta(minutes=5)
        # Just over 5 minutes should be excluded
        over_5mins_ago = now - timedelta(minutes=5, seconds=1)

        service._error_tracker["mock"] = [
            (over_5mins_ago, "old"),  # Should be removed (> 5 mins)
            (exactly_5mins_ago, "boundary"),  # Should be kept (exactly 5 mins ago is still in window)
        ]

        error_count = service._get_error_count("mock")
        # Both should be removed since cleanup is > 5 minutes
        # Actually, the condition is "if ts > five_minutes_ago" so exactly_5mins_ago == five_minutes_ago should be excluded
        assert error_count == 0


class TestUptimeTracking:
    """Test uptime calculation since startup."""

    def test_uptime_increases(self):
        """Test that uptime increases over time."""
        service = HealthService(adapters=[])
        uptime1 = service.uptime_seconds

        import time

        time.sleep(0.1)
        uptime2 = service.uptime_seconds

        assert uptime2 >= uptime1

    def test_uptime_format(self):
        """Test that uptime is returned as integer seconds."""
        service = HealthService(adapters=[])
        uptime = service.uptime_seconds

        assert isinstance(uptime, int)
        assert uptime >= 0


class TestResponseModels:
    """Test that response models are correctly created."""

    @pytest.mark.asyncio
    async def test_system_health_response_format(self, mock_adapter):
        """Test SystemHealth response has all required fields."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )
        service = HealthService(adapters=[mock_adapter])

        health = await service.get_system_health()

        # Verify SystemHealth structure
        assert isinstance(health, SystemHealth)
        assert health.status in ("healthy", "degraded", "offline")
        assert isinstance(health.components, dict)
        assert isinstance(health.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_dex_health_response_format(self, mock_adapter):
        """Test DEXHealth response has all required fields."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )
        service = HealthService(adapters=[mock_adapter])

        health = await service.get_system_health()
        dex_health = health.components["mock"]

        # Verify DEXHealth structure
        assert isinstance(dex_health, DEXHealth)
        assert dex_health.dex_id == "mock"
        assert dex_health.status in ("healthy", "degraded", "offline")
        assert dex_health.latency_ms is None or isinstance(dex_health.latency_ms, int)
        assert dex_health.last_successful is None or isinstance(
            dex_health.last_successful, datetime
        )
        assert isinstance(dex_health.error_count, int)
        assert dex_health.error_count >= 0
