"""Webhook endpoint for receiving TradingView signals."""

import hashlib
from datetime import datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import get_db_session, verify_webhook_token
from kitkat.models import Signal, SignalPayload
from kitkat.services import SignalDeduplicator

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
    code: Literal["INVALID_TOKEN", "INVALID_SIGNAL"]
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
) -> WebhookResponse:
    """Receive, validate, and deduplicate TradingView webhook signal.

    Validates payload structure and business rules. Detects duplicates within
    60-second window and rejects them idempotently. Only new signals are
    stored and processed further.

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

    Args:
        request: FastAPI request for accessing raw body if needed
        payload: Validated SignalPayload from Pydantic model
        token: Verified webhook token from X-Webhook-Token header
        db: AsyncSession for database operations

    Returns:
        WebhookResponse with signal_id and status ("received" or "duplicate")

    Raises:
        HTTPException: 400 for validation errors, 401 for invalid token
    """
    # Generate signal_id hash from payload (Story 1.4)
    payload_json = payload.model_dump_json()
    signal_id = generate_signal_hash(payload_json)

    # Get deduplicator from app state (initialized in lifespan)
    # Handle case where deduplicator might not be initialized (e.g., in tests)
    deduplicator: SignalDeduplicator | None = getattr(
        request.app.state, "deduplicator", None
    )

    # Check for duplicates (Story 1.5, AC2, AC5)
    if deduplicator and deduplicator.is_duplicate(signal_id):
        log = logger.bind(signal_id=signal_id, side=payload.side, symbol=payload.symbol)
        log.info("webhook_duplicate_signal_rejected")
        return WebhookResponse(
            status="duplicate",
            signal_id=signal_id,
            code="DUPLICATE_SIGNAL",
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
    log = logger.bind(signal_id=signal_id, side=payload.side, symbol=payload.symbol)
    log.info("webhook_signal_received")

    return WebhookResponse(status="received", signal_id=signal_id)
