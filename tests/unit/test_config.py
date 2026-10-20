import pytest
from pydantic import SecretStr

from voice_agent.config import Settings, key


def test_database_url_default_matches_compose_host_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert ":5433/" in Settings(_env_file=None).database_url  # type: ignore[call-arg]


def test_key_treats_blank_as_missing() -> None:
    assert key(None) is None
    assert key(SecretStr("   ")) is None
    assert key(SecretStr("abc")) == "abc"


def test_voice_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TTS_MODE", "SARVAM_STT_MODE", "LLM_REASONING_EFFORT"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.tts_mode == "sentence"
    assert s.sarvam_stt_mode == "translit"
    assert s.llm_reasoning_effort == "low"
    assert s.groq_compose_model is None
