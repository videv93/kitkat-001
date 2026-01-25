"""SQLAlchemy models and Pydantic schemas for the application."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from kitkat.database import Base


class SignalPayload(BaseModel):
    """TradingView webhook signal payload with validation.

    This model validates the JSON structure and business rules for incoming
    webhook signals from TradingView (Story 1.4).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1, description="Trading pair symbol")
    side: Literal["buy", "sell"] = Field(..., description="Direction: buy or sell")
    size: Decimal = Field(..., gt=0, description="Position size (must be positive)")

    @field_validator("side", mode="before")
    @classmethod
    def validate_side(cls, v: str) -> str:
        """Validate side is either 'buy' or 'sell'."""
        if v not in ("buy", "sell"):
            raise ValueError("Invalid side value. Expected: buy or sell")
        return v

    @field_validator("size", mode="before")
    @classmethod
    def validate_size(cls, v: Decimal | float | int | str) -> Decimal:
        """Validate size is positive."""
        try:
            size_decimal = Decimal(str(v)) if not isinstance(v, Decimal) else v
        except (ValueError, TypeError, Exception):
            raise ValueError("Size must be a valid number")

        if size_decimal <= 0:
            raise ValueError("Size must be positive")
        return size_decimal


class Signal(Base):
    """Signal model for storing webhook signals from TradingView."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# ============================================================================
# DEX Adapter Interface Models (Story 2.1)
# ============================================================================


class ConnectParams(BaseModel):
    """Base class for DEX adapter connection parameters.

    Adapters can subclass this to add DEX-specific parameters.
    For example, ExtendedConnectParams would add:
    - api_key: str
    - stark_private_key: str
    - account_address: str
    - network: Literal["testnet", "mainnet"]
    """

    model_config = ConfigDict(str_strip_whitespace=True)
    # Base class can be empty or have common fields


class OrderSubmissionResult(BaseModel):
    """Result of submitting an order to a DEX.

    This represents the immediate response from execute_order(), not the final
    execution status. The order has been submitted and assigned an ID, but we
    don't yet know if it filled, partially filled, or was rejected.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    order_id: str = Field(..., description="DEX-assigned order identifier")
    status: Literal["submitted"] = Field(
        default="submitted", description="Always 'submitted' on success"
    )
    submitted_at: datetime = Field(..., description="When order was submitted")
    filled_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Amount already executed (0 if unknown)",
    )
    dex_response: dict = Field(..., description="Raw DEX API response")


class OrderStatus(BaseModel):
    """Current status of a submitted order.

    Retrieved via get_order_status(order_id) or from WebSocket subscription.
    Represents the actual fill information and current order state.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    order_id: str = Field(..., description="DEX-assigned order identifier")
    status: Literal["pending", "filled", "partial", "failed", "cancelled"] = Field(
        ..., description="Current order status"
    )
    filled_amount: Decimal = Field(ge=0, description="Amount already executed")
    remaining_amount: Decimal = Field(
        ge=0, description="Amount still pending or cancelled"
    )
    average_price: Decimal = Field(ge=0, description="Average execution price (0 if no fills)")
    last_updated: datetime = Field(..., description="When status was last updated")


class HealthStatus(BaseModel):
    """Health status of a DEX adapter connection."""

    model_config = ConfigDict(str_strip_whitespace=True)

    dex_id: str = Field(..., description="DEX identifier (e.g., 'extended', 'mock')")
    status: Literal["healthy", "degraded", "offline"] = Field(
        ..., description="Current health status"
    )
    connected: bool = Field(..., description="Is adapter currently connected?")
    latency_ms: int = Field(ge=0, description="Last measured latency in milliseconds")
    last_check: datetime = Field(..., description="When was last health check")
    error_message: Optional[str] = Field(
        default=None,
        description="Error message explaining degraded/offline status (None if healthy)",
    )


class Position(BaseModel):
    """User's current position in a trading asset."""

    model_config = ConfigDict(str_strip_whitespace=True)

    symbol: str = Field(..., description="Trading pair symbol")
    size: Decimal = Field(ge=0, description="Amount held (0 = no position)")
    entry_price: Decimal = Field(gt=0, description="Price at entry")
    current_price: Decimal = Field(gt=0, description="Current market price")
    unrealized_pnl: Decimal = Field(..., description="Unrealized P&L (can be negative)")


@dataclass
class OrderUpdate:
    """Real-time order update from WebSocket subscription or polling.

    Used as callback parameter for subscribe_to_order_updates().
    """

    order_id: str
    status: Literal["pending", "filled", "partial", "failed", "cancelled"]
    filled_amount: Decimal
    remaining_amount: Decimal
    timestamp: datetime


