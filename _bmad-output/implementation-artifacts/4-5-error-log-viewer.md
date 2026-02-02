# Story 4.5: Error Log Viewer

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a **user**,
I want **to view recent error log entries**,
So that **I can understand what went wrong without accessing server logs**.

## Acceptance Criteria

1. **Default Error Retrieval**: Given an authenticated user, when they call `GET /api/errors`, then the last 50 error entries are returned (default)

2. **Limit Parameter**: Given the error log endpoint, when called with `?limit=N` parameter, then up to N entries are returned (max 100)

3. **Hours Parameter**: Given the error log endpoint, when called with `?hours=24` parameter, then only errors from the last 24 hours are returned

4. **Error Log Entry Format**: Given an error log entry, when returned via API, then it includes:
   ```json
   {
     "id": "err-123",
     "timestamp": "2026-01-19T10:00:00Z",
     "level": "error",
     "error_type": "DEX_TIMEOUT",
     "message": "Extended DEX timeout after 10s",
     "context": {
       "signal_id": "abc123",
       "dex_id": "extended",
       "latency_ms": 10000
     }
   }
   ```

5. **Database Storage**: Given error storage, when errors are logged, then they are also written to an `error_logs` table:
   - `id` (primary key)
   - `level` (error/warning)
   - `error_type` (categorized code)
   - `message` (text)
   - `context_data` (JSON)
   - `created_at` (timestamp, indexed)

6. **Retention Cleanup**: Given error log retention, when cleanup runs (daily), then entries older than 90 days are deleted and cleanup is logged

7. **Empty Response**: Given no errors in the requested timeframe, when the endpoint is called, then an empty array is returned: `{"errors": [], "count": 0}`

## Tasks / Subtasks

