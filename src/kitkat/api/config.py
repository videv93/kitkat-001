"""User configuration endpoints (Story 2.4: Webhook URL Generation)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

import structlog
from kitkat.api.deps import get_current_user, get_db
from kitkat.models import CurrentUser, PayloadFormat, TradingViewSetup, WebhookConfigResponse

logger = structlog.get_logger()

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
    """
    log = logger.bind(user=current_user.wallet_address[:10])

    # Get app host from request or environment
    host = request.headers.get("X-Forwarded-Host") or request.base_url.netloc

    # Build webhook URL
    webhook_url = f"http://{host}/api/webhook?token={current_user.webhook_token}"
    if request.url.scheme == "https":
        webhook_url = webhook_url.replace("http://", "https://")

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

    # TradingView setup instructions
    tradingview_setup = TradingViewSetup(
        alert_name="kitkat-001 Signal",
        webhook_url=webhook_url,
        message_template='{"symbol": "{{ticker}}", "side": "{{strategy.order.action}}", "size": "{{strategy.position_size}}"}',
    )

    response = WebhookConfigResponse(
        webhook_url=webhook_url,
        payload_format=payload_format,
        tradingview_setup=tradingview_setup,
    )

    log.info("Webhook config retrieved", webhook_url_prefix=webhook_url[:50])
    return response
