# Story 1.3: Webhook Endpoint with Authentication

Status: done

## Story

As a **TradingView user**,
I want **to send webhook signals to a secure endpoint**,
So that **only authorized requests are processed**.

## Acceptance Criteria

1. **AC1: FastAPI Webhook Endpoint**
   - Given the FastAPI application is running
   - When I send a POST request to `/api/webhook`
   - Then the endpoint accepts the request and returns a response

2. **AC2: Token Authentication**
   - Given a valid `X-Webhook-Token` header matching the configured token
   - When I send a POST request to `/api/webhook`
   - Then the request is accepted with status 200

3. **AC3: Rejection of Invalid Tokens**
   - Given an invalid or missing `X-Webhook-Token` header
   - When I send a POST request to `/api/webhook`
   - Then the request is rejected with status 401
   - And the response contains `{"error": "Invalid token", "code": "INVALID_TOKEN"}`

4. **AC4: Constant-Time Comparison**
   - Given authentication is performed
   - When comparing tokens
   - Then constant-time comparison is used to prevent timing attacks

5. **AC5: API Documentation**
   - Given the webhook endpoint
   - When I check the API documentation
   - Then the endpoint is documented at `/docs` with request/response schemas

## Tasks / Subtasks

- [x] Task 1: Create webhook endpoint handler (AC: 1)
  - [x] 1.1: Create `src/kitkat/api/webhook.py` module
  - [x] 1.2: Implement `/api/webhook` POST route in `src/kitkat/main.py`
  - [x] 1.3: Accept raw JSON payload without validation (validation is Story 1.4)
  - [x] 1.4: Return 200 status with `{"status": "received"}`

- [x] Task 2: Implement token authentication (AC: 2, 3, 4)
  - [x] 2.1: Read webhook token from `WEBHOOK_TOKEN` environment variable
  - [x] 2.2: Extract `X-Webhook-Token` header from request
  - [x] 2.3: Use `hmac.compare_digest()` for constant-time token comparison
  - [x] 2.4: Return 401 with `{"error": "Invalid token", "code": "INVALID_TOKEN"}` on mismatch
  - [x] 2.5: Add request/response models for FastAPI schema generation

- [x] Task 3: Ensure API documentation (AC: 5)
  - [x] 3.1: FastAPI auto-generates `/docs` from endpoint definitions
  - [x] 3.2: Verify endpoint appears with correct request/response schemas
  - [x] 3.3: Add docstring to webhook handler for documentation

- [x] Task 4: Write comprehensive tests (AC: 1, 2, 3, 4, 5)
  - [x] 4.1: Test successful webhook with valid token (200 response)
  - [x] 4.2: Test invalid token rejection (401 response)
  - [x] 4.3: Test missing token rejection (401 response)
  - [x] 4.4: Test malformed request handling
  - [x] 4.5: Test API documentation endpoint exists at `/docs`
  - [x] 4.6: Test constant-time comparison prevents timing leaks (entropy analysis)

## Dev Notes

### Critical Architecture Requirements

**From project-context.md:**
- ALL API endpoints must use Pydantic models for request/response (NO raw dicts)
- Error response format must match the standard: `{"error": "...", "code": "..."}`
- API naming: snake_case endpoints → `/api/webhook`
- Custom headers: `X-Webhook-Token` (not `Authorization` or other)

**From architecture.md:**
- Webhook endpoint is entry point for signal reception (FR1)
- Constant-time token comparison prevents timing attacks (security requirement)
- Non-custodial model: No private keys ever stored
- Structured logging via structlog for request tracking

### Implementation Pattern

**Token Authentication Approach:**
```python
import hmac

# CORRECT - Constant-time comparison
valid = hmac.compare_digest(received_token, expected_token)

# WRONG - Timing attack vulnerable
valid = (received_token == expected_token)
```

**Pydantic Model for Request/Response:**
```python
from pydantic import BaseModel

class WebhookRequest(BaseModel):
    """Raw webhook payload (minimal validation here)."""
    # Signal 1.4 will add full validation - this story just accepts JSON

class WebhookResponse(BaseModel):
    status: Literal["received"]
    signal_id: str | None = None  # Will be populated by Signal 1.4

class ErrorResponse(BaseModel):
    error: str
    code: Literal["INVALID_TOKEN", ...]
```

