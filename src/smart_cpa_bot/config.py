"""Application configuration primitives."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class LLMConfig(BaseModel):
    model: str = Field(default="gpt-oss-20b")
    endpoint: str = Field(default="http://127.0.0.1:11434/api/chat")
    temperature: float = Field(default=0.4)
    max_tokens: int = Field(default=500)
    timeout: float = Field(default=30.0)


class BotConfig(BaseModel):
    token: SecretStr = Field(default=SecretStr("stub-token"))
    name: str = Field(default="bot")
    llm_enabled: bool = Field(default=False)


class SaleadsConfig(BaseModel):
    base_url: str = Field(default="https://saleads.pro/api/v1")
    token: SecretStr = Field(default=SecretStr("stub-saleads-token"))
    default_stand_uuid: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    database_url: str = Field(default="sqlite+aiosqlite:///./smart_cpa.db")
    public_base_url: str = Field(default="http://127.0.0.1:8000")
    primary_bot: BotConfig = Field(default_factory=BotConfig)
    offers_bot: BotConfig = Field(default_factory=BotConfig)
    admin_ids: Sequence[int] = Field(default_factory=list)
    saleads: SaleadsConfig = Field(default_factory=SaleadsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    referral_bonus_fixed: int = 200
    referral_bonus_percent: float = 0.2
    payout_minimum: int = Field(default=700)
    payout_currency: str = Field(default="RUB")
    webhook_secret: str = Field(default="change-me")
    leaderboard_size: int = Field(default=50)


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()


settings = get_settings()
