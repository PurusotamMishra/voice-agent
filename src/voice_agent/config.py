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
    client_timings_path: Path = Path("logs/client_timings.jsonl")

    llm_provider: Literal["groq", "gemini"] = "groq"
    llm_fallback_provider: Literal["groq", "gemini", "none"] = "gemini"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_compose_model: str | None = None  # N6: composer on its own token bucket
    llm_reasoning_effort: Literal["low", "medium", "high"] = "low"  # N6: gpt-oss only
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash-lite"

    groq_stt_model: str = "whisper-large-v3"  # H2
    sarvam_api_key: SecretStr | None = None
    sarvam_stt_model: str = "saaras:v3"
    sarvam_stt_mode: Literal["translit", "codemix", "transcribe"] = "translit"  # N3

    elevenlabs_api_key: SecretStr | None = None
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model: str = "eleven_flash_v2_5"  # H3
    tts_mode: Literal["sentence", "whole"] = "sentence"  # N2 / J5

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"


def get_settings() -> Settings:
    return Settings()


def key(secret: SecretStr | None) -> str | None:
    """An empty `KEY=` line in .env yields SecretStr(''): treat it as unset."""
    if secret is None or not secret.get_secret_value().strip():
        return None
    return secret.get_secret_value()
