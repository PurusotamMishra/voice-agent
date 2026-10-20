import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_latency_table_groups_by_tts_mode_and_joins_client_timings() -> None:
    lat = _load("latency_report")
    turns = [
        {
            "turn_id": "a",
            "tts_mode": "sentence",
            "timings_ms": {"stt": 300, "first_audio_ready": 2000},
        },
        {
            "turn_id": "b",
            "tts_mode": "whole",
            "timings_ms": {"stt": 320, "first_audio_ready": 3000},
        },
    ]
    client = [{"turn_id": "a", "speech_end_to_first_audio_ms": 2400.0}]
    table = lat.latency_table(turns, client)
    assert "## tts_mode = sentence" in table and "## tts_mode = whole" in table
    assert "| speech_end_to_first_audio | 2400 | 2400 | 1 |" in table


def test_cost_summary_per_conversation() -> None:
    cost = _load("cost_report")
    prices = {
        "usd_to_inr": 100.0,
        "llm": {"groq": {"input": 1.0, "output": 2.0}},
        "stt": {"groq-stt": 3.6},
        "tts": {"elevenlabs-tts": 0.1},
    }
    turns = [
        {"session_id": "s1", "usage": [
            {"provider": "groq", "input_tokens": 1_000_000, "output_tokens": 0},
            {"provider": "groq-stt", "audio_seconds": 3600},
            {"provider": "elevenlabs-tts", "characters": 1000},
        ]},
        {"session_id": "s2", "usage": [{"provider": "groq", "input_tokens": 0, "output_tokens": 500_000}]},
    ]  # fmt: skip
    s = cost.cost_summary(turns, prices)
    assert s["conversations"] == 2 and s["turns"] == 2
    assert s["inr_total"] == pytest.approx(100.0 * (1.0 + 3.6 + 0.1 + 1.0))
    assert s["inr_per_conversation"] == s["inr_total"] / 2
    assert s["unpriced"] == []
