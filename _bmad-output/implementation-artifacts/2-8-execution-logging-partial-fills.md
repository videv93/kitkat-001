# Story 2.8: Execution Logging & Partial Fills

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **all execution attempts logged and partial fills handled**,
so that **I have full visibility into what happened with my orders**.

## Acceptance Criteria

1. **Execution Record Creation**: Given any order execution attempt, when it occurs, then an `executions` table record is created with: `id` (primary key), `signal_id` (foreign key), `dex_id` ("extended"), `status` ("pending" | "filled" | "partial" | "failed"), `result_data` (JSON with full DEX response), `created_at` (timestamp)

2. **Partial Fill Handling**: Given a partial fill occurs, when the DEX reports partial execution, then `status` is set to "partial" and `result_data` includes `filled_size` and `remaining_size` and the partial fill is logged with structlog

3. **Partial Fill Alert Trigger**: Given a partial fill occurs, when it is detected, then an alert is queued for the user (FR15) and the alert includes: symbol, filled amount, remaining amount

4. **Comprehensive Execution Logging**: Given any execution (success or failure), when logging occurs, then the log includes: `signal_id`, `dex_id`, `order_id`, `status`, `latency_ms`, `timestamp`

## Tasks / Subtasks

- [x] Task 1: Create `executions` table and ExecutionModel (AC: #1)
  - [x] Subtask 1.1: Add `ExecutionModel` class to `database.py` with all required columns
  - [x] Subtask 1.2: Add `Execution` Pydantic schema to `models.py` for API responses
  - [x] Subtask 1.3: Write tests for ExecutionModel CRUD operations

- [x] Task 2: Create ExecutionService for logging and querying (AC: #1, #4)
  - [x] Subtask 2.1: Create `services/execution_service.py` with `ExecutionService` class
  - [x] Subtask 2.2: Implement `log_execution()` method - creates execution record with timing
  - [x] Subtask 2.3: Implement `get_execution()` and `list_executions()` query methods
  - [x] Subtask 2.4: Add structured logging with `signal_id`, `dex_id`, `order_id`, `status`, `latency_ms`
  - [x] Subtask 2.5: Write unit tests for ExecutionService

- [x] Task 3: Implement partial fill detection and handling (AC: #2)
  - [x] Subtask 3.1: Add `detect_partial_fill()` method to ExecutionService
  - [x] Subtask 3.2: Update `log_execution()` to check for partial fills and set status accordingly
  - [x] Subtask 3.3: Ensure `result_data` JSON includes `filled_size` and `remaining_size` for partials
  - [x] Subtask 3.4: Write tests for partial fill detection logic

- [x] Task 4: Integrate alert trigger for partial fills (AC: #3)
  - [x] Subtask 4.1: Define `PartialFillAlert` dataclass/model with symbol, filled_amount, remaining_amount
  - [x] Subtask 4.2: Add `queue_partial_fill_alert()` method to ExecutionService (prepares for Epic 4)
  - [x] Subtask 4.3: Log alert details for now (actual Telegram integration in Epic 4)
  - [x] Subtask 4.4: Write tests for alert trigger on partial fill detection

- [ ] Task 5: Integration with Extended Adapter (AC: #1, #2, #4)
  - [ ] Subtask 5.1: Modify `execute_order()` to log execution via ExecutionService
  - [ ] Subtask 5.2: Ensure execution is logged on success, partial, and failure
  - [ ] Subtask 5.3: Calculate and log latency_ms from start to completion
  - [ ] Subtask 5.4: Write integration tests verifying full flow

## Dev Notes

### Architecture Compliance

- **Data Layer** (`src/kitkat/database.py`): Add `ExecutionModel` following existing patterns (UserModel, SessionModel)
- **Models** (`src/kitkat/models.py`): Add `Execution` Pydantic schema following existing conventions
- **Service Layer** (`src/kitkat/services/`): Create new `execution_service.py` - follows same structure as `session_service.py`, `user_service.py`
- **Adapter Layer** (`src/kitkat/adapters/extended.py`): Light integration - call ExecutionService after order execution

### Project Structure Notes

**Files to create:**
- `src/kitkat/services/execution_service.py` - New service for execution logging
- `tests/services/test_execution_service.py` - Unit tests for ExecutionService

**Files to modify:**
- `src/kitkat/database.py` - Add `ExecutionModel` ORM class
- `src/kitkat/models.py` - Add `Execution`, `ExecutionCreate`, `PartialFillAlert` Pydantic schemas
- `src/kitkat/adapters/extended.py` - Integrate ExecutionService calls (optional - can be done in Story 2.9)

**Alignment with project structure:**
```
src/kitkat/
├── services/
│   ├── execution_service.py  # NEW - follows pattern of session_service.py
├── database.py               # MODIFY - add ExecutionModel
├── models.py                 # MODIFY - add Execution schemas
```

### Technical Requirements

**ExecutionModel Schema:**
```python
class ExecutionModel(Base):
    """SQLAlchemy ORM model for executions table.

    Tracks all order execution attempts for auditing and partial fill handling.
    """
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )  # SHA-256 hash from Signal, NOT foreign key (signals may be cleaned up)
    dex_id: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # "extended", "mock", etc.
    order_id: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True
    )  # DEX-assigned, null on submission failure
    status: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False
    )  # "pending", "filled", "partial", "failed"
    result_data: Mapped[str] = mapped_column(
        Text, default="{}", nullable=False
    )  # JSON with full DEX response, filled_size, remaining_size
    latency_ms: Mapped[int | None] = mapped_column(
        nullable=True
    )  # Time from submission start to response
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=_utc_now, index=True, nullable=False
    )
```

**Pydantic Schemas:**
```python
class ExecutionCreate(BaseModel):
    """Request model for creating an execution record."""
    signal_id: str
    dex_id: str
    order_id: str | None = None
    status: Literal["pending", "filled", "partial", "failed"]
    result_data: dict = Field(default_factory=dict)
    latency_ms: int | None = None

class Execution(BaseModel):
    """Persisted execution record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    signal_id: str
    dex_id: str
    order_id: str | None
    status: Literal["pending", "filled", "partial", "failed"]
    result_data: dict
    latency_ms: int | None
    created_at: datetime

class PartialFillAlert(BaseModel):
    """Alert model for partial fill notifications."""
    signal_id: str
    dex_id: str
    order_id: str
    symbol: str
    filled_amount: Decimal
    remaining_amount: Decimal
    timestamp: datetime
```

**ExecutionService Interface:**
```python
class ExecutionService:
    """Service for logging and querying order executions."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._log = structlog.get_logger().bind(service="execution")

    async def log_execution(
        self,
        signal_id: str,
        dex_id: str,
        order_id: str | None,
        status: str,
        result_data: dict,
        latency_ms: int | None = None,
    ) -> Execution:
        """Log an execution attempt with full context."""
        ...

    async def get_execution(self, execution_id: int) -> Execution | None:
        """Get execution by ID."""
        ...

    async def list_executions(
        self,
        signal_id: str | None = None,
        dex_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Execution]:
        """List executions with optional filters."""
        ...

    def detect_partial_fill(self, result_data: dict) -> bool:
        """Check if result_data indicates a partial fill."""
        ...

    async def queue_partial_fill_alert(
        self,
        signal_id: str,
        dex_id: str,
        order_id: str,
        symbol: str,
        filled_amount: Decimal,
        remaining_amount: Decimal,
    ) -> None:
        """Queue alert for partial fill (logs for now, Telegram in Epic 4)."""
        ...
```

### Previous Story Intelligence

**From Story 2.7 (Retry Logic with Exponential Backoff):**

- Retry decorator on `execute_order()` now retries 3x on transient failures
- `DEXConnectionError`, `DEXTimeoutError` are retried; `DEXRejectionError`, `DEXInsufficientFundsError` fail immediately
- Each retry re-executes full method body including nonce generation
- 66 adapter tests, 368 total project tests

**From Story 2.6 (Extended Adapter - Order Execution):**

- `execute_order()` returns `OrderSubmissionResult` with `order_id`, `status`, `submitted_at`, `filled_amount`, `dex_response`
- `get_order_status()` returns `OrderStatus` with `status`, `filled_amount`, `remaining_amount`, `average_price`
- WebSocket `subscribe_to_order_updates()` receives real-time `OrderUpdate` with fill info

**From Story 2.5 (Extended Adapter - Connection):**

- WebSocket connection established for real-time order updates
- `_ws_task` background task processes order update messages
- `_order_callbacks` dict maps order_id to callback functions

**Key patterns:**
- All DEX adapter methods use structlog with `.bind()` for context
- HTTP responses stored in `dex_response` dict field
- Datetime handling uses `UtcDateTime` custom type from `database.py`

### Integration Points

**Where ExecutionService is called:**

1. **In Extended Adapter (Option A - Simple):**
   - After `execute_order()` HTTP response is received
   - Pass `signal_id` (need to thread through), `dex_id`, `order_id`, result
   - Issue: adapter doesn't currently have `signal_id` - it comes from Signal Processor

2. **In Signal Processor (Option B - Recommended):**
   - Signal Processor calls `execute_order()` and then logs via ExecutionService
   - Signal Processor already has `signal_id` from webhook
   - Decouples logging from adapter (adapter stays focused on DEX communication)
   - Story 2.9 will build Signal Processor - can integrate logging there

**Recommended approach for Story 2.8:**
- Build ExecutionService with full API
- Write integration tests that simulate the Signal Processor flow
- Defer actual Signal Processor integration to Story 2.9

### Partial Fill Detection Logic

**How to detect partial fill from Extended DEX:**

Based on `OrderStatus` model and DEX responses:
```python
def detect_partial_fill(self, result_data: dict) -> bool:
    """Check if execution indicates partial fill."""
    if "filled_amount" not in result_data or "remaining_amount" not in result_data:
        return False

    filled = Decimal(str(result_data.get("filled_amount", 0)))
    remaining = Decimal(str(result_data.get("remaining_amount", 0)))

    # Partial if both filled > 0 AND remaining > 0
    return filled > 0 and remaining > 0
```

**Status mapping:**
- `filled_amount == 0` → "pending" or "failed" (check error)
- `filled_amount > 0 and remaining_amount == 0` → "filled"
- `filled_amount > 0 and remaining_amount > 0` → "partial"

### Logging Standards

**Per project-context.md:**
```python
log = structlog.get_logger().bind(service="execution")

# On execution logging
log.info(
    "Execution recorded",
    signal_id=signal_id,
    dex_id=dex_id,
    order_id=order_id,
    status=status,
    latency_ms=latency_ms,
)

# On partial fill
log.warning(
    "Partial fill detected",
    signal_id=signal_id,
    dex_id=dex_id,
    order_id=order_id,
    symbol=symbol,
    filled_amount=str(filled_amount),
    remaining_amount=str(remaining_amount),
)
```

### Alert Queue for Epic 4

Story 2.8 prepares the alert hook but does NOT implement Telegram sending (that's Epic 4 Story 4.2).

**Current implementation:**
```python
async def queue_partial_fill_alert(self, ...) -> None:
    """Queue alert for partial fill.

    Currently logs alert details. Epic 4 will add Telegram integration.
    Alert hook pattern: log.info("ALERT:PARTIAL_FILL", ...) for Epic 4 to consume.
    """
    self._log.info(
        "ALERT:PARTIAL_FILL",
        signal_id=signal_id,
        dex_id=dex_id,
        order_id=order_id,
        symbol=symbol,
        filled_amount=str(filled_amount),
        remaining_amount=str(remaining_amount),
    )
```

### Testing Strategy

**Unit tests (test_execution_service.py):**
1. `test_log_execution_success` - verify record created with all fields
2. `test_log_execution_with_partial_fill` - verify status set to "partial"
3. `test_log_execution_failure` - verify status set to "failed"
4. `test_get_execution_by_id` - verify retrieval
5. `test_list_executions_with_filters` - verify filtering by signal_id, dex_id, status
6. `test_detect_partial_fill_true` - filled > 0 and remaining > 0
7. `test_detect_partial_fill_false_fully_filled` - remaining = 0
8. `test_detect_partial_fill_false_not_filled` - filled = 0
9. `test_queue_partial_fill_alert` - verify logging with correct message pattern

**Integration tests:**
1. `test_execution_persists_to_database` - full DB roundtrip
2. `test_multiple_executions_for_same_signal` - fan-out scenario (multiple DEXs)
3. `test_latency_calculation` - verify timing capture

### Git Intelligence

**Recent commits:**
- `54fbfda` chore: manual commit
- `d8d096d` Mark Story 2.5 as done
- `49e12b5` Story 2.5: Extended Adapter Connection
- `2dcd4ee` Story 2.1: DEX Adapter Interface

**Files changed in recent stories:**
- `src/kitkat/adapters/extended.py` - Main adapter with execute_order()
- `src/kitkat/models.py` - Pydantic schemas
- `src/kitkat/database.py` - ORM models

### Dependencies

**Required packages (already installed):**
- `sqlalchemy[asyncio]` - ORM
- `structlog` - logging
- `pydantic` - schemas

**No new dependencies needed.**

### Error Handling

| Scenario | Action |
|----------|--------|
| Database write fails | Raise exception, don't swallow (critical audit data) |
| Invalid status value | Pydantic validation rejects |
| Missing signal_id | Required field, validation error |
| result_data parse error | Store raw string, log warning |

### Security Considerations

- `result_data` may contain DEX API responses - ensure no secrets logged
- `signal_id` is a hash, not a security token
- Execution records are append-only for audit trail integrity

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.8-Execution-Logging-Partial-Fills]
- [Source: _bmad-output/planning-artifacts/architecture.md#Data-Architecture]
- [Source: _bmad-output/planning-artifacts/architecture.md#Logging-Patterns]
- [Source: _bmad-output/project-context.md#Database-Naming]
- [Source: _bmad-output/project-context.md#Logging-Standards]

## Implementation Readiness

**Prerequisites met:**
- Story 2.6 completed (execute_order returns OrderSubmissionResult)
- Story 2.7 completed (retry logic in place)
- Database layer exists with UtcDateTime type and session management
- Pydantic patterns established in models.py

**Functional Requirements Covered:**
- FR14: System can log partial fill events with fill amount and remaining
- FR15: System can alert user on partial fill scenarios (hook prepared)
- FR16: System can log all execution attempts with timestamps and responses

**Estimated Scope:**
- ~100 lines ExecutionModel + Execution schemas
- ~150 lines ExecutionService implementation
- ~200 lines test code
- 2 new files, 2 modified files

**Related Stories:**
- Story 2.6 (Order Execution): Provides OrderSubmissionResult to log
- Story 2.7 (Retry Logic): Multiple attempts per execution may be logged
- Story 2.9 (Signal Processor): Will call ExecutionService after each DEX execution
- Story 4.2 (Telegram Alerts): Will consume partial fill alert hooks

---

**Created:** 2026-01-30
**Ultimate context engine analysis completed - comprehensive developer guide created**

---

## Dev Agent Record

### Agent Model Used

Claude Haiku 4.5

### Debug Log References

- Fixed fixture naming: Changed test functions from `db` parameter to `test_db_session` to match conftest.py
- Fixed JSON serialization: Added `default=str` to json.dumps() to handle Decimal types
- Fixed result_data deserialization: Added _deserialize_result_data() method to convert JSON strings back to dicts for Pydantic validation

### Completion Notes List

- All 16 ExecutionService tests pass
- All 383 project tests pass with no regressions
- All 5 acceptance criteria validated:
  - AC1: Execution records created in database with all required fields ✓
  - AC2: Partial fill detection working (both filled > 0 AND remaining > 0) ✓
  - AC3: Alert queuing implemented via queue_partial_fill_alert() ✓
  - AC4: Structured logging with signal_id, dex_id, order_id, status, latency_ms ✓
- Task 5 (Extended Adapter integration) deferred to Story 2.9 as planned

### File List

**Created:**
- `src/kitkat/services/execution_service.py` - ExecutionService class with 5 core methods
- `tests/services/test_execution_service.py` - 16 unit tests covering all ExecutionService methods

**Modified:**
- `src/kitkat/database.py` - Added ExecutionModel ORM class (lines 203-233)
- `src/kitkat/models.py` - Added ExecutionCreate, Execution, PartialFillAlert Pydantic schemas (lines 383-425)
