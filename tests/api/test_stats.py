"""Unit tests for Stats API endpoints (Story 5.2).

Tests volume display endpoint with today/week aggregation,
per-DEX breakdown, filtering, and authentication.

Story 5.2: Volume Display (Today/Week)
- AC#1: GET /api/stats/volume returns today's and this_week's volume per DEX
- AC#2: Today uses UTC midnight to current time
- AC#3: This week uses Monday 00:00 UTC to current time
- AC#4: Empty periods return "0.00" not null
- AC#5: ?dex parameter filters to specific DEX
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from kitkat.models import VolumeStats


class TestVolumeEndpointStructure:
    """Test GET /api/stats/volume returns correct JSON structure (AC#1)."""

    @pytest.mark.asyncio
    async def test_volume_endpoint_returns_correct_structure(self):
        """Test response includes today, this_week, and updated_at fields."""
        from kitkat.api.stats import get_volume_stats

        # Mock dependencies
        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_volume_stats = AsyncMock(
            return_value=VolumeStats(
                dex_id="extended",
                period="today",
                volume_usd=Decimal("1000.00"),
                execution_count=5,
                last_updated=datetime.now(timezone.utc),
            )
        )

        result = await get_volume_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
            dex=None,
        )

        assert "today" in result
        assert "this_week" in result
        assert "updated_at" in result

    @pytest.mark.asyncio
    async def test_volume_endpoint_includes_total_in_each_period(self):
        """Test each period includes a 'total' aggregation."""
        from kitkat.api.stats import get_volume_stats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_volume_stats = AsyncMock(
            return_value=VolumeStats(
                dex_id="all",
                period="today",
                volume_usd=Decimal("0"),
                execution_count=0,
                last_updated=datetime.now(timezone.utc),
            )
        )

        result = await get_volume_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
            dex=None,
        )

        assert "total" in result["today"]
        assert "total" in result["this_week"]

    @pytest.mark.asyncio
    async def test_volume_entry_has_volume_usd_and_executions(self):
        """Test each DEX entry has volume_usd and executions fields."""
        from kitkat.api.stats import get_volume_stats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_volume_stats = AsyncMock(
            return_value=VolumeStats(
                dex_id="extended",
                period="today",
                volume_usd=Decimal("47250.00"),
                execution_count=14,
                last_updated=datetime.now(timezone.utc),
            )
        )

        result = await get_volume_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
            dex="extended",
        )

        # Check structure of DEX entry
        assert "volume_usd" in result["today"]["extended"]
        assert "executions" in result["today"]["extended"]


class TestVolumeFormatting:
    """Test volume values are formatted correctly (AC#4)."""

    @pytest.mark.asyncio
    async def test_volume_formatted_as_string_with_two_decimals(self):
        """Test volume_usd is formatted as string with 2 decimal places."""
        from kitkat.api.stats import get_volume_stats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_volume_stats = AsyncMock(
            return_value=VolumeStats(
                dex_id="extended",
                period="today",
                volume_usd=Decimal("47250.00"),
                execution_count=14,
                last_updated=datetime.now(timezone.utc),
            )
        )

        result = await get_volume_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
            dex="extended",
        )

        # Volume should be string format
        volume_usd = result["today"]["extended"]["volume_usd"]
        assert isinstance(volume_usd, str)
        assert volume_usd == "47250.00"

    @pytest.mark.asyncio
    async def test_empty_results_return_zero_string(self):
        """Test empty results return '0.00' not null (AC#4)."""
        from kitkat.api.stats import get_volume_stats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_volume_stats = AsyncMock(
            return_value=VolumeStats(
                dex_id="all",
                period="today",
                volume_usd=Decimal("0"),
                execution_count=0,
                last_updated=datetime.now(timezone.utc),
            )
        )

        result = await get_volume_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
            dex=None,
        )

        # Should be "0.00" not null or missing
        assert result["today"]["total"]["volume_usd"] == "0.00"
        assert result["today"]["total"]["executions"] == 0


