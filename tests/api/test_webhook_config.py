"""Tests for webhook URL retrieval endpoint (Story 2.4)."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_get_webhook_url_authenticated(
    client: TestClient, test_user_session_headers: dict
):
    """Test retrieving webhook URL for authenticated user (AC2)."""
    response = client.get(
        "/api/config/webhook",
        headers=test_user_session_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify URL format (AC2)
    assert "webhook_url" in data
    assert data["webhook_url"].startswith("http")
    assert "/api/webhook" in data["webhook_url"]
    assert "token=" in data["webhook_url"]

    # Verify payload format documentation (AC2)
    assert "payload_format" in data
    assert "required_fields" in data["payload_format"]
    assert "optional_fields" in data["payload_format"]
    assert "example" in data["payload_format"]

    # Verify TradingView setup instructions (AC2)
    assert "tradingview_setup" in data
    assert "alert_name" in data["tradingview_setup"]
    assert "webhook_url" in data["tradingview_setup"]
    assert "message_template" in data["tradingview_setup"]

    # Verify required fields are documented
    assert "symbol" in data["payload_format"]["required_fields"]
    assert "side" in data["payload_format"]["required_fields"]
    assert "size" in data["payload_format"]["required_fields"]


@pytest.mark.asyncio
async def test_get_webhook_url_unauthenticated(client: TestClient):
    """Test webhook URL endpoint rejects unauthenticated requests (AC2)."""
    response = client.get("/api/config/webhook")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_payload_format_includes_example(
    client: TestClient, test_user_session_headers: dict
):
    """Test payload format response includes working example (AC2)."""
    response = client.get(
        "/api/config/webhook",
        headers=test_user_session_headers,
    )

    assert response.status_code == 200
    data = response.json()

    example = data["payload_format"]["example"]

    # Example should have required fields
    assert "symbol" in example
    assert "side" in example
    assert "size" in example

    # Example values should be reasonable
    assert example["side"] in ["buy", "sell"]
    assert float(example["size"]) > 0


@pytest.mark.asyncio
async def test_webhook_url_format_correct(
    client: TestClient, test_user_session_headers: dict
):
    """Test webhook URL has correct format with token parameter."""
    response = client.get(
        "/api/config/webhook",
        headers=test_user_session_headers,
    )

    assert response.status_code == 200
    data = response.json()

    webhook_url = data["webhook_url"]

    # Must contain the token parameter
    assert "?token=" in webhook_url
    # Token should be non-empty
    token_part = webhook_url.split("?token=")[1]
    assert len(token_part) > 0


@pytest.mark.asyncio
async def test_tradingview_setup_has_all_fields(
    client: TestClient, test_user_session_headers: dict
):
    """Test TradingView setup includes all required fields (AC2)."""
    response = client.get(
        "/api/config/webhook",
        headers=test_user_session_headers,
    )

    assert response.status_code == 200
    data = response.json()

    tv_setup = data["tradingview_setup"]

    # Must have alert name
    assert "alert_name" in tv_setup
    assert len(tv_setup["alert_name"]) > 0

    # Must have webhook URL
    assert "webhook_url" in tv_setup
    assert "http" in tv_setup["webhook_url"]

    # Must have message template
    assert "message_template" in tv_setup
    assert "{" in tv_setup["message_template"]  # Must contain JSON-like template
