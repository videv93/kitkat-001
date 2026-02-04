# Story 5.7: Webhook URL & Payload Display

Status: done

## Story

As a **user**,
I want **to view my webhook URL and expected payload format**,
So that **I can configure TradingView alerts correctly**.

## Acceptance Criteria

1. **Given** an authenticated user, **When** they call `GET /api/config/webhook`, **Then** the response includes:
```json
{
  "webhook_url": "https://kitkat.example.com/api/webhook?token=abc123...",
  "payload_format": {
    "required_fields": ["symbol", "side", "size"],
    "optional_fields": ["price", "order_type"],
    "example": {
      "symbol": "ETH-PERP",
      "side": "buy",
      "size": "{{strategy.position_size}}"
    }
  },
  "tradingview_setup": {
    "alert_name": "kitkat-001 Signal",
    "webhook_url": "https://kitkat.example.com/api/webhook?token=abc123...",
    "message_template": "{\"symbol\": \"{{ticker}}\", \"side\": \"{{strategy.order.action}}\", \"size\": \"{{strategy.position_size}}\"}"
  }
}
```

2. **Given** the webhook URL display, **When** shown to user, **Then** it includes the full URL with their unique token **And** a "Copy" indicator suggests it can be copied

3. **Given** the payload format, **When** displayed, **Then** it shows required vs optional fields **And** includes a working example

4. **Given** TradingView setup instructions, **When** displayed, **Then** it provides ready-to-paste values for TradingView alert configuration

5. **Given** the webhook token, **When** displayed in the URL, **Then** only the first 8 characters are shown, rest replaced with "..." **And** a "Reveal" option shows the full token

## Tasks / Subtasks