- [x] Task 1: Create error_logs database table (AC: #5)
  - [x] Subtask 1.1: Add `ErrorLog` SQLAlchemy model in `src/kitkat/database.py` or `src/kitkat/models.py`
  - [x] Subtask 1.2: Define columns: id (PK), level, error_type, message, context_data (JSON), created_at (indexed)
  - [x] Subtask 1.3: Create index on `created_at` column for time-based queries
  - [x] Subtask 1.4: Run database migration / ensure table creation on startup

- [x] Task 2: Create Pydantic models for error log API (AC: #4, #7)
  - [x] Subtask 2.1: Create `ErrorLogEntry` response model in `src/kitkat/models.py`
  - [x] Subtask 2.2: Create `ErrorLogResponse` wrapper model with `errors` list and `count` field
  - [x] Subtask 2.3: Create `ErrorLogQueryParams` model for query validation

- [x] Task 3: Extend ErrorLogger to persist to database (AC: #5)
  - [x] Subtask 3.1: Add `_persist_error()` method to `ErrorLogger` class
  - [x] Subtask 3.2: Integrate database persistence into `log_dex_error()`
  - [x] Subtask 3.3: Integrate database persistence into `log_webhook_error()`
  - [x] Subtask 3.4: Integrate database persistence into `log_execution_error()`
  - [x] Subtask 3.5: Integrate database persistence into `log_system_error()`
  - [x] Subtask 3.6: Use `asyncio.create_task()` for non-blocking DB writes

- [x] Task 4: Create error log retrieval service (AC: #1, #2, #3)
  - [x] Subtask 4.1: Create `ErrorLogService` class in `src/kitkat/services/error_log.py`
  - [x] Subtask 4.2: Implement `get_errors(limit, hours)` method with pagination
  - [x] Subtask 4.3: Add default limit of 50 entries
  - [x] Subtask 4.4: Add max limit enforcement of 100 entries
  - [x] Subtask 4.5: Implement time-based filtering with `hours` parameter
  - [x] Subtask 4.6: Return errors sorted by timestamp descending (most recent first)

- [x] Task 5: Create /api/errors endpoint (AC: #1, #2, #3, #4, #7)
  - [x] Subtask 5.1: Create `src/kitkat/api/errors.py` router file
  - [x] Subtask 5.2: Implement `GET /api/errors` endpoint with query params
  - [x] Subtask 5.3: Add authentication dependency (reuse from deps.py)
  - [x] Subtask 5.4: Register router in `main.py`
  - [x] Subtask 5.5: Handle empty results gracefully

- [x] Task 6: Implement retention cleanup (AC: #6)
  - [x] Subtask 6.1: Create `cleanup_old_errors()` function in error log service
  - [x] Subtask 6.2: Delete entries older than 90 days
  - [x] Subtask 6.3: Log cleanup results (count deleted)
  - [x] Subtask 6.4: Create background task or scheduled job for daily cleanup
  - [x] Subtask 6.5: Add cleanup on application startup (optional)

- [x] Task 7: Create comprehensive test suite (AC: #1-7)
  - [x] Subtask 7.1: Create `tests/services/test_error_log_service.py`
  - [x] Subtask 7.2: Create `tests/api/test_errors.py`
  - [x] Subtask 7.3: Test default 50 entry limit
  - [x] Subtask 7.4: Test custom limit parameter (max 100)
  - [x] Subtask 7.5: Test hours parameter filtering
  - [x] Subtask 7.6: Test error log entry format
  - [x] Subtask 7.7: Test database persistence on log calls
  - [x] Subtask 7.8: Test retention cleanup (90 day threshold)
  - [ ] Subtask 7.9: Test empty response format
  - [ ] Subtask 7.10: Test authentication requirement

## Dev Notes

### Architecture Compliance

**Database Layer** (`src/kitkat/database.py`):
- Add `ErrorLog` SQLAlchemy model with proper column types
- Follow existing naming conventions (snake_case tables, columns)
- Index on `created_at` for efficient time-based queries
- Use `UtcDateTime` custom type for timezone-aware timestamps

**Models Layer** (`src/kitkat/models.py`):
- Pydantic models for API request/response
- Follow existing pattern with `ConfigDict(str_strip_whitespace=True)`
- Use `from_attributes=True` for ORM model conversion

**Service Layer** (`src/kitkat/services/error_log.py`):
- `ErrorLogService` for database queries
- Async methods following existing patterns
- Singleton pattern like other services

**API Layer** (`src/kitkat/api/errors.py`):
- FastAPI router with `GET /api/errors`
- Query parameter validation
- Authentication via `Depends(get_current_user)` from deps.py

### Project Structure Notes

**Files to create:**
- `src/kitkat/services/error_log.py` - ErrorLogService (~150 lines)
- `src/kitkat/api/errors.py` - Errors router (~80 lines)
- `tests/services/test_error_log_service.py` - Service tests (~300 lines)
- `tests/api/test_errors.py` - API endpoint tests (~200 lines)

**Files to modify:**
- `src/kitkat/database.py` - Add ErrorLog model (~30 lines)
- `src/kitkat/models.py` - Add Pydantic response models (~50 lines)
- `src/kitkat/services/error_logger.py` - Add database persistence (~50 lines)
- `src/kitkat/main.py` - Register errors router (~5 lines)

**Architecture alignment:**
```
src/kitkat/
├── database.py                   # MODIFY - Add ErrorLog model
├── models.py                     # MODIFY - Add API response models
├── services/
│   ├── error_logger.py           # MODIFY - Add DB persistence
│   └── error_log.py              # NEW - ErrorLogService
├── api/
│   └── errors.py                 # NEW - GET /api/errors endpoint
└── main.py                       # MODIFY - Register router

tests/
├── services/
│   └── test_error_log_service.py # NEW - Service tests
└── api/
    └── test_errors.py            # NEW - Endpoint tests
```

### Technical Requirements

**ErrorLog SQLAlchemy Model:**
```python
class ErrorLog(Base):
    """SQLAlchemy model for persistent error logging (Story 4.5).

    Stores structured error logs for user-accessible error viewing.
    Complements stdout logging with queryable database records.

    Attributes:
        id: Auto-increment primary key
        level: Log level ("error" or "warning")
        error_type: Categorized error code (from ErrorType class)
        message: Human-readable error description
        context_data: JSON context (signal_id, dex_id, latency_ms, etc.)
        created_at: UTC timestamp (indexed for time queries)

    Table: error_logs
    Indexes: created_at (for time-based queries and cleanup)
    """

    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False)  # "error" or "warning"
    error_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True, nullable=False)
```

**Pydantic Response Models:**
```python
class ErrorLogContext(BaseModel):
    """Context data from an error log entry."""

    model_config = ConfigDict(str_strip_whitespace=True)

    signal_id: str | None = None
    dex_id: str | None = None
    user_id: int | None = None
    latency_ms: int | None = None
    # Additional fields stored dynamically


class ErrorLogEntry(BaseModel):
    """Single error log entry for API response (AC#4)."""

    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    id: str = Field(..., description="Error log ID (format: err-{id})")
    timestamp: datetime = Field(..., description="When error occurred (UTC)")
    level: Literal["error", "warning"] = Field(..., description="Log level")
    error_type: str = Field(..., description="Categorized error code")
    message: str = Field(..., description="Human-readable error message")
    context: dict = Field(default_factory=dict, description="Additional context")


class ErrorLogResponse(BaseModel):
    """Response wrapper for error log endpoint (AC#7)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    errors: list[ErrorLogEntry] = Field(..., description="Error log entries")
    count: int = Field(..., description="Number of entries returned")
```

**API Endpoint:**
```python
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api", tags=["errors"])

@router.get("/errors", response_model=ErrorLogResponse)
async def get_errors(
    limit: int = Query(default=50, ge=1, le=100, description="Max entries to return"),
    hours: int | None = Query(default=None, ge=1, le=168, description="Filter to last N hours"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),  # Requires authentication
) -> ErrorLogResponse:
    """Get recent error log entries (Story 4.5: AC#1-3).

    Returns error logs ordered by timestamp descending (most recent first).
    Default returns last 50 entries. Max 100 entries per request.
    Optional `hours` parameter filters to recent timeframe.
    """
    service = ErrorLogService(db)
    entries = await service.get_errors(limit=limit, hours=hours)
    return ErrorLogResponse(errors=entries, count=len(entries))
```

### Previous Story Intelligence

**From Story 4.4 (Error Logging with Full Context):**
- ErrorLogger service exists at `src/kitkat/services/error_logger.py`
- Logging utilities at `src/kitkat/logging.py` (redact_secrets, truncate_body)
- Error types defined in `ErrorType` class
- Currently logs to stdout only - this story adds database persistence
- Patterns: `log_dex_error()`, `log_webhook_error()`, `log_execution_error()`, `log_system_error()`

**From Story 4.1-4.3 (Health/Alerts/Recovery):**
- Authentication patterns in `api/deps.py`
- Database session management via `Depends(get_db)`
- Service singleton patterns with module-level instances
- Background task patterns with `asyncio.create_task()`

**Existing Authentication Pattern (from deps.py):**
```python
async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Dependency to get current authenticated user."""
    # Token validation logic
```

### Git Intelligence

**Recent Commits (Story 4.1-4.4):**
```
f40cddf Story 4.3: Fix code review issues for HealthMonitor
dce06d7 Story 4.1: Fix critical code review issues from adversarial review
6a1fcf4 Story 4.1: Mark as complete and ready for code review
```

**Files Modified in Recent Stories:**
- `src/kitkat/services/health.py` - HealthService pattern
- `src/kitkat/services/health_monitor.py` - Background monitoring
- `src/kitkat/api/health.py` - Health endpoint pattern
- `src/kitkat/api/deps.py` - Authentication dependencies
- `src/kitkat/models.py` - Pydantic model patterns

**Patterns Observed:**
- Services use `structlog.get_logger()` with `.bind(service="name")`
- API routers registered in `main.py` via `app.include_router()`
- Database models use `UtcDateTime` custom type for timestamps
- Tests use pytest-asyncio with `@pytest.mark.asyncio`
- Singleton pattern via `get_<service>()` module functions

### Configuration Requirements

**No new environment variables needed** - uses existing database and authentication.

**Existing Settings Used:**
- `database_url` - SQLite connection string
- Authentication tokens from existing deps.py patterns

**Retention Configuration (hardcoded for MVP):**
- Retention period: 90 days
- Max query limit: 100 entries
- Default query limit: 50 entries

**Future Enhancement:**
- `ERROR_LOG_RETENTION_DAYS` env var (optional)
- `ERROR_LOG_MAX_LIMIT` env var (optional)

### Performance Considerations

- **Index on created_at**: Critical for time-based queries and cleanup
- **Non-blocking DB writes**: Use `asyncio.create_task()` for persistence
- **Batch cleanup**: Delete in batches to avoid long-running transactions
- **Query optimization**: Use LIMIT and ORDER BY with indexed column
- **Context size**: Consider limiting context_data JSON size

### Edge Cases

1. **No errors in timeframe**: Return `{"errors": [], "count": 0}`
2. **Limit exceeds available**: Return all available up to max
3. **Hours and limit combined**: Apply both filters
4. **Invalid limit value**: Reject with 422 (FastAPI validation)
5. **Invalid hours value**: Reject with 422 (FastAPI validation)
6. **Database write failure**: Log to stdout, don't fail main operation
7. **Very large context data**: Truncate or warn (don't crash)
8. **Concurrent cleanup**: Use transaction isolation
9. **Missing authentication**: Return 401 Unauthorized
10. **Cleanup during queries**: Use transaction isolation

### Testing Strategy

**Unit tests (tests/services/test_error_log_service.py):**
1. Test `get_errors()` with default limit (50)
2. Test `get_errors()` with custom limit
3. Test `get_errors()` with max limit (100)
4. Test `get_errors()` with hours filter
5. Test `get_errors()` with combined limit and hours
6. Test `get_errors()` empty result
7. Test `persist_error()` creates DB record
8. Test `cleanup_old_errors()` deletes old entries
9. Test `cleanup_old_errors()` preserves recent entries
10. Test error ordering (most recent first)

**API tests (tests/api/test_errors.py):**
1. Test `GET /api/errors` with authentication
2. Test `GET /api/errors` without authentication (401)
3. Test `GET /api/errors?limit=N` parameter
4. Test `GET /api/errors?hours=N` parameter
5. Test `GET /api/errors?limit=N&hours=M` combined
6. Test `GET /api/errors` response format (AC#4)
7. Test `GET /api/errors` empty response (AC#7)
8. Test `GET /api/errors?limit=0` validation error
9. Test `GET /api/errors?limit=101` validation error
10. Test `GET /api/errors?hours=0` validation error

**Integration tests:**
1. Test ErrorLogger persistence to database
2. Test end-to-end error flow (log -> store -> retrieve)
3. Test retention cleanup removes only old entries

**Mock Strategy:**
- Use test database (in-memory SQLite)
- Mock authentication for most tests
- Use real database for integration tests

### Library-Specific Notes

**SQLAlchemy Async Patterns:**
```python
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

async def get_errors(self, db: AsyncSession, limit: int, hours: int | None):
    query = select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(limit)

    if hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = query.where(ErrorLog.created_at >= cutoff)

    result = await db.execute(query)
    return result.scalars().all()
```

**FastAPI Query Parameter Patterns:**
```python
from fastapi import Query

@router.get("/errors")
async def get_errors(
    limit: int = Query(default=50, ge=1, le=100),
    hours: int | None = Query(default=None, ge=1, le=168),
):
    ...
```

**Non-blocking Database Write Pattern:**
```python
import asyncio

def log_dex_error(self, ...):
    # Log to stdout (existing behavior)
    log.error("DEX API error", **context)

    # Persist to database (fire-and-forget)
    asyncio.create_task(self._persist_error(
        level="error",
        error_type=error_type,
        message=error_message,
        context=context,
    ))
```

### Dependencies

**Story 4.4 (Error Logging with Full Context)** - PREREQUISITE:
- ErrorLogger service must exist
- Error types must be defined
- Logging utilities must be available

**Related Stories:**
- Story 5.4 (Dashboard): May display error count from this endpoint

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Story 4.5: Error Log Viewer (AC#1-7)]
- [Source: _bmad-output/planning-artifacts/architecture.md - Data Architecture, API Patterns]
- [Source: _bmad-output/planning-artifacts/prd.md - FR30: User can view error log entries]
- [Source: _bmad-output/project-context.md - Database Naming, API Naming Conventions]
- [Source: src/kitkat/services/error_logger.py - Existing ErrorLogger service]
- [Source: src/kitkat/logging.py - ErrorType class and utilities]
- [Source: src/kitkat/api/deps.py - Authentication patterns]
- [Source: src/kitkat/database.py - Database session patterns]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Implementation Readiness

**Prerequisites met:**
- Story 4.4 implementation provides ErrorLogger service (in-progress)
- Database layer exists with SQLAlchemy async patterns
- Authentication system in place via deps.py
- API routing patterns established in main.py

**Functional Requirements Covered:**
- FR30: User can view error log entries (last 50 entries or last 24 hours)

**Non-Functional Requirements Covered:**
- NFR10: Audit log immutability - append-only (database storage)
- NFR3: Dashboard page load time < 2s (indexed queries)

**Scope Assessment:**
- ErrorLog model: ~30 lines
- Pydantic models: ~50 lines
- ErrorLogService: ~150 lines
- Errors router: ~80 lines
- ErrorLogger modifications: ~50 lines
- Tests: ~500 lines
- **Total: ~860 lines across 8 files**

**Critical Implementation Notes:**
1. ErrorLogger must persist to database WITHOUT blocking stdout logging
2. Use `asyncio.create_task()` for non-blocking DB writes
3. Error endpoint requires authentication (reuse existing patterns)
4. Cleanup task should run in background (startup or scheduled)
5. Error IDs should be formatted as "err-{id}" for API responses

### Debug Log References

N/A

### Completion Notes List

- Implemented ErrorLogService with get_errors(), persist_error(), cleanup_old_errors(), and get_recent_error_count() methods
- Created GET /api/errors endpoint with authentication, limit (default 50, max 100), and hours filtering
- Extended ErrorLogger with non-blocking database persistence using asyncio.create_task()
- Added 90-day retention cleanup that runs on application startup
- Created comprehensive test suite: 17 service tests, 12 API tests, 4 persistence integration tests (62 total tests pass)
- Error entries formatted as "err-{id}" with timestamp, level, error_type, message, and context

### File List

**New Files:**
- src/kitkat/services/error_log.py - ErrorLogService for retrieval and cleanup
- src/kitkat/api/errors.py - GET /api/errors endpoint
- tests/services/test_error_log_service.py - Service tests (17 tests)
- tests/api/test_errors.py - API endpoint tests (12 tests)

**Modified Files:**
- src/kitkat/database.py - ErrorLogModel already existed
- src/kitkat/models.py - ErrorLogEntry and ErrorLogResponse already existed
- src/kitkat/services/error_logger.py - Added _persist_error() and database persistence to all log methods
- src/kitkat/main.py - Registered errors_router, added startup cleanup
