"""Tests for configuration API endpoints (Story 5.6, 5.7, 5.8)."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


# ============================================================================
# Webhook Config Tests (Story 5.7)
# ============================================================================


@pytest.mark.asyncio
async def test_webhook_config_returns_all_fields(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#1: GET /api/config/webhook returns complete structure."""
    response = await async_client.get(
        "/api/config/webhook",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all required fields
    assert "webhook_url" in data
    assert "payload_format" in data
    assert "tradingview_setup" in data
    assert "token_display" in data  # AC#5

    # Verify payload_format structure (AC#3)
    pf = data["payload_format"]
    assert "required_fields" in pf
    assert "optional_fields" in pf
    assert "example" in pf
    assert pf["required_fields"] == ["symbol", "side", "size"]
    assert pf["optional_fields"] == ["price", "order_type"]

    # Verify tradingview_setup structure (AC#4)
    ts = data["tradingview_setup"]
    assert "alert_name" in ts
    assert "webhook_url" in ts
    assert "message_template" in ts


@pytest.mark.asyncio
async def test_webhook_config_token_display_abbreviated(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#5: token_display shows first 8 chars + '...'"""
    response = await async_client.get(
        "/api/config/webhook",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()

    # Token display should be abbreviated
    token_display = data["token_display"]
    assert token_display.endswith("...")
    assert len(token_display) == 11  # 8 chars + "..."

    # Full token should be in webhook_url (extractable)
    full_token = data["webhook_url"].split("token=")[1]
    assert len(full_token) > 11  # Full token is longer than abbreviated
    assert token_display[:8] == full_token[:8]  # First 8 chars match


@pytest.mark.asyncio
async def test_webhook_config_requires_authentication(
    async_client: AsyncClient,
):
    """Test: GET /api/config/webhook requires authentication."""
    response = await async_client.get("/api/config/webhook")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_config_tradingview_message_template(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#4: TradingView setup contains ready-to-paste message."""
    response = await async_client.get(
        "/api/config/webhook",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()

    ts = data["tradingview_setup"]

    # Message template should be valid JSON
    import json
    template = json.loads(ts["message_template"])
    assert "symbol" in template
    assert "side" in template
    assert "size" in template


@pytest.mark.asyncio
async def test_webhook_config_url_contains_token(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#2: webhook_url includes user's unique token."""
    response = await async_client.get(
        "/api/config/webhook",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()

    # URL should contain token query param
    assert "?token=" in data["webhook_url"]
    # URL should contain user's webhook token
    assert authenticated_user["webhook_token"] in data["webhook_url"]


# ============================================================================
# Position Size Config Tests (Story 5.6)
# ============================================================================


@pytest.mark.asyncio
async def test_get_config_returns_correct_structure(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#1: GET /api/config returns all required fields."""
    response = await async_client.get(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all required fields
    assert "position_size" in data
    assert "max_position_size" in data
    assert "position_size_unit" in data

    # Verify types
    assert isinstance(data["position_size"], str)
    assert isinstance(data["max_position_size"], str)
    assert data["position_size_unit"] == "ETH"


@pytest.mark.asyncio
async def test_get_config_returns_defaults_when_not_configured(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#6: Defaults applied when not configured."""
    response = await async_client.get(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()

    # Check defaults (AC#6)
    assert data["position_size"] == "0.1"
    assert data["max_position_size"] == "10.0"


@pytest.mark.asyncio
async def test_put_config_updates_values(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#2: PUT /api/config updates and returns new values."""
    response = await async_client.put(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={
            "position_size": "1.0",
            "max_position_size": "5.0",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["position_size"] == "1.0"
    assert data["max_position_size"] == "5.0"

    # Verify persistence by fetching again
    get_response = await async_client.get(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    get_data = get_response.json()
    assert get_data["position_size"] == "1.0"
    assert get_data["max_position_size"] == "5.0"


@pytest.mark.asyncio
async def test_put_config_validates_position_size_positive(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#3: position_size must be > 0."""
    response = await async_client.put(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={"position_size": "-1.0"},
    )
    # App converts Pydantic validation errors to 400 per project standards
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_put_config_validates_position_size_zero(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#3: position_size must be > 0 (zero not allowed)."""
    response = await async_client.put(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={"position_size": "0"},
    )
    # App converts Pydantic validation errors to 400 per project standards
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_put_config_validates_max_not_exceed_system_limit(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#4: max_position_size must be <= 100."""
    response = await async_client.put(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={"max_position_size": "150.0"},
    )
    # App converts Pydantic validation errors to 400 per project standards
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_put_config_cross_validates_size_vs_max(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#3: position_size cannot exceed max_position_size."""
    response = await async_client.put(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={
            "position_size": "20.0",
            "max_position_size": "5.0",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "INVALID_CONFIG" in str(data.get("detail", data))


@pytest.mark.asyncio
async def test_put_config_partial_update_position_size_only(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#2: Partial update - only position_size."""
    # First set known values
    await async_client.put(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={"position_size": "2.0", "max_position_size": "8.0"},
    )

    # Update only position_size
    response = await async_client.put(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={"position_size": "3.0"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["position_size"] == "3.0"
    assert data["max_position_size"] == "8.0"  # Unchanged


@pytest.mark.asyncio
async def test_put_config_partial_update_max_only(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#2: Partial update - only max_position_size."""
    # First set known values
    await async_client.put(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={"position_size": "2.0", "max_position_size": "8.0"},
    )

    # Update only max_position_size
    response = await async_client.put(
        "/api/config",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={"max_position_size": "15.0"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["position_size"] == "2.0"  # Unchanged
    assert data["max_position_size"] == "15.0"


@pytest.mark.asyncio
async def test_get_config_requires_authentication(
    async_client: AsyncClient,
):
    """Test: GET /api/config requires authentication."""
    response = await async_client.get("/api/config")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_put_config_requires_authentication(
    async_client: AsyncClient,
):
    """Test: PUT /api/config requires authentication."""
    response = await async_client.put(
        "/api/config",
        json={"position_size": "1.0"},
    )
    assert response.status_code == 401


# ============================================================================
# Task 7.9: Test new user gets default values (AC#6)
# ============================================================================


@pytest.mark.asyncio
async def test_new_user_gets_default_position_size_values(db_session):
    """Test AC#6: New users get default position_size values."""
    from kitkat.services.user_service import UserService

    user_service = UserService(db_session)

    # Create new user
    user = await user_service.create_user(
        wallet_address="0xABC123456789DEF0123456789DEF0123456789Ab"
    )

    # Get config (uses default values)
    config = await user_service.get_config(user.wallet_address)

    # Verify defaults (AC#6)
    assert config.get("position_size") == "0.1"
    assert config.get("max_position_size") == "10.0"


# ============================================================================
# Telegram Configuration Tests (Story 5.8)
# ============================================================================


@pytest.mark.asyncio
async def test_get_telegram_config_not_configured(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#5: GET /api/config/telegram returns configured=false for new user."""
    response = await async_client.get(
        "/api/config/telegram",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["configured"] is False
    assert data["chat_id"] is None
    assert data["setup_instructions"] is not None
    assert "chat ID" in data["setup_instructions"].lower() or "chat_id" in data["setup_instructions"].lower()


@pytest.mark.asyncio
async def test_get_telegram_config_bot_status(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#1: GET /api/config/telegram shows bot_status and test_available."""
    response = await async_client.get(
        "/api/config/telegram",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()

    # Bot status should reflect configuration
    assert "bot_status" in data
    assert data["bot_status"] in ["connected", "not_configured", "error"]
    assert "test_available" in data
    assert isinstance(data["test_available"], bool)


@pytest.mark.asyncio
async def test_get_telegram_config_configured(
    async_client: AsyncClient,
    db_session,
):
    """Test AC#1: GET /api/config/telegram returns configured=true with chat_id."""
    from kitkat.services.session_service import SessionService
    from kitkat.services.user_service import UserService

    user_service = UserService(db_session)
    session_service = SessionService(db_session)

    # Create user with telegram configured
    user = await user_service.create_user(
        wallet_address="0xABCdef1234567890ABCdef1234567890ABCdef12"
    )

    # Update user config_data with telegram_chat_id
    import json
    from sqlalchemy import update
    from kitkat.database import UserModel

    await db_session.execute(
        update(UserModel)
        .where(UserModel.wallet_address == user.wallet_address)
        .values(config_data=json.dumps({"telegram_chat_id": "123456789"}))
    )
    await db_session.commit()

    # Create session
    session = await session_service.create_session(user.wallet_address)

    response = await async_client.get(
        "/api/config/telegram",
        headers={"Authorization": f"Bearer {session.token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["configured"] is True
    assert data["chat_id"] == "123456789"
    assert data["setup_instructions"] is None


@pytest.mark.asyncio
async def test_put_telegram_config_success(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#2, #3: PUT /api/config/telegram saves chat_id when test succeeds."""
    with patch("kitkat.api.config.TelegramAlertService") as mock_alert_class, \
         patch("kitkat.api.config.get_settings") as mock_get_settings:
        # Mock settings to have bot token
        mock_settings = mock_get_settings.return_value
        mock_settings.telegram_bot_token = "test-bot-token"

        # Mock the service to return success
        mock_instance = AsyncMock()
        mock_instance.send_test_message = AsyncMock(return_value=True)
        mock_alert_class.return_value = mock_instance

        response = await async_client.put(
            "/api/config/telegram",
            headers={"Authorization": f"Bearer {authenticated_user['token']}"},
            json={"chat_id": "987654321"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["configured"] is True
        assert data["chat_id"] == "987654321"
        assert data["bot_status"] == "connected"

        # Verify test message was called
        mock_instance.send_test_message.assert_called_once()


@pytest.mark.asyncio
async def test_put_telegram_config_test_fails(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#4: PUT /api/config/telegram returns 400 when test fails."""
    with patch("kitkat.api.config.TelegramAlertService") as mock_alert_class, \
         patch("kitkat.api.config.get_settings") as mock_get_settings:
        # Mock settings to have bot token
        mock_settings = mock_get_settings.return_value
        mock_settings.telegram_bot_token = "test-bot-token"

        # Mock the service to return failure
        mock_instance = AsyncMock()
        mock_instance.send_test_message = AsyncMock(return_value=False)
        mock_alert_class.return_value = mock_instance

        response = await async_client.put(
            "/api/config/telegram",
            headers={"Authorization": f"Bearer {authenticated_user['token']}"},
            json={"chat_id": "invalid_chat_id"},
        )
        assert response.status_code == 400
        data = response.json()

        assert "Failed to send test message" in data["detail"]


@pytest.mark.asyncio
async def test_put_telegram_config_not_saved_on_failure(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#4: Config is NOT saved when test message fails."""
    with patch("kitkat.api.config.TelegramAlertService") as mock_alert_class, \
         patch("kitkat.api.config.get_settings") as mock_get_settings:
        # Mock settings to have bot token
        mock_settings = mock_get_settings.return_value
        mock_settings.telegram_bot_token = "test-bot-token"

        # Mock the service to return failure
        mock_instance = AsyncMock()
        mock_instance.send_test_message = AsyncMock(return_value=False)
        mock_alert_class.return_value = mock_instance

        # Attempt configuration with failing test
        await async_client.put(
            "/api/config/telegram",
            headers={"Authorization": f"Bearer {authenticated_user['token']}"},
            json={"chat_id": "invalid_chat_id"},
        )

    # Verify config was NOT saved (outside the mock context)
    response = await async_client.get(
        "/api/config/telegram",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
    )
    data = response.json()
    assert data["configured"] is False


@pytest.mark.asyncio
async def test_telegram_config_get_requires_auth(
    async_client: AsyncClient,
):
    """Test: GET /api/config/telegram requires authentication."""
    response = await async_client.get("/api/config/telegram")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_telegram_config_put_requires_auth(
    async_client: AsyncClient,
):
    """Test: PUT /api/config/telegram requires authentication."""
    response = await async_client.put(
        "/api/config/telegram",
        json={"chat_id": "123456789"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_put_telegram_config_empty_chat_id_rejected(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test: PUT /api/config/telegram rejects empty chat_id."""
    response = await async_client.put(
        "/api/config/telegram",
        headers={"Authorization": f"Bearer {authenticated_user['token']}"},
        json={"chat_id": ""},
    )
    # Pydantic validation should reject empty string (min_length=1)
    assert response.status_code in [400, 422]


@pytest.mark.asyncio
async def test_put_telegram_config_bot_not_configured(
    async_client: AsyncClient,
    authenticated_user,
):
    """Test AC#6: PUT fails gracefully when bot token not configured on server."""
    # Patch settings to have no bot token
    with patch("kitkat.api.config.get_settings") as mock_settings:
        mock_settings.return_value.telegram_bot_token = ""

        response = await async_client.put(
            "/api/config/telegram",
            headers={"Authorization": f"Bearer {authenticated_user['token']}"},
            json={"chat_id": "123456789"},
        )
        assert response.status_code == 503
        data = response.json()
        assert "not configured" in data["detail"].lower()
