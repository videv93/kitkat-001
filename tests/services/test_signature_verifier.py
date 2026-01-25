"""Unit tests for signature verification service (Story 2.3)."""

import pytest
from datetime import datetime, timedelta, timezone
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys

from kitkat.services.signature_verifier import SignatureVerifier, ChallengeStore


@pytest.fixture
def challenge_store():
    """Create a new challenge store for each test."""
    return ChallengeStore()


@pytest.fixture
def verifier(challenge_store):
    """Create a signature verifier with isolated challenge store."""
    return SignatureVerifier(challenge_store=challenge_store)


@pytest.fixture
def wallet_pair():
    """Generate a test wallet address and private key for signing."""
    pk = keys.PrivateKey(b"\x01" * 32)
    account = Account.from_key(pk.to_bytes())
    return {
        "address": account.address,
        "private_key": pk.to_bytes(),
        "account": account,
    }


class TestChallengeStore:
    """Tests for the ChallengeStore class."""

    def test_create_challenge_returns_nonce_and_expiration(self, challenge_store):
        """Challenge creation returns nonce, expiration, and message."""
        wallet = "0x1234567890123456789012345678901234567890"

        nonce, expires_at, message = challenge_store.create_challenge(wallet)

        assert isinstance(nonce, str)
        assert len(nonce) > 0
        assert isinstance(expires_at, datetime)
        assert expires_at > datetime.now(timezone.utc)
        assert isinstance(message, str)
        assert wallet in message

    def test_create_challenge_generates_unique_nonces(self, challenge_store):
        """Each challenge has a unique nonce."""
        wallet = "0x1234567890123456789012345678901234567890"

        nonce1, _, _ = challenge_store.create_challenge(wallet)
        nonce2, _, _ = challenge_store.create_challenge(wallet)
        nonce3, _, _ = challenge_store.create_challenge(wallet)

        assert nonce1 != nonce2
        assert nonce2 != nonce3
        assert nonce1 != nonce3

    def test_get_challenge_returns_stored_challenge(self, challenge_store):
        """Get challenge returns the stored challenge."""
        wallet = "0x1234567890123456789012345678901234567890"

        nonce, expires_at, message = challenge_store.create_challenge(wallet)
        retrieved = challenge_store.get_challenge(nonce)

        assert retrieved is not None
        stored_wallet, stored_expires, stored_message = retrieved
        assert stored_wallet == wallet.lower()
        assert stored_message == message

    def test_get_challenge_returns_none_for_unknown_nonce(self, challenge_store):
        """Get challenge returns None for unknown nonce."""
        result = challenge_store.get_challenge("unknown-nonce-12345")

        assert result is None

    def test_consume_challenge_removes_challenge(self, challenge_store):
        """Consume challenge retrieves then removes the challenge."""
        wallet = "0x1234567890123456789012345678901234567890"

        nonce, _, _ = challenge_store.create_challenge(wallet)

        # First consume succeeds
        result = challenge_store.consume_challenge(nonce)
        assert result is not None

        # Second consume fails (already consumed)
        result = challenge_store.consume_challenge(nonce)
        assert result is None

    def test_consume_challenge_returns_none_for_expired(self, challenge_store):
        """Consume challenge returns None if challenge has expired."""
        wallet = "0x1234567890123456789012345678901234567890"

        # Manually add an expired challenge
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        message = "test message"
        nonce = "expired-nonce-123"
        challenge_store._challenges[nonce] = (wallet.lower(), past, message)

        result = challenge_store.consume_challenge(nonce)

        assert result is None


