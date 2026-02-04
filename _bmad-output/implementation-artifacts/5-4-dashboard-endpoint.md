# Story 5.4: Dashboard Endpoint

Status: done

## Story

As a **user**,
I want **a single dashboard endpoint with all key status information**,
So that **I can do a "glance and go" health check in 30 seconds**.

## Acceptance Criteria

1. **Given** an authenticated user, **When** they call `GET /api/dashboard`, **Then** the response includes all key information:
```json
{
  "status": "all_ok",
  "test_mode": false,
  "dex_status": {
    "extended": {"status": "healthy", "latency_ms": 45}
  },
  "volume_today": {
    "total_usd": "47250.00",
    "by_dex": {"extended": "47250.00"}
  },
  "executions_today": {
    "total": 14,
    "success_rate": "100.00%"
  },
  "recent_errors": 0,
  "onboarding_complete": true,
  "updated_at": "2026-01-19T10:00:00Z"
}
```

2. **Given** the "everything OK" indicator, **When** all conditions are met (All DEXs healthy, No errors in last hour, Onboarding complete), **Then** `status` is `"all_ok"`

3. **Given** any DEX is degraded or offline, **When** status is calculated, **Then** `status` is `"degraded"` or `"offline"`

4. **Given** errors occurred in the last hour, **When** status is calculated, **Then** `recent_errors` shows the count and `status` may still be `"all_ok"` if DEXs are healthy (errors are informational)

5. **Given** test mode is active, **When** dashboard is displayed, **Then** `test_mode: true` is prominently included and a `test_mode_warning` field contains: "No real trades - test mode active"

6. **Given** dashboard performance, **When** called, **Then** response time is < 200ms (NFR2 requires < 2s, we target much faster)

## Tasks / Subtasks

