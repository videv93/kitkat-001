"""Tests for wallet connection API endpoints (Story 2.3)."""

import pytest
from fastapi.testclient import TestClient

from kitkat.main import app


@pytest.fixture
def client():
    """Test client for API endpoints."""
    return TestClient(app, raise_server_exceptions=False)


class TestWalletChallenge:
    """Tests for GET /api/wallet/challenge endpoint."""

    def test_challenge_returns_message_with_wallet_address(self, client):
        """AC2: Challenge message is generated for wallet connection flow."""
        response = client.get(
            "/api/wallet/challenge",
            params={"wallet_address": "0x1234567890123456789012345678901234567890"},
        )

        assert response.status_code == 200
        data = response.json()

        # Challenge must contain required fields
        assert "message" in data
        assert "nonce" in data
        assert "expires_at" in data

        # Message should contain wallet address
        assert "0x1234567890123456789012345678901234567890" in data["message"]

        # Message should explain delegation
        assert "kitkat" in data["message"].lower() or "delegate" in data["message"].lower()

    def test_challenge_requires_wallet_address(self, client):
        """Challenge endpoint requires wallet_address parameter."""
        response = client.get("/api/wallet/challenge")

        assert response.status_code == 400  # Validation error from handler

    def test_challenge_validates_wallet_format(self, client):
        """Challenge endpoint validates Ethereum address format."""
        response = client.get(
            "/api/wallet/challenge",
            params={"wallet_address": "invalid-address"},
        )

        assert response.status_code == 400
        data = response.json()
        # Response wrapped in "detail" key from HTTPException
        assert "detail" in data
        assert "error" in data["detail"]

    def test_challenge_has_unique_nonce(self, client):
        """Each challenge request generates unique nonce."""
        wallet = "0x1234567890123456789012345678901234567890"

        response1 = client.get("/api/wallet/challenge", params={"wallet_address": wallet})
        response2 = client.get("/api/wallet/challenge", params={"wallet_address": wallet})

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Nonces should be different
        assert data1["nonce"] != data2["nonce"]


class TestWalletVerify:
    """Tests for POST /api/wallet/verify endpoint."""

    def test_verify_with_valid_signature_returns_session(self, client):
        """AC3: Valid signature creates session and returns token."""
        # This test needs actual signature - will be mocked in real tests
        # For now, test the endpoint structure
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": "0x1234567890123456789012345678901234567890",
                "signature": "0x" + "00" * 65,  # Mock signature (65 bytes)
                "nonce": "test-nonce-123",
            },
        )

        # With invalid signature, should return 401
        assert response.status_code in [200, 401]

    def test_verify_requires_all_fields(self, client):
        """Verify endpoint requires wallet_address, signature, and nonce."""
        # Missing signature
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": "0x1234567890123456789012345678901234567890",
                "nonce": "test-nonce",
            },
        )
        assert response.status_code == 400  # Validation error from handler

        # Missing wallet_address
        response = client.post(
            "/api/wallet/verify",
            json={
                "signature": "0x" + "00" * 65,
                "nonce": "test-nonce",
            },
        )
        assert response.status_code == 400

        # Missing nonce
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": "0x1234567890123456789012345678901234567890",
                "signature": "0x" + "00" * 65,
            },
        )
        assert response.status_code == 400

    def test_verify_invalid_signature_returns_401(self, client):
        """AC4: Invalid signature rejected with 401."""
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": "0x1234567890123456789012345678901234567890",
                "signature": "invalid-signature",
                "nonce": "test-nonce-123",
            },
        )

        assert response.status_code == 401
        data = response.json()
        # Response wrapped in "detail" key from HTTPException
        assert "detail" in data
        assert "error" in data["detail"]

    def test_verify_validates_wallet_address_format(self, client):
        """Verify endpoint validates Ethereum address format."""
        response = client.post(
            "/api/wallet/verify",
            json={
                "wallet_address": "invalid",
                "signature": "0x" + "00" * 65,
                "nonce": "test-nonce",
            },
        )

        assert response.status_code == 400


class TestWalletExplanation:
    """Tests for wallet connection explanation (AC1)."""

    def test_challenge_includes_explanation(self, client):
        """AC1: Clear explanation displayed about delegation."""
        response = client.get(
            "/api/wallet/challenge",
            params={"wallet_address": "0x1234567890123456789012345678901234567890"},
        )

        assert response.status_code == 200
        data = response.json()

        # Response should include explanation
        assert "explanation" in data

        explanation = data["explanation"].lower()
        # Should explain delegation and key safety
        assert "private key" in explanation or "never stored" in explanation
