"""Integration tests for health endpoint (Story 4.1).

Tests the GET /api/health endpoint including response format,
authentication (unauthenticated), and field validation.

Story 4.1: Health Service & DEX Status
- AC#4: Health endpoint returns all required fields
- AC#4: Endpoint is unauthenticated (standard pattern)
"""

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from kitkat.adapters.base import DEXAdapter, HealthStatus
from kitkat.main import app
from kitkat.services.health import HealthService


def create_health_status(
    dex_id: str = "mock",
    status: str = "healthy",
    connected: bool = True,
    latency_ms: int = 50,
    error_message: Optional[str] = None,
) -> HealthStatus:
    """Helper to create HealthStatus with all required fields."""
    return HealthStatus(
        dex_id=dex_id,
        status=status,
        connected=connected,
        latency_ms=latency_ms,
        last_check=datetime.now(timezone.utc),
        error_message=error_message,
    )


@pytest.fixture(autouse=True)
def reset_health_service_singleton():
    """Reset health service singleton before and after each test."""
    import kitkat.api.deps

    kitkat.api.deps._health_service = None
    yield
    kitkat.api.deps._health_service = None


@pytest.fixture
def mock_adapter():
    """Create a mock DEX adapter."""
    adapter = AsyncMock(spec=DEXAdapter)
    adapter.dex_id = "mock"
    adapter.health_check = AsyncMock()
    return adapter


@pytest.fixture
def mock_extended_adapter():
    """Create a mock Extended adapter."""
    adapter = AsyncMock(spec=DEXAdapter)
    adapter.dex_id = "extended"
    adapter.health_check = AsyncMock()
    return adapter


@pytest.fixture
def test_client(mock_adapter):
    """Create test client with mocked health service."""
    # Mock the app state with adapters
    app.state.adapters = [mock_adapter]
    return TestClient(app)


