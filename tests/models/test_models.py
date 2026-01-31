"""Tests for Pydantic models including dry-run response models (Story 3.3)."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from kitkat.models import WouldHaveExecuted, DryRunResponse


class TestWouldHaveExecuted:
    """Tests for WouldHaveExecuted nested model (Story 3.3: AC#2)."""

    def test_would_have_executed_valid_creation(self):
        """Test creating WouldHaveExecuted with all required fields."""
        now = datetime.now(timezone.utc)
        result = WouldHaveExecuted(
            dex="mock",
            symbol="ETH-PERP",
            side="buy",
            size=Decimal("0.5"),
            simulated_result={
                "order_id": "mock-order-000001",
                "status": "submitted",
                "fill_price": "2150.00",
                "submitted_at": now.isoformat(),
            },
        )
        assert result.dex == "mock"
        assert result.symbol == "ETH-PERP"
        assert result.side == "buy"
        assert result.size == Decimal("0.5")
        assert result.simulated_result["order_id"] == "mock-order-000001"

    def test_would_have_executed_requires_all_fields(self):
        """Test that WouldHaveExecuted requires all fields."""
        with pytest.raises(ValidationError):
            WouldHaveExecuted(
                dex="mock",
                symbol="ETH-PERP",
                side="buy",
                # Missing size and simulated_result
            )

    def test_would_have_executed_side_validation(self):
        """Test that side must be buy or sell."""
        with pytest.raises(ValidationError):
            WouldHaveExecuted(
                dex="mock",
                symbol="ETH-PERP",
                side="invalid",
                size=Decimal("0.5"),
                simulated_result={},
            )

    def test_would_have_executed_simulated_result_flexible(self):
        """Test that simulated_result can contain any dict structure."""
        result = WouldHaveExecuted(
            dex="mock",
            symbol="ETH-PERP",
            side="sell",
            size=Decimal("1.0"),
            simulated_result={
                "order_id": "mock-order-000002",
                "status": "submitted",
                "fill_price": "2150.00",
                "submitted_at": "2026-01-31T10:00:00Z",
                "extra_field": "can include any extra data",
            },
        )
        assert result.simulated_result["extra_field"] == "can include any extra data"


class TestDryRunResponse:
    """Tests for DryRunResponse model (Story 3.3: AC#1)."""

    def test_dry_run_response_valid_creation(self):
        """Test creating DryRunResponse with valid data."""
        now = datetime.now(timezone.utc)
        response = DryRunResponse(
            signal_id="abc123",
            would_have_executed=[
                WouldHaveExecuted(
                    dex="mock",
                    symbol="ETH-PERP",
                    side="buy",
                    size=Decimal("0.5"),
                    simulated_result={
                        "order_id": "mock-order-000001",
                        "status": "submitted",
                        "fill_price": "2150.00",
                        "submitted_at": now.isoformat(),
                    },
                )
            ],
            timestamp=now,
        )
        assert response.status == "dry_run"
        assert response.signal_id == "abc123"
        assert response.message == "Test mode - no real trade executed"
        assert len(response.would_have_executed) == 1
        assert response.timestamp == now

    def test_dry_run_response_status_is_literal_dry_run(self):
        """Test that status field is always 'dry_run'."""
        now = datetime.now(timezone.utc)
        response = DryRunResponse(
            signal_id="abc123",
            would_have_executed=[],
            timestamp=now,
        )
        assert response.status == "dry_run"

    def test_dry_run_response_default_message(self):
        """Test that message has default value."""
        now = datetime.now(timezone.utc)
        response = DryRunResponse(
            signal_id="abc123",
            would_have_executed=[],
            timestamp=now,
        )
        assert response.message == "Test mode - no real trade executed"

    def test_dry_run_response_custom_message(self):
        """Test that custom message can be provided."""
        now = datetime.now(timezone.utc)
        response = DryRunResponse(
            signal_id="abc123",
            message="Custom test mode message",
            would_have_executed=[],
            timestamp=now,
        )
        assert response.message == "Custom test mode message"

    def test_dry_run_response_multiple_would_have_executed(self):
        """Test DryRunResponse with multiple DEXs."""
        now = datetime.now(timezone.utc)
        response = DryRunResponse(
            signal_id="abc123",
            would_have_executed=[
                WouldHaveExecuted(
                    dex="mock",
                    symbol="ETH-PERP",
                    side="buy",
                    size=Decimal("0.5"),
                    simulated_result={"order_id": "mock-1"},
                ),
                WouldHaveExecuted(
                    dex="mock",
                    symbol="ETH-PERP",
                    side="buy",
                    size=Decimal("0.5"),
                    simulated_result={"order_id": "mock-2"},
                ),
            ],
            timestamp=now,
        )
        assert len(response.would_have_executed) == 2

    def test_dry_run_response_empty_would_have_executed(self):
        """Test DryRunResponse with empty execution list."""
        now = datetime.now(timezone.utc)
        response = DryRunResponse(
            signal_id="abc123",
            would_have_executed=[],
            timestamp=now,
        )
        assert response.would_have_executed == []

    def test_dry_run_response_requires_signal_id(self):
        """Test that signal_id is required."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            DryRunResponse(
                # Missing signal_id
                would_have_executed=[],
                timestamp=now,
            )

    def test_dry_run_response_requires_timestamp(self):
        """Test that timestamp is required."""
        with pytest.raises(ValidationError):
            DryRunResponse(
                signal_id="abc123",
                would_have_executed=[],
                # Missing timestamp
            )

    def test_dry_run_response_json_schema(self):
        """Test that DryRunResponse generates valid JSON schema."""
        schema = DryRunResponse.model_json_schema()
        assert "properties" in schema
        assert "status" in schema["properties"]
        assert "signal_id" in schema["properties"]
        assert "would_have_executed" in schema["properties"]
        assert "timestamp" in schema["properties"]

    def test_dry_run_response_timestamp_coerces_iso_string(self):
        """Test that timestamp coerces ISO string to datetime."""
        response = DryRunResponse(
            signal_id="abc123",
            would_have_executed=[],
            timestamp="2026-01-31T10:00:00Z",  # String coerced to datetime
        )
        assert isinstance(response.timestamp, datetime)
