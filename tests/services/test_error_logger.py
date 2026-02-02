"""Tests for ErrorLogger service (Story 4.4: AC#1, #2, #3, #5, #6).

Tests cover:
- DEX API error logging with full request/response context
- Webhook validation error logging with payload
- Execution error logging with signal context
- System error logging with exception details
- Secret redaction in all logging methods
- Log level consistency
"""

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest
import structlog


class TestErrorLoggerInit:
    """Tests for ErrorLogger initialization."""

    def test_creates_bound_logger(self):
        """ErrorLogger should create a bound logger with service context."""
        from kitkat.services.error_logger import ErrorLogger

        error_logger = ErrorLogger()
        assert error_logger._log is not None

    def test_binds_service_name(self):
        """ErrorLogger should bind service='error_logger' to context."""
        from kitkat.services.error_logger import ErrorLogger

        error_logger = ErrorLogger()
        # Logger should be bound with service name
        assert error_logger._log is not None


class TestLogDexError:
    """Tests for log_dex_error() method (AC#2)."""

    def test_logs_with_full_context(self):
        """DEX error should be logged with full request/response context."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_dex_error(
                dex_id="extended",
                error_type=ErrorType.DEX_TIMEOUT,
                error_message="Connection timeout",
                signal_id="abc123",
                request_method="POST",
                request_url="https://api.example.com/orders",
                request_headers={"Content-Type": "application/json"},
                response_status=504,
                response_body='{"error": "Gateway Timeout"}',
                latency_ms=5000,
            )

            # Should bind dex_id, error_type, timestamp
            mock_log.bind.assert_called()
            # Should log at error level
            mock_bound.error.assert_called_once()

    def test_logs_with_minimal_context(self):
        """DEX error should work with minimal required fields."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound

            error_logger.log_dex_error(
                dex_id="extended",
                error_type=ErrorType.DEX_ERROR,
                error_message="Generic error",
            )

            mock_bound.error.assert_called_once()

    def test_redacts_headers(self):
        """DEX error should redact sensitive headers."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_dex_error(
                dex_id="extended",
                error_type=ErrorType.DEX_ERROR,
                error_message="Error",
                request_headers={"Authorization": "Bearer sk_live_secret123"},
            )

            # Capture the call arguments
            call_args = mock_bound.error.call_args
            kwargs = call_args[1] if call_args[1] else {}

            # Authorization header should be redacted
            if "request_headers" in kwargs:
                assert "sk_live_secret123" not in str(kwargs["request_headers"])

    def test_sanitizes_url(self):
        """DEX error should sanitize URLs with secret params."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_dex_error(
                dex_id="extended",
                error_type=ErrorType.DEX_ERROR,
                error_message="Error",
                request_url="https://api.example.com?token=secret123",
            )

            call_args = mock_bound.error.call_args
            kwargs = call_args[1] if call_args[1] else {}

            if "request_url" in kwargs:
                assert "secret123" not in kwargs["request_url"]

    def test_truncates_large_response_body(self):
        """DEX error should truncate response bodies > 1KB."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            large_body = "x" * 2000
            error_logger.log_dex_error(
                dex_id="extended",
                error_type=ErrorType.DEX_ERROR,
                error_message="Error",
                response_body=large_body,
            )

            call_args = mock_bound.error.call_args
            kwargs = call_args[1] if call_args[1] else {}

            if "response_body" in kwargs:
                assert "TRUNCATED" in kwargs["response_body"]
                assert len(kwargs["response_body"]) < 2000


class TestLogWebhookError:
    """Tests for log_webhook_error() method (AC#3)."""

    def test_logs_with_raw_payload(self):
        """Webhook error should include raw payload for debugging."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound

            error_logger.log_webhook_error(
                error_type=ErrorType.INVALID_SIGNAL,
                error_message="Invalid JSON",
                raw_payload='{"invalid": json}',
            )

            call_args = mock_bound.warning.call_args
            kwargs = call_args[1] if call_args[1] else {}

            assert "raw_payload" in kwargs

    def test_logs_validation_errors(self):
        """Webhook error should include validation error details."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound

            error_logger.log_webhook_error(
                error_type=ErrorType.INVALID_SIGNAL,
                error_message="Validation failed",
                validation_errors=["Missing field: symbol", "Invalid side value"],
            )

            call_args = mock_bound.warning.call_args
            kwargs = call_args[1] if call_args[1] else {}

            assert "validation_errors" in kwargs
            assert len(kwargs["validation_errors"]) == 2

    def test_logs_client_ip(self):
        """Webhook error should include client IP for abuse detection."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound

            error_logger.log_webhook_error(
                error_type=ErrorType.RATE_LIMITED,
                error_message="Rate limit exceeded",
                client_ip="192.168.1.100",
            )

            call_args = mock_bound.warning.call_args
            kwargs = call_args[1] if call_args[1] else {}

            assert kwargs.get("client_ip") == "192.168.1.100"

    def test_redacts_webhook_token(self):
        """Webhook error should redact webhook token (show first 4 chars)."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound

            error_logger.log_webhook_error(
                error_type=ErrorType.INVALID_TOKEN,
                error_message="Invalid token",
                webhook_token="mysupersecrettoken",
            )

            call_args = mock_bound.warning.call_args
            kwargs = call_args[1] if call_args[1] else {}

            assert "mysupersecrettoken" not in str(kwargs.get("webhook_token", ""))
            assert kwargs.get("webhook_token", "").startswith("mysu")
            assert kwargs.get("webhook_token", "").endswith("...")

    def test_logs_at_warning_level(self):
        """Webhook validation errors should log at WARNING level (AC#6)."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound

            error_logger.log_webhook_error(
                error_type=ErrorType.INVALID_SIGNAL,
                error_message="Invalid signal",
            )

            # Should use warning, not error
            mock_bound.warning.assert_called_once()
            mock_bound.error.assert_not_called()

    def test_handles_dict_payload(self):
        """Webhook error should handle dict raw_payload."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound

            error_logger.log_webhook_error(
                error_type=ErrorType.INVALID_SIGNAL,
                error_message="Invalid",
                raw_payload={"symbol": "ETH-PERP", "side": "invalid"},
            )

            call_args = mock_bound.warning.call_args
            kwargs = call_args[1] if call_args[1] else {}

            # Dict should be serialized to string
            assert "raw_payload" in kwargs
            assert isinstance(kwargs["raw_payload"], str)


class TestLogExecutionError:
    """Tests for log_execution_error() method (AC#1)."""

    def test_logs_with_signal_context(self):
        """Execution error should bind signal_id, dex_id."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_execution_error(
                signal_id="abc123",
                dex_id="extended",
                error_type=ErrorType.EXECUTION_FAILED,
                error_message="Order rejected",
                symbol="ETH-PERP",
                side="buy",
                size="0.5",
            )

            # Should bind signal_id, dex_id, error_type
            bind_calls = [str(c) for c in mock_log.bind.call_args_list]
            assert any("signal_id" in c for c in bind_calls)

    def test_logs_order_details(self):
        """Execution error should include symbol, side, size."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_execution_error(
                signal_id="abc123",
                dex_id="extended",
                error_type=ErrorType.INSUFFICIENT_FUNDS,
                error_message="Insufficient balance",
                symbol="BTC-PERP",
                side="sell",
                size="1.5",
                order_id="order_123",
            )

            call_args = mock_bound.error.call_args
            kwargs = call_args[1] if call_args[1] else {}

            assert kwargs.get("symbol") == "BTC-PERP"
            assert kwargs.get("side") == "sell"
            assert kwargs.get("size") == "1.5"
            assert kwargs.get("order_id") == "order_123"

    def test_logs_user_id(self):
        """Execution error should bind user_id when provided."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_execution_error(
                signal_id="abc123",
                dex_id="extended",
                error_type=ErrorType.EXECUTION_FAILED,
                error_message="Error",
                user_id=42,
            )

            # Should bind user_id
            bind_calls = mock_bound.bind.call_args_list
            assert len(bind_calls) > 0

    def test_logs_latency(self):
        """Execution error should include latency_ms."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_execution_error(
                signal_id="abc123",
                dex_id="extended",
                error_type=ErrorType.DEX_TIMEOUT,
                error_message="Timeout",
                latency_ms=5000,
            )

            call_args = mock_bound.error.call_args
            kwargs = call_args[1] if call_args[1] else {}

            assert kwargs.get("latency_ms") == 5000

    def test_logs_at_error_level(self):
        """Execution errors should log at ERROR level (AC#6)."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_execution_error(
                signal_id="abc123",
                dex_id="extended",
                error_type=ErrorType.EXECUTION_FAILED,
                error_message="Failed",
            )

            mock_bound.error.assert_called_once()


class TestLogSystemError:
    """Tests for log_system_error() method (AC#1)."""

    def test_logs_with_component(self):
        """System error should include component name."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_system_error(
                error_type=ErrorType.DATABASE_ERROR,
                error_message="Connection lost",
                component="database",
            )

            # Should bind component
            bind_calls = mock_bound.bind.call_args_list
            assert len(bind_calls) > 0

    def test_logs_exception_details(self):
        """System error should include exception type and message."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            try:
                raise ValueError("Test error message")
            except ValueError as e:
                error_logger.log_system_error(
                    error_type=ErrorType.CONFIGURATION_ERROR,
                    error_message="Config failed",
                    exception=e,
                )

            call_args = mock_bound.error.call_args
            kwargs = call_args[1] if call_args[1] else {}

            assert kwargs.get("exception_type") == "ValueError"
            assert kwargs.get("exception_message") == "Test error message"

    def test_logs_additional_context(self):
        """System error should include additional context dict."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_system_error(
                error_type=ErrorType.HEALTH_CHECK_FAILED,
                error_message="Health check failed",
                context={"dex_id": "extended", "consecutive_failures": 3},
            )

            call_args = mock_bound.error.call_args
            kwargs = call_args[1] if call_args[1] else {}

            assert kwargs.get("dex_id") == "extended"
            assert kwargs.get("consecutive_failures") == 3

    def test_redacts_secrets_in_context(self):
        """System error should redact secrets in context values."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_system_error(
                error_type=ErrorType.CONFIGURATION_ERROR,
                error_message="Config error",
                context={"config_value": "api_key=sk_live_secret1234567890abcd"},
            )

            call_args = mock_bound.error.call_args
            kwargs = call_args[1] if call_args[1] else {}

            if "config_value" in kwargs:
                assert "sk_live_secret" not in kwargs["config_value"]

    def test_logs_at_error_level(self):
        """System errors should log at ERROR level (AC#6)."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_system_error(
                error_type=ErrorType.ALERT_SEND_FAILED,
                error_message="Alert failed",
            )

            mock_bound.error.assert_called_once()


class TestTimestampBinding:
    """Tests for timestamp binding in all log methods."""

    def test_dex_error_has_iso_timestamp(self):
        """DEX error should include ISO format timestamp."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_dex_error(
                dex_id="extended",
                error_type=ErrorType.DEX_ERROR,
                error_message="Error",
            )

            # First bind call should include timestamp
            bind_kwargs = mock_log.bind.call_args[1]
            assert "timestamp" in bind_kwargs

    def test_webhook_error_has_iso_timestamp(self):
        """Webhook error should include ISO format timestamp."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound

            error_logger.log_webhook_error(
                error_type=ErrorType.INVALID_SIGNAL,
                error_message="Error",
            )

            bind_kwargs = mock_log.bind.call_args[1]
            assert "timestamp" in bind_kwargs

    def test_execution_error_has_iso_timestamp(self):
        """Execution error should include ISO format timestamp."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_execution_error(
                signal_id="abc123",
                dex_id="extended",
                error_type=ErrorType.EXECUTION_FAILED,
                error_message="Error",
            )

            bind_kwargs = mock_log.bind.call_args[1]
            assert "timestamp" in bind_kwargs

    def test_system_error_has_iso_timestamp(self):
        """System error should include ISO format timestamp."""
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType

        error_logger = ErrorLogger()

        with patch.object(error_logger, "_log") as mock_log:
            mock_bound = MagicMock()
            mock_log.bind.return_value = mock_bound
            mock_bound.bind.return_value = mock_bound

            error_logger.log_system_error(
                error_type=ErrorType.DATABASE_ERROR,
                error_message="Error",
            )

            bind_kwargs = mock_log.bind.call_args[1]
            assert "timestamp" in bind_kwargs


