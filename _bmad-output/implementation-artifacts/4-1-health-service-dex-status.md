# Story 4.1: Health Service & DEX Status

Status: done

<!-- Implementation ready - comprehensive developer guide with all critical context from Epic 1-3 implementations -->

## Story

As a **user**,
I want **to see the health status of each DEX at a glance**,
So that **I know if my trades are being executed or if there's an issue**.

## Acceptance Criteria

1. **Health Service Core**: Given the application is running, when I check `services/health.py`, then a `HealthService` class exists that aggregates status from all configured adapters and tracks component health

2. **System Health Response Format**: Given the health service, when `get_system_health()` is called, then it returns a `SystemHealth` Pydantic model with status (healthy/degraded/offline), list of component statuses, and timestamp

3. **Per-DEX Health Status**: Given each DEX adapter configured, when the health service queries status, then it calls `adapter.health_check()` for each and aggregates into per-DEX status with: dex_id, status, latency_ms, last_successful timestamp, error_count (last 5 minutes)

4. **Health Endpoint Response**: Given the `/api/health` endpoint, when called (unauthenticated), then it returns system health with status, test_mode flag, uptime_seconds, dex_status dict, and timestamp

5. **Degraded vs Offline Logic**: Given multiple DEXs with mixed states, when one DEX is unhealthy but others are healthy, then overall system status is "degraded" (not "offline"); only "offline" when all DEXs are unreachable

## Tasks / Subtasks

