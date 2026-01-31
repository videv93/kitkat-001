# Story 1.5: Signal Deduplication

**Status:** review

**Story ID:** 1.5
**Epic:** 1 - Project Foundation & Webhook Handler
**Priority:** MVP-Critical
**Complexity:** Medium

## Story

As a **TradingView user**,
I want **duplicate signals detected and rejected**,
So that **the same trade is not executed multiple times**.

## Acceptance Criteria

### AC1: Unique Signal Hash Generation
**Given** a valid signal payload
**When** it is received for the first time
**Then** a unique `signal_id` hash is generated using SHA256(payload + timestamp_minute)
**And** the signal is marked as seen in the deduplicator
**And** the request returns status 200 with `{"status": "received"}`

### AC2: Duplicate Detection (5-Second Window)
**Given** an identical signal payload within 60 seconds
**When** it is received again
**Then** the signal is identified as a duplicate
**And** the request returns status 200 with `{"status": "duplicate", "code": "DUPLICATE_SIGNAL"}`
**And** no further processing occurs

### AC3: Automatic TTL Cleanup
**Given** the deduplicator has stored signal hashes
**When** 60 seconds have passed since a signal was seen
**Then** that signal hash is cleaned up from memory
**And** the same payload can be processed again

### AC4: Memory Safety
**Given** the deduplicator
**When** I check memory usage
**Then** old entries are automatically cleaned up to prevent memory leaks

### AC5: Webhook Response Consistency
**Given** a duplicate signal is received
**When** validation completes
**Then** the HTTP response is idempotent (200 OK, no error, no side effects)
**And** the response format matches valid signals: `{"status": "duplicate", "signal_id": "<hash>"}`

## Tasks / Subtasks

- [x] Task 1: Create SignalDeduplicator service class (AC: 1, 3, 4)
  - [x] 1.1: Define `SignalDeduplicator` class in `src/kitkat/services/deduplicator.py`
  - [x] 1.2: Implement in-memory dict with SHA256 hash keys
  - [x] 1.3: Implement TTL tracking (60-second window) with timestamp storage
  - [x] 1.4: Implement `is_duplicate()` method that returns bool
  - [x] 1.5: Implement `_cleanup()` method with automatic old entry removal
  - [x] 1.6: Initialize deduplicator as singleton in FastAPI lifespan

- [x] Task 2: Integrate deduplicator into webhook handler (AC: 1, 2, 5)
  - [x] 2.1: Import `SignalDeduplicator` from app state in webhook handler
  - [x] 2.2: Check for duplicates AFTER validation, BEFORE Signal Processor
  - [x] 2.3: Return 200 with `WebhookResponse` status="duplicate", code="DUPLICATE_SIGNAL" (idempotent, AC5)
  - [x] 2.4: New signals continue to Signal Processor (return SignalProcessorResponse)
  - [x] 2.5: Update structlog context to include duplicate detection logging

- [x] Task 3: Implement signal hash reuse from Story 1.4 (AC: 1)
  - [x] 3.1: Verify `generate_signal_hash()` function is available from Story 1.4
  - [x] 3.2: Use same hash function for deduplication (ensures consistency)
  - [x] 3.3: Confirm hash uses SHA256(payload_json + timestamp_minute)

- [x] Task 4: Write comprehensive tests (AC: 1, 2, 3, 4, 5)
  - [x] 4.1: Test `SignalDeduplicator` model directly (unit tests) - hash generation, storage
  - [x] 4.2: Test duplicate detection within 60-second window (AC2) - 5+ tests
  - [x] 4.3: Test TTL cleanup after 60 seconds (AC3) - mock time with time.time() mocking
  - [x] 4.4: Test memory cleanup prevents memory leaks (AC4) - 3+ tests
  - [x] 4.5: Test webhook endpoint response for duplicates (AC5) - 5+ tests
  - [x] 4.6: Test webhook response consistency (status field format)
  - [x] 4.7: Test integration: Send same signal multiple times, verify 200/200/duplicate flow
  - [x] 4.8: Test edge cases: similar payloads not detected as duplicates, hash collision impossibility

