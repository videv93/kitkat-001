"""User management service."""

import json
from hmac import compare_digest
from typing import Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from kitkat.database import UserModel
from kitkat.models import User
from kitkat.utils import generate_secure_token

logger = structlog.get_logger()

# Default user configuration
DEFAULT_USER_CONFIG = {
    "position_size": "0.1",
    "max_position_size": "10.0",
    "position_size_unit": "ETH",
    "onboarding_steps": {
        "wallet_connected": False,
        "dex_authorized": False,
        "webhook_configured": False,
        "test_signal_sent": False,
        "first_live_trade": False,
    },
    "dex_authorizations": [],
    "telegram_chat_id": None,
}


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    async def create_user(self, wallet_address: str) -> User:
        """Create new user with default config.

        Args:
            wallet_address: The user's wallet address.

        Returns:
            User: The created user model.

        Raises:
            ValueError: If wallet_address already exists or is invalid.
        """
        # Validate input
        if not wallet_address or not wallet_address.strip():
            raise ValueError("wallet_address cannot be empty")

        # Check if user already exists
        existing_user = await self.get_user(wallet_address)
        if existing_user:
            raise ValueError(f"User already exists: {wallet_address}")

        webhook_token = generate_secure_token()
        config_data = DEFAULT_USER_CONFIG.copy()

        user = UserModel(
            wallet_address=wallet_address,
            webhook_token=webhook_token,
            config_data=json.dumps(config_data),
        )
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError:
            # Handles race condition where user created between check and insert
            await self.db.rollback()
            raise ValueError(f"User already exists: {wallet_address}")
        await self.db.refresh(user)

        logger.info("User created for wallet", wallet_address=wallet_address)
        return User.model_validate(user)

    async def get_user(self, wallet_address: str) -> Optional[User]:
        """Retrieve user by wallet address.

        Args:
            wallet_address: The wallet address to look up.

        Returns:
            User: The user model if found, None otherwise.
        """
        stmt = select(UserModel).where(UserModel.wallet_address == wallet_address)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        return User.model_validate(user) if user else None

    async def get_config(self, wallet_address: str) -> dict:
        """Get user config with defaults merged.

        Args:
            wallet_address: The wallet address to get config for.

        Returns:
            dict: The merged config with defaults.

        Raises:
            ValueError: If user not found.
        """
        user = await self.get_user(wallet_address)
        if not user:
            raise ValueError(f"User not found: {wallet_address}")

        # config_data is already a dict thanks to Pydantic validator
        config = user.config_data if user.config_data else {}
        # Merge with defaults (defaults first, then override with user config)
        return {**DEFAULT_USER_CONFIG, **config}

    async def update_config(self, wallet_address: str, updates: dict) -> dict:
        """Update user config (merge only specified fields).

        Args:
            wallet_address: The wallet address to update config for.
            updates: Dictionary of fields to update.

        Returns:
            dict: The updated config.

        Raises:
            ValueError: If user not found.
        """
        user = await self.get_user(wallet_address)
        if not user:
            raise ValueError(f"User not found: {wallet_address}")

        # config_data is already a dict thanks to Pydantic validator
        config = user.config_data if user.config_data else {}
        config.update(updates)

        # Persist
        stmt = (
            update(UserModel)
            .where(UserModel.wallet_address == wallet_address)
            .values(config_data=json.dumps(config))
        )
        await self.db.execute(stmt)
        await self.db.commit()

        logger.info(
            "Config updated for wallet",
            wallet_address=wallet_address,
            fields=list(updates.keys()),
        )
        return config

    async def get_user_by_webhook_token(self, token: str) -> Optional[User]:
        """Retrieve user by webhook token (Story 2.4: AC3).

        Uses constant-time comparison to prevent timing attacks.

        Args:
            token: The webhook token to look up.

        Returns:
            User: The user model if found, None otherwise.
        """
        # Query all users with webhook_token (we'll do constant-time comparison)
        # This is not optimal, but safe for small user bases
        # In production, store hashed webhook_token for indexed lookups
        stmt = select(UserModel)
        result = await self.db.execute(stmt)
        users = result.scalars().all()

        for user in users:
            # Constant-time comparison to prevent timing attacks
            if compare_digest(user.webhook_token, token):
                logger.info("User found by webhook token", wallet_address=user.wallet_address[:10])
                return User.model_validate(user)

        logger.warning("Webhook token not found or invalid")
        return None