class TestHealthEndpointBasic:
    """Test basic health endpoint functionality."""

    def test_health_endpoint_returns_200(self, test_client, mock_adapter):
        """Test that health endpoint returns 200 OK (AC#4)."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")

        assert response.status_code == 200

    def test_health_endpoint_unauthenticated(self, test_client, mock_adapter):
        """Test that health endpoint is unauthenticated (AC#4)."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        # Should work without any authentication headers
        response = test_client.get("/api/health")

        assert response.status_code == 200

    def test_health_endpoint_returns_json(self, test_client, mock_adapter):
        """Test that health endpoint returns JSON response."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        assert isinstance(data, dict)


class TestHealthResponseFormat:
    """Test health endpoint response format (AC#4)."""

    def test_response_has_status_field(self, test_client, mock_adapter):
        """Test response includes 'status' field."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "offline")

    def test_response_has_test_mode_flag(self, test_client, mock_adapter):
        """Test response includes 'test_mode' flag (AC#4)."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        assert "test_mode" in data
        assert isinstance(data["test_mode"], bool)

    def test_response_has_uptime_seconds(self, test_client, mock_adapter):
        """Test response includes 'uptime_seconds' (AC#4)."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int)
        assert data["uptime_seconds"] >= 0

    def test_response_has_dex_status(self, test_client, mock_adapter):
        """Test response includes 'dex_status' dict (AC#4)."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        assert "dex_status" in data
        assert isinstance(data["dex_status"], dict)

    def test_response_has_timestamp(self, test_client, mock_adapter):
        """Test response includes 'timestamp' in ISO format (AC#4)."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        assert "timestamp" in data
        # Should be ISO format string
        assert isinstance(data["timestamp"], str)
        # Verify it's valid ISO format
        datetime.fromisoformat(data["timestamp"])


class TestDEXStatusStructure:
    """Test dex_status response structure (AC#4)."""

    def test_dex_status_includes_adapter_id(
        self, test_client, mock_adapter, mock_extended_adapter
    ):
        """Test dex_status has entry for each adapter."""
        app.state.adapters = [mock_adapter, mock_extended_adapter]
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )
        mock_extended_adapter.health_check.return_value = create_health_status(
            dex_id="extended", status="healthy", latency_ms=45
        )

        client = TestClient(app)
        response = client.get("/api/health")
        data = response.json()

        dex_status = data["dex_status"]
        assert "mock" in dex_status
        assert "extended" in dex_status

    def test_dex_status_entry_has_status(self, test_client, mock_adapter):
        """Test each dex_status entry has 'status' field."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        dex_entry = data["dex_status"]["mock"]
        assert "status" in dex_entry
        assert dex_entry["status"] in ("healthy", "degraded", "offline")

    def test_dex_status_entry_has_latency_ms(self, test_client, mock_adapter):
        """Test each dex_status entry has 'latency_ms' field."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        dex_entry = data["dex_status"]["mock"]
        assert "latency_ms" in dex_entry
        assert dex_entry["latency_ms"] is None or isinstance(dex_entry["latency_ms"], int)

    def test_dex_status_entry_has_error_count(self, test_client, mock_adapter):
        """Test each dex_status entry has 'error_count' field."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        dex_entry = data["dex_status"]["mock"]
        assert "error_count" in dex_entry
        assert isinstance(dex_entry["error_count"], int)
        assert dex_entry["error_count"] >= 0

    def test_dex_status_entry_has_last_successful(self, test_client, mock_adapter):
        """Test each dex_status entry has 'last_successful' field."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        dex_entry = data["dex_status"]["mock"]
        assert "last_successful" in dex_entry
        # Should be ISO format string or null
        if dex_entry["last_successful"] is not None:
            datetime.fromisoformat(dex_entry["last_successful"])


class TestHealthStatusValues:
    """Test various health status values returned by endpoint."""

    def test_healthy_status(self, test_client, mock_adapter):
        """Test endpoint returns 'healthy' status."""
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )

        response = test_client.get("/api/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert data["dex_status"]["mock"]["status"] == "healthy"

    def test_degraded_status(self, test_client, mock_adapter, mock_extended_adapter):
        """Test endpoint returns 'degraded' status when one adapter fails."""
        app.state.adapters = [mock_adapter, mock_extended_adapter]
        mock_adapter.health_check.return_value = create_health_status(
            dex_id="mock", status="healthy", latency_ms=50
        )
        mock_extended_adapter.health_check.side_effect = Exception("Failed")

        client = TestClient(app)
        response = client.get("/api/health")
        data = response.json()

        assert data["status"] == "degraded"

    def test_offline_status(self, test_client, mock_adapter):
        """Test endpoint returns 'offline' status when all adapters fail."""
        mock_adapter.health_check.side_effect = Exception("Failed")

        response = test_client.get("/api/health")
        data = response.json()

        assert data["status"] == "offline"

    def test_offline_adapter_has_no_latency(self, test_client, mock_adapter):
        """Test offline adapter has null latency_ms."""
        mock_adapter.health_check.side_effect = Exception("Failed")

        response = test_client.get("/api/health")
        data = response.json()

        assert data["dex_status"]["mock"]["latency_ms"] is None

    def test_offline_adapter_has_no_last_successful(self, test_client, mock_adapter):
        """Test offline adapter has null last_successful."""
        mock_adapter.health_check.side_effect = Exception("Failed")

        response = test_client.get("/api/health")
        data = response.json()

        assert data["dex_status"]["mock"]["last_successful"] is None


class TestErrorCounting:
    """Test error counting in health response."""

    def test_first_error_counted(self, test_client, mock_adapter):
        """Test first error is counted."""
        mock_adapter.health_check.side_effect = Exception("Failed")

        response = test_client.get("/api/health")
        data = response.json()

        assert data["dex_status"]["mock"]["error_count"] == 1

    def test_multiple_errors_counted(self, test_client, mock_adapter):
        """Test multiple errors are counted."""
        mock_adapter.health_check.side_effect = Exception("Failed")

        # First check
        test_client.get("/api/health")
        # Second check
        response = test_client.get("/api/health")
        data = response.json()

        assert data["dex_status"]["mock"]["error_count"] == 2


class TestEmptyAdapterList:
    """Test health endpoint with no adapters configured."""

    def test_empty_adapters_returns_healthy(self):
        """Test that endpoint returns healthy when no adapters configured."""
        app.state.adapters = []
        client = TestClient(app)

        response = client.get("/api/health")
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "healthy"
        assert data["dex_status"] == {}
