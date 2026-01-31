"""Unit tests for health endpoint test_mode reporting.

Story 3.1: Test Mode Feature Flag - AC#5
Tests that /api/health endpoint includes test_mode flag in response.
"""

import os

import pytest
from fastapi.testclient import TestClient

from kitkat.main import app


class TestHealthEndpoint:
    """Test suite for health endpoint test_mode reporting."""

    def test_health_endpoint_returns_test_mode_true(self):
        """Test that health endpoint returns test_mode=true when enabled.

        AC#5: Health endpoint response includes test_mode field with correct value
        """
        # Set test mode
        os.environ["TEST_MODE"] = "true"

        try:
            # Reset singleton to ensure fresh settings load
            import kitkat.config
            kitkat.config._settings_instance = None

            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert "test_mode" in data
            assert data["test_mode"] is True
            assert data["status"] == "healthy"
            assert "timestamp" in data
        finally:
            os.environ.pop("TEST_MODE", None)
            import kitkat.config
            kitkat.config._settings_instance = None

    def test_health_endpoint_returns_test_mode_false(self):
        """Test that health endpoint returns test_mode=false when disabled.

        AC#5: Health endpoint response includes test_mode=false in production
        """
        # Ensure test mode is false
        old_value = os.environ.pop("TEST_MODE", None)

        try:
            # Reset singleton to ensure fresh settings load
            import kitkat.config
            kitkat.config._settings_instance = None

            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert "test_mode" in data
            assert data["test_mode"] is False
            assert data["status"] == "healthy"
            assert "timestamp" in data
        finally:
            if old_value:
                os.environ["TEST_MODE"] = old_value
            import kitkat.config
            kitkat.config._settings_instance = None

    def test_health_endpoint_response_format(self):
        """Test that health endpoint response has correct format and all fields.

        AC#5: Response includes status, test_mode, and timestamp
        """
        os.environ["TEST_MODE"] = "false"

        try:
            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()

            # Verify all required fields
            assert "status" in data
            assert "test_mode" in data
            assert "timestamp" in data

            # Verify field types
            assert isinstance(data["status"], str)
            assert isinstance(data["test_mode"], bool)
            assert isinstance(data["timestamp"], str)
        finally:
            os.environ.pop("TEST_MODE", None)
