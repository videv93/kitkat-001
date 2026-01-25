"""Webhook endpoint for receiving TradingView signals."""

import hashlib
from datetime import datetime
from hmac import compare_digest
from typing import Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import get_db_session, verify_webhook_token
from kitkat.config import get_settings
from kitkat.models import Signal, SignalPayload
from kitkat.services import SignalDeduplicator
from kitkat.services.rate_limiter import RateLimiter
from kitkat.services.user_service import UserService

logger = structlog.get_logger()

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
    now = datetime.utcnow()
    timestamp_minute = now.replace(second=0, microsecond=0).isoformat()

    hash_input = f"{payload_json}:{timestamp_minute}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


@router.post("/webhook", response_model=WebhookResponse)
async def webhook_handler(
    request: Request,
    payload: SignalPayload,
    token: str = Depends(verify_webhook_token),
    db: AsyncSession = Depends(get_db_session),
) -> WebhookResponse | JSONResponse:
    """Receive, validate, deduplicate, and rate-limit TradingView webhook signal.

    Validates payload structure and business rules. Detects duplicates within
    60-second window and rejects them idempotently. Rate limits to 10 signals
    per minute per token. Only new, non-rate-limited signals are stored and
    processed further.

    Story 1.4: Signal Payload Parsing & Validation
    - AC1: Valid payload returns signal_id
    - AC2-4: Invalid payload returns 400 with error code
    - AC5: Raw payload logged on error

    Story 1.5: Signal Deduplication
    - AC1: Unique signal hash generated
    - AC2: Duplicates within 60s detected and rejected
    - AC3: TTL cleanup prevents memory leaks
    - AC4: Memory safely bounded
    - AC5: Idempotent 200 OK response for duplicates

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

    Args:
        request: FastAPI request for accessing raw body if needed
        payload: Validated SignalPayload from Pydantic model
        token: Verified webhook token from X-Webhook-Token header or ?token query param
        db: AsyncSession for database operations

    Returns:
        WebhookResponse with signal_id and status ("received" or "duplicate")
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
        log_user = user.wallet_address[:10]
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
    if deduplicator and deduplicator.is_duplicate(signal_id):
        log = logger.bind(
            signal_id=signal_id,
            side=payload.side,
            symbol=payload.symbol,
            user=log_user,
            user_id=user_id,
        )
        log.info("webhook_duplicate_signal_rejected")
        return WebhookResponse(
            status="duplicate",
            signal_id=signal_id,
            code="DUPLICATE_SIGNAL",
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
        log.warning("webhook_rate_limited", retry_after_seconds=retry_after)

        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "code": "RATE_LIMITED",
                "signal_id": signal_id,
                "dex": None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
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
        received_at=datetime.utcnow(),
    )
    db.add(signal_record)
    await db.commit()

    # Log successful reception
    log = logger.bind(
        signal_id=signal_id,
        side=payload.side,
        symbol=payload.symbol,
        user=log_user,
        user_id=user_id,
    )
    log.info("webhook_signal_received")

    return WebhookResponse(status="received", signal_id=signal_id)