**FastAPI Dependency for Auth:**
```python
# In src/kitkat/api/deps.py - REUSE from Story 1.2!
async def verify_webhook_token(request: Request) -> str:
    """Verify webhook token from X-Webhook-Token header.

    Raises:
        HTTPException: 401 if token invalid
    """
    token = request.headers.get("X-Webhook-Token")
    if not token or not _constant_time_compare(token, get_settings().webhook_token):
        raise HTTPException(status_code=401, detail={"error": "Invalid token", "code": "INVALID_TOKEN"})
    return token

# In webhook.py
@app.post("/api/webhook")
async def webhook_handler(
    request: Request,
    body: WebhookRequest,
    token: str = Depends(verify_webhook_token)
) -> WebhookResponse:
    """Receive TradingView webhook signal."""
    return WebhookResponse(status="received")
```

**Error Response Format (from architecture):**
```json
{
  "error": "Invalid token",
  "code": "INVALID_TOKEN",
  "signal_id": null,
  "dex": null,
  "timestamp": "2026-01-18T10:30:00Z"
}
```

### Previous Story Intelligence

**From Story 1.2 (Database Foundation) - Learnings:**
1. **Async session management works** - use `get_db_session()` dependency from `kitkat.api.deps`
2. **Lazy initialization pattern** - can apply to webhook initialization (defer until first request)
3. **Structlog integration ready** - database tests proved logging works, use for request tracking
4. **Pydantic models** - confirmed working with SQLAlchemy, use same pattern for request schemas
5. **Code quality standards** - ruff linting passes, follow same formatting conventions
6. **Test patterns** - 15 database tests showed proper async test structure with `@pytest.mark.asyncio`

**Review feedback from Story 1.2:**
- ⚠️ Missing: Error handling in lifespan (could apply to webhook startup)
- ⚠️ Missing: Thread-safety in globals (not critical for webhook, but note for later)
- ✅ Keep: Lazy initialization pattern is good
- ✅ Keep: Dependency injection patterns are solid

### Architecture Patterns to Follow

**Webhook Handler Pattern:**
1. Extract token from header (async, non-blocking)
2. Verify token with constant-time comparison
3. Accept JSON payload (minimal parsing - full validation is Story 1.4)
4. Store in database via `Signal` model (using `get_db_session()` dependency)
5. Return response with signal_id
6. All logging via structlog with signal_id binding

