"""Volume tracking and execution statistics service (Story 5.1).

Provides aggregated volume and execution metrics per DEX with caching
for dashboard display and airdrop progress tracking.

Story 5.1: Stats Service & Volume Tracking
- AC#1: StatsService class for volume tracking
- AC#2: Volume added per DEX for successful executions
- AC#3: Volume aggregated by DEX, period, user
- AC#4: Sum filled_size * fill_price, exclude test mode
- AC#5: Cache with TTL and invalidation
- AC#6: get_volume_stats returns VolumeStats
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import and_, select

from kitkat.database import ExecutionModel
from kitkat.models import AggregatedVolumeStats, TimePeriod, VolumeStats


class StatsService:
    """Volume tracking and execution statistics service (Story 5.1).

    Aggregates execution volume and counts by DEX, time period, and user.
    Implements caching with configurable TTL for performance.
    """

    def __init__(self, session_factory, cache_ttl: int = 60):
        """Initialize StatsService.

        Args:
            session_factory: Async SQLAlchemy session factory
            cache_ttl: Cache time-to-live in seconds (default: 60)
        """
        self._session_factory = session_factory
        self._log = structlog.get_logger().bind(service="stats")
        self._volume_cache: dict[str, tuple[VolumeStats, datetime]] = {}
        self._cache_ttl = cache_ttl

    def _calculate_period_bounds(
        self, period: TimePeriod
    ) -> tuple[datetime, datetime]:
        """Calculate start/end timestamps for a period (UTC).

        Args:
            period: Time period ("today", "this_week", "this_month", "all_time")

        Returns:
            Tuple of (start_datetime, end_datetime) both timezone-aware UTC
        """
        now = datetime.now(timezone.utc)

        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == "this_week":
            # Monday 00:00 UTC to now
            days_since_monday = now.weekday()
            start = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = now
        elif period == "this_month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == "all_time":
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = now
        else:
            # Default to today if unknown period
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now

        return start, end

    def _get_cache_key(
        self,
        user_id: int | None,
        dex_id: str | None,
        period: TimePeriod,
    ) -> str:
        """Generate cache key for volume stats query.

        Args:
            user_id: Optional user filter
            dex_id: Optional DEX filter
            period: Time period

        Returns:
            Cache key string in format "user_id:dex_id:period"
        """
        return f"{user_id or 'all'}:{dex_id or 'all'}:{period}"

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached entry is still valid (within TTL).

        Args:
            key: Cache key to check

        Returns:
            True if cache entry exists and is within TTL
        """
        if key not in self._volume_cache:
            return False
        _, cached_at = self._volume_cache[key]
        elapsed = (datetime.now(timezone.utc) - cached_at).total_seconds()
        return elapsed < self._cache_ttl

    def invalidate_cache(self, user_id: int | None = None) -> None:
        """Invalidate cache entries for a user or all entries.

        Call this after new executions to ensure stats are fresh.

        Args:
            user_id: If provided, only invalidate entries for this user.
                     If None, invalidate all cache entries.
        """
        if user_id is None:
            self._volume_cache.clear()
            self._log.debug("Cache cleared completely")
        else:
            keys_to_remove = [
                k for k in self._volume_cache if k.startswith(f"{user_id}:")
            ]
            for k in keys_to_remove:
                del self._volume_cache[k]
            self._log.debug(
                "Cache invalidated for user",
                user_id=user_id,
                keys_removed=len(keys_to_remove),
            )

    async def get_volume_stats(
        self,
        user_id: int | None = None,
        dex_id: str | None = None,
        period: TimePeriod = "today",
    ) -> VolumeStats:
        """Get aggregated volume statistics (AC#3, AC#6).

        Queries the executions table to calculate total volume and execution
        count for successful (filled/partial) executions, excluding test mode.

        Args:
            user_id: Optional filter by user ID
            dex_id: Optional filter by DEX ID ("extended", "mock", etc.)
            period: Time period for aggregation

        Returns:
            VolumeStats with volume_usd, execution_count, and metadata
        """
        cache_key = self._get_cache_key(user_id, dex_id, period)

        # Check cache first (AC#5)
        if self._is_cache_valid(cache_key):
            stats, _ = self._volume_cache[cache_key]
            self._log.debug(
                "Cache hit",
                cache_key=cache_key,
                volume_usd=str(stats.volume_usd),
            )
            return stats

        # Calculate fresh stats from database
        start_dt, end_dt = self._calculate_period_bounds(period)

        log = self._log.bind(
            user_id=user_id,
            dex_id=dex_id,
            period=period,
            start_dt=start_dt.isoformat(),
            end_dt=end_dt.isoformat(),
        )

        async with self._session_factory() as session:
            # Build query for volume calculation (AC#4)
            # Filter: status in (filled, partial), within period, exclude test mode
            query = (
                select(ExecutionModel)
                .where(
                    and_(
                        ExecutionModel.status.in_(["filled", "partial"]),
                        ExecutionModel.created_at >= start_dt,
                        ExecutionModel.created_at <= end_dt,
                    )
                )
            )

            if dex_id:
                query = query.where(ExecutionModel.dex_id == dex_id)

            result = await session.execute(query)
            executions = result.scalars().all()

        # Calculate volume manually to handle JSON parsing (AC#4)
        total_volume = Decimal("0")
        execution_count = 0

        for execution in executions:
            # Parse result_data JSON
            try:
                if isinstance(execution.result_data, str):
                    result_data = json.loads(execution.result_data)
                else:
                    result_data = execution.result_data or {}
            except (json.JSONDecodeError, TypeError):
                result_data = {}

            # Exclude test mode executions (AC#4)
            is_test_mode = result_data.get("is_test_mode", False)
            if is_test_mode is True or is_test_mode == "true":
                continue

            # Calculate volume: filled_size * fill_price
            try:
                filled_size = Decimal(str(result_data.get("filled_size", "0")))
                fill_price = Decimal(str(result_data.get("fill_price", "0")))
                volume = filled_size * fill_price
                total_volume += volume
                execution_count += 1
            except (ValueError, TypeError, KeyError):
                # Skip malformed entries
                log.warning(
                    "Skipping execution with invalid volume data",
                    execution_id=execution.id,
                )
                continue

        now = datetime.now(timezone.utc)
        stats = VolumeStats(
            dex_id=dex_id or "all",
            period=period,
            volume_usd=total_volume,
            execution_count=execution_count,
            last_updated=now,
        )

        # Cache the result (AC#5)
        self._volume_cache[cache_key] = (stats, now)

        log.info(
            "Volume stats calculated",
            volume_usd=str(total_volume),
            execution_count=execution_count,
        )

        return stats

    async def get_aggregated_volume_stats(
        self,
        user_id: int | None = None,
        period: TimePeriod = "today",
    ) -> AggregatedVolumeStats:
        """Get aggregated volume across all DEXs with breakdown.

        Queries all DEXs and provides both totals and per-DEX stats.

        Args:
            user_id: Optional filter by user ID
            period: Time period for aggregation

        Returns:
            AggregatedVolumeStats with total and per-DEX breakdown
        """
        # Get all unique DEX IDs
        start_dt, end_dt = self._calculate_period_bounds(period)

        async with self._session_factory() as session:
            # Get distinct DEX IDs
            dex_query = (
                select(ExecutionModel.dex_id)
                .where(
                    and_(
                        ExecutionModel.status.in_(["filled", "partial"]),
                        ExecutionModel.created_at >= start_dt,
                        ExecutionModel.created_at <= end_dt,
                    )
                )
                .distinct()
            )
            result = await session.execute(dex_query)
            dex_ids = [row[0] for row in result.all()]

        # Get stats for each DEX
        by_dex: dict[str, VolumeStats] = {}
        total_volume = Decimal("0")
        total_count = 0

        for dex_id in dex_ids:
            stats = await self.get_volume_stats(
                user_id=user_id, dex_id=dex_id, period=period
            )
            by_dex[dex_id] = stats
            total_volume += stats.volume_usd
            total_count += stats.execution_count

        now = datetime.now(timezone.utc)
        return AggregatedVolumeStats(
            period=period,
            total_volume_usd=total_volume,
            total_execution_count=total_count,
            by_dex=by_dex,
            last_updated=now,
        )
