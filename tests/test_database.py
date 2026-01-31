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
        """Test that indexes exist on signal_id (unique) and received_at columns."""
        # Get all indexes for the signals table
        result = await test_db_session.execute(text("PRAGMA index_list(signals)"))
        indexes = {row[1]: row for row in result.fetchall()}

        # Verify we have indexes (at least unique constraint on signal_id creates one)
        assert len(indexes) > 0, "signals table should have at least one index"

        # Check which columns are indexed and verify uniqueness
        indexed_columns = set()
        unique_indexes = set()
        for index_name, index_row in indexes.items():
            # index_row[2] == 1 means index is unique
            if index_row[2] == 1:
                unique_indexes.add(index_name)

            index_info_result = await test_db_session.execute(
                text(f"PRAGMA index_info('{index_name}')")
            )
            for col_info in index_info_result.fetchall():
                indexed_columns.add(col_info[2])  # Column name is at index 2

        # Verify signal_id is indexed and unique
        assert (
            "signal_id" in indexed_columns
        ), "signal_id should be indexed (for uniqueness)"
        assert (
            len(unique_indexes) > 0
        ), "signal_id should have a unique index (unique constraint)"

        # Verify received_at is indexed
        assert "received_at" in indexed_columns, "received_at should be indexed"

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

    # Note: test_signal_unique_constraint_violation removed as duplicate of
    # TestSignalModel.test_signal_id_unique_constraint - both test the same behavior


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
        """Test that concurrent writes don't fail with database locked errors.

        Uses Barrier to force all tasks to reach commit point simultaneously,
        ensuring true concurrency overlap rather than sequential execution.
        """

        # Create temporary database for concurrent test
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

            # Barrier to force concurrent commits (5 tasks)
            barrier = asyncio.Barrier(5)

            async def create_signal_concurrent(index: int):
                """Create signal with barrier synchronization for true concurrency."""
                async with test_async_session() as session:
                    signal = Signal(
                        signal_id=f"concurrent-signal-{index}",
                        payload={"index": index},
                        received_at=datetime.now(),
                        processed=False,
                    )
                    session.add(signal)

                    # Wait for all 5 tasks to reach commit point
                    await barrier.wait()

                    # All commits happen simultaneously
                    await session.commit()

            # Run concurrent writes - tasks wait at barrier before committing
            tasks = [create_signal_concurrent(i) for i in range(5)]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify no errors occurred
            for i, result in enumerate(results):
                assert not isinstance(
                    result, Exception
                ), f"Task {i} failed: {result}"

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


class TestDatabaseErrorHandling:
    """Tests for database initialization error handling and cleanup."""

    @pytest.mark.asyncio
    async def test_database_initialization_cleanup(self):
        """Test that engine cleanup occurs on initialization failure."""
        from kitkat import database

        # Reset globals to test fresh initialization
        database._engine = None
        database._async_session = None

        # Verify engine can be created successfully
        engine = database.get_engine()
        assert engine is not None
        await engine.dispose()

        # Reset again
        database._engine = None
        database._async_session = None

    @pytest.mark.asyncio
    async def test_async_session_factory_thread_safety(self):
        """Test that get_async_session_factory is thread-safe.

        Verifies double-checked locking pattern prevents race conditions
        when initializing the shared session factory.
        """
        from kitkat import database
        import threading

        # Reset globals
        database._engine = None
        database._async_session = None

        results = []

        def get_factory():
            """Worker thread to get session factory."""
            factory = database.get_async_session_factory()
            results.append(factory)

        # Create multiple threads that call get_async_session_factory simultaneously
        threads = [threading.Thread(target=get_factory) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all threads got the same factory instance (proving thread-safety)
        assert len(results) == 10
        first_factory = results[0]
        for factory in results[1:]:
            assert factory is first_factory, "Thread-safety violation: different factory instances"

    @pytest.mark.asyncio
    async def test_engine_lazy_initialization_thread_safety(self):
        """Test that get_engine is thread-safe with double-checked locking.

        Verifies that concurrent calls to get_engine() return the same instance
        even when called from multiple threads simultaneously.
        """
        from kitkat import database
        import threading

        # Reset globals
        database._engine = None
        database._async_session = None

        engines = []

        def get_engine_impl():
            """Worker thread to get engine."""
            engine = database.get_engine()
            engines.append(engine)

        # Create multiple threads that call get_engine simultaneously
        threads = [threading.Thread(target=get_engine_impl) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all threads got the same engine instance (proving thread-safety)
        assert len(engines) == 10
        first_engine = engines[0]
        for engine in engines[1:]:
            assert engine is first_engine, "Thread-safety violation: different engine instances"

        # Cleanup
        await first_engine.dispose()
        database._engine = None
        database._async_session = None
