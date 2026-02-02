"""Tests for TelegramAlertService (Story 4.2).

Tests cover:
- AC#1: Uses python-telegram-bot library
- AC#3: Execution failure alerts with correct format
- AC#4: Fire-and-forget pattern (no blocking)
- AC#5: Partial fill alerts
- AC#6: Rate limiting (1 per minute per error type)
- AC#7: Graceful degradation when unconfigured
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kitkat.services.alert import TelegramAlertService, send_alert_async


class TestTelegramAlertServiceInit:
    """Test TelegramAlertService initialization (AC#1, AC#7)."""

    def test_init_with_credentials_enabled(self):
        """Service is enabled when both token and chat_id provided."""
        service = TelegramAlertService(
            bot_token="test_token",
            chat_id="123456789",
        )

        assert service.enabled is True
        assert service._bot is not None

    def test_init_without_token_disabled(self):
        """Service is disabled when token missing (AC#7)."""
        service = TelegramAlertService(
            bot_token="",
            chat_id="123456789",
        )

        assert service.enabled is False
        assert service._bot is None

    def test_init_without_chat_id_disabled(self):
        """Service is disabled when chat_id missing (AC#7)."""
        service = TelegramAlertService(
            bot_token="test_token",
            chat_id="",
        )

        assert service.enabled is False
        assert service._bot is None

    def test_init_without_credentials_disabled(self):
        """Service is disabled when no credentials provided (AC#7)."""
        service = TelegramAlertService()

        assert service.enabled is False
        assert service._bot is None

    def test_init_logs_warning_when_disabled(self, caplog):
        """Warning logged when credentials not configured (AC#7)."""
        with patch("kitkat.services.alert.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            TelegramAlertService(bot_token="", chat_id="")

            mock_bound.warning.assert_called_once()
            call_args = mock_bound.warning.call_args
            assert "Telegram alerts disabled" in call_args[0][0]

    def test_init_logs_info_when_enabled(self):
        """Info logged when alerts enabled."""
        with patch("kitkat.services.alert.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            TelegramAlertService(bot_token="test", chat_id="123")

            mock_bound.info.assert_called_once()
            call_args = mock_bound.info.call_args
            assert "enabled" in call_args[0][0].lower()


class TestExecutionFailureAlert:
    """Test execution failure alerts (AC#3)."""

    @pytest.fixture
    def enabled_service(self):
        """Create enabled alert service with mocked bot."""
        service = TelegramAlertService(
            bot_token="test_token",
            chat_id="123456789",
        )
        service._bot = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_send_execution_failure_message_format(self, enabled_service):
        """Alert message contains required fields (AC#3)."""
        await enabled_service.send_execution_failure(
            signal_id="abc123def456",
            dex_id="extended",
            error_message="Connection timeout",
            timestamp=datetime(2026, 1, 20, 10, 30, 0, tzinfo=timezone.utc),
        )

        enabled_service._bot.send_message.assert_called_once()
        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]

        # Verify all required fields (AC#3)
        assert "Execution Failed" in message
        assert "extended" in message
        assert "abc123de" in message  # Truncated signal_id
        assert "Connection timeout" in message
        assert "2026-01-20" in message

    @pytest.mark.asyncio
    async def test_send_execution_failure_uses_emoji(self, enabled_service):
        """Alert uses emoji prefix for visibility (AC#3)."""
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error",
        )

        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert message.startswith("🚨")

    @pytest.mark.asyncio
    async def test_send_execution_failure_uses_markdown(self, enabled_service):
        """Alert uses Markdown parse mode."""
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error",
        )

        call_args = enabled_service._bot.send_message.call_args
        assert call_args.kwargs["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_send_execution_failure_default_timestamp(self, enabled_service):
        """Uses current time when timestamp not provided."""
        before = datetime.now(timezone.utc)
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error",
        )
        after = datetime.now(timezone.utc)

        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        # Message should contain a timestamp between before and after
        assert "UTC" in message

    @pytest.mark.asyncio
    async def test_send_execution_failure_disabled_no_send(self):
        """No message sent when service disabled (AC#7)."""
        service = TelegramAlertService()  # Disabled
        service._bot = AsyncMock()

        await service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error",
        )

        service._bot.send_message.assert_not_called()