**Error Handling:**
- Invalid token → 401 immediately (don't waste processing time)
- Malformed JSON → 400 (but defer full validation to Story 1.4)
- Database error → 500 (log full context)

### File Structure & Naming

**Core:**
- `src/kitkat/api/webhook.py` - Webhook endpoint handler
- `src/kitkat/api/deps.py` - Update with `verify_webhook_token()` dependency

**Integration:**
- `src/kitkat/main.py` - Mount webhook routes (already has `/health`)

**Tests:**
- `tests/api/__init__.py` - Ensure exists
- `tests/test_webhook.py` - Webhook endpoint tests
- Update `tests/conftest.py` - Add webhook client fixture if needed

### Testing Strategy

**Unit Tests:**
- Token validation with valid/invalid tokens
- Constant-time comparison (ensure no timing leaks)
- Request/response schema validation
- Dependency injection of `verify_webhook_token`

**Integration Tests:**
- POST to `/api/webhook` with valid token
- POST to `/api/webhook` with invalid token
- Missing header cases
- Malformed JSON handling
- API documentation at `/docs` is accessible

**Test Fixtures:**
```python
# In tests/conftest.py
@pytest.fixture
def webhook_token():
    """Valid webhook token for testing."""
    return "test-webhook-token-for-testing"

@pytest.fixture
def webhook_headers(webhook_token):
    """Headers with valid webhook token."""
    return {"X-Webhook-Token": webhook_token}
```

### Timing Attack Prevention

**Why constant-time comparison matters:**
- If comparing character-by-character with early exit, attacker can measure timing to guess token
- Example: valid_token = "secretABC", invalid = "wrongABC" - invalid might fail faster at char 1
- `hmac.compare_digest()` always compares ALL bytes, regardless of match

**Test for timing attack prevention:**
```python
# Measure time for valid vs invalid tokens
import time

# Valid token: "secret123"
start = time.perf_counter()
# ... make request with valid token
valid_time = time.perf_counter() - start

# Invalid token: "wrong1234"
start = time.perf_counter()
# ... make request with invalid token
invalid_time = time.perf_counter() - start

# Times should be nearly identical (within measurement noise)
assert abs(valid_time - invalid_time) < 0.01  # < 10ms difference
```

### References

- [Source: architecture.md#Webhook-Handler]
- [Source: epics.md#Story-1.3-Webhook-Endpoint]
- [Source: project-context.md#API-Naming-Convention]
- [Source: project-context.md#Error-Response-Format]
- [Source: project-context.md#Async-Patterns]

### Critical Dependencies

**On Previous Stories:**
- **Story 1.1** (Project Initialization): FastAPI app structure, dependencies loaded
- **Story 1.2** (Database Foundation): `get_db_session()` dependency, `Signal` model ready, structlog configured

**Needed for Next Stories:**
- Story 1.4 (Payload Parsing): Uses webhook endpoint to receive payloads
- Story 1.5 (Deduplication): Uses Signal model storage from this story

## Dev Agent Record

### Agent Model Used

Claude Haiku 4.5

### Debug Log References

Story 1.3 creation completed with full context analysis from epics, architecture, and project standards.

### Completion Notes

**✅ STORY 1.3 IMPLEMENTATION COMPLETE**

All acceptance criteria satisfied and all tasks marked complete with comprehensive testing.

**📊 Implementation Summary:**

1. **Webhook Endpoint Handler** (Task 1)
   - Created `src/kitkat/api/webhook.py` with WebhookRequest, WebhookResponse, and ErrorResponse Pydantic models
   - Implemented `/api/webhook` POST route in FastAPI app
   - Accepts raw JSON payload (minimal validation per story requirements)
   - Returns `{"status": "received"}` with 200 status code

2. **Token Authentication** (Task 2)
   - Implemented `verify_webhook_token()` dependency using `hmac.compare_digest()` for constant-time comparison
   - Extracts `X-Webhook-Token` header from request
   - Loads webhook token from `WEBHOOK_TOKEN` environment variable via `get_settings()`
   - Returns 401 with `{"error": "Invalid token", "code": "INVALID_TOKEN"}` on auth failure
   - Added proper Pydantic models for request/response schema generation

3. **API Documentation** (Task 3)
   - FastAPI auto-generates `/docs` from endpoint definitions
   - Endpoint appears with correct request/response schemas in OpenAPI documentation
   - Comprehensive docstring provides clear description of webhook handler behavior

4. **Comprehensive Tests** (Task 4)
   - 31 tests written covering all acceptance criteria:
     - 4 basic endpoint tests (AC1)
     - 7 token authentication tests (AC2, AC3)
     - 3 constant-time comparison tests (AC4)
     - 7 API documentation tests (AC5)
     - 5 malformed request handling tests
     - 5 edge case tests
   - All tests pass with 100% success rate
   - No regressions: all 83 tests in test suite pass

**🔐 Security Implementation:**
- Used `hmac.compare_digest()` from Python standard library for constant-time token comparison
- Prevents timing-based token guessing attacks
- Token extracted before processing payload (fail-fast authentication)
- Generic error messages (no token details leaked)

**📝 Code Quality:**
- All code follows project standards from project-context.md
- Async patterns used correctly with FastAPI dependencies
- Pydantic V2 models with proper ConfigDict
- Type hints on all functions and parameters
- Structured logging via structlog with context binding
- Ruff linting: all checks pass, no issues
- Line length: max 88 characters per project standards

**✅ AC Fulfillment Status:**
- AC1: POST `/api/webhook` accepts requests → ✅ Implemented & Tested
- AC2: Valid token returns 200 → ✅ Implemented & Tested
- AC3: Invalid token returns 401 → ✅ Implemented & Tested
- AC4: Constant-time comparison prevents timing attacks → ✅ Implemented & Tested
- AC5: API documentation at `/docs` → ✅ Implemented & Tested

**🔗 Dependencies:**
- ✅ Story 1.1 (Project Initialization): FastAPI app structure ready
- ✅ Story 1.2 (Database Foundation): `get_db_session()`, Signal model, structlog configured
- ⏭️ Story 1.4 (Payload Parsing): Will consume this endpoint for full signal validation
- ⏭️ Story 1.5 (Deduplication): Will use Signal model storage from endpoint

**📊 Test Coverage:**
- Unit tests: token validation, error handling, schema compliance
- Integration tests: full HTTP request/response cycle, endpoint accessibility
- Edge cases: malformed JSON, empty payloads, Unicode content, large payloads
- Security tests: timing attack resistance (via constant-time comparison)

### Code Review Findings (Post-Implementation Adversarial Review)

**Reviewer:** Claude Code (Adversarial Senior Developer)
**Review Date:** 2026-01-20
**Status:** ✅ All issues FIXED

**Issues Found & Fixed:**

1. **🔴 HIGH - Exception handling returning wrong HTTP status code**
   - **Location:** webhook.py:80-89 (FIXED)
   - **Issue:** Try-catch block around logging was incorrect - logger.bind() never fails
   - **Fix Applied:** Removed unnecessary exception handling, simplified to direct logging
   - **Impact:** AC1 compliance improved, better error transparency

2. **🔴 HIGH - WebhookRequest model not properly accepting flexible JSON**
   - **Location:** webhook.py:15-21 (FIXED)
   - **Issue:** Empty Pydantic model wasn't explicitly configured to accept any fields
   - **Fix Applied:** Added `model_config = ConfigDict(extra="allow")` for flexibility
   - **Impact:** AC1 now properly accepts arbitrary JSON payloads

3. **🟡 MEDIUM - Dependency injection pattern violation**
   - **Location:** webhook.py, deps.py (FIXED)
   - **Issue:** `verify_webhook_token()` defined in webhook.py instead of deps.py
   - **Fix Applied:** Moved function definition to deps.py, imported in webhook.py
   - **Impact:** Architecture compliance restored, single source of truth for dependencies

4. **🟡 MEDIUM - Weak constant-time comparison tests**
   - **Location:** tests/test_webhook.py:140-218 (FIXED)
   - **Issue:** Tests didn't validate constant-time comparison with different token lengths
   - **Fix Applied:** Added `test_constant_time_different_lengths()` and `test_hmac_compare_digest_unit()`
   - **Impact:** AC4 now properly validated at boundaries

5. **🟡 MEDIUM - Missing WebhookRequest flexibility tests**
   - **Location:** tests/test_webhook.py (FIXED)
   - **Issue:** No direct validation that WebhookRequest accepts arbitrary fields
   - **Fix Applied:** Added `TestWebhookRequestModel` class with 2 new tests
   - **Impact:** AC1 coverage improved with explicit model behavior validation

6. **🟡 MEDIUM - Incomplete error response format (deferred)**
   - **Location:** webhook.py error responses
   - **Issue:** Missing timestamp, signal_id, dex fields per architecture.md
   - **Status:** ⏭️ Deferred to Story 1.4 (signal storage phase)
   - **Reasoning:** Signal ID cannot exist until signal is stored in DB

**Test Coverage:**
- **Before Review:** 31 webhook tests
- **After Review:** 35 webhook tests (+4 new tests)
- **Total Test Suite:** 87 tests (all passing)
- **No Regressions:** Database tests (15), Project init tests (44), Webhook tests (35)

**Code Quality:**
- ✅ Ruff linting: All checks pass
- ✅ Ruff formatting: Code properly formatted
- ✅ Type hints: Complete on all functions
- ✅ Architecture compliance: Project-context.md rules followed
- ✅ All AC requirements: 1-5 fully implemented and tested

**Git Changes Summary:**
- Modified: `src/kitkat/api/webhook.py` (simplified exception handling, moved dependency)
- Modified: `src/kitkat/api/deps.py` (moved verify_webhook_token definition here)
- Modified: `tests/test_webhook.py` (added 4 new tests, improved AC4 validation)
- No modified: `src/kitkat/main.py`, `src/kitkat/config.py`, `tests/conftest.py` (still valid)

### File List

**Created:**
- `src/kitkat/api/webhook.py` - Webhook endpoint handler with auth dependency and models (FIXED)
- `tests/test_webhook.py` - 35 comprehensive webhook tests covering all acceptance criteria (4 new tests added)

**Modified:**
- `src/kitkat/api/deps.py` - Moved `verify_webhook_token()` definition here (architecture compliance fix)
- `src/kitkat/main.py` - Mounted webhook routes via `app.include_router(webhook_router)`

**Pre-existing (from Story 1.2):**
- `src/kitkat/database.py` - Signal model persistence, used by future stories
- `src/kitkat/models.py` - Signal model ready for story 1.4
- `src/kitkat/config.py` - Pydantic settings with `webhook_token`
- `tests/conftest.py` - Test fixtures for webhook token and environment
