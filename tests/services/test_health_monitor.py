"""Unit tests for HealthMonitor background service (Story 4.3).

Tests comprehensive health monitoring, auto-recovery, and alert integration
for DEX adapters with exponential backoff reconnection.

Story 4.3: Auto-Recovery After Outage
- AC#1: Health check polling every 30 seconds
- AC#2: Degraded state detection with alerts
- AC#3: Exponential backoff reconnection (1s, 2s, 4s, 8s, max 30s)
- AC#4: Offline threshold (3 consecutive failures)
- AC#5: Automatic recovery detection
- AC#6: Zero manual intervention
- AC#7: Configurable interval
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kitkat.models import HealthStatus
from kitkat.services.health_monitor import HealthMonitor


def create_health_status(
    dex_id: str = "mock",
    status: str = "healthy",
    connected: bool = True,
    latency_ms: int = 50,
    error_message: Optional[str] = None,
) -> HealthStatus:
    """Helper to create HealthStatus with all required fields."""
    return HealthStatus(
        dex_id=dex_id,
        status=status,
        connected=connected,
        latency_ms=latency_ms,
        last_check=datetime.now(timezone.utc),
        error_message=error_message,
    )


@pytest.fixture
def mock_adapter():
    """Create a mock DEX adapter for testing."""
    adapter = MagicMock()
    adapter.dex_id = "mock"
    adapter.get_health_status = AsyncMock(
        return_value=create_health_status(dex_id="mock", status="healthy")
    )
    adapter.connect = AsyncMock()
    adapter.disconnect = AsyncMock()
    return adapter


@pytest.fixture
def mock_extended_adapter():
    """Create a mock Extended adapter."""
    adapter = MagicMock()
    adapter.dex_id = "extended"
    adapter.get_health_status = AsyncMock(
        return_value=create_health_status(dex_id="extended", status="healthy")
    )
    adapter.connect = AsyncMock()
    adapter.disconnect = AsyncMock()
    return adapter


@pytest.fixture
def mock_alert_service():
    """Create a mock Telegram alert service."""
    service = MagicMock()
    service.enabled = True
    service.send_dex_status_change = AsyncMock()
    return service


class TestHealthMonitorInitialization:
    """Test HealthMonitor initialization."""

    def test_init_with_defaults(self, mock_adapter, mock_alert_service):
        """Test initialization with default settings."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )
        assert monitor._check_interval == 30
        assert monitor._max_failures == 3
        assert monitor._max_backoff == 30
        assert not monitor.is_running
        # Failure counts dict may be empty or have dex_id key
        has_dex = mock_adapter.dex_id in monitor._failure_counts
        assert len(monitor._failure_counts) == 0 or has_dex

    def test_init_with_custom_settings(self, mock_adapter, mock_alert_service):
        """Test initialization with custom settings (AC#7)."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            check_interval=60,
            max_failures=5,
            max_backoff=60,
        )
        assert monitor._check_interval == 60
        assert monitor._max_failures == 5
        assert monitor._max_backoff == 60

    def test_init_empty_adapters(self, mock_alert_service):
        """Test initialization with no adapters."""
        monitor = HealthMonitor(
            adapters=[],
            alert_service=mock_alert_service,
        )
        assert monitor._adapters == []


class TestHealthMonitorLifecycle:
    """Test HealthMonitor start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_background_task(
        self, mock_adapter, mock_alert_service
    ):
        """Test that start() creates a background monitoring task."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            check_interval=1,  # Short interval for testing
        )

        assert not monitor.is_running
        await monitor.start()
        assert monitor.is_running
        assert monitor._monitor_task is not None

        # Let it run briefly
        await asyncio.sleep(0.1)

        # Stop
        await monitor.stop()
        assert not monitor.is_running

    @pytest.mark.asyncio
    async def test_stop_cancels_background_task(self, mock_adapter, mock_alert_service):
        """Test that stop() gracefully cancels the monitoring task."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            check_interval=1,
        )

        await monitor.start()
        await asyncio.sleep(0.1)
        await monitor.stop()

        assert not monitor.is_running
        # Task should be cancelled
        assert monitor._monitor_task.cancelled() or monitor._monitor_task.done()

    @pytest.mark.asyncio
    async def test_double_start_warning(self, mock_adapter, mock_alert_service):
        """Test starting twice logs warning, no duplicate tasks."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            check_interval=1,
        )

        await monitor.start()
        first_task = monitor._monitor_task

        # Start again - should warn and not create new task
        await monitor.start()
        assert monitor._monitor_task is first_task

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, mock_adapter, mock_alert_service):
        """Test that stop() is safe to call when not running."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        # Should not raise
        await monitor.stop()
        assert not monitor.is_running


