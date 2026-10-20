import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.fakes import FakeSTT, FakeTTS
from tests.unit.api.test_stream import FakeRunner
from voice_agent.api.app import create_app
from voice_agent.api.stream import VoiceServices
from voice_agent.config import Settings
from voice_agent.domain.ports import SttChoice


def _app(tmp_path: Path) -> TestClient:
    settings = Settings(_env_file=None, client_timings_path=tmp_path / "ct.jsonl")  # type: ignore[call-arg]

    @asynccontextmanager
    async def services(_: Settings) -> AsyncIterator[VoiceServices]:
        yield VoiceServices(
            runner=FakeRunner(), stt={"en": SttChoice(FakeSTT("Tata Ace in Pune"))}, tts=FakeTTS()
        )

    return TestClient(create_app(settings, services))


def _lines(body: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def test_session_then_typed_turn_streams_ndjson(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        sid = client.post("/api/session").json()["session_id"]
        resp = client.post("/api/turn", data={"session_id": sid, "text": "Tata Ace in Pune"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/x-ndjson")
        events = _lines(resp.text)
        assert events[0]["type"] == "transcript" and events[-1]["type"] == "done"


def test_audio_turn(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        files = {"audio": ("speech.webm", b"webm-bytes", "audio/webm")}
        resp = client.post("/api/turn", data={"session_id": "s1", "language": "en"}, files=files)
        assert _lines(resp.text)[0]["text"] == "Tata Ace in Pune"


def test_turn_without_audio_or_text_is_400(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        assert client.post("/api/turn", data={"session_id": "s1", "text": "  "}).status_code == 400


def test_bad_language_is_422(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        resp = client.post("/api/turn", data={"session_id": "s", "text": "x", "language": "fr"})
        assert resp.status_code == 422


def test_client_timings_are_logged(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        body = {"t_speech_end": 1000.0, "t_first_audio": 3500.0}
        assert client.post("/api/turn/abc/client-timings", json=body).status_code == 204
    record = json.loads((tmp_path / "ct.jsonl").read_text(encoding="utf-8"))
    assert record == {
        "turn_id": "abc",
        "t_speech_end": 1000.0,
        "t_first_audio": 3500.0,
        "speech_end_to_first_audio_ms": 2500.0,
    }


def test_state_and_health(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        assert client.get("/api/session/s9/state").json() == {"session_id": "s9"}
        health = client.get("/api/health").json()
        assert health["ok"] is True and health["stt"] == {"en": "fake-stt"}
        assert health["tts"] == "fake-tts" and health["tts_mode"] == "sentence"
