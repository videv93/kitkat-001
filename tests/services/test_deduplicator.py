"""Unit tests for SignalDeduplicator service.

Tests the in-memory deduplication logic with 60-second TTL window.
Covers AC1-AC5 from Story 1.5.
"""

from unittest.mock import patch

import pytest

from kitkat.services.deduplicator import SignalDeduplicator


class TestSignalDeduplicatorBasics:
    """Test basic deduplication functionality (AC1, AC2)."""

    def test_new_signal_not_duplicate(self):
        """AC1: First signal should return False (not a duplicate)."""
        dedup = SignalDeduplicator(ttl_seconds=60)
        result = dedup.is_duplicate("hash1")
        assert result is False

    def test_duplicate_within_window(self):
        """AC2: Second occurrence within 60s should return True."""
        dedup = SignalDeduplicator(ttl_seconds=60)
        dedup.is_duplicate("hash1")  # Add signal
        result = dedup.is_duplicate("hash1")  # Check duplicate
        assert result is True

    def test_different_signals_not_duplicates(self):
        """Different signal hashes should not be detected as duplicates."""
        dedup = SignalDeduplicator(ttl_seconds=60)
        dedup.is_duplicate("hash1")
        result = dedup.is_duplicate("hash2")
        assert result is False

    def test_multiple_different_signals(self):
        """Multiple different signals should each be stored independently."""
        dedup = SignalDeduplicator(ttl_seconds=60)
        # Add 5 different signals
        for i in range(5):
            result = dedup.is_duplicate(f"hash{i}")
            assert result is False

        # Verify each is now a duplicate
        for i in range(5):
            result = dedup.is_duplicate(f"hash{i}")
            assert result is True


class TestTTLCleanup:
    """Test TTL cleanup mechanism (AC3)."""

    @patch("time.time")
    def test_ttl_cleanup_removes_old_entries(self, mock_time):
        """AC3: Entries older than TTL should be removed from memory."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        # Add signal at time 100
        mock_time.return_value = 100.0
        result = dedup.is_duplicate("hash1")
        assert result is False

        # Check within window (120s later)
        mock_time.return_value = 120.0
        result = dedup.is_duplicate("hash1")
        assert result is True

        # Check after TTL (161s later - beyond 60s window)
        mock_time.return_value = 161.0
        result = dedup.is_duplicate("hash1")
        assert result is False  # Should be treated as new

    @patch("time.time")
    def test_same_payload_after_ttl(self, mock_time):
        """AC3: Same payload should be accepted as new after TTL expires."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        # First signal at t=0
        mock_time.return_value = 0.0
        result1 = dedup.is_duplicate("same_hash")
        assert result1 is False

        # Same signal at t=30 (within TTL)
        mock_time.return_value = 30.0
        result2 = dedup.is_duplicate("same_hash")
        assert result2 is True

        # Same signal at t=61 (after TTL)
        mock_time.return_value = 61.0
        result3 = dedup.is_duplicate("same_hash")
        assert result3 is False

    @patch("time.time")
    def test_cleanup_called_on_every_check(self, mock_time):
        """_cleanup() should be called on every is_duplicate() check."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        # Add multiple signals
        mock_time.return_value = 0.0
        dedup.is_duplicate("hash1")
        dedup.is_duplicate("hash2")
        dedup.is_duplicate("hash3")
        assert len(dedup._seen) == 3

        # Move time forward 61 seconds
        mock_time.return_value = 61.0
        # Cleanup happens on every call
        dedup.is_duplicate("hash_new")
        # Old entries should be removed
        assert len(dedup._seen) == 1


class TestMemorySafety:
    """Test memory safety and cleanup (AC4)."""

    @patch("time.time")
    def test_memory_bounded_with_many_signals(self, mock_time):
        """AC4: Memory should be bounded even with many signals."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        # Add 1000 signals over time
        mock_time.return_value = 0.0
        for i in range(500):
            dedup.is_duplicate(f"hash{i}")

        # Move to t=30 (within TTL for first batch)
        mock_time.return_value = 30.0
        for i in range(500, 1000):
            dedup.is_duplicate(f"hash{i}")

        # All 1000 should be in memory (within 60s window)
        assert len(dedup._seen) == 1000

        # Move to t=61 (first 500 should be expired)
        mock_time.return_value = 61.0
        dedup.is_duplicate("new_hash")

        # Only entries from t=30+ should remain (~500)
        assert len(dedup._seen) <= 501  # 500 + new_hash

    @patch("time.time")
    def test_no_memory_leak_after_cleanup(self, mock_time):
        """Verify memory cleanup reduces dict size properly."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        # Add 100 signals at t=0
        mock_time.return_value = 0.0
        for i in range(100):
            dedup.is_duplicate(f"hash{i}")
        size_before = len(dedup._seen)

        # Move to t=61 and trigger cleanup
        mock_time.return_value = 61.0
        dedup.is_duplicate("new")

        size_after = len(dedup._seen)
        # Should have removed most old entries
        assert size_after < size_before


class TestHashConsistency:
    """Test hash function consistency."""

    def test_same_signal_hash_consistency(self):
        """Same signal hash should be detected consistently."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        # Add same hash multiple times
        result1 = dedup.is_duplicate("abc123")
        result2 = dedup.is_duplicate("abc123")
        result3 = dedup.is_duplicate("abc123")

        assert result1 is False  # First occurrence
        assert result2 is True  # Second
        assert result3 is True  # Third


@pytest.mark.asyncio
class TestWebhookIntegration:
    """Integration tests for webhook endpoint with deduplicator."""

    async def test_duplicate_signal_returns_200_status(self):
        """AC2, AC5: Duplicate signal should return HTTP 200."""
        # This will be tested via integration tests in test_webhook.py
        pass

    async def test_duplicate_signal_no_database_write(self):
        """Duplicate signals should not create additional database records."""
        # Integration test - actual DB tested separately
        pass


class TestEdgeCases:
    """Edge case tests."""

    @patch("time.time")
    def test_boundary_exactly_at_ttl(self, mock_time):
        """Signal at TTL boundary - < operator means it's cleaned up at TTL."""
        dedup = SignalDeduplicator(ttl_seconds=60)

        mock_time.return_value = 0.0
        dedup.is_duplicate("hash1")

        # Exactly at 60s - (60 - 0) = 60, which is NOT < 60, so cleaned up
        mock_time.return_value = 60.0
        result = dedup.is_duplicate("hash1")
        assert result is False  # Expired (60 - 0 = 60, not < 60)

        # Just before TTL (59.9s)
        mock_time.return_value = 59.9
        dedup.is_duplicate("hash2")
        mock_time.return_value = 60.0
        result = dedup.is_duplicate("hash2")
        assert result is True  # Still valid (60 - 59.9 = 0.1 < 60)

    def test_empty_signal_hash(self):
        """Empty string should be handled as valid signal ID."""
        dedup = SignalDeduplicator(ttl_seconds=60)
        result1 = dedup.is_duplicate("")
        result2 = dedup.is_duplicate("")
        assert result1 is False
        assert result2 is True
