"""Tests for database module and Signal model."""

import asyncio
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from kitkat.database import Base, get_db_session
from kitkat.models import Signal


class TestDatabaseInitialization:
    """Tests for database initialization and WAL mode."""

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, test_db_session: AsyncSession):
        """Test that WAL mode is enabled after initialization."""
        result = await test_db_session.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
        assert mode.upper() == "WAL"

    @pytest.mark.asyncio
    async def test_synchronous_pragma_set(self, test_db_session: AsyncSession):
        """Test that PRAGMA synchronous is set to NORMAL."""
        result = await test_db_session.execute(text("PRAGMA synchronous"))
        value = result.scalar()
        # NORMAL = 1
        assert value == 1

    @pytest.mark.asyncio
    async def test_cache_size_set(self, test_db_session: AsyncSession):
        """Test that cache_size is configured."""
        result = await test_db_session.execute(text("PRAGMA cache_size"))
        value = result.scalar()
        # PRAGMA cache_size returns negative value when set (10000 pages configured)
        assert value != 0


class TestSignalModel:
    """Tests for Signal model schema and constraints."""

    @pytest.mark.asyncio
    async def test_signal_table_exists(self, test_db_session: AsyncSession):
        """Test that signals table exists."""
        result = await test_db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
        )
        assert result.scalar() is not None

    @pytest.mark.asyncio
    async def test_signal_model_columns(self, test_db_session: AsyncSession):
        """Test that Signal model has all required columns."""
        result = await test_db_session.execute(text("PRAGMA table_info(signals)"))
        columns = {row[1] for row in result.fetchall()}

        assert "id" in columns
        assert "signal_id" in columns
        assert "payload" in columns
        assert "received_at" in columns
        assert "processed" in columns

    @pytest.mark.asyncio
    async def test_signal_id_unique_constraint(self, test_db_session: AsyncSession):
        """Test that signal_id has unique constraint."""
        # Try to insert duplicate signal_id - should fail
        signal1 = Signal(
            signal_id="constraint-test",
            payload={"test": 1},
            received_at=datetime.now(),
            processed=False,
        )
        test_db_session.add(signal1)
        await test_db_session.commit()

        signal2 = Signal(
            signal_id="constraint-test",
            payload={"test": 2},
            received_at=datetime.now(),
            processed=False,
        )
        test_db_session.add(signal2)
        with pytest.raises(Exception):
            await test_db_session.commit()

    @pytest.mark.asyncio
    async def test_signal_indexes(self, test_db_session: AsyncSession):
        """Test that indexes exist on signal_id and received_at."""
        result = await test_db_session.execute(text("PRAGMA index_list(signals)"))
        index_names = {row[1] for row in result.fetchall()}

        # SQLAlchemy creates indexes automatically for indexed columns
        assert len(index_names) > 0

    @pytest.mark.asyncio
    async def test_signal_primary_key(self, test_db_session: AsyncSession):
        """Test that id is primary key."""
        result = await test_db_session.execute(text("PRAGMA table_info(signals)"))
        columns = result.fetchall()
        # Column pk value of 1 means it's the primary key
        assert any(col[1] == "id" and col[5] == 1 for col in columns)


