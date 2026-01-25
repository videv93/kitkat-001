"""Shared pytest fixtures."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from kitkat.database import Base
from kitkat.main import app


@pytest.fixture(autouse=True)
def reset_settings_singleton():
    """Reset settings singleton before each test."""
    import kitkat.config

    kitkat.config._settings_instance = None
    yield
    kitkat.config._settings_instance = None


@pytest.fixture(autouse=True)
def set_test_env():
    """Set test environment variables."""
    os.environ["WEBHOOK_TOKEN"] = "test-webhook-token-for-testing"
    yield


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for async tests."""
    return "asyncio"


@pytest.fixture(autouse=True)
def setup_test_database():
    """Set up test database with tables before each test."""
    import asyncio

    from kitkat.database import Base, get_engine

    async def _setup():
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    # Run setup
    try:
        asyncio.run(_setup())
    except RuntimeError:
        # Event loop already running (in async context)
        pass

    yield

    # Cleanup
    try:
        asyncio.run(_setup())
    except RuntimeError:
        pass


@pytest.fixture
async def test_db_session():
    """Provide async DB session for tests with test database."""
    with TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        database_url = f"sqlite+aiosqlite:///{db_path}"

        from sqlalchemy import event

        engine = create_async_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        # Enable WAL mode for test database
        @event.listens_for(engine.sync_engine, "connect")
        def setup_sqlite(dbapi_conn, connection_record):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA synchronous=NORMAL")

        async_session_factory = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Provide session
        async with async_session_factory() as session:
            yield session

        # Cleanup
        await engine.dispose()


@pytest.fixture
async def db_session():
    """Provide async DB session for tests."""
    from kitkat.database import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        yield session
        await session.close()


@pytest.fixture
def client():
    """Provide FastAPI test client."""
    return TestClient(app)
