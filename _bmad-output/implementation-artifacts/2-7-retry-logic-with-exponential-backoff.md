# Story 2.7: Retry Logic with Exponential Backoff

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **system**,
I want **transient failures retried with exponential backoff**,
so that **temporary network issues don't cause permanent failures**.

## Acceptance Criteria

1. **Timeout Retry**: Given an order submission fails with a timeout, when the retry logic activates, then up to 3 retry attempts are made and delays follow exponential backoff: 1s, 2s, 4s

2. **Server Error Retry**: Given an order submission fails with HTTP 5xx, when the retry logic activates, then retries are attempted with backoff and each attempt is logged with attempt number

3. **Client Error No Retry**: Given an order submission fails with HTTP 4xx (client error), when the error is received, then no retry is attempted (business error, not transient) and the error is returned immediately

4. **Retries Exhausted**: Given all 3 retry attempts fail, when retries are exhausted, then the final error is returned and an alert is triggered (will be handled in Epic 4)

5. **Tenacity Implementation**: Given the retry mechanism, when I check the implementation, then tenacity library is used with `@retry` decorator and jitter is applied to prevent thundering herd

## Tasks / Subtasks

- [x] Task 1: Create retry service/wrapper for DEX adapter operations (AC: #1, #2, #5)
  - [x] Subtask 1.1: Design retry strategy - tenacity decorator on adapter methods (Option A)
  - [x] Subtask 1.2: Implement retry logic using tenacity with `stop_after_attempt(4)` and `wait_exponential_jitter`
  - [x] Subtask 1.3: Configure retry to trigger on `DEXConnectionError`, `DEXTimeoutError`
  - [x] Subtask 1.4: Add structured logging before each retry attempt via `before_sleep_log`

- [x] Task 2: Implement error classification for retry decisions (AC: #3)
  - [x] Subtask 2.1: Ensure `DEXRejectionError`, `DEXInsufficientFundsError`, `DEXOrderNotFoundError` are NOT retried
  - [x] Subtask 2.2: Ensure HTTP 4xx errors from Extended DEX are raised as non-retryable exceptions immediately
  - [x] Subtask 2.3: Ensure HTTP 5xx errors are raised as `DEXConnectionError` (retryable)

- [x] Task 3: Apply retry to `execute_order()` method (AC: #1, #2, #5)
  - [x] Subtask 3.1: Wrap `execute_order()` with tenacity retry decorator
  - [x] Subtask 3.2: Configure backoff: initial=1s, max=8s with jitter
  - [x] Subtask 3.3: Ensure nonce is regenerated on each retry attempt (avoid replay)

- [x] Task 4: Handle retry exhaustion (AC: #4)
  - [x] Subtask 4.1: On retries exhausted, `reraise=True` re-raises the last underlying exception
  - [x] Subtask 4.2: Log final failure via `before_sleep_log` on each retry attempt
  - [x] Subtask 4.3: Prepare alert hook for Epic 4 integration (log message that alert service will consume)

- [x] Task 5: Write comprehensive tests (AC: #1, #2, #3, #4, #5)
  - [x] Subtask 5.1: Test retry on timeout - verify 3 attempts with backoff delays
  - [x] Subtask 5.2: Test retry on HTTP 5xx - verify retries are attempted
  - [x] Subtask 5.3: Test no retry on HTTP 400 (DEXRejectionError) - verify immediate failure
  - [x] Subtask 5.4: Test no retry on DEXInsufficientFundsError - verify immediate failure
  - [x] Subtask 5.5: Test all retries exhausted - verify final error returned
  - [x] Subtask 5.6: Test retry logging - verify attempt number logged on each retry
  - [x] Subtask 5.7: Test that jitter is applied (delays are not exact)
  - [x] Subtask 5.8: Test nonce regeneration on retry (no duplicate nonces)
  - [x] Subtask 5.9: Test retry on `DEXConnectionError` (network errors)
  - [x] Subtask 5.10: Test successful recovery on retry (fails once, succeeds on second attempt)

## Dev Notes

### Architecture Compliance

- **Adapter Layer** (`src/kitkat/adapters/`): Primary modification target - add retry decorator to `execute_order()` in `extended.py`
- **Service Layer**: No changes needed - retry is at the adapter level, transparent to SignalProcessor
- **Models** (`src/kitkat/models.py`): No changes needed - existing exception hierarchy already classifies errors correctly
- **Exceptions** (`src/kitkat/adapters/exceptions.py`): No changes needed - existing exceptions already distinguish retryable vs non-retryable

### Project Structure Notes

**Files to modify:**
- `src/kitkat/adapters/extended.py` - Add retry decorator to `execute_order()`, possibly `get_order_status()` and `get_position()`
- `tests/adapters/test_extended.py` - Add retry behavior tests

**Files NOT to create:**
- No new service file needed - retry lives as a decorator on adapter methods
- No new exception types needed - existing hierarchy is sufficient

### Technical Requirements

**Tenacity Library Usage (v9.1.2, already installed):**

The project already uses tenacity for WebSocket reconnection in `_connect_websocket()` (line 173-177 of `extended.py`):
```python
@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    retry=retry_if_exception_type((ConnectionError, OSError)),
    reraise=True,
)
async def _connect_websocket(self) -> None:
```

**Retry Configuration for Order Execution:**

Per architecture document and epics requirements:
- **Max attempts:** 3 retries (4 total calls including initial)
- **Backoff:** Exponential 1s -> 2s -> 4s
- **Jitter:** Applied to prevent thundering herd
- **Retryable errors:** `DEXConnectionError`, `DEXTimeoutError`
- **Non-retryable errors:** `DEXRejectionError`, `DEXInsufficientFundsError`, `DEXOrderNotFoundError`

**Recommended Implementation Pattern:**

```python
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
    after_log,
)
import logging

# For before_sleep logging with structlog
_tenacity_logger = logging.getLogger("kitkat.adapters.extended.retry")

@retry(
    stop=stop_after_attempt(4),  # 1 initial + 3 retries
    wait=wait_exponential_jitter(initial=1, max=8, jitter=2),
    retry=retry_if_exception_type((DEXConnectionError, DEXTimeoutError)),
    reraise=True,
    before_sleep=before_sleep_log(_tenacity_logger, logging.WARNING),
)
async def execute_order(self, symbol, side, size) -> OrderSubmissionResult:
    ...
```

**CRITICAL: Nonce Regeneration on Retry**

The current `execute_order()` generates a nonce at the start of the method. Since the entire method body is retried by tenacity, the nonce will be regenerated automatically on each retry attempt because `_generate_nonce()` is called within the method body. This is correct behavior - each retry gets a fresh nonce.

**Error Classification Already Correct:**

The existing `execute_order()` implementation already correctly classifies errors:
- HTTP 400 -> `DEXRejectionError` or `DEXInsufficientFundsError` (NOT retryable)
- HTTP 5xx -> `httpx.HTTPStatusError` -> need to map to `DEXConnectionError` (retryable)
- Timeout -> `DEXTimeoutError` (retryable)
- Network -> `DEXConnectionError` (retryable)

**Current gap:** The `response.raise_for_status()` call at line 452 raises `httpx.HTTPStatusError` for 5xx errors, which is NOT in the retry list. This needs to be caught and re-raised as `DEXConnectionError` to be retried. **This is already handled** at line 467-471:
```python
except httpx.HTTPStatusError as e:
    log.error("Order HTTP error", status_code=e.response.status_code)
    raise DEXConnectionError(
        f"Order submission failed: HTTP {e.response.status_code}"
    ) from e
```

So 5xx errors are already converted to `DEXConnectionError` and will be retried.

### Implementation Approach

**Option A (Recommended): Decorator on `execute_order()` directly**

Add `@retry(...)` decorator to the existing `execute_order()` method. This is the simplest approach and follows the existing pattern used for `_connect_websocket()`.

Pros:
- Minimal code changes
- Follows existing codebase pattern
- Tenacity handles all retry mechanics (backoff, jitter, logging)
- Nonce regeneration happens automatically (within method body)

Cons:
- Retry logic is coupled to adapter method

**Option B: Separate retry wrapper function**

Create a `_execute_order_with_retry()` wrapper. More complex, less idiomatic.

**Recommendation: Option A** - Add decorator directly, consistent with existing `_connect_websocket()` pattern.

### Which Methods to Add Retry To

Per FR13 ("System can retry failed orders with exponential backoff"), the retry should apply to:

1. **`execute_order()`** - Primary target. Order submissions are the critical path.
2. **`get_order_status()`** - Optional but recommended. Status queries can fail transiently.
3. **`get_position()`** - Optional but recommended. Position queries can fail transiently.
4. **`cancel_order()`** - Optional. Cancel operations are important but not FR-required for retry.

**Minimum scope:** `execute_order()` only (per FR13).
**Recommended scope:** `execute_order()`, `get_order_status()`, `get_position()` (all read/write operations that interact with DEX API).

### Previous Story Intelligence

**From Story 2.6 (Extended Adapter - Order Execution):**

- `execute_order()` fully implemented at lines 366-474 of `extended.py`
- Error handling already classifies: timeout -> `DEXTimeoutError`, network -> `DEXConnectionError`, 400 -> `DEXRejectionError`/`DEXInsufficientFundsError`
- `_generate_nonce()` and `_create_order_signature()` are called at start of `execute_order()` body - they will be re-executed on retry automatically
- 50 tests currently exist in `test_extended.py`
- Code review in 2.6 fixed: nonce collision risk (microsecond timestamp), json.JSONDecodeError handling, moved hashlib import

**Key patterns from Story 2.6:**
```python
# Existing error handling that makes retry classification work:
except httpx.TimeoutException as e:
    raise DEXTimeoutError(...)  # Will be retried
except httpx.HTTPStatusError as e:
    raise DEXConnectionError(...)  # Will be retried (covers 5xx)
except httpx.HTTPError as e:
    raise DEXConnectionError(...)  # Will be retried
```

The `DEXRejectionError` and `DEXInsufficientFundsError` are raised BEFORE the httpx exception handlers (in the `if response.status_code == 400:` block), so they correctly bypass the catch-all and will NOT be retried.

### Git Intelligence

**Recent commits showing patterns:**
- `d8d096d` Mark Story 2.5 as done
- `49e12b5` Story 2.5: Extended Adapter Connection - tenacity used for WebSocket reconnect
- `2dcd4ee` Story 2.1: DEX Adapter Interface - established exception hierarchy

**Existing tenacity usage in codebase:**
- `extended.py:173-177` - `@retry` on `_connect_websocket()` with `wait_exponential_jitter(initial=1, max=30, jitter=2)`
- Already imports: `retry`, `retry_if_exception_type`, `stop_after_attempt`, `wait_exponential_jitter`, `RetryError`

### Testing Standards

**Test approach for retry behavior:**

Use `unittest.mock.patch` to control `_http_client.post` behavior across multiple calls. Tenacity can be configured in tests with shorter waits or `wait_none()` to avoid actual delays.

```python
from tenacity import wait_none

@pytest.mark.asyncio
async def test_execute_order_retries_on_timeout(connected_adapter):
    """Test that execute_order retries 3 times on timeout."""
    # Override retry wait for faster tests
    connected_adapter.execute_order.retry.wait = wait_none()

    mock_post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    with patch.object(connected_adapter._http_client, "post", mock_post):
        with pytest.raises(DEXTimeoutError):
            await connected_adapter.execute_order("ETH-PERP", "buy", Decimal("1.0"))

    # Should have been called 4 times (1 initial + 3 retries)
    assert mock_post.call_count == 4


@pytest.mark.asyncio
async def test_execute_order_no_retry_on_rejection(connected_adapter):
    """Test that DEXRejectionError is NOT retried."""
    mock_response = httpx.Response(
        400,
        json={"error": "INVALID_SYMBOL", "message": "Symbol not found"},
        request=httpx.Request("POST", "http://test/user/order"),
    )
    mock_post = AsyncMock(return_value=mock_response)
    with patch.object(connected_adapter._http_client, "post", mock_post):
        with pytest.raises(DEXRejectionError):
            await connected_adapter.execute_order("INVALID", "buy", Decimal("1.0"))

    # Should have been called only once (no retry)
    assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_execute_order_succeeds_on_retry(connected_adapter):
    """Test successful recovery on second attempt."""
    connected_adapter.execute_order.retry.wait = wait_none()

    success_response = httpx.Response(
        200,
        json={"order_id": "ord_123", "status": "PENDING", "created_at": "2026-01-27T10:00:00Z"},
        request=httpx.Request("POST", "http://test/user/order"),
    )

    mock_post = AsyncMock(
        side_effect=[
            httpx.TimeoutException("timeout"),  # First call fails
            success_response,  # Second call succeeds
        ]
    )
    with patch.object(connected_adapter._http_client, "post", mock_post):
        result = await connected_adapter.execute_order("ETH-PERP", "buy", Decimal("1.0"))

    assert result.order_id == "ord_123"
    assert mock_post.call_count == 2
```

**Important: Accessing tenacity retry on bound methods**

When testing, the retry configuration can be accessed via `connected_adapter.execute_order.retry`. For instance methods decorated with `@retry`, tenacity wraps the function and exposes `.retry` attribute for test configuration overrides.

### Security Considerations

- No new security concerns introduced by retry logic
- Nonce is regenerated per attempt (no replay risk)
- API key is not re-exposed by retry (same HTTP client reused)
- Log messages during retry should NOT log secrets (already handled in Story 2.5/2.6)

### Dependencies

**Required packages (already installed):**
- `tenacity>=9.1.2` - retry with backoff (already in pyproject.toml)
- No new dependencies needed

### Error Handling Reference

| Error Type | Retryable? | Max Retries |
|------------|-----------|-------------|
| `DEXConnectionError` | Yes | 3 |
| `DEXTimeoutError` | Yes | 3 |
| `DEXRejectionError` | No | 0 |
| `DEXInsufficientFundsError` | No | 0 |
| `DEXOrderNotFoundError` | No | 0 |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.7-Retry-Logic-with-Exponential-Backoff]
- [Source: _bmad-output/planning-artifacts/architecture.md#Retry-Behavior]
- [Source: _bmad-output/planning-artifacts/architecture.md#WebSocket-Reconnection]
- [Source: _bmad-output/project-context.md#Error-Handling]
- [Source: _bmad-output/project-context.md#Async-Patterns]

## Implementation Readiness

**Prerequisites met:**
- Story 2.6 completed (execute_order fully implemented with proper error classification)
- tenacity 9.1.2 already installed and used in codebase
- All exception types already defined and correctly raised
- Error classification (retryable vs non-retryable) already in place

**Functional Requirements Covered:**
- FR13: System can retry failed orders with exponential backoff (3 attempts)

**Estimated Scope:**
- ~15-20 lines of new/modified adapter code (decorator + imports)
- ~150-200 lines of test code (10 new tests)
- No new files created

**Related Stories:**
- Story 2.5 (Extended Adapter - Connection): Established tenacity retry pattern for WebSocket
- Story 2.6 (Extended Adapter - Order Execution): Provides the methods to wrap with retry
- Story 2.8 (Execution Logging & Partial Fills): Will log retry attempts to database
- Story 2.9 (Signal Processor & Fan-Out): Will call adapter methods that now have retry

---

**Created:** 2026-01-27
**Ultimate context engine analysis completed - comprehensive developer guide created**

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- All 5 ACs verified: timeout retry, server error retry, client error no retry, retries exhausted, tenacity with jitter
- 13 new Story 2.7 tests added (66 total adapter tests, 368 total project tests)
- Retry decorator applied to `execute_order()` using tenacity with `stop_after_attempt(4)`, `wait_exponential_jitter(initial=1, max=8, jitter=2)`
- Retryable: `DEXConnectionError`, `DEXTimeoutError`; Non-retryable: `DEXRejectionError`, `DEXInsufficientFundsError`, `DEXOrderNotFoundError`
- `before_sleep_log` provides retry logging via stdlib logger (tenacity requirement)
- Nonce regeneration verified: each retry attempt gets a fresh nonce (method body re-executes)

### Code Review Changelog

- **H1 FIX**: Changed `execute_order()` not-connected guard from `DEXConnectionError` to `DEXError` (base class) to prevent pointless retry on disconnected adapter
- **H2 FIX**: Added `wait_none()` to Story 2.6 timeout/connection error tests to prevent 33s of real backoff delays; added `call_count == 4` assertions to acknowledge retry behavior
- Test suite time reduced from 41s to 8s for adapter tests, 79s to 53s for full suite

### File List

- `src/kitkat/adapters/extended.py` - Added `@retry` decorator to `execute_order()`, `DEXError` import, tenacity imports
- `tests/adapters/test_extended.py` - Added 13 retry tests (7 test classes), `DEXError` import, `wait_none` fixes

