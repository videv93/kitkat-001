"""Application configuration using Pydantic Settings."""

from pathlib import Path

from pydantic import Field, field_validator
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
    extended_stark_private_key: str = ""  # For SNIP12 order signing
    extended_account_address: str = ""  # Starknet account address
    extended_network: str = "testnet"  # "mainnet" or "testnet"

    @property
    def extended_api_base_url(self) -> str:
        """Get Extended API base URL based on network."""
        if self.extended_network == "mainnet":
            return "https://api.starknet.extended.exchange/api/v1"
        return "https://api.starknet.sepolia.extended.exchange/api/v1"

    @property
    def extended_ws_url(self) -> str:
        """Get Extended WebSocket URL based on network."""
        if self.extended_network == "mainnet":
            return "wss://api.starknet.extended.exchange/stream.extended.exchange/v1"
        return "wss://starknet.sepolia.extended.exchange/stream.extended.exchange/v1"

    # Feature Flags
    test_mode: bool = False
    mock_fail_rate: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Mock adapter failure rate (0-100%) for testing error paths. Default: 0 (always succeed)",
    )

    # Application host for URL generation (Story 2.4)
    app_host: str = "localhost:8000"

    # Graceful shutdown (Story 2.11)
    shutdown_grace_period_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Grace period in seconds to wait for in-flight orders during shutdown (min: 5, max: 300)",
    )

    # Database
    database_url: str = ""

    @field_validator("app_host", mode="before")
    @classmethod
    def validate_app_host(cls, v: str) -> str:
        """Validate app_host configuration (Story 2.4).

        Args:
            v: The app_host value to validate

        Returns:
            str: The validated app_host

        Raises:
            ValueError: If app_host format is invalid
        """
        if not v:
            raise ValueError("app_host cannot be empty")

        # Allow formats like:
        # - localhost:8000
        # - 127.0.0.1:8000
        # - example.com
        # - api.example.com:3000
        # Don't allow full URLs (those belong in X-Forwarded-Host header)
        if v.startswith(("http://", "https://")):
            raise ValueError(
                "app_host should be a domain/host only (e.g., 'example.com' or 'localhost:8000'), "
                "not a full URL. Use X-Forwarded-Host header for reverse proxy scenarios."
            )

        return v

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
