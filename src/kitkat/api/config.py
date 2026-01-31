"""User configuration endpoints (Story 2.4: Webhook URL Generation)."""

import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

import structlog
from kitkat.api.deps import get_current_user, get_db
from kitkat.models import CurrentUser, PayloadFormat, TradingViewSetup, WebhookConfigResponse

logger = structlog.get_logger()

# Display length for wallet addresses in logs (shows first 10 chars, e.g., "0x12345678")
WALLET_ADDRESS_DISPLAY_LENGTH = 10

# TradingView message template for ready-to-paste configuration
TRADINGVIEW_MESSAGE_TEMPLATE = json.dumps({
    "symbol": "{{ticker}}",
    "side": "{{strategy.order.action}}",
    "size": "{{strategy.position_size}}"
})

router = APIRouter(prefix="/api/config", tags=["config"])


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

    response = WebhookConfigResponse(
        webhook_url=webhook_url,
        payload_format=payload_format,
        tradingview_setup=tradingview_setup,
    )

    log.info("Webhook config retrieved", webhook_url_prefix=webhook_url[:50])
    return response
