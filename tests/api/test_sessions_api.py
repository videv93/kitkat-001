"""Tests for session API endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_create_session_endpoint_success(client, db_session):
    """Test POST /api/sessions with valid wallet_address."""
    # Create user first
    user_response = client.post(
        "/api/users",
        json={"wallet_address": "0x1234567890abcdef1234567890abcdef12345678"},
    )
    assert user_response.status_code == 201

    # Create session
    response = client.post(
        "/api/sessions",
        json={"wallet_address": "0x1234567890abcdef1234567890abcdef12345678"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["token"] is not None
    assert data["wallet_address"] == "0x1234567890abcdef1234567890abcdef12345678"
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_create_session_endpoint_user_not_found(client, db_session):
    """Test POST /api/sessions with non-existent wallet_address returns 404."""
    response = client.post(
        "/api/sessions",
        json={"wallet_address": "0xnonexistent1111111111111111111111111111"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_multiple_sessions_for_same_user(client, db_session):
    """Test that one user can have multiple concurrent sessions."""
    wallet = "0x1234567890abcdef1234567890abcdef12345678"

    # Create user
    client.post("/api/users", json={"wallet_address": wallet})

    # Create multiple sessions
    response1 = client.post("/api/sessions", json={"wallet_address": wallet})
    response2 = client.post("/api/sessions", json={"wallet_address": wallet})

    assert response1.status_code == 201
    assert response2.status_code == 201
    token1 = response1.json()["token"]
    token2 = response2.json()["token"]
    assert token1 != token2
