# Story 4.2: Telegram Alert Service

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a **user**,
I want **to receive Telegram alerts when executions fail**,
So that **I'm immediately aware of issues even when not watching the dashboard**.

## Acceptance Criteria

1. **Alert Service Exists**: Given the alert service, when I check `services/alert.py`, then a `TelegramAlertService` class exists using `python-telegram-bot` library

2. **Telegram Configuration**: Given Telegram configuration in environment, when set, then the following are required: `TELEGRAM_BOT_TOKEN` (Bot API token), `TELEGRAM_CHAT_ID` (Target chat/channel ID)

3. **Execution Failure Alert**: Given an execution failure occurs, when the alert service is triggered, then a Telegram message is sent with: Alert type (e.g., "Execution Failed"), Signal ID, DEX name, Error message, Timestamp

4. **Fire-and-Forget Pattern**: Given alert sending, when implemented, then it uses `asyncio.create_task()` for fire-and-forget, alert failures don't block order processing, and alert failures are logged but don't raise exceptions

5. **Partial Fill Alert**: Given a partial fill occurs, when detected, then an alert is sent with: "Partial Fill", Symbol, filled amount, remaining amount, DEX name

6. **Alert Rate Limiting**: Given many alerts would be sent rapidly, when alert rate limiting is active, then alerts are throttled to max 1 per minute per error type, and a summary is sent: "X additional errors suppressed"

7. **Graceful Degradation**: Given Telegram credentials are not configured, when the application starts, then a warning is logged: "Telegram alerts disabled - credentials not configured", and the application continues without alerting capability

## Tasks / Subtasks