- [x] Task 1: Verify existing implementation (AC: #1, #3, #4)
  - [x] 1.1 Review existing `GET /api/config/webhook` endpoint in `api/config.py`
  - [x] 1.2 Verify response includes all required fields from AC#1
  - [x] 1.3 Confirm payload_format includes required_fields and optional_fields
  - [x] 1.4 Confirm tradingview_setup includes ready-to-paste message_template

- [x] Task 2: Add token abbreviation with reveal capability (AC: #5)
  - [x] 2.1 Add `token_abbreviated` field to response showing first 8 chars + "..."
  - [x] 2.2 Keep full webhook_url for backend use (won't change)
  - [x] 2.3 Add `token_display` field with abbreviated version: `abc12345...`
  - [x] 2.4 Decision: Reveal is a UI concern - backend returns full token, client handles display

- [x] Task 3: Update Pydantic models for enhanced response (AC: #2, #5)
  - [x] 3.1 Add `token_display` field to `WebhookConfigResponse` model
  - [x] 3.2 Add description clarifying token abbreviation format
  - [x] 3.3 Ensure backward compatibility with existing fields

- [x] Task 4: Implement token abbreviation logic (AC: #5)
  - [x] 4.1 Extract token from webhook_url or current_user.webhook_token
  - [x] 4.2 Create abbreviated display: first 8 chars + "..."
  - [x] 4.3 Add to response alongside full webhook_url

- [x] Task 5: Write/update tests (AC: #1-5)
  - [x] 5.1 Test endpoint returns all required fields from AC#1
  - [x] 5.2 Test payload_format contains required_fields and optional_fields
  - [x] 5.3 Test tradingview_setup contains ready-to-paste message
  - [x] 5.4 Test token_display shows abbreviated format (8 chars + "...")
  - [x] 5.5 Test authentication required (401 without session)
  - [x] 5.6 Test 500 error when webhook token not configured

## Dev Notes

### Architecture Patterns (MUST FOLLOW)

**From Project Context:**
- **File Location**: Existing `src/kitkat/api/config.py` already has the endpoint
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Use absolute imports from `kitkat.*` package
- **Async**: ALL database operations must be async
- **Logging**: Use `structlog.get_logger()` with bound context

**CRITICAL: Existing Implementation Status**
The `GET /api/config/webhook` endpoint already exists and implements most of AC#1-4. The main gap is AC#5 (token abbreviation with reveal option).

### Existing Implementation (api/config.py lines 79-141)

```python
@router.get("/webhook", response_model=WebhookConfigResponse)
async def get_webhook_config(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookConfigResponse:
    """
    Retrieve webhook URL and configuration for authenticated user (Story 2.4: AC2).
    """
    # ... implementation already exists ...
```

**What Already Works:**
- Full webhook URL with user's unique token
- Payload format with required_fields and optional_fields
- TradingView setup with ready-to-paste message_template
- Authentication via `get_current_user` dependency

**What Needs Addition (AC#5):**
- Token abbreviation (first 8 chars + "...")
- The "reveal" option is a UI/client-side concern - backend always returns full token

### Pydantic Models (models.py)

**Existing models (lines 391-426):**
```python
class PayloadFormat(BaseModel):
    required_fields: list[str]
    optional_fields: list[str]
    example: dict

class TradingViewSetup(BaseModel):
    alert_name: str
    webhook_url: str
    message_template: str

class WebhookConfigResponse(BaseModel):
    webhook_url: str
    payload_format: PayloadFormat
    tradingview_setup: TradingViewSetup
```

**Add to WebhookConfigResponse:**
```python
class WebhookConfigResponse(BaseModel):
    # Existing fields
    webhook_url: str
    payload_format: PayloadFormat
    tradingview_setup: TradingViewSetup

    # New field for AC#5
    token_display: str = Field(
        ...,
        description="Abbreviated token for display (first 8 chars + '...')"
    )
```

### Implementation Changes

**Update api/config.py:**
```python
# Add after building response, before return:

# Token abbreviation for display (AC#5)
token = current_user.webhook_token
token_display = f"{token[:8]}..." if len(token) > 8 else token

return WebhookConfigResponse(
    webhook_url=webhook_url,
    payload_format=payload_format,
    tradingview_setup=tradingview_setup,
    token_display=token_display,  # NEW
)
```

### Design Decision: Reveal Option

**AC#5 states:** "a 'Reveal' option shows the full token"

**Implementation Approach:**
- Backend always returns the full token in `webhook_url` field
- Backend also returns `token_display` with abbreviated version
- Client-side UI handles the toggle between abbreviated and full display
- This is a display concern, not API logic
- No additional endpoint needed - single response serves both needs

### Testing Patterns

**Create/Update tests/api/test_config.py:**
```python
@pytest.mark.asyncio
async def test_webhook_config_returns_all_fields(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#1: GET /api/config/webhook returns complete structure."""
    response = await async_client.get(
        "/api/config/webhook",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all required fields
    assert "webhook_url" in data
    assert "payload_format" in data
    assert "tradingview_setup" in data
    assert "token_display" in data  # NEW for AC#5

    # Verify payload_format structure
    pf = data["payload_format"]
    assert "required_fields" in pf
    assert "optional_fields" in pf
    assert "example" in pf
    assert pf["required_fields"] == ["symbol", "side", "size"]

    # Verify tradingview_setup structure
    ts = data["tradingview_setup"]
    assert "alert_name" in ts
    assert "webhook_url" in ts
    assert "message_template" in ts


@pytest.mark.asyncio
async def test_token_display_abbreviated(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#5: token_display shows first 8 chars + '...'"""
    response = await async_client.get(
        "/api/config/webhook",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Token display should be abbreviated
    token_display = data["token_display"]
    assert token_display.endswith("...")
    assert len(token_display) == 11  # 8 chars + "..."

    # Full token should be in webhook_url
    assert data["webhook_url"].split("token=")[1] != token_display


@pytest.mark.asyncio
async def test_webhook_config_requires_auth(
    async_client: AsyncClient,
):
    """Test authentication required for webhook config."""
    response = await async_client.get("/api/config/webhook")
    assert response.status_code == 401
```

### Previous Story Intelligence

**From Story 5.6 (Position Size Configuration):**
- Same router pattern in `api/config.py`
- Same auth dependency: `Depends(get_current_user)`
- Same database session pattern: `Depends(get_db)`
- Test patterns with authenticated_headers fixture
- All tests in `tests/api/test_config.py`

**From Story 2.4 (Webhook URL Generation):**
- Original implementation of webhook URL display
- WebhookConfigResponse model created
- PayloadFormat and TradingViewSetup models created

### Git Intelligence

Recent commits follow naming convention:
- `Story 5.1: Stats Service & Volume Tracking - Implementation Complete`
- `Story 4.5: Error Log Viewer - Implementation Complete`

**Follow same pattern for this story's commits.**

### Error Handling

- Return 401 if not authenticated (handled by `get_current_user` dependency)
- Return 500 if webhook token not configured for user
- No validation needed for read-only endpoint

### Performance Considerations

- Single database query via `get_current_user` dependency
- No additional queries needed - all data from current_user context
- Very lightweight endpoint

### Security Considerations

- Users can only access their own webhook configuration
- Full token returned in response (client can choose to display abbreviated)
- HTTPS required for transport security
- Token is 128-bit random (high entropy)

### Project Structure Notes

**Files to Modify:**
- `src/kitkat/models.py` - Add `token_display` field to `WebhookConfigResponse`
- `src/kitkat/api/config.py` - Add `token_display` calculation to response

**Test Files to Modify:**
- `tests/api/test_config.py` - Add tests for webhook config endpoint

### Implementation Priority

This story is **mostly complete** from Story 2.4. Remaining work:
1. Add `token_display` field to Pydantic model
2. Calculate abbreviated token in endpoint
3. Add/update tests for the new field

**Estimated effort: Low** - primarily adding one field and minor tests.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.7]
- [Source: _bmad-output/planning-artifacts/prd.md#FR46] - View webhook URL
- [Source: _bmad-output/planning-artifacts/prd.md#FR47] - View payload format
- [Source: _bmad-output/planning-artifacts/architecture.md] - API patterns
- [Source: src/kitkat/api/config.py] - Existing implementation (lines 79-141)
- [Source: src/kitkat/models.py] - WebhookConfigResponse model (lines 391-426)
- [Source: 5-6-position-size-configuration.md] - Previous story patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No debugging issues encountered.

### Completion Notes List

- Task 1 was already complete (verification of existing implementation)
- Task 2-4: Added `token_display` field with abbreviated token format (first 8 chars + "...")
- Task 5: Tests already written in `tests/api/test_config.py` - all 5 webhook config tests pass
- Total 17 tests in test_config.py now cover both Story 5.6 and 5.7
- Implementation was minimal - only added one field to model and one calculation to endpoint

### File List

**Modified Files:**
- `src/kitkat/models.py` - Added `token_display` field to `WebhookConfigResponse` model
- `src/kitkat/api/config.py` - Added token abbreviation calculation to `get_webhook_config` endpoint
- `tests/api/test_config.py` - Added 5 webhook config tests for Story 5.7 ACs

### Change Log

- 2026-02-04: **Code Review PASSED** - All issues fixed:
  - C1: Committed all previously uncommitted code review fixes
  - M1: Fixed example payload to use TradingView placeholder syntax `{{strategy.position_size}}`
  - M2: Added test assertions to verify TradingView placeholder values
  - L2: Updated docstring to reference Story 5.7
  - Fixed test mocking to use FastAPI dependency_overrides instead of patch
- 2026-02-03: Code review fixes applied:
  - Added missing test for 500 error when webhook_token not configured (H1)
  - Fixed test edge case handling for short webhook tokens (H2)
  - Removed partial token exposure from log output (M2)
  - Updated File List to include test file (M1)
- 2026-02-02: Story 5.7 implementation completed - Added token_display field for abbreviated webhook token display

