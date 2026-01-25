"""Signature verification service for EIP-191 personal_sign messages."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from eth_account import Account
from eth_account.messages import encode_defunct

logger = structlog.get_logger()

# Challenge expiration time (5 minutes per spec)
CHALLENGE_TTL_MINUTES = 5


class ChallengeStore:
    """In-memory store for pending challenges with automatic expiration.

    Tracks challenge nonces to prevent replay attacks. Each nonce is valid
    for CHALLENGE_TTL_MINUTES and can only be used once.
    """

    def __init__(self):
        """Initialize the challenge store."""
        self._challenges: dict[str, tuple[str, datetime, str]] = {}
        # Map of nonce -> (wallet_address, expires_at, message)

    def create_challenge(self, wallet_address: str) -> tuple[str, datetime, str]:
        """Create a new challenge for the given wallet address.

        Args:
            wallet_address: The Ethereum wallet address requesting challenge.

        Returns:
            Tuple of (nonce, expires_at, message).
        """
        nonce = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=CHALLENGE_TTL_MINUTES)

        # Format the challenge message per spec
        message = self._format_message(wallet_address, nonce, expires_at)

        # Store the challenge
        self._challenges[nonce] = (wallet_address.lower(), expires_at, message)

        # Cleanup expired challenges
        self._cleanup_expired()

        logger.info(
            "Challenge created",
            wallet_address=wallet_address[:10] + "...",
            nonce=nonce[:8] + "...",
            expires_at=expires_at.isoformat(),
        )

        return nonce, expires_at, message

    def _format_message(self, wallet_address: str, nonce: str, expires_at: datetime) -> str:
        """Format the challenge message for signing.

        Args:
            wallet_address: The wallet address.
            nonce: The unique nonce.
            expires_at: When the challenge expires.

        Returns:
            Formatted message string.
        """
        timestamp = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            f"Sign this message to authenticate with kitkat-001:\n\n"
            f"Wallet: {wallet_address}\n"
            f"Timestamp: {timestamp}\n"
            f"Nonce: {nonce}"
        )

    def get_challenge(self, nonce: str) -> Optional[tuple[str, datetime, str]]:
        """Get a pending challenge by nonce.

        Args:
            nonce: The challenge nonce.

        Returns:
            Tuple of (wallet_address, expires_at, message) or None if not found.
        """
        challenge = self._challenges.get(nonce)
        if not challenge:
            return None

        wallet_address, expires_at, message = challenge

        # Check expiration
        if expires_at < datetime.now(timezone.utc):
            del self._challenges[nonce]
            logger.info("Challenge expired", nonce=nonce[:8] + "...")
            return None

        return challenge

    def consume_challenge(self, nonce: str) -> Optional[tuple[str, datetime, str]]:
        """Get and remove a challenge (single use).

        Args:
            nonce: The challenge nonce.

        Returns:
            Tuple of (wallet_address, expires_at, message) or None if not found.
        """
        challenge = self.get_challenge(nonce)
        if challenge:
            del self._challenges[nonce]
        return challenge

    def _cleanup_expired(self) -> None:
        """Remove expired challenges from the store."""
        now = datetime.now(timezone.utc)
        expired = [
            nonce for nonce, (_, expires_at, _) in self._challenges.items()
            if expires_at < now
        ]
        for nonce in expired:
            del self._challenges[nonce]


class SignatureVerifier:
    """Service for verifying EIP-191 signatures.

    Handles challenge generation, storage, and cryptographic verification
    of Ethereum personal_sign messages.
    """

    def __init__(self, challenge_store: Optional[ChallengeStore] = None):
        """Initialize the signature verifier.

        Args:
            challenge_store: Optional challenge store instance. Creates new one if not provided.
        """
        self._challenge_store = challenge_store or ChallengeStore()

    def create_challenge(self, wallet_address: str) -> tuple[str, datetime, str]:
        """Create a challenge for the wallet to sign.

        Args:
            wallet_address: The Ethereum wallet address.

        Returns:
            Tuple of (nonce, expires_at, message).
        """
        return self._challenge_store.create_challenge(wallet_address)

    def verify_signature(
        self, wallet_address: str, signature: str, nonce: str
    ) -> bool:
        """Verify a signature against a pending challenge.

        Uses EIP-191 personal_sign verification. The signature must be from
        the wallet that requested the challenge.

        Args:
            wallet_address: The claimed wallet address.
            signature: The signature bytes as hex string (with or without 0x prefix).
            nonce: The challenge nonce.

        Returns:
            True if signature is valid and matches the wallet address.

        Raises:
            ValueError: If challenge not found, expired, or signature invalid.
        """
        log = logger.bind(
            wallet_address=wallet_address[:10] + "...",
            nonce=nonce[:8] + "...",
        )

        # Get and consume the challenge (one-time use)
        challenge = self._challenge_store.consume_challenge(nonce)
        if not challenge:
            log.warning("Challenge not found or expired")
            raise ValueError("Challenge not found or expired")

        expected_wallet, expires_at, message = challenge

        # Verify wallet address matches challenge
        if wallet_address.lower() != expected_wallet:
            log.warning(
                "Wallet address mismatch",
                expected=expected_wallet[:10] + "...",
            )
            raise ValueError("Wallet address does not match challenge")

        # Verify signature using EIP-191
        try:
            recovered_address = self._recover_address(message, signature)
        except Exception as e:
            log.warning("Signature verification failed", error=str(e))
            raise ValueError(f"Invalid signature format: {e}")

        # Compare addresses (case-insensitive)
        if recovered_address.lower() != wallet_address.lower():
            log.warning(
                "Signature mismatch",
                recovered=recovered_address[:10] + "...",
            )
            raise ValueError("Signature does not match wallet address")

        log.info("Signature verified successfully")
        return True

    def _recover_address(self, message: str, signature: str) -> str:
        """Recover the signer's address from a message and signature.

        Uses EIP-191 personal_sign format:
        \\x19Ethereum Signed Message:\\n{length}{message}

        Args:
            message: The original message that was signed.
            signature: The signature as hex string.

        Returns:
            The recovered Ethereum address.
        """
        # Ensure signature has 0x prefix
        if not signature.startswith("0x"):
            signature = "0x" + signature

        # Encode message for EIP-191
        signable_message = encode_defunct(text=message)

        # Recover address from signature
        return Account.recover_message(signable_message, signature=signature)


# Module-level singleton for challenge store (shared across requests)
_challenge_store = ChallengeStore()


def get_signature_verifier() -> SignatureVerifier:
    """Get the signature verifier instance with shared challenge store."""
    return SignatureVerifier(challenge_store=_challenge_store)