- [x] Task 1: Create TelegramAlertService class (AC: #1, #4, #7)
  - [x] Subtask 1.1: Define `TelegramAlertService` in `src/kitkat/services/alert.py`
  - [x] Subtask 1.2: Constructor accepts bot_token and chat_id (optional)
  - [x] Subtask 1.3: Detect unconfigured state and log warning
  - [x] Subtask 1.4: Use `python-telegram-bot` library for sending
  - [x] Subtask 1.5: Implement fire-and-forget `send_alert()` method
  - [x] Subtask 1.6: All errors logged but never raised (graceful degradation)

- [x] Task 2: Implement execution failure alerts (AC: #3)
  - [x] Subtask 2.1: Create `send_execution_failure()` method
  - [x] Subtask 2.2: Format message with alert type, signal_id, dex_id, error, timestamp
  - [x] Subtask 2.3: Use emoji prefix for visibility
  - [x] Subtask 2.4: Include actionable context in message
  - [x] Subtask 2.5: Bind structlog context for tracing

- [x] Task 3: Implement partial fill alerts (AC: #5)
  - [x] Subtask 3.1: Create `send_partial_fill()` method
  - [x] Subtask 3.2: Accept symbol, filled_size, remaining_size, dex_id
  - [x] Subtask 3.3: Format message with warning emoji
  - [x] Subtask 3.4: Calculate fill percentage for context

- [x] Task 4: Implement alert rate limiting (AC: #6)
  - [x] Subtask 4.1: Track last alert timestamp per error type
  - [x] Subtask 4.2: Throttle to max 1 per minute per error type
  - [x] Subtask 4.3: Count suppressed alerts per error type
  - [x] Subtask 4.4: Send summary message after throttle window
  - [x] Subtask 4.5: Clean up old suppression counts

- [x] Task 5: Integrate with SignalProcessor (AC: #3, #4, #5)
  - [x] Subtask 5.1: Inject TelegramAlertService into SignalProcessor
  - [x] Subtask 5.2: Call `send_execution_failure()` on DEX errors
  - [x] Subtask 5.3: Call `send_partial_fill()` on partial fills
  - [x] Subtask 5.4: Use asyncio.create_task() for fire-and-forget
  - [x] Subtask 5.5: Ensure alert failures don't block execution flow

- [x] Task 6: Add to dependency injection (AC: #1, #7)
  - [x] Subtask 6.1: Create `get_alert_service()` in deps.py
  - [x] Subtask 6.2: Singleton pattern with thread-safe initialization
  - [x] Subtask 6.3: Read credentials from settings
  - [x] Subtask 6.4: Handle missing credentials gracefully

- [x] Task 7: Create comprehensive test suite (AC: #1-7)
  - [x] Subtask 7.1: Create `tests/services/test_alert_service.py`
  - [x] Subtask 7.2: Test alert formatting for all message types
  - [x] Subtask 7.3: Test rate limiting logic
  - [x] Subtask 7.4: Test suppression counting and summary
  - [x] Subtask 7.5: Test graceful degradation when unconfigured
  - [x] Subtask 7.6: Test fire-and-forget pattern
  - [x] Subtask 7.7: Test integration with SignalProcessor
  - [x] Subtask 7.8: Mock python-telegram-bot to avoid real API calls

## Dev Notes

### Architecture Compliance

**Service Layer** (`src/kitkat/services/alert.py`):
- TelegramAlertService handles all Telegram communication
- Fire-and-forget pattern using asyncio.create_task()
- Rate limiting with 1-minute throttle per error type
- Graceful degradation when credentials missing

**Dependencies** (`src/kitkat/api/deps.py`):
- Singleton TelegramAlertService instance
- Thread-safe initialization with double-checked locking
- Reads credentials from settings

**Integration** (`src/kitkat/services/signal_processor.py`):
- SignalProcessor receives AlertService via constructor
- Triggers alerts on execution failures and partial fills
- Never blocks on alert delivery

### Project Structure Notes

**Files to create:**
- `src/kitkat/services/alert.py` - TelegramAlertService class (~200 lines)
- `tests/services/test_alert_service.py` - Service tests (~400 lines)

**Files to modify:**
- `src/kitkat/api/deps.py` - Add get_alert_service singleton (~40 lines)
- `src/kitkat/services/signal_processor.py` - Integrate alert calls (~30 lines)
- Note: main.py modification NOT required - alert service is injected via deps.py

**Architecture alignment:**
```
src/kitkat/
├── services/
│   ├── alert.py            # NEW - TelegramAlertService
│   └── signal_processor.py # MODIFY - Add alert integration
├── api/
│   └── deps.py             # MODIFY - Add get_alert_service
# Note: main.py NOT modified - alert service injected via deps.py

tests/
└── services/
    └── test_alert_service.py  # NEW - Alert service tests
```

### Technical Requirements

**TelegramAlertService Class:**
```python
"""Telegram alert service for real-time notifications (Story 4.2).

Provides fire-and-forget alerting for execution failures and partial fills.
Uses python-telegram-bot library for Telegram Bot API integration.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog
from telegram import Bot
from telegram.error import TelegramError

logger = structlog.get_logger()


class TelegramAlertService:
    """Fire-and-forget Telegram alert service.

    Story 4.2: Telegram Alert Service
    - AC#1: Uses python-telegram-bot library
    - AC#4: Fire-and-forget via asyncio.create_task()
    - AC#6: Rate limiting (1 per minute per error type)
    - AC#7: Graceful degradation when unconfigured
    """

    # Rate limiting: 1 alert per minute per error type
    THROTTLE_SECONDS = 60

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
        message = (
            f"🚨 *Execution Failed*\n\n"
            f"📍 DEX: `{dex_id}`\n"
            f"🔑 Signal: `{signal_id[:8]}...`\n"
            f"❌ Error: {error_message}\n"
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

        message = (
            f"⚠️ *Partial Fill*\n\n"
            f"📍 DEX: `{dex_id}`\n"
            f"💱 Symbol: `{symbol}`\n"
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
        emoji = "✅" if new_status == "healthy" else "⚠️" if new_status == "degraded" else "🚨"

        message = (
            f"{emoji} *DEX Status Change*\n\n"
            f"📍 DEX: `{dex_id}`\n"
            f"🔄 {old_status} → {new_status}\n"
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
        except Exception as e:
            # Catch all exceptions to ensure we never crash the main flow
            self._log.error(
                "Unexpected error sending Telegram alert",
                error=str(e),
                error_type=type(e).__name__,
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
```

**Dependency Injection (deps.py additions):**
```python
import threading
from kitkat.services.alert import TelegramAlertService
from kitkat.config import get_settings

_alert_service: TelegramAlertService | None = None
_alert_service_lock = threading.Lock()

def get_alert_service() -> TelegramAlertService:
    """Get singleton TelegramAlertService instance.

    Thread-safe initialization using double-checked locking.
    Reads credentials from settings.

    Returns:
        TelegramAlertService: Alert service instance (may be disabled)
    """
    global _alert_service

    if _alert_service is None:
        with _alert_service_lock:
            if _alert_service is None:
                settings = get_settings()
                _alert_service = TelegramAlertService(
                    bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id,
                )

    return _alert_service
```

**SignalProcessor Integration:**
```python
# In src/kitkat/services/signal_processor.py

from kitkat.services.alert import TelegramAlertService, send_alert_async

class SignalProcessor:
    def __init__(
        self,
        adapters: list[DEXAdapter],
        deduplicator: SignalDeduplicator,
        rate_limiter: RateLimiter,
        alert_service: TelegramAlertService,  # NEW
        db_session_factory,
    ):
        # ... existing initialization ...
        self._alert_service = alert_service

    async def _execute_on_dex(self, adapter: DEXAdapter, signal: Signal) -> ExecutionResult:
        """Execute signal on a single DEX."""
        try:
            result = await adapter.execute_order(
                symbol=signal.symbol,
                side=signal.side,
                size=signal.size,
            )

            # Check for partial fill (AC#5)
            if result.status == "partial":
                send_alert_async(
                    self._alert_service,
                    self._alert_service.send_partial_fill(
                        symbol=signal.symbol,
                        filled_size=str(result.filled_size),
                        remaining_size=str(result.remaining_size),
                        dex_id=adapter.dex_id,
                    )
                )

            return result

        except DEXError as e:
            # Send execution failure alert (AC#3)
            send_alert_async(
                self._alert_service,
                self._alert_service.send_execution_failure(
                    signal_id=signal.signal_id,
                    dex_id=adapter.dex_id,
                    error_message=str(e),
                )
            )
            raise
```

### Previous Story Intelligence

**From Story 4.1 (Health Service & DEX Status):**
- Singleton pattern with thread-safe double-checked locking established
- Dependency injection via Depends() mechanism in place
- Async patterns with asyncio.gather() and proper error handling
- Structlog for contextual logging (bind service name)
- Pydantic models for responses
- App startup sets up services in main.py lifespan

**From Story 3.3 (Dry-Run Execution Output):**
- Test mode awareness in services
- Response formatting patterns
- Feature flag checking pattern

**From Story 2.9 (Signal Processor & Fan-Out):**
- SignalProcessor handles execution across adapters
- Parallel execution with asyncio.gather(return_exceptions=True)
- Error collection and per-DEX result tracking
- Existing injection point for alert service

**From Story 2.8 (Execution Logging & Partial Fills):**
- Partial fill detection already implemented
- FR15: Alert on partial fill scenarios referenced but not implemented
- Result includes filled_size and remaining_size fields

**Key Patterns Observed:**
- Fire-and-forget with asyncio.create_task() for non-blocking operations
- Singleton services with thread-safe initialization
- Graceful degradation (disabled state when unconfigured)
- Structlog binding for service identification
- Never raise exceptions in fire-and-forget handlers

### Git Intelligence

**Recent Commits:**
- Story 4.1: Health Service complete with parallel health checks
- Story 3.3: Dry-run execution output with comprehensive test coverage
- Story 3.1: Test mode feature flag integration
- Story 2.9: Signal processor fan-out pattern

**Common Implementation Approach:**
1. Create service class with singleton pattern
2. Add to dependency injection (deps.py)
3. Inject into consumers (SignalProcessor)
4. Fire-and-forget via asyncio.create_task()
5. Comprehensive test coverage with mocks

### Configuration Requirements

**Environment Variables (already defined in config.py):**
```python
# Telegram
telegram_bot_token: str = ""  # Already exists
telegram_chat_id: str = ""    # Already exists
```

**No new configuration needed** - the settings already include telegram_bot_token and telegram_chat_id with empty string defaults, enabling graceful degradation when not configured.

### Library-Specific Notes

**python-telegram-bot Usage:**
```python
from telegram import Bot
from telegram.error import TelegramError

# Async sending
bot = Bot(token=bot_token)
await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

# Error handling
try:
    await bot.send_message(...)
except TelegramError as e:
    logger.error("Telegram send failed", error=str(e))
```

**Important:** The library is already in dependencies (from architecture.md), so no new installation needed.

### Testing Strategy

**Unit tests (tests/services/test_alert_service.py):**
1. Test TelegramAlertService initialization with credentials
2. Test initialization without credentials (disabled state)
3. Test execution failure message formatting
4. Test partial fill message formatting
5. Test DEX status change message formatting
6. Test rate limiting (throttle after first alert)
7. Test suppression counting
8. Test suppression summary generation
9. Test graceful error handling (TelegramError caught)
10. Test fire-and-forget pattern (no blocking)
11. Test enabled/disabled property

**Integration tests:**
1. Test SignalProcessor calls alert service on failure
2. Test SignalProcessor calls alert service on partial fill
3. Test alert service doesn't block execution flow
4. Test async tasks complete without exceptions

**Mock Strategy:**
- Mock `telegram.Bot` to avoid real API calls
- Mock `telegram.Bot.send_message` to verify arguments
- Use pytest-mock for patching

### Performance Considerations

- Fire-and-forget pattern ensures zero impact on execution latency
- Rate limiting prevents Telegram API abuse (1 alert/minute/type)
- In-memory rate limiting state (no database overhead)
- Suppression summary reduces message count
- Alert failures logged but never block main flow

### Edge Cases

1. **Empty credentials**: Service disabled, warning logged, no errors
2. **Invalid bot token**: TelegramError caught, logged, not raised
3. **Invalid chat ID**: TelegramError caught, logged, not raised
4. **Rate limit hit**: Alert suppressed, count tracked, summary queued
5. **Multiple error types**: Each type has independent rate limit
6. **Very long error messages**: Truncate or handle Telegram limits (4096 chars)
7. **Network timeout**: TelegramError caught, logged, not raised
8. **Bot blocked by user**: TelegramError caught, logged, not raised
9. **Markdown formatting errors**: Use safe formatting or escape special chars

### References

- [Source: _bmad-output/planning-artifacts/architecture.md - Alert Service specification]
- [Source: _bmad-output/planning-artifacts/epics.md - Story 4.2: Telegram Alert Service (AC#1-7)]
- [Source: _bmad-output/planning-artifacts/prd.md - FR27: Send Telegram error alerts on execution failure]
- [Source: _bmad-output/planning-artifacts/prd.md - FR15: Alert on partial fill scenarios]
- [Source: _bmad-output/planning-artifacts/prd.md - NFR16: Error alerting latency < 30 seconds]
- [Source: Story 4.1 - Singleton pattern and dependency injection]
- [Source: Story 2.9 - SignalProcessor integration point]
- [Source: Story 2.8 - Partial fill detection]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Implementation Readiness

**Prerequisites met:**
- python-telegram-bot in dependencies (from Story 1.1)
- Settings include telegram_bot_token and telegram_chat_id (already defined)
- SignalProcessor exists with execution flow (Story 2.9)
- Partial fill detection implemented (Story 2.8)
- Singleton pattern established (Story 4.1)
- Structlog logging in place (All stories)

**Functional Requirements Covered:**
- FR27: System can send error alerts to Telegram on execution failure
- FR15: System can alert user on partial fill scenarios

**Non-Functional Requirements Covered:**
- NFR16: Error alerting latency < 30 seconds from failure to Telegram notification

**Scope Assessment:**
- TelegramAlertService class: ~200 lines
- Dependency injection update: ~40 lines
- SignalProcessor integration: ~30 lines
- Main.py modifications: ~10 lines
- Tests: ~400 lines
- **Total: ~680 lines across 5 files**

**Dependencies:**
- Story 4.1 complete (singleton pattern, deps.py structure)
- Story 2.9 complete (SignalProcessor exists)
- Story 2.8 complete (partial fill detection)

**Related Stories:**
- Story 4.3 (Auto-Recovery After Outage): Will use alert service for recovery notifications
- Story 4.4 (Error Logging): Will work alongside alerts for comprehensive error handling
- Story 5.8 (Telegram Configuration): User-configurable chat_id (future enhancement)

### Debug Log References

N/A

### Completion Notes List

1. Created `src/kitkat/services/alert.py` (~290 lines) with TelegramAlertService class
2. Created `tests/services/test_alert_service.py` (~560 lines) with 31 unit tests - all passing
3. Modified `src/kitkat/api/deps.py` - added get_alert_service() singleton with thread-safe initialization
4. Modified `src/kitkat/services/signal_processor.py` - integrated alert service with fire-and-forget pattern
5. Added 4 integration tests in `tests/services/test_signal_processor.py` - 19 tests total, all passing
6. Fixed pre-existing issues in test_signal_processor.py:
   - Added missing `is_connected` property to MockDEXAdapter
   - Fixed incorrect test expectation in `test_decimal_amounts_preserved`
7. Total test results: 263 tests passing, 3 pre-existing failures unrelated to this story (test_health.py tests for `/health` endpoint vs `/api/health/status`)

### Code Review Fixes (2026-02-01)

Adversarial review found and fixed 5 issues:

**HIGH Priority Fixed:**
1. **Subtask 4.5 cleanup mechanism**: Added `_cleanup_stale_entries()` to prevent memory leaks from unbounded `_last_alert` and `_suppressed_counts` dicts
2. **Story documentation**: Corrected File List - main.py was NOT modified (alert service injected via deps.py)

**MEDIUM Priority Fixed:**
3. **Message truncation**: Added `_truncate()` method and `MAX_MESSAGE_LENGTH`/`MAX_ERROR_LENGTH` constants to handle Telegram's 4096 char limit
4. **Markdown escaping**: Added `_escape_markdown()` method to escape special characters in user-provided content (error messages, symbols, DEX IDs)
5. **Missing partial fill test**: Added `test_partial_fill_alert_sent` and `test_no_partial_fill_alert_without_signal` integration tests

**New Tests Added:**
- `TestMarkdownEscaping` (3 tests): escape special chars, preserve normal text, verify escaping in alerts
- `TestMessageTruncation` (4 tests): truncation with ellipsis, default max length, long error handling
- `TestRateLimitCleanup` (2 tests): stale entry cleanup, active entry preservation
- `test_partial_fill_alert_sent`: verify partial fill alerts are sent
- `test_no_partial_fill_alert_without_signal`: verify no alert without signal context

**Final Test Results:** 61 tests passing (42 alert service + 21 signal processor - 2 overlap)

### File List

**Created:**
- `src/kitkat/services/alert.py` - TelegramAlertService class with rate limiting, fire-and-forget, escaping, truncation
- `tests/services/test_alert_service.py` - Comprehensive test suite (42 tests after review fixes)

**Modified:**
- `src/kitkat/api/deps.py` - Added get_alert_service() dependency injection
- `src/kitkat/services/signal_processor.py` - Integrated alert calls in _process_result()
- `tests/services/test_signal_processor.py` - Added 6 alert integration tests (including partial fill), fixed pre-existing issues

**NOT Modified (corrected from original plan):**
- `src/kitkat/main.py` - Alert service injected via deps.py, no main.py changes needed

