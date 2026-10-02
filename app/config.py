from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = "Echo"
    environment: str = "development"
    database_url: str = Field(default="sqlite+aiosqlite:///./data/echo.db")

    model_provider: str = Field(default="gemini")
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    model_request_timeout_seconds: int = 25
    
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    telegram_bot_token: str | None = None
    telegram_webhook_url: str | None = None
    echo_api_base_url: str = "http://127.0.0.1:8000"

    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"

    # Speech-to-text (voice pipeline)
    stt_provider: str = "mock"
    stt_api_key: str | None = None
    stt_model: str | None = None
    stt_request_timeout_seconds: int = 25

    # Text-to-speech (voice pipeline)
    tts_provider: str = "mock"
    tts_api_key: str | None = None
    tts_model: str | None = None
    tts_voice: str | None = None
    tts_request_timeout_seconds: int = 25

    # Shared Spitch configuration (used when STT_PROVIDER/TTS_PROVIDER=spitch)
    spitch_api_key: str | None = None
    spitch_stt_language: str = "en"
    spitch_tts_language: str = "en"
    spitch_tts_voice: str = "lucy"
    spitch_tts_speed: float = Field(default=1.0, ge=0.7, le=1.2)
    spitch_max_retries: int = Field(default=2, ge=0, le=5)

    # Audio output format for /voice
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    max_voice_upload_mb: int = 5

    @property
    def effective_stt_api_key(self) -> str | None:
        """Allow Groq STT to reuse the existing Groq credential."""
        return self.stt_api_key or self.groq_api_key

    google_calendar_provider: str = "google"
    google_calendar_id: str = "primary"
    google_calendar_credentials_file: str | None = None
    google_calendar_token_file: str = "data/google-calendar-token.json"
    google_calendar_client_secrets_file: str | None = None
    google_calendar_service_account_subject: str | None = None

    google_gmail_client_secrets_file: str | None = None
    google_gmail_token_file: str = "data/google-gmail-token.json"

    default_timezone: str = "Africa/Lagos"

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlite_path(self) -> Path | None:
        if not self.database_url.startswith("sqlite"):
            return None
        raw_path = self.database_url.rsplit("///", maxsplit=1)[-1]
        return Path(raw_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
