"""Scoring rules of eval/run_eval.py (the CLI itself needs Postgres + Groq, so only pure parts here)."""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.fakes import make_listing
from voice_agent.domain.models import ScoredListing
from voice_agent.graph.runner import TurnResult
from voice_agent.response import templates
from voice_agent.response.schema import Verdict

_RUN_EVAL = Path(__file__).resolve().parents[2] / "eval" / "run_eval.py"


@pytest.fixture(scope="module")
def run_eval() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_eval", _RUN_EVAL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result(route: str, **overrides: Any) -> TurnResult:
    response = templates.simple("error")
    fields: dict[str, Any] = {
        "session_id": "s",
        "turn": 1,
        "text": "hi",
        "intent": None,
        "language": None,
        "route": route,
        "slots": {},
        "slot_diff": {},
        "filters": None,
        "sql": None,
        "sql_params": {},
        "results": [],
        "relaxation": None,
        "pending_confirmation": None,
        "followup_listing_id": None,
        "followup_rank": None,
        "response": response,
        "response_text": response.text(),
        "verdict": Verdict(ok=True, source="template"),
        "fallback_used": [],
        "timings_ms": {"total": 1.0},
    }
    return TurnResult(**{**fields, **overrides})


def test_error_turn_always_fails(run_eval: ModuleType) -> None:
    r = _result("error", fallback_used=["error"])
    # Without the guard these would pass: no filters == {} and no expectations at all.
    for expect in ({"expect_filters": {}}, {}):
        failures = run_eval.check_turn(expect, r)
        assert failures and "turn errored" in failures[0] and "['error']" in failures[0]


def test_reset_turn_with_no_filters_passes(run_eval: ModuleType) -> None:
    assert (
        run_eval.check_turn({"expect_route": "reset", "expect_filters": {}}, _result("reset")) == []
    )


def test_summary_shows_na_safety_when_nothing_shown(run_eval: ModuleType) -> None:
    result = {
        "run_at": "2026-01-01 00:00 UTC",
        "cases": [{"id": "x", "category": "other", "passed": True, "failures": []}],
        "timings": {"total": [1.0]},
        "shown": 0,
        "unsafe": 0,
        "recheck_shown": 0,
        "recheck_unsafe": 0,
    }
    summary = run_eval.summarise(result)
    assert "Constraint safety (vs stated constraints): n/a" in summary
    assert "Re-check (vs executed filters): n/a" in summary
    assert "2026-01-01 00:00 UTC" in summary and "known_failures.md" in summary
    assert run_eval.pass_rate(result) == 1.0


def _shown(price: int) -> ScoredListing:
    return ScoredListing(
        listing=make_listing(price_inr=price), rank=1, score=1.0, features={}, contributions={}
    )


def test_safety_is_measured_against_stated_constraints(run_eval: ModuleType) -> None:
    # The pipeline dropped the budget (filters={}); its own re-check cannot see that,
    # the stated-constraint check must.
    r = _result("search", filters={}, results=[_shown(400_000), _shown(600_000)])
    assert run_eval.recheck_violations(r) == 0
    assert run_eval.safety_violations(r, {"budget_max": 500_000}) == 1
    assert run_eval.safety_violations(r, {}) == 0


def test_recheck_counts_breaks_of_executed_filters(run_eval: ModuleType) -> None:
    r = _result("search", filters={"budget_max": 500_000}, results=[_shown(600_000)])
    assert run_eval.recheck_violations(r) == 1


def test_summary_reports_both_safety_lines(run_eval: ModuleType) -> None:
    result = {
        "run_at": "2026-01-01 00:00 UTC",
        "cases": [{"id": "x", "category": "other", "passed": True, "failures": []}],
        "timings": {"total": [1.0]},
        "shown": 10,
        "unsafe": 1,
        "recheck_shown": 12,
        "recheck_unsafe": 0,
    }
    summary = run_eval.summarise(result)
    assert "Constraint safety (vs stated constraints): 90.0% of 10" in summary
    assert "Re-check (vs executed filters): 0 of 12" in summary


def test_select_cases_by_category(run_eval: ModuleType) -> None:
    cases = [{"id": "a", "category": "hinglish"}, {"id": "b", "category": "english"}]
    assert [c["id"] for c in run_eval.select_cases(cases, "hinglish")] == ["a"]
    assert run_eval.select_cases(cases, None) == cases
