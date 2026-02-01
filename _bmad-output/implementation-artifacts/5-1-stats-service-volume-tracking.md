# Story 5.1: Stats Service & Volume Tracking

Status: review

## Story

As a **system**,
I want **to track and aggregate execution volume per DEX**,
So that **users can see their trading activity and progress toward airdrop goals**.

## Acceptance Criteria

1. **Given** the stats service, **When** I check `services/stats.py`, **Then** a `StatsService` class exists for volume and execution tracking

2. **Given** any successful execution, **When** it is recorded, **Then** the volume is added to the user's total for that DEX and volume is stored in USD equivalent (or base asset value)

3. **Given** volume tracking, **When** queried, **Then** volume can be aggregated by:
   - Per DEX (`extended`, `mock`, etc.)
   - Per time period (today, this week, this month, all-time)
   - Per user

4. **Given** the `executions` table, **When** volume is calculated, **Then** it sums `filled_size * fill_price` for all successful executions and excludes test mode executions (`is_test_mode: true`)

5. **Given** volume calculation performance, **When** queried frequently, **Then** aggregated totals are cached and updated incrementally with cache invalidation on new executions

6. **Given** the stats service, **When** `get_volume_stats(user_id, dex_id, period)` is called, **Then** it returns:
```python
VolumeStats(
    dex_id="extended",
    period="today",
    volume_usd=Decimal("47250.00"),
    execution_count=14,
    last_updated=datetime
)
```

## Tasks / Subtasks

