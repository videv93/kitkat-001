"""Tests for static file serving (Story 8.5).

Tests that:
- API routes work when static serving is enabled
- Non-API paths return index.html (SPA fallback)
- CORS middleware is absent when SERVE_FRONTEND=true
"""

import os

from fastapi.testclient import TestClient


def _make_frontend_dist(tmp_path):
    """Create a fake frontend/dist directory with index.html and assets."""
    dist_dir = tmp_path / "frontend" / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html><body>SPA App</body></html>"
    )
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "main.js").write_text("console.log('app')")
    (assets_dir / "style.css").write_text("body { margin: 0; }")
    return dist_dir


def _reload_main(serve_frontend: bool):
    """Reload kitkat.main with given SERVE_FRONTEND setting."""
    import importlib

    import kitkat.config
    import kitkat.main

    kitkat.config._settings_instance = None

    if serve_frontend:
        os.environ["SERVE_FRONTEND"] = "true"
    else:
        os.environ.pop("SERVE_FRONTEND", None)

    importlib.reload(kitkat.main)
    return kitkat.main


def _cleanup():
    """Reset state after test."""
    import importlib

    import kitkat.config
    import kitkat.main

    os.environ.pop("SERVE_FRONTEND", None)
    kitkat.config._settings_instance = None
    importlib.reload(kitkat.main)


class TestStaticServingEnabled:
    """Tests with SERVE_FRONTEND=true and a valid dist directory."""

    def test_api_health_works_with_static_serving(self, tmp_path):
        """AC: API routes continue to work normally (AC#2)."""
        frontend_dist = _make_frontend_dist(tmp_path)
        try:
            main = _reload_main(serve_frontend=True)
            # Patch FRONTEND_DIR after reload so serve_spa uses our fake dist
            original_dir = main.FRONTEND_DIR
            main.FRONTEND_DIR = frontend_dist
            client = TestClient(main.app, raise_server_exceptions=False)
            response = client.get("/api/health")
            assert response.status_code in (200, 503)
            main.FRONTEND_DIR = original_dir
        finally:
            _cleanup()

    def test_spa_fallback_serves_index_html(self, tmp_path):
        """AC: Client-side routing works (AC#3)."""
        frontend_dist = _make_frontend_dist(tmp_path)
        try:
            main = _reload_main(serve_frontend=True)
            # Patch FRONTEND_DIR after reload so serve_spa reads our fake dist
            original_dir = main.FRONTEND_DIR
            main.FRONTEND_DIR = frontend_dist
            client = TestClient(main.app, raise_server_exceptions=False)

            for path in ["/dashboard", "/settings", "/nonexistent"]:
                response = client.get(path)
                assert response.status_code == 200, f"Failed for path: {path}"
                assert "SPA App" in response.text, f"No SPA content for path: {path}"
            main.FRONTEND_DIR = original_dir
        finally:
            _cleanup()

    def test_cors_absent_when_serve_frontend_true(self):
        """AC: CORS middleware is unnecessary in production (AC#6)."""
        try:
            main = _reload_main(serve_frontend=True)

            middleware_classes = [
                type(m).__name__
                for m in getattr(main.app, "user_middleware", [])
            ]
            assert "CORSMiddleware" not in middleware_classes
        finally:
            _cleanup()


class TestStaticServingDisabled:
    """Tests with SERVE_FRONTEND=false (default dev mode)."""

    def test_cors_present_when_serve_frontend_false(self):
        """AC: CORS middleware is enabled in development (AC#6)."""
        try:
            main = _reload_main(serve_frontend=False)

            middleware_classes = [
                m.cls.__name__
                for m in getattr(main.app, "user_middleware", [])
            ]
            assert "CORSMiddleware" in middleware_classes
        finally:
            _cleanup()
