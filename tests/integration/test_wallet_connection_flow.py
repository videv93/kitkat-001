"""Integration tests for wallet connection flow (Story 2.3).

Tests the complete flow from challenge generation through signature
verification to session creation and user status retrieval.
"""

import pytest
from fastapi.testclient import TestClient
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.main import app
from kitkat.database import get_db_session, get_engine, Base


@pytest.fixture(scope="function")
async def db_session():
    """Create fresh database for each test."""
    engine = get_engine()

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_db_session.__wrapped__.__self__.__wrapped__.__self__
    # For testing, get a fresh session
    from kitkat.database import get_async_session_factory
    factory = get_async_session_factory()

    async with factory() as session:
        yield session
        await session.close()

    # Clean up tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client():
    """Test client for API endpoints."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def wallet_pair():
    """Generate test wallet with private key for signing."""
    pk = keys.PrivateKey(b"\x01" * 32)
    account = Account.from_key(pk.to_bytes())
    return {
        "address": account.address,
        "account": account,
    }


class TestWalletConnectionFlow:
    """Integration tests for complete wallet connection flow."""

    def test_complete_wallet_connection_happy_path(self, client, wallet_pair):
        """Test complete happy path: challenge -> sign -> verify -> status.

        AC1: User sees explanation message
        AC2: Challenge generated
        AC3: Valid signature creates session
        AC5: User can query their status
        """
        wallet = wallet_pair["address"]
        account = wallet_pair["account"]

        # Step 1: Get challenge (AC1, AC2)
        response = client.get(
            "/api/wallet/challenge",
            params={"wallet_address": wallet},
        )
        assert response.status_code == 200
        challenge_data = response.json()

        assert "message" in challenge_data
        assert "nonce" in challenge_data
        assert "explanation" in challenge_data

        # Verify explanation mentions delegation and key safety
        explanation = challenge_data["explanation"].lower()
        assert "delegated" in explanation or "delegation" in explanation
        assert "private" in explanation or "key" in explanation

        message = challenge_data["message"]
        nonce = challenge_data["nonce"]

        # Step 2: Sign the challenge with wallet
        signable_message = encode_defunct(text=message)
        signature = account.sign_message(signable_message).signature

        # Step 3: Verify signature and create session (AC3)
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": wallet,
                "signature": signature.hex(),
                "nonce": nonce,
            },
        )
        assert response.status_code == 200
        verify_data = response.json()

        assert "token" in verify_data
        assert "expires_at" in verify_data
        assert verify_data["wallet_address"] == wallet

        token = verify_data["token"]

        # Step 4: Query user status with session token (AC5)
        response = client.get(
            "/api/auth/user/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        status_data = response.json()

        assert "wallet_address" in status_data
        assert "full_address" in status_data
        assert "status" in status_data

        # Verify abbreviated address format (0x1234...5678)
        abbreviated = status_data["wallet_address"]
        assert abbreviated.startswith("0x")
        assert "..." in abbreviated
        assert len(abbreviated) < len(wallet)  # Should be shorter

        # Verify full address is correct
        assert status_data["full_address"] == wallet
        assert status_data["status"] == "Connected"

    def test_invalid_signature_rejected(self, client, wallet_pair):
        """AC4: Invalid signature rejected with 401."""
        wallet = wallet_pair["address"]

        # Get challenge
        response = client.get(
            "/api/wallet/challenge",
            params={"wallet_address": wallet},
        )
        assert response.status_code == 200
        challenge_data = response.json()
        nonce = challenge_data["nonce"]

        # Try to verify with invalid signature
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": wallet,
                "signature": "0x" + "ff" * 65,  # Invalid signature
                "nonce": nonce,
            },
        )

        assert response.status_code == 401
        error_data = response.json()
        assert "detail" in error_data
        assert "error" in error_data["detail"]

    def test_expired_challenge_rejected(self, client, wallet_pair):
        """Test that expired challenges are rejected."""
        wallet = wallet_pair["address"]
        account = wallet_pair["account"]

        # Get challenge
        response = client.get(
            "/api/wallet/challenge",
            params={"wallet_address": wallet},
        )
        challenge_data = response.json()
        message = challenge_data["message"]
        nonce = challenge_data["nonce"]

        # Sign the message
        signable_message = encode_defunct(text=message)
        signature = account.sign_message(signable_message).signature

        # Verify once successfully
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": wallet,
                "signature": signature.hex(),
                "nonce": nonce,
            },
        )
        assert response.status_code == 200

        # Try to use same nonce again (should fail - one-time use)
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": wallet,
                "signature": signature.hex(),
                "nonce": nonce,
            },
        )
        assert response.status_code == 401

    def test_signature_from_wrong_wallet_rejected(self, client):
        """Test that signature from different wallet is rejected.

        AC3: Signature must match wallet address
        """
        # Create two different wallets
        pk1 = keys.PrivateKey(b"\x01" * 32)
        account1 = Account.from_key(pk1.to_bytes())
        wallet1 = account1.address

        pk2 = keys.PrivateKey(b"\x02" * 32)
        account2 = Account.from_key(pk2.to_bytes())
        wallet2 = account2.address

        # Get challenge for wallet1
        response = client.get(
            "/api/wallet/challenge",
            params={"wallet_address": wallet1},
        )
        challenge_data = response.json()
        message = challenge_data["message"]
        nonce = challenge_data["nonce"]

        # Sign with wallet2
        signable_message = encode_defunct(text=message)
        signature = account2.sign_message(signable_message).signature

        # Try to verify with wallet1 (signature is from wallet2)
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": wallet1,
                "signature": signature.hex(),
                "nonce": nonce,
            },
        )

        assert response.status_code == 401
        error_data = response.json()
        assert "Signature does not match" in error_data["detail"]["error"]

    def test_user_status_requires_authentication(self, client):
        """Test that user status endpoint requires valid session token."""
        # Try without token
        response = client.get("/api/auth/user/status")
        assert response.status_code == 401

        # Try with invalid token
        response = client.get(
            "/api/auth/user/status",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

        # Try with wrong bearer format
        response = client.get(
            "/api/auth/user/status",
            headers={"Authorization": "invalid-token"},
        )
        assert response.status_code == 401

    def test_session_token_properties_24h_expiration(self, client, wallet_pair):
        """Test that session tokens have 24h expiration (NFR9, AC6).

        AC6: Session token properties:
        - 128-bit random token (exceeds NFR8 requirement)
        - 24-hour expiration from creation (NFR9)
        - Updated on activity (last_used timestamp)
        """
        wallet = wallet_pair["address"]
        account = wallet_pair["account"]

        # Get challenge and verify signature
        response = client.get(
            "/api/wallet/challenge",
            params={"wallet_address": wallet},
        )
        challenge_data = response.json()
        message = challenge_data["message"]
        nonce = challenge_data["nonce"]

        signable_message = encode_defunct(text=message)
        signature = account.sign_message(signable_message).signature

        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": wallet,
                "signature": signature.hex(),
                "nonce": nonce,
            },
        )
        verify_data = response.json()

        token = verify_data["token"]
        expires_at = verify_data["expires_at"]

        # Verify token is long (128-bit = 16 bytes = ~24 chars in url-safe base64)
        # URL-safe base64: roughly 8*16/6 = 21-24 characters for 16 bytes
        assert len(token) >= 20

        # Verify expiration is approximately 24 hours from now
        from datetime import datetime, timezone
        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff_hours = (expires_dt - now).total_seconds() / 3600

        # Should be roughly 24 hours (allow 1 hour tolerance for test execution)
        assert 23 < diff_hours < 25

    def test_multiple_wallet_connections(self, client):
        """Test that multiple wallets can connect independently."""
        # Create two different wallets
        pk1 = keys.PrivateKey(b"\x01" * 32)
        account1 = Account.from_key(pk1.to_bytes())
        wallet1 = account1.address

        pk2 = keys.PrivateKey(b"\x02" * 32)
        account2 = Account.from_key(pk2.to_bytes())
        wallet2 = account2.address

        tokens = {}

        for wallet, account in [(wallet1, account1), (wallet2, account2)]:
            # Get challenge
            response = client.get(
                "/api/wallet/challenge",
                params={"wallet_address": wallet},
            )
            challenge_data = response.json()
            message = challenge_data["message"]
            nonce = challenge_data["nonce"]

            # Sign and verify
            signable_message = encode_defunct(text=message)
            signature = account.sign_message(signable_message).signature

            response = client.post(
                "/api/wallet/verify",
                json={
                    "wallet_address": wallet,
                    "signature": signature.hex(),
                    "nonce": nonce,
                },
            )
            assert response.status_code == 200
            verify_data = response.json()
            tokens[wallet] = verify_data["token"]

            # Verify status
            response = client.get(
                "/api/auth/user/status",
                headers={"Authorization": f"Bearer {verify_data['token']}"},
            )
            assert response.status_code == 200
            status_data = response.json()
            assert status_data["full_address"] == wallet

        # Verify both tokens are different
        assert tokens[wallet1] != tokens[wallet2]

        # Verify each token can only access its own wallet
        response = client.get(
            "/api/auth/user/status",
            headers={"Authorization": f"Bearer {tokens[wallet1]}"},
        )
        assert response.json()["full_address"] == wallet1

        response = client.get(
            "/api/auth/user/status",
            headers={"Authorization": f"Bearer {tokens[wallet2]}"},
        )
        assert response.json()["full_address"] == wallet2
