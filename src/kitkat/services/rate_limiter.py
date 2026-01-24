"""Rate limiter for webhook requests.

Implements per-token rate limiting with a sliding window approach.
Tracks up to 10 requests per 60-second window per webhook token.
"""

import time
from collections import defaultdict
from typing import Dict, List

import structlog

logger = structlog.get_logger()


class RateLimiter:
    """Rate limiter with per-token request tracking using sliding window."""

    def __init__(self, window_seconds: int = 60, max_requests: int = 10):
        """Initialize rate limiter.

        Args:
            window_seconds: Time window for rate limiting in seconds (default: 60)
            max_requests: Max requests allowed in the window (default: 10)
        """
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        # token -> [timestamp1, timestamp2, ...]
        self._buckets: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, token: str) -> bool:
        """Check if request is allowed for the given token.

        Performs automatic cleanup of old timestamps and updates the bucket.

        Args:
            token: Webhook token to rate limit on

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        now = time.time()
        bucket = self._buckets[token]

        # Clean up old timestamps (older than window_seconds)
        cutoff_time = now - self.window_seconds
        self._buckets[token] = [ts for ts in bucket if ts > cutoff_time]

        # Check if limit exceeded
        if len(self._buckets[token]) >= self.max_requests:
            log = logger.bind(token=token[:4] + "...")
            log.warning(
                "rate_limit_exceeded",
                window_seconds=self.window_seconds,
                max_requests=self.max_requests,
                current_count=len(self._buckets[token]),
            )
            return False

        # Add current timestamp
        self._buckets[token].append(now)
        return True

    def get_retry_after(self, token: str) -> int:
        """Calculate seconds until rate limit window resets.

        Args:
            token: Webhook token to check

        Returns:
            Seconds until quota resets (0 if no limit active)
        """
        now = time.time()
        bucket = self._buckets.get(token, [])

        if not bucket:
            return 0

        # Clean up old timestamps first
        cutoff_time = now - self.window_seconds
        bucket = [ts for ts in bucket if ts > cutoff_time]

        if not bucket:
            return 0

        # Find oldest timestamp and calculate when it falls out of window
        oldest_timestamp = min(bucket)
        reset_time = oldest_timestamp + self.window_seconds
        retry_after = max(0, int(reset_time - now))

        return retry_after

    def cleanup(self) -> None:
        """Perform cleanup of expired tokens (optional manual cleanup).

        Removes buckets that have no active timestamps.
        Usually not needed as cleanup happens per-request, but useful for testing.
        """
        now = time.time()
        cutoff_time = now - self.window_seconds

        # Remove buckets with no recent timestamps
        tokens_to_remove = []
        for token, bucket in self._buckets.items():
            active_bucket = [ts for ts in bucket if ts > cutoff_time]
            if not active_bucket:
                tokens_to_remove.append(token)

        for token in tokens_to_remove:
            del self._buckets[token]

        if tokens_to_remove:
            logger.debug("rate_limiter_cleanup", removed_tokens=len(tokens_to_remove))