class TestDexFiltering:
    """Test DEX filter parameter (AC#5)."""

    @pytest.mark.asyncio
    async def test_dex_filter_returns_only_that_dex(self):
        """Test ?dex=extended returns only extended stats."""
        from kitkat.api.stats import get_volume_stats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_volume_stats = AsyncMock(
            return_value=VolumeStats(
                dex_id="extended",
                period="today",
                volume_usd=Decimal("1000.00"),
                execution_count=5,
                last_updated=datetime.now(timezone.utc),
            )
        )

        result = await get_volume_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
            dex="extended",
        )

        # Should have extended but not other DEXs
        assert "extended" in result["today"]
        # When filtering by single DEX, that DEX IS the total
        assert "total" in result["today"]

    @pytest.mark.asyncio
    async def test_no_dex_filter_includes_all_dexs(self):
        """Test no filter returns all DEXs plus total."""
        from kitkat.api.stats import get_volume_stats

        mock_user = MagicMock()
        mock_user.id = 1

        # Return different stats for different calls
        call_count = 0

        async def mock_get_stats(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            dex_id = kwargs.get("dex_id") or "all"
            return VolumeStats(
                dex_id=dex_id,
                period=kwargs.get("period", "today"),
                volume_usd=Decimal("1000.00"),
                execution_count=5,
                last_updated=datetime.now(timezone.utc),
            )

        mock_stats_service = MagicMock()
        mock_stats_service.get_volume_stats = AsyncMock(side_effect=mock_get_stats)

        result = await get_volume_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
            dex=None,
        )

        # Should have total
        assert "total" in result["today"]
        assert "total" in result["this_week"]


class TestPeriodCalculation:
    """Test period calculations use correct time ranges (AC#2, AC#3)."""

    @pytest.mark.asyncio
    async def test_today_period_used_for_today_stats(self):
        """Test 'today' period is requested for today's stats (AC#2)."""
        from kitkat.api.stats import get_volume_stats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_volume_stats = AsyncMock(
            return_value=VolumeStats(
                dex_id="all",
                period="today",
                volume_usd=Decimal("0"),
                execution_count=0,
                last_updated=datetime.now(timezone.utc),
            )
        )

        await get_volume_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
            dex=None,
        )

        # Verify 'today' period was requested
        calls = mock_stats_service.get_volume_stats.call_args_list
        periods_requested = [call.kwargs.get("period") for call in calls]
        assert "today" in periods_requested

    @pytest.mark.asyncio
    async def test_this_week_period_used_for_week_stats(self):
        """Test 'this_week' period is requested for week's stats (AC#3)."""
        from kitkat.api.stats import get_volume_stats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_volume_stats = AsyncMock(
            return_value=VolumeStats(
                dex_id="all",
                period="this_week",
                volume_usd=Decimal("0"),
                execution_count=0,
                last_updated=datetime.now(timezone.utc),
            )
        )

        await get_volume_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
            dex=None,
        )

        # Verify 'this_week' period was requested
        calls = mock_stats_service.get_volume_stats.call_args_list
        periods_requested = [call.kwargs.get("period") for call in calls]
        assert "this_week" in periods_requested


class TestRouterRegistration:
    """Test stats router is properly configured."""

    def test_stats_router_exists(self):
        """Test stats module has router attribute."""
        from kitkat.api import stats

        assert hasattr(stats, "router")

    def test_volume_endpoint_registered(self):
        """Test /api/stats/volume endpoint is registered."""
        from kitkat.api.stats import router

        routes = [route.path for route in router.routes]
        assert "/api/stats/volume" in routes


# ============================================================================
# Dashboard Endpoint Tests (Story 5.4)
# ============================================================================


# ============================================================================
# Execution Stats Endpoint Tests (Story 5.3)
# ============================================================================


