"""Application configuration using Pydantic Settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Auth
    webhook_token: str

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # DEX Credentials
    extended_api_key: str = ""
    extended_api_secret: str = ""

    # Feature Flags
    test_mode: bool = False

    # Application host for URL generation (Story 2.4)
    app_host: str = "localhost:8000"

    # Database
    database_url: str = ""

    def __init__(self, **data):
        """Initialize settings with computed defaults."""
        super().__init__(**data)
        # Use absolute path for database if not overridden
        if not self.database_url:
            db_path = Path(__file__).parent.parent.parent / "kitkat.db"
            self.database_url = f"sqlite+aiosqlite:///{db_path}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Module-level singleton instance
_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Get application settings instance (singleton pattern)."""
    global _settings_instance
    if _settings_instance is None:
        try:
            _settings_instance = Settings()
        except Exception as e:
            msg = (
                "Failed to initialize settings. "
                "Ensure WEBHOOK_TOKEN is set in environment."
            )
            raise RuntimeError(msg) from e
    return _settings_instance
