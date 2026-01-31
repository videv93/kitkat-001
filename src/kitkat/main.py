"""FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from kitkat.api.auth import router as auth_router
from kitkat.api.config import router as config_router
from kitkat.api.sessions import router as sessions_router
from kitkat.api.users import router as users_router
from kitkat.api.wallet import router as wallet_router
from kitkat.api.webhook import router as webhook_router
from kitkat.config import get_settings
from kitkat.database import Base, get_async_session_factory, get_engine
from kitkat.services import SignalDeduplicator, ShutdownManager
from kitkat.services.rate_limiter import RateLimiter

logger = structlog.get_logger()

# Global deduplicator singleton - initialized in lifespan
deduplicator: SignalDeduplicator | None = None
# Global rate limiter singleton - initialized in lifespan
rate_limiter: RateLimiter | None = None
# Global shutdown manager singleton - initialized in lifespan
shutdown_manager: ShutdownManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup/shutdown."""
    global deduplicator, rate_limiter, shutdown_manager

    # Startup
    settings = get_settings()
    app.state.settings = settings

    # Initialize database with comprehensive error handling
    engine = None
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

        # Verify WAL mode is enabled
        factory = get_async_session_factory()
        async with factory() as session:
            result = await session.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            logger.info("Database journal mode enabled", mode=mode)
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        # Ensure engine cleanup on failure to prevent partial initialization state
        if engine is not None:
            try:
                await engine.dispose()
                logger.info("Engine disposed after initialization failure")
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to dispose engine during error cleanup",
                    error=str(cleanup_error),
                )
        raise RuntimeError(f"Failed to initialize database: {e}") from e

    # Initialize signal deduplicator (Story 1.5)
    # Store in app.state instead of global to avoid race conditions during shutdown
    deduplicator = SignalDeduplicator(ttl_seconds=60)
    app.state.deduplicator = deduplicator
    logger.info("Signal deduplicator initialized", ttl_seconds=60)

    # Initialize rate limiter (Story 1.6)
    rate_limiter = RateLimiter(window_seconds=60, max_requests=10)
    app.state.rate_limiter = rate_limiter
    logger.info("Rate limiter initialized", window_seconds=60, max_requests=10)

    # Initialize shutdown manager (Story 2.11)
    shutdown_manager = ShutdownManager(
        grace_period_seconds=settings.shutdown_grace_period_seconds
    )
    app.state.shutdown_manager = shutdown_manager
    logger.info("Shutdown manager initialized", grace_period=settings.shutdown_grace_period_seconds)

    yield

    # Shutdown sequence (Story 2.11)
    logger.info("Shutdown signal received - initiating graceful shutdown")
    shutdown_manager.initiate_shutdown()

    # Wait for in-flight orders to complete
    clean_shutdown = await shutdown_manager.wait_for_completion()

    if clean_shutdown:
        logger.info("Graceful shutdown complete - all orders finished")
    else:
        logger.warning("Forced shutdown - some orders may be incomplete")

    # Disconnect all adapters (Story 2.11 AC5)
    # Use timeout to prevent shutdown from hanging if disconnect is stuck
    adapters = getattr(app.state, "adapters", [])
    for adapter in adapters:
        try:
            await asyncio.wait_for(adapter.disconnect(), timeout=5.0)
            logger.info("Adapter disconnected", dex_id=adapter.dex_id)
        except asyncio.TimeoutError:
            logger.warning("Adapter disconnect timeout", dex_id=adapter.dex_id, timeout_seconds=5)
        except Exception as e:
            logger.warning("Adapter disconnect failed", dex_id=adapter.dex_id, error=str(e))

    # Cleanup other resources
    if deduplicator is not None:
        deduplicator.shutdown()
        logger.info("Signal deduplicator shut down")
    deduplicator = None
    rate_limiter = None
    shutdown_manager = None
    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(
    title="Kitkat",
    description="TradingView to DEX signal execution engine",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount routers
app.include_router(webhook_router)
app.include_router(users_router)
app.include_router(sessions_router)
app.include_router(wallet_router)
app.include_router(auth_router)
app.include_router(config_router)


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
