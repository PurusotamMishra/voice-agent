"""Runtime settings from env / .env (standards §1: no os.getenv elsewhere)."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://voice:voice@localhost:5433/voice"
    data_dir: Path = Path("data")
    ranking_config: Path = Path("config/ranking.yaml")
    turn_log_path: Path = Path("logs/turns.jsonl")

    llm_provider: Literal["groq", "gemini"] = "groq"
    llm_fallback_provider: Literal["groq", "gemini", "none"] = "gemini"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash-lite"


def get_settings() -> Settings:
    return Settings()
