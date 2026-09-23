"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings for the Kalshi trading process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    kalshi_env: Literal["demo", "prod"] = Field(default="demo", validation_alias="KALSHI_ENV")
    kalshi_key_id: str = Field(default="", validation_alias="KALSHI_KEY_ID")
    kalshi_private_key_path: str = Field(default="", validation_alias="KALSHI_PRIVATE_KEY_PATH")
    max_daily_loss_usd: float = Field(default=100.0, gt=0, validation_alias="MAX_DAILY_LOSS_USD")
    max_position_size: int = Field(default=10, gt=0, validation_alias="MAX_POSITION_SIZE")

    @property
    def base_url(self) -> str:
        """Return the API base URL associated with the selected environment."""

        if self.kalshi_env == "prod":
            return "https://api.elections.kalshi.com/trade-api/v2"
        return "https://demo-api.kalshi.co/trade-api/v2"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one process-wide, validated settings instance."""

    return Settings()
