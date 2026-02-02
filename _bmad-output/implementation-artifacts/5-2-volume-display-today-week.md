# Story 5.2: Volume Display (Today/Week)

Status: review

## Story

As a **user**,
I want **to see today's and this week's volume totals**,
So that **I can track my progress toward airdrop qualification thresholds**.

## Acceptance Criteria

1. **Given** an authenticated user, **When** they call `GET /api/stats/volume`, **Then** the response includes today's volume per DEX:
```json
{
  "today": {
    "extended": {"volume_usd": "47250.00", "executions": 14},
    "total": {"volume_usd": "47250.00", "executions": 14}
  },
  "this_week": {
    "extended": {"volume_usd": "284000.00", "executions": 89},
    "total": {"volume_usd": "284000.00", "executions": 89}
  },
  "updated_at": "2026-01-19T10:00:00Z"
}
```

2. **Given** "today" calculation, **When** determining the time range, **Then** it uses UTC midnight to current time

3. **Given** "this week" calculation, **When** determining the time range, **Then** it uses Monday 00:00 UTC to current time

4. **Given** no executions in a period, **When** volume is queried, **Then** the values are `"0.00"` (not null or missing)

5. **Given** the volume endpoint, **When** called with `?dex=extended` parameter, **Then** only that DEX's volume is returned

## Tasks / Subtasks

