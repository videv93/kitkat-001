"""Integration tests for webhook deduplication (Story 1.5).

Tests the webhook endpoint's integration with SignalDeduplicator.
Covers AC1-AC5 from Story 1.5.

Note: These are basic integration tests that verify the deduplicator
works correctly with the webhook endpoint. Full end-to-end tests with
database and FastAPI client would require additional fixtures.
"""

from decimal import Decimal
from unittest.mock import patch

from kitkat.api.webhook import generate_signal_hash
from kitkat.models import SignalPayload
from kitkat.services.deduplicator import SignalDeduplicator


class TestWebhookDeduplicationIntegration:
    """Integration tests for webhook deduplication with real models."""

    def test_signal_hash_consistency_enables_deduplication(self):
        """Verify that generate_signal_hash creates consistent hashes."""
        payload = SignalPayload(symbol="BTC/USDT", side="buy", size=Decimal("1.5"))
        payload_json = payload.model_dump_json()

        # Same payload should produce same hash
        hash1 = generate_signal_hash(payload_json)
        hash2 = generate_signal_hash(payload_json)

        assert hash1 == hash2
        assert len(hash1) == 16  # Should be truncated

    def test_whitespace_stripped_payload_same_hash(self):
        """AC1: SignalPayload strips whitespace, enabling duplicate detection."""
        # Create two payloads - one with whitespace, one without
        payload_normal = SignalPayload(
            symbol="BTC/USDT", side="buy", size=Decimal("1.0")
        )
        # The second payload will have whitespace stripped by Pydantic
        # Note: side validation happens before str_strip, so we need valid side
        payload_with_spaces = SignalPayload(
            symbol=" BTC/USDT ", side="buy", size=Decimal("1.0")
        )

        # Both should serialize to identical JSON due to str_strip_whitespace on symbol
        hash1 = generate_signal_hash(payload_normal.model_dump_json())
        hash2 = generate_signal_hash(payload_with_spaces.model_dump_json())

        assert hash1 == hash2

    def test_different_payloads_different_hashes(self):
        """Different payloads produce different hashes."""
        payload1 = SignalPayload(symbol="BTC/USDT", side="buy", size=Decimal("1.0"))
        payload2 = SignalPayload(symbol="BTC/USDT", side="sell", size=Decimal("1.0"))

        hash1 = generate_signal_hash(payload1.model_dump_json())
        hash2 = generate_signal_hash(payload2.model_dump_json())

        assert hash1 != hash2

    def test_deduplicator_rejects_duplicate_signal_hashes(self):
        """AC2: Deduplicator detects duplicate signal hashes."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        payload = SignalPayload(symbol="BTC/USDT", side="buy", size=Decimal("1.0"))
        signal_hash = generate_signal_hash(payload.model_dump_json())

        # First occurrence
        result1 = dedup.is_duplicate(signal_hash)
        assert result1 is False

        # Duplicate
        result2 = dedup.is_duplicate(signal_hash)
        assert result2 is True

    def test_webhook_flow_new_signal(self):
        """Simulate webhook flow for new signal (without FastAPI client)."""
        # Initialize deduplicator
        dedup = SignalDeduplicator(ttl_seconds=60)

        # Create payload
        payload = SignalPayload(symbol="BTC/USDT", side="buy", size=Decimal("1.0"))
        signal_hash = generate_signal_hash(payload.model_dump_json())

        # Check for duplicate (should be False for new signal)
        is_dup = dedup.is_duplicate(signal_hash)
        assert is_dup is False

        # Store would happen here in real webhook
        # Verify same hash is now duplicate
        is_dup2 = dedup.is_duplicate(signal_hash)
        assert is_dup2 is True

    def test_webhook_flow_duplicate_signal(self):
        """Simulate webhook flow for duplicate signal."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        payload = SignalPayload(symbol="ETH/USDT", side="sell", size=Decimal("10.0"))
        signal_hash = generate_signal_hash(payload.model_dump_json())

        # First check
        assert dedup.is_duplicate(signal_hash) is False

        # Second check (duplicate)
        assert dedup.is_duplicate(signal_hash) is True

        # Response should be status="duplicate" with same signal_id
        # (verified in unit tests)

    @patch("time.time")
    def test_webhook_flow_ttl_expiry(self, mock_time):
        """AC3: After TTL, same payload accepted as new."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        payload = SignalPayload(symbol="SOL/USDT", side="buy", size=Decimal("100.0"))
        signal_hash = generate_signal_hash(payload.model_dump_json())

        # Signal at t=0
        mock_time.return_value = 0.0
        assert dedup.is_duplicate(signal_hash) is False

        # Duplicate at t=30
        mock_time.return_value = 30.0
        assert dedup.is_duplicate(signal_hash) is True

        # After TTL at t=61
        mock_time.return_value = 61.0
        assert dedup.is_duplicate(signal_hash) is False  # Treated as new

    def test_multiple_concurrent_different_signals(self):
        """Multiple different signals don't interfere with each other."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        payloads = [
            SignalPayload(symbol="BTC/USDT", side="buy", size=Decimal("1.0")),
            SignalPayload(symbol="ETH/USDT", side="buy", size=Decimal("10.0")),
            SignalPayload(symbol="SOL/USDT", side="sell", size=Decimal("100.0")),
        ]

        hashes = [generate_signal_hash(p.model_dump_json()) for p in payloads]

        # All new
        for h in hashes:
            assert dedup.is_duplicate(h) is False

        # All duplicates
        for h in hashes:
            assert dedup.is_duplicate(h) is True


class TestWebhookResponseFormats:
    """Test response format consistency (AC5)."""

    def test_received_response_format(self):
        """Verify response format for new signals."""
        # This would be tested with actual FastAPI client in full integration
        # For now, verify the Pydantic model
        from kitkat.api.webhook import WebhookResponse

        response = WebhookResponse(status="received", signal_id="abc123")
        assert response.status == "received"
        assert response.signal_id == "abc123"
        assert response.code is None

    def test_duplicate_response_format(self):
        """Verify response format for duplicate signals."""
        from kitkat.api.webhook import WebhookResponse

        response = WebhookResponse(
            status="duplicate", signal_id="abc123", code="DUPLICATE_SIGNAL"
        )
        assert response.status == "duplicate"
        assert response.signal_id == "abc123"
        assert response.code == "DUPLICATE_SIGNAL"

    def test_response_always_includes_signal_id(self):
        """AC5: Both response types include signal_id."""
        from kitkat.api.webhook import WebhookResponse

        response1 = WebhookResponse(status="received", signal_id="xyz789")
        assert response1.signal_id == "xyz789"

        response2 = WebhookResponse(status="duplicate", signal_id="xyz789")
        assert response2.signal_id == "xyz789"
