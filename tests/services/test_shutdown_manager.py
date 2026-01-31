"""Unit tests for ShutdownManager service (Story 2.11)."""

import asyncio
import pytest

from kitkat.services.shutdown_manager import ShutdownManager


class TestShutdownManagerInitialization:
    """Test ShutdownManager initialization and initial state."""

    def test_is_shutting_down_initially_false(self):
        """Verify shutdown flag is initially false."""
        manager = ShutdownManager(grace_period_seconds=30)
        assert manager.is_shutting_down is False

    def test_in_flight_count_initially_zero(self):
        """Verify no orders in flight initially."""
        manager = ShutdownManager(grace_period_seconds=30)
        assert manager.in_flight_count == 0

    def test_grace_period_configured(self):
        """Verify grace period is stored."""
        manager = ShutdownManager(grace_period_seconds=60)
        assert manager._grace_period == 60

    def test_default_grace_period_thirty_seconds(self):
        """Verify default grace period is 30 seconds."""
        manager = ShutdownManager()
        assert manager._grace_period == 30


class TestShutdownManagerInitiation:
    """Test shutdown initiation."""

    def test_initiate_shutdown_sets_flag(self):
        """Verify initiate_shutdown sets the shutdown flag."""
        manager = ShutdownManager()
        manager.initiate_shutdown()
        assert manager.is_shutting_down is True

    def test_initiate_shutdown_idempotent(self):
        """Verify initiate_shutdown can be called multiple times safely."""
        manager = ShutdownManager()
        manager.initiate_shutdown()
        manager.initiate_shutdown()  # Should not raise
        assert manager.is_shutting_down is True


class TestInFlightTracking:
    """Test in-flight order tracking."""

    @pytest.mark.asyncio
    async def test_track_in_flight_adds_signal(self):
        """Verify track_in_flight context manager adds signal."""
        manager = ShutdownManager()
        signal_id = "test-signal-123"

        async with manager.track_in_flight(signal_id):
            assert manager.in_flight_count == 1
            assert signal_id in manager.get_in_flight_signals()

    @pytest.mark.asyncio
    async def test_track_in_flight_removes_signal_on_exit(self):
        """Verify signal is removed when context exits."""
        manager = ShutdownManager()
        signal_id = "test-signal-456"

        async with manager.track_in_flight(signal_id):
            assert manager.in_flight_count == 1

        assert manager.in_flight_count == 0
        assert signal_id not in manager.get_in_flight_signals()

    @pytest.mark.asyncio
    async def test_track_in_flight_multiple_signals(self):
        """Verify multiple signals can be tracked simultaneously."""
        manager = ShutdownManager()
        signal_ids = ["signal-1", "signal-2", "signal-3"]

        # Manually track multiple signals (simulating concurrent processing)
        for signal_id in signal_ids:
            manager._in_flight.add(signal_id)

        assert manager.in_flight_count == 3
        assert set(manager.get_in_flight_signals()) == set(signal_ids)

    @pytest.mark.asyncio
    async def test_track_in_flight_cleans_up_on_exception(self):
        """Verify signal is removed even if exception occurs in context."""
        manager = ShutdownManager()
        signal_id = "test-signal-exception"

        try:
            async with manager.track_in_flight(signal_id):
                assert manager.in_flight_count == 1
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Signal should be cleaned up despite exception
        assert manager.in_flight_count == 0
        assert signal_id not in manager.get_in_flight_signals()

    @pytest.mark.asyncio
    async def test_get_in_flight_signals_returns_list(self):
        """Verify get_in_flight_signals returns a list."""
        manager = ShutdownManager()
        result = manager.get_in_flight_signals()
        assert isinstance(result, list)
        assert len(result) == 0


class TestWaitForCompletion:
    """Test waiting for in-flight orders to complete."""

    @pytest.mark.asyncio
    async def test_wait_for_completion_immediate_if_no_inflight(self):
        """Verify immediate completion if no in-flight orders."""
        manager = ShutdownManager()
        manager.initiate_shutdown()

        result = await manager.wait_for_completion()

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_completion_returns_true_on_completion(self):
        """Verify True returned when all in-flight orders complete."""
        manager = ShutdownManager()
        manager.initiate_shutdown()

        # Add an in-flight signal
        manager._in_flight.add("signal-1")

        # Schedule signal removal after short delay
        async def remove_signal():
            await asyncio.sleep(0.1)
            manager._in_flight.discard("signal-1")
            manager._shutdown_event.set()

        asyncio.create_task(remove_signal())

        result = await manager.wait_for_completion()

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_completion_returns_false_on_timeout(self):
        """Verify False returned when grace period expires."""
        manager = ShutdownManager(grace_period_seconds=0.1)
        manager.initiate_shutdown()

        # Add an in-flight signal that won't complete
        manager._in_flight.add("signal-stuck")

        result = await manager.wait_for_completion()

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_completion_with_multiple_signals(self):
        """Verify completion waits for all signals."""
        manager = ShutdownManager(grace_period_seconds=2)
        manager.initiate_shutdown()

        # Add multiple signals
        signals = ["sig-1", "sig-2", "sig-3"]
        for signal_id in signals:
            manager._in_flight.add(signal_id)

        # Schedule sequential removal
        async def remove_all():
            for signal_id in signals:
                await asyncio.sleep(0.05)
                manager._in_flight.discard(signal_id)
            manager._shutdown_event.set()

        asyncio.create_task(remove_all())

        result = await manager.wait_for_completion()

        assert result is True
        assert manager.in_flight_count == 0


class TestShutdownIntegration:
    """Test shutdown integration scenarios."""

    @pytest.mark.asyncio
    async def test_shutdown_flow_with_inflight_completion(self):
        """Integration test: shutdown with in-flight order completion."""
        manager = ShutdownManager(grace_period_seconds=2)

        # Simulate signal processing
        signal_id = "integration-test-signal"

        async def process_signal():
            async with manager.track_in_flight(signal_id):
                await asyncio.sleep(0.05)  # Simulate processing

        # Start signal processing
        task = asyncio.create_task(process_signal())

        # Give it time to start
        await asyncio.sleep(0.01)

        # Initiate shutdown
        manager.initiate_shutdown()
        assert manager.is_shutting_down is True

        # Wait for completion
        result = await manager.wait_for_completion()

        assert result is True
        assert task.done()

    @pytest.mark.asyncio
    async def test_shutdown_flow_with_timeout(self):
        """Integration test: shutdown timeout when orders don't complete."""
        manager = ShutdownManager(grace_period_seconds=0.2)

        # Add in-flight signal that won't complete
        manager._in_flight.add("stuck-signal")
        manager.initiate_shutdown()

        # Wait should timeout
        result = await manager.wait_for_completion()

        assert result is False
        # Signal should still be in flight (shutdown doesn't remove it)
        assert manager.in_flight_count == 1
