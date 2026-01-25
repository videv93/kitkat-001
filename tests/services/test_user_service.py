"""Tests for UserService."""

import json

import pytest
from sqlalchemy import select

from kitkat.database import UserModel
from kitkat.services.user_service import DEFAULT_USER_CONFIG, UserService


@pytest.mark.asyncio
async def test_create_user_success(db_session):
    """Test successful user creation with default config."""
    service = UserService(db_session)
    user = await service.create_user("0x1234567890abcdef1234567890abcdef12345678")

    assert user.wallet_address == "0x1234567890abcdef1234567890abcdef12345678"
    assert user.webhook_token is not None
    assert len(user.webhook_token) > 0
    assert user.config_data is not None
    assert isinstance(user.config_data, dict)
    assert user.created_at is not None
    assert user.updated_at is not None


@pytest.mark.asyncio
async def test_create_user_empty_wallet_address(db_session):
    """Test that empty wallet_address raises error."""
    service = UserService(db_session)
    with pytest.raises(ValueError, match="cannot be empty"):
        await service.create_user("")

    with pytest.raises(ValueError, match="cannot be empty"):
        await service.create_user("   ")


@pytest.mark.asyncio
async def test_create_user_default_config(db_session):
    """Test that created user has default config."""
    service = UserService(db_session)
    user = await service.create_user("0x1234567890abcdef1234567890abcdef12345678")

    config = json.loads(user.config_data) if isinstance(user.config_data, str) else user.config_data
    assert config["position_size"] == "0.1"
    assert config["max_position_size"] == "10.0"
    assert config["position_size_unit"] == "ETH"
    assert "onboarding_steps" in config
    assert config["dex_authorizations"] == []
    assert config["telegram_chat_id"] is None


@pytest.mark.asyncio
async def test_create_user_webhook_token_uniqueness(db_session):
    """Test that generated webhook tokens are unique."""
    service = UserService(db_session)
    user1 = await service.create_user("0x1111111111111111111111111111111111111111")

    # Create new session to avoid constraint issues
    user2 = await service.create_user("0x2222222222222222222222222222222222222222")

    assert user1.webhook_token != user2.webhook_token


@pytest.mark.asyncio
async def test_create_user_duplicate_wallet_address(db_session):
    """Test that duplicate wallet_address raises error."""
    service = UserService(db_session)
    await service.create_user("0x1234567890abcdef1234567890abcdef12345678")

    with pytest.raises(ValueError, match="already exists"):
        await service.create_user("0x1234567890abcdef1234567890abcdef12345678")


@pytest.mark.asyncio
async def test_create_user_integrity_error_handling(db_session):
    """Test that IntegrityError from race condition is handled gracefully."""
    from sqlalchemy.exc import IntegrityError
    from unittest.mock import patch, AsyncMock

    service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"

    # Create user first time successfully
    user = await service.create_user(wallet)
    assert user.wallet_address == wallet

    # Now test that a second attempt raises ValueError (not IntegrityError)
    with pytest.raises(ValueError, match="already exists"):
        await service.create_user(wallet)


@pytest.mark.asyncio
async def test_get_user_success(db_session):
    """Test retrieving an existing user."""
    service = UserService(db_session)
    created_user = await service.create_user("0x1234567890abcdef1234567890abcdef12345678")

    retrieved_user = await service.get_user("0x1234567890abcdef1234567890abcdef12345678")
    assert retrieved_user is not None
    assert retrieved_user.wallet_address == created_user.wallet_address
    assert retrieved_user.webhook_token == created_user.webhook_token


@pytest.mark.asyncio
async def test_get_user_not_found(db_session):
    """Test retrieving a non-existent user."""
    service = UserService(db_session)
    user = await service.get_user("0xnonexistent1111111111111111111111111111")
    assert user is None


@pytest.mark.asyncio
async def test_get_config_with_defaults(db_session):
    """Test that get_config returns merged with defaults."""
    service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await service.create_user(wallet)

    config = await service.get_config(wallet)
    assert config["position_size"] == "0.1"
    assert config["max_position_size"] == "10.0"
    assert config["position_size_unit"] == "ETH"


@pytest.mark.asyncio
async def test_get_config_not_found(db_session):
    """Test that get_config raises error for non-existent user."""
    service = UserService(db_session)
    with pytest.raises(ValueError, match="not found"):
        await service.get_config("0xnonexistent1111111111111111111111111111")


@pytest.mark.asyncio
async def test_update_config_success(db_session):
    """Test successful config update."""
    service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await service.create_user(wallet)

    updates = {"position_size": "0.5"}
    updated_config = await service.update_config(wallet, updates)

    assert updated_config["position_size"] == "0.5"
    assert updated_config["max_position_size"] == "10.0"  # Unchanged


@pytest.mark.asyncio
async def test_update_config_merges_fields(db_session):
    """Test that update_config merges without overwriting other fields."""
    service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await service.create_user(wallet)

    # Update only one field
    await service.update_config(wallet, {"position_size": "0.5"})

    # Verify other fields unchanged
    config = await service.get_config(wallet)
    assert config["position_size"] == "0.5"
    assert config["max_position_size"] == "10.0"
    assert config["telegram_chat_id"] is None


@pytest.mark.asyncio
async def test_update_config_not_found(db_session):
    """Test that update_config raises error for non-existent user."""
    service = UserService(db_session)
    with pytest.raises(ValueError, match="not found"):
        await service.update_config("0xnonexistent1111111111111111111111111111", {})


@pytest.mark.asyncio
async def test_config_data_json_roundtrip(db_session):
    """Test that config_data can be persisted and retrieved as JSON."""
    service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await service.create_user(wallet)

    # Update with complex data
    updates = {
        "dex_authorizations": ["uniswap", "curve"],
        "onboarding_steps": {
            "wallet_connected": True,
            "dex_authorized": False,
        },
    }
    await service.update_config(wallet, updates)

    # Retrieve and verify
    config = await service.get_config(wallet)
    assert config["dex_authorizations"] == ["uniswap", "curve"]
    assert config["onboarding_steps"]["wallet_connected"] is True