class TestHealthCheckPolling:
    """Test health check polling behavior."""

    @pytest.mark.asyncio
    async def test_health_check_calls_adapter(self, mock_adapter, mock_alert_service):
        """Test that health check calls adapter.get_health_status() (AC#1)."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            check_interval=100,  # Long interval so we control timing
        )

        # Call internal method directly
        await monitor._check_all_adapters()

        mock_adapter.get_health_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_parallel_adapter_checks(
        self, mock_adapter, mock_extended_adapter, mock_alert_service
    ):
        """Test that multiple adapters are checked in parallel."""
        monitor = HealthMonitor(
            adapters=[mock_adapter, mock_extended_adapter],
            alert_service=mock_alert_service,
        )

        await monitor._check_all_adapters()

        mock_adapter.get_health_status.assert_called_once()
        mock_extended_adapter.get_health_status.assert_called_once()


class TestFailureTracking:
    """Test consecutive failure counting."""

    @pytest.mark.asyncio
    async def test_failure_count_increments(self, mock_adapter, mock_alert_service):
        """Test that failure count increments on health check failure (AC#4)."""
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        await monitor._check_all_adapters()
        assert monitor.get_failure_count("mock") == 1

        await monitor._check_all_adapters()
        assert monitor.get_failure_count("mock") == 2

    @pytest.mark.asyncio
    async def test_failure_count_resets_on_success(
        self, mock_adapter, mock_alert_service
    ):
        """Test that failure count resets on successful health check (AC#5)."""
        # First fail
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        await monitor._check_all_adapters()
        assert monitor.get_failure_count("mock") == 1

        # Now succeed
        mock_adapter.get_health_status = AsyncMock(
            return_value=create_health_status(dex_id="mock", status="healthy")
        )

        await monitor._check_all_adapters()
        assert monitor.get_failure_count("mock") == 0

    @pytest.mark.asyncio
    async def test_unhealthy_status_counts_as_failure(
        self, mock_adapter, mock_alert_service
    ):
        """Test that non-healthy status counts as failure."""
        mock_adapter.get_health_status = AsyncMock(
            return_value=create_health_status(dex_id="mock", status="degraded")
        )

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        await monitor._check_all_adapters()
        assert monitor.get_failure_count("mock") == 1


class TestStatusTransitions:
    """Test DEX status state transitions."""

    @pytest.mark.asyncio
    async def test_healthy_to_degraded_on_first_failure(
        self, mock_adapter, mock_alert_service
    ):
        """Test transition from healthy to degraded on first failure (AC#2)."""
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        await monitor._check_all_adapters()

        assert monitor.get_status("mock") == "degraded"

    @pytest.mark.asyncio
    async def test_degraded_to_offline_on_max_failures(
        self, mock_adapter, mock_alert_service
    ):
        """Test transition from degraded to offline after max failures (AC#4)."""
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            max_failures=3,
        )

        # First 2 failures: degraded
        await monitor._check_all_adapters()
        assert monitor.get_status("mock") == "degraded"

        await monitor._check_all_adapters()
        assert monitor.get_status("mock") == "degraded"

        # Third failure: offline
        await monitor._check_all_adapters()
        assert monitor.get_status("mock") == "offline"

    @pytest.mark.asyncio
    async def test_offline_to_healthy_on_recovery(
        self, mock_adapter, mock_alert_service
    ):
        """Test transition from offline to healthy on recovery (AC#5)."""
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            max_failures=2,
        )

        # Make it go offline
        await monitor._check_all_adapters()
        await monitor._check_all_adapters()
        assert monitor.get_status("mock") == "offline"

        # Clear reconnecting flag to allow health check
        # (In production, reconnection would complete or timeout first)
        monitor._reconnecting["mock"] = False

        # Now recover
        mock_adapter.get_health_status = AsyncMock(
            return_value=create_health_status(dex_id="mock", status="healthy")
        )

        await monitor._check_all_adapters()
        assert monitor.get_status("mock") == "healthy"


