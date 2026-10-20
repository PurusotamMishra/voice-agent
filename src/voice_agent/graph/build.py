"""LangGraph wiring (C2). Nodes call one component each and write state; no business logic here."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from voice_agent.catalog.filters import constraint_violations
from voice_agent.catalog.ranker import rank
from voice_agent.catalog.relax import propose_relaxation
from voice_agent.domain.enums import AliasKind, City, Language
from voice_agent.domain.models import Filters, ResultRef, Slots
from voice_agent.domain.ports import LLM, Catalog, Normalizer
from voice_agent.graph.state import ConversationState
from voice_agent.response import templates
from voice_agent.response.composer import compose_results
from voice_agent.response.factsheet import build_fact_item, build_fact_sheet
from voice_agent.response.schema import ComposedResponse, Verdict
from voice_agent.response.validator import EntityVocab
from voice_agent.state.models import Memory
from voice_agent.state.reducer import apply_understanding
from voice_agent.telemetry.timing import timed
from voice_agent.understanding.extractor import LLMSlotExtractor
from voice_agent.understanding.pipeline import understand
from voice_agent.understanding.schema import ExtractionContext

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Deps:
    llm: LLM
    normalizer: Normalizer
    catalog: Catalog
    vocab: EntityVocab
    neighbors: Mapping[City, Sequence[City]]
    weights: Mapping[str, float]
    alias_map: Mapping[AliasKind, Mapping[str, str]]
    compose_llm: LLM | None = None


def _memory(s: ConversationState) -> Memory:
    return Memory(
        slots=s.get("slots") or Slots(),
        pending_confirmation=s.get("pending_confirmation"),
        pending_relaxation=s.get("pending_relaxation"),
        last_results=s.get("last_results") or [],
        focused_listing_id=s.get("focused_listing_id"),
    )


def _pending_question(mem: Memory) -> str | None:
    if mem.pending_confirmation:
        return f"Did you mean {mem.pending_confirmation.candidate}? (yes/no)"
    if mem.pending_relaxation:
        r = mem.pending_relaxation
        return f"Offered to relax {r.slot} to {r.new}. (relax if accepted)"
    return None


def _timing(s: ConversationState, stage: str, ms: float) -> dict[str, float]:
    return {**s.get("timings_ms", {}), stage: ms}


def build_graph(deps: Deps, checkpointer: BaseCheckpointSaver[Any] | None = None) -> Any:
    extractor = LLMSlotExtractor(deps.llm, deps.alias_map)

    async def understand_node(s: ConversationState) -> dict[str, Any]:
        mem = _memory(s)
        ctx = ExtractionContext(
            slots=mem.slots, last_results=mem.last_results, pending_question=_pending_question(mem)
        )
        with timed() as t:
            u = await understand(s["text"], ctx, extractor, deps.normalizer, deps.alias_map)
        return {
            "understanding": u,
            "timings_ms": _timing(s, "nlu", t.ms),
            "usage": [*s.get("usage", []), *u.usage],
            "fallback_used": [*s.get("fallback_used", []), *u.fallbacks],
        }

    async def update_state_node(s: ConversationState) -> dict[str, Any]:
        understanding = s["understanding"]
        assert understanding is not None
        mem, diff, route = apply_understanding(_memory(s), understanding)
        return {
            "turn": s.get("turn", 0) + 1,
            "slots": mem.slots,
            "pending_confirmation": mem.pending_confirmation,
            "pending_relaxation": mem.pending_relaxation,
            "last_results": mem.last_results,
            "focused_listing_id": mem.focused_listing_id,
            "slot_diff": diff,
            "route": route,
        }

    async def search_node(s: ConversationState) -> dict[str, Any]:
        filters = Filters.from_slots(s["slots"])
        with timed() as t:
            result = await deps.catalog.search(filters)
        safe = [r for r in result.rows if not constraint_violations(r, filters)]
        fallbacks = list(s.get("fallback_used", []))
        if len(safe) != len(result.rows):  # F2.3: should never happen; loud if it does
            log.error("constraint re-check dropped %d rows", len(result.rows) - len(safe))
            fallbacks.append("constraint_drop")
        return {
            "filters": filters,
            "executed_sql": result.sql,
            "sql_params": result.params,
            "candidates": safe,
            "fallback_used": fallbacks,
            "timings_ms": _timing(s, "search", t.ms),
        }

    async def rank_node(s: ConversationState) -> dict[str, Any]:
        with timed() as t:
            results = rank(s["candidates"], s["slots"], deps.weights)
        refs = [
            ResultRef(
                listing_id=r.listing.listing_id,
                rank=r.rank,
                make=r.listing.make,
                model=r.listing.model,
            )
            for r in results
        ]
        return {
            "results": results,
            "last_results": refs,
            "focused_listing_id": None,
            "timings_ms": _timing(s, "rank", t.ms),
        }

    async def relax_node(s: ConversationState) -> dict[str, Any]:
        filters = s["filters"]
        assert filters is not None
        with timed() as t:
            relaxation = await propose_relaxation(filters, deps.catalog.count, deps.neighbors)
        # Zero rows: the previous results are no longer on screen, so "the first one" must not
        # resolve against them.
        return {
            "pending_relaxation": relaxation,
            "last_results": [],
            "focused_listing_id": None,
            "timings_ms": _timing(s, "relax", t.ms),
        }

    async def respond_node(s: ConversationState) -> dict[str, Any]:
        route = s["route"]
        assert route is not None
        understanding = s.get("understanding")
        language = understanding.turn_intent.language if understanding else Language.EN
        usage, fallbacks = list(s.get("usage", [])), list(s.get("fallback_used", []))
        verdict = Verdict(ok=True, source="template")
        response: ComposedResponse
        with timed() as t:
            if route.kind == "search" and s.get("results"):
                facts = build_fact_sheet(s["results"], s["slots"].purpose, language)
                outcome = await compose_results(facts, deps.compose_llm or deps.llm, deps.vocab)
                response, verdict = outcome.response, outcome.verdict
                usage += outcome.usage
                fallbacks += outcome.fallbacks
            elif route.kind == "search":
                response = templates.zero_results(s["slots"], s.get("pending_relaxation"))
            elif route.kind == "follow_up" and route.listing_id:
                listing = await deps.catalog.get(route.listing_id)
                ranks = {r.listing_id: r.rank for r in s.get("last_results", [])}
                if listing is None or route.follow_up_field is None:
                    response = templates.simple("which_one")
                else:
                    item = build_fact_item(listing, ranks.get(listing.listing_id, 1), [], None)
                    response = templates.follow_up(item, route.follow_up_field)
            elif route.kind == "confirm" and s.get("pending_confirmation"):
                response = templates.confirm(s["pending_confirmation"])  # type: ignore[arg-type]
            elif route.kind == "unsupported":
                response = templates.unsupported(route.unsupported)
            elif route.kind in ("reset", "out_of_domain", "need_info", "which_one"):
                response = templates.simple(route.kind)
            else:
                response = templates.simple("error")
        return {
            "response": response,
            "verdict": verdict,
            "usage": usage,
            "fallback_used": fallbacks,
            "timings_ms": _timing(s, "compose", t.ms),
        }

    def after_state(s: ConversationState) -> str:
        route = s["route"]
        return "search" if route is not None and route.kind == "search" else "respond"

    def after_search(s: ConversationState) -> str:
        return "rank" if s["candidates"] else "relax"

    # Typed as Any: LangGraph's add_node overloads reject a TypedDict-typed node under mypy.
    nodes: dict[str, Any] = {
        "understand": understand_node,
        "update_state": update_state_node,
        "search": search_node,
        "rank": rank_node,
        "relax": relax_node,
        "respond": respond_node,
    }
    g = StateGraph(ConversationState)
    for name, node in nodes.items():
        g.add_node(name, node)
    g.add_edge(START, "understand")
    g.add_edge("understand", "update_state")
    g.add_conditional_edges("update_state", after_state, ["search", "respond"])
    g.add_conditional_edges("search", after_search, ["rank", "relax"])
    g.add_edge("rank", "respond")
    g.add_edge("relax", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer)