- [x] Task 1: Create dashboard endpoint in API (AC: #1, #6)
  - [x] 1.1 Add `GET /api/dashboard` endpoint to `api/stats.py` (alongside existing volume/execution endpoints)
  - [x] 1.2 Use `Depends(get_current_user)` for authentication
  - [x] 1.3 Inject `StatsService`, `HealthService` via dependencies
  - [x] 1.4 Return response matching AC#1 JSON structure

- [x] Task 2: Create Pydantic response models (AC: #1)
  - [x] 2.1 Add `DashboardDexStatus` model with: status, latency_ms
  - [x] 2.2 Add `DashboardVolumeToday` model with: total_usd, by_dex
  - [x] 2.3 Add `DashboardExecutionsToday` model with: total, success_rate
  - [x] 2.4 Add `DashboardResponse` model with all fields from AC#1

- [x] Task 3: Implement overall status calculation (AC: #2, #3)
  - [x] 3.1 Check all DEX health statuses from `health_service.get_system_health()`
  - [x] 3.2 If all DEXs "healthy" AND no errors in last hour AND onboarding complete → `"all_ok"`
  - [x] 3.3 If any DEX "degraded" → overall status `"degraded"`
  - [x] 3.4 If any DEX "offline" → overall status `"offline"`
  - [x] 3.5 Implement status priority: offline > degraded > all_ok

- [x] Task 4: Implement recent errors count (AC: #4)
  - [x] 4.1 Query error_logs table for entries in last 60 minutes
  - [x] 4.2 Count errors (level = "error") only, not warnings
  - [x] 4.3 Add method to StatsService or create helper: `get_recent_error_count(minutes: int = 60)`

- [x] Task 5: Implement onboarding status check (AC: #2)
  - [x] 5.1 For MVP, implement simple check: onboarding_complete = True if user exists with connected wallet
  - [x] 5.2 Full onboarding checklist to be implemented in Story 5.5 (just use placeholder for now)

- [x] Task 6: Implement test mode handling (AC: #5)
  - [x] 6.1 Read `test_mode` from settings via `get_settings()`
  - [x] 6.2 If `test_mode: true`, add `test_mode_warning` field with message

- [x] Task 7: Aggregate volume and execution stats (AC: #1)
  - [x] 7.1 Get today's volume using `stats_service.get_aggregated_volume_stats(period="today")`
  - [x] 7.2 Get today's execution stats using `stats_service.get_execution_stats(period="today")`
  - [x] 7.3 Format volume with per-DEX breakdown

- [x] Task 8: Write comprehensive tests
  - [x] 8.1 Test endpoint returns correct JSON structure (AC#1)
  - [x] 8.2 Test "all_ok" status when all conditions met (AC#2)
  - [x] 8.3 Test "degraded" status when DEX degraded (AC#3)
  - [x] 8.4 Test "offline" status when DEX offline (AC#3)
  - [x] 8.5 Test recent_errors count (AC#4)
  - [x] 8.6 Test test_mode_warning appears when test mode active (AC#5)
  - [x] 8.7 Test authentication required (401 without valid session)
  - [x] 8.8 Test response time < 200ms with mock services

## Dev Notes

### Architecture Patterns (MUST FOLLOW)

**From Project Context:**
- **File Location**: Add endpoint to existing `src/kitkat/api/stats.py`
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Use absolute imports from `kitkat.*` package
- **Async**: ALL database operations must be async
- **Logging**: Use `structlog.get_logger()` with bound context

**CRITICAL: Extend existing files, do NOT create new ones:**
- `api/stats.py` - Add dashboard endpoint to existing router
- `models.py` - Add DashboardResponse model alongside existing models

### Existing Services to Reuse (MUST USE)

**HealthService (services/health.py):**
```python
# Already implemented in Story 4.1
async def get_system_health() -> SystemHealth
# Returns: SystemHealth with status, components dict, timestamp

# SystemHealth.status is one of: "healthy", "degraded", "offline"
# SystemHealth.components is dict[str, HealthStatus] for each DEX
```

**StatsService (services/stats.py):**
```python
# Already implemented in Stories 5.1, 5.2, 5.3
async def get_volume_stats(user_id, dex_id, period) -> VolumeStats
async def get_aggregated_volume_stats(user_id, period) -> AggregatedVolumeStats
async def get_execution_stats(user_id, period) -> ExecutionPeriodStats
```

**Dependencies (api/deps.py):**
```python
# Already implemented
get_current_user() -> CurrentUser  # Auth dependency
get_stats_service() -> StatsService  # Stats singleton
get_health_service() -> HealthService  # Health singleton
```

### Dashboard Status Logic (AC#2, AC#3)

**Status Priority (highest to lowest):**
1. `"offline"` - Any DEX is offline
2. `"degraded"` - Any DEX is degraded (but none offline)
3. `"all_ok"` - All DEXs healthy AND no errors AND onboarding complete

**Implementation:**
```python
def _calculate_dashboard_status(
    system_health: SystemHealth,
    recent_errors: int,
    onboarding_complete: bool,
) -> str:
    """Calculate overall dashboard status.

    Priority: offline > degraded > all_ok
    """
    # Check for offline first (highest priority)
    for dex_status in system_health.components.values():
        if dex_status.status == "offline":
            return "offline"

    # Check for degraded
    for dex_status in system_health.components.values():
        if dex_status.status == "degraded":
            return "degraded"

    # All DEXs are healthy - check other conditions
    # Note: errors are informational, don't affect status if DEXs healthy (AC#4)
    return "all_ok"
```

### Recent Errors Count (AC#4)

**Query error_logs table (if exists, otherwise use logging approach):**
```python
async def get_recent_error_count(self, minutes: int = 60) -> int:
    """Count errors in the last N minutes.

    Note: If error_logs table doesn't exist yet (Story 4.4/4.5),
    return 0 as placeholder.
    """
    # Check if ErrorLog model exists
    try:
        from kitkat.database import ErrorLog
    except ImportError:
        # Story 4.4/4.5 not yet implemented
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    async with self._session_factory() as session:
        query = select(func.count()).select_from(ErrorLog).where(
            and_(
                ErrorLog.level == "error",
                ErrorLog.created_at >= cutoff,
            )
        )
        result = await session.execute(query)
        return result.scalar() or 0
```

**Alternative if error_logs not yet implemented:**
Check sprint status - Story 4.4 and 4.5 are `in-progress`. The error logging infrastructure may not be complete yet. In that case, return 0 for `recent_errors` as a placeholder.

### Onboarding Status (AC#2)

**For MVP (Story 5.5 implements full checklist):**
```python
# Simple check: user exists and has connected wallet
onboarding_complete = current_user is not None

# In Story 5.5, this will become:
# onboarding_complete = await onboarding_service.is_complete(user_id)
```

### Test Mode Handling (AC#5)

**From existing patterns in health.py:**
```python
from kitkat.config import get_settings

settings = get_settings()

response = {
    "test_mode": settings.test_mode,
    # ...
}

if settings.test_mode:
    response["test_mode_warning"] = "No real trades - test mode active"
```

### Pydantic Response Models

**Add to models.py:**
```python
class DashboardDexStatus(BaseModel):
    """DEX status for dashboard display."""
    status: Literal["healthy", "degraded", "offline"]
    latency_ms: int | None = None


class DashboardVolumeToday(BaseModel):
    """Today's volume stats for dashboard."""
    total_usd: str = Field(..., description="Total volume as formatted string")
    by_dex: dict[str, str] = Field(default_factory=dict, description="Volume per DEX")


class DashboardExecutionsToday(BaseModel):
    """Today's execution stats for dashboard."""
    total: int = Field(..., ge=0)
    success_rate: str = Field(..., description="Percentage or N/A")


class DashboardResponse(BaseModel):
    """Response for GET /api/dashboard endpoint (Story 5.4: AC#1).

    Aggregates all key status information for "glance and go" dashboard.
    """
    status: Literal["all_ok", "degraded", "offline"]
    test_mode: bool
    test_mode_warning: str | None = None
    dex_status: dict[str, DashboardDexStatus]
    volume_today: DashboardVolumeToday
    executions_today: DashboardExecutionsToday
    recent_errors: int = Field(..., ge=0)
    onboarding_complete: bool
    updated_at: datetime
```

### API Endpoint Implementation

**Add to api/stats.py:**
```python
@router.get("/api/dashboard")
async def get_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    stats_service: StatsService = Depends(get_stats_service),
    health_service: HealthService = Depends(get_health_service),
) -> DashboardResponse:
    """Get aggregated dashboard status for glance-and-go check (Story 5.4: AC#1).

    Combines health status, volume stats, execution stats, and error counts
    into a single response optimized for quick dashboard display.

    Args:
        current_user: Authenticated user (injected)
        stats_service: Stats service for volume/execution queries (injected)
        health_service: Health service for DEX status (injected)

    Returns:
        DashboardResponse with all key status information
    """
    now = datetime.now(timezone.utc)
    settings = get_settings()

    # Get health status
    system_health = await health_service.get_system_health()

    # Get today's volume (aggregated across all DEXs)
    volume_stats = await stats_service.get_aggregated_volume_stats(period="today")

    # Get today's execution stats
    exec_stats = await stats_service.get_execution_stats(period="today")

    # Get recent error count (last hour)
    recent_errors = await _get_recent_error_count(stats_service)

    # Onboarding check (simple for now, Story 5.5 implements full checklist)
    onboarding_complete = True  # Placeholder until Story 5.5

    # Calculate overall status
    status = _calculate_dashboard_status(
        system_health=system_health,
        recent_errors=recent_errors,
        onboarding_complete=onboarding_complete,
    )

    # Build DEX status dict
    dex_status = {
        dex_id: DashboardDexStatus(
            status=dex.status,
            latency_ms=dex.latency_ms,
        )
        for dex_id, dex in system_health.components.items()
    }

    # Build volume breakdown
    volume_today = DashboardVolumeToday(
        total_usd=f"{volume_stats.total_volume_usd:.2f}",
        by_dex={
            dex_id: f"{dex_stats.volume_usd:.2f}"
            for dex_id, dex_stats in volume_stats.by_dex.items()
        },
    )

    # Build execution stats
    executions_today = DashboardExecutionsToday(
        total=exec_stats.total,
        success_rate=exec_stats.success_rate,
    )

    # Build response
    response = DashboardResponse(
        status=status,
        test_mode=settings.test_mode,
        dex_status=dex_status,
        volume_today=volume_today,
        executions_today=executions_today,
        recent_errors=recent_errors,
        onboarding_complete=onboarding_complete,
        updated_at=now,
    )

    # Add test mode warning if active (AC#5)
    if settings.test_mode:
        response.test_mode_warning = "No real trades - test mode active"

    return response
```

### Testing Patterns

**Test File Location:** `tests/api/test_stats.py` (extend existing)

**Key Test Cases:**
```python
@pytest.mark.asyncio
async def test_dashboard_returns_correct_structure(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#1: Dashboard returns all required fields."""
    response = await async_client.get(
        "/api/dashboard",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all required fields present
    assert "status" in data
    assert "test_mode" in data
    assert "dex_status" in data
    assert "volume_today" in data
    assert "executions_today" in data
    assert "recent_errors" in data
    assert "onboarding_complete" in data
    assert "updated_at" in data

    # Verify nested structure
    assert "total_usd" in data["volume_today"]
    assert "by_dex" in data["volume_today"]
    assert "total" in data["executions_today"]
    assert "success_rate" in data["executions_today"]


@pytest.mark.asyncio
async def test_dashboard_status_all_ok_when_healthy(
    async_client: AsyncClient,
    authenticated_headers: dict,
    mock_healthy_dexs,
):
    """Test AC#2: Status is all_ok when all conditions met."""
    response = await async_client.get(
        "/api/dashboard",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "all_ok"


@pytest.mark.asyncio
async def test_dashboard_status_degraded_when_dex_degraded(
    async_client: AsyncClient,
    authenticated_headers: dict,
    mock_degraded_dex,
):
    """Test AC#3: Status is degraded when any DEX degraded."""
    response = await async_client.get(
        "/api/dashboard",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_dashboard_test_mode_warning(
    async_client: AsyncClient,
    authenticated_headers: dict,
    test_mode_enabled,
):
    """Test AC#5: Test mode warning appears when enabled."""
    response = await async_client.get(
        "/api/dashboard",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["test_mode"] is True
    assert data["test_mode_warning"] == "No real trades - test mode active"
```

### Previous Story Intelligence

**From Story 5.1 (Stats Service):**
- `get_aggregated_volume_stats()` returns `AggregatedVolumeStats` with `total_volume_usd`, `by_dex` dict
- Caching with 60s TTL reduces database load
- Test mode executions excluded automatically

**From Story 5.2/5.3 (Stats API):**
- API router pattern established with `Depends(get_current_user)`
- Response formatting with `datetime.isoformat()`
- Volume formatted as `f"{value:.2f}"` string

**From Story 4.1 (Health Service):**
- `get_system_health()` returns `SystemHealth` with status and components
- DEX status is `"healthy"`, `"degraded"`, or `"offline"`
- `health_service.uptime_seconds` available for additional info

### Error Handling

- Return 401 if not authenticated (handled by `get_current_user` dependency)
- If services fail, let exceptions propagate (FastAPI will return 500)
- For missing error_logs table, return 0 for recent_errors gracefully

### Project Structure Notes

**Files to Modify:**
- `src/kitkat/api/stats.py` - Add `/api/dashboard` endpoint
- `src/kitkat/models.py` - Add dashboard response models

**Test Files to Modify:**
- `tests/api/test_stats.py` - Add dashboard endpoint tests

### Performance Considerations (AC#6)

**Target: < 200ms response time**

- Reuse cached stats from StatsService (60s TTL)
- Health check is fast (in-memory adapter status)
- Single database query for error count (if implemented)
- Parallel async calls using `asyncio.gather()` if needed:

```python
# If performance becomes an issue, parallelize:
system_health, volume_stats, exec_stats = await asyncio.gather(
    health_service.get_system_health(),
    stats_service.get_aggregated_volume_stats(period="today"),
    stats_service.get_execution_stats(period="today"),
)
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.4]
- [Source: _bmad-output/planning-artifacts/prd.md#FR31-FR32] - Dashboard requirements
- [Source: _bmad-output/planning-artifacts/prd.md#NFR2] - Performance < 2s (we target 200ms)
- [Source: _bmad-output/implementation-artifacts/5-1-stats-service-volume-tracking.md] - StatsService
- [Source: _bmad-output/implementation-artifacts/5-2-volume-display-today-week.md] - Volume API pattern
- [Source: _bmad-output/implementation-artifacts/5-3-execution-count-success-rate.md] - Execution stats
- [Source: src/kitkat/api/stats.py] - Existing stats router to extend
- [Source: src/kitkat/api/health.py] - Health endpoint pattern reference
- [Source: src/kitkat/services/stats.py] - StatsService implementation
- [Source: src/kitkat/services/health.py] - HealthService implementation
- [Source: _bmad-output/project-context.md] - Naming conventions, async patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Story 5.4 implementation was pre-existing from previous sessions
- Verified all 8 tasks complete with 10 dashboard-specific tests passing:
  - `test_dashboard_returns_all_required_fields` (AC#1)
  - `test_status_all_ok_when_all_healthy` (AC#2)
  - `test_status_degraded_when_dex_degraded` (AC#3)
  - `test_status_offline_when_dex_offline` (AC#3)
  - `test_test_mode_warning_when_enabled` (AC#5)
  - `test_no_warning_when_test_mode_disabled` (AC#5)
  - `test_recent_errors_returns_count` (AC#4)
  - `test_dashboard_requires_authentication`
  - `test_dashboard_response_time_under_200ms` (AC#6)
  - `test_dashboard_endpoint_registered`
- Implementation satisfies all 6 Acceptance Criteria:
  - AC#1: GET /api/dashboard returns all key status information
  - AC#2: status is "all_ok" when all DEXs healthy
  - AC#3: status is "degraded"/"offline" when DEX status is degraded/offline
  - AC#4: recent_errors shows error count (returns 0 as placeholder until Story 4.4/4.5 complete)
  - AC#5: test_mode_warning appears when test mode active
  - AC#6: Response time < 200ms verified with mock services

### Debug Log References

None - implementation was verified working with no issues.

### File List

**Pre-existing (verified working):**
- `src/kitkat/api/stats.py` - Contains `GET /api/dashboard` endpoint (lines 168-251) and `_calculate_dashboard_status` helper (lines 143-165)
- `src/kitkat/models.py` - Contains `DashboardDexStatus`, `DashboardVolumeToday`, `DashboardExecutionsToday`, `DashboardResponse` models (lines 772-845)
- `tests/api/test_stats.py` - Contains 10 dashboard tests

## Change Log

- 2026-02-04: **Code Review PASSED** - No issues found, all ACs verified
- 2026-02-02: Verified all implementation complete, all 10 dashboard tests pass, marked story for review