class TestAlertIntegration:
    """Test Telegram alert integration."""

    @pytest.mark.asyncio
    async def test_alert_on_degraded_transition(
        self, mock_adapter, mock_alert_service
    ):
        """Test alert sent when transitioning to degraded (AC#2)."""
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        await monitor._check_all_adapters()
        # Give async task time to be created
        await asyncio.sleep(0.01)

        # Alert should have been triggered
        mock_alert_service.send_dex_status_change.assert_called_once_with(
            dex_id="mock",
            old_status="healthy",
            new_status="degraded",
        )

    @pytest.mark.asyncio
    async def test_alert_on_offline_transition(
        self, mock_adapter, mock_alert_service
    ):
        """Test alert sent when transitioning to offline (AC#4)."""
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            max_failures=2,
        )

        # First failure: degraded alert
        await monitor._check_all_adapters()
        await asyncio.sleep(0.01)

        # Second failure: offline alert
        await monitor._check_all_adapters()
        await asyncio.sleep(0.01)

        # Should have 2 alerts: healthy->degraded, degraded->offline
        assert mock_alert_service.send_dex_status_change.call_count == 2
        calls = mock_alert_service.send_dex_status_change.call_args_list
        assert calls[1][1] == {
            "dex_id": "mock",
            "old_status": "degraded",
            "new_status": "offline",
        }

    @pytest.mark.asyncio
    async def test_alert_on_recovery(
        self, mock_adapter, mock_alert_service
    ):
        """Test recovery alert sent when returning to healthy (AC#5)."""
        # Start with failures to get to degraded
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        await monitor._check_all_adapters()
        await asyncio.sleep(0.01)
        mock_alert_service.send_dex_status_change.reset_mock()

        # Now recover
        mock_adapter.get_health_status = AsyncMock(
            return_value=create_health_status(dex_id="mock", status="healthy")
        )

        await monitor._check_all_adapters()
        await asyncio.sleep(0.01)

        mock_alert_service.send_dex_status_change.assert_called_once_with(
            dex_id="mock",
            old_status="degraded",
            new_status="healthy",
        )

    @pytest.mark.asyncio
    async def test_no_alert_when_status_unchanged(
        self, mock_adapter, mock_alert_service
    ):
        """Test no alert sent when status remains the same."""
        mock_adapter.get_health_status = AsyncMock(
            return_value=create_health_status(dex_id="mock", status="healthy")
        )

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        await monitor._check_all_adapters()
        await monitor._check_all_adapters()
        await asyncio.sleep(0.01)

        # No status transitions, no alerts
        mock_alert_service.send_dex_status_change.assert_not_called()


class TestReconnection:
    """Test reconnection with exponential backoff."""

    @pytest.mark.asyncio
    async def test_reconnection_triggered_on_offline(
        self, mock_adapter, mock_alert_service
    ):
        """Test that reconnection is triggered when transitioning to offline (AC#3)."""
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            max_failures=2,  # Go offline after 2 failures
        )

        # First failure: degraded (no reconnection yet)
        await monitor._check_all_adapters()
        await asyncio.sleep(0.01)
        assert not monitor._reconnecting.get("mock", False)

        # Second failure: offline (reconnection triggered)
        await monitor._check_all_adapters()
        # Give reconnection task time to start
        await asyncio.sleep(0.05)

        # Reconnection should have been triggered
        # Disconnect should have been called as part of reconnection attempt
        mock_adapter.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_reconnection_calls_connect(
        self, mock_adapter, mock_alert_service
    ):
        """Test successful reconnection calls adapter.connect() (AC#3)."""
        # Make first health check fail
        fail_count = 0

        async def health_check_with_eventual_success():
            nonlocal fail_count
            fail_count += 1
            if fail_count <= 1:
                raise Exception("Failed")
            return create_health_status(dex_id="mock", status="healthy")

        mock_adapter.get_health_status = AsyncMock(
            side_effect=health_check_with_eventual_success
        )

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        # Trigger reconnection
        await monitor._attempt_reconnection(mock_adapter)

        # connect() should have been called
        mock_adapter.connect.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_reconnection_prevented(
        self, mock_adapter, mock_alert_service
    ):
        """Test that concurrent reconnection attempts are prevented."""
        # Make reconnection slow
        async def slow_connect():
            await asyncio.sleep(0.1)

        mock_adapter.connect = AsyncMock(side_effect=slow_connect)
        mock_adapter.get_health_status = AsyncMock(
            return_value=create_health_status(dex_id="mock", status="healthy")
        )

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        # Start two reconnection attempts concurrently
        task1 = asyncio.create_task(monitor._attempt_reconnection(mock_adapter))
        await asyncio.sleep(0.01)  # Let first one start
        task2 = asyncio.create_task(monitor._attempt_reconnection(mock_adapter))

        await asyncio.gather(task1, task2)

        # connect() should only be called once (second attempt skipped)
        assert mock_adapter.connect.call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, mock_adapter, mock_alert_service):
        """Test that reconnection uses exponential backoff (AC#3).

        Verifies backoff sequence: 1s, 2s, 4s... with jitter (0.8-1.2x).
        """
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        # Make reconnection fail 3 times, then succeed
        attempt = 0

        async def failing_then_success():
            nonlocal attempt
            attempt += 1
            if attempt <= 3:
                raise Exception(f"Attempt {attempt} failed")
            return create_health_status(dex_id="mock", status="healthy")

        mock_adapter.get_health_status = AsyncMock(side_effect=failing_then_success)

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            max_backoff=30,
        )

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await monitor._reconnect_with_backoff(mock_adapter)

        # Should have 3 sleep calls (after each of 3 failures)
        assert len(sleep_calls) == 3

        # Verify exponential progression with jitter (0.8-1.2x)
        # Expected base delays: 1, 2, 4
        assert 0.8 <= sleep_calls[0] <= 1.2  # 1s * jitter
        assert 1.6 <= sleep_calls[1] <= 2.4  # 2s * jitter
        assert 3.2 <= sleep_calls[2] <= 4.8  # 4s * jitter