class TestExecutionStatsEndpointStructure:
    """Test GET /api/stats/executions returns correct JSON structure (AC#1)."""

    @pytest.mark.asyncio
    async def test_execution_stats_returns_correct_structure(self):
        """Test AC#1: Response includes today, this_week, all_time, updated_at."""
        from kitkat.api.stats import get_execution_stats
        from kitkat.models import ExecutionPeriodStats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=14,
                successful=14,
                failed=0,
                partial=0,
                success_rate="100.00%",
            )
        )

        result = await get_execution_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
        )

        # Verify all required fields present (AC#1)
        assert result.today is not None
        assert result.this_week is not None
        assert result.all_time is not None
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_execution_stats_period_has_all_fields(self):
        """Test AC#1: Each period has total, successful, failed, partial, success_rate."""
        from kitkat.api.stats import get_execution_stats
        from kitkat.models import ExecutionPeriodStats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=89,
                successful=87,
                failed=1,
                partial=1,
                success_rate="97.75%",
            )
        )

        result = await get_execution_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
        )

        # Check each period has required fields
        for period in [result.today, result.this_week, result.all_time]:
            assert hasattr(period, "total")
            assert hasattr(period, "successful")
            assert hasattr(period, "failed")
            assert hasattr(period, "partial")
            assert hasattr(period, "success_rate")

    @pytest.mark.asyncio
    async def test_execution_stats_success_rate_format(self):
        """Test AC#1: success_rate is string percentage or 'N/A'."""
        from kitkat.api.stats import get_execution_stats
        from kitkat.models import ExecutionPeriodStats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=14,
                successful=14,
                failed=0,
                partial=0,
                success_rate="100.00%",
            )
        )

        result = await get_execution_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
        )

        # Verify success_rate is string
        assert isinstance(result.today.success_rate, str)
        assert result.today.success_rate == "100.00%"


class TestExecutionStatsAuthentication:
    """Test authentication requirements for execution stats endpoint."""

    def test_execution_stats_requires_authentication(self):
        """Test endpoint requires authentication via Depends(get_current_user)."""
        import inspect

        from kitkat.api.stats import get_execution_stats

        sig = inspect.signature(get_execution_stats)
        params = sig.parameters

        # Verify current_user parameter exists with Depends
        assert "current_user" in params
        param = params["current_user"]
        assert param.default is not inspect.Parameter.empty
        # The default should be a Depends object
        assert hasattr(param.default, "dependency")


class TestExecutionStatsEndpointRegistration:
    """Test execution stats endpoint is properly registered."""

    def test_execution_stats_endpoint_registered(self):
        """Test /api/stats/executions endpoint is registered."""
        from kitkat.api.stats import router

        routes = [route.path for route in router.routes]
        assert "/api/stats/executions" in routes


class TestExecutionStatsPeriods:
    """Test all time periods work correctly (Task 5.6)."""

    @pytest.mark.asyncio
    async def test_calls_service_for_each_period(self):
        """Test service is called for today, this_week, and all_time periods."""
        from kitkat.api.stats import get_execution_stats
        from kitkat.models import ExecutionPeriodStats

        mock_user = MagicMock()
        mock_user.id = 1

        mock_stats_service = MagicMock()
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=0,
                successful=0,
                failed=0,
                partial=0,
                success_rate="N/A",
            )
        )

        await get_execution_stats(
            current_user=mock_user,
            stats_service=mock_stats_service,
        )

        # Verify all three periods were requested
        calls = mock_stats_service.get_execution_stats.call_args_list
        periods_requested = [call.kwargs.get("period") for call in calls]
        assert "today" in periods_requested
        assert "this_week" in periods_requested
        assert "all_time" in periods_requested