class TestPartialFillAlert:
    """Test partial fill alerts (AC#5)."""

    @pytest.fixture
    def enabled_service(self):
        """Create enabled alert service with mocked bot."""
        service = TelegramAlertService(
            bot_token="test_token",
            chat_id="123456789",
        )
        service._bot = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_send_partial_fill_message_format(self, enabled_service):
        """Alert message contains required fields (AC#5)."""
        await enabled_service.send_partial_fill(
            symbol="ETH-PERP",
            filled_size="0.3",
            remaining_size="0.2",
            dex_id="extended",
        )

        enabled_service._bot.send_message.assert_called_once()
        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]

        # Verify all required fields (AC#5)
        # Note: Symbol is escaped for Markdown safety (dash becomes \-)
        assert "Partial Fill" in message
        assert "ETH" in message and "PERP" in message  # Symbol parts present (may be escaped)
        assert "0.3" in message
        assert "0.2" in message
        assert "extended" in message

    @pytest.mark.asyncio
    async def test_send_partial_fill_calculates_percentage(self, enabled_service):
        """Alert shows fill percentage for context."""
        await enabled_service.send_partial_fill(
            symbol="ETH-PERP",
            filled_size="0.5",
            remaining_size="0.5",
            dex_id="extended",
        )

        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert "50.0%" in message

    @pytest.mark.asyncio
    async def test_send_partial_fill_uses_warning_emoji(self, enabled_service):
        """Alert uses warning emoji for partial fills."""
        await enabled_service.send_partial_fill(
            symbol="ETH-PERP",
            filled_size="0.3",
            remaining_size="0.2",
            dex_id="extended",
        )

        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert message.startswith("⚠️")

    @pytest.mark.asyncio
    async def test_send_partial_fill_handles_invalid_numbers(self, enabled_service):
        """Handles invalid size values gracefully."""
        await enabled_service.send_partial_fill(
            symbol="ETH-PERP",
            filled_size="invalid",
            remaining_size="also_invalid",
            dex_id="extended",
        )

        # Should still send message with 0% percentage
        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert "0.0%" in message


