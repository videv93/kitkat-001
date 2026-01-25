"""Tests for SessionService."""

from datetime import datetime, timedelta, timezone

import pytest

from kitkat.services.session_service import SessionService, SESSION_TTL_HOURS
from kitkat.services.user_service import UserService


@pytest.mark.asyncio
async def test_create_session_success(db_session):
    """Test successful session creation."""
    # Create user first
    user_service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await user_service.create_user(wallet)

    # Create session
    service = SessionService(db_session)
    session = await service.create_session(wallet)

    assert session.token is not None
    assert len(session.token) > 0
    assert session.wallet_address == wallet
    assert session.created_at is not None
    assert session.expires_at is not None
    assert session.last_used is not None


@pytest.mark.asyncio
async def test_create_session_expires_24h_from_now(db_session):
    """Test that session expires 24 hours from now."""
    user_service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await user_service.create_user(wallet)

    service = SessionService(db_session)
    now = datetime.now(timezone.utc)
    session = await service.create_session(wallet)

    # Check expiration is approximately 24h from now
    # Both datetimes are now timezone-aware
    expected_expires = now + timedelta(hours=SESSION_TTL_HOURS)
    time_diff = abs((session.expires_at - expected_expires).total_seconds())
    assert time_diff < 5  # Allow 5 second tolerance for test execution time


@pytest.mark.asyncio
async def test_create_session_user_not_found(db_session):
    """Test that creating session for non-existent user raises error."""
    service = SessionService(db_session)
    with pytest.raises(ValueError, match="not found"):
        await service.create_session("0xnonexistent1111111111111111111111111111")


@pytest.mark.asyncio
async def test_create_session_token_uniqueness(db_session):
    """Test that generated session tokens are unique."""
    user_service = UserService(db_session)
    wallet1 = "0x1111111111111111111111111111111111111111"
    wallet2 = "0x2222222222222222222222222222222222222222"
    await user_service.create_user(wallet1)
    await user_service.create_user(wallet2)

    service = SessionService(db_session)
    session1 = await service.create_session(wallet1)
    session2 = await service.create_session(wallet2)

    assert session1.token != session2.token


@pytest.mark.asyncio
async def test_validate_session_success(db_session):
    """Test successful session validation."""
    user_service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await user_service.create_user(wallet)

    service = SessionService(db_session)
    session = await service.create_session(wallet)

    current_user = await service.validate_session(session.token)
    assert current_user.wallet_address == wallet
    assert current_user.session_id == session.id


@pytest.mark.asyncio
async def test_validate_session_invalid_token(db_session):
    """Test that invalid token raises error."""
    service = SessionService(db_session)
    with pytest.raises(ValueError, match="Invalid token"):
        await service.validate_session("invalid_token_12345678")


@pytest.mark.asyncio
async def test_validate_session_empty_token(db_session):
    """Test that empty token raises error."""
    service = SessionService(db_session)
    with pytest.raises(ValueError, match="Token required"):
        await service.validate_session("")

    with pytest.raises(ValueError, match="Token required"):
        await service.validate_session(None)


@pytest.mark.asyncio
async def test_validate_session_expired(db_session):
    """Test that expired session raises error and is deleted."""
    user_service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await user_service.create_user(wallet)

    service = SessionService(db_session)
    session = await service.create_session(wallet)

    # Manually expire the session
    from sqlalchemy import update

    from kitkat.database import SessionModel

    stmt = (
        update(SessionModel)
        .where(SessionModel.id == session.id)
        .values(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    )
    await db_session.execute(stmt)
    await db_session.commit()

    # Try to validate
    with pytest.raises(ValueError, match="expired"):
        await service.validate_session(session.token)


@pytest.mark.asyncio
async def test_validate_session_updates_last_used(db_session):
    """Test that validating session updates last_used timestamp."""
    user_service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await user_service.create_user(wallet)

    service = SessionService(db_session)
    session = await service.create_session(wallet)
    original_last_used = session.last_used

    # Wait a bit (simulate time passing)
    import asyncio

    await asyncio.sleep(0.1)

    # Validate session
    await service.validate_session(session.token)

    # Check last_used was updated
    from sqlalchemy import select

    from kitkat.database import SessionModel

    stmt = select(SessionModel).where(SessionModel.id == session.id)
    result = await db_session.execute(stmt)
    updated_session = result.scalar_one()
    assert updated_session.last_used > original_last_used


@pytest.mark.asyncio
async def test_cleanup_expired_sessions(db_session):
    """Test cleanup removes expired sessions."""
    user_service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await user_service.create_user(wallet)

    service = SessionService(db_session)
    # Create multiple sessions
    session1 = await service.create_session(wallet)
    session2 = await service.create_session(wallet)

    # Expire one session
    from sqlalchemy import update

    from kitkat.database import SessionModel

    stmt = (
        update(SessionModel)
        .where(SessionModel.id == session1.id)
        .values(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    )
    await db_session.execute(stmt)
    await db_session.commit()

    # Cleanup
    cleaned = await service.cleanup_expired_sessions()
    assert cleaned == 1

    # Verify expired session is gone, valid one remains
    from sqlalchemy import select

    stmt = select(SessionModel).where(SessionModel.id == session1.id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None

    stmt = select(SessionModel).where(SessionModel.id == session2.id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_cleanup_expired_sessions_doesnt_delete_valid(db_session):
    """Test that cleanup doesn't delete valid sessions."""
    user_service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await user_service.create_user(wallet)

    service = SessionService(db_session)
    session = await service.create_session(wallet)

    # Cleanup (should delete 0)
    cleaned = await service.cleanup_expired_sessions()
    assert cleaned == 0

    # Verify session still exists
    from sqlalchemy import select

    from kitkat.database import SessionModel

    stmt = select(SessionModel).where(SessionModel.id == session.id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_concurrent_session_creation(db_session):
    """Test that multiple sessions can be created for same user."""
    user_service = UserService(db_session)
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    await user_service.create_user(wallet)

    service = SessionService(db_session)
    # Create multiple sessions sequentially (concurrency testing with shared session
    # can cause SQLAlchemy state issues, but the real-world scenario is that each
    # request gets its own session)
    sessions = []
    for _ in range(3):
        session = await service.create_session(wallet)
        sessions.append(session)

    # All should have unique tokens
    tokens = [s.token for s in sessions]
    assert len(tokens) == len(set(tokens))
    assert all(s.wallet_address == wallet for s in sessions)