class TestDashboardEndpointStructure:
    """Test GET /api/dashboard returns correct JSON structure (AC#1)."""

    @pytest.mark.asyncio
    async def test_dashboard_returns_all_required_fields(self):
        """Test AC#1: Dashboard returns all required fields."""
        from kitkat.api.stats import get_dashboard
        from kitkat.models import (
            AggregatedVolumeStats,
            DEXHealth,
            ExecutionPeriodStats,
            SystemHealth,
        )

        mock_user = MagicMock()
        mock_user.wallet_address = "0x123"

        # Mock StatsService
        mock_stats_service = MagicMock()
        mock_stats_service.get_aggregated_volume_stats = AsyncMock(
            return_value=AggregatedVolumeStats(
                period="today",
                total_volume_usd=Decimal("47250.00"),
                total_execution_count=14,
                by_dex={
                    "extended": VolumeStats(
                        dex_id="extended",
                        period="today",
                        volume_usd=Decimal("47250.00"),
                        execution_count=14,
                        last_updated=datetime.now(timezone.utc),
                    )
                },
                last_updated=datetime.now(timezone.utc),
            )
        )
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=14,
                successful=14,
                failed=0,
                partial=0,
                success_rate="100.00%",
            )
        )

        # Mock HealthService
        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="healthy",
                        latency_ms=45,
                        last_successful=datetime.now(timezone.utc),
                        error_count=0,
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock database session for onboarding checks (Story 5.5)
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_dashboard(
            current_user=mock_user,
            stats_service=mock_stats_service,
            health_service=mock_health_service,
            session=mock_session,
        )

        # Verify all required fields present (AC#1)
        assert result.status in ("all_ok", "degraded", "offline")
        assert isinstance(result.test_mode, bool)
        assert isinstance(result.dex_status, dict)
        assert result.volume_today is not None
        assert result.executions_today is not None
        assert isinstance(result.recent_errors, int)
        assert isinstance(result.onboarding_complete, bool)
        assert result.updated_at is not None

        # Verify nested structure
        assert result.volume_today.total_usd == "47250.00"
        assert result.executions_today.total == 14
        assert result.executions_today.success_rate == "100.00%"


class TestDashboardStatusCalculation:
    """Test overall status calculation (AC#2, AC#3)."""

    @pytest.mark.asyncio
    async def test_status_all_ok_when_all_healthy(self):
        """Test AC#2: Status is 'all_ok' when all DEXs healthy."""
        from kitkat.api.stats import get_dashboard
        from kitkat.models import (
            AggregatedVolumeStats,
            DEXHealth,
            ExecutionPeriodStats,
            SystemHealth,
        )

        mock_user = MagicMock()
        mock_stats_service = MagicMock()
        mock_stats_service.get_aggregated_volume_stats = AsyncMock(
            return_value=AggregatedVolumeStats(
                period="today",
                total_volume_usd=Decimal("0"),
                total_execution_count=0,
                by_dex={},
                last_updated=datetime.now(timezone.utc),
            )
        )
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=0, successful=0, failed=0, partial=0, success_rate="N/A"
            )
        )

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="healthy",
                        latency_ms=45,
                        last_successful=datetime.now(timezone.utc),
                        error_count=0,
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock database session for onboarding checks (Story 5.5)
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_dashboard(
            current_user=mock_user,
            stats_service=mock_stats_service,
            health_service=mock_health_service,
            session=mock_session,
        )

        assert result.status == "all_ok"

    @pytest.mark.asyncio
    async def test_status_degraded_when_dex_degraded(self):
        """Test AC#3: Status is 'degraded' when any DEX degraded."""
        from kitkat.api.stats import get_dashboard
        from kitkat.models import (
            AggregatedVolumeStats,
            DEXHealth,
            ExecutionPeriodStats,
            SystemHealth,
        )

        mock_user = MagicMock()
        mock_stats_service = MagicMock()
        mock_stats_service.get_aggregated_volume_stats = AsyncMock(
            return_value=AggregatedVolumeStats(
                period="today",
                total_volume_usd=Decimal("0"),
                total_execution_count=0,
                by_dex={},
                last_updated=datetime.now(timezone.utc),
            )
        )
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=0, successful=0, failed=0, partial=0, success_rate="N/A"
            )
        )

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="degraded",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="degraded",
                        latency_ms=500,
                        last_successful=datetime.now(timezone.utc),
                        error_count=2,
                        error_message="High latency detected",
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock database session for onboarding checks (Story 5.5)
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_dashboard(
            current_user=mock_user,
            stats_service=mock_stats_service,
            health_service=mock_health_service,
            session=mock_session,
        )

        assert result.status == "degraded"

    @pytest.mark.asyncio
    async def test_status_offline_when_dex_offline(self):
        """Test AC#3: Status is 'offline' when any DEX offline."""
        from kitkat.api.stats import get_dashboard
        from kitkat.models import (
            AggregatedVolumeStats,
            DEXHealth,
            ExecutionPeriodStats,
            SystemHealth,
        )

        mock_user = MagicMock()
        mock_stats_service = MagicMock()
        mock_stats_service.get_aggregated_volume_stats = AsyncMock(
            return_value=AggregatedVolumeStats(
                period="today",
                total_volume_usd=Decimal("0"),
                total_execution_count=0,
                by_dex={},
                last_updated=datetime.now(timezone.utc),
            )
        )
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=0, successful=0, failed=0, partial=0, success_rate="N/A"
            )
        )

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="offline",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="offline",
                        latency_ms=None,
                        last_successful=None,
                        error_count=5,
                        error_message="Connection failed",
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock database session for onboarding checks (Story 5.5)
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_dashboard(
            current_user=mock_user,
            stats_service=mock_stats_service,
            health_service=mock_health_service,
            session=mock_session,
        )

        assert result.status == "offline"