class TestSignatureVerifier:
    """Tests for the SignatureVerifier class."""

    def test_create_challenge(self, verifier):
        """Create challenge generates challenge data."""
        wallet = "0x1234567890123456789012345678901234567890"

        nonce, expires_at, message = verifier.create_challenge(wallet)

        assert isinstance(nonce, str)
        assert len(nonce) > 0
        assert isinstance(expires_at, datetime)
        assert isinstance(message, str)

    def test_verify_valid_signature(self, verifier, wallet_pair):
        """Valid signature verifies successfully."""
        wallet = wallet_pair["address"]
        account = wallet_pair["account"]

        # Create challenge
        nonce, _, message = verifier.create_challenge(wallet)

        # Sign with correct account
        signable_message = encode_defunct(text=message)
        signature = account.sign_message(signable_message).signature

        # Verify signature
        result = verifier.verify_signature(wallet, signature.hex(), nonce)

        assert result is True

    def test_verify_signature_with_0x_prefix(self, verifier, wallet_pair):
        """Signature verification works with 0x prefix."""
        wallet = wallet_pair["address"]
        account = wallet_pair["account"]

        nonce, _, message = verifier.create_challenge(wallet)

        signable_message = encode_defunct(text=message)
        signature = account.sign_message(signable_message).signature

        # Verify with 0x prefix
        result = verifier.verify_signature(wallet, "0x" + signature.hex(), nonce)

        assert result is True

    def test_verify_signature_without_0x_prefix(self, verifier, wallet_pair):
        """Signature verification works without 0x prefix."""
        wallet = wallet_pair["address"]
        account = wallet_pair["account"]

        nonce, _, message = verifier.create_challenge(wallet)

        signable_message = encode_defunct(text=message)
        signature = account.sign_message(signable_message).signature

        # Verify without 0x prefix (should add it)
        result = verifier.verify_signature(wallet, signature.hex(), nonce)

        assert result is True

    def test_verify_invalid_signature_format_raises(self, verifier, wallet_pair):
        """Invalid signature format raises ValueError."""
        wallet = wallet_pair["address"]

        nonce, _, _ = verifier.create_challenge(wallet)

        with pytest.raises(ValueError, match="Invalid signature"):
            verifier.verify_signature(wallet, "not-a-valid-signature", nonce)

    def test_verify_signature_wrong_wallet_raises(self, verifier, wallet_pair):
        """Signature from different wallet raises ValueError."""
        wallet = wallet_pair["address"]
        account = wallet_pair["account"]

        nonce, _, message = verifier.create_challenge(wallet)

        signable_message = encode_defunct(text=message)
        signature = account.sign_message(signable_message).signature

        # Try to verify with different wallet address
        different_wallet = "0x0000000000000000000000000000000000000000"

        with pytest.raises(ValueError, match="does not match"):
            verifier.verify_signature(different_wallet, signature.hex(), nonce)

    def test_verify_expired_challenge_raises(self, verifier, wallet_pair):
        """Expired challenge raises ValueError."""
        wallet = wallet_pair["address"]

        # Manually add an expired challenge
        nonce = "expired-nonce-123"
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        message = "old message"
        verifier._challenge_store._challenges[nonce] = (wallet.lower(), past, message)

        with pytest.raises(ValueError, match="Challenge not found or expired"):
            verifier.verify_signature(wallet, "0x" + "00" * 65, nonce)

    def test_verify_unknown_nonce_raises(self, verifier, wallet_pair):
        """Unknown nonce raises ValueError."""
        wallet = wallet_pair["address"]

        with pytest.raises(ValueError, match="Challenge not found or expired"):
            verifier.verify_signature(wallet, "0x" + "00" * 65, "unknown-nonce")

    def test_verify_signature_case_insensitive(self, verifier, wallet_pair):
        """Signature verification is case-insensitive for wallet addresses."""
        wallet = wallet_pair["address"]
        account = wallet_pair["account"]

        nonce, _, message = verifier.create_challenge(wallet)

        signable_message = encode_defunct(text=message)
        signature = account.sign_message(signable_message).signature

        # Verify with lowercase
        result = verifier.verify_signature(wallet.lower(), signature.hex(), nonce)

        assert result is True

    def test_verify_signature_single_use(self, verifier, wallet_pair):
        """Challenge nonce can only be used once."""
        wallet = wallet_pair["address"]
        account = wallet_pair["account"]

        nonce, _, message = verifier.create_challenge(wallet)

        signable_message = encode_defunct(text=message)
        signature = account.sign_message(signable_message).signature

        # First verification succeeds
        result = verifier.verify_signature(wallet, signature.hex(), nonce)
        assert result is True

        # Second verification fails (nonce consumed)
        with pytest.raises(ValueError, match="Challenge not found or expired"):
            verifier.verify_signature(wallet, signature.hex(), nonce)

    def test_verify_signature_wrong_nonce_for_wallet(self, verifier, wallet_pair):
        """Signature fails if nonce doesn't match wallet."""
        wallet1 = wallet_pair["address"]
        account = wallet_pair["account"]

        # Create challenges for two different wallets
        nonce1, _, message1 = verifier.create_challenge(wallet1)
        wallet2 = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        nonce2, _, _ = verifier.create_challenge(wallet2)

        # Sign with wallet1 but use wallet2's nonce
        signable_message = encode_defunct(text=message1)
        signature = account.sign_message(signable_message).signature

        with pytest.raises(ValueError, match="does not match"):
            verifier.verify_signature(wallet1, signature.hex(), nonce2)

    def test_message_format_includes_wallet(self, verifier):
        """Challenge message includes wallet address."""
        wallet = "0x1234567890123456789012345678901234567890"

        _, _, message = verifier.create_challenge(wallet)

        assert wallet in message

    def test_message_format_includes_timestamp(self, verifier):
        """Challenge message includes timestamp."""
        wallet = "0x1234567890123456789012345678901234567890"

        _, _, message = verifier.create_challenge(wallet)

        assert "Timestamp:" in message or "timestamp" in message.lower()

    def test_message_format_includes_nonce(self, verifier):
        """Challenge message includes nonce."""
        wallet = "0x1234567890123456789012345678901234567890"

        nonce, _, message = verifier.create_challenge(wallet)

        assert nonce in message

    def test_challenge_expiration_is_future(self, verifier):
        """Challenge expiration is in the future."""
        wallet = "0x1234567890123456789012345678901234567890"

        _, expires_at, _ = verifier.create_challenge(wallet)

        now = datetime.now(timezone.utc)
        assert expires_at > now
        # Should be roughly 5 minutes from now (allow 10 second tolerance)
        diff = (expires_at - now).total_seconds()
        assert 290 < diff < 310  # ~5 minutes
