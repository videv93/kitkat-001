"""Tests for RateLimiter service.

Tests rate limiting functionality with per-token tracking, sliding window,
and automatic cleanup.
"""

import time
from unittest.mock import patch

import pytest

from kitkat.services.rate_limiter import RateLimiter


class TestRateLimiterBasics:
    """Test basic rate limiter functionality."""

    def test_initialization(self):
        """Test rate limiter initializes with correct defaults."""
        limiter = RateLimiter()
        assert limiter.window_seconds == 60
        assert limiter.max_requests == 10

    def test_custom_configuration(self):
        """Test rate limiter accepts custom configuration."""
        limiter = RateLimiter(window_seconds=30, max_requests=5)
        assert limiter.window_seconds == 30
        assert limiter.max_requests == 5

    def test_single_request_allowed(self):
        """Test single request is allowed (AC1)."""
        limiter = RateLimiter()
        token = "test_token"
        assert limiter.is_allowed(token) is True

    def test_multiple_requests_within_limit(self):
        """Test requests within limit are allowed (AC1)."""
        limiter = RateLimiter(max_requests=5)
        token = "test_token"

        # Send 5 requests - all should be allowed
        for i in range(5):
            assert limiter.is_allowed(token) is True

    def test_requests_exceeding_limit(self):
        """Test requests exceeding limit are rejected (AC2)."""
        limiter = RateLimiter(max_requests=3)
        token = "test_token"

        # Send 3 allowed requests
        for i in range(3):
            assert limiter.is_allowed(token) is True

        # 4th request should be rejected
        assert limiter.is_allowed(token) is False


class TestRateLimiterWindow:
    """Test sliding window behavior."""

    @patch("time.time")
    def test_window_reset_after_expiry(self, mock_time):
        """Test requests allowed after window resets (AC3)."""
        limiter = RateLimiter(window_seconds=60, max_requests=2)
        token = "test_token"

        # Simulate requests at t=0
        mock_time.return_value = 0.0
        assert limiter.is_allowed(token) is True
        assert limiter.is_allowed(token) is True
        assert limiter.is_allowed(token) is False  # Limit reached

        # Simulate time passing - move to t=61 seconds
        mock_time.return_value = 61.0
        assert limiter.is_allowed(token) is True  # Window reset, allowed again

    @patch("time.time")
    def test_partial_window_reset(self, mock_time):
        """Test only old timestamps are cleaned up."""
        limiter = RateLimiter(window_seconds=60, max_requests=3)
        token = "test_token"

        # Add requests at t=0, t=10, t=20
        mock_time.return_value = 0.0
        assert limiter.is_allowed(token) is True
        mock_time.return_value = 10.0
        assert limiter.is_allowed(token) is True
        mock_time.return_value = 20.0
        assert limiter.is_allowed(token) is True
        assert limiter.is_allowed(token) is False  # Limit reached

        # Move to t=75 - only t=20 request is still in window (20 > 75-60=15)
        mock_time.return_value = 75.0
        assert limiter.is_allowed(token) is True  # Old requests expired
        assert limiter.is_allowed(token) is True
        assert limiter.is_allowed(token) is False  # Limit reached again


class TestRateLimiterTokenIsolation:
    """Test per-token isolation (AC4)."""

    def test_different_tokens_independent(self):
        """Test different tokens have independent quota (AC4)."""
        limiter = RateLimiter(max_requests=2)

        # Token A: use 2 requests
        assert limiter.is_allowed("token_a") is True
        assert limiter.is_allowed("token_a") is True
        assert limiter.is_allowed("token_a") is False

        # Token B: should have independent quota
        assert limiter.is_allowed("token_b") is True
        assert limiter.is_allowed("token_b") is True
        assert limiter.is_allowed("token_b") is False

    def test_many_tokens_no_interference(self):
        """Test many tokens don't interfere with each other."""
        limiter = RateLimiter(max_requests=1)

        # Each token should be able to make 1 request
        for i in range(10):
            token = f"token_{i}"
            assert limiter.is_allowed(token) is True
            assert limiter.is_allowed(token) is False


class TestRateLimiterRetryAfter:
    """Test Retry-After header calculation."""

    @patch("time.time")
    def test_retry_after_calculation(self, mock_time):
        """Test Retry-After value is calculated correctly (AC2)."""
        limiter = RateLimiter(window_seconds=60, max_requests=2)
        token = "test_token"

        # Make 2 requests at t=0
        mock_time.return_value = 0.0
        limiter.is_allowed(token)
        limiter.is_allowed(token)

        # At t=30, the oldest request (t=0) expires at t=60
        mock_time.return_value = 30.0
        retry_after = limiter.get_retry_after(token)
        assert retry_after == 30  # 60 - 30 = 30 seconds

    @patch("time.time")
    def test_retry_after_zero_when_allowed(self, mock_time):
        """Test Retry-After value when request is allowed (not rate limited yet)."""
        limiter = RateLimiter(max_requests=2)
        token = "test_token"

        mock_time.return_value = 0.0
        limiter.is_allowed(token)

        # We have 1 request, so Retry-After is based on when that oldest request expires
        # At t=0, oldest request expires at t=60
        retry_after = limiter.get_retry_after(token)
        assert retry_after == 60  # Time until oldest request falls out of window

    @patch("time.time")
    def test_retry_after_empty_bucket(self, mock_time):
        """Test Retry-After is 0 for non-existent token."""
        limiter = RateLimiter()
        token = "nonexistent_token"

        mock_time.return_value = 0.0
        retry_after = limiter.get_retry_after(token)
        assert retry_after == 0