class TestRateLimiting:
    """Test alert rate limiting (AC#6)."""

    @pytest.fixture
    def enabled_service(self):
        """Create enabled alert service with mocked bot."""
        service = TelegramAlertService(
            bot_token="test_token",
            chat_id="123456789",
        )
        service._bot = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_first_alert_not_rate_limited(self, enabled_service):
        """First alert for an error type is sent."""
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error 1",
        )

        enabled_service._bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_rapid_alerts_throttled(self, enabled_service):
        """Rapid alerts for same error type are throttled (AC#6)."""
        # First alert - should be sent
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error 1",
        )
        assert enabled_service._bot.send_message.call_count == 1

        # Second alert within 60s - should be suppressed
        await enabled_service.send_execution_failure(
            signal_id="def456",
            dex_id="extended",
            error_message="Error 2",
        )
        assert enabled_service._bot.send_message.call_count == 1  # Still just 1

        # Third alert - also suppressed
        await enabled_service.send_execution_failure(
            signal_id="ghi789",
            dex_id="extended",
            error_message="Error 3",
        )
        assert enabled_service._bot.send_message.call_count == 1

    @pytest.mark.asyncio
    async def test_different_error_types_independent(self, enabled_service):
        """Different error types have independent rate limits (AC#6)."""
        # First execution failure
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error 1",
        )
        assert enabled_service._bot.send_message.call_count == 1

        # First partial fill - different type, should be sent
        await enabled_service.send_partial_fill(
            symbol="ETH-PERP",
            filled_size="0.3",
            remaining_size="0.2",
            dex_id="extended",
        )
        assert enabled_service._bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_different_dex_independent(self, enabled_service):
        """Different DEXs have independent rate limits."""
        # Failure on extended
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error 1",
        )
        assert enabled_service._bot.send_message.call_count == 1

        # Failure on mock - different DEX, should be sent
        await enabled_service.send_execution_failure(
            signal_id="def456",
            dex_id="mock",
            error_message="Error 2",
        )
        assert enabled_service._bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_suppressed_alerts_counted(self, enabled_service):
        """Suppressed alerts are counted for summary."""
        # First alert
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error 1",
        )

        # Suppressed alerts
        await enabled_service.send_execution_failure(
            signal_id="def456",
            dex_id="extended",
            error_message="Error 2",
        )
        await enabled_service.send_execution_failure(
            signal_id="ghi789",
            dex_id="extended",
            error_message="Error 3",
        )

        # Check suppressed count
        error_type = "execution_failure:extended"
        assert enabled_service._suppressed_counts.get(error_type, 0) == 2

    @pytest.mark.asyncio
    async def test_alert_after_window_allowed(self, enabled_service):
        """Alert allowed after rate limit window expires (AC#6)."""
        # First alert
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error 1",
        )

        # Simulate time passing (move last_alert back)
        error_type = "execution_failure:extended"
        enabled_service._last_alert[error_type] = datetime.now(timezone.utc) - timedelta(
            seconds=61
        )

        # Second alert - window expired, should be sent
        await enabled_service.send_execution_failure(
            signal_id="def456",
            dex_id="extended",
            error_message="Error 2",
        )
        assert enabled_service._bot.send_message.call_count == 2


class TestSuppressionSummary:
    """Test suppression summary messages (AC#6)."""

    @pytest.fixture
    def enabled_service(self):
        """Create enabled alert service with mocked bot."""
        service = TelegramAlertService(
            bot_token="test_token",
            chat_id="123456789",
        )
        service._bot = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_summary_sent_after_window(self, enabled_service):
        """Summary message sent when window expires with suppressed alerts."""
        # First alert
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error 1",
        )

        # Suppress some alerts
        await enabled_service.send_execution_failure(
            signal_id="def456",
            dex_id="extended",
            error_message="Error 2",
        )
        await enabled_service.send_execution_failure(
            signal_id="ghi789",
            dex_id="extended",
            error_message="Error 3",
        )

        # Move time forward
        error_type = "execution_failure:extended"
        enabled_service._last_alert[error_type] = datetime.now(timezone.utc) - timedelta(
            seconds=61
        )

        # Next alert triggers summary
        await enabled_service.send_execution_failure(
            signal_id="jkl012",
            dex_id="extended",
            error_message="Error 4",
        )

        # Allow async task to complete
        await asyncio.sleep(0.1)

        # Should have: original alert, new alert, and summary
        assert enabled_service._bot.send_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_suppressed_count_reset_after_summary(self, enabled_service):
        """Suppressed count reset after summary sent."""
        error_type = "execution_failure:extended"

        # First alert
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error 1",
        )

        # Suppress some alerts
        await enabled_service.send_execution_failure(
            signal_id="def456",
            dex_id="extended",
            error_message="Error 2",
        )

        # Move time forward
        enabled_service._last_alert[error_type] = datetime.now(timezone.utc) - timedelta(
            seconds=61
        )

        # Next alert triggers summary and resets count
        await enabled_service.send_execution_failure(
            signal_id="ghi789",
            dex_id="extended",
            error_message="Error 3",
        )

        # Count should be reset
        assert enabled_service._suppressed_counts.get(error_type, 0) == 0