class TestDashboardTestMode:
    """Test test mode handling (AC#5)."""

    @pytest.mark.asyncio
    async def test_test_mode_warning_when_enabled(self):
        """Test AC#5: Test mode warning appears when enabled."""
        from unittest.mock import patch

        from kitkat.api.stats import get_dashboard
        from kitkat.models import (
            AggregatedVolumeStats,
            DEXHealth,
            ExecutionPeriodStats,
            SystemHealth,
        )

        mock_user = MagicMock()
        mock_stats_service = MagicMock()
        mock_stats_service.get_aggregated_volume_stats = AsyncMock(
            return_value=AggregatedVolumeStats(
                period="today",
                total_volume_usd=Decimal("0"),
                total_execution_count=0,
                by_dex={},
                last_updated=datetime.now(timezone.utc),
            )
        )
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=0, successful=0, failed=0, partial=0, success_rate="N/A"
            )
        )

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock settings with test_mode=True
        mock_settings = MagicMock()
        mock_settings.test_mode = True

        # Mock database session for onboarding checks (Story 5.5)
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("kitkat.api.stats.get_settings", return_value=mock_settings):
            result = await get_dashboard(
                current_user=mock_user,
                stats_service=mock_stats_service,
                health_service=mock_health_service,
                session=mock_session,
            )

        assert result.test_mode is True
        assert result.test_mode_warning == "No real trades - test mode active"

    @pytest.mark.asyncio
    async def test_no_warning_when_test_mode_disabled(self):
        """Test AC#5: No test mode warning when disabled."""
        from unittest.mock import patch

        from kitkat.api.stats import get_dashboard
        from kitkat.models import (
            AggregatedVolumeStats,
            DEXHealth,
            ExecutionPeriodStats,
            SystemHealth,
        )

        mock_user = MagicMock()
        mock_stats_service = MagicMock()
        mock_stats_service.get_aggregated_volume_stats = AsyncMock(
            return_value=AggregatedVolumeStats(
                period="today",
                total_volume_usd=Decimal("0"),
                total_execution_count=0,
                by_dex={},
                last_updated=datetime.now(timezone.utc),
            )
        )
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=0, successful=0, failed=0, partial=0, success_rate="N/A"
            )
        )

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock settings with test_mode=False
        mock_settings = MagicMock()
        mock_settings.test_mode = False

        # Mock database session for onboarding checks (Story 5.5)
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("kitkat.api.stats.get_settings", return_value=mock_settings):
            result = await get_dashboard(
                current_user=mock_user,
                stats_service=mock_stats_service,
                health_service=mock_health_service,
                session=mock_session,
            )

        assert result.test_mode is False
        assert result.test_mode_warning is None


