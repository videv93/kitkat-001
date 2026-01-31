"""Session management service."""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.database import SessionModel, UserModel
from kitkat.models import CurrentUser, Session
from kitkat.utils import generate_secure_token

logger = structlog.get_logger()

SESSION_TTL_HOURS = 24


class SessionService:
    """Service for session management operations."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    async def create_session(self, wallet_address: str) -> Session:
        """Create new session for user.

        Args:
            wallet_address: The user's wallet address.

        Returns:
            Session: The created session model.

        Raises:
            ValueError: If wallet_address doesn't exist.
        """
        # Verify user exists
        stmt = select(UserModel).where(UserModel.wallet_address == wallet_address)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User not found: {wallet_address}")

        token = generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)

        session = SessionModel(
            token=token,
            wallet_address=wallet_address,
            expires_at=expires_at,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        logger.info(
            "Session created for wallet",
            wallet_address=wallet_address,
            expires_at=expires_at,
        )
        return Session.model_validate(session)

    async def validate_session(self, token: str) -> CurrentUser:
        """Validate session token, update last_used, return current user.

        Args:
            token: The session token to validate.

        Returns:
            CurrentUser: The authenticated user context.

        Raises:
            ValueError: If token invalid or expired.
        """
        if not token:
            raise ValueError("Token required")

        stmt = select(SessionModel).where(SessionModel.token == token)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError("Invalid token")

        if session.expires_at < datetime.now(timezone.utc):
            # Delete expired session
            await self.db.delete(session)
            await self.db.commit()
            raise ValueError("Session expired")

        # Update last_used
        session.last_used = datetime.now(timezone.utc)
        await self.db.commit()

        # Load user to get webhook_token (Story 2.4)
        user_stmt = select(UserModel).where(UserModel.wallet_address == session.wallet_address)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        logger.info("Session validated, last_used updated")
        return CurrentUser(
            wallet_address=session.wallet_address,
            session_id=session.id,
            webhook_token=user.webhook_token if user else "",
        )

    async def cleanup_expired_sessions(self) -> int:
        """Delete all expired sessions.

        Returns:
            int: Number of sessions deleted.
        """
        stmt = delete(SessionModel).where(SessionModel.expires_at < datetime.now(timezone.utc))
        result = await self.db.execute(stmt)
        await self.db.commit()
        count = result.rowcount
        logger.info("Cleaned up expired sessions", count=count)
        return count

    async def delete_session(self, session_id: int) -> bool:
        """Delete a specific session by ID.

        Args:
            session_id: The session ID to delete.

        Returns:
            bool: True if session was deleted, False if not found.
        """
        stmt = delete(SessionModel).where(SessionModel.id == session_id)
        result = await self.db.execute(stmt)
        await self.db.commit()

        if result.rowcount > 0:
            logger.info("Session deleted", session_id=session_id)
            return True
        return False

    async def delete_all_user_sessions(self, wallet_address: str) -> int:
        """Delete all sessions for a wallet address.

        Used for full wallet revocation - ensures no active sessions remain.

        Args:
            wallet_address: The wallet address to revoke all sessions for.

        Returns:
            int: Number of sessions deleted.
        """
        stmt = delete(SessionModel).where(SessionModel.wallet_address == wallet_address)
        result = await self.db.execute(stmt)
        await self.db.commit()

        count = result.rowcount
        logger.info("All sessions deleted for wallet", wallet_address=wallet_address[:10], count=count)
        return count