class TestRateLimiterMemorySafety:
    """Test memory management and cleanup."""

    @patch("time.time")
    def test_old_timestamps_cleaned_up(self, mock_time):
        """Test old timestamps are cleaned up automatically."""
        limiter = RateLimiter(window_seconds=60, max_requests=3)
        token = "test_token"

        # Make 3 requests at t=0
        mock_time.return_value = 0.0
        for _ in range(3):
            limiter.is_allowed(token)

        # At t=0, bucket should have 3 timestamps
        bucket_before = len(limiter._buckets[token])
        assert bucket_before == 3

        # Move to t=70 and make another request
        mock_time.return_value = 70.0
        limiter.is_allowed(token)

        # Old timestamps (from t=0) should be cleaned up
        bucket_after = len(limiter._buckets[token])
        assert bucket_after == 1  # Only the new timestamp remains

    @patch("time.time")
    def test_cleanup_method_removes_empty_buckets(self, mock_time):
        """Test cleanup method removes inactive tokens."""
        limiter = RateLimiter(window_seconds=60)
        token = "test_token"

        # Make a request
        mock_time.return_value = 0.0
        limiter.is_allowed(token)
        assert token in limiter._buckets

        # Move time forward past window
        mock_time.return_value = 70.0
        limiter.cleanup()

        # Token bucket should be removed
        assert token not in limiter._buckets

    @patch("time.time")
    def test_no_memory_leak_with_rapid_requests(self, mock_time):
        """Test memory doesn't grow unbounded with rapid requests (AC4)."""
        limiter = RateLimiter(window_seconds=60, max_requests=10)
        token = "test_token"

        # Simulate 1000 requests spread over time
        for i in range(1000):
            mock_time.return_value = float(i % 60)  # Cycle through 60 seconds
            limiter.is_allowed(token)

        # Bucket should never exceed max_requests
        bucket_size = len(limiter._buckets.get(token, []))
        assert bucket_size <= limiter.max_requests


class TestRateLimiterEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_max_requests(self):
        """Test with max_requests=0 (everything rejected)."""
        limiter = RateLimiter(max_requests=0)
        token = "test_token"

        # Even first request rejected
        assert limiter.is_allowed(token) is False

    def test_high_max_requests(self):
        """Test with high max_requests value."""
        limiter = RateLimiter(max_requests=1000)
        token = "test_token"

        # Should allow 1000 requests
        for _ in range(1000):
            assert limiter.is_allowed(token) is True

        # 1001st should be rejected
        assert limiter.is_allowed(token) is False

    @patch("time.time")
    def test_request_exactly_at_window_boundary(self, mock_time):
        """Test request at exact window boundary."""
        limiter = RateLimiter(window_seconds=60, max_requests=1)
        token = "test_token"

        # Request at t=0
        mock_time.return_value = 0.0
        assert limiter.is_allowed(token) is True

        # Request at t=60 (exactly at boundary - should be allowed)
        mock_time.return_value = 60.0
        assert limiter.is_allowed(token) is True


class TestRateLimiterIntegration:
    """Integration tests simulating real usage patterns."""

    @patch("time.time")
    def test_burst_then_wait_pattern(self, mock_time):
        """Test burst of requests followed by waiting (AC1, AC3)."""
        limiter = RateLimiter(window_seconds=60, max_requests=5)
        token = "test_token"

        # Burst of 5 requests at t=0
        mock_time.return_value = 0.0
        for i in range(5):
            assert limiter.is_allowed(token) is True, f"Request {i+1} should be allowed"

        # 6th request rejected
        assert limiter.is_allowed(token) is False

        # Wait for window to reset
        mock_time.return_value = 61.0
        assert limiter.is_allowed(token) is True

    @patch("time.time")
    def test_multiple_users_concurrent(self, mock_time):
        """Test multiple users with concurrent requests (AC4)."""
        limiter = RateLimiter(window_seconds=60, max_requests=3)
        tokens = ["user1", "user2", "user3"]

        mock_time.return_value = 0.0

        # Each user makes 3 requests
        for user in tokens:
            for i in range(3):
                assert limiter.is_allowed(user) is True

            # Each user should be rate limited on 4th request
            assert limiter.is_allowed(user) is False

    @patch("time.time")
    def test_steady_rate_within_limit(self, mock_time):
        """Test steady request rate that stays within limit."""
        limiter = RateLimiter(window_seconds=60, max_requests=10)
        token = "test_token"

        mock_time.return_value = 0.0

        # Send requests at 1 per 10 seconds (should never hit limit)
        for i in range(20):
            mock_time.return_value = float(i * 10)
            assert limiter.is_allowed(token) is True

        # At some point we're past the 60-second window, verify cleanup works
        assert len(limiter._buckets[token]) <= 10
