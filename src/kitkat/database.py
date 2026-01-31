"""Database configuration and session management."""

import threading
from datetime import datetime, timezone
from typing import List

import structlog
from sqlalchemy import DateTime, ForeignKey, String, Text, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship, sessionmaker
from sqlalchemy.types import TypeDecorator

logger = structlog.get_logger()

# Thread-safe lock for lazy initialization of globals
_init_lock = threading.Lock()


class UtcDateTime(TypeDecorator):
    """Store timezone-aware UTC datetimes as naive UTC in SQLite.

    SQLite doesn't understand timezones, so we:
    1. Accept timezone-aware datetimes from Python
    2. Store them as naive UTC in the database
    3. Return them as timezone-aware UTC when retrieved
    """

    impl = DateTime(timezone=False)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert timezone-aware datetime to naive UTC before storing."""
        if value is not None:
            if value.tzinfo is not None:
                # Convert to UTC and strip timezone
                value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        """Convert naive UTC from DB back to timezone-aware UTC."""
        if value is not None:
            # Assume stored value is UTC and make it timezone-aware
            return value.replace(tzinfo=timezone.utc)
        return value


def _utc_now():
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


# SQLAlchemy declarative base for models
Base = declarative_base()

# Engine and session factory will be initialized lazily
_engine = None
_async_session = None


def _create_engine():
    """Create async SQLAlchemy engine with WAL mode configuration.

    Database Configuration:
    - WAL mode (Write-Ahead Logging): Enables concurrent readers and writers
    - PRAGMA synchronous=NORMAL: Balance between safety and performance
    - Isolation level: SERIALIZABLE (SQLite default, enforced via constraints)
      - Prevents race conditions through unique constraint enforcement
      - IntegrityError raised on constraint violation during commit
      - Applications must catch IntegrityError for duplicate key handling
    """
    from kitkat.config import get_settings

    settings = get_settings()

    engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    # Enable WAL mode and optimize SQLite for concurrent writes
    @event.listens_for(engine.sync_engine, "connect")
    def setup_sqlite(dbapi_conn, connection_record):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")
        dbapi_conn.execute("PRAGMA cache_size=10000")
        # SQLite default isolation level is SERIALIZABLE
        # This ensures unique constraints prevent race conditions

    return engine


def get_engine():
    """Get or create the database engine (lazy initialization).

    Thread-safe using double-checked locking pattern.
    """
    global _engine
    if _engine is None:
        with _init_lock:
            # Double-check after acquiring lock
            if _engine is None:
                _engine = _create_engine()
    return _engine


def get_async_session_factory():
    """Get or create the async session factory (lazy initialization).

    Thread-safe using double-checked locking pattern.
    """
    global _async_session
    if _async_session is None:
        with _init_lock:
            # Double-check after acquiring lock
            if _async_session is None:
                engine = get_engine()
                _async_session = sessionmaker(
                    engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autocommit=False,
                    autoflush=False,
                )
    return _async_session


async def get_db_session() -> AsyncSession:
    """Dependency function to provide async database session.

    The async context manager handles session cleanup automatically.

    Yields:
        AsyncSession: Database session for the request.
    """
    factory = get_async_session_factory()
    async with factory() as session:
        yield session




# ============================================================================
# ORM Models for User & Session Management (Story 2.2)
# ============================================================================


class UserModel(Base):
    """SQLAlchemy ORM model for users table."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_address: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    webhook_token: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    config_data: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=_utc_now, onupdate=_utc_now, nullable=False
    )

    # Relationship for cascading deletes
    sessions: Mapped[List["SessionModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SessionModel(Base):
    """SQLAlchemy ORM model for sessions table."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    wallet_address: Mapped[str] = mapped_column(
        String(255), ForeignKey("users.wallet_address"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=_utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        UtcDateTime, index=True, nullable=False
    )
    last_used: Mapped[datetime] = mapped_column(
        UtcDateTime, default=_utc_now, nullable=False
    )

    # Relationship
    user: Mapped["UserModel"] = relationship(back_populates="sessions")


# ============================================================================
# ORM Models for Execution Logging & Partial Fills (Story 2.8)
# ============================================================================


class ExecutionModel(Base):
    """SQLAlchemy ORM model for executions table.

    Tracks all order execution attempts for auditing and partial fill handling.
    """

    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )  # SHA-256 hash from Signal, NOT foreign key (signals may be cleaned up)
    dex_id: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # "extended", "mock", etc.
    order_id: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True
    )  # DEX-assigned, null on submission failure
    status: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False
    )  # "pending", "filled", "partial", "failed"
    result_data: Mapped[str] = mapped_column(
        Text, default="{}", nullable=False
    )  # JSON with full DEX response, filled_size, remaining_size
    latency_ms: Mapped[int | None] = mapped_column(
        nullable=True
    )  # Time from submission start to response
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=_utc_now, index=True, nullable=False
    )