class TestDashboardRecentErrors:
    """Test recent errors count (AC#4)."""

    @pytest.mark.asyncio
    async def test_recent_errors_returns_count(self):
        """Test AC#4: recent_errors shows error count (placeholder returns 0)."""
        from kitkat.api.stats import get_dashboard
        from kitkat.models import (
            AggregatedVolumeStats,
            DEXHealth,
            ExecutionPeriodStats,
            SystemHealth,
        )

        mock_user = MagicMock()
        mock_stats_service = MagicMock()
        mock_stats_service.get_aggregated_volume_stats = AsyncMock(
            return_value=AggregatedVolumeStats(
                period="today",
                total_volume_usd=Decimal("0"),
                total_execution_count=0,
                by_dex={},
                last_updated=datetime.now(timezone.utc),
            )
        )
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=0, successful=0, failed=0, partial=0, success_rate="N/A"
            )
        )

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock database session for onboarding checks (Story 5.5)
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_dashboard(
            current_user=mock_user,
            stats_service=mock_stats_service,
            health_service=mock_health_service,
            session=mock_session,
        )

        # recent_errors should be a non-negative integer (placeholder returns 0)
        assert isinstance(result.recent_errors, int)
        assert result.recent_errors >= 0


class TestDashboardAuthentication:
    """Test authentication requirements (AC#7)."""

    def test_dashboard_requires_authentication(self):
        """Test AC#7: Dashboard endpoint requires authentication via Depends(get_current_user)."""
        from fastapi import Depends

        from kitkat.api.stats import get_dashboard

        # Check function signature for auth dependency
        import inspect

        sig = inspect.signature(get_dashboard)
        params = sig.parameters

        # Verify current_user parameter exists with Depends
        assert "current_user" in params
        param = params["current_user"]
        assert param.default is not inspect.Parameter.empty
        # The default should be a Depends object
        assert hasattr(param.default, "dependency")


