"""User configuration endpoints (Story 2.4: Webhook URL Generation, Story 5.6: Position Size, Story 5.8: Telegram)."""

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import structlog
from kitkat.api.deps import get_current_user, get_db
from kitkat.config import get_settings
from kitkat.database import UserModel
from kitkat.models import (
    CurrentUser,
    PayloadFormat,
    PositionSizeConfig,
    PositionSizeUpdate,
    TelegramConfigResponse,
    TelegramConfigUpdate,
    TradingViewSetup,
    WebhookConfigResponse,
)
from kitkat.services.alert import TelegramAlertService

logger = structlog.get_logger()

# Display length for wallet addresses in logs (shows first 10 chars, e.g., "0x12345678")
WALLET_ADDRESS_DISPLAY_LENGTH = 10

# TradingView message template for ready-to-paste configuration
TRADINGVIEW_MESSAGE_TEMPLATE = json.dumps({
    "symbol": "{{ticker}}",
    "side": "{{strategy.order.action}}",
    "size": "{{strategy.position_size}}"
})

# Position size defaults (Story 5.6: AC#6)
DEFAULT_POSITION_SIZE = Decimal("0.1")
DEFAULT_MAX_POSITION_SIZE = Decimal("10.0")
SYSTEM_MAX_POSITION_SIZE = Decimal("100.0")

router = APIRouter(prefix="/api/config", tags=["config"])


def _get_config_value(
    config_data: dict | str | None,
    key: str,
    default: Decimal,
) -> Decimal:
    """Extract config value from config_data with default fallback.

    Handles both dict and JSON string formats for config_data.

    Args:
        config_data: User's config_data (dict, JSON string, or None)
        key: Configuration key to extract
        default: Default value if key not found

    Returns:
        Decimal value from config or default
    """
    if not config_data:
        return default

    # Parse JSON string if needed
    if isinstance(config_data, str):
        try:
            config_data = json.loads(config_data)
        except (json.JSONDecodeError, TypeError):
            return default

    value = config_data.get(key)
    if value is None:
        return default

    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return default


@router.get("/webhook", response_model=WebhookConfigResponse)
async def get_webhook_config(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookConfigResponse:
    """
    Retrieve webhook URL and configuration for authenticated user (Story 2.4, 5.7).

    Returns:
        WebhookConfigResponse: Webhook URL and payload format documentation

    Raises:
        HTTPException: 401 if user not authenticated (handled by get_current_user)
        HTTPException: 500 if webhook token not configured for user
    """
    wallet_display = current_user.wallet_address[:WALLET_ADDRESS_DISPLAY_LENGTH]
    log = logger.bind(user=wallet_display)

    # Validate webhook token exists
    if not current_user.webhook_token:
        log.error("User webhook token not configured")
        raise HTTPException(
            status_code=500,
            detail="Webhook token not configured for user account"
        )

    # Get app host from request or environment
    # X-Forwarded-Host is used when behind reverse proxy
    host = request.headers.get("X-Forwarded-Host") or request.base_url.netloc

    # Get scheme from X-Forwarded-Proto (common behind reverse proxy) or request
    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)

    # Build webhook URL with proper scheme
    webhook_url = f"{scheme}://{host}/api/webhook?token={current_user.webhook_token}"

    # Define payload format (AC#3: required vs optional fields with working example)
    payload_format = PayloadFormat(
        required_fields=["symbol", "side", "size"],
        optional_fields=["price", "order_type"],
        example={
            "symbol": "ETH-PERP",
            "side": "buy",
            "size": "{{strategy.position_size}}",  # TradingView placeholder syntax
        },
    )

    # TradingView setup instructions (uses pre-defined template constant)
    tradingview_setup = TradingViewSetup(
        alert_name="kitkat-001 Signal",
        webhook_url=webhook_url,
        message_template=TRADINGVIEW_MESSAGE_TEMPLATE,
    )

    # Token abbreviation for display (Story 5.7: AC#5)
    token = current_user.webhook_token
    token_display = f"{token[:8]}..." if len(token) > 8 else token

    response = WebhookConfigResponse(
        webhook_url=webhook_url,
        payload_format=payload_format,
        tradingview_setup=tradingview_setup,
        token_display=token_display,
    )

    log.info("Webhook config retrieved")
    return response


