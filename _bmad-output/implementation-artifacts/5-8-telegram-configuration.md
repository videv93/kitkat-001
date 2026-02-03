# Story 5.8: Telegram Configuration

Status: done

## Story

As a **user**,
I want **to configure my Telegram alert destination**,
So that **I receive alerts in my preferred chat**.

## Acceptance Criteria

1. **Given** an authenticated user, **When** they call `GET /api/config/telegram`, **Then** the response includes:
```json
{
  "configured": true,
  "chat_id": "123456789",
  "bot_status": "connected",
  "test_available": true
}
```

2. **Given** an authenticated user, **When** they call `PUT /api/config/telegram` with:
```json
{
  "chat_id": "123456789"
}
```
**Then** the chat ID is saved to `users.config_data`
**And** a test message is sent to verify the configuration

3. **Given** Telegram configuration, **When** the test message is sent, **Then** it contains: "✅ kitkat-001 alerts configured successfully!"
**And** the response indicates success or failure

4. **Given** an invalid chat ID, **When** configuration is attempted, **Then** the test message fails
**And** the response includes: `{"error": "Failed to send test message - check chat ID"}`
**And** the configuration is NOT saved

5. **Given** Telegram not configured, **When** the config endpoint is called, **Then** `configured: false` is returned
**And** setup instructions are included

6. **Given** the system bot token, **When** Telegram is configured per-user, **Then** the bot token is system-wide (from env)
**And** only the chat_id is user-configurable
**And** users cannot see or modify the bot token

## Tasks / Subtasks