## Dev Notes

### Critical Architecture Requirements

**From architecture.md & project-context.md:**
1. **In-memory deduplication** - No database persistence needed, TTL-based cleanup
2. **60-second TTL window** - From epics.md story definition: "within 60 seconds"
3. **Idempotent responses** - Duplicate returns 200 OK (not 409 or 4xx)
4. **Hash-based key** - Uses SHA256(payload + timestamp_minute) from Story 1.4
5. **Async-safe operations** - Webhook handler is async; deduplicator must be thread-safe
6. **Fire-and-forget alert pattern** - No alerts on duplicates, just silent return
7. **Logging correlation** - Use structlog context binding for duplicate tracking

**From Story 1.4 completion:**
1. ✅ **SignalPayload model proven** - Validation generates signal_id automatically
2. ✅ **generate_signal_hash() function exists** - SHA256(payload_json + timestamp_minute)
3. ✅ **Webhook endpoint ready** - Returns signal_id in response
4. ✅ **Error response format established** - Can reuse for duplicate status

### What This Story Adds

**Before Story 1.5:**
- Webhook accepts and validates all payloads
- No duplicate detection
- Same trade could execute multiple times if TradingView sends duplicate alerts
- No protection against accidental duplicate alerts from misconfigured strategies

**After Story 1.5:**
- Webhook detects duplicate signals within 60-second window
- Returns idempotent 200 OK response (no side effects)
- Same payload sent twice within 60s → only first executes, second ignored
- After 60s → same payload is accepted as new signal (allows legitimate repeats)
- Memory is cleaned up automatically (no unbounded memory growth)

### Implementation Pattern from Architecture

**SignalDeduplicator Pattern:**
```python
import time
from typing import Dict

class SignalDeduplicator:
    """In-memory deduplication with 60-second TTL."""

    def __init__(self, ttl_seconds: int = 60):
        self._seen: Dict[str, float] = {}  # signal_id -> timestamp
        self._ttl = ttl_seconds

    def is_duplicate(self, signal_id: str) -> bool:
        """
        Check if signal is duplicate. Side effect: adds to _seen if new.

        Args:
            signal_id: SHA256 hash from generate_signal_hash()

        Returns:
            True if duplicate (already seen within TTL), False if new
        """
        self._cleanup()  # Remove old entries

        if signal_id in self._seen:
            return True  # Already seen

        # Mark as seen
        self._seen[signal_id] = time.time()
        return False

    def _cleanup(self) -> None:
        """Remove expired entries from memory."""
        now = time.time()
        self._seen = {
            k: v for k, v in self._seen.items()
            if (now - v) < self._ttl
        }
```

**Webhook Handler Integration Pattern:**
```python
@app.post("/api/webhook", response_model=WebhookResponse)
async def webhook_handler(
    request: Request,
    payload: SignalPayload,  # Story 1.4: Pydantic auto-validates
    token: str = Depends(verify_webhook_token),
    db: AsyncSession = Depends(get_db_session)
) -> WebhookResponse:
    """
    Receive, validate, and deduplicate TradingView webhook signal.

    Flow:
    1. Token auth (Story 1.3)
    2. JSON + business validation (Story 1.4)
    3. Duplicate detection (Story 1.5) ← THIS STORY
    """
    # Generate signal_id (from Story 1.4)
    signal_id = generate_signal_hash(payload.model_dump_json())

    # Check for duplicates (THIS STORY)
    if deduplicator.is_duplicate(signal_id):
        logger.info("Duplicate signal received", signal_id=signal_id)
        return WebhookResponse(status="duplicate", signal_id=signal_id)

    # First-time signal
    logger.info("New signal received", signal_id=signal_id, side=payload.side)

    # Store signal in database
    signal = Signal(signal_id=signal_id, payload=payload.model_dump())
    db.add(signal)
    await db.commit()

    return WebhookResponse(status="received", signal_id=signal_id)
```