@router.get("", response_model=PositionSizeConfig)
async def get_config(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PositionSizeConfig:
    """Get user's position size configuration (Story 5.6: AC#1).

    Returns current position size settings with defaults applied
    if not explicitly configured.

    Returns:
        PositionSizeConfig with current settings

    Raises:
        HTTPException: 401 if not authenticated (handled by get_current_user)
        HTTPException: 404 if user not found in database
    """
    wallet_display = current_user.wallet_address[:WALLET_ADDRESS_DISPLAY_LENGTH]
    log = logger.bind(user=wallet_display)
    log.debug("Fetching user config")

    # Query user's config_data
    query = select(UserModel).where(
        UserModel.wallet_address == current_user.wallet_address
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        log.error("Authenticated user not found in database")
        raise HTTPException(status_code=404, detail="User not found")

    # Extract values with defaults (AC#6)
    position_size = _get_config_value(
        user.config_data, "position_size", DEFAULT_POSITION_SIZE
    )
    max_position_size = _get_config_value(
        user.config_data, "max_position_size", DEFAULT_MAX_POSITION_SIZE
    )

    log.info(
        "Config retrieved",
        position_size=str(position_size),
        max_position_size=str(max_position_size),
    )

    return PositionSizeConfig(
        position_size=str(position_size),
        max_position_size=str(max_position_size),
        position_size_unit="ETH",
    )


@router.put("", response_model=PositionSizeConfig)
async def update_config(
    config_update: PositionSizeUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PositionSizeConfig:
    """Update user's position size configuration (Story 5.6: AC#2, #3, #4).

    Validates and updates position size settings. Both fields are optional -
    only provided fields are updated.

    Validation rules:
    - position_size must be > 0 (AC#3, enforced by Pydantic)
    - max_position_size must be > 0 and <= 100 (AC#4, enforced by Pydantic)
    - position_size must be <= max_position_size (AC#3, cross-validation)

    Returns:
        PositionSizeConfig with updated settings

    Raises:
        HTTPException: 400 if cross-validation fails
        HTTPException: 401 if not authenticated
        HTTPException: 404 if user not found
        HTTPException: 422 if Pydantic validation fails
    """
    wallet_display = current_user.wallet_address[:WALLET_ADDRESS_DISPLAY_LENGTH]
    log = logger.bind(user=wallet_display)
    log.debug("Updating user config", update=config_update.model_dump())

    # Get current user from database
    query = select(UserModel).where(
        UserModel.wallet_address == current_user.wallet_address
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        log.error("Authenticated user not found in database")
        raise HTTPException(status_code=404, detail="User not found")

    # Parse current config_data (handle JSON string or dict)
    if isinstance(user.config_data, str):
        try:
            config_data = json.loads(user.config_data)
        except (json.JSONDecodeError, TypeError):
            config_data = {}
    else:
        config_data = dict(user.config_data) if user.config_data else {}

    # Get current values with defaults
    current_position_size = _get_config_value(
        config_data, "position_size", DEFAULT_POSITION_SIZE
    )
    current_max_size = _get_config_value(
        config_data, "max_position_size", DEFAULT_MAX_POSITION_SIZE
    )

    # Determine new values (use current if not provided)
    new_position_size = (
        config_update.position_size
        if config_update.position_size is not None
        else current_position_size
    )
    new_max_size = (
        config_update.max_position_size
        if config_update.max_position_size is not None
        else current_max_size
    )

    # Cross-validation: position_size <= max_position_size (AC#3)
    if new_position_size > new_max_size:
        log.warning(
            "Position size exceeds max",
            position_size=str(new_position_size),
            max_position_size=str(new_max_size),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "position_size cannot exceed max_position_size",
                "code": "INVALID_CONFIG",
                "position_size": str(new_position_size),
                "max_position_size": str(new_max_size),
            },
        )

    # Update config_data
    config_data["position_size"] = str(new_position_size)
    config_data["max_position_size"] = str(new_max_size)

    # Save to database (config_data is stored as JSON string)
    update_stmt = (
        update(UserModel)
        .where(UserModel.wallet_address == current_user.wallet_address)
        .values(config_data=json.dumps(config_data))
    )
    await db.execute(update_stmt)
    await db.commit()

    log.info(
        "Config updated",
        position_size=str(new_position_size),
        max_position_size=str(new_max_size),
    )

    return PositionSizeConfig(
        position_size=str(new_position_size),
        max_position_size=str(new_max_size),
        position_size_unit="ETH",
    )


# ============================================================================
# Telegram Configuration Endpoints (Story 5.8)
# ============================================================================


# Setup instructions for unconfigured users
TELEGRAM_SETUP_INSTRUCTIONS = (
    "To configure Telegram alerts:\n"
    "1. Start a chat with the kitkat-001 bot on Telegram\n"
    "2. Send /start to the bot\n"
    "3. Copy your chat ID from the bot's response\n"
    "4. Use PUT /api/config/telegram with your chat_id"
)


@router.get("/telegram", response_model=TelegramConfigResponse)
async def get_telegram_config(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelegramConfigResponse:
    """Retrieve Telegram configuration for authenticated user (Story 5.8: AC#1, #5).

    Returns:
        TelegramConfigResponse with current configuration status

    Raises:
        HTTPException: 401 if user not authenticated (handled by get_current_user)
        HTTPException: 404 if user not found in database
    """
    wallet_display = current_user.wallet_address[:WALLET_ADDRESS_DISPLAY_LENGTH]
    log = logger.bind(user=wallet_display)
    log.debug("Fetching telegram config")

    # Query user's config_data
    query = select(UserModel).where(
        UserModel.wallet_address == current_user.wallet_address
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        log.error("Authenticated user not found in database")
        raise HTTPException(status_code=404, detail="User not found")

    # Parse config_data
    if isinstance(user.config_data, str):
        try:
            config_data = json.loads(user.config_data)
        except (json.JSONDecodeError, TypeError):
            config_data = {}
    else:
        config_data = dict(user.config_data) if user.config_data else {}

    # Check user's telegram configuration
    chat_id = config_data.get("telegram_chat_id")
    configured = bool(chat_id)

    # Check if bot token is configured system-wide (AC#6)
    settings = get_settings()
    bot_configured = bool(settings.telegram_bot_token)

    # Determine bot status
    if not bot_configured:
        bot_status = "not_configured"
    else:
        bot_status = "connected"  # Assume connected if token exists

    # Setup instructions when not configured (AC#5)
    setup_instructions = None if configured else TELEGRAM_SETUP_INSTRUCTIONS

    log.info(
        "Telegram config retrieved",
        configured=configured,
        bot_status=bot_status,
    )

    return TelegramConfigResponse(
        configured=configured,
        chat_id=chat_id,
        bot_status=bot_status,
        test_available=bot_configured,
        setup_instructions=setup_instructions,
    )


@router.put("/telegram", response_model=TelegramConfigResponse)
async def update_telegram_config(
    config_update: TelegramConfigUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelegramConfigResponse:
    """Update Telegram configuration for authenticated user (Story 5.8: AC#2, #3, #4).

    Sends a test message before saving. If test fails, config is NOT saved.

    Returns:
        TelegramConfigResponse with updated configuration

    Raises:
        HTTPException: 400 if test message fails (invalid chat_id)
        HTTPException: 401 if user not authenticated
        HTTPException: 404 if user not found
        HTTPException: 503 if bot token not configured on server
    """
    wallet_display = current_user.wallet_address[:WALLET_ADDRESS_DISPLAY_LENGTH]
    log = logger.bind(user=wallet_display, chat_id=config_update.chat_id)
    log.debug("Updating telegram config")

    # Check bot token is configured (AC#6 - system-wide token)
    settings = get_settings()
    if not settings.telegram_bot_token:
        log.warning("Telegram bot token not configured on server")
        raise HTTPException(
            status_code=503,
            detail="Telegram bot not configured on server"
        )

    # Query user from database
    query = select(UserModel).where(
        UserModel.wallet_address == current_user.wallet_address
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        log.error("Authenticated user not found in database")
        raise HTTPException(status_code=404, detail="User not found")

    # Send test message to verify chat_id (AC#3)
    alert_service = TelegramAlertService(
        bot_token=settings.telegram_bot_token,
        chat_id=config_update.chat_id,
    )

    test_success = await alert_service.send_test_message()

    if not test_success:
        # AC#4: Test failed - do NOT save config
        log.warning("Test message failed", chat_id=config_update.chat_id)
        raise HTTPException(
            status_code=400,
            detail="Failed to send test message - check chat ID"
        )

    # Test succeeded - save configuration (AC#2)
    # Parse current config_data
    if isinstance(user.config_data, str):
        try:
            config_data = json.loads(user.config_data)
        except (json.JSONDecodeError, TypeError):
            config_data = {}
    else:
        config_data = dict(user.config_data) if user.config_data else {}

    # Update with new telegram_chat_id
    config_data["telegram_chat_id"] = config_update.chat_id

    # Save to database
    update_stmt = (
        update(UserModel)
        .where(UserModel.wallet_address == current_user.wallet_address)
        .values(config_data=json.dumps(config_data))
    )
    await db.execute(update_stmt)
    await db.commit()

    log.info("Telegram configuration updated successfully")

    return TelegramConfigResponse(
        configured=True,
        chat_id=config_update.chat_id,
        bot_status="connected",
        test_available=True,
        setup_instructions=None,
    )