- [x] Task 1: Create Pydantic models for stats (AC: #6)
  - [x] 1.1 Add `VolumeStats` model to `models.py` with fields: dex_id, period, volume_usd, execution_count, last_updated
  - [x] 1.2 Add `TimePeriod` Literal type: "today", "this_week", "this_month", "all_time"
  - [x] 1.3 Add `AggregatedVolumeStats` model for multi-DEX responses

- [x] Task 2: Create StatsService class (AC: #1, #3)
  - [x] 2.1 Create `src/kitkat/services/stats.py` with `StatsService` class
  - [x] 2.2 Implement `__init__` accepting async session factory
  - [x] 2.3 Implement `get_volume_stats(user_id: int | None, dex_id: str | None, period: TimePeriod)` method
  - [x] 2.4 Implement private helper `_calculate_period_bounds(period)` returning (start_dt, end_dt)

- [x] Task 3: Implement volume calculation logic (AC: #2, #4)
  - [x] 3.1 Query `executions` table filtering by: status in ("filled", "partial"), user_id (if provided), dex_id (if provided), created_at within period bounds
  - [x] 3.2 Exclude test mode executions using `result_data->>'is_test_mode' != 'true'` or similar
  - [x] 3.3 Calculate volume as SUM(result_data->>'filled_size' * result_data->>'fill_price')
  - [x] 3.4 Return execution count alongside volume

- [x] Task 4: Implement caching for performance (AC: #5)
  - [x] 4.1 Add in-memory cache dict `_volume_cache: dict[str, tuple[VolumeStats, datetime]]`
  - [x] 4.2 Implement cache key generation: `f"{user_id}:{dex_id}:{period}"`
  - [x] 4.3 Set cache TTL to 60 seconds (configurable)
  - [x] 4.4 Add `invalidate_cache(user_id: int | None = None)` method for cache clearing on new executions

- [x] Task 5: Register StatsService in application (AC: #1)
  - [x] 5.1 Add `get_stats_service()` singleton in `api/deps.py`
  - [x] 5.2 Export `StatsService` from `services/__init__.py`
  - [x] 5.3 Initialize StatsService in `main.py` lifespan if needed (not needed - lazy init via singleton)

- [x] Task 6: Write comprehensive tests
  - [x] 6.1 Test volume calculation with successful executions
  - [x] 6.2 Test test mode executions are excluded
  - [x] 6.3 Test period filtering (today, this_week, etc.)
  - [x] 6.4 Test per-DEX filtering
  - [x] 6.5 Test cache behavior and invalidation
  - [x] 6.6 Test empty results return zero values

## Dev Notes

### Architecture Patterns (MUST FOLLOW)

**From Architecture Document:**
- **File Location**: `src/kitkat/services/stats.py` (services layer)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Use absolute imports from `kitkat.*` package
- **Async**: All database operations must be async
- **Logging**: Use `structlog.get_logger()` with bound context

**Service Pattern:**
```python
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

class StatsService:
    """Volume tracking and execution statistics service (Story 5.1)."""

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._log = structlog.get_logger().bind(service="stats")
        self._volume_cache: dict[str, tuple[VolumeStats, datetime]] = {}
        self._cache_ttl = 60  # seconds
```

### Database Schema Reference

**Executions Table** (from existing `database.py`):
```python
class ExecutionRecord(Base):
    __tablename__ = "executions"

    id: Mapped[int]
    signal_id: Mapped[str]  # FK to signals
    dex_id: Mapped[str]     # "extended", "mock"
    order_id: Mapped[str | None]
    status: Mapped[str]     # "pending", "filled", "partial", "failed"
    result_data: Mapped[dict]  # JSON with DEX response
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime]
```

**result_data JSON structure** (from MockAdapter and ExtendedAdapter):
```json
{
    "filled_size": "0.5",
    "fill_price": "2150.00",
    "is_test_mode": true,
    "order_id": "mock-12345",
    "submitted_at": "2026-01-19T10:00:00Z"
}
```

### Period Calculation Logic

```python
from datetime import datetime, timezone, timedelta

def _calculate_period_bounds(period: str) -> tuple[datetime, datetime]:
    """Calculate start/end timestamps for a period (UTC)."""
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

    return start, end
```

### SQLAlchemy Query Pattern

```python
from sqlalchemy import select, func, and_, cast, Numeric
from sqlalchemy.dialects.sqlite import JSON

async def get_volume_stats(
    self,
    user_id: int | None = None,
    dex_id: str | None = None,
    period: str = "today"
) -> VolumeStats:
    start_dt, end_dt = self._calculate_period_bounds(period)

    async with self._session_factory() as session:
        query = select(
            func.count().label("execution_count"),
            # SQLite JSON extraction for volume calculation
            func.sum(
                cast(ExecutionRecord.result_data["filled_size"].astext, Numeric) *
                cast(ExecutionRecord.result_data["fill_price"].astext, Numeric)
            ).label("volume_usd")
        ).where(
            and_(
                ExecutionRecord.status.in_(["filled", "partial"]),
                ExecutionRecord.created_at >= start_dt,
                ExecutionRecord.created_at <= end_dt,
                # Exclude test mode
                func.coalesce(
                    ExecutionRecord.result_data["is_test_mode"].astext, "false"
                ) != "true"
            )
        )

        if dex_id:
            query = query.where(ExecutionRecord.dex_id == dex_id)

        result = await session.execute(query)
        row = result.one()

        return VolumeStats(
            dex_id=dex_id or "all",
            period=period,
            volume_usd=row.volume_usd or Decimal("0"),
            execution_count=row.execution_count,
            last_updated=datetime.now(timezone.utc)
        )
```

### Project Structure Notes

**Files to Create:**
- `src/kitkat/services/stats.py` - StatsService implementation

**Files to Modify:**
- `src/kitkat/models.py` - Add VolumeStats, TimePeriod models
- `src/kitkat/services/__init__.py` - Export StatsService
- `src/kitkat/api/deps.py` - Add get_stats_service singleton

**Test Files to Create:**
- `tests/services/test_stats.py` - StatsService unit tests

### Integration with Existing Code

**Execution Recording (Story 2.8):**
The `execution_service.py` already creates execution records. Ensure `result_data` includes:
- `filled_size`: Decimal as string
- `fill_price`: Decimal as string
- `is_test_mode`: boolean

**Signal Processor (Story 2.9):**
After execution, signal processor should call `stats_service.invalidate_cache()` if real-time accuracy needed.

### Caching Strategy

```python
def _get_cache_key(self, user_id: int | None, dex_id: str | None, period: str) -> str:
    return f"{user_id or 'all'}:{dex_id or 'all'}:{period}"

def _is_cache_valid(self, key: str) -> bool:
    if key not in self._volume_cache:
        return False
    _, cached_at = self._volume_cache[key]
    return (datetime.now(timezone.utc) - cached_at).seconds < self._cache_ttl

def invalidate_cache(self, user_id: int | None = None):
    """Invalidate cache entries for a user or all entries."""
    if user_id is None:
        self._volume_cache.clear()
    else:
        keys_to_remove = [k for k in self._volume_cache if k.startswith(f"{user_id}:")]
        for k in keys_to_remove:
            del self._volume_cache[k]
```

### Error Handling

- Return zero values for empty results (not None or exceptions)
- Log queries with structlog for debugging
- Handle JSON extraction failures gracefully (treat as 0)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Architecture]
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Patterns]
- [Source: src/kitkat/services/execution_service.py] - Execution recording
- [Source: src/kitkat/models.py] - Existing execution models

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- All 6 tasks completed using TDD red-green-refactor cycle
- 21 unit tests written and passing
- StatsService provides volume tracking with caching (60s TTL)
- Test mode executions properly excluded from volume calculations
- Period bounds correctly calculated for today/this_week/this_month/all_time
- Singleton pattern with thread-safe double-checked locking in deps.py

### Debug Log References

N/A - No debug issues encountered

### File List

- src/kitkat/models.py - Added VolumeStats, TimePeriod, AggregatedVolumeStats
- src/kitkat/services/stats.py - New StatsService implementation
- src/kitkat/services/__init__.py - Added StatsService export
- src/kitkat/api/deps.py - Added get_stats_service() singleton
- tests/services/test_stats.py - 21 comprehensive unit tests
