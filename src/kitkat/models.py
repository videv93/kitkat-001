"""SQLAlchemy models and Pydantic schemas for the application."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, Boolean, DateTime, Integer, String
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
