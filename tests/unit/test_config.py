import pytest

from voice_agent.config import Settings


def test_database_url_default_matches_compose_host_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert ":5433/" in Settings(_env_file=None).database_url  # type: ignore[call-arg]
