"""Webhook endpoint for receiving TradingView signals."""

import hashlib
from datetime import datetime, timezone
from hmac import compare_digest
from typing import Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import get_db_session, verify_webhook_token, get_signal_processor, check_shutdown
from kitkat.config import get_settings
from kitkat.models import Signal, SignalPayload, SignalProcessorResponse
from kitkat.services import SignalDeduplicator
from kitkat.services.signal_processor import SignalProcessor
from kitkat.services.rate_limiter import RateLimiter
from kitkat.services.user_service import UserService

logger = structlog.get_logger()

# Display length for wallet addresses in logs
WALLET_ADDRESS_DISPLAY_LENGTH = 10

# Router for webhook endpoints
router = APIRouter(prefix="/api", tags=["webhook"])


class WebhookResponse(BaseModel):
    """Response for webhook reception (received or duplicate)."""

    status: Literal["received", "duplicate"]
    signal_id: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str
    code: Literal["INVALID_TOKEN", "INVALID_SIGNAL", "RATE_LIMITED"]
    signal_id: None = None
    dex: None = None
    timestamp: str


def generate_signal_hash(payload_json: str) -> str:
    """Generate unique signal ID using SHA256(payload + timestamp_minute).

    This creates a deterministic hash that enables deduplication.
    The timestamp_minute is included to support deduplication.

    Args:
        payload_json: JSON string of the payload

    Returns:
        Truncated SHA256 hex hash (16 characters)
    """
    now = datetime.now(timezone.utc)
    timestamp_minute = now.replace(second=0, microsecond=0, tzinfo=None).isoformat()

    hash_input = f"{payload_json}:{timestamp_minute}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


