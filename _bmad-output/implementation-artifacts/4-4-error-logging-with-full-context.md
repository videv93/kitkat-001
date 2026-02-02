# Story 4.4: Error Logging with Full Context

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a **developer/operator**,
I want **all errors logged with full context**,
So that **I can debug issues quickly**.

## Acceptance Criteria

1. **Structured Error Logging**: Given any error in the system, when it is logged, then structlog is used with bound context: signal_id (if applicable), dex_id (if applicable), user_id (if applicable), error_type (categorized error code), error_message (human-readable description), timestamp (ISO format)

2. **DEX API Error Context**: Given a DEX API error, when logged, then the log includes: full request details (method, URL, headers without secrets), response status code, response body (truncated if > 1KB), latency

3. **Webhook Validation Error Context**: Given a webhook validation error, when logged, then the log includes: raw payload (for debugging malformed JSON), validation error details, client IP (for abuse detection)

4. **Structured JSON Output**: Given structlog configuration, when the application starts, then JSON format is used for structured log output and logs are written to stdout (container-friendly)

5. **Secret Redaction**: Given sensitive data, when logging occurs, then secrets are redacted: API keys show as "***", tokens show as first 4 chars + "...", wallet addresses are NOT redacted (needed for debugging)

6. **Log Level Consistency**: Given log levels, when used consistently, then: DEBUG for development details/raw payloads, INFO for normal operations/successful executions, WARNING for recoverable issues/degraded states, ERROR for failures requiring attention

## Tasks / Subtasks

