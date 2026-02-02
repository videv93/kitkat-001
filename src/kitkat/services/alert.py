"""Telegram alert service for real-time notifications (Story 4.2).

Provides fire-and-forget alerting for execution failures and partial fills.
Uses python-telegram-bot library for Telegram Bot API integration.

Key responsibilities:
- Send execution failure alerts with signal/DEX context
- Send partial fill alerts with fill amounts
- Rate limit alerts per error type (1 per minute)
- Graceful degradation when credentials missing
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog
from telegram import Bot
from telegram.error import TelegramError

from kitkat.logging import ErrorType
from kitkat.services.error_logger import get_error_logger

logger = structlog.get_logger()


class TelegramAlertService:
    """Fire-and-forget Telegram alert service.

    Story 4.2: Telegram Alert Service
    - AC#1: Uses python-telegram-bot library
    - AC#4: Fire-and-forget via asyncio.create_task()
    - AC#6: Rate limiting (1 per minute per error type)
    - AC#7: Graceful degradation when unconfigured
    """

    # Rate limiting: 1 alert per minute per error type (AC#6)
    THROTTLE_SECONDS = 60

    # Telegram message limit is 4096 chars; use 4000 to leave room for formatting
    MAX_MESSAGE_LENGTH = 4000

    # Max length for error messages to prevent oversized alerts
    MAX_ERROR_LENGTH = 500

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        """Initialize alert service.

        Args:
            bot_token: Telegram Bot API token
            chat_id: Target chat/channel ID
        """
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._bot: Optional[Bot] = None
        self._enabled = bool(bot_token and chat_id)
        self._log = logger.bind(service="alert")

        # Rate limiting state (AC#6)
        self._last_alert: dict[str, datetime] = {}  # {error_type: last_sent_time}
        self._suppressed_counts: dict[str, int] = {}  # {error_type: count}

        if not self._enabled:
            self._log.warning(
                "Telegram alerts disabled - credentials not configured",
                has_token=bool(bot_token),
                has_chat_id=bool(chat_id),
            )
        else:
            self._bot = Bot(token=bot_token)
            self._log.info("Telegram alerts enabled", chat_id=chat_id)

    @property
    def enabled(self) -> bool:
        """Check if alerts are enabled."""
        return self._enabled

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape Markdown special characters to prevent formatting errors.

        Args:
            text: Text that may contain Markdown special characters

        Returns:
            Text with special characters escaped
        """
        # Characters that need escaping in Telegram Markdown
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        result = text
        for char in special_chars:
            result = result.replace(char, f'\\{char}')
        return result

    @classmethod
    def _truncate(cls, text: str, max_length: int | None = None) -> str:
        """Truncate text to maximum length with ellipsis.

        Args:
            text: Text to truncate
            max_length: Maximum length (defaults to MAX_ERROR_LENGTH)

        Returns:
            Truncated text with '...' suffix if truncated
        """
        if max_length is None:
            max_length = cls.MAX_ERROR_LENGTH
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    async def send_execution_failure(
        self,
        signal_id: str,
        dex_id: str,
        error_message: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Send alert for execution failure (AC#3).

        Args:
            signal_id: Signal identifier
            dex_id: DEX identifier
            error_message: Error description
            timestamp: Failure timestamp (defaults to now)
        """
        if not self._enabled:
            return

        error_type = f"execution_failure:{dex_id}"
        if not self._should_send(error_type):
            return

        ts = timestamp or datetime.now(timezone.utc)
        # Escape and truncate user-provided content to prevent Markdown errors and oversized messages
        safe_error = self._escape_markdown(self._truncate(error_message))
        safe_dex = self._escape_markdown(dex_id)
        message = (
            f"🚨 *Execution Failed*\n\n"
            f"📍 DEX: `{safe_dex}`\n"
            f"🔑 Signal: `{signal_id[:8]}...`\n"
            f"❌ Error: {safe_error}\n"
            f"🕐 Time: {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        await self._send_message(message, error_type)

    async def send_partial_fill(
        self,
        symbol: str,
        filled_size: str,
        remaining_size: str,
        dex_id: str,
    ) -> None:
        """Send alert for partial fill (AC#5).

        Args:
            symbol: Trading pair symbol
            filled_size: Amount filled
            remaining_size: Amount remaining
            dex_id: DEX identifier
        """
        if not self._enabled:
            return

        error_type = f"partial_fill:{dex_id}"
        if not self._should_send(error_type):
            return

        # Calculate fill percentage
        try:
            filled = float(filled_size)
            remaining = float(remaining_size)
            total = filled + remaining
            percentage = (filled / total * 100) if total > 0 else 0
        except (ValueError, ZeroDivisionError):
            percentage = 0

        # Escape user-provided content to prevent Markdown errors
        safe_dex = self._escape_markdown(dex_id)
        safe_symbol = self._escape_markdown(symbol)
        message = (
            f"⚠️ *Partial Fill*\n\n"
            f"📍 DEX: `{safe_dex}`\n"
            f"💱 Symbol: `{safe_symbol}`\n"
            f"✅ Filled: {filled_size} ({percentage:.1f}%)\n"
            f"⏳ Remaining: {remaining_size}\n"
            f"🕐 Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        await self._send_message(message, error_type)

    async def send_dex_status_change(
        self,
        dex_id: str,
        old_status: str,
        new_status: str,
    ) -> None:
        """Send alert for DEX status change (used by HealthService in Story 4.3).

        Args:
            dex_id: DEX identifier
            old_status: Previous status
            new_status: New status
        """
        if not self._enabled:
            return

        error_type = f"dex_status:{dex_id}"
        if not self._should_send(error_type):
            return

        # Choose emoji based on new status
        if new_status == "healthy":
            emoji = "✅"
        elif new_status == "degraded":
            emoji = "⚠️"
        else:
            emoji = "🚨"

        # Escape user-provided content to prevent Markdown errors
        safe_dex = self._escape_markdown(dex_id)
        safe_old = self._escape_markdown(old_status)
        safe_new = self._escape_markdown(new_status)
        message = (
            f"{emoji} *DEX Status Change*\n\n"
            f"📍 DEX: `{safe_dex}`\n"
            f"🔄 {safe_old} → {safe_new}\n"
            f"🕐 Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        await self._send_message(message, error_type)

    def _should_send(self, error_type: str) -> bool:
        """Check if alert should be sent based on rate limiting (AC#6).

        Args:
            error_type: Category of error for rate limiting

        Returns:
            bool: True if alert should be sent
        """
        now = datetime.now(timezone.utc)
        last_sent = self._last_alert.get(error_type)

        # Periodic cleanup of stale entries (Subtask 4.5)
        self._cleanup_stale_entries(now)

        if last_sent is None:
            return True

        elapsed = (now - last_sent).total_seconds()

        if elapsed >= self.THROTTLE_SECONDS:
            # Check if we have suppressed alerts to report
            suppressed = self._suppressed_counts.get(error_type, 0)
            if suppressed > 0:
                asyncio.create_task(self._send_suppression_summary(error_type, suppressed))
                self._suppressed_counts[error_type] = 0
            return True

        # Suppress this alert
        self._suppressed_counts[error_type] = self._suppressed_counts.get(error_type, 0) + 1
        self._log.debug(
            "Alert suppressed (rate limited)",
            error_type=error_type,
            suppressed_count=self._suppressed_counts[error_type],
        )
        return False

    def _cleanup_stale_entries(self, now: datetime) -> None:
        """Remove stale entries from rate limiting state (Subtask 4.5).

        Entries older than 2x THROTTLE_SECONDS are removed to prevent
        unbounded memory growth in long-running processes.

        Args:
            now: Current timestamp for comparison
        """
        # Use 2x throttle window to avoid cleaning up entries that might still be relevant
        cleanup_threshold = self.THROTTLE_SECONDS * 2

        # Find stale keys
        stale_keys = [
            key for key, last_time in self._last_alert.items()
            if (now - last_time).total_seconds() > cleanup_threshold
        ]

        # Remove stale entries
        for key in stale_keys:
            del self._last_alert[key]
            self._suppressed_counts.pop(key, None)
            self._log.debug("Cleaned up stale rate limit entry", error_type=key)

    async def _send_suppression_summary(self, error_type: str, count: int) -> None:
        """Send summary of suppressed alerts.

        Args:
            error_type: Category of error
            count: Number of suppressed alerts
        """
        message = (
            f"📊 *Alert Summary*\n\n"
            f"Type: `{error_type}`\n"
            f"Suppressed: {count} additional alerts\n"
            f"🕐 Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        # Direct send without rate limiting
        await self._send_message_direct(message)

    async def _send_message(self, message: str, error_type: str) -> None:
        """Send message to Telegram with error handling (AC#4).

        Args:
            message: Formatted message text
            error_type: Error category for rate limit tracking
        """
        self._last_alert[error_type] = datetime.now(timezone.utc)
        await self._send_message_direct(message)

    async def _send_message_direct(self, message: str) -> None:
        """Send message directly to Telegram (no rate limiting).

        Errors are logged but never raised (AC#4, AC#7).

        Args:
            message: Formatted message text
        """
        if not self._bot or not self._chat_id:
            return

        try:
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=message,
                parse_mode="Markdown",
            )
            self._log.debug("Telegram alert sent", message_length=len(message))
        except TelegramError as e:
            # Log but don't raise - alerts are fire-and-forget (AC#4)
            self._log.error(
                "Failed to send Telegram alert",
                error=str(e),
                chat_id=self._chat_id,
            )
            # Story 4.4: Log alert send failure with context (AC#1)
            get_error_logger().log_system_error(
                error_type=ErrorType.ALERT_SEND_FAILED,
                error_message=f"Failed to send Telegram alert: {e}",
                component="telegram_alert",
                exception=e,
                context={"message_length": len(message)},
            )
        except Exception as e:
            # Catch all exceptions to ensure we never crash the main flow
            self._log.error(
                "Unexpected error sending Telegram alert",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Story 4.4: Log unexpected alert error (AC#1)
            get_error_logger().log_system_error(
                error_type=ErrorType.ALERT_SEND_FAILED,
                error_message=f"Unexpected error sending Telegram alert: {e}",
                component="telegram_alert",
                exception=e,
            )


def send_alert_async(alert_service: TelegramAlertService, coro) -> None:
    """Fire-and-forget wrapper for alert sending (AC#4).

    Creates a task that runs in the background without blocking.
    Errors are handled within the coroutine, not raised here.

    Args:
        alert_service: The alert service instance
        coro: Coroutine to execute (e.g., send_execution_failure())
    """
    if not alert_service.enabled:
        return

    asyncio.create_task(coro)
