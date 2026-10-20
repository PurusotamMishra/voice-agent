"""Audio subset (J1): clip -> STT -> the real pipeline -> filter check. STT errors reported apart.

Usage: uv run python eval/run_audio_eval.py
Runs each clip through every STT valid for its language: en -> Groq; hi-en -> Sarvam (if keyed)
and Groq with the Roman-script prompt. Writes eval/results/audio_latest.md.
"""

import re
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from run_eval import check_turn  # same directory: the script runs as eval/run_audio_eval.py

from voice_agent.aio import run
from voice_agent.config import Settings, get_settings, key
from voice_agent.domain.ports import SpeechToText
from voice_agent.graph.runtime import build_runtime
from voice_agent.providers.http import open_http_client
from voice_agent.providers.stt import HINGLISH_PROMPT, GroqSTT, SarvamSTT

AUDIO_DIR = Path(__file__).parent / "audio"
RESULTS = Path(__file__).parent / "results" / "audio_latest.md"


def normalise(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def word_error_rate(ref: str, hyp: str) -> float:
    r, h = normalise(ref).split(), normalise(hyp).split()
    dist = list(range(len(h) + 1))
    for i, rw in enumerate(r, start=1):
        prev, dist[0] = dist[0], i
        for j, hw in enumerate(h, start=1):
            prev, dist[j] = dist[j], min(dist[j] + 1, dist[j - 1] + 1, prev + (rw != hw))
    return round(dist[len(h)] / max(1, len(r)), 3)


def stts_for(language: str, settings: Settings, client: Any) -> list[SpeechToText]:
    groq, sarvam = key(settings.groq_api_key), key(settings.sarvam_api_key)
    out: list[SpeechToText] = []
    if language == "en" and groq:
        out.append(GroqSTT(groq, settings.groq_stt_model, client))
    if language == "hi-en":
        if sarvam:
            out.append(
                SarvamSTT(sarvam, settings.sarvam_stt_model, settings.sarvam_stt_mode, client)
            )
        if groq:
            out.append(
                GroqSTT(
                    groq, settings.groq_stt_model, client, language=None, prompt=HINGLISH_PROMPT
                )
            )
    return out


async def run_all(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    settings = get_settings()
    rows: list[dict[str, Any]] = []
    async with open_http_client() as client, build_runtime(settings, log_turns=False) as runner:
        for case in cases:
            path = AUDIO_DIR / case["file"]
            if not path.exists():
                rows.append({"file": case["file"], "provider": "-", "status": "missing clip"})
                continue
            for stt in stts_for(case["language"], settings, client):
                tr = await stt.transcribe(path.read_bytes(), path.name, "audio/wav")
                result = await runner.run(f"audio-{uuid4().hex[:6]}", tr.text)
                failures = check_turn({"expect_filters": case["expect_filters"]}, result)
                rows.append(
                    {
                        "file": case["file"],
                        "provider": stt.name,
                        "synthetic": case.get("synthetic", False),
                        "transcript": tr.text,
                        "wer": word_error_rate(case["say"], tr.text),
                        "status": "PASS" if not failures else "FAIL: " + "; ".join(failures),
                    }
                )
                print(f"{rows[-1]['status'][:4]}  {case['file']:<18} {stt.name:<7} {tr.text}")
    return rows


def summarise(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Audio eval (STT subset, J1)",
        "",
        "| Clip | STT | Synthetic | WER | Transcript | Result |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['file']} | {r['provider']} | {r.get('synthetic', '')} | {r.get('wer', '')} "
            f"| {r.get('transcript', '')} | {r['status']} |"
        )
    passed = sum(r["status"] == "PASS" for r in rows)
    lines += ["", f"**{passed}/{len(rows)} clip×provider runs passed.**"]
    lines += ["A failure with high WER is an STT miss; low WER plus FAIL is an understanding miss."]
    return "\n".join(lines) + "\n"


def main() -> int:
    cases = yaml.safe_load((AUDIO_DIR / "cases.yaml").read_text(encoding="utf-8"))
    rows = run(run_all(cases))
    text = summarise(rows)
    print("\n" + text)
    RESULTS.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
