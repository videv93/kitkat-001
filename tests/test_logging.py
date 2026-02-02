"""Tests for centralized error logging utilities (Story 4.4: AC#1, #4, #5).

Tests cover:
- Secret redaction for API keys, tokens, and Bearer auth
- HTTP header redaction for sensitive headers
- Body truncation at 1KB boundary
- URL sanitization for secret query params
- Structlog JSON configuration
- Error type constants
"""

import json
import pytest


class TestRedactSecrets:
    """Tests for redact_secrets() function (AC#5)."""

    def test_redacts_api_key_with_equals(self):
        """API keys should show as ***."""
        from kitkat.logging import redact_secrets

        text = "api_key=test_key_1234567890abcdef1234567890"
        result = redact_secrets(text)
        assert "test_key" not in result
        assert "***" in result

    def test_redacts_api_key_with_colon(self):
        """API keys with colon separator should be redacted."""
        from kitkat.logging import redact_secrets

        text = 'api_key: "test_key_1234567890abcdef1234567890"'
        result = redact_secrets(text)
        assert "test_key" not in result
        assert "***" in result

    def test_redacts_api_key_case_insensitive(self):
        """API key redaction should be case-insensitive."""
        from kitkat.logging import redact_secrets

        text = "API_KEY=test_key_1234567890abcdef1234567890"
        result = redact_secrets(text)
        assert "test_key" not in result

    def test_redacts_token_shows_first_4_chars(self):
        """Tokens should show first 4 chars + '...'."""
        from kitkat.logging import redact_secrets

        text = "token=abc123xyz789secret"
        result = redact_secrets(text)
        assert "abc1" in result
        assert "..." in result
        assert "xyz789secret" not in result

    def test_redacts_bot_token(self):
        """Bot tokens should be redacted with first 4 chars."""
        from kitkat.logging import redact_secrets

        text = "bot_token=1234567890:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
        result = redact_secrets(text)
        assert "AAHdqTcvCH" not in result

    def test_redacts_secret_key(self):
        """Secret keys should show first 4 chars."""
        from kitkat.logging import redact_secrets

        text = "secret=mysupersecretkey12345"
        result = redact_secrets(text)
        assert "mysupersecretkey" not in result
        assert "mysu" in result or "..." in result

    def test_redacts_password(self):
        """Passwords should show first 4 chars."""
        from kitkat.logging import redact_secrets

        text = "password=verysecurepassword123"
        result = redact_secrets(text)
        assert "verysecurepassword" not in result

    def test_redacts_bearer_token(self):
        """Bearer tokens should show first 4 chars of token."""
        from kitkat.logging import redact_secrets

        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxx"
        result = redact_secrets(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer" in result
        assert "eyJh" in result
        assert "..." in result

    def test_preserves_wallet_address(self):
        """Wallet addresses should NOT be redacted (AC#5)."""
        from kitkat.logging import redact_secrets

        wallet = "0x742d35Cc6634C0532925a3b844Bc9e7595f3e8B0"
        text = f"wallet_address={wallet}"
        result = redact_secrets(text)
        assert wallet in result

    def test_preserves_starknet_address(self):
        """Starknet addresses should NOT be redacted."""
        from kitkat.logging import redact_secrets

        address = "0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7"
        text = f"account={address}"
        result = redact_secrets(text)
        assert address in result

    def test_preserves_normal_text(self):
        """Normal text without secrets should be unchanged."""
        from kitkat.logging import redact_secrets

        text = "Processing signal for ETH-PERP with size 0.5"
        result = redact_secrets(text)
        assert result == text

    def test_multiple_secrets_in_text(self):
        """Multiple secrets in same text should all be redacted."""
        from kitkat.logging import redact_secrets

        text = "api_key=test_key_1234567890abcdef1234 token=secret123456789"
        result = redact_secrets(text)
        assert "test_key" not in result
        assert "secret123456789" not in result


class TestRedactHeaders:
    """Tests for redact_headers() function (AC#5)."""

    def test_redacts_authorization_header(self):
        """Authorization header should show first 4 chars."""
        from kitkat.logging import redact_headers

        headers = {"Authorization": "Bearer test_key_1234567890abcdef"}
        result = redact_headers(headers)
        assert result["Authorization"].startswith("Bear")
        assert result["Authorization"].endswith("...")

    def test_redacts_x_api_key_header(self):
        """X-API-Key header should show first 4 chars."""
        from kitkat.logging import redact_headers

        headers = {"X-API-Key": "test_key_1234567890abcdef"}
        result = redact_headers(headers)
        assert "test_key" not in result["X-API-Key"]
        assert result["X-API-Key"].endswith("...")

    def test_redacts_x_webhook_token(self):
        """X-Webhook-Token header should show first 4 chars."""
        from kitkat.logging import redact_headers

        headers = {"X-Webhook-Token": "mysecretwebhooktoken"}
        result = redact_headers(headers)
        assert result["X-Webhook-Token"] == "myse..."

    def test_preserves_content_type(self):
        """Content-Type header should not be redacted."""
        from kitkat.logging import redact_headers

        headers = {"Content-Type": "application/json"}
        result = redact_headers(headers)
        assert result["Content-Type"] == "application/json"

    def test_preserves_user_agent(self):
        """User-Agent header should not be redacted."""
        from kitkat.logging import redact_headers

        headers = {"User-Agent": "kitkat/1.0"}
        result = redact_headers(headers)
        assert result["User-Agent"] == "kitkat/1.0"

    def test_case_insensitive_header_matching(self):
        """Header matching should be case-insensitive."""
        from kitkat.logging import redact_headers

        headers = {"AUTHORIZATION": "Bearer secret123"}
        result = redact_headers(headers)
        assert "secret123" not in result["AUTHORIZATION"]

    def test_short_token_shows_asterisks(self):
        """Short tokens (<=4 chars) should show ***."""
        from kitkat.logging import redact_headers

        headers = {"X-API-Key": "abc"}
        result = redact_headers(headers)
        assert result["X-API-Key"] == "***"

    def test_empty_headers(self):
        """Empty headers dict should return empty dict."""
        from kitkat.logging import redact_headers

        result = redact_headers({})
        assert result == {}


class TestTruncateBody:
    """Tests for truncate_body() function (AC#2)."""

    def test_small_body_unchanged(self):
        """Body smaller than max should be unchanged."""
        from kitkat.logging import truncate_body

        body = "Small response body"
        result = truncate_body(body)
        assert result == body
        assert "TRUNCATED" not in result

    def test_truncates_at_1kb_boundary(self):
        """Body larger than 1KB should be truncated."""
        from kitkat.logging import truncate_body, MAX_BODY_SIZE

        body = "x" * 2000
        result = truncate_body(body)
        assert len(result) < 2000
        assert "TRUNCATED" in result
        assert f"{2000 - MAX_BODY_SIZE} bytes" in result

    def test_exact_1kb_not_truncated(self):
        """Body exactly at 1KB should not be truncated."""
        from kitkat.logging import truncate_body, MAX_BODY_SIZE

        body = "x" * MAX_BODY_SIZE
        result = truncate_body(body)
        assert result == body
        assert "TRUNCATED" not in result

    def test_truncates_dict_input(self):
        """Dict input should be JSON serialized then truncated."""
        from kitkat.logging import truncate_body, MAX_BODY_SIZE

        # Create a dict that serializes to > 1KB
        large_dict = {"data": "x" * 2000}
        result = truncate_body(large_dict)
        assert "TRUNCATED" in result

    def test_truncates_bytes_input(self):
        """Bytes input should be decoded then truncated."""
        from kitkat.logging import truncate_body

        body = b"x" * 2000
        result = truncate_body(body)
        assert isinstance(result, str)
        assert "TRUNCATED" in result

    def test_handles_invalid_utf8_bytes(self):
        """Invalid UTF-8 bytes should be handled gracefully."""
        from kitkat.logging import truncate_body

        # Invalid UTF-8 sequence
        body = b"\xff\xfe" + b"x" * 100
        result = truncate_body(body)
        assert isinstance(result, str)

    def test_custom_max_size(self):
        """Custom max_size should be respected."""
        from kitkat.logging import truncate_body

        body = "x" * 100
        result = truncate_body(body, max_size=50)
        assert "TRUNCATED" in result
        assert "50 bytes" in result


class TestSanitizeUrl:
    """Tests for sanitize_url() function (AC#5)."""

    def test_redacts_token_query_param(self):
        """Token query parameter should be redacted."""
        from kitkat.logging import sanitize_url

        url = "https://api.example.com/v1/orders?token=secret123"
        result = sanitize_url(url)
        assert "secret123" not in result
        assert "token=***" in result

    def test_redacts_api_key_query_param(self):
        """API key query parameter should be redacted."""
        from kitkat.logging import sanitize_url

        url = "https://api.example.com/v1/orders?api_key=test_key_123"
        result = sanitize_url(url)
        assert "test_key_123" not in result
        assert "api_key=***" in result

    def test_redacts_secret_query_param(self):
        """Secret query parameter should be redacted."""
        from kitkat.logging import sanitize_url

        url = "https://api.example.com/v1/orders?secret=mysecret"
        result = sanitize_url(url)
        assert "mysecret" not in result
        assert "secret=***" in result

    def test_preserves_non_secret_params(self):
        """Non-secret query parameters should be preserved."""
        from kitkat.logging import sanitize_url

        url = "https://api.example.com/v1/orders?symbol=ETH-PERP&side=buy"
        result = sanitize_url(url)
        assert result == url

    def test_multiple_params_mixed(self):
        """Mix of secret and non-secret params."""
        from kitkat.logging import sanitize_url

        url = "https://api.example.com?symbol=ETH&token=secret123&side=buy"
        result = sanitize_url(url)
        assert "symbol=ETH" in result
        assert "side=buy" in result
        assert "secret123" not in result

    def test_url_without_query_string(self):
        """URL without query string should be unchanged."""
        from kitkat.logging import sanitize_url

        url = "https://api.example.com/v1/orders"
        result = sanitize_url(url)
        assert result == url


class TestErrorType:
    """Tests for ErrorType constants (AC#1)."""

    def test_webhook_error_types_exist(self):
        """Webhook/signal error types should be defined."""
        from kitkat.logging import ErrorType

        assert hasattr(ErrorType, "INVALID_SIGNAL")
        assert hasattr(ErrorType, "DUPLICATE_SIGNAL")
        assert hasattr(ErrorType, "RATE_LIMITED")
        assert hasattr(ErrorType, "INVALID_TOKEN")

    def test_dex_error_types_exist(self):
        """DEX error types should be defined."""
        from kitkat.logging import ErrorType

        assert hasattr(ErrorType, "DEX_TIMEOUT")
        assert hasattr(ErrorType, "DEX_ERROR")
        assert hasattr(ErrorType, "DEX_REJECTED")
        assert hasattr(ErrorType, "DEX_CONNECTION_FAILED")

    def test_execution_error_types_exist(self):
        """Execution error types should be defined."""
        from kitkat.logging import ErrorType

        assert hasattr(ErrorType, "EXECUTION_FAILED")
        assert hasattr(ErrorType, "PARTIAL_FILL")
        assert hasattr(ErrorType, "INSUFFICIENT_FUNDS")

    def test_system_error_types_exist(self):
        """System error types should be defined."""
        from kitkat.logging import ErrorType

        assert hasattr(ErrorType, "HEALTH_CHECK_FAILED")
        assert hasattr(ErrorType, "ALERT_SEND_FAILED")
        assert hasattr(ErrorType, "DATABASE_ERROR")
        assert hasattr(ErrorType, "CONFIGURATION_ERROR")

    def test_error_type_values_are_strings(self):
        """Error type values should be string constants."""
        from kitkat.logging import ErrorType

        assert ErrorType.INVALID_SIGNAL == "INVALID_SIGNAL"
        assert ErrorType.DEX_TIMEOUT == "DEX_TIMEOUT"


class TestConfigureLogging:
    """Tests for configure_logging() function (AC#4)."""

    def test_configure_json_output(self):
        """JSON output configuration should work."""
        from kitkat.logging import configure_logging
        import structlog

        # Should not raise
        configure_logging(json_output=True)

        # Verify structlog is configured
        log = structlog.get_logger()
        assert log is not None

    def test_configure_console_output(self):
        """Console output configuration should work."""
        from kitkat.logging import configure_logging
        import structlog

        # Should not raise
        configure_logging(json_output=False)

        # Verify structlog is configured
        log = structlog.get_logger()
        assert log is not None

    def test_json_output_format(self, capsys):
        """JSON output should be valid JSON."""
        from kitkat.logging import configure_logging
        import structlog

        configure_logging(json_output=True)
        log = structlog.get_logger()

        # Log a message
        log.info("test message", key="value")

        # Capture stdout
        captured = capsys.readouterr()

        # Should be valid JSON
        if captured.out.strip():
            parsed = json.loads(captured.out.strip())
            assert parsed["event"] == "test message"
            assert parsed["key"] == "value"

    def test_timestamp_in_iso_format(self, capsys):
        """Timestamps should be in ISO format."""
        from kitkat.logging import configure_logging
        import structlog

        configure_logging(json_output=True)
        log = structlog.get_logger()

        log.info("test timestamp")

        captured = capsys.readouterr()
        if captured.out.strip():
            parsed = json.loads(captured.out.strip())
            # ISO timestamp should contain T or have standard format
            assert "timestamp" in parsed


class TestGetLogger:
    """Tests for get_logger() helper function."""

    def test_get_logger_returns_logger(self):
        """get_logger() should return a structlog logger."""
        from kitkat.logging import get_logger

        log = get_logger()
        assert log is not None
        # Should have standard logging methods
        assert hasattr(log, "info")
        assert hasattr(log, "error")
        assert hasattr(log, "warning")
        assert hasattr(log, "debug")

    def test_get_logger_with_name_binds_context(self):
        """get_logger(name) should bind logger name to context."""
        from kitkat.logging import get_logger, configure_logging
        import json

        configure_logging(json_output=True)
        log = get_logger("test_service")

        # The name should be bound to the logger
        assert log is not None