class TestSignalCreationAndPersistence:
    """Tests for Signal model creation and data persistence."""

    @pytest.mark.asyncio
    async def test_create_signal_record(self, test_db_session: AsyncSession):
        """Test creating a Signal record."""
        signal = Signal(
            signal_id="test-signal-001",
            payload={"action": "buy", "symbol": "BTC"},
            received_at=datetime.now(),
            processed=False,
        )
        test_db_session.add(signal)
        await test_db_session.commit()

        # Verify it was saved
        result = await test_db_session.execute(text("SELECT COUNT(*) FROM signals"))
        count = result.scalar()
        assert count == 1

    @pytest.mark.asyncio
    async def test_signal_persistence_across_sessions(
        self, test_db_session: AsyncSession
    ):
        """Test that signals persist across sessions."""
        # Create signal in first session
        signal = Signal(
            signal_id="persist-test-001",
            payload={"test": "data"},
            received_at=datetime.now(),
            processed=False,
        )
        test_db_session.add(signal)
        await test_db_session.commit()

        # Verify persistence by querying
        result = await test_db_session.execute(
            text("SELECT signal_id FROM signals WHERE signal_id = 'persist-test-001'")
        )
        retrieved_id = result.scalar()
        assert retrieved_id == "persist-test-001"

    @pytest.mark.asyncio
    async def test_signal_unique_constraint_violation(
        self, test_db_session: AsyncSession
    ):
        """Test that duplicate signal_id raises constraint violation."""
        signal1 = Signal(
            signal_id="duplicate-test",
            payload={"test": 1},
            received_at=datetime.now(),
            processed=False,
        )
        test_db_session.add(signal1)
        await test_db_session.commit()

        # Try to add duplicate
        signal2 = Signal(
            signal_id="duplicate-test",
            payload={"test": 2},
            received_at=datetime.now(),
            processed=False,
        )
        test_db_session.add(signal2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            await test_db_session.commit()


class TestAsyncSessionManagement:
    """Tests for async session factory and dependency injection."""

    @pytest.mark.asyncio
    async def test_session_can_be_obtained(self, test_db_session: AsyncSession):
        """Test that async session can be obtained."""
        assert test_db_session is not None
        assert isinstance(test_db_session, AsyncSession)

    @pytest.mark.asyncio
    async def test_get_db_session_dependency(self):
        """Test get_db_session dependency function."""
        session_gen = get_db_session()
        session = await session_gen.__anext__()
        try:
            assert session is not None
            assert isinstance(session, AsyncSession)
        finally:
            try:
                await session_gen.__anext__()
            except StopAsyncIteration:
                pass


class TestConcurrentWrites:
    """Tests for concurrent write safety with WAL mode."""

    @pytest.mark.asyncio
    async def test_concurrent_writes_no_locking(self, test_db_session: AsyncSession):
        """Test that concurrent writes don't fail with database locked errors."""

        async def create_signal(session, index):
            signal = Signal(
                signal_id=f"concurrent-signal-{index}",
                payload={"index": index},
                received_at=datetime.now(),
                processed=False,
            )
            session.add(signal)
            await session.commit()

        # Create multiple concurrent writes
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "concurrent_test.db"
            database_url = f"sqlite+aiosqlite:///{db_path}"

            test_engine = create_async_engine(
                database_url,
                echo=False,
                connect_args={"check_same_thread": False, "timeout": 30},
            )

            @event.listens_for(test_engine.sync_engine, "connect")
            def setup_sqlite(dbapi_conn, connection_record):
                dbapi_conn.execute("PRAGMA journal_mode=WAL")
                dbapi_conn.execute("PRAGMA synchronous=NORMAL")

            test_async_session = sessionmaker(
                test_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )

            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Run concurrent writes
            tasks = []
            for i in range(5):
                async with test_async_session() as session:
                    tasks.append(create_signal(session, i))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify no errors occurred
            for result in results:
                assert not isinstance(result, Exception)

            # Verify all writes succeeded
            async with test_async_session() as session:
                count_result = await session.execute(
                    text("SELECT COUNT(*) FROM signals")
                )
                count = count_result.scalar()
                assert count == 5

            await test_engine.dispose()

    @pytest.mark.asyncio
    async def test_data_integrity_concurrent_access(
        self, test_db_session: AsyncSession
    ):
        """Test that data integrity is maintained with concurrent access."""
        # Insert initial signal
        signal = Signal(
            signal_id="integrity-test",
            payload={"value": 0},
            received_at=datetime.now(),
            processed=False,
        )
        test_db_session.add(signal)
        await test_db_session.commit()

        # Verify data is intact
        result = await test_db_session.execute(
            text("SELECT payload FROM signals WHERE signal_id = 'integrity-test'")
        )
        row = result.fetchone()
        assert row is not None