- [x] Task 1: Create centralized error logging utilities (AC: #1, #4, #5)
  - [x] Subtask 1.1: Create `src/kitkat/logging.py` with error logging utilities
  - [x] Subtask 1.2: Implement `LogContext` class for context binding
  - [x] Subtask 1.3: Implement `redact_secrets()` function for secret sanitization
  - [x] Subtask 1.4: Implement `truncate_body()` function for large payload handling
  - [x] Subtask 1.5: Configure structlog JSON processor for stdout output
  - [x] Subtask 1.6: Create error category constants (ERROR_TYPES enum or dict)

- [x] Task 2: Create error logging service (AC: #1, #2, #3)
  - [x] Subtask 2.1: Create `ErrorLogger` class in `src/kitkat/services/error_logger.py`
  - [x] Subtask 2.2: Implement `log_dex_error()` with full request/response context
  - [x] Subtask 2.3: Implement `log_webhook_error()` with payload and validation details
  - [x] Subtask 2.4: Implement `log_execution_error()` with signal and DEX context
  - [x] Subtask 2.5: Implement `log_system_error()` for general system errors
  - [x] Subtask 2.6: Bind context automatically (signal_id, dex_id, user_id)

- [x] Task 3: Integrate error logging throughout codebase (AC: #1, #2, #3, #6)
  - [x] Subtask 3.1: Integrate into `adapters/extended.py` for DEX API errors
  - [x] Subtask 3.2: Integrate into `adapters/mock.py` for test mode errors
  - [x] Subtask 3.3: Integrate into `api/webhook.py` for validation errors
  - [x] Subtask 3.4: Integrate into `services/signal_processor.py` for execution errors
  - [x] Subtask 3.5: Integrate into `services/health_monitor.py` for health check errors
  - [x] Subtask 3.6: Integrate into `services/alert.py` for alert sending errors

- [x] Task 4: Implement secret redaction (AC: #5)
  - [x] Subtask 4.1: Identify all secrets in settings (api keys, tokens, bot tokens)
  - [x] Subtask 4.2: Create redaction patterns for each secret type
  - [x] Subtask 4.3: Apply redaction in request logging (headers, URLs)
  - [x] Subtask 4.4: Apply redaction in response logging (body content)
  - [x] Subtask 4.5: Verify wallet addresses pass through unredacted
  - [x] Subtask 4.6: Test redaction doesn't break logging functionality

- [x] Task 5: Configure structlog for JSON output (AC: #4)
  - [x] Subtask 5.1: Update `main.py` or create `logging.py` for structlog config
  - [x] Subtask 5.2: Configure JSONRenderer for production
  - [x] Subtask 5.3: Configure ConsoleRenderer for development (optional based on env)
  - [x] Subtask 5.4: Add timestamp processor with ISO format
  - [x] Subtask 5.5: Add exception formatter for stack traces
  - [x] Subtask 5.6: Ensure stdout output (no file handlers)

- [x] Task 6: Create comprehensive test suite (AC: #1-6)
  - [x] Subtask 6.1: Create `tests/test_logging.py` for utility tests
  - [x] Subtask 6.2: Create `tests/services/test_error_logger.py` for service tests
  - [x] Subtask 6.3: Test secret redaction for all secret types
  - [x] Subtask 6.4: Test body truncation at 1KB boundary
  - [x] Subtask 6.5: Test DEX error logging with full context
  - [x] Subtask 6.6: Test webhook error logging with payload
  - [x] Subtask 6.7: Test log level consistency
  - [x] Subtask 6.8: Test JSON output format
  - [x] Subtask 6.9: Test wallet address non-redaction

## Dev Notes

### Architecture Compliance

**New File** (`src/kitkat/logging.py`):
- Centralized structlog configuration
- Secret redaction utilities
- Body truncation utilities
- Error type constants

**Service Layer** (`src/kitkat/services/error_logger.py`):
- ErrorLogger class with specialized logging methods
- Context binding for signal_id, dex_id, user_id
- Structured error formatting

**Integration Points:**
- `adapters/extended.py` - DEX API error logging
- `adapters/mock.py` - Test mode error logging
- `api/webhook.py` - Webhook validation error logging
- `services/signal_processor.py` - Execution error logging
- `services/health_monitor.py` - Health check error logging
- `services/alert.py` - Alert sending error logging

### Project Structure Notes

**Files to create:**
- `src/kitkat/logging.py` - Centralized logging config and utilities (~150 lines)
- `src/kitkat/services/error_logger.py` - ErrorLogger service (~200 lines)
- `tests/test_logging.py` - Logging utility tests (~200 lines)
- `tests/services/test_error_logger.py` - ErrorLogger service tests (~300 lines)

**Files to modify:**
- `src/kitkat/main.py` - Initialize structlog configuration (~10 lines)
- `src/kitkat/adapters/extended.py` - Add error logging calls (~15 lines)
- `src/kitkat/adapters/mock.py` - Add error logging calls (~10 lines)
- `src/kitkat/api/webhook.py` - Add error logging calls (~15 lines)
- `src/kitkat/services/signal_processor.py` - Add error logging calls (~20 lines)
- `src/kitkat/services/health_monitor.py` - Add error logging calls (~10 lines)
- `src/kitkat/services/alert.py` - Add error logging calls (~10 lines)

**Architecture alignment:**
```
src/kitkat/
├── logging.py                   # NEW - Centralized structlog config
├── services/
│   ├── error_logger.py          # NEW - ErrorLogger service
│   ├── signal_processor.py      # MODIFY - Add error logging
│   ├── health_monitor.py        # MODIFY - Add error logging
│   └── alert.py                 # MODIFY - Add error logging
├── adapters/
│   ├── extended.py              # MODIFY - Add DEX error logging
│   └── mock.py                  # MODIFY - Add test mode error logging
├── api/
│   └── webhook.py               # MODIFY - Add validation error logging
└── main.py                      # MODIFY - Initialize structlog

tests/
├── test_logging.py              # NEW - Logging utility tests
└── services/
    └── test_error_logger.py     # NEW - ErrorLogger tests
```

### Technical Requirements

**Error Type Constants:**
```python
# Error categories for structured logging (AC#1)
class ErrorType:
    """Standardized error type codes for structured logging."""

    # Webhook/Signal errors
    INVALID_SIGNAL = "INVALID_SIGNAL"
    DUPLICATE_SIGNAL = "DUPLICATE_SIGNAL"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_TOKEN = "INVALID_TOKEN"

    # DEX errors
    DEX_TIMEOUT = "DEX_TIMEOUT"
    DEX_ERROR = "DEX_ERROR"
    DEX_REJECTED = "DEX_REJECTED"
    DEX_CONNECTION_FAILED = "DEX_CONNECTION_FAILED"

    # Execution errors
    EXECUTION_FAILED = "EXECUTION_FAILED"
    PARTIAL_FILL = "PARTIAL_FILL"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"

    # System errors
    HEALTH_CHECK_FAILED = "HEALTH_CHECK_FAILED"
    ALERT_SEND_FAILED = "ALERT_SEND_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
```

**Secret Redaction Utilities (AC#5):**
```python
"""Logging utilities for secret redaction and body truncation."""

import re
from typing import Any

# Maximum body size before truncation (1KB)
MAX_BODY_SIZE = 1024

# Patterns for secret detection
SECRET_PATTERNS = {
    "api_key": re.compile(r"(api[_-]?key[s]?)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_-]{20,})", re.I),
    "token": re.compile(r"(token|secret|password)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_-]{8,})", re.I),
    "bearer": re.compile(r"(Bearer\s+)([a-zA-Z0-9_.-]+)", re.I),
}


def redact_secrets(value: str) -> str:
    """Redact secrets from a string value.

    AC#5: API keys show as "***", tokens show as first 4 chars + "..."
    Wallet addresses are NOT redacted (needed for debugging).

    Args:
        value: String that may contain secrets

    Returns:
        String with secrets redacted
    """
    result = value

    # Redact API keys (show as ***)
    result = re.sub(
        r"(api[_-]?key[s]?[\"']?\s*[:=]\s*[\"']?)([a-zA-Z0-9_-]{20,})",
        r"\1***",
        result,
        flags=re.I
    )

    # Redact tokens/secrets (show first 4 chars + ...)
    result = re.sub(
        r"(token|secret|password|bot_token)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_-]{8,})",
        lambda m: f"{m.group(1)}={m.group(2)[:4]}...",
        result,
        flags=re.I
    )

    # Redact Bearer tokens
    result = re.sub(
        r"(Bearer\s+)([a-zA-Z0-9_.-]+)",
        lambda m: f"{m.group(1)}{m.group(2)[:4]}...",
        result,
        flags=re.I
    )

    return result


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact secrets from HTTP headers.

    Args:
        headers: Dictionary of HTTP headers

    Returns:
        Headers with sensitive values redacted
    """
    sensitive_headers = {
        "authorization", "x-api-key", "x-webhook-token",
        "x-secret", "api-key", "token"
    }

    result = {}
    for key, value in headers.items():
        if key.lower() in sensitive_headers:
            # Show first 4 chars + ...
            result[key] = f"{value[:4]}..." if len(value) > 4 else "***"
        else:
            result[key] = value
    return result


def truncate_body(body: str | bytes | dict, max_size: int = MAX_BODY_SIZE) -> str:
    """Truncate response body if it exceeds max size (AC#2).

    Args:
        body: Response body (string, bytes, or dict)
        max_size: Maximum size in bytes (default: 1KB)

    Returns:
        Truncated body as string with indicator if truncated
    """
    if isinstance(body, dict):
        import json
        body = json.dumps(body)
    elif isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")

    if len(body) > max_size:
        return f"{body[:max_size]}... [TRUNCATED {len(body) - max_size} bytes]"
    return body


def sanitize_url(url: str) -> str:
    """Remove query parameters that might contain secrets.

    Args:
        url: URL that may contain secret query params

    Returns:
        URL with secret query params redacted
    """
    # Redact token query params
    result = re.sub(
        r"(\?|&)(token|api_key|secret)=([^&]+)",
        r"\1\2=***",
        url,
        flags=re.I
    )
    return result
```

**ErrorLogger Service (AC#1, #2, #3):**
```python
"""Centralized error logging service (Story 4.4).

Provides structured error logging with full context for debugging.
All errors are logged with categorized error codes, relevant context,
and sensitive data redaction.
"""

from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from kitkat.logging import (
    ErrorType,
    redact_headers,
    redact_secrets,
    sanitize_url,
    truncate_body,
)

logger = structlog.get_logger()


class ErrorLogger:
    """Centralized error logging with context binding.

    Story 4.4: Error Logging with Full Context
    - AC#1: Structured logging with bound context
    - AC#2: DEX API error context
    - AC#3: Webhook validation error context
    - AC#5: Secret redaction
    - AC#6: Consistent log levels
    """

    def __init__(self):
        """Initialize error logger."""
        self._log = logger.bind(service="error_logger")

    def log_dex_error(
        self,
        dex_id: str,
        error_type: str,
        error_message: str,
        *,
        signal_id: Optional[str] = None,
        request_method: Optional[str] = None,
        request_url: Optional[str] = None,
        request_headers: Optional[dict] = None,
        response_status: Optional[int] = None,
        response_body: Optional[str | dict] = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        """Log DEX API error with full context (AC#2).

        Args:
            dex_id: DEX identifier
            error_type: Categorized error code (e.g., DEX_TIMEOUT)
            error_message: Human-readable error description
            signal_id: Signal hash (if applicable)
            request_method: HTTP method (GET, POST, etc.)
            request_url: Request URL (secrets redacted)
            request_headers: Request headers (secrets redacted)
            response_status: HTTP response status code
            response_body: Response body (truncated if > 1KB)
            latency_ms: Request latency in milliseconds
        """
        log = self._log.bind(
            dex_id=dex_id,
            error_type=error_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if signal_id:
            log = log.bind(signal_id=signal_id)

        context: dict[str, Any] = {"error_message": error_message}

        # Add request context (AC#2)
        if request_method:
            context["request_method"] = request_method
        if request_url:
            context["request_url"] = sanitize_url(request_url)
        if request_headers:
            context["request_headers"] = redact_headers(request_headers)

        # Add response context (AC#2)
        if response_status is not None:
            context["response_status"] = response_status
        if response_body is not None:
            context["response_body"] = truncate_body(response_body)
        if latency_ms is not None:
            context["latency_ms"] = latency_ms

        log.error("DEX API error", **context)

    def log_webhook_error(
        self,
        error_type: str,
        error_message: str,
        *,
        raw_payload: Optional[str | dict] = None,
        validation_errors: Optional[list[str]] = None,
        client_ip: Optional[str] = None,
        webhook_token: Optional[str] = None,
    ) -> None:
        """Log webhook validation error with context (AC#3).

        Args:
            error_type: Categorized error code (e.g., INVALID_SIGNAL)
            error_message: Human-readable error description
            raw_payload: Raw webhook payload for debugging
            validation_errors: List of validation error details
            client_ip: Client IP address for abuse detection
            webhook_token: Webhook token (first 4 chars only)
        """
        log = self._log.bind(
            error_type=error_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        context: dict[str, Any] = {"error_message": error_message}

        # Add payload context (AC#3)
        if raw_payload is not None:
            if isinstance(raw_payload, dict):
                import json
                context["raw_payload"] = json.dumps(raw_payload)
            else:
                context["raw_payload"] = raw_payload

        if validation_errors:
            context["validation_errors"] = validation_errors

        if client_ip:
            context["client_ip"] = client_ip

        if webhook_token:
            # Redact token - show first 4 chars only (AC#5)
            context["webhook_token"] = f"{webhook_token[:4]}..."

        log.warning("Webhook validation error", **context)

    def log_execution_error(
        self,
        signal_id: str,
        dex_id: str,
        error_type: str,
        error_message: str,
        *,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        size: Optional[str] = None,
        order_id: Optional[str] = None,
        user_id: Optional[int] = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        """Log execution error with signal context (AC#1).

        Args:
            signal_id: Signal hash for correlation
            dex_id: DEX identifier
            error_type: Categorized error code
            error_message: Human-readable error description
            symbol: Trading pair symbol
            side: Order side (buy/sell)
            size: Order size
            order_id: DEX order ID (if available)
            user_id: User ID (if applicable)
            latency_ms: Execution latency in milliseconds
        """
        log = self._log.bind(
            signal_id=signal_id,
            dex_id=dex_id,
            error_type=error_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if user_id:
            log = log.bind(user_id=user_id)

        context: dict[str, Any] = {"error_message": error_message}

        if symbol:
            context["symbol"] = symbol
        if side:
            context["side"] = side
        if size:
            context["size"] = size
        if order_id:
            context["order_id"] = order_id
        if latency_ms is not None:
            context["latency_ms"] = latency_ms

        log.error("Execution error", **context)

    def log_system_error(
        self,
        error_type: str,
        error_message: str,
        *,
        component: Optional[str] = None,
        exception: Optional[Exception] = None,
        context: Optional[dict] = None,
    ) -> None:
        """Log general system error (AC#1).

        Args:
            error_type: Categorized error code
            error_message: Human-readable error description
            component: System component name
            exception: Exception object (for stack trace)
            context: Additional context dictionary
        """
        log = self._log.bind(
            error_type=error_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if component:
            log = log.bind(component=component)

        log_context: dict[str, Any] = {"error_message": error_message}

        if exception:
            log_context["exception_type"] = type(exception).__name__
            log_context["exception_message"] = str(exception)

        if context:
            # Redact any secrets in context values
            for key, value in context.items():
                if isinstance(value, str):
                    log_context[key] = redact_secrets(value)
                else:
                    log_context[key] = value

        log.error("System error", **log_context)
```

**Structlog Configuration (AC#4):**
```python
"""Structlog configuration for JSON output (Story 4.4: AC#4)."""

import logging
import sys

import structlog


def configure_logging(json_output: bool = True) -> None:
    """Configure structlog for structured JSON logging.

    AC#4: JSON format for structured output, stdout for container-friendliness.

    Args:
        json_output: Use JSON format (True) or console format (False)
    """
    # Shared processors for all outputs
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        # Production: JSON output to stdout
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Development: Colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer()
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (optional, for context binding)

    Returns:
        Configured structlog logger
    """
    log = structlog.get_logger()
    if name:
        log = log.bind(logger=name)
    return log
```

### Previous Story Intelligence

**From Story 4.3 (Auto-Recovery After Outage):**
- HealthMonitor logs health check failures with `self._log.warning("Health check failed", ...)`
- Pattern: Bind context once (`self._log.bind(dex_id=dex_id)`), then log with additional context
- Errors logged but not raised (graceful degradation)
- Uses `structlog.get_logger()` throughout

**From Story 4.2 (Telegram Alert Service):**
- Alert failures logged at ERROR level with context
- Pattern: `self._log.error("Failed to send Telegram alert", error=str(e), chat_id=...)`
- Fire-and-forget pattern - errors logged but never block main flow
- Rate limiting state tracked in-memory

**From Story 4.1 (Health Service & DEX Status):**
- Health check results logged with latency_ms
- Pattern: `log.info("Health check passed", latency_ms=result.latency_ms)`
- Status transitions logged: `log.info("DEX recovered", old_status=old_status)`
- 5-minute error window tracking (could be extended for error logging)

**From Story 2.9 (Signal Processor & Fan-Out):**
- Parallel execution with `asyncio.gather(return_exceptions=True)`
- Per-DEX results collected and logged
- Pattern: `logger.bind(signal_id=signal.id)` at start of processing
- Errors logged with dex_id, signal_id, error_message

**From Story 2.5 (Extended Adapter - Connection):**
- Connection errors logged with full context
- Pattern: `log.error("Connection failed", error=str(e), dex_id=self.dex_id)`
- HTTP request/response logging already exists (needs secret redaction)

**Key Patterns Observed:**
1. Structlog used throughout with `logger.bind()` for context
2. ERROR level for failures, WARNING for recoverable issues
3. Context bound once, then logged with additional details
4. Errors never block main flow (fire-and-forget pattern)
5. Latency tracked and logged for performance visibility

### Git Intelligence

**Recent Commits (Story 4.1-4.3):**
```
f40cddf Story 4.3: Fix code review issues for HealthMonitor
dce06d7 Story 4.1: Fix critical code review issues from adversarial review
6a1fcf4 Story 4.1: Mark as complete and ready for code review
```

**Patterns Observed:**
- Comprehensive test coverage (30-40 tests per story)
- Code review fixes for edge cases
- Consistent use of structlog for logging
- Secret handling in config (telegram_bot_token, telegram_chat_id)
- JSON configuration data stored in user config

**Existing Logging Patterns in Codebase:**
```python
# From services/health_monitor.py
self._log = logger.bind(service="health_monitor")
log = self._log.bind(dex_id=dex_id)
log.warning("Health check failed", consecutive_failures=failure_count)

# From services/alert.py
self._log = logger.bind(service="alert")
self._log.error("Failed to send Telegram alert", error=str(e), chat_id=self._chat_id)

# From services/signal_processor.py
self._log = logger.bind(service="signal_processor")
log = self._log.bind(signal_id=signal_id)
log.error("Execution failed", dex_id=dex_id, error=str(e))
```

### Configuration Requirements

**No new configuration needed** - this story enhances existing logging without new environment variables.

**Existing Settings Used:**
- `telegram_bot_token` - Must be redacted in logs
- `telegram_chat_id` - Must be redacted in logs
- `extended_api_key` - Must be redacted in logs
- `extended_api_secret` - Must be redacted in logs
- `webhook_token` - Must be redacted in logs

**Optional Future Enhancement:**
- `LOG_FORMAT` env var to toggle JSON/console output (not required for MVP)
- `LOG_LEVEL` env var to control log level (not required for MVP)

### Performance Considerations

- Logging should NEVER block main execution flow
- Secret redaction uses regex - optimize patterns for performance
- Body truncation at 1KB prevents memory issues with large responses
- Use lazy evaluation for expensive log context (e.g., JSON serialization)
- Structlog caches logger instances for performance

### Edge Cases

1. **Empty response body**: Log as empty string, not None
2. **Binary response body**: Decode with errors='replace' to prevent crashes
3. **Very long URLs**: Don't truncate, but redact query params
4. **Missing context fields**: Log without them (optional fields)
5. **Exception with no message**: Log exception type only
6. **Unicode in payloads**: Handle encoding properly
7. **Nested secrets in JSON**: Redact recursively if needed
8. **Concurrent logging**: Structlog is thread-safe
9. **Logging during shutdown**: Ensure logs flush before exit
10. **Circular references in context**: Use safe JSON serialization

### Testing Strategy

**Unit tests (tests/test_logging.py):**
1. Test `redact_secrets()` with API keys
2. Test `redact_secrets()` with tokens (first 4 chars + ...)
3. Test `redact_secrets()` preserves wallet addresses
4. Test `redact_headers()` with sensitive headers
5. Test `truncate_body()` at 1KB boundary
6. Test `truncate_body()` with dict input
7. Test `truncate_body()` with bytes input
8. Test `sanitize_url()` with token query params
9. Test `configure_logging()` with JSON output
10. Test `configure_logging()` with console output

**Service tests (tests/services/test_error_logger.py):**
1. Test `log_dex_error()` with full context
2. Test `log_dex_error()` with minimal context
3. Test `log_webhook_error()` with raw payload
4. Test `log_webhook_error()` with validation errors
5. Test `log_execution_error()` with signal context
6. Test `log_system_error()` with exception
7. Test secret redaction in all logging methods
8. Test body truncation in DEX error logging
9. Test context binding (signal_id, dex_id, user_id)
10. Test log level consistency (ERROR for failures)

**Integration tests:**
1. Test logging integration in webhook endpoint
2. Test logging integration in signal processor
3. Test JSON output format in production mode
4. Test logs written to stdout

**Mock Strategy:**
- Mock `structlog.get_logger()` to capture log calls
- Assert on log level, message, and context
- Verify secret redaction in captured logs

### Library-Specific Notes

**Structlog Patterns:**
```python
import structlog

# Get logger and bind context
logger = structlog.get_logger()
log = logger.bind(signal_id="abc123", dex_id="extended")

# Log with additional context
log.info("Processing signal", symbol="ETH-PERP", side="buy")
log.error("Execution failed", error_type="DEX_TIMEOUT", error="Connection reset")

# Output (JSON format):
# {"event": "Processing signal", "signal_id": "abc123", "dex_id": "extended",
#  "symbol": "ETH-PERP", "side": "buy", "level": "info", "timestamp": "2026-01-19T..."}
```

**Log Level Guidelines (AC#6):**
| Level | Usage | Examples |
|-------|-------|----------|
| DEBUG | Development details, raw payloads | `log.debug("Raw payload", payload=raw)` |
| INFO | Normal operations, successful executions | `log.info("Signal processed", signal_id=...)` |
| WARNING | Recoverable issues, degraded states | `log.warning("DEX degraded", dex_id=...)` |
| ERROR | Failures requiring attention | `log.error("Execution failed", error=...)` |

### References

- [Source: _bmad-output/planning-artifacts/architecture.md - Logging Pattern: structlog with signal_id binding]
- [Source: _bmad-output/planning-artifacts/epics.md - Story 4.4: Error Logging with Full Context (AC#1-6)]
- [Source: _bmad-output/planning-artifacts/prd.md - FR29: Log errors with full context]
- [Source: _bmad-output/project-context.md - Logging Standards]
- [Source: Story 4.1 - HealthService logging patterns]
- [Source: Story 4.2 - TelegramAlertService error logging]
- [Source: Story 4.3 - HealthMonitor health check logging]
- [Source: Story 2.9 - SignalProcessor execution logging]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Implementation Readiness

**Prerequisites met:**
- Structlog already in dependencies and used throughout codebase
- Error logging exists but needs standardization and enhancement
- Signal context binding pattern established (Story 2.9)
- DEX adapter error handling exists (Story 2.5+)
- Webhook validation errors already logged (Story 1.4)

**Functional Requirements Covered:**
- FR29: System can log errors with full context (payload, DEX response, timestamps)

**Non-Functional Requirements Covered:**
- NFR10: Audit log immutability - append-only, no deletion capability (stdout logging)

**Scope Assessment:**
- Logging utilities: ~150 lines
- ErrorLogger service: ~200 lines
- Integration changes: ~80 lines across 6 files
- Tests: ~500 lines
- **Total: ~930 lines across 10+ files**

**Dependencies:**
- Story 4.1 complete (HealthService logging established)
- Story 4.2 complete (AlertService error logging established)
- Story 4.3 complete (HealthMonitor logging established)
- All Epic 1-3 stories complete (existing logging patterns)

**Related Stories:**
- Story 4.5 (Error Log Viewer): Will read errors logged by this story from database (future - currently stdout only)
- Story 5.4 (Dashboard): May reference error counts from logs

### Debug Log References

N/A

### Completion Notes List

N/A

### File List

N/A
