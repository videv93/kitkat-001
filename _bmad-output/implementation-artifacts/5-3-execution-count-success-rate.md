# Story 5.3: Execution Count & Success Rate

Status: review

## Story

As a **user**,
I want **to see my execution count and success rate**,
So that **I can monitor system reliability**.

## Acceptance Criteria

1. **Given** an authenticated user, **When** they call `GET /api/stats/executions`, **Then** the response includes:
```json
{
  "today": {
    "total": 14,
    "successful": 14,
    "failed": 0,
    "partial": 0,
    "success_rate": "100.00%"
  },
  "this_week": {
    "total": 89,
    "successful": 87,
    "failed": 1,
    "partial": 1,
    "success_rate": "97.75%"
  },
  "all_time": {
    "total": 523,
    "successful": 515,
    "failed": 5,
    "partial": 3,
    "success_rate": "98.47%"
  }
}
```

2. **Given** success rate calculation, **When** computed, **Then** `success_rate = (successful + partial) / total * 100` (partial fills count as successful)

3. **Given** zero executions, **When** success rate is calculated, **Then** it returns `"N/A"` (not divide by zero error)

4. **Given** execution counts, **When** queried, **Then** test mode executions are excluded from counts

## Tasks / Subtasks

- [x] Task 1: Add execution stats method to StatsService (AC: #1, #2, #3, #4)
  - [x] 1.1 Add `get_execution_stats(user_id, period)` method to `services/stats.py`
  - [x] 1.2 Query executions table filtering by period bounds (reuse `_calculate_period_bounds`)
  - [x] 1.3 Exclude test mode executions (check `result_data->>'is_test_mode' != 'true'`)
  - [x] 1.4 Count by status: filled, partial, failed
  - [x] 1.5 Calculate success_rate = (successful + partial) / total * 100, return "N/A" if total=0

- [x] Task 2: Create Pydantic response models (AC: #1)
  - [x] 2.1 Add `ExecutionPeriodStats` model with: total, successful, failed, partial, success_rate
  - [x] 2.2 Add `ExecutionStatsResponse` model with: today, this_week, all_time, updated_at
  - [x] 2.3 Ensure success_rate is string ("100.00%" or "N/A")

- [x] Task 3: Add execution stats endpoint to API (AC: #1)
  - [x] 3.1 Add `GET /api/stats/executions` endpoint to `api/stats.py`
  - [x] 3.2 Use `Depends(get_current_user)` for authentication
  - [x] 3.3 Inject StatsService via `Depends(get_stats_service)`
  - [x] 3.4 Call `stats_service.get_execution_stats()` for each period
  - [x] 3.5 Return structured response matching AC#1 format

- [x] Task 4: Add caching for execution stats (AC: #4)
  - [x] 4.1 Add execution stats cache separate from volume cache (different TTL may apply)
  - [x] 4.2 Reuse cache key pattern: `f"exec:{user_id or 'all'}:{period}"`
  - [x] 4.3 Invalidate with `invalidate_cache()` on new executions

- [x] Task 5: Write comprehensive tests
  - [x] 5.1 Test endpoint returns correct JSON structure (AC#1)
  - [x] 5.2 Test success rate calculation includes partial as successful (AC#2)
  - [x] 5.3 Test zero executions returns "N/A" (AC#3)
  - [x] 5.4 Test test mode executions excluded (AC#4)
  - [x] 5.5 Test authentication required (401 without valid session)
  - [x] 5.6 Test each time period (today, this_week, all_time)

## Dev Notes

### Architecture Patterns (MUST FOLLOW)

**From Project Context:**
- **File Location**: Extend existing `src/kitkat/api/stats.py` and `src/kitkat/services/stats.py`
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Use absolute imports from `kitkat.*` package
- **Async**: ALL database operations must be async
- **Logging**: Use `structlog.get_logger()` with bound context

**CRITICAL: Extend existing files, do NOT create new ones:**
- `services/stats.py` - Add `get_execution_stats()` method to existing `StatsService` class
- `api/stats.py` - Add new endpoint to existing router
- `models.py` - Add new Pydantic models alongside existing `VolumeStats`

### Existing Code to Reuse (MUST USE)

**From Story 5.1 - StatsService (services/stats.py):**
```python
# REUSE these existing methods:
def _calculate_period_bounds(self, period: TimePeriod) -> tuple[datetime, datetime]
def _get_cache_key(self, user_id, dex_id, period) -> str
def _is_cache_valid(self, key) -> bool
def invalidate_cache(self, user_id=None) -> None

# REUSE this query pattern for excluding test mode:
# Check result_data["is_test_mode"] != True or "true"
```

**From Story 5.2 - API Pattern (api/stats.py):**
```python
# REUSE this endpoint pattern:
@router.get("/api/stats/executions")
async def get_execution_stats(
    current_user: CurrentUser = Depends(get_current_user),
    stats_service: StatsService = Depends(get_stats_service),
) -> ExecutionStatsResponse:
    ...
```

### ExecutionModel Schema (from database.py)

**Existing Execution Statuses (MUST USE):**
- `"filled"` - Full execution (counts as successful)
- `"partial"` - Partial fill (counts as successful per AC#2)
- `"failed"` - Execution failed (counts as failed)
- `"pending"` - Not yet completed (exclude from counts)

**result_data JSON structure:**
```json
{
    "filled_size": "0.5",
    "fill_price": "2150.00",
    "is_test_mode": true,  // EXCLUDE these from counts
    "order_id": "mock-12345"
}
```

### Implementation Pattern for get_execution_stats

```python
async def get_execution_stats(
    self,
    user_id: int | None = None,
    period: TimePeriod = "today",
) -> ExecutionPeriodStats:
    """Get execution count and success rate for a period.

    Args:
        user_id: Optional filter by user
        period: Time period ("today", "this_week", "all_time")

    Returns:
        ExecutionPeriodStats with counts and success_rate
    """
    cache_key = f"exec:{user_id or 'all'}:{period}"

    # Check cache (reuse _is_cache_valid pattern)
    if self._is_cache_valid(cache_key):
        stats, _ = self._exec_cache[cache_key]
        return stats

    start_dt, end_dt = self._calculate_period_bounds(period)

    async with self._session_factory() as session:
        # Query all executions in period, excluding pending
        query = select(ExecutionModel).where(
            and_(
                ExecutionModel.status.in_(["filled", "partial", "failed"]),
                ExecutionModel.created_at >= start_dt,
                ExecutionModel.created_at <= end_dt,
            )
        )
        result = await session.execute(query)
        executions = result.scalars().all()

    # Count by status, excluding test mode
    successful = 0
    partial = 0
    failed = 0

    for exec in executions:
        # Parse result_data (same pattern as get_volume_stats)
        result_data = _parse_result_data(exec.result_data)

        # Exclude test mode
        if result_data.get("is_test_mode") in (True, "true"):
            continue

        if exec.status == "filled":
            successful += 1
        elif exec.status == "partial":
            partial += 1
        elif exec.status == "failed":
            failed += 1

    total = successful + partial + failed

    # Calculate success rate (AC#2, AC#3)
    if total == 0:
        success_rate = "N/A"
    else:
        rate = ((successful + partial) / total) * 100
        success_rate = f"{rate:.2f}%"

    return ExecutionPeriodStats(
        total=total,
        successful=successful,
        failed=failed,
        partial=partial,
        success_rate=success_rate,
    )
```

### Pydantic Models to Add (models.py)

```python
class ExecutionPeriodStats(BaseModel):
    """Execution statistics for a single time period (Story 5.3)."""

    total: int = Field(..., ge=0, description="Total executions")
    successful: int = Field(..., ge=0, description="Fully filled executions")
    failed: int = Field(..., ge=0, description="Failed executions")
    partial: int = Field(..., ge=0, description="Partial fills")
    success_rate: str = Field(..., description="Success rate as percentage or N/A")


class ExecutionStatsResponse(BaseModel):
    """Response for GET /api/stats/executions (Story 5.3: AC#1)."""

    today: ExecutionPeriodStats
    this_week: ExecutionPeriodStats
    all_time: ExecutionPeriodStats
    updated_at: datetime
```

### API Endpoint Implementation

**Add to existing api/stats.py:**
```python
@router.get("/api/stats/executions")
async def get_execution_stats(
    current_user: CurrentUser = Depends(get_current_user),
    stats_service: StatsService = Depends(get_stats_service),
) -> ExecutionStatsResponse:
    """Get execution count and success rate statistics (FR37, FR38)."""
    now = datetime.now(timezone.utc)

    today_stats = await stats_service.get_execution_stats(period="today")
    week_stats = await stats_service.get_execution_stats(period="this_week")
    all_time_stats = await stats_service.get_execution_stats(period="all_time")

    return ExecutionStatsResponse(
        today=today_stats,
        this_week=week_stats,
        all_time=all_time_stats,
        updated_at=now,
    )
```

### Testing Patterns

**Test File Location:** `tests/api/test_stats.py` (extend existing) and `tests/services/test_stats.py` (extend existing)

**Key Test Cases:**

```python
@pytest.mark.asyncio
async def test_execution_stats_correct_structure(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#1: Response has correct JSON structure."""
    response = await async_client.get(
        "/api/stats/executions",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "today" in data
    assert "this_week" in data
    assert "all_time" in data
    assert "updated_at" in data
    # Check period structure
    for period in ["today", "this_week", "all_time"]:
        assert "total" in data[period]
        assert "successful" in data[period]
        assert "failed" in data[period]
        assert "partial" in data[period]
        assert "success_rate" in data[period]


@pytest.mark.asyncio
async def test_success_rate_includes_partial(stats_service, db_session):
    """Test AC#2: Partial fills count as successful in rate calculation."""
    # Create: 8 filled, 2 partial, 1 failed = 11 total
    # Success rate = (8 + 2) / 11 * 100 = 90.91%
    ...


@pytest.mark.asyncio
async def test_zero_executions_returns_na(stats_service):
    """Test AC#3: Zero executions returns 'N/A' not error."""
    stats = await stats_service.get_execution_stats(period="today")
    assert stats.success_rate == "N/A"
    assert stats.total == 0


@pytest.mark.asyncio
async def test_excludes_test_mode(stats_service, db_session):
    """Test AC#4: Test mode executions excluded from counts."""
    # Create executions with is_test_mode=true
    # Verify they don't appear in counts
    ...
```

### Previous Story Intelligence

**From Story 5.1 (Stats Service):**
- StatsService class is fully implemented with caching
- Period bounds calculation uses UTC correctly
- Test mode exclusion pattern established: `result_data.get("is_test_mode") in (True, "true")`
- Cache invalidation works per-user or globally

**From Story 5.2 (Volume Endpoint):**
- API router pattern established in `api/stats.py`
- Authentication via `Depends(get_current_user)` works
- Service injection via `Depends(get_stats_service)` works
- Response formatting with datetime.isoformat() established

### Error Handling

- Return 401 if not authenticated (handled by `get_current_user` dependency)
- Return "N/A" for success_rate when total=0 (AC#3) - NOT an error
- Handle malformed result_data gracefully (skip execution, log warning)

### Project Structure Notes

**Files to Modify:**
- `src/kitkat/services/stats.py` - Add `get_execution_stats()` method
- `src/kitkat/api/stats.py` - Add `/api/stats/executions` endpoint
- `src/kitkat/models.py` - Add `ExecutionPeriodStats`, `ExecutionStatsResponse` models

**Test Files to Modify:**
- `tests/services/test_stats.py` - Add execution stats unit tests
- `tests/api/test_stats.py` - Add endpoint tests

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.3]
- [Source: _bmad-output/planning-artifacts/prd.md#FR37-FR38]
- [Source: _bmad-output/implementation-artifacts/5-1-stats-service-volume-tracking.md] - StatsService
- [Source: _bmad-output/implementation-artifacts/5-2-volume-display-today-week.md] - API pattern
- [Source: src/kitkat/services/stats.py] - Existing StatsService to extend
- [Source: src/kitkat/api/stats.py] - Existing stats router to extend
- [Source: _bmad-output/project-context.md] - Naming conventions, async patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Story 5.3 implementation was largely pre-existing from previous sessions
- Verified all core functionality: `get_execution_stats()` method, Pydantic models, API endpoint, and caching
- Added 6 missing API-level tests for `/api/stats/executions` endpoint:
  - `test_execution_stats_returns_correct_structure` (AC#1)
  - `test_execution_stats_period_has_all_fields` (AC#1)
  - `test_execution_stats_success_rate_format` (AC#1)
  - `test_execution_stats_requires_authentication` (Task 5.5)
  - `test_execution_stats_endpoint_registered` (endpoint registration)
  - `test_calls_service_for_each_period` (Task 5.6)
- All 61 stats-related tests pass (34 service tests + 27 API tests)
- Implementation satisfies all 4 Acceptance Criteria:
  - AC#1: GET /api/stats/executions returns today, this_week, all_time with correct structure
  - AC#2: success_rate = (successful + partial) / total * 100
  - AC#3: Zero executions returns "N/A" (no divide by zero)
  - AC#4: Test mode executions excluded from counts

### Debug Log References

None - implementation was straightforward with no debugging issues.

### File List

**Modified:**
- `tests/api/test_stats.py` - Added 6 API-level tests for execution stats endpoint (Story 5.3)

**Pre-existing (verified working):**
- `src/kitkat/services/stats.py` - Contains `get_execution_stats()` method (lines 357-470)
- `src/kitkat/api/stats.py` - Contains `GET /api/stats/executions` endpoint (lines 110-140)
- `src/kitkat/models.py` - Contains `ExecutionPeriodStats`, `ExecutionStatsResponse` models (lines 733-764)
- `tests/services/test_stats.py` - Contains service-level tests for execution stats

## Change Log

- 2026-02-02: Added API-level tests for /api/stats/executions endpoint, verified all implementation complete, marked story for review