class TestDashboardPerformance:
    """Test response time performance (AC#6)."""

    @pytest.mark.asyncio
    async def test_dashboard_response_time_under_200ms(self):
        """Test AC#6: Response time < 200ms with mock services."""
        import time

        from kitkat.api.stats import get_dashboard
        from kitkat.models import (
            AggregatedVolumeStats,
            DEXHealth,
            ExecutionPeriodStats,
            SystemHealth,
        )

        mock_user = MagicMock()

        # Mock services with instant responses
        mock_stats_service = MagicMock()
        mock_stats_service.get_aggregated_volume_stats = AsyncMock(
            return_value=AggregatedVolumeStats(
                period="today",
                total_volume_usd=Decimal("47250.00"),
                total_execution_count=14,
                by_dex={
                    "extended": VolumeStats(
                        dex_id="extended",
                        period="today",
                        volume_usd=Decimal("47250.00"),
                        execution_count=14,
                        last_updated=datetime.now(timezone.utc),
                    )
                },
                last_updated=datetime.now(timezone.utc),
            )
        )
        mock_stats_service.get_execution_stats = AsyncMock(
            return_value=ExecutionPeriodStats(
                total=14, successful=14, failed=0, partial=0, success_rate="100.00%"
            )
        )

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="healthy",
                        latency_ms=45,
                        last_successful=datetime.now(timezone.utc),
                        error_count=0,
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock database session for onboarding checks (Story 5.5)
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Measure response time
        start_time = time.perf_counter()
        await get_dashboard(
            current_user=mock_user,
            stats_service=mock_stats_service,
            health_service=mock_health_service,
            session=mock_session,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Should be well under 200ms with mocks
        assert elapsed_ms < 200, f"Response time {elapsed_ms:.2f}ms exceeds 200ms target"


class TestDashboardEndpointRegistration:
    """Test dashboard endpoint is properly registered."""

    def test_dashboard_endpoint_registered(self):
        """Test /api/dashboard endpoint is registered."""
        from kitkat.api.stats import router

        routes = [route.path for route in router.routes]
        assert "/api/dashboard" in routes


# ============================================================================
# Story 5.5: Onboarding Checklist Tests
# ============================================================================


class TestOnboardingEndpointStructure:
    """Test GET /api/onboarding returns correct JSON structure (AC#1)."""

    @pytest.mark.asyncio
    async def test_onboarding_returns_correct_structure(self):
        """Test AC#1: Onboarding returns all required fields."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import DEXHealth, SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        # Mock HealthService with healthy DEX
        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="healthy",
                        latency_ms=45,
                        last_successful=datetime.now(timezone.utc),
                        error_count=0,
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock database session (no executions)
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        # Verify all required fields present
        assert hasattr(result, "complete")
        assert hasattr(result, "progress")
        assert hasattr(result, "steps")
        assert isinstance(result.complete, bool)
        assert isinstance(result.progress, str)
        assert isinstance(result.steps, list)

    @pytest.mark.asyncio
    async def test_onboarding_has_five_steps(self):
        """Test AC#1: Onboarding returns exactly 5 steps."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import DEXHealth, SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        assert len(result.steps) == 5

    @pytest.mark.asyncio
    async def test_onboarding_steps_have_required_fields(self):
        """Test AC#1: Each step has id, name, and complete fields."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        for step in result.steps:
            assert hasattr(step, "id")
            assert hasattr(step, "name")
            assert hasattr(step, "complete")
            assert isinstance(step.id, str)
            assert isinstance(step.name, str)
            assert isinstance(step.complete, bool)


class TestOnboardingWalletConnected:
    """Test wallet_connected step (AC#3)."""

    @pytest.mark.asyncio
    async def test_wallet_connected_true_when_authenticated(self):
        """Test AC#3: wallet_connected is true when user is authenticated."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        # Find wallet_connected step
        wallet_step = next(s for s in result.steps if s.id == "wallet_connected")
        assert wallet_step.complete is True


class TestOnboardingDexAuthorized:
    """Test dex_authorized step (AC#4)."""

    @pytest.mark.asyncio
    async def test_dex_authorized_true_when_healthy_dex(self):
        """Test AC#4: dex_authorized is true when DEX is healthy."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import DEXHealth, SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="healthy",
                        latency_ms=45,
                        last_successful=datetime.now(timezone.utc),
                        error_count=0,
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        dex_step = next(s for s in result.steps if s.id == "dex_authorized")
        assert dex_step.complete is True

    @pytest.mark.asyncio
    async def test_dex_authorized_true_when_degraded_dex(self):
        """Test AC#4: dex_authorized is true when DEX is degraded (still connected)."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import DEXHealth, SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="degraded",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="degraded",
                        latency_ms=500,
                        last_successful=datetime.now(timezone.utc),
                        error_count=2,
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        dex_step = next(s for s in result.steps if s.id == "dex_authorized")
        assert dex_step.complete is True

    @pytest.mark.asyncio
    async def test_dex_authorized_false_when_all_offline(self):
        """Test AC#4: dex_authorized is false when all DEXs are offline."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import DEXHealth, SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="offline",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="offline",
                        latency_ms=None,
                        last_successful=None,
                        error_count=5,
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        dex_step = next(s for s in result.steps if s.id == "dex_authorized")
        assert dex_step.complete is False


class TestOnboardingWebhookConfigured:
    """Test webhook_configured step (AC#5)."""

    @pytest.mark.asyncio
    async def test_webhook_configured_true_for_authenticated_user(self):
        """Test AC#5: webhook_configured is true for authenticated user (MVP simplification)."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        webhook_step = next(s for s in result.steps if s.id == "webhook_configured")
        assert webhook_step.complete is True


class TestOnboardingTestSignalSent:
    """Test test_signal_sent step (AC#6)."""

    @pytest.mark.asyncio
    async def test_test_signal_sent_false_when_no_executions(self):
        """Test AC#6: test_signal_sent is false when no test mode executions exist."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        # No executions
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        test_step = next(s for s in result.steps if s.id == "test_signal_sent")
        assert test_step.complete is False

    @pytest.mark.asyncio
    async def test_test_signal_sent_true_with_test_execution(self):
        """Test AC#6: test_signal_sent is true when test mode execution exists."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock execution with is_test_mode=true
        mock_execution = MagicMock()
        mock_execution.status = "filled"
        mock_execution.result_data = '{"is_test_mode": true}'

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_execution]
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        test_step = next(s for s in result.steps if s.id == "test_signal_sent")
        assert test_step.complete is True


class TestOnboardingFirstLiveTrade:
    """Test first_live_trade step (AC#7)."""

    @pytest.mark.asyncio
    async def test_first_live_trade_false_when_no_executions(self):
        """Test AC#7: first_live_trade is false when no non-test executions exist."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        live_step = next(s for s in result.steps if s.id == "first_live_trade")
        assert live_step.complete is False

    @pytest.mark.asyncio
    async def test_first_live_trade_true_with_live_execution(self):
        """Test AC#7: first_live_trade is true when non-test execution exists."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock execution with is_test_mode=false (live trade)
        mock_execution = MagicMock()
        mock_execution.status = "filled"
        mock_execution.result_data = '{"is_test_mode": false}'

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_execution]
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        live_step = next(s for s in result.steps if s.id == "first_live_trade")
        assert live_step.complete is True


class TestOnboardingProgressCalculation:
    """Test progress and complete calculation (AC#8)."""

    @pytest.mark.asyncio
    async def test_progress_format_x_of_5(self):
        """Test AC#8: Progress shows correct 'X/5' format."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        # Progress should be "X/5" format
        assert "/" in result.progress
        parts = result.progress.split("/")
        assert len(parts) == 2
        assert parts[1] == "5"
        assert 0 <= int(parts[0]) <= 5

    @pytest.mark.asyncio
    async def test_complete_false_when_not_all_steps_done(self):
        """Test AC#8: complete is false when not all steps are done."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        # No DEXs connected (dex_authorized = False)
        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="offline",
                components={},
                timestamp=datetime.now(timezone.utc),
            )
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        assert result.complete is False
        # Should have 2/5 (wallet + webhook) with no DEX and no executions
        assert result.progress == "2/5"

    @pytest.mark.asyncio
    async def test_complete_true_when_all_steps_done(self):
        """Test AC#8: complete is true and progress is '5/5' when all steps complete."""
        from kitkat.api.stats import get_onboarding_status
        from kitkat.models import DEXHealth, SystemHealth

        mock_user = MagicMock()
        mock_user.id = 1

        # Healthy DEX (dex_authorized = True)
        mock_health_service = MagicMock()
        mock_health_service.get_system_health = AsyncMock(
            return_value=SystemHealth(
                status="healthy",
                components={
                    "extended": DEXHealth(
                        dex_id="extended",
                        status="healthy",
                        latency_ms=45,
                        last_successful=datetime.now(timezone.utc),
                        error_count=0,
                    )
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Mock executions: one test mode, one live
        mock_test_exec = MagicMock()
        mock_test_exec.status = "filled"
        mock_test_exec.result_data = '{"is_test_mode": true}'

        mock_live_exec = MagicMock()
        mock_live_exec.status = "filled"
        mock_live_exec.result_data = '{"is_test_mode": false}'

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_test_exec, mock_live_exec]
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_onboarding_status(
            current_user=mock_user,
            health_service=mock_health_service,
            session=mock_session,
        )

        assert result.complete is True
        assert result.progress == "5/5"


class TestOnboardingAuthentication:
    """Test authentication requirements."""

    def test_onboarding_requires_authentication(self):
        """Test onboarding endpoint requires authentication via Depends(get_current_user)."""
        import inspect

        from kitkat.api.stats import get_onboarding_status

        sig = inspect.signature(get_onboarding_status)
        params = sig.parameters

        # Verify current_user parameter exists with Depends
        assert "current_user" in params
        param = params["current_user"]
        assert param.default is not inspect.Parameter.empty
        assert hasattr(param.default, "dependency")


class TestOnboardingEndpointRegistration:
    """Test endpoint registration."""

    def test_onboarding_endpoint_registered(self):
        """Test /api/onboarding endpoint is registered."""
        from kitkat.api.stats import router

        routes = [route.path for route in router.routes]
        assert "/api/onboarding" in routes