# ============================================================================
# User & Session Management Models (Story 2.2)
# ============================================================================


class UserCreate(BaseModel):
    """Request model for creating a new user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str = Field(..., min_length=1, max_length=255)
    # Note: signature validation happens in Story 2.3


class User(BaseModel):
    """Persisted user with configuration."""

    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    id: int
    wallet_address: str
    webhook_token: str
    config_data: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @field_validator("config_data", mode="before")
    @classmethod
    def parse_config_data(cls, v):
        """Parse config_data from JSON string if needed."""
        if isinstance(v, str):
            import json

            return json.loads(v)
        return v if v else {}


class SessionCreate(BaseModel):
    """Request model for creating a new session."""

    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str = Field(..., min_length=1, max_length=255)


class Session(BaseModel):
    """Persisted session token."""

    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    id: int
    token: str
    wallet_address: str
    created_at: datetime
    expires_at: datetime
    last_used: datetime


class CurrentUser(BaseModel):
    """Authenticated user context from valid session."""

    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str
    session_id: int
    webhook_token: str


# ============================================================================
# Wallet Connection Models (Story 2.3)
# ============================================================================


class ChallengeRequest(BaseModel):
    """Request model for wallet challenge generation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str = Field(..., min_length=42, max_length=42)

    @field_validator("wallet_address")
    @classmethod
    def validate_ethereum_address(cls, v: str) -> str:
        """Validate Ethereum address format (0x + 40 hex chars)."""
        if not v.startswith("0x"):
            raise ValueError("Invalid Ethereum address: must start with 0x")
        if len(v) != 42:
            raise ValueError("Invalid Ethereum address: must be 42 characters")
        try:
            int(v[2:], 16)  # Validate hex
        except ValueError:
            raise ValueError("Invalid Ethereum address: invalid hex characters")
        return v


class ChallengeResponse(BaseModel):
    """Response model for wallet challenge."""

    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(..., description="Challenge message to sign")
    nonce: str = Field(..., description="Unique nonce for replay prevention")
    expires_at: datetime = Field(..., description="Challenge expiration timestamp")
    explanation: str = Field(
        ...,
        description="User-facing explanation of what signing means",
    )


class VerifyRequest(BaseModel):
    """Request model for signature verification."""

    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str = Field(..., min_length=42, max_length=42)
    signature: str = Field(..., min_length=1)
    nonce: str = Field(..., min_length=1)

    @field_validator("wallet_address")
    @classmethod
    def validate_ethereum_address(cls, v: str) -> str:
        """Validate Ethereum address format."""
        if not v.startswith("0x"):
            raise ValueError("Invalid Ethereum address: must start with 0x")
        if len(v) != 42:
            raise ValueError("Invalid Ethereum address: must be 42 characters")
        try:
            int(v[2:], 16)
        except ValueError:
            raise ValueError("Invalid Ethereum address: invalid hex characters")
        return v


class VerifyResponse(BaseModel):
    """Response model for successful signature verification."""

    model_config = ConfigDict(str_strip_whitespace=True)

    token: str = Field(..., description="Session token for authentication")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    wallet_address: str = Field(..., description="Verified wallet address")


# ============================================================================
# Webhook Configuration Models (Story 2.4)
# ============================================================================


class PayloadFormat(BaseModel):
    """Webhook payload format specification."""

    model_config = ConfigDict(str_strip_whitespace=True)

    required_fields: list[str] = Field(
        ..., description="Required fields in webhook payload"
    )
    optional_fields: list[str] = Field(
        default_factory=list, description="Optional fields in webhook payload"
    )
    example: dict = Field(..., description="Example payload")


class TradingViewSetup(BaseModel):
    """TradingView alert configuration instructions."""

    model_config = ConfigDict(str_strip_whitespace=True)

    alert_name: str = Field(..., description="Recommended alert name in TradingView")
    webhook_url: str = Field(..., description="Complete webhook URL with token")
    message_template: str = Field(
        ..., description="Ready-to-paste message template for TradingView"
    )


class WebhookConfigResponse(BaseModel):
    """Response for webhook configuration endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True)

    webhook_url: str = Field(..., description="Complete webhook URL for user")
    payload_format: PayloadFormat = Field(..., description="Payload format specification")
    tradingview_setup: TradingViewSetup = Field(
        ..., description="TradingView setup instructions"
    )