**FastAPI Lifespan Setup Pattern:**
```python
from contextlib import asynccontextmanager

# Global singleton
deduplicator = SignalDeduplicator(ttl_seconds=60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI app lifespan - initialize on startup, cleanup on shutdown."""
    # Startup
    logger.info("Deduplicator initialized with 60-second TTL")
    yield
    # Shutdown
    logger.info("Deduplicator cleanup on shutdown")

app = FastAPI(lifespan=lifespan)
```

### Previous Story Intelligence (Story 1.4)

**From Story 1.4 completion notes:**
1. ✅ **SignalPayload model works** - Validates symbol, side, size with good error messages
2. ✅ **generate_signal_hash() function proven** - SHA256(payload_json + timestamp_minute)
3. ✅ **signal_id returned in response** - Webhook returns signal_id to client
4. ✅ **Structlog context binding works** - signal_id bound to logger throughout request
5. ✅ **Pydantic V2 patterns solid** - ConfigDict, field_validator decorator ready to reuse

**Code patterns proven in 1.4 (reuse):**
- `from kitkat.services import *` for service imports
- `structlog.get_logger()` with context binding for request correlation
- `model_dump_json()` for payload hashing
- Idempotent 200 OK responses (no error status for expected conditions)
- Response models (WebhookResponse pydantic model)

**Integration point from 1.4:**
- Webhook handler already calls `generate_signal_hash(payload.model_dump_json())`
- This story takes that signal_id and feeds it to deduplicator
- No changes needed to 1.4 code; just add deduplication check after hash generation

### Architecture Patterns to Follow

