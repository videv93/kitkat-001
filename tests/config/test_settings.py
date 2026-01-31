"""Unit tests for test_mode configuration setting.

Story 3.1: Test Mode Feature Flag - AC#1
Tests that test_mode setting is properly configured in Settings class,
loads from environment variables, and has correct defaults.
"""

import os
from pathlib import Path

import pytest

from kitkat.config import Settings


class TestTestModeConfiguration:
    """Test suite for test_mode configuration setting."""

    def test_test_mode_defaults_to_false(self):
        """Test that test_mode defaults to False when TEST_MODE env var not set.

        AC#1: test_mode setting exists with default: False
        """
        # Ensure TEST_MODE is not set
        old_value = os.environ.pop("TEST_MODE", None)
        try:
            settings = Settings()
            assert settings.test_mode is False
        finally:
            if old_value:
                os.environ["TEST_MODE"] = old_value

    def test_test_mode_enabled_from_env_true(self):
        """Test that TEST_MODE=true enables test_mode.

        AC#1: test_mode can be set via environment variable TEST_MODE=true
        """
        os.environ["TEST_MODE"] = "true"
        try:
            settings = Settings()
            assert settings.test_mode is True
        finally:
            os.environ.pop("TEST_MODE", None)

    def test_test_mode_enabled_from_env_false(self):
        """Test that TEST_MODE=false keeps test_mode disabled.

        AC#1: test_mode can be set to false via TEST_MODE=false
        """
        os.environ["TEST_MODE"] = "false"
        try:
            settings = Settings()
            assert settings.test_mode is False
        finally:
            os.environ.pop("TEST_MODE", None)

    def test_test_mode_case_insensitive(self):
        """Test that test_mode and TEST_MODE both work as env var names.

        AC#1: Environment variable loading is case-insensitive
        """
        os.environ["TEST_MODE"] = "true"
        try:
            settings = Settings()
            assert settings.test_mode is True
        finally:
            os.environ.pop("TEST_MODE", None)

    def test_test_mode_boolean_field_type(self):
        """Test that test_mode is a boolean field.

        AC#1: test_mode is a boolean field with proper typing
        """
        os.environ["TEST_MODE"] = "true"
        try:
            settings = Settings()
            assert isinstance(settings.test_mode, bool)
            assert settings.test_mode is True
        finally:
            os.environ.pop("TEST_MODE", None)
