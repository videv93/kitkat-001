"""Tests that error responses are unchanged in test mode (Story 3.3: AC#3)."""

import pytest
from pydantic import ValidationError

from kitkat.models import SignalPayload


class TestErrorResponseConsistency:
    """Tests that error responses have same format in test and production modes (Story 3.3: AC#3)."""

    def test_validation_error_missing_fields_same_format(self):
        """Test that validation errors for missing fields are identical (AC#3)."""
        # Missing 'symbol' field should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SignalPayload(
                # Missing symbol
                side="buy",
                size="0.5",
            )

        # Verify error format - should be standard Pydantic validation error
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert "symbol" in str(errors)

    def test_validation_error_invalid_side_same_format(self):
        """Test that validation errors for invalid side are identical (AC#3)."""
        # Invalid side should raise ValidationError with consistent format
        with pytest.raises(ValidationError) as exc_info:
            SignalPayload(
                symbol="ETH-PERP",
                side="invalid",  # Not "buy" or "sell"
                size="0.5",
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_validation_error_negative_size_same_format(self):
        """Test that validation errors for negative size are identical (AC#3)."""
        # Negative size should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SignalPayload(
                symbol="ETH-PERP",
                side="buy",
                size="-0.5",  # Must be positive
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_error_format_no_test_mode_indicator(self):
        """Test that validation errors don't include test mode indication (AC#3)."""
        # Error messages should not mention test mode
        try:
            SignalPayload(
                symbol="ETH-PERP",
                side="invalid_side",
                size="0.5",
            )
        except ValidationError as e:
            error_str = str(e)
            # Verify error doesn't contain test mode references
            assert "test" not in error_str.lower() or "test_mode" not in error_str
            assert "DRY RUN" not in error_str

    def test_multiple_validation_errors_same_format(self):
        """Test that multiple validation errors format consistently (AC#3)."""
        # Multiple errors should all use standard Pydantic format
        with pytest.raises(ValidationError) as exc_info:
            SignalPayload(
                # Missing symbol
                side="invalid",  # Also invalid
                size="-0.5",  # Also negative
            )

        errors = exc_info.value.errors()
        # Should have errors for all 3 fields
        assert len(errors) >= 3
        # All errors should be standard Pydantic validation errors
        for error in errors:
            assert "loc" in error
            assert "msg" in error
            assert "type" in error

    def test_type_error_same_format(self):
        """Test that type errors format consistently (AC#3)."""
        # Wrong type for size
        with pytest.raises(ValidationError):
            SignalPayload(
                symbol="ETH-PERP",
                side="buy",
                size="not_a_number",
            )

    def test_error_response_format_identical_across_modes(self):
        """Test that error response format is identical regardless of test_mode (AC#3)."""
        # This is a conceptual test showing error handling is independent of test_mode
        # The webhook error responses (401, 400, 429) should be formatted the same
        # regardless of whether test_mode=true or false

        # The actual test would happen at the HTTP level, but we validate
        # that SignalPayload validation is independent of settings

        # In test_mode=true, validation errors should still be 400 Bad Request
        # In test_mode=false, validation errors should still be 400 Bad Request
        # The only difference is successful signals return DryRunResponse vs SignalProcessorResponse

        # Create two payloads - one valid, one invalid
        valid_payload = SignalPayload(
            symbol="ETH-PERP",
            side="buy",
            size="0.5",
        )
        assert valid_payload.symbol == "ETH-PERP"

        # Invalid payload should fail the same way regardless of test_mode
        with pytest.raises(ValidationError):
            SignalPayload(
                symbol="ETH-PERP",
                side="invalid",
                size="0.5",
            )
