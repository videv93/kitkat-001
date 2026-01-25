"""Tests for user API endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_create_user_endpoint_success(client, db_session):
    """Test POST /api/users with valid wallet_address."""
    response = client.post(
        "/api/users",
        json={"wallet_address": "0x1234567890abcdef1234567890abcdef12345678"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["wallet_address"] == "0x1234567890abcdef1234567890abcdef12345678"
    assert data["webhook_token"] is not None
    assert data["config_data"] is not None


@pytest.mark.asyncio
async def test_create_user_endpoint_duplicate(client, db_session):
    """Test POST /api/users with duplicate wallet_address returns 409."""
    wallet = "0x1234567890abcdef1234567890abcdef12345678"

    # Create first user
    response1 = client.post("/api/users", json={"wallet_address": wallet})
    assert response1.status_code == 201

    # Try to create duplicate
    response2 = client.post("/api/users", json={"wallet_address": wallet})
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_create_user_endpoint_whitespace_stripped(client, db_session):
    """Test that wallet_address whitespace is stripped."""
    response = client.post(
        "/api/users",
        json={"wallet_address": "  0x1234567890abcdef1234567890abcdef12345678  "},
    )

    assert response.status_code == 201
    data = response.json()
    # Should be stripped
    assert data["wallet_address"] == "0x1234567890abcdef1234567890abcdef12345678"
