"""p50/p95 per stage from logs/turns.jsonl (+ browser timings), split by TTS mode (J4, J5).

Usage: uv run python scripts/latency_report.py [--out eval/results/latency.md]
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

STAGES = [
    "stt",
    "nlu",
    "search",
    "rank",
    "relax",
    "compose",
    "pipeline",
    "first_audio_ready",
    "tts",
    "server_total",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _p(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def latency_table(turns: list[dict[str, Any]], client: list[dict[str, Any]]) -> str:
    browser = {
        c["turn_id"]: c["speech_end_to_first_audio_ms"]
        for c in client
        if c.get("speech_end_to_first_audio_ms") is not None
    }
    groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for t in turns:
        if "turn_id" not in t:  # CLI/runner records have no API stages
            continue
        stages = groups[t.get("tts_mode", "unknown")]
        for name, ms in t.get("timings_ms", {}).items():
            stages[name].append(float(ms))
        if t["turn_id"] in browser:
            stages["speech_end_to_first_audio"].append(float(browser[t["turn_id"]]))
    lines = ["# Latency report", ""]
    for mode, stages in sorted(groups.items()):
        lines += [
            f"## tts_mode = {mode}",
            "",
            "| Stage | p50 ms | p95 ms | n |",
            "|---|---|---|---|",
        ]
        order = [s for s in [*STAGES, "speech_end_to_first_audio"] if s in stages]
        for name in order:
            v = stages[name]
            lines.append(f"| {name} | {statistics.median(v):.0f} | {_p(v, 0.95):.0f} | {len(v)} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=Path, default=Path("logs/turns.jsonl"))
    parser.add_argument("--client", type=Path, default=Path("logs/client_timings.jsonl"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    text = latency_table(read_jsonl(args.turns), read_jsonl(args.client))
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
