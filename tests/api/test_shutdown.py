"""Tests for graceful shutdown functionality (Story 2.11)."""

import asyncio
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import check_shutdown
from kitkat.services.shutdown_manager import ShutdownManager


class TestCheckShutdownDependency:
    """Test check_shutdown dependency for rejecting requests during shutdown."""

    @pytest.mark.asyncio
    async def test_check_shutdown_allows_requests_when_not_shutting_down(self):
        """Verify requests are allowed when shutdown is not in progress."""
        from unittest.mock import Mock

        manager = ShutdownManager()
        request = Mock()
        request.app.state.shutdown_manager = manager

        # Should not raise any exception
        result = await check_shutdown(request)
        assert result is None

    @pytest.mark.asyncio
    async def test_check_shutdown_rejects_requests_during_shutdown(self):
        """Verify requests are rejected with 503 during shutdown."""
        from fastapi import HTTPException
        from unittest.mock import Mock

        manager = ShutdownManager()
        manager.initiate_shutdown()
        request = Mock()
        request.app.state.shutdown_manager = manager

        # Should raise HTTPException with 503 status
        with pytest.raises(HTTPException) as exc_info:
            await check_shutdown(request)

        assert exc_info.value.status_code == 503
        detail = exc_info.value.detail
        assert detail["code"] == "SERVICE_UNAVAILABLE"
        assert "shutting down" in detail["error"].lower()
        assert detail["signal_id"] is None
        assert detail["dex"] is None
        assert "timestamp" in detail

    @pytest.mark.asyncio
    async def test_check_shutdown_handles_missing_shutdown_manager(self):
        """Verify dependency handles missing shutdown manager gracefully."""
        from unittest.mock import Mock

        request = Mock()
        request.app.state.shutdown_manager = None

        # Should not raise any exception when manager is None
        result = await check_shutdown(request)
        assert result is None

    @pytest.mark.asyncio
    async def test_check_shutdown_response_format_has_timestamp(self):
        """Verify 503 response includes ISO timestamp."""
        from fastapi import HTTPException
        from unittest.mock import Mock

        manager = ShutdownManager()
        manager.initiate_shutdown()
        request = Mock()
        request.app.state.shutdown_manager = manager

        with pytest.raises(HTTPException) as exc_info:
            await check_shutdown(request)

        detail = exc_info.value.detail
        timestamp = detail["timestamp"]
        assert timestamp.endswith("Z")
        # Verify it's a valid ISO format
        assert "T" in timestamp


class TestWebhookShutdownBehavior:
    """Test webhook behavior during shutdown."""

    @pytest.mark.asyncio
    async def test_webhook_tracks_in_flight_orders(self):
        """Verify webhook tracks signal processing."""
        manager = ShutdownManager()

        # Simulate webhook processing with in-flight tracking
        signal_id = "test-signal-123"

        async with manager.track_in_flight(signal_id):
            assert manager.in_flight_count == 1
            assert signal_id in manager.get_in_flight_signals()

        assert manager.in_flight_count == 0

    @pytest.mark.asyncio
    async def test_webhook_completes_during_shutdown(self):
        """Verify webhooks can complete even after shutdown initiated."""
        manager = ShutdownManager()
        signal_id = "shutdown-test-signal"

        # Start processing
        processing_task = asyncio.create_task(self._process_signal(manager, signal_id))

        # Give processing time to start
        await asyncio.sleep(0.01)

        # Initiate shutdown
        manager.initiate_shutdown()
        assert manager.is_shutting_down is True

        # Signal should still be in flight
        assert manager.in_flight_count == 1

        # Wait for processing to complete
        await processing_task

        # Now it should be done
        assert manager.in_flight_count == 0

    async def _process_signal(self, manager: ShutdownManager, signal_id: str):
        """Helper to simulate signal processing."""
        async with manager.track_in_flight(signal_id):
            await asyncio.sleep(0.05)  # Simulate processing


class TestShutdownGracePeriod:
    """Test shutdown grace period behavior."""

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_completion_within_grace_period(self):
        """Verify shutdown waits for orders to complete within grace period."""
        manager = ShutdownManager(grace_period_seconds=5)
        signal_ids = ["sig-1", "sig-2", "sig-3"]

        for signal_id in signal_ids:
            manager._in_flight.add(signal_id)

        manager.initiate_shutdown()

        # Schedule completion
        async def complete_signals():
            for signal_id in signal_ids:
                await asyncio.sleep(0.1)
                manager._in_flight.discard(signal_id)
            manager._shutdown_event.set()

        asyncio.create_task(complete_signals())

        # Wait should complete successfully
        result = await manager.wait_for_completion()

        assert result is True

    @pytest.mark.asyncio
    async def test_shutdown_times_out_when_orders_stuck(self):
        """Verify shutdown times out if orders don't complete."""
        manager = ShutdownManager(grace_period_seconds=0.1)

        # Add signals that won't complete
        manager._in_flight.add("stuck-signal-1")
        manager._in_flight.add("stuck-signal-2")

        manager.initiate_shutdown()

        # Wait should timeout
        result = await manager.wait_for_completion()

        assert result is False
        assert manager.in_flight_count == 2  # Signals still there


class TestWebhookRejectionDuring503:
    """Test that webhook properly rejects requests with 503 during shutdown."""

    @pytest.mark.asyncio
    async def test_webhook_503_response_format(self):
        """Verify 503 response matches standard error response format."""
        from fastapi import HTTPException
        from unittest.mock import Mock

        manager = ShutdownManager()
        manager.initiate_shutdown()
        request = Mock()
        request.app.state.shutdown_manager = manager

        with pytest.raises(HTTPException) as exc_info:
            await check_shutdown(request)

        detail = exc_info.value.detail

        # Verify standard error format fields
        assert "error" in detail
        assert "code" in detail
        assert "signal_id" in detail
        assert "dex" in detail
        assert "timestamp" in detail

        # Verify expected values
        assert detail["code"] == "SERVICE_UNAVAILABLE"
        assert detail["signal_id"] is None
        assert detail["dex"] is None

    @pytest.mark.asyncio
    async def test_webhook_accepts_requests_before_shutdown(self):
        """Verify webhook acceptance when shutdown not initiated."""
        from unittest.mock import Mock

        manager = ShutdownManager()
        request = Mock()
        request.app.state.shutdown_manager = manager

        # Should not raise when not shutting down
        result = await check_shutdown(request)
        assert result is None