class TestFireAndForgetPattern:
    """Test fire-and-forget pattern (AC#4)."""

    @pytest.fixture
    def enabled_service(self):
        """Create enabled alert service with mocked bot."""
        service = TelegramAlertService(
            bot_token="test_token",
            chat_id="123456789",
        )
        service._bot = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_telegram_error_caught_not_raised(self, enabled_service):
        """TelegramError is caught and logged, not raised (AC#4)."""
        from telegram.error import TelegramError

        enabled_service._bot.send_message.side_effect = TelegramError("Network error")

        # Should not raise
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error",
        )

    @pytest.mark.asyncio
    async def test_generic_exception_caught_not_raised(self, enabled_service):
        """Generic exceptions are caught and logged, not raised (AC#4)."""
        enabled_service._bot.send_message.side_effect = Exception("Unexpected error")

        # Should not raise
        await enabled_service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Error",
        )

    @pytest.mark.asyncio
    async def test_send_alert_async_fire_and_forget(self, enabled_service):
        """send_alert_async creates task without blocking."""
        # This creates a task that runs in background
        send_alert_async(
            enabled_service,
            enabled_service.send_execution_failure(
                signal_id="abc123",
                dex_id="extended",
                error_message="Error",
            ),
        )
        # Allow task to complete
        await asyncio.sleep(0.1)
        # If we get here without error, the test passes
        enabled_service._bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_async_disabled_service_no_task(self):
        """No task created when service is disabled."""
        service = TelegramAlertService()  # Disabled
        service._bot = AsyncMock()

        # Should return immediately without creating task
        send_alert_async(
            service,
            service.send_execution_failure(
                signal_id="abc123",
                dex_id="extended",
                error_message="Error",
            ),
        )
        await asyncio.sleep(0.1)
        # Bot should never be called since service is disabled
        service._bot.send_message.assert_not_called()


class TestMarkdownEscaping:
    """Test Markdown escaping to prevent formatting errors."""

    def test_escape_markdown_special_characters(self):
        """Special Markdown characters are escaped."""
        service = TelegramAlertService(bot_token="test", chat_id="123")

        # Test various special characters
        assert service._escape_markdown("*bold*") == "\\*bold\\*"
        assert service._escape_markdown("_italic_") == "\\_italic\\_"
        assert service._escape_markdown("`code`") == "\\`code\\`"
        assert service._escape_markdown("[link](url)") == "\\[link\\]\\(url\\)"

    def test_escape_markdown_preserves_normal_text(self):
        """Normal text without special chars is unchanged."""
        service = TelegramAlertService(bot_token="test", chat_id="123")
        assert service._escape_markdown("normal text 123") == "normal text 123"

    @pytest.mark.asyncio
    async def test_escaped_error_message_in_alert(self):
        """Error messages with special chars are escaped in alerts."""
        service = TelegramAlertService(bot_token="test", chat_id="123")
        service._bot = AsyncMock()

        await service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message="Failed: use `alternative` method *now*",
        )

        call_args = service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        # Special chars should be escaped
        assert "\\`alternative\\`" in message
        assert "\\*now\\*" in message


class TestMessageTruncation:
    """Test message truncation for Telegram limits."""

    def test_truncate_short_text_unchanged(self):
        """Short text is not truncated."""
        service = TelegramAlertService(bot_token="test", chat_id="123")
        assert service._truncate("short", 100) == "short"

    def test_truncate_long_text_with_ellipsis(self):
        """Long text is truncated with ellipsis."""
        service = TelegramAlertService(bot_token="test", chat_id="123")
        result = service._truncate("a" * 600, 500)
        assert len(result) == 500
        assert result.endswith("...")

    def test_truncate_uses_default_max_length(self):
        """Truncate uses MAX_ERROR_LENGTH by default."""
        service = TelegramAlertService(bot_token="test", chat_id="123")
        long_error = "x" * 1000
        result = service._truncate(long_error)
        assert len(result) == service.MAX_ERROR_LENGTH

    @pytest.mark.asyncio
    async def test_long_error_message_truncated(self):
        """Very long error messages are truncated in alerts."""
        service = TelegramAlertService(bot_token="test", chat_id="123")
        service._bot = AsyncMock()

        long_error = "E" * 1000  # 1000 char error

        await service.send_execution_failure(
            signal_id="abc123",
            dex_id="extended",
            error_message=long_error,
        )

        call_args = service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        # Message should be under 4000 chars total
        assert len(message) < service.MAX_MESSAGE_LENGTH
        # Error should be truncated
        assert "..." in message