@router.post("/webhook", response_model=SignalProcessorResponse, dependencies=[Depends(check_shutdown)])
async def webhook_handler(
    request: Request,
    payload: SignalPayload,
    token: str = Depends(verify_webhook_token),
    db: AsyncSession = Depends(get_db_session),
    signal_processor: SignalProcessor = Depends(get_signal_processor),
) -> SignalProcessorResponse | JSONResponse:
    """Receive, validate, deduplicate, rate-limit, and process TradingView webhook signal.

    Validates payload structure and business rules. Detects duplicates within
    60-second window and rejects them idempotently. Rate limits to 10 signals
    per minute per token. New, non-rate-limited signals are stored and then
    processed through SignalProcessor for parallel execution on all active DEX adapters.

    Story 1.4: Signal Payload Parsing & Validation
    - AC1: Valid payload returns signal_id
    - AC2-4: Invalid payload returns 400 with error code
    - AC5: Raw payload logged on error

    Story 1.5: Signal Deduplication
    - AC1: Unique signal hash generated
    - AC2: Duplicates within 60s detected and rejected
    - AC3: TTL cleanup prevents memory leaks
    - AC4: Memory safely bounded
    - AC5: Idempotent response for duplicates

    Story 1.6: Rate Limiting
    - AC1: Up to 10 signals per minute accepted
    - AC2: 11th+ signals rejected with 429
    - AC3: Window resets after 60 seconds
    - AC4: Per-token isolation
    - AC5: Duplicates don't count toward rate limit

    Story 2.4: Webhook URL Generation
    - AC3: Token-based authentication for user-specific webhooks
    - AC4: Invalid token returns 401
    - AC6: User association with signal

    Story 2.9: Signal Processor & Fan-Out
    - AC1: Signal routed to active DEX adapters
    - AC2: Parallel execution via asyncio.gather with 30s timeout
    - AC5: Per-DEX response format returned with total_latency_ms

    Args:
        request: FastAPI request for accessing raw body if needed
        payload: Validated SignalPayload from Pydantic model
        token: Verified webhook token from X-Webhook-Token header or ?token query param
        db: AsyncSession for database operations
        signal_processor: SignalProcessor dependency for parallel DEX execution

    Returns:
        SignalProcessorResponse with per-DEX execution results and overall status,
        or JSONResponse with 429 for rate limit exceeded

    Raises:
        HTTPException: 400 for validation errors, 401 for invalid token
    """
    # Story 2.4: Check if this is a user-specific webhook token (not X-Webhook-Token)
    # If token is not the system token, validate it against user webhook tokens
    settings = get_settings()
    is_user_webhook = False
    user_id: Optional[int] = None

    # Try to find user by webhook token (Story 2.4: AC3)
    if not compare_digest(token, settings.webhook_token):
        # This is a user webhook token, not the system token
        is_user_webhook = True
        user_service = UserService(db)
        user = await user_service.get_user_by_webhook_token(token)
        if not user:
            raise HTTPException(
                status_code=401,
                detail={"error": "Invalid token", "code": "INVALID_TOKEN"},
            )
        user_id = user.id
        log_user = user.wallet_address[:WALLET_ADDRESS_DISPLAY_LENGTH]
    else:
        log_user = "system"

    # Generate signal_id hash from payload (Story 1.4)
    payload_json = payload.model_dump_json()
    signal_id = generate_signal_hash(payload_json)

    # Get deduplicator from app state (initialized in lifespan)
    # Handle case where deduplicator might not be initialized (e.g., in tests)
    deduplicator: SignalDeduplicator | None = getattr(
        request.app.state, "deduplicator", None
    )

    # Check for duplicates (Story 1.5, AC2, AC5)
    # Duplicates don't count toward rate limit (Story 1.6, AC5)
    # Return idempotent response for duplicates per AC5
    # Return SignalProcessorResponse with empty results (already processed)
    if deduplicator is not None and deduplicator.is_duplicate(signal_id):
        log = logger.bind(
            signal_id=signal_id,
            side=payload.side,
            symbol=payload.symbol,
            user=log_user,
            user_id=user_id,
        )
        log.info("webhook_duplicate_signal_detected")
        # Return idempotent response: signal was already processed
        return SignalProcessorResponse(
            signal_id=signal_id,
            overall_status="success",  # Idempotent - already processed
            results=[],
            total_dex_count=0,
            successful_count=0,
            failed_count=0,
            timestamp=datetime.now(timezone.utc),
        )

    # Get rate limiter from app state (Story 1.6)
    rate_limiter: RateLimiter | None = getattr(
        request.app.state, "rate_limiter", None
    )

    # Check rate limit (Story 1.6, AC2)
    # Rate limit check happens AFTER deduplication, so duplicates don't count
    if rate_limiter and not rate_limiter.is_allowed(token):
        retry_after = rate_limiter.get_retry_after(token)
        log = logger.bind(
            signal_id=signal_id,
            side=payload.side,
            symbol=payload.symbol,
            user=log_user,
            user_id=user_id,
        )
        log.warning(
            "webhook_rate_limited",
            retry_after_seconds=retry_after,
            payload=payload_json,
        )

        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "code": "RATE_LIMITED",
                "signal_id": signal_id,
                "dex": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            headers={"Retry-After": str(retry_after)},
        )

    # New signal - store in database
    # Convert Decimal to float for JSON serialization
    payload_dict = payload.model_dump()
    payload_dict["size"] = float(payload_dict["size"])
    signal_record = Signal(
        signal_id=signal_id,
        payload=payload_dict,
        received_at=datetime.now(timezone.utc),
    )
    db.add(signal_record)
    await db.commit()

    # Log signal received
    log = logger.bind(
        signal_id=signal_id,
        side=payload.side,
        symbol=payload.symbol,
        user=log_user,
        user_id=user_id,
    )
    log.info("webhook_signal_received")

    # Get shutdown manager for in-flight tracking (Story 2.11)
    shutdown_manager = getattr(request.app.state, "shutdown_manager", None)

    # Story 2.9: Process signal through all active DEX adapters in parallel
    # Story 2.11: Track in-flight orders for graceful shutdown
    # Returns per-DEX execution results and overall status
    try:
        if shutdown_manager:
            async with shutdown_manager.track_in_flight(signal_id):
                response = await signal_processor.process_signal(payload, signal_id)
        else:
            # Fallback for tests without shutdown manager
            response = await signal_processor.process_signal(payload, signal_id)

        # TODO (Story 4.2): Trigger alerts on execution failures
        # if response.overall_status == "failed":
        #     await alert_service.send_alert(signal_id, response)

        return response
    except Exception as e:
        # Log execution service failure but return partial response
        log = logger.bind(
            signal_id=signal_id,
            side=payload.side,
            symbol=payload.symbol,
            user=log_user,
            user_id=user_id,
        )
        log.error("Signal processing failed", error=str(e))
        # Return failed response with context for debugging
        return SignalProcessorResponse(
            signal_id=signal_id,
            overall_status="failed",
            results=[],
            total_dex_count=0,
            successful_count=0,
            failed_count=0,
            timestamp=datetime.now(timezone.utc),
        )
