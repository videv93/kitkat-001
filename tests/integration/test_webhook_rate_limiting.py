"""Integration tests for rate limiting logic.

Tests the RateLimiter service with realistic usage patterns.
These tests focus on the rate limiting mechanism without requiring database setup.
"""

import time
from unittest.mock import patch

import pytest

from kitkat.services.rate_limiter import RateLimiter


class TestRateLimitingIntegration:
    """Integration tests for rate limiting scenarios."""

    def test_single_user_workflow(self):
        """Test complete workflow: requests, rate limit, reset."""
        limiter = RateLimiter(window_seconds=60, max_requests=10)
        token = "user_token"

        # Phase 1: Send 10 requests (should all succeed)
        allowed_count = 0
        for i in range(10):
            if limiter.is_allowed(token):
                allowed_count += 1

        assert allowed_count == 10, "All 10 requests should be allowed"

        # Phase 2: Send more requests (should be rate limited)
        retry_afters = []
        for i in range(5):
            if not limiter.is_allowed(token):
                retry_after = limiter.get_retry_after(token)
                retry_afters.append(retry_after)

        assert len(retry_afters) == 5, "All 5 additional requests should be rate limited"
        assert all(0 < ra <= 60 for ra in retry_afters), "Retry-After should be between 0 and 60"

    @patch("time.time")
    def test_multiple_users_concurrent_activity(self, mock_time):
        """Test multiple users with concurrent activity."""
        limiter = RateLimiter(window_seconds=60, max_requests=3)

        mock_time.return_value = 0.0

        users = {
            "user_a": "token_a",
            "user_b": "token_b",
            "user_c": "token_c",
        }

        # Each user sends 3 requests (should all succeed)
        for user, token in users.items():
            for i in range(3):
                assert limiter.is_allowed(token) is True, f"{user} request {i+1} should be allowed"

        # Each user tries 1 more request (should be rate limited)
        for user, token in users.items():
            assert (
                limiter.is_allowed(token) is False
            ), f"{user} 4th request should be rate limited"

    @patch("time.time")
    def test_burst_traffic_pattern(self, mock_time):
        """Test handling of burst traffic pattern."""
        limiter = RateLimiter(window_seconds=60, max_requests=10)
        token = "api_client"

        mock_time.return_value = 0.0

        # Simulate burst of 15 rapid requests
        results = []
        for i in range(15):
            allowed = limiter.is_allowed(token)
            results.append(allowed)

        # First 10 should be allowed, last 5 should be rejected
        assert sum(results[:10]) == 10, "First 10 requests should be allowed"
        assert sum(results[10:]) == 0, "Requests 11-15 should be rejected"

    @patch("time.time")
    def test_steady_request_rate(self, mock_time):
        """Test handling steady request rate within limits."""
        limiter = RateLimiter(window_seconds=60, max_requests=10)
        token = "steady_client"

        mock_time.return_value = 0.0

        # Send 1 request every 5 seconds for 120 seconds
        # Should never be rate limited (1 req/5s = 12/min, but window slides)
        allowed_count = 0
        blocked_count = 0

        for i in range(25):
            mock_time.return_value = i * 5.0
            if limiter.is_allowed(token):
                allowed_count += 1
            else:
                blocked_count += 1

        # Most should be allowed due to sliding window
        assert allowed_count > 10, f"Should allow most requests: {allowed_count} allowed"

    @patch("time.time")
    def test_retry_after_accuracy(self, mock_time):
        """Test Retry-After header accuracy."""
        limiter = RateLimiter(window_seconds=60, max_requests=2)
        token = "test_token"

        # Make 2 requests at t=0
        mock_time.return_value = 0.0
        limiter.is_allowed(token)
        limiter.is_allowed(token)

        # Check retry_after at various times
        mock_time.return_value = 0.0
        retry_0 = limiter.get_retry_after(token)
        assert retry_0 == 60, f"At t=0, retry_after should be 60, got {retry_0}"

        mock_time.return_value = 30.0
        retry_30 = limiter.get_retry_after(token)
        assert retry_30 == 30, f"At t=30, retry_after should be 30, got {retry_30}"

        mock_time.return_value = 59.0
        retry_59 = limiter.get_retry_after(token)
        assert retry_59 == 1, f"At t=59, retry_after should be 1, got {retry_59}"

    @patch("time.time")
    def test_window_sliding_behavior(self, mock_time):
        """Test sliding window behavior."""
        limiter = RateLimiter(window_seconds=60, max_requests=3)
        token = "sliding_token"

        # t=0: Make 3 requests
        mock_time.return_value = 0.0
        for _ in range(3):
            assert limiter.is_allowed(token) is True

        # t=0: 4th request should be blocked
        assert limiter.is_allowed(token) is False

        # t=20: Oldest request still in window, should still be blocked
        mock_time.return_value = 20.0
        assert limiter.is_allowed(token) is False

        # t=61: Oldest request (t=0) just expired, should be allowed again
        mock_time.return_value = 61.0
        assert limiter.is_allowed(token) is True

    def test_token_isolation_under_stress(self):
        """Test token isolation when many tokens exist."""
        limiter = RateLimiter(window_seconds=60, max_requests=5)

        # Create 50 tokens and send 5 requests each
        for token_id in range(50):
            token = f"token_{token_id}"

            # Each token should allow 5 requests
            for req in range(5):
                assert limiter.is_allowed(token) is True

            # 6th should be blocked
            assert limiter.is_allowed(token) is False

    @patch("time.time")
    def test_memory_efficiency_with_old_tokens(self, mock_time):
        """Test memory cleanup with old inactive tokens."""
        limiter = RateLimiter(window_seconds=60, max_requests=5)

        # Create tokens and send requests
        mock_time.return_value = 0.0
        for i in range(10):
            token = f"token_{i}"
            for _ in range(3):
                limiter.is_allowed(token)

        assert len(limiter._buckets) == 10, "Should have 10 tokens"

        # Move time forward and trigger cleanup
        mock_time.return_value = 70.0
        limiter.cleanup()

        # Old buckets should be removed
        assert len(limiter._buckets) == 0, "Old buckets should be cleaned up"

    def test_error_response_on_rate_limit(self):
        """Test error response structure when rate limited."""
        limiter = RateLimiter(max_requests=1)
        token = "limited_token"

        # First request allowed
        assert limiter.is_allowed(token) is True

        # Second request blocked
        assert limiter.is_allowed(token) is False

        # Get retry after value for error response
        retry_after = limiter.get_retry_after(token)
        assert isinstance(retry_after, int), "Retry-After should be an integer"
        assert retry_after > 0, "Retry-After should be positive"

    @patch("time.time")
    def test_complex_scenario_mixed_patterns(self, mock_time):
        """Test complex scenario with mixed traffic patterns."""
        limiter = RateLimiter(window_seconds=60, max_requests=10)

        # User A: Steady rate
        user_a_token = "user_a"
        # User B: Burst at start, then waits
        user_b_token = "user_b"

        mock_time.return_value = 0.0

        # User B burst: sends 10 requests at t=0
        for _ in range(10):
            assert limiter.is_allowed(user_b_token) is True
        assert limiter.is_allowed(user_b_token) is False  # Rate limited

        # User A steady: sends 5 requests at t=0
        for _ in range(5):
            assert limiter.is_allowed(user_a_token) is True

        # Move to t=30
        mock_time.return_value = 30.0

        # User A sends 5 more (total 10 in window)
        for _ in range(5):
            assert limiter.is_allowed(user_a_token) is True
        assert limiter.is_allowed(user_a_token) is False  # Rate limited

        # User B still rate limited (oldest request from t=0 still in window)
        assert limiter.is_allowed(user_b_token) is False

        # Move to t=65 - both should reset
        mock_time.return_value = 65.0

        # Both users should be able to send requests again
        assert limiter.is_allowed(user_a_token) is True
        assert limiter.is_allowed(user_b_token) is True