class TestStatusQueries:
    """Test status query methods."""

    def test_get_status_default_healthy(self, mock_adapter, mock_alert_service):
        """Test that unknown DEX returns healthy by default."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        assert monitor.get_status("unknown") == "healthy"

    def test_get_failure_count_default_zero(self, mock_adapter, mock_alert_service):
        """Test that unknown DEX returns zero failure count."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        assert monitor.get_failure_count("unknown") == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_adapter_list(self, mock_alert_service):
        """Test monitoring with no adapters doesn't crash."""
        monitor = HealthMonitor(
            adapters=[],
            alert_service=mock_alert_service,
        )

        await monitor.start()
        await asyncio.sleep(0.05)
        await monitor.stop()

        # Should complete without error

    @pytest.mark.asyncio
    async def test_health_check_loop_error_recovery(
        self, mock_adapter, mock_alert_service
    ):
        """Test that monitoring loop continues after check error."""
        call_count = 0

        async def failing_health_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Unexpected error")
            return create_health_status(dex_id="mock", status="healthy")

        mock_adapter.get_health_status = AsyncMock(side_effect=failing_health_check)

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            check_interval=0.01,  # Very short for testing
        )

        await monitor.start()
        await asyncio.sleep(0.05)  # Let it run a few cycles
        await monitor.stop()

        # Should have been called multiple times despite first failure
        assert call_count > 1

    @pytest.mark.asyncio
    async def test_skip_check_during_reconnection(
        self, mock_adapter, mock_alert_service
    ):
        """Test that health check is skipped while reconnection is in progress."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        # Simulate reconnection in progress
        monitor._reconnecting["mock"] = True

        await monitor._check_adapter(mock_adapter)

        # get_health_status should NOT have been called
        mock_adapter.get_health_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_health_check_timeout_treated_as_failure(
        self, mock_adapter, mock_alert_service
    ):
        """Test that health check timeout is treated as a failure."""

        async def hanging_health_check():
            # Simulate a hanging health check
            await asyncio.sleep(20)  # Will be interrupted by timeout
            return create_health_status(dex_id="mock", status="healthy")

        mock_adapter.get_health_status = AsyncMock(side_effect=hanging_health_check)

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
        )

        # Use a shorter timeout for testing by patching asyncio.wait_for
        original_wait_for = asyncio.wait_for

        async def fast_timeout_wait_for(coro, timeout):
            return await original_wait_for(coro, timeout=0.01)

        with patch("asyncio.wait_for", side_effect=fast_timeout_wait_for):
            await monitor._check_adapter(mock_adapter)

        # Timeout should be treated as failure
        assert monitor.get_failure_count("mock") == 1
        assert monitor.get_status("mock") == "degraded"


class TestConfigurationFromSettings:
    """Test configuration from settings."""

    @pytest.mark.asyncio
    async def test_interval_from_settings(self, mock_adapter, mock_alert_service):
        """Test that check interval is configurable (AC#7)."""
        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            check_interval=60,
        )

        assert monitor._check_interval == 60

    @pytest.mark.asyncio
    async def test_max_failures_from_settings(self, mock_adapter, mock_alert_service):
        """Test that max failures threshold is configurable."""
        mock_adapter.get_health_status = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(
            adapters=[mock_adapter],
            alert_service=mock_alert_service,
            max_failures=5,
        )

        # 4 failures should still be degraded
        for _ in range(4):
            await monitor._check_all_adapters()

        assert monitor.get_status("mock") == "degraded"

        # 5th failure should go offline
        await monitor._check_all_adapters()
        assert monitor.get_status("mock") == "offline"
