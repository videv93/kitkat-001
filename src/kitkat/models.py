"""SQLAlchemy models and Pydantic schemas for the application."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from kitkat.database import Base, UtcDateTime


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
    """SQLAlchemy model for storing TradingView webhook signals.

    This model persists incoming signals from TradingView webhooks for deduplication,
    auditing, and async processing. Each signal is uniquely identified by its
    signal_id hash to prevent duplicate execution.

    Payload Structure (Story 1.4 - Signal Payload Parsing & Validation):
        The payload field stores the raw JSON from the webhook. Expected structure:
        {
            "symbol": str,      # Trading pair (e.g., "BTCUSDT") - required
            "side": str,        # "buy" or "sell" - required
            "size": Decimal     # Position size (must be positive) - required
        }

        Use SignalPayload Pydantic model to validate payload structure:
            from kitkat.models import SignalPayload
            validated = SignalPayload(**signal.payload)  # Validates and raises ValueError if invalid

    Attributes:
        id: Auto-increment primary key.
        signal_id: Unique hash (SHA-256 of payload) for deduplication. Indexed.
        payload: Raw JSON payload from webhook (dict with required fields).
        received_at: UTC timestamp when signal was received (timezone-aware). Indexed for time queries.
        processed: Whether signal has been processed by SignalProcessor.

    Table: signals
    Indexes: signal_id (unique), received_at
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def validate_payload(self) -> "SignalPayload":
        """Validate and parse payload using SignalPayload schema.

        Returns:
            SignalPayload: Validated payload model.

        Raises:
            ValueError: If payload structure is invalid or required fields are missing.
        """
        return SignalPayload(**self.payload)


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


class DisconnectResponse(BaseModel):
    """Response for wallet disconnect endpoint (Story 2.10).

    Disconnects the current session only. Other concurrent sessions (if any)
    remain active. Webhook token is NOT invalidated - webhooks will continue
    to execute if properly configured. To fully disable all access, use revoke.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str = Field(..., description="Wallet address (abbreviated)")
    message: str = Field(..., description="Confirmation message")
    timestamp: datetime = Field(..., description="When disconnect occurred")


class RevokeResponse(BaseModel):
    """Response for wallet revocation endpoint (Story 2.10).

    Complete revocation of all wallet delegation and sessions. All active
    sessions are invalidated immediately. Webhook token is NOT invalidated
    as it operates in a separate security domain. Users must explicitly
    regenerate webhook token if needed.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str = Field(..., description="Wallet address (abbreviated)")
    sessions_deleted: int = Field(..., description="Number of sessions invalidated")
    delegation_revoked: bool = Field(..., description="Whether DEX delegation was revoked")
    message: str = Field(..., description="Confirmation message")
    timestamp: datetime = Field(..., description="When revocation occurred")


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


# ============================================================================
# Execution Logging & Partial Fills Models (Story 2.8)
# ============================================================================


class ExecutionCreate(BaseModel):
    """Request model for creating an execution record."""

    model_config = ConfigDict(str_strip_whitespace=True)

    signal_id: str = Field(..., description="Signal hash for correlation")
    dex_id: str = Field(..., description="DEX identifier")
    order_id: str | None = Field(None, description="DEX-assigned order ID")
    status: Literal["pending", "filled", "partial", "failed"] = Field(
        ..., description="Execution status"
    )
    result_data: dict = Field(default_factory=dict, description="DEX response data")
    latency_ms: int | None = Field(None, description="Execution latency in milliseconds")


class Execution(BaseModel):
    """Persisted execution record."""

    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    id: int
    signal_id: str
    dex_id: str
    order_id: str | None
    status: Literal["pending", "filled", "partial", "failed"]
    result_data: dict
    latency_ms: int | None
    created_at: datetime


class PartialFillAlert(BaseModel):
    """Alert model for partial fill notifications."""

    model_config = ConfigDict(str_strip_whitespace=True)

    signal_id: str = Field(..., description="Signal hash")
    dex_id: str = Field(..., description="DEX identifier")
    order_id: str = Field(..., description="Order ID")
    symbol: str = Field(..., description="Trading symbol")
    filled_amount: Decimal = Field(..., ge=0, description="Amount filled")
    remaining_amount: Decimal = Field(..., ge=0, description="Amount remaining")
    timestamp: datetime = Field(..., description="Alert timestamp")


# ============================================================================
# Signal Processor & Fan-Out Models (Story 2.9)
# ============================================================================


class DEXExecutionResult(BaseModel):
    """Result of executing a signal on a single DEX."""

    model_config = ConfigDict(str_strip_whitespace=True)

    dex_id: str = Field(..., description="DEX identifier (e.g., 'extended', 'mock')")
    status: Literal["filled", "partial", "failed", "error"] = Field(
        ..., description="Execution status"
    )
    order_id: str | None = Field(None, description="DEX-assigned order ID (None on failure)")
    filled_amount: Decimal = Field(
        default=Decimal("0"), ge=0, description="Amount filled"
    )
    error_message: str | None = Field(None, description="Error message on failure")
    latency_ms: int = Field(ge=0, description="Execution latency in milliseconds")


class SignalProcessorResponse(BaseModel):
    """Aggregated response from processing a signal across all DEXs."""

    model_config = ConfigDict(str_strip_whitespace=True)

    signal_id: str = Field(..., description="Signal hash for correlation")
    overall_status: Literal["success", "partial", "failed"] = Field(
        ..., description="Aggregate status across all DEXs"
    )
    results: list[DEXExecutionResult] = Field(
        ..., description="Per-DEX execution results"
    )
    total_dex_count: int = Field(..., description="Total DEXs attempted")
    successful_count: int = Field(..., description="DEXs that executed successfully")
    failed_count: int = Field(..., description="DEXs that failed")
    timestamp: datetime = Field(..., description="When processing completed")


# ============================================================================
# Health Endpoint Models (Story 3.1)
# ============================================================================


class HealthResponse(BaseModel):
    """Health status response including test mode flag."""

    model_config = ConfigDict(str_strip_whitespace=True)

    status: Literal["healthy", "degraded", "offline"] = Field(
        ..., description="Overall health status"
    )
    test_mode: bool = Field(..., description="Whether test mode is enabled")
    timestamp: datetime = Field(..., description="Health check timestamp")
