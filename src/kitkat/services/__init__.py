"""Business logic services."""

from kitkat.services.deduplicator import SignalDeduplicator
from kitkat.services.error_logger import ErrorLogger, get_error_logger
from kitkat.services.rate_limiter import RateLimiter
from kitkat.services.shutdown_manager import ShutdownManager
from kitkat.services.signal_processor import SignalProcessor
from kitkat.services.stats import StatsService

__all__ = [
    "SignalDeduplicator",
    "ErrorLogger",
    "get_error_logger",
    "RateLimiter",
    "ShutdownManager",
    "SignalProcessor",
    "StatsService",
]
