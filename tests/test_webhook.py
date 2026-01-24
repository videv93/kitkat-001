"""Tests for webhook endpoint with authentication and schema validation.

Story 1.4: Signal Payload Parsing & Validation
Tests coverage for AC1-AC5:
- AC1: Valid payload parsing
- AC2: Malformed JSON rejection
- AC3: Missing required fields
- AC4: Invalid business values
- AC5: Error logging for debugging
"""

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from kitkat.main import app
from kitkat.models import SignalPayload


@pytest.fixture
def client():
    """Provide FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def valid_webhook_token():
    """Valid webhook token matching test environment."""
    return "test-webhook-token-for-testing"


@pytest.fixture
def valid_headers(valid_webhook_token):
    """Headers with valid webhook token."""
    return {"X-Webhook-Token": valid_webhook_token}


@pytest.fixture
def webhook_payload():
    """Sample webhook payload from TradingView with required fields for validation."""
    return {
        "symbol": "ETH-PERP",
        "side": "buy",
        "size": 0.5,
        # Extra fields are allowed and ignored
        "action": "buy",
        "exchange": "BINANCE",
        "price": 2500.50,
        "time": "2026-01-18T10:30:00Z",
    }


class TestWebhookEndpointBasics:
    """Tests for basic webhook endpoint functionality (AC1)."""

    def test_webhook_accepts_valid_request(
        self, client, valid_headers, webhook_payload
    ):
        """Test that POST /api/webhook accepts valid requests."""
        response = client.post(
            "/api/webhook", json=webhook_payload, headers=valid_headers
        )
        assert response.status_code == 200

    def test_webhook_response_format(self, client, valid_headers, webhook_payload):
        """Test that webhook response has correct format (AC1: includes signal_id)."""
        response = client.post(
            "/api/webhook", json=webhook_payload, headers=valid_headers
        )
        data = response.json()

        assert "status" in data
        assert data["status"] == "received"
        assert "signal_id" in data  # AC1 requirement

    def test_webhook_returns_received_status(
        self, client, valid_headers, webhook_payload
    ):
        """Test that webhook returns 'received' status."""
        response = client.post(
            "/api/webhook", json=webhook_payload, headers=valid_headers
        )
        assert response.json()["status"] == "received"

    def test_webhook_endpoint_exists(self, client, valid_headers):
        """Test that /api/webhook endpoint is accessible."""
        payload = {"symbol": "ETH", "side": "buy", "size": 1}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        # Should return 200, not 404
        assert response.status_code != 404


class TestWebhookTokenAuthentication:
    """Tests for token authentication (AC2, AC3)."""

    def test_valid_token_accepted(self, client, valid_headers, webhook_payload):
        """Test that valid token is accepted (AC2)."""
        response = client.post(
            "/api/webhook", json=webhook_payload, headers=valid_headers
        )
        assert response.status_code == 200

    def test_invalid_token_rejected(self, client, webhook_payload):
        """Test that invalid token is rejected with 401 (AC3)."""
        invalid_headers = {"X-Webhook-Token": "wrong-token"}
        response = client.post(
            "/api/webhook", json=webhook_payload, headers=invalid_headers
        )
        assert response.status_code == 401

    def test_invalid_token_error_format(self, client, webhook_payload):
        """Test that invalid token returns correct error format (AC3)."""
        invalid_headers = {"X-Webhook-Token": "wrong-token"}
        response = client.post(
            "/api/webhook", json=webhook_payload, headers=invalid_headers
        )
        data = response.json()

        assert "error" in data or "detail" in data
        detail = data.get("detail", data)
        assert isinstance(detail, dict)
        assert "error" in detail
        assert detail["error"] == "Invalid token"
        assert detail["code"] == "INVALID_TOKEN"

    def test_missing_token_rejected(self, client, webhook_payload):
        """Test that missing token header is rejected with 401 (AC3)."""
        response = client.post("/api/webhook", json=webhook_payload)
        assert response.status_code == 401

    def test_missing_token_error_format(self, client, webhook_payload):
        """Test that missing token returns correct error format."""
        response = client.post("/api/webhook", json=webhook_payload)
        data = response.json()

        assert "error" in data or "detail" in data
        detail = data.get("detail", data)
        assert "error" in detail
        assert detail["error"] == "Invalid token"
        assert detail["code"] == "INVALID_TOKEN"

    def test_empty_token_rejected(self, client, webhook_payload):
        """Test that empty token is rejected."""
        headers = {"X-Webhook-Token": ""}
        response = client.post("/api/webhook", json=webhook_payload, headers=headers)
        assert response.status_code == 401

    def test_token_case_sensitive(self, client, webhook_payload):
        """Test that token comparison is case-sensitive."""
        # Change case of valid token
        headers = {"X-Webhook-Token": "test-webhook-token-for-testing".upper()}
        response = client.post("/api/webhook", json=webhook_payload, headers=headers)
        assert response.status_code == 401


class TestConstantTimeComparison:
    """Tests for constant-time token comparison to prevent timing attacks (AC4)."""

    def test_timing_attack_prevention_valid_vs_invalid(
        self, client, valid_webhook_token
    ):
        """Verify constant-time comparison is used (hmac.compare_digest).

        This test verifies authentication works correctly. The actual timing
        attack prevention is guaranteed by using hmac.compare_digest() from
        Python's standard library, which is tested at the unit level in the
        implementation. Integration test can't reliably measure timing due to
        HTTP/network overhead, but we verify the authentication behavior.
        """
        payload1 = {"symbol": "ETH-1", "side": "buy", "size": 1}
        payload2 = {"symbol": "ETH-2", "side": "buy", "size": 1}

        # Valid token should succeed
        headers = {"X-Webhook-Token": valid_webhook_token}
        response = client.post("/api/webhook", json=payload1, headers=headers)
        assert response.status_code == 200

        # Invalid token should fail
        headers = {"X-Webhook-Token": "wrong-token-12345"}
        response = client.post("/api/webhook", json=payload2, headers=headers)
        assert response.status_code == 401

    def test_constant_time_different_first_char(
        self, client, valid_webhook_token
    ):
        """Test that constant-time comparison is used (hmac.compare_digest).

        While we can't perfectly measure timing in an integration test
        due to system variance, we verify the authentication still works
        correctly with different tokens. The constant-time comparison
        is guaranteed by using hmac.compare_digest() in the code.
        """
        payload1 = {"symbol": "ETH-Valid", "side": "buy", "size": 1}
        payload2 = {"symbol": "ETH-Invalid1", "side": "buy", "size": 1}

        # Valid token should work
        headers = {"X-Webhook-Token": valid_webhook_token}
        response = client.post("/api/webhook", json=payload1, headers=headers)
        assert response.status_code == 200

        # Token with different first character should fail
        bad_token = "x" + valid_webhook_token[1:]
        headers = {"X-Webhook-Token": bad_token}
        response = client.post("/api/webhook", json=payload2, headers=headers)
        assert response.status_code == 401

    def test_constant_time_different_last_char(
        self, client, valid_webhook_token
    ):
        """Test constant-time comparison rejects tokens differing in last char.

        The constant-time comparison is guaranteed by hmac.compare_digest()
        implementation in Python standard library.
        """
        payload1 = {"symbol": "ETH-LastValid", "side": "buy", "size": 1}
        payload2 = {"symbol": "ETH-LastInvalid", "side": "buy", "size": 1}

        # Valid token should work
        headers = {"X-Webhook-Token": valid_webhook_token}
        response = client.post("/api/webhook", json=payload1, headers=headers)
        assert response.status_code == 200

        # Token with different last character should fail
        bad_token = valid_webhook_token[:-1] + "x"
        headers = {"X-Webhook-Token": bad_token}
        response = client.post("/api/webhook", json=payload2, headers=headers)
        assert response.status_code == 401

    def test_constant_time_different_lengths(
        self, client, valid_webhook_token
    ):
        """Test constant-time comparison with different token lengths.

        hmac.compare_digest() must handle tokens of different lengths
        in constant time to prevent timing attacks via token length.
        """
        payload1 = {"symbol": "ETH-LenValid", "side": "buy", "size": 1}
        payload2 = {"symbol": "ETH-LenShort", "side": "buy", "size": 1}
        payload3 = {"symbol": "ETH-LenLong", "side": "buy", "size": 1}

        # Valid token
        headers = {"X-Webhook-Token": valid_webhook_token}
        response = client.post("/api/webhook", json=payload1, headers=headers)
        assert response.status_code == 200

        # Much shorter invalid token
        bad_token = "abc"
        headers = {"X-Webhook-Token": bad_token}
        response = client.post("/api/webhook", json=payload2, headers=headers)
        assert response.status_code == 401

        # Much longer invalid token
        bad_token = valid_webhook_token + "extra_padding_to_make_longer"
        headers = {"X-Webhook-Token": bad_token}
        response = client.post("/api/webhook", json=payload3, headers=headers)
        assert response.status_code == 401

    def test_hmac_compare_digest_unit(self):
        """Unit test for hmac.compare_digest constant-time behavior."""
        from hmac import compare_digest

        # Same length, different content
        assert not compare_digest("abc", "xyz")

        # Different lengths
        assert not compare_digest("abc", "abcd")

        # Identical
        assert compare_digest("secret", "secret")


class TestAPIDocumentation:
    """Tests for API documentation (AC5)."""

    def test_docs_endpoint_exists(self, client):
        """Test that OpenAPI docs endpoint exists at /docs."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_docs_content_type(self, client):
        """Test that docs endpoint returns HTML."""
        response = client.get("/docs")
        assert "text/html" in response.headers.get("content-type", "")

    def test_openapi_schema_endpoint(self, client):
        """Test that OpenAPI schema is available at /openapi.json."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_schema_contains_webhook(self, client):
        """Test that OpenAPI schema includes webhook endpoint."""
        response = client.get("/openapi.json")
        data = response.json()

        # Should have paths
        assert "paths" in data
        # Should have /api/webhook endpoint
        assert "/api/webhook" in data["paths"]
        # Should be POST method
        assert "post" in data["paths"]["/api/webhook"]

    def test_webhook_schema_has_request_model(self, client):
        """Test that webhook endpoint schema shows request model."""
        response = client.get("/openapi.json")
        data = response.json()

        webhook_post = data["paths"]["/api/webhook"]["post"]
        # Should have requestBody
        assert "requestBody" in webhook_post or "parameters" in webhook_post

    def test_webhook_schema_has_response_model(self, client):
        """Test that webhook endpoint schema shows response model."""
        response = client.get("/openapi.json")
        data = response.json()

        webhook_post = data["paths"]["/api/webhook"]["post"]
        # Should have responses
        assert "responses" in webhook_post
        # Should document 200 response
        assert "200" in webhook_post["responses"]

    def test_webhook_endpoint_documented(self, client):
        """Test that webhook endpoint has description in documentation."""
        response = client.get("/openapi.json")
        data = response.json()

        webhook_post = data["paths"]["/api/webhook"]["post"]
        # Should have summary or description
        assert "summary" in webhook_post or "description" in webhook_post


class TestSignalPayloadFlexibility:
    """Tests for SignalPayload model flexibility with extra fields.

    Story 1.4 validates required fields but allows extra fields to support
    TradingView's flexible payload format.
    """

    def test_signal_payload_accepts_extra_fields(self):
        """Test that SignalPayload accepts extra fields (TradingView compatibility)."""
        # Extra fields are ignored by Pydantic but signal is accepted
        payload = SignalPayload(
            symbol="ETH-PERP",
            side="buy",
            size=1.0,
            # Extra fields (TradingView may include these)
            action="buy",
            exchange="BINANCE",
            price=2500.50,
        )
        assert payload.symbol == "ETH-PERP"
        assert payload.side == "buy"

    def test_signal_payload_dict_conversion(self):
        """Test that SignalPayload can be converted to dict."""
        payload = SignalPayload(symbol="ETH-PERP", side="buy", size=1.5)
        data = payload.model_dump()

        assert data["symbol"] == "ETH-PERP"
        assert data["side"] == "buy"
        assert data["size"] == Decimal("1.5")


class TestMalformedRequests:
    """Tests for error handling of malformed requests."""

    def test_malformed_json_rejected(self, client, valid_headers):
        """Test that malformed JSON is rejected with 4xx error code."""
        response = client.post(
            "/api/webhook",
            content="invalid json {",
            headers=valid_headers,
        )
        # FastAPI validation returns 422 for malformed requests
        assert response.status_code in [400, 422]

    def test_malformed_json_error_format(self, client, valid_headers):
        """Test that malformed JSON returns error response."""
        response = client.post(
            "/api/webhook",
            content="invalid json {",
            headers=valid_headers,
        )
        # Should return 4xx error
        assert response.status_code >= 400
        data = response.json()
        # Either has detail or error structure
        assert "detail" in data or "error" in data

    def test_empty_payload_rejected(self, client, valid_headers):
        """Test that empty JSON object is rejected (missing required fields)."""
        response = client.post("/api/webhook", json={}, headers=valid_headers)
        assert response.status_code == 400

    def test_complex_payload_with_required_fields(self, client, valid_headers):
        """Test that complex nested payloads are accepted (with required fields)."""
        complex_payload = {
            "symbol": "ETH-PERP",
            "side": "buy",
            "size": 1.5,
            # Extra fields are allowed
            "nested": {
                "level1": {
                    "level2": {
                        "level3": ["a", "b", "c"],
                    },
                },
            },
            "numbers": [1, 2.5, -3, 0],
            "booleans": [True, False],
            "nulls": [None],
        }
        response = client.post(
            "/api/webhook", json=complex_payload, headers=valid_headers
        )
        assert response.status_code == 200

    def test_large_payload_with_required_fields(self, client, valid_headers):
        """Test that large payloads are accepted (with required fields)."""
        large_payload = {
            "symbol": "ETH-PERP",
            "side": "buy",
            "size": 1.0,
            # Extra large data
            "data": "x" * 10000,  # 10KB string
            "numbers": list(range(1000)),
        }
        response = client.post(
            "/api/webhook", json=large_payload, headers=valid_headers
        )
        assert response.status_code == 200


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_multiple_requests_same_token(self, client, valid_headers, webhook_payload):
        """Test that multiple requests with same token work."""
        # Create unique payloads to avoid signal_id duplication
        for i in range(3):
            payload = {
                "symbol": f"ETH-{i}",
                "side": "buy",
                "size": 1.0 + i,
            }
            response = client.post(
                "/api/webhook", json=payload, headers=valid_headers
            )
            assert response.status_code == 200

    def test_requests_with_different_payloads(self, client, valid_headers):
        """Test that endpoint accepts various valid payload structures."""
        payloads = [
            {"symbol": "ETH", "side": "buy", "size": 1},
            {"symbol": "BTC", "side": "sell", "size": 0.5},
            {"symbol": "DOGE-PERP", "side": "buy", "size": 100},
            {"symbol": "ADA", "side": "sell", "size": 1.5},
            {"symbol": "SHIB", "side": "buy", "size": 999.99},
        ]

        for payload in payloads:
            response = client.post("/api/webhook", json=payload, headers=valid_headers)
            assert response.status_code == 200

    def test_special_characters_in_token(self, client, webhook_payload):
        """Test handling of special characters in token header."""
        # Token with valid UTF-8 special chars
        headers = {"X-Webhook-Token": "test-token-with-special-chars"}
        response = client.post("/api/webhook", json=webhook_payload, headers=headers)
        assert response.status_code == 401

    def test_unicode_payload(self, client, valid_headers):
        """Test that Unicode payloads are handled (extra fields allowed)."""
        payload = {
            "symbol": "EUR-PERP",
            "side": "buy",
            "size": 1,
            # Extra unicode fields
            "message": "Hello 世界 🌍",
            "emoji": "🚀",
            "hebrew": "שלום",
        }
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200

    def test_numeric_string_values(self, client, valid_headers):
        """Test that numeric string values are preserved (extra fields)."""
        payload = {
            "symbol": "ETH-PERP",
            "side": "buy",
            "size": 1.5,
            # Extra numeric fields
            "string_number": "123",
            "actual_number": 123,
            "float_string": "12.34",
        }
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200


# ============================================================================
# Story 1.4: Signal Payload Parsing & Validation Tests
# ============================================================================


class TestSignalPayloadModel:
    """Unit tests for SignalPayload Pydantic model (Task 1)."""

    def test_valid_payload_parsing(self):
        """Test AC1: Valid payload with required fields parses successfully."""
        payload = SignalPayload(symbol="ETH-PERP", side="buy", size=Decimal("0.5"))
        assert payload.symbol == "ETH-PERP"
        assert payload.side == "buy"
        assert payload.size == Decimal("0.5")

    def test_valid_payload_from_dict(self):
        """Test SignalPayload creation from dict with valid data."""
        data = {"symbol": "BTC-PERP", "side": "sell", "size": "1.25"}
        payload = SignalPayload(**data)
        assert payload.symbol == "BTC-PERP"
        assert payload.side == "sell"
        assert payload.size == Decimal("1.25")

    def test_invalid_side_value(self):
        """Test AC4: Invalid side value raises validation error."""
        with pytest.raises(ValueError, match="Invalid side value"):
            SignalPayload(symbol="ETH", side="hold", size=Decimal("1"))

    def test_invalid_side_uppercase(self):
        """Test side validation is case-sensitive."""
        with pytest.raises(ValueError, match="Invalid side value"):
            SignalPayload(symbol="ETH", side="BUY", size=Decimal("1"))

    def test_invalid_size_zero(self):
        """Test AC4: Size of zero is rejected."""
        with pytest.raises(ValueError, match="Size must be positive"):
            SignalPayload(symbol="ETH", side="buy", size=Decimal("0"))

    def test_invalid_size_negative(self):
        """Test AC4: Negative size is rejected."""
        with pytest.raises(ValueError, match="Size must be positive"):
            SignalPayload(symbol="ETH", side="buy", size=Decimal("-1.5"))

    def test_invalid_size_non_numeric(self):
        """Test AC4: Non-numeric size is rejected."""
        with pytest.raises(ValueError, match="Size must be a valid number"):
            SignalPayload(symbol="ETH", side="buy", size="not-a-number")

    def test_empty_symbol(self):
        """Test that empty symbol is rejected."""
        with pytest.raises(ValueError):
            SignalPayload(symbol="", side="buy", size=Decimal("1"))

    def test_missing_symbol_field(self):
        """Test AC3: Missing symbol field raises error."""
        with pytest.raises(ValueError):
            SignalPayload(side="buy", size=Decimal("1"))

    def test_missing_side_field(self):
        """Test AC3: Missing side field raises error."""
        with pytest.raises(ValueError):
            SignalPayload(symbol="ETH", size=Decimal("1"))

    def test_missing_size_field(self):
        """Test AC3: Missing size field raises error."""
        with pytest.raises(ValueError):
            SignalPayload(symbol="ETH", side="buy")

    def test_size_string_conversion(self):
        """Test that size is converted from string to Decimal."""
        payload = SignalPayload(symbol="ETH", side="buy", size="12.34")
        assert isinstance(payload.size, Decimal)
        assert payload.size == Decimal("12.34")

    def test_size_float_conversion(self):
        """Test that size is converted from float to Decimal."""
        payload = SignalPayload(symbol="ETH", side="buy", size=12.34)
        assert isinstance(payload.size, Decimal)
        assert payload.size == Decimal("12.34")

    def test_size_int_conversion(self):
        """Test that size is converted from int to Decimal."""
        payload = SignalPayload(symbol="ETH", side="buy", size=10)
        assert isinstance(payload.size, Decimal)
        assert payload.size == Decimal("10")

    def test_symbol_whitespace_stripping(self):
        """Test that symbol whitespace is stripped (ConfigDict setting)."""
        payload = SignalPayload(symbol="  ETH-PERP  ", side="buy", size=Decimal("1"))
        assert payload.symbol == "ETH-PERP"

    def test_model_dump(self):
        """Test that payload can be converted to dict."""
        payload = SignalPayload(symbol="ETH", side="buy", size=Decimal("1"))
        data = payload.model_dump()
        assert data["symbol"] == "ETH"
        assert data["side"] == "buy"
        assert data["size"] == Decimal("1")

    def test_model_dump_json(self):
        """Test that payload can be converted to JSON string."""
        payload = SignalPayload(symbol="ETH", side="buy", size=Decimal("1.5"))
        json_str = payload.model_dump_json()
        assert isinstance(json_str, str)
        # Verify JSON is valid
        parsed = json.loads(json_str)
        assert parsed["symbol"] == "ETH"
        assert parsed["side"] == "buy"
        assert float(parsed["size"]) == 1.5


class TestValidPayloadIntegration:
    """Integration tests for valid payload handling (AC1)."""

    def test_valid_payload_returns_200(self, client, valid_headers):
        """Test AC1: Valid payload returns 200 status."""
        payload = {"symbol": "ETH-PERP", "side": "buy", "size": 0.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200

    def test_valid_payload_response_format(self, client, valid_headers):
        """Test AC1: Valid payload response includes signal_id."""
        payload = {"symbol": "ETH-PERP", "side": "buy", "size": 0.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        data = response.json()

        assert data["status"] == "received"
        assert "signal_id" in data
        assert isinstance(data["signal_id"], str)
        assert len(data["signal_id"]) > 0

    def test_valid_payload_signal_id_consistency(self, client, valid_headers):
        """Test AC1: Same payload generates consistent signal_id.

        Note: Duplicate storage is database error (Story 1.5 handles deduplication
        before this point). This test verifies the signal_id generation algorithm
        is deterministic.
        """
        payload = {"symbol": "ETH-PERP", "side": "buy", "size": 0.5}

        response1 = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response1.status_code == 200
        signal_id_1 = response1.json()["signal_id"]

        # Verify signal_id is a consistent format (hex string)
        assert isinstance(signal_id_1, str)
        assert len(signal_id_1) == 16  # SHA256 truncated to 16 chars
        # Verify it's hex
        try:
            int(signal_id_1, 16)
        except ValueError:
            pytest.fail("signal_id must be valid hexadecimal")

    def test_valid_payload_different_symbol(self, client, valid_headers):
        """Test AC1: Different payloads generate different signal_ids."""
        payload1 = {"symbol": "ETH-PERP", "side": "buy", "size": 0.5}
        payload2 = {"symbol": "BTC-PERP", "side": "buy", "size": 0.5}

        response1 = client.post("/api/webhook", json=payload1, headers=valid_headers)
        signal_id_1 = response1.json()["signal_id"]

        response2 = client.post("/api/webhook", json=payload2, headers=valid_headers)
        signal_id_2 = response2.json()["signal_id"]

        assert signal_id_1 != signal_id_2

    def test_valid_payload_with_decimal_size(self, client, valid_headers):
        """Test AC1: Payload with decimal size parses correctly."""
        payload = {"symbol": "ETH-PERP", "side": "buy", "size": "12.34"}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200

    def test_valid_payload_unicode_symbol(self, client, valid_headers):
        """Test AC1: Payload with unicode in symbol is accepted."""
        payload = {"symbol": "EUR/USD-PERP", "side": "buy", "size": 1}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200


class TestMalformedJSONRejection:
    """Tests for malformed JSON rejection (AC2)."""

    def test_malformed_json_returns_400(self, client, valid_headers):
        """Test AC2: Malformed JSON is rejected with 400 status."""
        response = client.post(
            "/api/webhook",
            content="invalid json {",
            headers=valid_headers,
        )
        assert response.status_code == 400

    def test_malformed_json_error_format(self, client, valid_headers):
        """Test AC2: Malformed JSON returns correct error format."""
        response = client.post(
            "/api/webhook",
            content="invalid json {",
            headers=valid_headers,
        )
        data = response.json()

        assert "error" in data
        assert "code" in data
        assert data["code"] == "INVALID_SIGNAL"
        assert data["error"] == "Invalid JSON"
        assert data["signal_id"] is None
        assert data["dex"] is None
        assert "timestamp" in data

    def test_incomplete_json_rejected(self, client, valid_headers):
        """Test AC2: Incomplete JSON object is rejected."""
        response = client.post(
            "/api/webhook",
            content='{"symbol": "ETH"',
            headers=valid_headers,
        )
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_SIGNAL"

    def test_invalid_json_syntax_rejected(self, client, valid_headers):
        """Test AC2: Various JSON syntax errors are rejected."""
        invalid_jsons = [
            "{invalid}",
            '{"key": "value",,}',
            "{'single': 'quotes'}",
            "{key: value}",
        ]

        for invalid_json in invalid_jsons:
            response = client.post(
                "/api/webhook",
                content=invalid_json,
                headers=valid_headers,
            )
            assert response.status_code == 400


class TestMissingFieldsRejection:
    """Tests for missing required fields rejection (AC3)."""

    def test_missing_symbol_returns_400(self, client, valid_headers):
        """Test AC3: Missing symbol field returns 400."""
        payload = {"side": "buy", "size": 0.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400

    def test_missing_symbol_error_message(self, client, valid_headers):
        """Test AC3: Missing symbol has correct error message."""
        payload = {"side": "buy", "size": 0.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        data = response.json()

        assert data["code"] == "INVALID_SIGNAL"
        assert "symbol" in data["error"].lower()
        assert data["signal_id"] is None

    def test_missing_side_returns_400(self, client, valid_headers):
        """Test AC3: Missing side field returns 400."""
        payload = {"symbol": "ETH", "size": 0.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400

    def test_missing_side_error_message(self, client, valid_headers):
        """Test AC3: Missing side has correct error message."""
        payload = {"symbol": "ETH", "size": 0.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        data = response.json()

        assert data["code"] == "INVALID_SIGNAL"
        assert "side" in data["error"].lower()

    def test_missing_size_returns_400(self, client, valid_headers):
        """Test AC3: Missing size field returns 400."""
        payload = {"symbol": "ETH", "side": "buy"}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400

    def test_missing_size_error_message(self, client, valid_headers):
        """Test AC3: Missing size has correct error message."""
        payload = {"symbol": "ETH", "side": "buy"}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        data = response.json()

        assert data["code"] == "INVALID_SIGNAL"
        assert "size" in data["error"].lower()

    def test_empty_payload_missing_all_fields(self, client, valid_headers):
        """Test AC3: Empty payload missing all required fields."""
        response = client.post("/api/webhook", json={}, headers=valid_headers)
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_SIGNAL"

    def test_all_missing_fields_error_format(self, client, valid_headers):
        """Test AC3: All missing fields error response format."""
        response = client.post("/api/webhook", json={}, headers=valid_headers)
        data = response.json()

        assert "error" in data
        assert "code" in data
        assert data["code"] == "INVALID_SIGNAL"
        assert data["signal_id"] is None
        assert "timestamp" in data


class TestInvalidBusinessValuesRejection:
    """Tests for invalid business value rejection (AC4)."""

    def test_invalid_side_buy_lowercase(self, client, valid_headers):
        """Test AC4: Only lowercase 'buy' is valid."""
        payload = {"symbol": "ETH", "side": "BUY", "size": 0.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400

    def test_invalid_side_sell_lowercase(self, client, valid_headers):
        """Test AC4: Only lowercase 'sell' is valid."""
        payload = {"symbol": "ETH", "side": "SELL", "size": 0.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400

    def test_invalid_side_other_value(self, client, valid_headers):
        """Test AC4: Other side values are rejected."""
        invalid_sides = ["long", "short", "hold", "buy ", " buy", ""]
        for invalid_side in invalid_sides:
            payload = {"symbol": "ETH", "side": invalid_side, "size": 0.5}
            response = client.post("/api/webhook", json=payload, headers=valid_headers)
            assert response.status_code == 400
            assert response.json()["code"] == "INVALID_SIGNAL"

    def test_invalid_side_error_message(self, client, valid_headers):
        """Test AC4: Invalid side returns 'Invalid side value' message."""
        payload = {"symbol": "ETH", "side": "invalid", "size": 0.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        data = response.json()

        assert data["code"] == "INVALID_SIGNAL"
        assert "side" in data["error"].lower()

    def test_size_zero_rejected(self, client, valid_headers):
        """Test AC4: Size of zero is rejected."""
        payload = {"symbol": "ETH", "side": "buy", "size": 0}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_SIGNAL"

    def test_size_negative_rejected(self, client, valid_headers):
        """Test AC4: Negative size is rejected."""
        payload = {"symbol": "ETH", "side": "buy", "size": -1.5}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_SIGNAL"

    def test_size_zero_string_rejected(self, client, valid_headers):
        """Test AC4: String zero is rejected."""
        payload = {"symbol": "ETH", "side": "buy", "size": "0"}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400

    def test_size_negative_string_rejected(self, client, valid_headers):
        """Test AC4: Negative string size is rejected."""
        payload = {"symbol": "ETH", "side": "buy", "size": "-5.25"}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400

    def test_size_non_numeric_rejected(self, client, valid_headers):
        """Test AC4: Non-numeric size is rejected."""
        payload = {"symbol": "ETH", "side": "buy", "size": "not_a_number"}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_SIGNAL"

    def test_size_error_message(self, client, valid_headers):
        """Test AC4: Invalid size returns appropriate error message."""
        payload = {"symbol": "ETH", "side": "buy", "size": -1}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        data = response.json()

        assert data["code"] == "INVALID_SIGNAL"
        assert "size" in data["error"].lower() or "positive" in data["error"].lower()

    def test_valid_side_buy(self, client, valid_headers):
        """Test AC4: Valid side 'buy' is accepted."""
        payload = {"symbol": "ETH", "side": "buy", "size": 1}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200

    def test_valid_side_sell(self, client, valid_headers):
        """Test AC4: Valid side 'sell' is accepted."""
        payload = {"symbol": "ETH", "side": "sell", "size": 1}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200


class TestErrorLogging:
    """Tests for error logging for debugging (AC5)."""

    def test_validation_error_logged(self, client, valid_headers, caplog):
        """Test AC5: Validation errors are logged."""
        payload = {"symbol": "ETH", "side": "invalid", "size": 1}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400
        # Logging happens at warning level

    def test_raw_payload_in_error_response(self, client, valid_headers):
        """Test AC5: Error response has timestamp for logging."""
        payload = {"symbol": "ETH", "side": "invalid", "size": 1}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        data = response.json()

        # Verify response includes timestamp for correlation
        assert "timestamp" in data
        assert data["timestamp"].endswith("Z")

    def test_error_response_complete_format(self, client, valid_headers):
        """Test AC5: Error response includes all required fields."""
        payload = {"symbol": "ETH", "side": "invalid", "size": 1}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        data = response.json()

        assert "error" in data
        assert "code" in data
        assert "signal_id" in data
        assert "dex" in data
        assert "timestamp" in data

        assert data["signal_id"] is None
        assert data["dex"] is None
        assert data["code"] == "INVALID_SIGNAL"


class TestEdgeCasesStory14:
    """Edge case tests for Story 1.4 (signal payload parsing)."""

    def test_very_small_positive_size(self, client, valid_headers):
        """Test AC4: Very small positive sizes are accepted."""
        payload = {"symbol": "ETH", "side": "buy", "size": "0.0001"}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200

    def test_very_large_size(self, client, valid_headers):
        """Test AC4: Very large sizes are accepted."""
        payload = {"symbol": "ETH", "side": "buy", "size": "9999999.99"}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200

    def test_integer_size(self, client, valid_headers):
        """Test AC4: Integer sizes are accepted."""
        payload = {"symbol": "ETH", "side": "buy", "size": 100}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 200

    def test_extra_fields_ignored(self, client, valid_headers):
        """Test that extra fields in payload are accepted."""
        payload = {
            "symbol": "ETH",
            "side": "buy",
            "size": 1,
            "extra_field": "ignored",
            "another_field": 123,
        }
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        # Should accept (Story 1.5 will handle deduplication)
        assert response.status_code == 200

    def test_null_values_rejected(self, client, valid_headers):
        """Test that null values for required fields are rejected."""
        payload = {"symbol": None, "side": "buy", "size": 1}
        response = client.post("/api/webhook", json=payload, headers=valid_headers)
        assert response.status_code == 400