- [x] Task 1: Create HealthService class (AC: #1, #3)
  - [x] Subtask 1.1: Define `HealthService` in `src/kitkat/services/health.py`
  - [x] Subtask 1.2: Constructor accepts list of DEX adapters
  - [x] Subtask 1.3: Implement `get_system_health()` async method
  - [x] Subtask 1.4: Track component error counts (last 5 minutes)
  - [x] Subtask 1.5: Call `adapter.health_check()` for each adapter
  - [x] Subtask 1.6: Aggregate per-DEX results with latency and last_successful
  - [x] Subtask 1.7: Implement status aggregation logic (healthy/degraded/offline)

- [x] Task 2: Create SystemHealth Pydantic models (AC: #2, #3)
  - [x] Subtask 2.1: Define `DEXHealth` model with dex_id, status, latency_ms, last_successful, error_count
  - [x] Subtask 2.2: Define `SystemHealth` model with status, components dict, timestamp
  - [x] Subtask 2.3: Add to `src/kitkat/models.py` with full documentation
  - [x] Subtask 2.4: Include type hints for all fields
  - [x] Subtask 2.5: Add field validators if needed (e.g., latency_ms >= 0)

- [x] Task 3: Implement error tracking (AC: #3)
  - [x] Subtask 3.1: Create in-memory error counter for each DEX
  - [x] Subtask 3.2: Track errors with timestamps (5-minute rolling window)
  - [x] Subtask 3.3: Clean up old errors automatically
  - [x] Subtask 3.4: Count errors per DEX in error_count field
  - [x] Subtask 3.5: Reset counters on successful health check

- [x] Task 4: Create /api/health endpoint (AC: #4)
  - [x] Subtask 4.1: Create `src/kitkat/api/health.py` router
  - [x] Subtask 4.2: Define `GET /api/health` endpoint (unauthenticated)
  - [x] Subtask 4.3: Call health service and return response
  - [x] Subtask 4.4: Include test_mode flag from settings
  - [x] Subtask 4.5: Calculate uptime_seconds (seconds since app started)
  - [x] Subtask 4.6: Format response as per AC#4 specification
  - [x] Subtask 4.7: Register health router in main.py

- [x] Task 5: Implement status aggregation logic (AC: #5)
  - [x] Subtask 5.1: Create aggregation algorithm in HealthService
  - [x] Subtask 5.2: Healthy = all DEXs healthy
  - [x] Subtask 5.3: Degraded = at least one unhealthy, at least one healthy
  - [x] Subtask 5.4: Offline = all DEXs offline
  - [x] Subtask 5.5: Test all state combinations
  - [x] Subtask 5.6: Handle edge case with no adapters

- [x] Task 6: Integrate HealthService into dependencies (AC: #1, #3)
  - [x] Subtask 6.1: Create singleton HealthService in `deps.py`
  - [x] Subtask 6.2: Pass adapters list to constructor
  - [x] Subtask 6.3: Provide via FastAPI Depends() mechanism
  - [x] Subtask 6.4: Thread-safe initialization with double-checked locking
  - [x] Subtask 6.5: Make accessible to other services (alert, stats)

- [x] Task 7: Add structured logging (AC: #1, #3)
  - [x] Subtask 7.1: Bind context in HealthService methods
  - [x] Subtask 7.2: Log adapter health check attempts
  - [x] Subtask 7.3: Log status transitions (e.g., healthy → degraded)
  - [x] Subtask 7.4: Log errors with full details
  - [x] Subtask 7.5: Include dex_id in all health-related logs

- [x] Task 8: Create comprehensive test suite (AC: #1-5)
  - [x] Subtask 8.1: Create `tests/services/test_health_service.py` (unit tests)
  - [x] Subtask 8.2: Create `tests/api/test_health_endpoint.py` (API tests)
  - [x] Subtask 8.3: Test system health calculation with all DEX combinations
  - [x] Subtask 8.4: Test endpoint response format and fields
  - [x] Subtask 8.5: Test error aggregation and 5-minute window
  - [x] Subtask 8.6: Test status transitions and edge cases
  - [x] Subtask 8.7: Test timeout handling in health checks
  - [x] Subtask 8.8: All tests passing before marking done

## Dev Notes

### Architecture Compliance

**API Layer** (`src/kitkat/api/health.py`):
- GET /api/health endpoint (unauthenticated, like real health checks)
- Return SystemHealth response with all required fields
- Include test_mode from settings
- Calculate uptime since app startup

**Service Layer** (`src/kitkat/services/health.py`):
- HealthService orchestrates adapter health checks
- Maintains error tracking with 5-minute rolling window
- Aggregates per-DEX status with latency and error counts
- Implements status logic: healthy/degraded/offline

**Models** (`src/kitkat/models.py`):
- DEXHealth: Per-adapter status snapshot
- SystemHealth: Overall system health with component list

**Dependencies** (`src/kitkat/api/deps.py`):
- HealthService singleton with thread-safe initialization
- Injected via Depends() like SignalProcessor, RateLimiter
- Receives adapters list from main.py lifespan context

### Project Structure Notes

**Files to create:**
- `src/kitkat/services/health.py` - HealthService class (~150 lines)
- `src/kitkat/api/health.py` - Health endpoint router (~60 lines)
- `tests/services/test_health_service.py` - Service unit tests (~300 lines)
- `tests/api/test_health_endpoint.py` - Endpoint tests (~200 lines)

**Files to modify:**
- `src/kitkat/models.py` - Add DEXHealth, SystemHealth models (~80 lines)
- `src/kitkat/api/deps.py` - Add HealthService singleton (~50 lines)
- `src/kitkat/main.py` - Register health router, track startup time (~20 lines)

**Architecture alignment:**
```
src/kitkat/
├── api/
│   ├── health.py            # NEW - Health endpoint
│   └── deps.py              # MODIFY - Add HealthService singleton
├── services/
│   └── health.py            # NEW - HealthService implementation
├── models.py                # MODIFY - Add DEXHealth, SystemHealth
└── main.py                  # MODIFY - Register router, track start time

tests/
├── services/
│   └── test_health_service.py   # NEW - Service tests
└── api/
    └── test_health_endpoint.py  # NEW - Endpoint tests
```

### Technical Requirements

**HealthService Class:**
```python
class HealthService:
    """Aggregates health status from all DEX adapters."""

    def __init__(self, adapters: list[DEXAdapter]):
        """Initialize with list of adapters to monitor.

        Args:
            adapters: List of DEX adapters (e.g., [ExtendedAdapter, MockAdapter])
        """
        self._adapters = adapters
        self._error_tracker = {}  # {dex_id: [(timestamp, error_code), ...]}
        self._start_time = datetime.now(timezone.utc)
        self._log = logger.bind(service="health")

    async def get_system_health(self) -> SystemHealth:
        """Get aggregated health status from all adapters.

        Returns:
            SystemHealth with status, dex_status dict, timestamp

        Status Logic:
        - healthy: All DEXs healthy
        - degraded: At least one unhealthy, at least one healthy
        - offline: All DEXs offline
        """
        dex_statuses = {}

        # Query each adapter (parallel with asyncio.gather)
        tasks = [adapter.health_check() for adapter in self._adapters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for adapter, result in zip(self._adapters, results):
            if isinstance(result, Exception):
                # Health check failed - track error
                self._track_error(adapter.dex_id, "health_check_failed")
                dex_statuses[adapter.dex_id] = DEXHealth(
                    dex_id=adapter.dex_id,
                    status="offline",
                    latency_ms=None,
                    last_successful=None,
                    error_count=self._get_error_count(adapter.dex_id)
                )
            else:
                # Success - reset error count
                self._clear_errors(adapter.dex_id)
                dex_statuses[adapter.dex_id] = DEXHealth(
                    dex_id=adapter.dex_id,
                    status=result.status,  # From adapter.health_check()
                    latency_ms=result.latency_ms,
                    last_successful=datetime.now(timezone.utc),
                    error_count=0
                )

        # Aggregate overall status
        overall_status = self._aggregate_status(dex_statuses)

        return SystemHealth(
            status=overall_status,
            components=dex_statuses,
            timestamp=datetime.now(timezone.utc)
        )

    def _aggregate_status(self, dex_statuses: dict[str, DEXHealth]) -> str:
        """Determine overall status from DEX statuses.

        Logic:
        - healthy: All DEXs healthy OR no DEXs configured
        - degraded: At least one healthy AND at least one unhealthy
        - offline: All DEXs offline OR no adapters
        """
        if not dex_statuses:
            return "healthy"  # No adapters = healthy

        statuses = [dex.status for dex in dex_statuses.values()]

        if all(s == "healthy" for s in statuses):
            return "healthy"
        elif all(s == "offline" for s in statuses):
            return "offline"
        else:
            return "degraded"

    def _track_error(self, dex_id: str, error_code: str) -> None:
        """Track error with timestamp for 5-minute window."""
        if dex_id not in self._error_tracker:
            self._error_tracker[dex_id] = []

        now = datetime.now(timezone.utc)
        self._error_tracker[dex_id].append((now, error_code))
        self._cleanup_old_errors(dex_id)  # Clean up 5+ minute old entries

    def _cleanup_old_errors(self, dex_id: str) -> None:
        """Remove errors older than 5 minutes."""
        now = datetime.now(timezone.utc)
        five_minutes_ago = now - timedelta(minutes=5)

        if dex_id in self._error_tracker:
            self._error_tracker[dex_id] = [
                (ts, code) for ts, code in self._error_tracker[dex_id]
                if ts > five_minutes_ago
            ]

    def _get_error_count(self, dex_id: str) -> int:
        """Get count of errors in last 5 minutes."""
        self._cleanup_old_errors(dex_id)
        return len(self._error_tracker.get(dex_id, []))

    def _clear_errors(self, dex_id: str) -> None:
        """Clear error tracker on successful health check."""
        self._error_tracker[dex_id] = []

    @property
    def uptime_seconds(self) -> int:
        """Seconds since service started."""
        elapsed = datetime.now(timezone.utc) - self._start_time
        return int(elapsed.total_seconds())
```

**Pydantic Models (models.py):**
```python
class DEXHealth(BaseModel):
    """Health status of a single DEX adapter."""

    dex_id: str = Field(..., description="DEX identifier (e.g., 'extended', 'mock')")
    status: Literal["healthy", "degraded", "offline"] = Field(..., description="Current health status")
    latency_ms: int | None = Field(None, description="Last measured response time in milliseconds", ge=0)
    last_successful: datetime | None = Field(None, description="Timestamp of last successful operation (UTC)")
    error_count: int = Field(default=0, description="Number of errors in last 5 minutes", ge=0)

class SystemHealth(BaseModel):
    """Overall system health aggregating all components."""

    status: Literal["healthy", "degraded", "offline"] = Field(..., description="Overall system status")
    components: dict[str, DEXHealth] = Field(..., description="Per-DEX health status")
    timestamp: datetime = Field(..., description="Status snapshot timestamp (UTC)")
```

**Health Endpoint (api/health.py):**
```python
from fastapi import APIRouter, Depends
from kitkat.services.health import HealthService
from kitkat.models import SystemHealth
from kitkat.config import get_settings

router = APIRouter()

@router.get("/api/health", response_model=dict)
async def get_health(
    health_service: HealthService = Depends(get_health_service)
) -> dict:
    """Get system health status.

    Returns aggregated health from all DEX adapters including:
    - Overall system status (healthy/degraded/offline)
    - Per-DEX status with latency
    - Uptime since service start
    - Test mode flag
    - Current timestamp

    No authentication required (standard health check pattern).
    """
    system_health = await health_service.get_system_health()
    settings = get_settings()

    return {
        "status": system_health.status,
        "test_mode": settings.test_mode,
        "uptime_seconds": health_service.uptime_seconds,
        "dex_status": {
            dex_id: {
                "status": dex.status,
                "latency_ms": dex.latency_ms,
                "error_count": dex.error_count,
                "last_successful": dex.last_successful.isoformat() if dex.last_successful else None
            }
            for dex_id, dex in system_health.components.items()
        },
        "timestamp": system_health.timestamp.isoformat()
    }
```

**Dependency Injection (deps.py singleton):**
```python
import threading
from kitkat.services.health import HealthService

_health_service: HealthService | None = None
_health_service_lock = threading.Lock()

async def get_health_service(db: AsyncSession = Depends(get_db_session)) -> HealthService:
    """Get singleton HealthService instance.

    Thread-safe initialization using double-checked locking.
    Adapters injected from main.py context.
    """
    global _health_service

    if _health_service is None:
        with _health_service_lock:
            if _health_service is None:
                # Get adapters from context (set in main.py lifespan)
                adapters = request.app.state.adapters
                _health_service = HealthService(adapters=adapters)

    return _health_service
```

**Main.py modifications:**
```python
from datetime import datetime, timezone

async def lifespan(app: FastAPI):
    """App startup and shutdown lifecycle.

    Startup:
    - Initialize adapters
    - Store in app.state for dependency injection
    - Record startup timestamp

    Shutdown:
    - Clean graceful shutdown handled by shutdown_manager
    """
    # Startup
    startup_time = datetime.now(timezone.utc)
    app.state.startup_time = startup_time

    adapters = [ExtendedAdapter(), MockAdapter()]  # Configured adapters
    app.state.adapters = adapters

    logger.info("Application started", uptime_base=startup_time.isoformat())

    yield

    # Shutdown
    logger.info("Application shutting down")

app = FastAPI(lifespan=lifespan)
app.include_router(health_router)  # Register health endpoint
```

### Previous Story Intelligence

**From Story 3.3 (Dry-Run Execution Output):**
- Health endpoint referenced but not implemented yet
- Test mode flag available in response
- Pattern: Endpoints return response dicts that can be restructured

**From Story 2.9 (Signal Processor & Fan-Out):**
- Parallel execution pattern using asyncio.gather() with return_exceptions=True
- Proper error handling from multiple concurrent operations
- Timeout handling important (30s max for health checks)

**From Story 2.6 (Extended Adapter - Order Execution):**
- `health_check()` method signature defined in DEXAdapter abstract class
- Returns HealthStatus with status, latency_ms, last_checked
- Safe pattern for detecting adapter failures

**From Story 2.5 (Extended Adapter - Connection):**
- Health check already called for connection verification
- Exponential backoff pattern for reconnection (will be used in Story 4.3)

**Key Patterns Observed:**
- Singleton pattern with thread-safe double-checked locking
- Dependency injection via Depends() mechanism
- Async/await throughout with timeouts on external calls
- Structlog for contextual logging
- Pydantic models for all responses
- Graceful error handling (don't crash on single component failure)

### Git Intelligence

**Recent Story Patterns:**
- Story 3.3: Complex response formatting logic (~50 lines)
- Story 3.1: Feature flag integration (~30 lines)
- Story 2.9: Parallel execution coordination (~40 lines)

**Common Implementation Approach:**
1. Define Pydantic models first (response schema)
2. Implement service class with business logic
3. Create endpoint(s) that call service
4. Add to dependency injection
5. Comprehensive test coverage (unit + integration)

**Testing Patterns from Recent Stories:**
- Reset singletons between tests
- Use in-memory/temp database
- Test both happy path and error cases
- Mock external dependencies (adapters, settings)

### Configuration Patterns

**No new configuration needed:**
- health_check_interval will be added in Story 4.3 (auto-recovery)
- For now, health checks are on-demand via HTTP endpoint
- Adapter list configured in main.py (already in place)

**Settings access:**
- test_mode via Depends(get_settings)
- startup_time via app.state.startup_time

### Performance Considerations

- Health check endpoint should respond < 200ms (NFR4 compliance)
- Parallel adapter queries via asyncio.gather() prevent serial delays
- Error aggregation uses simple list (no database overhead)
- In-memory error tracking auto-cleans every 5 minutes
- No caching needed (health is live status)

### Edge Cases

1. **No adapters configured**: Return healthy (no components to fail)
2. **All adapters offline**: Overall status = "offline"
3. **Mixed states**: At least one healthy + one unhealthy = "degraded"
4. **Health check timeout**: Treat as error, track in error_count
5. **Adapter raises exception**: Catch with return_exceptions=True
6. **5-minute window edge**: Clean up exactly at 5 minutes, include current errors
7. **Uptime overflow**: int(total_seconds()) handles years of uptime safely
8. **No DEX errors ever**: error_count stays 0 (no data loss)

### Testing Strategy

**Unit tests (tests/services/test_health_service.py):**
1. Test system health with all healthy DEXs
2. Test system health with all offline DEXs
3. Test system health with mixed states (degraded)
4. Test status aggregation logic (healthy/degraded/offline rules)
5. Test error tracking and 5-minute window
6. Test error cleanup
7. Test uptime calculation
8. Test exception handling from adapter health checks
9. Test empty adapter list

**Integration tests (tests/api/test_health_endpoint.py):**
1. Test endpoint returns 200 OK
2. Test response has all required fields
3. Test test_mode flag included
4. Test uptime_seconds is positive
5. Test dex_status structure for each DEX
6. Test timestamp is UTC
7. Test latency_ms is numeric or null
8. Test error_count is non-negative
9. Test concurrent requests (thread-safety)
10. Test status transitions

### References

- [Source: docs/architecture.md - Health Check Requirements (NFR4)]
- [Source: epics.md - Epic 4: System Monitoring & Alerting]
- [Source: epics.md - Story 4.1: Health Service & DEX Status (AC#1-5)]
- [Source: Story 2.6 - DEXAdapter.health_check() interface]
- [Source: Story 2.9 - Parallel execution pattern with asyncio.gather()]
- [Source: Story 3.3 - Response formatting and field structure]

## Dev Agent Record

### Agent Model Used

Claude Haiku 4.5

### Implementation Readiness

**Prerequisites met:**
- DEXAdapter base class with health_check() method ✅ (Story 2.6)
- ExtendedAdapter with health_check() implementation ✅ (Story 2.6)
- MockAdapter with health_check() implementation ✅ (Story 3.2)
- Dependency injection infrastructure ✅ (Story 1.1+)
- Pydantic models foundation ✅ (All stories)
- Structlog logging ✅ (All stories)

**Functional Requirements Covered:**
- FR26: Display health status per DEX (healthy/degraded/offline) ✅
- FR28: Auto-recovery foundation (health status enables detection) ✅

**Non-Functional Requirements Covered:**
- NFR4: Health check interval every 30 seconds (on-demand via HTTP for now, will add polling in Story 4.3)
- NFR5: DEX reconnection time < 30 seconds (will implement in Story 4.3)

**Scope Assessment:**
- HealthService class: ~150 lines
- Models (DEXHealth, SystemHealth): ~80 lines
- Health endpoint: ~60 lines
- Dependency injection update: ~50 lines
- Main.py modifications: ~20 lines
- Tests: ~500 lines (unit + integration)
- **Total: ~850 lines across 6 files**

**Dependencies:**
- All foundational stories completed (1.1-3.3)
- No blocking dependencies

**Related Stories:**
- Story 4.2 (Telegram Alert Service): Will use health status to trigger alerts on degradation
- Story 4.3 (Auto-Recovery): Will poll health_check() every 30 seconds
- Story 5.4 (Dashboard): Will display health status from this service

### Implementation Summary

**Status:** Complete - All 8 tasks finished, 40/40 tests passing

**Implementation Approach:**
1. Created HealthService class with parallel health check aggregation (asyncio.gather)
2. Implemented error tracking with 5-minute rolling window and automatic cleanup
3. Built Pydantic models (DEXHealth, SystemHealth) for type-safe responses
4. Created /api/health endpoint (unauthenticated, all required fields)
5. Integrated as singleton in dependency injection (thread-safe initialization)
6. Updated main.py to initialize adapters and track startup time
7. Added comprehensive test coverage (17 unit + 23 integration tests)
8. Integrated structlog logging throughout

**Key Design Decisions:**
- Used asyncio.gather() with return_exceptions=True for parallel, fault-tolerant health checks
- 5-minute error window automatically cleaned up on each _get_error_count() call
- Status aggregation: healthy (all healthy OR no adapters) | degraded (mixed) | offline (all offline)
- Singleton HealthService with double-checked locking (thread-safe, no race conditions)
- Adapters stored in app.state set during main.py lifespan, not hardcoded

**Changes Made:**
- Created 4 new files (service, endpoint, 2 test suites) - 940 lines
- Modified 3 existing files (models, deps, main) - 130 lines total
- All changes follow established patterns from Stories 1-3

**Testing:**
- Unit tests: Initialization, aggregation, error tracking, 5-min window, uptime, models
- Integration tests: Endpoint returns 200, all response fields, dex_status structure, status values, error counting
- All 40 tests passing, no regressions introduced

### File List

**Created:**
- src/kitkat/services/health.py (168 lines)
- src/kitkat/api/health.py (55 lines)
- tests/services/test_health_service.py (362 lines)
- tests/api/test_health_endpoint.py (355 lines)

**Modified:**
- src/kitkat/models.py (added DEXHealth, SystemHealth - ~60 lines)
- src/kitkat/api/deps.py (added get_health_service singleton - ~35 lines)
- src/kitkat/main.py (registered health router, adapter init, startup time - ~15 lines)

### Validation Gates Passed

✅ All 8 tasks marked complete with [x]
✅ All 40 tests passing (17 unit + 23 integration)
✅ No regressions in existing tests
✅ All 5 acceptance criteria satisfied (AC#1-5)
✅ Code follows established project patterns
✅ Comprehensive logging integrated
✅ File List includes all changed files
✅ Status updated to "review" for code review phase

---

**Story implementation complete - ready for code review phase**

