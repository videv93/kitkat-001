"""Centralized logging utilities for error logging (Story 4.4).

Provides:
- Secret redaction for API keys, tokens, and auth headers
- Body truncation for large payloads (1KB limit)
- URL sanitization for secret query params
- Structlog JSON/console configuration
- Standardized error type constants

AC#1: Structured error logging with bound context
AC#4: JSON format for structured log output
AC#5: Secret redaction (API keys as ***, tokens as first 4 chars + ...)
"""

import json as json_module
import logging
import re
import sys
from typing import Any

import structlog

# Maximum body size before truncation (1KB per AC#2)
MAX_BODY_SIZE = 1024


class ErrorType:
    """Standardized error type codes for structured logging (AC#1).

    Categories:
    - Webhook/Signal errors: Validation and authentication failures
    - DEX errors: API communication failures
    - Execution errors: Order execution failures
    - System errors: Infrastructure and configuration failures
    """

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


def redact_secrets(value: str) -> str:
    """Redact secrets from a string value (AC#5).

    Redaction rules:
    - API keys: Show as "***"
    - Tokens/secrets/passwords: Show first 4 chars + "..."
    - Bearer tokens: Show "Bearer" + first 4 chars of token + "..."
    - Wallet addresses: NOT redacted (needed for debugging)

    Args:
        value: String that may contain secrets

    Returns:
        String with secrets redacted
    """
    result = value

    # Redact API keys (show as ***)
    # Matches: api_key=xxx, api-key: "xxx", API_KEY="xxx"
    result = re.sub(
        r"(api[_-]?key[s]?[\"']?\s*[:=]\s*[\"']?)([a-zA-Z0-9_-]{20,})",
        r"\1***",
        result,
        flags=re.IGNORECASE,
    )

    # Redact tokens/secrets/passwords (show first 4 chars + ...)
    # Matches: token=xxx, secret: xxx, password="xxx", bot_token=xxx
    result = re.sub(
        r"(token|secret|password|bot_token)([\"']?\s*[:=]\s*[\"']?)([a-zA-Z0-9_:-]{8,})",
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)[:4]}...",
        result,
        flags=re.IGNORECASE,
    )

    # Redact Bearer tokens
    # Matches: Bearer eyJxxx... or Bearer sk_xxx
    result = re.sub(
        r"(Bearer\s+)([a-zA-Z0-9_.-]+)",
        lambda m: f"{m.group(1)}{m.group(2)[:4]}...",
        result,
        flags=re.IGNORECASE,
    )

    return result


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact secrets from HTTP headers (AC#5).

    Sensitive headers are redacted to show first 4 chars + "...".
    Non-sensitive headers are preserved unchanged.

    Args:
        headers: Dictionary of HTTP headers

    Returns:
        Headers with sensitive values redacted
    """
    sensitive_headers = {
        "authorization",
        "x-api-key",
        "x-webhook-token",
        "x-secret",
        "api-key",
        "token",
    }

    result = {}
    for key, value in headers.items():
        if key.lower() in sensitive_headers:
            # Show first 4 chars + ... for longer values, *** for short
            if len(value) > 4:
                result[key] = f"{value[:4]}..."
            else:
                result[key] = "***"
        else:
            result[key] = value
    return result


def truncate_body(body: str | bytes | dict[str, Any], max_size: int = MAX_BODY_SIZE) -> str:
    """Truncate response body if it exceeds max size (AC#2).

    Handles string, bytes, and dict inputs. Large bodies are truncated
    with an indicator showing how many bytes were removed.

    Args:
        body: Response body (string, bytes, or dict)
        max_size: Maximum size in bytes (default: 1KB)

    Returns:
        Truncated body as string with indicator if truncated
    """
    if isinstance(body, dict):
        body = json_module.dumps(body)
    elif isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")

    if len(body) > max_size:
        truncated_bytes = len(body) - max_size
        return f"{body[:max_size]}... [TRUNCATED {truncated_bytes} bytes]"
    return body


def sanitize_url(url: str) -> str:
    """Remove query parameters that might contain secrets (AC#5).

    Redacts common secret query parameters like token, api_key, secret.
    Non-sensitive parameters are preserved.

    Args:
        url: URL that may contain secret query params

    Returns:
        URL with secret query params redacted
    """
    # Redact token/api_key/secret query params
    result = re.sub(
        r"(\?|&)(token|api_key|secret)=([^&]+)",
        r"\1\2=***",
        url,
        flags=re.IGNORECASE,
    )
    return result


def configure_logging(json_output: bool = True) -> None:
    """Configure structlog for structured JSON logging (AC#4).

    Sets up structlog with:
    - JSON output (production) or console output (development)
    - ISO timestamp format
    - Log level and stack trace formatting
    - Stdout output (container-friendly)

    Args:
        json_output: Use JSON format (True) or console format (False)
    """
    # Shared processors for all outputs
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        # Production: JSON output to stdout
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        # Development: Colored console output
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
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
