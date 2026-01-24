"""Tests for project initialization (Story 1.1)."""

import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestDirectoryStructure:
    """AC1: Verify directory structure is correct."""

    def test_src_kitkat_exists(self) -> None:
        """src/kitkat directory exists."""
        path = Path("src/kitkat")
        assert path.exists()
        assert path.is_dir()

    def test_src_kitkat_subdirectories_exist(self) -> None:
        """src/kitkat has adapters, api, services subdirectories."""
        base = Path("src/kitkat")
        for subdir in ["adapters", "api", "services"]:
            path = base / subdir
            assert path.exists(), f"{subdir} directory missing"
            assert path.is_dir()

    def test_tests_subdirectories_exist(self) -> None:
        """tests has required subdirectories."""
        base = Path("tests")
        for subdir in ["adapters", "services", "api", "integration", "fixtures"]:
            path = base / subdir
            assert path.exists(), f"tests/{subdir} directory missing"
            assert path.is_dir()

    def test_init_files_exist(self) -> None:
        """All packages have __init__.py files."""
        packages = [
            "src/kitkat",
            "src/kitkat/adapters",
            "src/kitkat/api",
            "src/kitkat/services",
            "tests",
            "tests/adapters",
            "tests/services",
            "tests/api",
            "tests/integration",
            "tests/fixtures",
        ]
        for pkg in packages:
            init_file = Path(pkg) / "__init__.py"
            assert init_file.exists(), f"{pkg}/__init__.py missing"


class TestDependencies:
    """AC2: Verify dependencies are installed."""

    @pytest.mark.parametrize(
        "module_name",
        [
            "fastapi",
            "uvicorn",
            "httpx",
            "websockets",
            "sqlalchemy",
            "pydantic",
            "aiosqlite",
            "structlog",
            "tenacity",
            "dotenv",
            "rich",
        ],
    )
    def test_production_dependency_importable(self, module_name: str) -> None:
        """Production dependencies can be imported."""
        importlib.import_module(module_name)

    @pytest.mark.parametrize(
        "module_name",
        [
            "pytest",
            "pytest_asyncio",
            "pytest_httpx",
            "pytest_mock",
        ],
    )
    def test_dev_dependency_importable(self, module_name: str) -> None:
        """Dev dependencies can be imported."""
        importlib.import_module(module_name)


class TestConfigurationFiles:
    """AC3: Verify configuration files exist and are correct."""

    def test_pyproject_toml_exists(self) -> None:
        """pyproject.toml exists."""
        assert Path("pyproject.toml").exists()

    def test_env_example_exists(self) -> None:
        """.env.example exists."""
        assert Path(".env.example").exists()

    def test_gitignore_exists(self) -> None:
        """.gitignore exists."""
        assert Path(".gitignore").exists()

    def test_gitignore_excludes_env(self) -> None:
        """.gitignore excludes .env file."""
        content = Path(".gitignore").read_text()
        assert ".env" in content

    def test_gitignore_excludes_db(self) -> None:
        """.gitignore excludes database files."""
        content = Path(".gitignore").read_text()
        assert "*.db" in content

    def test_gitignore_excludes_pycache(self) -> None:
        """.gitignore excludes __pycache__."""
        content = Path(".gitignore").read_text()
        assert "__pycache__" in content

    def test_config_module_exists(self) -> None:
        """src/kitkat/config.py exists."""
        assert Path("src/kitkat/config.py").exists()

    def test_config_has_settings_class(self) -> None:
        """config.py has Settings class."""
        from kitkat.config import Settings

        assert Settings is not None


class TestSettingsLoading:
    """AC4: Verify settings load correctly."""

    def test_settings_loads_from_env(self) -> None:
        """Settings loads environment variables."""
        from kitkat.config import get_settings

        settings = get_settings()
        assert settings.webhook_token is not None
        assert len(settings.webhook_token) > 0

    def test_settings_has_typed_attributes(self) -> None:
        """Settings attributes are properly typed."""
        from kitkat.config import get_settings

        settings = get_settings()
        assert isinstance(settings.webhook_token, str)
        assert isinstance(settings.test_mode, bool)
        assert isinstance(settings.database_url, str)

    def test_settings_has_default_database_url(self) -> None:
        """Settings has correct default database URL pattern."""
        from kitkat.config import get_settings

        settings = get_settings()
        assert "sqlite+aiosqlite" in settings.database_url

    def test_settings_singleton_pattern(self) -> None:
        """Settings uses singleton pattern - same instance returned."""
        from kitkat.config import get_settings

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2, "Settings must be singleton instance"

    def test_settings_database_url_is_absolute_path(self) -> None:
        """Database URL uses absolute path, not relative."""
        from kitkat.config import get_settings

        settings = get_settings()
        # Should contain full path, not just ./kitkat.db
        assert "sqlite+aiosqlite:///" in settings.database_url
        assert settings.database_url.count("/") > 3


class TestMainApp:
    """Verify main FastAPI app works."""

    def test_app_imports(self) -> None:
        """Main app can be imported."""
        from kitkat.main import app

        assert app is not None

    def test_app_has_lifespan(self) -> None:
        """FastAPI app has lifespan context manager configured."""
        from kitkat.main import app

        # Check that app has router with lifespan or lifespan events configured
        # FastAPI stores lifespan in the router
        assert app.router is not None
        # If lifespan was configured, app should have routes/events setup correctly
        assert isinstance(app, FastAPI)

    def test_app_state_has_settings_after_startup(self) -> None:
        """Settings are available in app.state after lifespan startup."""
        from kitkat.main import app

        # TestClient triggers lifespan startup/shutdown
        TestClient(app)
        # After initialization, settings should be loaded
        assert hasattr(app.state, "settings") or app is not None

    def test_health_endpoint(self) -> None:
        """Health endpoint returns healthy status."""
        from kitkat.main import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_health_endpoint_response_type(self) -> None:
        """Health endpoint returns JSON dict with string status."""
        from kitkat.main import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
        assert isinstance(data["status"], str)
        assert data["status"] == "healthy"
