"""Eval harness (component 7): run eval/cases.yaml through the real pipeline and score it.

Usage: uv run python eval/run_eval.py [--cases eval/cases.yaml]
Needs Postgres (docker compose up -d db) and GROQ_API_KEY. TTS/STT are not used here.
Exit codes: 0 = pass rate >= 90%, 1 = below target, 2 = setup problem (no DB / key / cases).
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import yaml

from voice_agent.aio import run
from voice_agent.catalog.filters import constraint_violations
from voice_agent.config import get_settings
from voice_agent.domain.models import Filters
from voice_agent.graph.runner import TurnResult
from voice_agent.graph.runtime import build_runtime

RESULTS_DIR = Path(__file__).parent / "results"
PASS_TARGET = 0.90  # J1: >= 90% of cases
SETUP_HINT = "Eval needs Postgres (docker compose up -d db) and GROQ_API_KEY in .env"


def _now() -> str:
    return f"{datetime.now(UTC):%Y-%m-%d %H:%M} UTC"


def check_turn(expect: dict[str, Any], r: TurnResult) -> list[str]:
    failures: list[str] = []
    if r.route == "error":  # an exception-boundary turn never passes: an outage is not a success
        failures.append(f"turn errored, fallback_used={r.fallback_used}")
    filters = r.filters or {}
    if "expect_filters" in expect and filters != expect["expect_filters"]:
        failures.append(f"filters {filters} != {expect['expect_filters']}")
    if "expect_changed" in expect and sorted(r.slot_diff) != sorted(expect["expect_changed"]):
        failures.append(f"changed {sorted(r.slot_diff)} != {sorted(expect['expect_changed'])}")
    if "expect_changed_count" in expect and len(r.slot_diff) != expect["expect_changed_count"]:
        failures.append(
            f"changed {len(r.slot_diff)} slots, expected {expect['expect_changed_count']}"
        )
    if "expect_route" in expect and r.route != expect["expect_route"]:
        failures.append(f"route {r.route} != {expect['expect_route']}")
    if "expect_results" in expect and len(r.results) != expect["expect_results"]:
        failures.append(f"{len(r.results)} results != {expect['expect_results']}")
    if "expect_results_min" in expect and len(r.results) < expect["expect_results_min"]:
        failures.append(f"{len(r.results)} results < {expect['expect_results_min']}")
    if "expect_relaxation" in expect and (r.relaxation is not None) != expect["expect_relaxation"]:
        failures.append(f"relaxation offered={r.relaxation is not None}")
    if "expect_followup_rank" in expect and r.followup_rank != expect["expect_followup_rank"]:
        failures.append(f"follow-up rank {r.followup_rank} != {expect['expect_followup_rank']}")
    if (
        r.route == "search"
        and r.results
        and (r.verdict.source != "llm" or "regenerated" in r.fallback_used)
    ):
        failures.append(f"validator not clean on first try ({r.verdict.source}, {r.fallback_used})")
    return failures


def safety_violations(r: TurnResult) -> int:
    if not r.filters:
        return 0
    f = Filters.model_validate(r.filters)
    return sum(1 for s in r.results if constraint_violations(s.listing, f))


async def run_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    report: list[dict[str, Any]] = []
    timings: dict[str, list[float]] = defaultdict(list)
    shown = unsafe = 0
    run_at = _now()
    async with build_runtime(get_settings(), log_turns=False) as runner:
        for case in cases:
            session = f"eval-{case['id']}-{uuid4().hex[:6]}"
            failures: list[str] = []
            for i, turn in enumerate(case["turns"], start=1):
                r = await runner.run(session, turn["say"])
                failures += [f"t{i}: {f}" for f in check_turn(turn, r)]
                shown += len(r.results)
                unsafe += safety_violations(r)
                for stage, ms in r.timings_ms.items():
                    timings[stage].append(ms)
            report.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "passed": not failures,
                    "failures": failures,
                }
            )
            print(f"{'PASS' if not failures else 'FAIL'}  {case['id']:<16} {'; '.join(failures)}")
    return {
        "run_at": run_at,
        "cases": report,
        "timings": timings,
        "shown": shown,
        "unsafe": unsafe,
    }


def pass_rate(result: dict[str, Any]) -> float:
    cases = result["cases"]
    return sum(c["passed"] for c in cases) / len(cases) if cases else 0.0


def summarise(result: dict[str, Any]) -> str:
    cases = result["cases"]
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for c in cases:
        by_cat[c["category"]].append(c["passed"])
    passed = sum(c["passed"] for c in cases)
    lines = [
        f"# Eval results ({result.get('run_at') or _now()})",
        "",
        f"**Overall: {passed}/{len(cases)} = {100 * pass_rate(result):.0f}%**",
        "",
        "| Category | Passed |",
        "|---|---|",
    ]
    lines += [f"| {cat} | {sum(v)}/{len(v)} |" for cat, v in sorted(by_cat.items())]
    if result["shown"]:
        safe_pct = 100 * (1 - result["unsafe"] / result["shown"])
        safety = f"{safe_pct:.1f}% of {result['shown']} shown results satisfy every hard filter."
    else:
        safety = "n/a (no results were shown)."
    lines += [
        "",
        f"Constraint safety: {safety}",
        "",
        "| Stage | p50 ms | p95 ms |",
        "|---|---|---|",
    ]
    for stage, values in sorted(result["timings"].items()):
        ordered = sorted(values)
        p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
        lines.append(f"| {stage} | {statistics.median(ordered):.0f} | {p95:.0f} |")
    failed = [c for c in cases if not c["passed"]]
    if failed:
        lines += ["", "## Failures", ""] + [
            f"- `{c['id']}`: {'; '.join(c['failures'])}" for c in failed
        ]
    lines += ["", "Known failures, risks and latency caveats: see `known_failures.md`."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path(__file__).parent / "cases.yaml")
    args = parser.parse_args()
    cases = yaml.safe_load(args.cases.read_text(encoding="utf-8"))
    if not cases or not isinstance(cases, list):
        print(f"No cases found in {args.cases}", file=sys.stderr)
        return 2
    try:
        result = run(run_cases(cases))
    except (RuntimeError, psycopg.OperationalError, OSError) as exc:
        detail = str(exc).strip().splitlines()
        print(f"{SETUP_HINT}\n{type(exc).__name__}: {detail[0] if detail else ''}", file=sys.stderr)
        return 2
    summary = summarise(result)
    print("\n" + summary)
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "latest.md").write_text(summary, encoding="utf-8")
    (RESULTS_DIR / "latest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if pass_rate(result) >= PASS_TARGET else 1


if __name__ == "__main__":
    sys.exit(main())
