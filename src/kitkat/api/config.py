"""User configuration endpoints (Story 2.4: Webhook URL Generation, Story 5.6: Position Size)."""

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import structlog
from kitkat.api.deps import get_current_user, get_db
from kitkat.database import UserModel
from kitkat.models import (
    CurrentUser,
    PayloadFormat,
    PositionSizeConfig,
    PositionSizeUpdate,
    TradingViewSetup,
    WebhookConfigResponse,
)

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
    Retrieve webhook URL and configuration for authenticated user (Story 2.4: AC2).

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

    # Define payload format
    payload_format = PayloadFormat(
        required_fields=["symbol", "side", "size"],
        optional_fields=["price", "order_type"],
        example={
            "symbol": "ETH-PERP",
            "side": "buy",
            "size": "0.5",
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

    log.info("Webhook config retrieved", webhook_url_prefix=webhook_url[:50])
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