- [x] Task 1: Create API endpoint file (AC: #1)
  - [x] 1.1 Create `src/kitkat/api/stats.py` with FastAPI router
  - [x] 1.2 Add router import and include in `main.py`

- [x] Task 2: Implement volume endpoint (AC: #1, #4)
  - [x] 2.1 Create `GET /api/stats/volume` endpoint with authentication dependency
  - [x] 2.2 Inject StatsService via `get_stats_service()` dependency
  - [x] 2.3 Return response matching AC#1 JSON structure with proper Decimal formatting

- [x] Task 3: Implement per-DEX aggregation (AC: #1, #2, #3)
  - [x] 3.1 Call `stats_service.get_volume_stats()` for "today" period per DEX
  - [x] 3.2 Call `stats_service.get_volume_stats()` for "this_week" period per DEX
  - [x] 3.3 Aggregate totals across all DEXs for each period
  - [x] 3.4 Use existing `_calculate_period_bounds()` (already uses UTC, Monday start)

- [x] Task 4: Implement DEX filter parameter (AC: #5)
  - [x] 4.1 Add optional `dex: str | None = Query(None)` parameter
  - [x] 4.2 When `?dex=extended` provided, only return that DEX's stats
  - [x] 4.3 Return 400 if invalid DEX ID provided

- [x] Task 5: Create Pydantic response models (AC: #1)
  - [x] 5.1 Add `VolumeResponse` model to `models.py`
  - [x] 5.2 Add `DexVolumeEntry` model for per-DEX breakdown
  - [x] 5.3 Ensure Decimal fields serialize as strings ("47250.00" format)

- [x] Task 6: Write comprehensive tests
  - [x] 6.1 Test endpoint returns correct JSON structure
  - [x] 6.2 Test today's volume calculation
  - [x] 6.3 Test this_week's volume calculation
  - [x] 6.4 Test ?dex filter parameter
  - [x] 6.5 Test empty results return "0.00"
  - [x] 6.6 Test authentication required (401 without valid session)

## Dev Notes

### Architecture Patterns (MUST FOLLOW)

**From Architecture Document:**
- **File Location**: `src/kitkat/api/stats.py` (API layer)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Use absolute imports from `kitkat.*` package
- **Router Pattern**: Use `router = APIRouter()` with `@router.get()` decorators
- **Authentication**: Use `Depends(get_current_user)` for authenticated endpoints

**API Pattern (from health.py):**
```python
from fastapi import APIRouter, Depends, Query

from kitkat.api.deps import get_current_user, get_stats_service
from kitkat.models import CurrentUser
from kitkat.services.stats import StatsService

router = APIRouter()

@router.get("/api/stats/volume")
async def get_volume_stats(
    current_user: CurrentUser = Depends(get_current_user),
    stats_service: StatsService = Depends(get_stats_service),
    dex: str | None = Query(None, description="Filter by DEX ID"),
) -> dict:
    """Get volume statistics for today and this week."""
    ...
```

### Previous Story Intelligence (Story 5.1)

**What Story 5.1 Built:**
- `StatsService` class in `services/stats.py`
- `get_volume_stats(user_id, dex_id, period)` method returns `VolumeStats`
- `VolumeStats` model with: `dex_id`, `period`, `volume_usd` (Decimal), `execution_count`, `last_updated`
- `TimePeriod` Literal type: `"today"`, `"this_week"`, `"this_month"`, `"all_time"`
- `get_stats_service()` singleton in `deps.py`
- Caching with 60s TTL already implemented

**Key Learning from Story 5.1:**
- Volume is stored as Decimal and should be serialized as string in JSON
- Period bounds use UTC (midnight for today, Monday for week)
- Empty results return `Decimal("0")` not None
- Test mode executions already excluded by StatsService

### Response Structure

**Required JSON Response (AC#1):**
```json
{
  "today": {
    "extended": {"volume_usd": "47250.00", "executions": 14},
    "mock": {"volume_usd": "0.00", "executions": 0},
    "total": {"volume_usd": "47250.00", "executions": 14}
  },
  "this_week": {
    "extended": {"volume_usd": "284000.00", "executions": 89},
    "mock": {"volume_usd": "0.00", "executions": 0},
    "total": {"volume_usd": "284000.00", "executions": 89}
  },
  "updated_at": "2026-01-19T10:00:00Z"
}
```

**Pydantic Response Model:**
```python
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field

class DexVolumeEntry(BaseModel):
    """Volume stats for a single DEX."""
    volume_usd: str = Field(..., description="Volume in USD as string")
    executions: int = Field(..., ge=0)

class PeriodVolumeStats(BaseModel):
    """Volume stats for a time period with per-DEX breakdown."""
    # Dynamic keys for DEX IDs, plus total
    # Use dict instead of fixed fields for flexibility

class VolumeResponse(BaseModel):
    """Response for GET /api/stats/volume endpoint."""
    today: dict[str, DexVolumeEntry]
    this_week: dict[str, DexVolumeEntry]
    updated_at: datetime
```

### Implementation Strategy

1. **Get all active DEX IDs**: Query distinct `dex_id` values from executions table or use known DEX list
2. **Loop through DEXs**: Call `stats_service.get_volume_stats(dex_id=dex, period="today")` for each
3. **Aggregate totals**: Sum volume_usd and execution_count across all DEXs
4. **Format Decimals**: Use `f"{volume:.2f}"` for consistent string format

### Router Registration Pattern

**In main.py:**
```python
from kitkat.api import stats

app.include_router(stats.router)
```

### Testing Patterns

**Test File Location:** `tests/api/test_stats.py`

**Test Pattern (from existing tests):**
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_volume_endpoint_returns_correct_structure(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    response = await async_client.get(
        "/api/stats/volume",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "today" in data
    assert "this_week" in data
    assert "total" in data["today"]
```

### Project Structure Notes

**Files to Create:**
- `src/kitkat/api/stats.py` - Volume stats endpoint

**Files to Modify:**
- `src/kitkat/main.py` - Import and include stats router
- `src/kitkat/models.py` - Add VolumeResponse, DexVolumeEntry models (optional, can use dict)

**Test Files to Create:**
- `tests/api/test_stats.py` - API endpoint tests

### Error Handling

- Return 401 if not authenticated (handled by `get_current_user` dependency)
- Return 400 if invalid DEX ID filter provided
- Return empty `"0.00"` values for periods with no executions (AC#4)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.2]
- [Source: _bmad-output/implementation-artifacts/5-1-stats-service-volume-tracking.md] - StatsService implementation
- [Source: src/kitkat/services/stats.py] - StatsService class
- [Source: src/kitkat/api/deps.py] - get_stats_service singleton
- [Source: src/kitkat/api/health.py] - API router pattern reference

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Implementation was already complete from previous session
- All 21 API tests pass (tests/api/test_stats.py)
- All 34 StatsService tests pass (tests/services/test_stats.py)
- Fixed one test that needed lazy initialization of `_exec_cache`
- Volume endpoint returns today/this_week with per-DEX breakdown and totals
- DEX filter parameter works correctly
- Empty periods return "0.00" as required

### Debug Log References

N/A - no issues encountered

### File List

- src/kitkat/api/stats.py (existing - volume endpoint implementation)
- src/kitkat/main.py (existing - router registration)
- src/kitkat/models.py (existing - VolumeStats, AggregatedVolumeStats models)
- src/kitkat/services/stats.py (existing - StatsService with get_volume_stats)
- src/kitkat/api/deps.py (existing - get_stats_service dependency)
- tests/api/test_stats.py (existing - 21 passing tests)
- tests/services/test_stats.py (modified - fixed lazy cache initialization test)

### Change Log

- 2026-02-02: Story 5.2 validated and marked for review - all tasks complete, all tests passing