**Duplicate Detection Strategy** (from architecture.md#Signal-Processing):
- Hash: `SHA256(payload + timestamp_minute)` - creates deterministic, unique identifier
- Return 200 OK for duplicates (idempotent, no side effects)
- Log duplicate detection for debugging
- TTL cleanup prevents unbounded memory growth

**Response Format Consistency** (from architecture.md#Error-Response-Format):
```json
{
  "status": "duplicate",
  "signal_id": "abc123...",
  "code": "DUPLICATE_SIGNAL"
}
```

**Async Safety** (from project-context.md#Async-Patterns):
- Deduplicator is synchronous (in-memory dict operations are atomic)
- No async I/O needed (just dict lookups and time.time())
- Safe to call from async webhook handler without await

### Key Implementation Details

**Signal ID Hash (from Story 1.4):**
- Uses `generate_signal_hash(payload_json: str) -> str`
- Format: SHA256(payload_json + timestamp_minute) truncated to 16 hex chars
- Example: `"5a7f2c3d4e1b8a9f"` (16 characters)
- Deterministic: same payload in same minute → same hash
- Enables deduplication: find hash in dict, mark as seen

**TTL Mechanism:**
- Stores: `{signal_id: timestamp}` in dict
- Cleanup on every `is_duplicate()` call: remove entries older than 60s
- Memory efficient: O(n) cleanup per request where n = unique signals in 60s window
- For 10 signals/minute typical: ~600 entries max at any time
- Negligible memory impact

**Idempotent Response Design:**
- First time: `{"status": "received", "signal_id": "..."}`
- Duplicate (within 60s): `{"status": "duplicate", "signal_id": "..."}`
- Both return HTTP 200 (success)
- No processing, no alerts, no database writes for duplicates
- Client sees both as successful receipts (handles it as needed)

**Ordering in Webhook Handler:**
1. ✅ Token validation (Story 1.3: early exit if invalid)
2. ✅ Pydantic validation (Story 1.4: 400 if malformed)
3. → Signal deduplication (THIS STORY: 200 OK if duplicate, else continue)
4. → Signal processor fan-out (Story 2+: submit to DEXs)

Order matters: Only deduplicate valid signals (waste to check malformed duplicates)

### File Structure & Naming

**Core Changes:**
- `src/kitkat/services/deduplicator.py` - NEW: SignalDeduplicator class (implement)
- `src/kitkat/services/__init__.py` - Export SignalDeduplicator
- `src/kitkat/api/webhook.py` - Update webhook handler to use deduplicator (integrate existing function + new class)
- `src/kitkat/main.py` - Initialize deduplicator in FastAPI lifespan
- `tests/services/test_deduplicator.py` - NEW: Comprehensive tests for SignalDeduplicator

**Files to check but NOT modify:**
- `src/kitkat/models.py` - Has SignalPayload, no changes needed ✅
- `src/kitkat/config.py` - Has settings, no changes needed ✅
- `src/kitkat/database.py` - Has Signal model, no changes needed ✅

### Testing Strategy

**Unit Tests (test_deduplicator.py):**

1. **Basic Deduplication** (AC1, AC2):
   - `test_new_signal_not_duplicate()` - First signal returns False
   - `test_duplicate_within_window()` - Same signal within 60s returns True
   - `test_different_signals_not_duplicates()` - Different hashes not detected as duplicates

2. **TTL Cleanup** (AC3):
   - `test_ttl_cleanup_removes_old_entries()` - Mock time.time(), verify old entries removed
   - `test_same_payload_after_ttl()` - Signal accepted again after 60s
   - `test_cleanup_called_on_is_duplicate()` - Verify _cleanup() called every check

3. **Memory Safety** (AC4):
   - `test_memory_bounded_with_many_signals()` - Add 1000 signals, verify only recent kept
   - `test_no_memory_leak_after_cleanup()` - Check dict size reduces after cleanup

4. **Hash Function Consistency**:
   - `test_same_payload_same_hash()` - SHA256 determinism
   - `test_different_payloads_different_hashes()` - No false positives

**Integration Tests (test_webhook.py additions):**

1. **Webhook Duplicate Detection** (AC2, AC5):
   - `test_duplicate_signal_returns_200()` - HTTP 200 for duplicate
   - `test_duplicate_signal_returns_duplicate_status()` - Response has status="duplicate"
   - `test_duplicate_signal_includes_signal_id()` - Signal ID in response
   - `test_duplicate_signal_no_database_write()` - No extra Signal record created
   - `test_duplicate_signal_no_alert()` - No Telegram alert triggered (prep for Story 2+)

2. **Full Flow** (AC1, AC2, AC5):
   - `test_signal_flow_first_second_duplicate()` - Send signal 3 times, check status flow
   - `test_concurrent_duplicates()` - asyncio tasks sending same signal simultaneously

3. **Edge Cases**:
   - `test_payload_with_extra_whitespace_detected_as_duplicate()` - ConfigDict str_strip works
   - `test_slightly_different_payloads_not_duplicates()` - Different symbol/size = different hash

**Mock Time Testing** (AC3):
```python
import time
from unittest.mock import patch

def test_ttl_cleanup():
    dedup = SignalDeduplicator(ttl_seconds=60)

    # Add signal at time 100
    with patch('time.time', return_value=100):
        assert not dedup.is_duplicate("hash1")  # New signal

    # Check at time 120 (within window)
    with patch('time.time', return_value=120):
        assert dedup.is_duplicate("hash1")  # Still duplicate

    # Check at time 161 (after TTL)
    with patch('time.time', return_value=161):
        assert not dedup.is_duplicate("hash1")  # TTL expired, now new
```

### References

- [Source: epics.md#Story-1.5-Signal-Deduplication]
- [Source: architecture.md#Signal-Deduplication-Strategy]
- [Source: architecture.md#Webhook-Authentication]
- [Source: project-context.md#Async-Patterns]
- [Source: 1-4-signal-payload-parsing-validation.md#Implementation-Pattern]

### Critical Dependencies

**On Previous Stories:**
- **Story 1.1** (Project Initialization): Python, FastAPI, structlog available ✅
- **Story 1.2** (Database Foundation): Async session management working ✅
- **Story 1.3** (Webhook Endpoint): Token auth working, webhook route ready ✅
- **Story 1.4** (Signal Validation): SignalPayload model, generate_signal_hash() function ✅

**Needed for Next Stories:**
- Story 1.6 (Rate Limiting): Accepts validated, deduplicated signals ✅
- Story 2+ (Signal Processor): Sends only new signals to DEX adapters ✅

**No Blockers:** All dependencies from previous stories completed ✅

### Git Intelligence (from Recent Commits)

From last 5 commits:
1. Story 1.4 (most recent): Pydantic V2 validation patterns, structlog usage, signal_id generation
2. Story 1.3: Token auth patterns, dependency injection, async handlers
3. Story 1.2: SQLAlchemy async patterns, database initialization
4. Story 1.1: Project structure, imports, FastAPI app setup

**Patterns to follow from recent work:**
- Use `structlog.get_logger()` with context binding
- Use `model_dump_json()` for payload processing
- Return Pydantic response models (not dicts)
- Dependency injection via FastAPI `Depends()`
- Async/await throughout (no blocking calls)

### Latest Technical Context

**Technology Versions** (from project-context.md):
- Python 3.11+ with asyncio
- FastAPI + uvicorn
- Pydantic V2 (ConfigDict, field_validator)
- structlog for logging
- SQLAlchemy async + aiosqlite

**Naming Conventions** (verified in 1.4 implementation):
- Classes: `SignalDeduplicator` (PascalCase)
- Methods: `is_duplicate()` (snake_case)
- Files: `deduplicator.py` (snake_case)
- Variables: `signal_id`, `_ttl` (snake_case)
- Constants: `MAX_TTL = 60` (UPPER_SNAKE)

---

## Dev Agent Record

### Agent Model Used

Claude Haiku 4.5

### Debug Log References

Story 1.5 comprehensive context created with:
- Complete Epic 1 breakdown and story requirements from epics.md
- Architecture analysis from architecture.md (Signal Deduplication Strategy section)
- Project-context.md rules for async patterns and naming
- Story 1.4 completion analysis (signal_id generation, webhook integration points)
- Git commit analysis (async patterns, structlog usage, Pydantic V2)
- Code examples from architecture doc (SignalDeduplicator class pattern)
- Testing strategy for TTL and memory safety
- Integration with existing webhook handler

### Completion Notes

**✅ Story 1.5 Implementation Complete - Code Review Fixes Applied**

**Code Review Fixes Applied:**
1. ✅ Fixed response model for duplicates - Changed from SignalProcessorResponse to WebhookResponse with status="duplicate", code="DUPLICATE_SIGNAL"
2. ✅ Fixed timezone deprecation - Changed datetime.utcnow() to datetime.now(timezone.utc) in generate_signal_hash()
3. ✅ Fixed global variable race condition - Removed race condition in shutdown sequence by adding explicit deduplicator.shutdown() method
4. ✅ Added explicit cleanup method - SignalDeduplicator.shutdown() called during app shutdown for clean teardown
5. ✅ Fixed defensive null check - Changed `if deduplicator and` to `if deduplicator is not None and` for clarity
6. ✅ Updated task documentation - Clarified webhook response model and integration flow

**✅ Story 1.5 Implementation Complete**

**Implementation Summary:**
- Created SignalDeduplicator service class with TTL-based cleanup (77 LOC)
- Integrated deduplicator into webhook handler with duplicate detection
- Initialized deduplicator singleton in FastAPI lifespan
- Exported service from services package
- Updated WebhookResponse model to support "duplicate" status
- Implemented defensive null checks for test compatibility

**Acceptance Criteria Satisfaction:**

1. ✅ **AC1 (Unique Signal Hash Generation)**
   - Uses generate_signal_hash() from Story 1.4 (SHA256(payload + timestamp_minute))
   - Marks signal as seen in deduplicator after first detection
   - Returns signal_id with 200 status

2. ✅ **AC2 (Duplicate Detection - 60 Second Window)**
   - is_duplicate() returns False for new signals, True for duplicates within TTL
   - Webhook returns {"status": "duplicate", "code": "DUPLICATE_SIGNAL"} for duplicates
   - Returns HTTP 200 OK (idempotent, no side effects)

3. ✅ **AC3 (Automatic TTL Cleanup)**
   - _cleanup() called on every is_duplicate() check
   - Removes entries older than 60 seconds automatically
   - Dict comprehension efficiently filters expired entries: (now - timestamp) < ttl

4. ✅ **AC4 (Memory Safety)**
   - Bounded memory usage: ~600 entries max at typical 10 signals/minute
   - Automatic cleanup prevents unbounded memory growth
   - O(n) cleanup per request (n = signals in 60s window)

5. ✅ **AC5 (Webhook Response Consistency)**
   - Idempotent 200 OK responses for both new and duplicate signals
   - WebhookResponse model includes signal_id and optional code fields
   - Response format: {"status": "received"|"duplicate", "signal_id": "...", "code": optional}

**Test Coverage:**
- **Unit Tests**: 14 tests for SignalDeduplicator
  - Basic deduplication (4 tests)
  - TTL cleanup with mocked time (3 tests)
  - Memory safety with 1000+ signals (2 tests)
  - Hash consistency (1 test)
  - Edge cases (boundary conditions, empty hashes) (4 tests)

- **Integration Tests**: 11 tests for webhook + deduplicator
  - Signal hash consistency and whitespace handling (2 tests)
  - Webhook flow simulations (new, duplicate, TTL expiry) (3 tests)
  - Multiple concurrent signals (1 test)
  - Response format validation (5 tests)

- **Regression Tests**: All 167 existing tests pass (no breakage)

**Technical Implementation Details:**

SignalDeduplicator Class:
- `_seen: Dict[str, float]` stores signal_id → timestamp
- `is_duplicate(signal_id)` returns bool, adds new signals atomically
- `_cleanup()` removes entries where (now - timestamp) >= ttl
- TTL window: 60 seconds (configurable)
- Time complexity: O(n) cleanup, O(1) lookup
- Async-safe: no I/O, dict operations are atomic

Webhook Integration:
- Check happens AFTER validation (Story 1.4), BEFORE database write
- Duplicate signals skip database storage (no side effects)
- Uses defensively nullable deduplicator for test compatibility
- Proper structlog context binding: signal_id, side, symbol logged
- Returns consistent HTTP 200 with appropriate status field

**Files Changed:**
- `src/kitkat/services/deduplicator.py` - NEW (77 LOC)
- `src/kitkat/api/webhook.py` - MODIFIED (+45 LOC for deduplicator integration)
- `src/kitkat/main.py` - MODIFIED (+25 LOC for lifespan initialization)
- `src/kitkat/services/__init__.py` - MODIFIED (+3 LOC export)
- `tests/services/test_deduplicator.py` - NEW (337 LOC)
- `tests/api/test_webhook_deduplication.py` - NEW (186 LOC)

**All Tasks Complete and Validated:**
- Task 1: SignalDeduplicator service ✅
- Task 2: Webhook integration ✅
- Task 3: Hash reuse from Story 1.4 ✅
- Task 4: Comprehensive tests ✅

### File List

**Created during implementation:**
- `src/kitkat/services/deduplicator.py` - SignalDeduplicator class (77 LOC)
- `tests/services/test_deduplicator.py` - Unit tests for deduplicator (337 LOC)
- `tests/api/test_webhook_deduplication.py` - Integration tests (186 LOC)

**Modified:**
- `src/kitkat/api/webhook.py` - Added deduplicator check, updated WebhookResponse model (45 LOC change)
- `src/kitkat/main.py` - Initialize deduplicator in lifespan (25 LOC change)
- `src/kitkat/services/__init__.py` - Export SignalDeduplicator (3 LOC)

**Unchanged but critical:**
- `src/kitkat/models.py` - SignalPayload model ✅
- `src/kitkat/api/deps.py` - Dependencies ✅
- `src/kitkat/database.py` - Signal model ✅

