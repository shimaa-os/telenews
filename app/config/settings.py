"""Environment-based application settings."""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    telegram_bot_token: SecretStr | None = Field(
        default=None, alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")
    api_bearer_token: SecretStr | None = Field(default=None, alias="API_BEARER_TOKEN")
    timezone: str = Field(default="Africa/Cairo", alias="TIMEZONE")
    news_lookback_hours: int = Field(
        default=24, ge=1, le=168, alias="NEWS_LOOKBACK_HOURS"
    )
    max_news_items: int = Field(default=5, ge=1, le=10, alias="MAX_NEWS_ITEMS")
    openai_model: str = Field(default="gpt-5-mini", alias="OPENAI_MODEL")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    request_timeout_seconds: float = Field(
        default=20.0, gt=0, le=120, alias="REQUEST_TIMEOUT_SECONDS"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown IANA timezone: {value}") from exc
        return value

    @field_validator("openai_model", mode="before")
    @classmethod
    def default_blank_model(cls, value: object) -> str:
        if value is None or not str(value).strip():
            return "gpt-5-mini"
        return str(value).strip()

    @field_validator("telegram_chat_id", "openai_base_url", mode="before")
    @classmethod
    def normalize_optional_string(cls, value: object) -> str | None:
        if value is None or not str(value).strip():
            return None
        return str(value).strip()

    @property
    def zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def require_openai_key(self) -> str:
        if self.openai_api_key is None or not self.openai_api_key.get_secret_value():
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return self.openai_api_key.get_secret_value()

    def require_telegram_credentials(self) -> tuple[str, str]:
        if self.telegram_bot_token is None or not self.telegram_bot_token.get_secret_value():
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        if not self.telegram_chat_id:
            raise RuntimeError("TELEGRAM_CHAT_ID is not configured")
        return self.telegram_bot_token.get_secret_value(), self.telegram_chat_id


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
