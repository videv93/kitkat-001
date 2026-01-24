"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from kitkat.api.webhook import router as webhook_router
from kitkat.config import get_settings
from kitkat.database import Base, async_session, get_engine
from kitkat.services import SignalDeduplicator
from kitkat.services.rate_limiter import RateLimiter

logger = structlog.get_logger()

# Global deduplicator singleton - initialized in lifespan
deduplicator: SignalDeduplicator | None = None
# Global rate limiter singleton - initialized in lifespan
rate_limiter: RateLimiter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup/shutdown."""
    global deduplicator, rate_limiter

    # Startup
    settings = get_settings()
    app.state.settings = settings

    # Initialize database
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    # Verify WAL mode is enabled
    factory = async_session()
    async with factory() as session:
        result = await session.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
        logger.info("Database journal mode enabled", mode=mode)

    # Initialize signal deduplicator (Story 1.5)
    deduplicator = SignalDeduplicator(ttl_seconds=60)
    app.state.deduplicator = deduplicator
    logger.info("Signal deduplicator initialized", ttl_seconds=60)

    # Initialize rate limiter (Story 1.6)
    rate_limiter = RateLimiter(window_seconds=60, max_requests=10)
    app.state.rate_limiter = rate_limiter
    logger.info("Rate limiter initialized", window_seconds=60, max_requests=10)

    yield

    # Shutdown
    deduplicator = None
    rate_limiter = None
    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(
    title="Kitkat",
    description="TradingView to DEX signal execution engine",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount webhook router
app.include_router(webhook_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors and format per architecture spec.

    Story 1.4: AC2-4 require validation errors to return 400 with specific format.
    AC5 requires logging raw payload for debugging.
    """
    # Extract raw body for logging (AC5)
    try:
        body = await request.body()
        raw_payload = body.decode() if body else "{}"
    except Exception:
        raw_payload = "unavailable"

    # Log raw payload for debugging (AC5)
    log = logger.bind(endpoint=str(request.url))
    log.warning(
        "Webhook validation failed", raw_payload=raw_payload, errors=exc.errors()
    )

    # Format error response per AC2-4
    # Get first validation error for error message
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    error_message = first_error.get("msg", "Invalid request")

    # Map Pydantic error types to user-friendly messages
    error_type = first_error.get("type", "")
    loc = first_error.get("loc", [])

    # Extract field name from location tuple (e.g., ('symbol',) or ('body', 'symbol'))
    field_name = None
    if loc:
        # Try to get the last non-numeric part of the location
        for part in reversed(loc):
            if isinstance(part, str) and not part.isdigit() and part != "body":
                field_name = part
                break

    if "missing" in error_type.lower():
        if field_name:
            error_message = f"Missing required field: {field_name}"
        else:
            error_message = "Missing required field"
    elif error_type == "literal_error" or "literal" in error_message.lower():
        error_message = "Invalid side value"
    elif error_type == "greater_than" or "greater than" in error_message.lower():
        error_message = "Size must be positive"
    elif error_type == "decimal" or "decimal" in error_message.lower():
        error_message = "Size must be a valid number"
    elif "json" in error_message.lower() or "json" in error_type.lower():
        error_message = "Invalid JSON"

    return JSONResponse(
        status_code=400,
        content={
            "error": error_message,
            "code": "INVALID_SIGNAL",
            "signal_id": None,
            "dex": None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy"}
