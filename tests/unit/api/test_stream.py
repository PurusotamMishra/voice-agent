import base64
from typing import Any

from tests.fakes import FakeSTT, FakeTTS
from voice_agent.api.stream import STT_FAILED_TEXT, TurnInput, VoiceServices, run_turn
from voice_agent.domain.ports import ProviderError, SttChoice
from voice_agent.graph.runner import TurnResult
from voice_agent.response.schema import ComposedResponse, ItemSentence, Verdict


def _result(session_id: str, text: str) -> TurnResult:
    response = ComposedResponse(
        intro="Here are the best matches.",
        items=[ItemSentence(listing_id="A", text="First, the Tata Ace at ₹4 lakh.")],
        closing="Want details?",
    )
    return TurnResult(
        session_id=session_id, turn=1, text=text, intent="search", language="en", route="search",
        slots={"city": "pune"}, slot_diff={"city": [None, "pune"]}, filters={"city": "pune"},
        sql="SELECT 1", sql_params={}, results=[], relaxation=None, pending_confirmation=None,
        followup_listing_id=None, followup_rank=None, response=response,
        response_text=response.text(), verdict=Verdict(ok=True, source="llm"),
        fallback_used=[], timings_ms={"nlu": 10.0, "compose": 5.0, "total": 20.0},
    )  # fmt: skip


class FakeRunner:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def run(self, session_id: str, text: str) -> TurnResult:
        self.texts.append(text)
        return _result(session_id, text)

    async def state(self, session_id: str) -> dict[str, Any]:
        return {"session_id": session_id}


async def _events(svc: VoiceServices, inp: TurnInput) -> list[dict[str, Any]]:
    return [e async for e in run_turn(svc, inp)]


def _svc(**kw: Any) -> VoiceServices:
    base: dict[str, Any] = {"runner": FakeRunner(), "stt": {}, "tts": FakeTTS()}
    return VoiceServices(**{**base, **kw})


async def test_typed_turn_event_order_and_sentence_audio() -> None:
    svc = _svc()
    ev = await _events(svc, TurnInput(session_id="s", text="Tata Ace in Pune"))
    assert [e["type"] for e in ev] == [
        "transcript", "understanding", "search", "sentence", "sentence", "sentence", "done",
    ]  # fmt: skip
    assert ev[0]["source"] == "typed" and ev[0]["text"] == "Tata Ace in Pune"
    first = ev[3]
    assert first["tts"] == "server" and base64.b64decode(first["audio_b64"]).startswith(b"mp3:")
    done = ev[-1]
    assert done["timings_ms"]["pipeline"] == 20.0 and "first_audio_ready" in done["timings_ms"]
    assert "total" not in done["timings_ms"]
    assert {u["provider"] for u in done["usage"]} == {"fake-tts-tts"}


async def test_audio_turn_uses_stt_for_the_chosen_language() -> None:
    runner = FakeRunner()
    stt = {"en": SttChoice(FakeSTT("english")), "hi-en": SttChoice(FakeSTT("hinglish"), ("x",))}
    svc = _svc(runner=runner, stt=stt)
    ev = await _events(svc, TurnInput(session_id="s", audio=b"a", language="hi-en"))
    assert runner.texts == ["hinglish"] and ev[0]["source"] == "stt"
    assert "x" in ev[-1]["fallback_used"] and "stt" in ev[-1]["timings_ms"]


async def test_stt_failure_speaks_apology_and_skips_runner() -> None:
    runner = FakeRunner()
    stt = {"en": SttChoice(FakeSTT(error=ProviderError("fake-stt", "down")))}
    ev = await _events(_svc(runner=runner, stt=stt), TurnInput(session_id="s", audio=b"a"))
    assert runner.texts == []
    assert [e["type"] for e in ev] == ["transcript", "sentence", "done"]
    assert ev[1]["text"] == STT_FAILED_TEXT and "stt_error" in ev[-1]["fallback_used"]
    assert ev[-1]["turn"] is None and ev[-1]["verdict"] is None


async def test_empty_transcript_is_a_recorded_fallback() -> None:
    stt = {"en": SttChoice(FakeSTT(""))}
    ev = await _events(_svc(stt=stt), TurnInput(session_id="s", audio=b"a"))
    assert "stt_empty" in ev[-1]["fallback_used"]


async def test_tts_failure_hands_remaining_sentences_to_browser() -> None:
    ev = await _events(_svc(tts=FakeTTS(fail_after=1)), TurnInput(session_id="s", text="x"))
    sentences = [e for e in ev if e["type"] == "sentence"]
    assert [s["tts"] for s in sentences] == ["server", "client", "client"]
    assert ev[-1]["fallback_used"].count("tts_client") == 1


async def test_no_tts_configured_means_client_speech() -> None:
    ev = await _events(_svc(tts=None), TurnInput(session_id="s", text="x"))
    assert all(e["audio_b64"] is None for e in ev if e["type"] == "sentence")
    assert "tts_client" in ev[-1]["fallback_used"]


async def test_whole_mode_sends_one_sentence() -> None:
    ev = await _events(_svc(tts_mode="whole"), TurnInput(session_id="s", text="x"))
    sentences = [e for e in ev if e["type"] == "sentence"]
    assert len(sentences) == 1 and sentences[0]["text"].startswith("Here are")


async def test_turn_is_logged_with_turn_id(tmp_path: Any) -> None:
    import json

    log = tmp_path / "turns.jsonl"
    ev = await _events(_svc(turn_log_path=log), TurnInput(session_id="s", text="x"))
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert record["turn_id"] == ev[-1]["turn_id"] and record["tts_mode"] == "sentence"
    assert record["input"] == "typed" and record["sql"] == "SELECT 1"