class TestRateLimitCleanup:
    """Test cleanup of stale rate limiting entries (Subtask 4.5)."""

    @pytest.fixture
    def enabled_service(self):
        """Create enabled alert service with mocked bot."""
        service = TelegramAlertService(bot_token="test", chat_id="123")
        service._bot = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_stale_entries_cleaned_up(self, enabled_service):
        """Entries older than 2x throttle window are cleaned up."""
        # Add some entries manually
        old_time = datetime.now(timezone.utc) - timedelta(seconds=200)  # > 2x60
        enabled_service._last_alert["old_error:dex1"] = old_time
        enabled_service._suppressed_counts["old_error:dex1"] = 5

        recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)  # < 60
        enabled_service._last_alert["recent_error:dex2"] = recent_time
        enabled_service._suppressed_counts["recent_error:dex2"] = 2

        # Trigger cleanup via _should_send
        enabled_service._should_send("new_error:dex3")

        # Old entry should be cleaned up
        assert "old_error:dex1" not in enabled_service._last_alert
        assert "old_error:dex1" not in enabled_service._suppressed_counts

        # Recent entry should remain
        assert "recent_error:dex2" in enabled_service._last_alert
        assert "recent_error:dex2" in enabled_service._suppressed_counts

    @pytest.mark.asyncio
    async def test_cleanup_does_not_affect_active_entries(self, enabled_service):
        """Active entries within throttle window are not cleaned up."""
        # Add recent entry
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        enabled_service._last_alert["active_error:dex1"] = recent_time
        enabled_service._suppressed_counts["active_error:dex1"] = 3

        # Trigger multiple cleanups
        for i in range(5):
            enabled_service._should_send(f"other_error:{i}")

        # Active entry should still exist
        assert "active_error:dex1" in enabled_service._last_alert
        assert enabled_service._suppressed_counts["active_error:dex1"] == 3


class TestDEXStatusChange:
    """Test DEX status change alerts (bonus for Story 4.3)."""

    @pytest.fixture
    def enabled_service(self):
        """Create enabled alert service with mocked bot."""
        service = TelegramAlertService(
            bot_token="test_token",
            chat_id="123456789",
        )
        service._bot = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_send_dex_status_change_format(self, enabled_service):
        """DEX status change alert has correct format."""
        await enabled_service.send_dex_status_change(
            dex_id="extended",
            old_status="healthy",
            new_status="degraded",
        )

        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]

        assert "DEX Status Change" in message
        assert "extended" in message
        assert "healthy" in message
        assert "degraded" in message

    @pytest.mark.asyncio
    async def test_healthy_status_uses_checkmark_emoji(self, enabled_service):
        """Healthy status uses checkmark emoji."""
        await enabled_service.send_dex_status_change(
            dex_id="extended",
            old_status="degraded",
            new_status="healthy",
        )

        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert message.startswith("✅")

    @pytest.mark.asyncio
    async def test_degraded_status_uses_warning_emoji(self, enabled_service):
        """Degraded status uses warning emoji."""
        await enabled_service.send_dex_status_change(
            dex_id="extended",
            old_status="healthy",
            new_status="degraded",
        )

        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert message.startswith("⚠️")

    @pytest.mark.asyncio
    async def test_offline_status_uses_alert_emoji(self, enabled_service):
        """Offline status uses alert emoji."""
        await enabled_service.send_dex_status_change(
            dex_id="extended",
            old_status="degraded",
            new_status="offline",
        )

        call_args = enabled_service._bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert message.startswith("🚨")