- [x] Task 1: Create Pydantic models for Telegram config (AC: #1, #5)
  - [x] 1.1 Create `TelegramConfigResponse` model with fields: `configured`, `chat_id`, `bot_status`, `test_available`
  - [x] 1.2 Create `TelegramConfigUpdate` model with `chat_id` field
  - [x] 1.3 Add field descriptions and validation (chat_id must be non-empty string)

- [x] Task 2: Implement GET /api/config/telegram endpoint (AC: #1, #5, #6)
  - [x] 2.1 Add route to `api/config.py` router
  - [x] 2.2 Load user's `config_data` from database to check for existing `telegram_chat_id`
  - [x] 2.3 Check bot status by calling `settings.telegram_bot_token` existence check
  - [x] 2.4 Return `configured: false` with setup instructions if not configured
  - [x] 2.5 Return `configured: true` with chat_id (if configured)
  - [x] 2.6 Set `test_available: true` when bot token is configured in environment

- [x] Task 3: Implement PUT /api/config/telegram endpoint (AC: #2, #3, #4)
  - [x] 3.1 Add route to `api/config.py` router with `TelegramConfigUpdate` body
  - [x] 3.2 Validate chat_id is non-empty
  - [x] 3.3 Send test message using `TelegramAlertService` before saving
  - [x] 3.4 If test succeeds: save chat_id to `users.config_data.telegram_chat_id`
  - [x] 3.5 If test fails: return 400 with error message, do NOT save config
  - [x] 3.6 Return success response with new configuration

- [x] Task 4: Update TelegramAlertService for user-specific chat (AC: #3)
  - [x] 4.1 Review existing `services/alert.py` implementation
  - [x] 4.2 Add method `send_test_message(chat_id: str) -> bool` for config verification
  - [x] 4.3 Test message content: "✅ kitkat-001 alerts configured successfully!"
  - [x] 4.4 Return True on success, False on failure (catch exceptions)

- [x] Task 5: Write comprehensive tests (AC: #1-6)
  - [x] 5.1 Test GET returns `configured: false` for new user without telegram config
  - [x] 5.2 Test GET returns `configured: true` with chat_id for configured user
  - [x] 5.3 Test GET includes setup instructions when not configured
  - [x] 5.4 Test PUT saves chat_id when test message succeeds
  - [x] 5.5 Test PUT returns 400 when test message fails (invalid chat_id)
  - [x] 5.6 Test PUT does NOT save config when test fails
  - [x] 5.7 Test authentication required for both endpoints
  - [x] 5.8 Test bot_status reflects actual bot configuration
  - [x] 5.9 Mock TelegramAlertService.send_test_message in tests

## Dev Notes

### Architecture Patterns (MUST FOLLOW)

**From Project Context (CRITICAL):**
- **File Location**: Add to existing `src/kitkat/api/config.py` router (like Story 5.6 and 5.7)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Use absolute imports from `kitkat.*` package
- **Async**: ALL database operations must be async
- **Logging**: Use `structlog.get_logger()` with bound context
- **Pydantic V2**: Use `model_config = ConfigDict(...)` syntax, NOT `class Config`

**CRITICAL: User-Specific vs System-Wide Configuration**
- Bot token (`TELEGRAM_BOT_TOKEN`) is system-wide from environment
- Chat ID is user-specific, stored in `users.config_data`
- Users NEVER see or modify the bot token
- This allows multi-tenant operation with single bot

### Existing Implementation Context

**TelegramAlertService (services/alert.py):**
From Story 4.2, the alert service already exists with:
```python
class TelegramAlertService:
    """Sends alerts via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token) if bot_token else None

    async def send_alert(self, message: str) -> bool:
        """Send alert message. Returns True on success, False on failure."""
        # ... implementation exists ...
```

**Adaptation Required:**
- Add `send_test_message(chat_id: str) -> bool` method
- This allows testing with a specific chat_id before saving
- The test message should use the provided chat_id, not the default

### User Model Context

**From Story 2.2 (User & Session Management):**
```python
class User(Base):
    __tablename__ = "users"
    id: int
    wallet_address: str
    config_data: dict  # JSON field for user preferences
    created_at: datetime
```

**config_data Structure:**
```python
{
    "webhook_token": "abc123...",       # Story 2.4
    "position_size": "0.5",             # Story 5.6
    "max_position_size": "10.0",        # Story 5.6
    "telegram_chat_id": "123456789",    # Story 5.8 (NEW)
}
```

### Pydantic Models to Add (models.py)

```python
class TelegramConfigResponse(BaseModel):
    """Response for GET /api/config/telegram."""
    model_config = ConfigDict(str_strip_whitespace=True)

    configured: bool = Field(
        ...,
        description="Whether Telegram alerts are configured for this user"
    )
    chat_id: str | None = Field(
        default=None,
        description="User's Telegram chat ID (null if not configured)"
    )
    bot_status: str = Field(
        ...,
        description="Bot connection status: 'connected', 'not_configured', or 'error'"
    )
    test_available: bool = Field(
        ...,
        description="Whether test message can be sent (bot token configured)"
    )
    setup_instructions: str | None = Field(
        default=None,
        description="Instructions for setting up Telegram (shown when not configured)"
    )


class TelegramConfigUpdate(BaseModel):
    """Request body for PUT /api/config/telegram."""
    model_config = ConfigDict(str_strip_whitespace=True)

    chat_id: str = Field(
        ...,
        min_length=1,
        description="Telegram chat ID to receive alerts"
    )
```

### API Implementation (api/config.py)

**GET /api/config/telegram:**
```python
@router.get("/telegram", response_model=TelegramConfigResponse)
async def get_telegram_config(
    current_user: CurrentUser = Depends(get_current_user),
) -> TelegramConfigResponse:
    """
    Retrieve Telegram configuration for authenticated user (Story 5.8: AC#1, #5).
    """
    log = logger.bind(user_id=current_user.id)

    # Check if bot token is configured system-wide
    bot_configured = bool(settings.telegram_bot_token)

    # Check user's telegram configuration
    config_data = current_user.config_data or {}
    chat_id = config_data.get("telegram_chat_id")
    configured = bool(chat_id)

    # Determine bot status
    if not bot_configured:
        bot_status = "not_configured"
    else:
        bot_status = "connected"  # Assume connected if token exists

    # Setup instructions when not configured
    setup_instructions = None
    if not configured:
        setup_instructions = (
            "To configure Telegram alerts:\n"
            "1. Start a chat with @kitkat001_bot on Telegram\n"
            "2. Send /start to the bot\n"
            "3. Copy your chat ID from the bot's response\n"
            "4. Use PUT /api/config/telegram with your chat_id"
        )

    log.info(
        "Telegram config retrieved",
        configured=configured,
        bot_status=bot_status,
    )

    return TelegramConfigResponse(
        configured=configured,
        chat_id=chat_id,
        bot_status=bot_status,
        test_available=bot_configured,
        setup_instructions=setup_instructions,
    )
```

**PUT /api/config/telegram:**
```python
@router.put("/telegram", response_model=TelegramConfigResponse)
async def update_telegram_config(
    update: TelegramConfigUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelegramConfigResponse:
    """
    Update Telegram configuration for authenticated user (Story 5.8: AC#2, #3, #4).

    Sends a test message before saving. If test fails, config is NOT saved.
    """
    log = logger.bind(user_id=current_user.id, chat_id=update.chat_id)

    # Check bot token is configured
    if not settings.telegram_bot_token:
        log.warning("Telegram bot token not configured")
        raise HTTPException(
            status_code=503,
            detail="Telegram bot not configured on server"
        )

    # Send test message to verify chat_id
    alert_service = TelegramAlertService(
        bot_token=settings.telegram_bot_token,
        chat_id=update.chat_id,
    )

    test_success = await alert_service.send_test_message()

    if not test_success:
        log.warning("Test message failed", chat_id=update.chat_id)
        raise HTTPException(
            status_code=400,
            detail="Failed to send test message - check chat ID"
        )

    # Test succeeded - save configuration
    config_data = dict(current_user.config_data or {})
    config_data["telegram_chat_id"] = update.chat_id

    # Update user in database
    current_user.config_data = config_data
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    log.info("Telegram configuration updated successfully")

    return TelegramConfigResponse(
        configured=True,
        chat_id=update.chat_id,
        bot_status="connected",
        test_available=True,
        setup_instructions=None,
    )
```

### TelegramAlertService Update (services/alert.py)

**Add send_test_message method:**
```python
async def send_test_message(self) -> bool:
    """
    Send a test message to verify Telegram configuration.

    Returns True if message sent successfully, False otherwise.
    """
    if not self.bot:
        return False

    try:
        await self.bot.send_message(
            chat_id=self.chat_id,
            text="✅ kitkat-001 alerts configured successfully!",
        )
        return True
    except Exception as e:
        logger.warning(
            "Test message failed",
            chat_id=self.chat_id,
            error=str(e),
        )
        return False
```

### Testing Patterns

**Test File: tests/api/test_config.py**

Add tests alongside existing 5.6 and 5.7 tests:

```python
# =====================================================
# Story 5.8: Telegram Configuration Tests
# =====================================================

@pytest.mark.asyncio
async def test_get_telegram_config_not_configured(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#5: Returns configured=false for new user."""
    response = await async_client.get(
        "/api/config/telegram",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["configured"] is False
    assert data["chat_id"] is None
    assert "setup_instructions" in data
    assert data["setup_instructions"] is not None


@pytest.mark.asyncio
async def test_get_telegram_config_configured(
    async_client: AsyncClient,
    authenticated_headers: dict,
    user_with_telegram_config: User,  # Fixture with telegram_chat_id set
):
    """Test AC#1: Returns configured=true with chat_id."""
    response = await async_client.get(
        "/api/config/telegram",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["configured"] is True
    assert data["chat_id"] == "123456789"
    assert data["setup_instructions"] is None


@pytest.mark.asyncio
async def test_put_telegram_config_success(
    async_client: AsyncClient,
    authenticated_headers: dict,
    mock_telegram_alert_service,  # Mocks send_test_message to return True
):
    """Test AC#2, #3: PUT saves chat_id when test succeeds."""
    response = await async_client.put(
        "/api/config/telegram",
        headers=authenticated_headers,
        json={"chat_id": "123456789"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["configured"] is True
    assert data["chat_id"] == "123456789"

    # Verify test message was called
    mock_telegram_alert_service.send_test_message.assert_called_once()


@pytest.mark.asyncio
async def test_put_telegram_config_test_fails(
    async_client: AsyncClient,
    authenticated_headers: dict,
    mock_telegram_alert_service_fails,  # Mocks send_test_message to return False
):
    """Test AC#4: PUT returns 400 when test fails."""
    response = await async_client.put(
        "/api/config/telegram",
        headers=authenticated_headers,
        json={"chat_id": "invalid_chat_id"},
    )
    assert response.status_code == 400
    data = response.json()

    assert "Failed to send test message" in data["detail"]


@pytest.mark.asyncio
async def test_put_telegram_config_not_saved_on_failure(
    async_client: AsyncClient,
    authenticated_headers: dict,
    mock_telegram_alert_service_fails,
    db: AsyncSession,
):
    """Test AC#4: Config is NOT saved when test fails."""
    # Attempt configuration with failing test
    await async_client.put(
        "/api/config/telegram",
        headers=authenticated_headers,
        json={"chat_id": "invalid_chat_id"},
    )

    # Verify config was NOT saved
    response = await async_client.get(
        "/api/config/telegram",
        headers=authenticated_headers,
    )
    data = response.json()
    assert data["configured"] is False


@pytest.mark.asyncio
async def test_telegram_config_requires_auth(
    async_client: AsyncClient,
):
    """Test authentication required for telegram endpoints."""
    # GET without auth
    response = await async_client.get("/api/config/telegram")
    assert response.status_code == 401

    # PUT without auth
    response = await async_client.put(
        "/api/config/telegram",
        json={"chat_id": "123456789"},
    )
    assert response.status_code == 401
```

### Previous Story Intelligence

**From Story 5.7 (Webhook URL Display):**
- Same router in `api/config.py`
- Same auth dependency pattern
- Same test patterns with authenticated_headers fixture
- Model additions in `models.py`
- Tests in `tests/api/test_config.py`

**From Story 4.2 (Telegram Alert Service):**
- TelegramAlertService exists in `services/alert.py`
- Uses `python-telegram-bot` library
- Fire-and-forget pattern for alerts
- Bot token from environment

### Git Intelligence

**Recent commits:**
- `Story 5.6 & 5.7: Position Size Configuration & Webhook URL Display`
- `Epic 4 & 5: Multiple story implementations`
- `Story 4.5: Error Log Viewer - Implementation Complete`

**Follow same commit message pattern:**
- `Story 5.8: Telegram Configuration - Implementation Complete`

### Error Handling

| Scenario | HTTP Status | Error Message |
|----------|-------------|---------------|
| Not authenticated | 401 | "Not authenticated" |
| Bot token not configured | 503 | "Telegram bot not configured on server" |
| Test message fails | 400 | "Failed to send test message - check chat ID" |
| Empty chat_id | 422 | Pydantic validation error |

### Security Considerations

- Bot token is NEVER exposed to users (system-wide secret)
- Users can only configure their own chat_id
- Test message verifies user has access to the chat
- Chat ID validation via actual message delivery (not just format check)

### Performance Considerations

- GET endpoint: Single database query (current_user already loaded)
- PUT endpoint: One external API call (Telegram) + one database write
- Telegram API call is async, non-blocking
- No caching needed for config data

### Dependencies

**Story 5.8 depends on:**
- Story 2.2: User model with config_data field
- Story 4.2: TelegramAlertService implementation

**No stories depend on 5.8** - it's the last story in Epic 5.

### Project Structure Notes

**Files to Modify:**
- `src/kitkat/models.py` - Add `TelegramConfigResponse` and `TelegramConfigUpdate` models
- `src/kitkat/api/config.py` - Add GET and PUT endpoints for `/telegram`
- `src/kitkat/services/alert.py` - Add `send_test_message` method

**Test Files to Modify:**
- `tests/api/test_config.py` - Add Telegram configuration tests
- `tests/conftest.py` - Add fixtures for mocking TelegramAlertService

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.8] - Story requirements
- [Source: _bmad-output/planning-artifacts/prd.md#FR48] - Configure Telegram destination
- [Source: _bmad-output/planning-artifacts/architecture.md] - Alert service pattern
- [Source: _bmad-output/project-context.md] - Coding standards and patterns
- [Source: src/kitkat/services/alert.py] - Existing TelegramAlertService
- [Source: src/kitkat/api/config.py] - Existing config router
- [Source: src/kitkat/models.py] - User model with config_data
- [Source: 5-7-webhook-url-payload-display.md] - Previous story patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All tests pass: `uv run pytest tests/api/test_config.py -v` (27 passed)

### Completion Notes List

- Implemented GET /api/config/telegram endpoint with setup instructions for unconfigured users
- Implemented PUT /api/config/telegram endpoint with test message verification before saving
- Added TelegramAlertService.send_test_message() method for configuration validation
- Bot token remains system-wide (AC#6), only chat_id is user-configurable
- Test message sends "✅ kitkat-001 alerts configured successfully!" per AC#3
- Config not saved if test message fails (AC#4)
- 10 comprehensive tests covering all acceptance criteria

### File List

- src/kitkat/models.py (modified) - Added TelegramConfigResponse and TelegramConfigUpdate models
- src/kitkat/api/config.py (modified) - Added GET and PUT /api/config/telegram endpoints
- src/kitkat/services/alert.py (modified) - Added send_test_message() method
- tests/api/test_config.py (modified) - Added 10 tests for Story 5.8

### Change Log

- 2026-02-03: Code review completed, story documentation updated (Claude Opus 4.5)