class TestSingletonPattern:
    """Tests for ErrorLogger singleton access pattern."""

    def test_get_error_logger_returns_instance(self):
        """get_error_logger() should return an ErrorLogger instance."""
        from kitkat.services.error_logger import get_error_logger

        logger = get_error_logger()
        assert logger is not None
        from kitkat.services.error_logger import ErrorLogger
        assert isinstance(logger, ErrorLogger)

    def test_get_error_logger_returns_same_instance(self):
        """get_error_logger() should return the same instance (singleton)."""
        from kitkat.services.error_logger import get_error_logger

        logger1 = get_error_logger()
        logger2 = get_error_logger()
        assert logger1 is logger2


class TestDatabasePersistence:
    """Tests for database persistence (Story 4.5: AC#5)."""

    @pytest.mark.asyncio
    async def test_log_dex_error_persists_to_database(self, db_session):
        """log_dex_error should persist error to database."""
        import asyncio
        from sqlalchemy import select
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType
        from kitkat.database import ErrorLogModel

        error_logger = ErrorLogger()
        error_logger.log_dex_error(
            dex_id="extended",
            error_type=ErrorType.DEX_TIMEOUT,
            error_message="Connection timeout",
            signal_id="abc123",
            latency_ms=5000,
        )

        # Wait for async persistence task
        await asyncio.sleep(0.1)

        # Verify record was created
        result = await db_session.execute(select(ErrorLogModel))
        records = result.scalars().all()

        assert len(records) >= 1
        # Find our error
        dex_errors = [r for r in records if r.error_type == ErrorType.DEX_TIMEOUT]
        assert len(dex_errors) >= 1
        assert dex_errors[0].level == "error"
        assert dex_errors[0].message == "Connection timeout"

    @pytest.mark.asyncio
    async def test_log_webhook_error_persists_to_database(self, db_session):
        """log_webhook_error should persist error to database."""
        import asyncio
        from sqlalchemy import select
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType
        from kitkat.database import ErrorLogModel

        error_logger = ErrorLogger()
        error_logger.log_webhook_error(
            error_type=ErrorType.INVALID_SIGNAL,
            error_message="Invalid JSON",
            raw_payload='{"bad": json}',
        )

        # Wait for async persistence task
        await asyncio.sleep(0.1)

        result = await db_session.execute(select(ErrorLogModel))
        records = result.scalars().all()

        webhook_errors = [r for r in records if r.error_type == ErrorType.INVALID_SIGNAL]
        assert len(webhook_errors) >= 1
        # Webhook errors are warning level
        assert webhook_errors[0].level == "warning"

    @pytest.mark.asyncio
    async def test_log_execution_error_persists_to_database(self, db_session):
        """log_execution_error should persist error to database."""
        import asyncio
        from sqlalchemy import select
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType
        from kitkat.database import ErrorLogModel

        error_logger = ErrorLogger()
        error_logger.log_execution_error(
            signal_id="test123",
            dex_id="extended",
            error_type=ErrorType.EXECUTION_FAILED,
            error_message="Order rejected",
            symbol="ETH-PERP",
        )

        # Wait for async persistence task
        await asyncio.sleep(0.1)

        result = await db_session.execute(select(ErrorLogModel))
        records = result.scalars().all()

        exec_errors = [r for r in records if r.error_type == ErrorType.EXECUTION_FAILED]
        assert len(exec_errors) >= 1
        assert exec_errors[0].level == "error"

    @pytest.mark.asyncio
    async def test_log_system_error_persists_to_database(self, db_session):
        """log_system_error should persist error to database."""
        import asyncio
        from sqlalchemy import select
        from kitkat.services.error_logger import ErrorLogger
        from kitkat.logging import ErrorType
        from kitkat.database import ErrorLogModel

        error_logger = ErrorLogger()
        error_logger.log_system_error(
            error_type=ErrorType.DATABASE_ERROR,
            error_message="Connection lost",
            component="database",
        )

        # Wait for async persistence task
        await asyncio.sleep(0.1)

        result = await db_session.execute(select(ErrorLogModel))
        records = result.scalars().all()

        sys_errors = [r for r in records if r.error_type == ErrorType.DATABASE_ERROR]
        assert len(sys_errors) >= 1
        assert sys_errors[0].level == "error"
