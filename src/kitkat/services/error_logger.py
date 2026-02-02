"""Centralized error logging service (Story 4.4 + Story 4.5).

Provides structured error logging with full context for debugging.
All errors are logged with categorized error codes, relevant context,
and sensitive data redaction.

Story 4.4:
AC#1: Structured logging with bound context (signal_id, dex_id, user_id)
AC#2: DEX API error context (request/response details)
AC#3: Webhook validation error context (payload, validation errors)
AC#5: Secret redaction
AC#6: Consistent log levels

Story 4.5:
AC#5: Database persistence for error log viewer
"""

import asyncio
import json as json_module
from datetime import datetime, timezone
from typing import Any

import structlog

from kitkat.logging import (
    redact_headers,
    redact_secrets,
    sanitize_url,
    truncate_body,
)

logger = structlog.get_logger()

# Module-level singleton instance
_error_logger_instance: "ErrorLogger | None" = None


class ErrorLogger:
    """Centralized error logging with context binding.

    Story 4.4: Error Logging with Full Context
    - AC#1: Structured logging with bound context
    - AC#2: DEX API error context
    - AC#3: Webhook validation error context
    - AC#5: Secret redaction
    - AC#6: Consistent log levels

    Story 4.5: Database Persistence
    - AC#5: Errors persisted to database for user viewing
    """

    def __init__(self) -> None:
        """Initialize error logger with service context binding."""
        self._log = logger.bind(service="error_logger")

    def _persist_error(
        self,
        level: str,
        error_type: str,
        message: str,
        context: dict[str, Any],
    ) -> None:
        """Persist error to database using fire-and-forget pattern (Story 4.5).

        Uses asyncio.create_task() for non-blocking database writes.
        Failures are logged but don't affect the main logging operation.

        Args:
            level: Log level ("error" or "warning")
            error_type: Categorized error code
            message: Human-readable error description
            context: Additional context dictionary
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._async_persist_error(level, error_type, message, context))
        except RuntimeError:
            # No running event loop - skip persistence (e.g., in sync tests)
            pass

    async def _async_persist_error(
        self,
        level: str,
        error_type: str,
        message: str,
        context: dict[str, Any],
    ) -> None:
        """Async helper to persist error to database.

        Args:
            level: Log level
            error_type: Error type code
            message: Error message
            context: Context data
        """
        try:
            from kitkat.database import ErrorLogModel, get_async_session_factory

            factory = get_async_session_factory()
            async with factory() as session:
                record = ErrorLogModel(
                    level=level,
                    error_type=error_type,
                    message=message,
                    context_data=json_module.dumps(context),
                    created_at=datetime.now(timezone.utc),
                )
                session.add(record)
                await session.commit()
        except Exception as e:
            # Log failure but don't raise - persistence is fire-and-forget
            self._log.warning(
                "Failed to persist error to database",
                error=str(e),
                error_type=error_type,
            )

    def log_dex_error(
        self,
        dex_id: str,
        error_type: str,
        error_message: str,
        *,
        signal_id: str | None = None,
        request_method: str | None = None,
        request_url: str | None = None,
        request_headers: dict[str, str] | None = None,
        response_status: int | None = None,
        response_body: str | bytes | dict[str, Any] | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Log DEX API error with full context (AC#2).

        Logs DEX communication failures with complete request/response details
        for debugging. Sensitive data is automatically redacted.

        Args:
            dex_id: DEX identifier (e.g., "extended")
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

        # Persist to database (Story 4.5: AC#5)
        persist_context = {
            "dex_id": dex_id,
            "signal_id": signal_id,
            "latency_ms": latency_ms,
        }
        self._persist_error("error", error_type, error_message, persist_context)

    def log_webhook_error(
        self,
        error_type: str,
        error_message: str,
        *,
        raw_payload: str | dict[str, Any] | None = None,
        validation_errors: list[str] | None = None,
        client_ip: str | None = None,
        webhook_token: str | None = None,
    ) -> None:
        """Log webhook validation error with context (AC#3).

        Logs webhook validation failures with payload and client details
        for debugging malformed requests and detecting abuse.

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
                context["raw_payload"] = json_module.dumps(raw_payload)
            else:
                context["raw_payload"] = raw_payload

        if validation_errors:
            context["validation_errors"] = validation_errors

        if client_ip:
            context["client_ip"] = client_ip

        if webhook_token:
            # Redact token - show first 4 chars only (AC#5)
            context["webhook_token"] = f"{webhook_token[:4]}..."

        # Webhook validation errors are WARNING level (AC#6)
        # They indicate client errors, not system failures
        log.warning("Webhook validation error", **context)

        # Persist to database (Story 4.5: AC#5)
        persist_context = {
            "client_ip": client_ip,
            "validation_errors": validation_errors,
        }
        self._persist_error("warning", error_type, error_message, persist_context)

    def log_execution_error(
        self,
        signal_id: str,
        dex_id: str,
        error_type: str,
        error_message: str,
        *,
        symbol: str | None = None,
        side: str | None = None,
        size: str | None = None,
        order_id: str | None = None,
        user_id: int | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Log execution error with signal context (AC#1).

        Logs order execution failures with full signal and order context
        for debugging trade failures.

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

        # Execution errors are ERROR level (AC#6)
        log.error("Execution error", **context)

        # Persist to database (Story 4.5: AC#5)
        persist_context = {
            "signal_id": signal_id,
            "dex_id": dex_id,
            "symbol": symbol,
            "side": side,
            "size": size,
            "order_id": order_id,
            "user_id": user_id,
            "latency_ms": latency_ms,
        }
        self._persist_error("error", error_type, error_message, persist_context)

    def log_system_error(
        self,
        error_type: str,
        error_message: str,
        *,
        component: str | None = None,
        exception: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log general system error (AC#1).

        Logs infrastructure and system-level errors with exception details
        and component context.

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
            # Redact any secrets in context values (AC#5)
            for key, value in context.items():
                if isinstance(value, str):
                    log_context[key] = redact_secrets(value)
                else:
                    log_context[key] = value

        # System errors are ERROR level (AC#6)
        log.error("System error", **log_context)

        # Persist to database (Story 4.5: AC#5)
        persist_context = {
            "component": component,
        }
        if exception:
            persist_context["exception_type"] = type(exception).__name__
            persist_context["exception_message"] = str(exception)
        if context:
            # Merge additional context (already redacted in log_context)
            for key, value in context.items():
                if isinstance(value, str):
                    persist_context[key] = redact_secrets(value)
                else:
                    persist_context[key] = value
        self._persist_error("error", error_type, error_message, persist_context)


def get_error_logger() -> ErrorLogger:
    """Get ErrorLogger singleton instance.

    Returns:
        ErrorLogger: Singleton instance for centralized error logging
    """
    global _error_logger_instance
    if _error_logger_instance is None:
        _error_logger_instance = ErrorLogger()
    return _error_logger_instance
