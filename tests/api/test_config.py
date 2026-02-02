"""Tests for configuration API endpoints (Story 5.6, 5.7)."""

import pytest
from httpx import AsyncClient


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
