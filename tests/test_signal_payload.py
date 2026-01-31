"""Unit tests for SignalPayload Pydantic model (Story 1.4 - Task 1.6)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from kitkat.models import SignalPayload


class TestSignalPayloadValidation:
    """Unit tests for SignalPayload model validation."""

    def test_valid_payload_parses(self):
        """Test that valid payload parses successfully (AC1)."""
        payload = SignalPayload(symbol="ETH", side="buy", size=Decimal("1.5"))
        assert payload.symbol == "ETH"
        assert payload.side == "buy"
        assert payload.size == Decimal("1.5")

    def test_valid_payload_with_float_size(self):
        """Test that float size values are converted to Decimal."""
        payload = SignalPayload(symbol="BTC", side="sell", size=0.5)
        assert payload.size == Decimal("0.5")
        assert isinstance(payload.size, Decimal)

    def test_valid_payload_with_string_size(self):
        """Test that string size values are converted to Decimal."""
        payload = SignalPayload(symbol="XRP", side="buy", size="10.25")
        assert payload.size == Decimal("10.25")

    def test_missing_symbol_rejected(self):
        """Test that missing symbol field is rejected (AC3)."""
        with pytest.raises(ValidationError) as exc:
            SignalPayload(side="buy", size=1)
        assert "symbol" in str(exc.value)

    def test_missing_side_rejected(self):
        """Test that missing side field is rejected (AC3)."""
        with pytest.raises(ValidationError) as exc:
            SignalPayload(symbol="ETH", size=1)
        assert "side" in str(exc.value)

    def test_missing_size_rejected(self):
        """Test that missing size field is rejected (AC3)."""
        with pytest.raises(ValidationError) as exc:
            SignalPayload(symbol="ETH", side="buy")
        assert "size" in str(exc.value)

    def test_invalid_side_value_rejected(self):
        """Test that invalid side value is rejected (AC4)."""
        with pytest.raises(ValidationError) as exc:
            SignalPayload(symbol="ETH", side="hold", size=1)
        assert "side" in str(exc.value).lower() or "invalid" in str(exc.value).lower()

    def test_side_case_sensitive(self):
        """Test that side is case-sensitive (only lowercase buy/sell)."""
        with pytest.raises(ValidationError):
            SignalPayload(symbol="ETH", side="BUY", size=1)

        with pytest.raises(ValidationError):
            SignalPayload(symbol="ETH", side="Sell", size=1)

    def test_zero_size_rejected(self):
        """Test that zero size is rejected (AC4)."""
        with pytest.raises(ValidationError) as exc:
            SignalPayload(symbol="ETH", side="buy", size=0)
        assert "size" in str(exc.value).lower() or "positive" in str(exc.value).lower()

    def test_negative_size_rejected(self):
        """Test that negative size is rejected (AC4)."""
        with pytest.raises(ValidationError) as exc:
            SignalPayload(symbol="ETH", side="buy", size=-5)
        assert "size" in str(exc.value).lower() or "positive" in str(exc.value).lower()

    def test_empty_symbol_rejected(self):
        """Test that empty symbol is rejected."""
        with pytest.raises(ValidationError) as exc:
            SignalPayload(symbol="", side="buy", size=1)
        assert "symbol" in str(exc.value).lower()

    def test_whitespace_stripped_from_symbol(self):
        """Test that whitespace is stripped from symbol (ConfigDict str_strip_whitespace)."""
        payload = SignalPayload(symbol="  ETH  ", side="buy", size=1)
        assert payload.symbol == "ETH"

    def test_whitespace_stripped_from_side(self):
        """Test that whitespace is stripped from side."""
        payload = SignalPayload(symbol="ETH", side="  buy  ", size=1)
        assert payload.side == "buy"

    def test_unicode_symbols_accepted(self):
        """Test that unicode characters in symbol are accepted."""
        payload = SignalPayload(symbol="ETH€", side="buy", size=1)
        assert payload.symbol == "ETH€"

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored (Pydantic default behavior)."""
        payload = SignalPayload(
            symbol="ETH",
            side="buy",
            size=1,
            extra_field="ignored",
            another_field=123,
        )
        assert payload.symbol == "ETH"
        assert payload.side == "buy"
        assert payload.size == 1
        assert not hasattr(payload, "extra_field")

    def test_model_dump_includes_all_fields(self):
        """Test that model_dump includes all required fields."""
        payload = SignalPayload(symbol="ETH", side="buy", size=Decimal("1.5"))
        dumped = payload.model_dump()

        assert "symbol" in dumped
        assert "side" in dumped
        assert "size" in dumped
        assert dumped["symbol"] == "ETH"
        assert dumped["side"] == "buy"
        assert dumped["size"] == Decimal("1.5")

    def test_model_dump_json_serializable(self):
        """Test that model_dump_json produces valid JSON."""
        payload = SignalPayload(symbol="ETH", side="buy", size=Decimal("1.5"))
        json_str = payload.model_dump_json()

        assert isinstance(json_str, str)
        assert "ETH" in json_str
        assert "buy" in json_str
        assert "1.5" in json_str

    def test_signal_id_consistency(self):
        """Test that same payload produces same signal_id hash (for deduplication)."""
        from kitkat.api.webhook import generate_signal_hash

        payload1 = SignalPayload(symbol="ETH", side="buy", size=Decimal("1.5"))
        payload2 = SignalPayload(symbol="ETH", side="buy", size=Decimal("1.5"))

        json1 = payload1.model_dump_json()
        json2 = payload2.model_dump_json()

        # Same JSON should produce same hash (within same minute)
        assert json1 == json2
        hash1 = generate_signal_hash(json1)
        hash2 = generate_signal_hash(json2)
        assert hash1 == hash2
