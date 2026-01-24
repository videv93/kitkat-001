"""Database configuration and session management."""

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = structlog.get_logger()

# SQLAlchemy declarative base for models
Base = declarative_base()

# Engine and session factory will be initialized lazily
_engine = None
_async_session = None


def _create_engine():
    """Create async SQLAlchemy engine with WAL mode configuration."""
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

    return engine


def get_engine():
    """Get or create the database engine (lazy initialization)."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_async_session_factory():
    """Get or create the async session factory (lazy initialization)."""
    global _async_session
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

    Yields:
        AsyncSession: Database session for the request.
    """
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


# Module-level accessors for backwards compatibility
def engine():
    """Get database engine."""
    return get_engine()


def async_session():
    """Get async session factory."""
    return get_async_session_factory()
