"""Unit tests for StatsService volume tracking (Story 5.1).

Tests comprehensive volume calculation, period filtering, caching behavior,
and test mode exclusion for execution statistics.

Story 5.1: Stats Service & Volume Tracking
- AC#1: StatsService class exists for volume tracking
- AC#2: Volume added per DEX for successful executions
- AC#3: Volume aggregated by DEX, period, and user
- AC#4: Calculate volume from filled_size * fill_price, exclude test mode
- AC#5: Cache with TTL and invalidation
- AC#6: get_volume_stats returns VolumeStats model
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kitkat.models import TimePeriod, VolumeStats


class TestVolumeStatsModel:
    """Test VolumeStats Pydantic model (AC#6)."""

    def test_volume_stats_creation(self):
        """Test VolumeStats model can be created with required fields."""
        stats = VolumeStats(
            dex_id="extended",
            period="today",
            volume_usd=Decimal("47250.00"),
            execution_count=14,
            last_updated=datetime.now(timezone.utc),
        )

        assert stats.dex_id == "extended"
        assert stats.period == "today"
        assert stats.volume_usd == Decimal("47250.00")
        assert stats.execution_count == 14
        assert stats.last_updated is not None

    def test_volume_stats_zero_values(self):
        """Test VolumeStats accepts zero values for empty results."""
        stats = VolumeStats(
            dex_id="all",
            period="this_week",
            volume_usd=Decimal("0"),
            execution_count=0,
            last_updated=datetime.now(timezone.utc),
        )

        assert stats.volume_usd == Decimal("0")
        assert stats.execution_count == 0

    def test_volume_stats_large_volume(self):
        """Test VolumeStats handles large volume values."""
        stats = VolumeStats(
            dex_id="extended",
            period="all_time",
            volume_usd=Decimal("999999999.99"),
            execution_count=100000,
            last_updated=datetime.now(timezone.utc),
        )

        assert stats.volume_usd == Decimal("999999999.99")


class TestTimePeriodType:
    """Test TimePeriod Literal type (Task 1.2)."""

    def test_valid_periods(self):
        """Test all valid period values are accepted."""
        valid_periods: list[TimePeriod] = [
            "today",
            "this_week",
            "this_month",
            "all_time",
        ]

        for period in valid_periods:
            stats = VolumeStats(
                dex_id="mock",
                period=period,
                volume_usd=Decimal("0"),
                execution_count=0,
                last_updated=datetime.now(timezone.utc),
            )
            assert stats.period == period


class TestAggregatedVolumeStats:
    """Test AggregatedVolumeStats model for multi-DEX responses (Task 1.3)."""

    def test_aggregated_stats_creation(self):
        """Test AggregatedVolumeStats aggregates multiple DEX stats."""
        from kitkat.models import AggregatedVolumeStats

        stats = AggregatedVolumeStats(
            period="today",
            total_volume_usd=Decimal("100000.00"),
            total_execution_count=50,
            by_dex={
                "extended": VolumeStats(
                    dex_id="extended",
                    period="today",
                    volume_usd=Decimal("80000.00"),
                    execution_count=40,
                    last_updated=datetime.now(timezone.utc),
                ),
                "mock": VolumeStats(
                    dex_id="mock",
                    period="today",
                    volume_usd=Decimal("20000.00"),
                    execution_count=10,
                    last_updated=datetime.now(timezone.utc),
                ),
            },
            last_updated=datetime.now(timezone.utc),
        )

        assert stats.total_volume_usd == Decimal("100000.00")
        assert stats.total_execution_count == 50
        assert len(stats.by_dex) == 2
        assert "extended" in stats.by_dex
        assert "mock" in stats.by_dex


class TestStatsServiceInit:
    """Test StatsService initialization (AC#1, Task 2)."""

    def test_stats_service_exists(self):
        """Test StatsService class can be imported (AC#1)."""
        from kitkat.services.stats import StatsService

        assert StatsService is not None

    def test_stats_service_init(self):
        """Test StatsService initializes with session factory."""
        from kitkat.services.stats import StatsService

        mock_factory = MagicMock()
        service = StatsService(session_factory=mock_factory)

        assert service._session_factory == mock_factory
        assert service._volume_cache == {}
        assert service._cache_ttl == 60


class TestPeriodBoundsCalculation:
    """Test _calculate_period_bounds helper (Task 2.4)."""

    def test_today_bounds(self):
        """Test 'today' period starts at midnight UTC."""
        from kitkat.services.stats import StatsService

        service = StatsService(session_factory=MagicMock())
        start, end = service._calculate_period_bounds("today")

        now = datetime.now(timezone.utc)
        expected_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        assert start == expected_start
        assert end <= now
        assert start.tzinfo is not None
        assert end.tzinfo is not None

    def test_this_week_bounds(self):
        """Test 'this_week' period starts on Monday 00:00 UTC."""
        from kitkat.services.stats import StatsService

        service = StatsService(session_factory=MagicMock())
        start, end = service._calculate_period_bounds("this_week")

        # Start should be a Monday
        assert start.weekday() == 0
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0
        assert start.tzinfo is not None

    def test_this_month_bounds(self):
        """Test 'this_month' period starts on 1st of month."""
        from kitkat.services.stats import StatsService

        service = StatsService(session_factory=MagicMock())
        start, end = service._calculate_period_bounds("this_month")

        assert start.day == 1
        assert start.hour == 0
        assert start.minute == 0
        assert start.tzinfo is not None

    def test_all_time_bounds(self):
        """Test 'all_time' period starts from 2020."""
        from kitkat.services.stats import StatsService

        service = StatsService(session_factory=MagicMock())
        start, end = service._calculate_period_bounds("all_time")

        assert start.year == 2020
        assert start.month == 1
        assert start.day == 1
        assert start.tzinfo is not None


class TestVolumeCalculation:
    """Test volume calculation logic (AC#2, AC#4, Task 3)."""

    @pytest.fixture
    def mock_session_factory(self):
        """Create a mock session factory for testing."""
        mock_factory = MagicMock()
        return mock_factory

    @pytest.mark.asyncio
    async def test_volume_calculation_with_filled_executions(self):
        """Test volume sums filled_size * fill_price (AC#4)."""
        from kitkat.database import ExecutionModel
        from kitkat.services.stats import StatsService

        # Create mock executions
        mock_execution1 = MagicMock(spec=ExecutionModel)
        mock_execution1.id = 1
        mock_execution1.dex_id = "extended"
        mock_execution1.status = "filled"
        mock_execution1.result_data = json.dumps({
            "filled_size": "0.5",
            "fill_price": "2000.00",
            "is_test_mode": False
        })
        mock_execution1.created_at = datetime.now(timezone.utc)

        mock_execution2 = MagicMock(spec=ExecutionModel)
        mock_execution2.id = 2
        mock_execution2.dex_id = "extended"
        mock_execution2.status = "filled"
        mock_execution2.result_data = json.dumps({
            "filled_size": "1.0",
            "fill_price": "2100.00",
            "is_test_mode": False
        })
        mock_execution2.created_at = datetime.now(timezone.utc)

        # Mock session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_execution1, mock_execution2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock factory context manager
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        service = StatsService(session_factory=mock_factory)
        stats = await service.get_volume_stats(dex_id="extended", period="today")

        # 0.5 * 2000 + 1.0 * 2100 = 1000 + 2100 = 3100
        assert stats.volume_usd == Decimal("3100.00")
        assert stats.execution_count == 2
        assert stats.dex_id == "extended"

    @pytest.mark.asyncio
    async def test_test_mode_executions_excluded(self):
        """Test that test mode executions are excluded from volume (AC#4)."""
        from kitkat.database import ExecutionModel
        from kitkat.services.stats import StatsService

        # One regular execution, one test mode
        mock_execution1 = MagicMock(spec=ExecutionModel)
        mock_execution1.id = 1
        mock_execution1.dex_id = "extended"
        mock_execution1.status = "filled"
        mock_execution1.result_data = json.dumps({
            "filled_size": "1.0",
            "fill_price": "2000.00",
            "is_test_mode": False
        })
        mock_execution1.created_at = datetime.now(timezone.utc)

        mock_execution2 = MagicMock(spec=ExecutionModel)
        mock_execution2.id = 2
        mock_execution2.dex_id = "mock"
        mock_execution2.status = "filled"
        mock_execution2.result_data = json.dumps({
            "filled_size": "5.0",
            "fill_price": "2000.00",
            "is_test_mode": True  # Test mode - should be excluded
        })
        mock_execution2.created_at = datetime.now(timezone.utc)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_execution1, mock_execution2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        service = StatsService(session_factory=mock_factory)
        stats = await service.get_volume_stats(period="today")

        # Only first execution counted: 1.0 * 2000 = 2000
        assert stats.volume_usd == Decimal("2000.00")
        assert stats.execution_count == 1

    @pytest.mark.asyncio
    async def test_empty_results_return_zero(self):
        """Test empty results return zero values (Task 6.6)."""
        from kitkat.services.stats import StatsService

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []  # No executions
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        service = StatsService(session_factory=mock_factory)
        stats = await service.get_volume_stats(dex_id="extended", period="today")

        assert stats.volume_usd == Decimal("0")
        assert stats.execution_count == 0

    @pytest.mark.asyncio
    async def test_per_dex_filtering(self):
        """Test volume is filtered by DEX ID (Task 6.4)."""
        from kitkat.database import ExecutionModel
        from kitkat.services.stats import StatsService

        # Execution for 'extended' DEX
        mock_execution1 = MagicMock(spec=ExecutionModel)
        mock_execution1.id = 1
        mock_execution1.dex_id = "extended"
        mock_execution1.status = "filled"
        mock_execution1.result_data = json.dumps({
            "filled_size": "1.0",
            "fill_price": "2000.00",
            "is_test_mode": False
        })
        mock_execution1.created_at = datetime.now(timezone.utc)

        # Execution for 'mock' DEX
        mock_execution2 = MagicMock(spec=ExecutionModel)
        mock_execution2.id = 2
        mock_execution2.dex_id = "mock"
        mock_execution2.status = "filled"
        mock_execution2.result_data = json.dumps({
            "filled_size": "5.0",
            "fill_price": "1000.00",
            "is_test_mode": False
        })
        mock_execution2.created_at = datetime.now(timezone.utc)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        # Return only extended execution when filtering by dex_id="extended"
        mock_scalars.all.return_value = [mock_execution1]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        service = StatsService(session_factory=mock_factory)
        stats = await service.get_volume_stats(dex_id="extended", period="today")

        # Only 'extended' DEX volume: 1.0 * 2000 = 2000
        assert stats.volume_usd == Decimal("2000.00")
        assert stats.execution_count == 1
        assert stats.dex_id == "extended"


class TestCaching:
    """Test caching behavior (AC#5, Task 4)."""

    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """Test cache key format (Task 4.2)."""
        from kitkat.services.stats import StatsService

        service = StatsService(session_factory=MagicMock())

        key1 = service._get_cache_key(user_id=123, dex_id="extended", period="today")
        assert key1 == "123:extended:today"

        key2 = service._get_cache_key(user_id=None, dex_id=None, period="this_week")
        assert key2 == "all:all:this_week"

        key3 = service._get_cache_key(user_id=456, dex_id=None, period="all_time")
        assert key3 == "456:all:all_time"

    def test_cache_validity_check(self):
        """Test cache TTL validation (Task 4.3)."""
        from kitkat.services.stats import StatsService

        service = StatsService(session_factory=MagicMock(), cache_ttl=60)

        # Not in cache
        assert not service._is_cache_valid("nonexistent:key:today")

        # Add to cache
        now = datetime.now(timezone.utc)
        stats = VolumeStats(
            dex_id="extended",
            period="today",
            volume_usd=Decimal("1000"),
            execution_count=5,
            last_updated=now,
        )
        service._volume_cache["test:key:today"] = (stats, now)

        # Should be valid immediately
        assert service._is_cache_valid("test:key:today")

        # Simulate expired cache
        old_time = now - timedelta(seconds=120)
        service._volume_cache["old:key:today"] = (stats, old_time)
        assert not service._is_cache_valid("old:key:today")

    def test_cache_invalidation_all(self):
        """Test cache invalidation for all entries (Task 4.4)."""
        from kitkat.services.stats import StatsService

        service = StatsService(session_factory=MagicMock())
        now = datetime.now(timezone.utc)
        stats = VolumeStats(
            dex_id="extended",
            period="today",
            volume_usd=Decimal("1000"),
            execution_count=5,
            last_updated=now,
        )

        service._volume_cache["1:extended:today"] = (stats, now)
        service._volume_cache["2:mock:this_week"] = (stats, now)
        assert len(service._volume_cache) == 2

        service.invalidate_cache()  # Clear all
        assert len(service._volume_cache) == 0

    def test_cache_invalidation_per_user(self):
        """Test cache invalidation for specific user (Task 4.4)."""
        from kitkat.services.stats import StatsService

        service = StatsService(session_factory=MagicMock())
        now = datetime.now(timezone.utc)
        stats = VolumeStats(
            dex_id="extended",
            period="today",
            volume_usd=Decimal("1000"),
            execution_count=5,
            last_updated=now,
        )

        service._volume_cache["1:extended:today"] = (stats, now)
        service._volume_cache["1:mock:this_week"] = (stats, now)
        service._volume_cache["2:extended:today"] = (stats, now)
        assert len(service._volume_cache) == 3

        service.invalidate_cache(user_id=1)  # Only user 1
        assert len(service._volume_cache) == 1
        assert "2:extended:today" in service._volume_cache


class TestStatsServiceDependency:
    """Test get_stats_service dependency (Task 5.1)."""

    def test_get_stats_service_singleton(self):
        """Test get_stats_service returns singleton instance."""
        from kitkat.api import deps

        # Reset singleton for clean test
        deps._stats_service = None

        # Mock the session factory to avoid real database connection
        with patch("kitkat.database.get_async_session_factory") as mock_factory:
            mock_factory.return_value = MagicMock()

            service1 = deps.get_stats_service()
            service2 = deps.get_stats_service()

            # Same instance returned
            assert service1 is service2
            # Factory only called once (singleton pattern)
            mock_factory.assert_called_once()

        # Reset after test
        deps._stats_service = None

    def test_get_stats_service_exported(self):
        """Test get_stats_service is exported from deps module."""
        from kitkat.api.deps import get_stats_service

        assert callable(get_stats_service)
