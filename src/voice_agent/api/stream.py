"""One turn as NDJSON events (architecture §10, H4, J4). STT and TTS sit outside the graph:
transcribe -> TurnRunner.run -> speak each validated sentence. Plain Python, no FastAPI here."""

import base64
import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

from voice_agent.domain.ports import ProviderError, SttChoice, TextToSpeech, Usage
from voice_agent.graph.runner import TurnResult
from voice_agent.telemetry.timing import Clock, timed
from voice_agent.telemetry.turnlog import append_turn

log = logging.getLogger(__name__)

STT_FAILED_TEXT = "Sorry, I didn't catch that. Could you say it again, or type it?"


class Runner(Protocol):
    async def run(self, session_id: str, text: str) -> TurnResult: ...

    async def state(self, session_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class TurnInput:
    session_id: str
    text: str | None = None
    audio: bytes | None = None
    filename: str = "speech.webm"
    content_type: str = "audio/webm"
    language: str = "en"
    audio_seconds: float = 0.0  # client-measured clip length; Sarvam reports none (L5)


@dataclass(frozen=True)
class VoiceServices:
    runner: Runner
    stt: Mapping[str, SttChoice]
    tts: TextToSpeech | None
    tts_mode: Literal["sentence", "whole"] = "sentence"
    turn_log_path: Path | None = None


@dataclass
class _Turn:
    """Mutable bookkeeping for one request."""

    clock: Clock
    timings: dict[str, float]
    fallbacks: list[str]
    usage: list[Usage]


async def run_turn(svc: VoiceServices, inp: TurnInput) -> AsyncIterator[dict[str, Any]]:
    t = _Turn(Clock(), {}, [], [])
    text, transcript = await _transcribe(svc, inp, t)
    yield transcript
    result: TurnResult | None = None
    if text:
        result = await svc.runner.run(inp.session_id, text)
        dumped = result.model_dump(mode="json")
        yield _understanding_event(dumped)
        yield _search_event(dumped)
        t.fallbacks += result.fallback_used
        t.usage += result.usage
        stages = dict(result.timings_ms)
        t.timings["pipeline"] = stages.pop("total", 0.0)
        t.timings.update(stages)
        sentences = _sentences(result, svc.tts_mode)
    else:
        sentences = [STT_FAILED_TEXT]
    async for event in _speak(svc, sentences, t):
        yield event
    t.timings["server_total"] = t.clock.ms()
    done = {
        "type": "done",
        "turn_id": uuid4().hex,
        "turn": result.turn if result else None,
        "response_text": result.response_text if result else STT_FAILED_TEXT,
        "verdict": result.verdict.model_dump(mode="json") if result else None,
        "fallback_used": t.fallbacks,
        "timings_ms": t.timings,
        "usage": [u.model_dump(mode="json") for u in t.usage],
    }
    _log_turn(svc, inp, transcript, result, done)
    yield done


async def _transcribe(svc: VoiceServices, inp: TurnInput, t: _Turn) -> tuple[str, dict[str, Any]]:
    if inp.audio is None:
        text = (inp.text or "").strip()
        return text, _transcript_event(text, "typed", None, None, None)
    choice = svc.stt.get(inp.language) or svc.stt.get("en")
    if choice is None:
        log.warning("no STT configured for %s", inp.language)
        t.fallbacks.append("stt_unavailable")
        return "", _transcript_event("", "stt", None, None, None)
    t.fallbacks += choice.fallbacks
    try:
        with timed() as sw:
            tr = await choice.stt.transcribe(inp.audio, inp.filename, inp.content_type)
    except ProviderError as exc:
        log.warning("stt failed: %s", exc)
        t.timings["stt"] = sw.ms
        t.fallbacks.append("stt_error")
        return "", _transcript_event("", "stt", choice.stt.name, None, None)
    t.timings["stt"] = sw.ms
    seconds = tr.audio_seconds or inp.audio_seconds
    t.usage.append(Usage(provider=f"{tr.provider}-stt", audio_seconds=seconds))
    if not tr.text:
        log.warning("stt returned an empty transcript (%s)", tr.provider)
        t.fallbacks.append("stt_empty")
    return tr.text, _transcript_event(tr.text, "stt", tr.provider, tr.confidence, tr.language)


async def _speak(
    svc: VoiceServices, sentences: list[str], t: _Turn
) -> AsyncIterator[dict[str, Any]]:
    tts = svc.tts
    if tts is None:
        t.fallbacks.append("tts_client")
    tts_ms = 0.0
    for index, text in enumerate(sentences):
        audio: bytes | None = None
        if tts is not None:
            try:
                with timed() as sw:
                    audio = await tts.synthesize(text)
                tts_ms += sw.ms
                t.usage.append(Usage(provider=f"{tts.name}-tts", characters=len(text)))
            except ProviderError as exc:  # H5: the browser speaks the rest of this turn
                log.warning("tts failed, switching to browser speech: %s", exc)
                t.fallbacks.append("tts_client")
                tts = None
        if index == 0:
            t.timings["first_audio_ready"] = t.clock.ms()
        yield {
            "type": "sentence",
            "index": index,
            "text": text,
            "audio_b64": base64.b64encode(audio).decode("ascii") if audio else None,
            "tts": "server" if audio else "client",
        }
    if tts_ms:
        t.timings["tts"] = round(tts_ms, 1)


def _sentences(result: TurnResult, mode: str) -> list[str]:
    if mode == "whole":
        return [result.response_text]
    return result.response.sentences() or [result.response_text]


def _transcript_event(
    text: str, source: str, provider: str | None, confidence: float | None, language: str | None
) -> dict[str, Any]:
    return {
        "type": "transcript",
        "text": text,
        "source": source,
        "provider": provider,
        "confidence": confidence,
        "language": language,
    }


def _understanding_event(d: dict[str, Any]) -> dict[str, Any]:
    keys = ("turn", "intent", "language", "route", "slots", "slot_diff", "pending_confirmation")
    return {"type": "understanding", **{k: d[k] for k in keys}}


def _search_event(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "search",
        "filters": d["filters"],
        "sql": d["sql"],
        "params": d["sql_params"],
        "results": d["results"],
        "relaxation": d["relaxation"],
    }


def _log_turn(
    svc: VoiceServices,
    inp: TurnInput,
    transcript: dict[str, Any],
    result: TurnResult | None,
    done: dict[str, Any],
) -> None:
    """N5: one record per API turn, richer than the runner's own (adds STT/TTS stages)."""
    if svc.turn_log_path is None:
        return
    record: dict[str, Any] = result.model_dump(mode="json") if result else {}
    record.update(
        turn_id=done["turn_id"],
        session_id=inp.session_id,
        input="audio" if inp.audio is not None else "typed",
        input_language=inp.language,
        transcript=transcript,
        tts_mode=svc.tts_mode,
        timings_ms=done["timings_ms"],
        fallback_used=done["fallback_used"],
        usage=done["usage"],
    )
    append_turn(svc.turn_log_path, record)
