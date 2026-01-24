"""Signal deduplication service with TTL-based cleanup.

Implements in-memory deduplication for TradingView webhook signals.
Detects duplicate signals within a 60-second window and prevents
duplicate trade execution.

Story 1.5: Signal Deduplication
"""

import time
from typing import Dict


class SignalDeduplicator:
    """In-memory deduplication service with TTL cleanup.

    Stores signal hashes and tracks timestamps for TTL-based expiration.
    Prevents the same signal from executing multiple times within a
    60-second window while allowing legitimate repeats after TTL expires.

    AC1: Generates unique signal hash and marks as seen
    AC2: Detects duplicates within 60-second window
    AC3: Automatically cleans up expired entries
    AC4: Prevents unbounded memory growth
    AC5: Returns idempotent responses
    """

    def __init__(self, ttl_seconds: int = 60):
        """Initialize the deduplicator with TTL window.

        Args:
            ttl_seconds: Time-to-live in seconds for signal tracking (default 60)
        """
        self._seen: Dict[str, float] = {}  # signal_id -> timestamp when first seen
        self._ttl = ttl_seconds

    def is_duplicate(self, signal_id: str) -> bool:
        """Check if signal is a duplicate and mark as seen if new.

        Side effect: Adds new signals to the deduplication cache.
        Automatically cleans up expired entries before checking.

        AC1: New signals return False
        AC2: Duplicates within TTL return True
        AC3: Expired entries are removed before checking

        Args:
            signal_id: SHA256 hash from generate_signal_hash()
                      (typically 16 hex characters)

        Returns:
            True if signal was seen within TTL window (duplicate),
            False if signal is new or TTL has expired
        """
        self._cleanup()

        if signal_id in self._seen:
            return True  # Already seen within TTL

        # Mark as seen at current time
        self._seen[signal_id] = time.time()
        return False

    def _cleanup(self) -> None:
        """Remove expired entries from the deduplication cache.

        AC3: Removes entries older than TTL seconds
        AC4: Prevents unbounded memory growth

        Entries are considered expired if the time elapsed since they were
        added exceeds the TTL window. Uses simple dict comprehension for
        efficient cleanup.

        Time complexity: O(n) where n = number of tracked signals
        Space complexity: O(n)
        """
        now = time.time()
        self._seen = {
            signal_id: timestamp
            for signal_id, timestamp in self._seen.items()
            if (now - timestamp) < self._ttl
        }
