"""₹ per conversation from logged usage (L5), priced with config/prices.yaml.

Usage: uv run python scripts/cost_report.py [--out eval/results/cost.md] [--monthly 100000]
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def usd(u: dict[str, Any], prices: dict[str, Any]) -> float | None:
    p = u["provider"]
    if p in prices["llm"]:
        rate = prices["llm"][p]
        return (
            u.get("input_tokens", 0) * rate["input"] + u.get("output_tokens", 0) * rate["output"]
        ) / 1e6
    if p in prices["stt"]:
        return u.get("audio_seconds", 0.0) / 3600 * prices["stt"][p]
    if p in prices["tts"]:
        return u.get("characters", 0) / 1000 * prices["tts"][p]
    return None


def cost_summary(turns: list[dict[str, Any]], prices: dict[str, Any]) -> dict[str, Any]:
    by_provider: dict[str, float] = defaultdict(float)
    sessions: set[str] = set()
    unpriced: set[str] = set()
    for t in turns:
        sessions.add(t.get("session_id", "?"))
        for u in t.get("usage", []):
            cost = usd(u, prices)
            if cost is None:
                unpriced.add(u["provider"])
            else:
                by_provider[u["provider"]] += cost
    inr_total = sum(by_provider.values()) * prices["usd_to_inr"]
    n = max(1, len(sessions))
    return {
        "turns": len(turns),
        "conversations": len(sessions),
        "inr_by_provider": {k: v * prices["usd_to_inr"] for k, v in sorted(by_provider.items())},
        "inr_total": inr_total,
        "inr_per_conversation": inr_total / n,
        "unpriced": sorted(unpriced),
    }


def render(s: dict[str, Any], monthly: int, checked: str) -> str:
    lines = [
        "# Cost report (L5)",
        "",
        f"Prices: config/prices.yaml (checked {checked}; re-verify before quoting).",
        f"{s['turns']} turns in {s['conversations']} conversations.",
        "",
        "| Provider | ₹ total |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v:.4f} |" for k, v in s["inr_by_provider"].items()]
    per = s["inr_per_conversation"]
    lines += [
        "",
        f"**₹ per conversation: {per:.3f}**. At {monthly:,} conversations/month: ₹{per * monthly:,.0f}.",
    ]
    if s["unpriced"]:
        lines.append(f"Unpriced providers (add to prices.yaml): {', '.join(s['unpriced'])}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=Path, default=Path("logs/turns.jsonl"))
    parser.add_argument("--prices", type=Path, default=Path("config/prices.yaml"))
    parser.add_argument("--monthly", type=int, default=100_000)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows cp1252 cannot print the rupee sign
    prices = yaml.safe_load(args.prices.read_text(encoding="utf-8"))
    text = render(
        cost_summary(read_jsonl(args.turns), prices), args.monthly, prices.get("checked", "?")
    )
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
