"""TurnRunner: the seam the CLI, eval and (Plan 2) API call. One call = one conversational turn."""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from voice_agent.domain.models import Relaxation, ScoredListing
from voice_agent.domain.ports import Usage
from voice_agent.graph.state import MEMORY_DEFAULTS, TURN_RESET
from voice_agent.response import templates
from voice_agent.response.schema import ComposedResponse, Verdict
from voice_agent.state.models import PendingConfirmation
from voice_agent.telemetry.timing import timed
from voice_agent.telemetry.turnlog import append_turn

log = logging.getLogger(__name__)


class TurnResult(BaseModel):
    session_id: str
    turn: int
    text: str
    intent: str | None
    language: str | None
    route: str  # a RouteKind, or "error" when the turn failed
    slots: dict[str, Any]
    slot_diff: dict[str, list[Any]]
    filters: dict[str, Any] | None
    sql: str | None
    sql_params: dict[str, Any]
    results: list[ScoredListing]
    relaxation: Relaxation | None
    pending_confirmation: PendingConfirmation | None
    followup_listing_id: str | None
    followup_rank: int | None
    response: ComposedResponse
    response_text: str
    verdict: Verdict
    fallback_used: list[str]
    timings_ms: dict[str, float]
    usage: list[Usage] = Field(default_factory=list)


class TurnRunner:
    def __init__(self, graph: Any, turn_log_path: Path | None) -> None:
        self._graph = graph
        self._log = turn_log_path

    async def run(self, session_id: str, text: str) -> TurnResult:
        config = {"configurable": {"thread_id": session_id}}
        before = await self._snapshot(session_id, config)
        state: dict[str, Any] | None = None
        with timed() as total:
            try:
                state = await self._graph.ainvoke({**TURN_RESET, "text": text}, config=config)
            except Exception:  # turn boundary: one failed turn must not end the session
                log.exception("turn failed (session=%s)", session_id)
                await self._rollback(session_id, config, before)
        if state is None:
            result = await self._error_result(session_id, text, config, total.ms)
        else:
            result = _to_result(session_id, text, state, total.ms)
        if self._log is not None:
            append_turn(self._log, result.model_dump(mode="json"))
        return result

    async def _snapshot(self, session_id: str, config: dict[str, Any]) -> Any | None:
        try:
            return await self._graph.aget_state(config)
        except Exception:
            log.warning("could not read checkpoint before turn (session=%s)", session_id)
            return None

    async def _rollback(self, session_id: str, config: dict[str, Any], before: Any | None) -> None:
        """N17: LangGraph saves after every node, so a failed turn has half-saved its changes.
        Write the pre-turn state back as the latest checkpoint."""
        if before is None:
            return  # nothing known to restore; _snapshot logged why
        try:
            if before.values:
                await self._graph.aupdate_state(before.config, before.values)
            else:
                await self._graph.aupdate_state(config, MEMORY_DEFAULTS)
        except Exception:
            log.warning("could not roll back failed turn (session=%s)", session_id)

    async def _error_result(
        self, session_id: str, text: str, config: dict[str, Any], total_ms: float
    ) -> TurnResult:
        memory: dict[str, Any] = {}
        try:  # best effort: show the slots from the latest checkpoint
            memory = (await self._graph.aget_state(config)).values
        except Exception:
            log.warning("could not read checkpoint after failed turn (session=%s)", session_id)
        slots = memory.get("slots")
        response = templates.simple("error")
        return TurnResult(
            session_id=session_id,
            turn=memory.get("turn", 0),
            text=text,
            intent=None,
            language=None,
            route="error",
            slots=slots.filled() if slots else {},
            slot_diff={},
            filters=None,
            sql=None,
            sql_params={},
            results=[],
            relaxation=None,
            pending_confirmation=None,
            followup_listing_id=None,
            followup_rank=None,
            response=response,
            response_text=response.text(),
            verdict=Verdict(ok=True, source="template"),
            fallback_used=["error"],
            timings_ms={"total": total_ms},
        )

    async def state(self, session_id: str) -> dict[str, Any]:
        """JSON-safe conversation memory (GET /api/session/{id}/state)."""
        snapshot = await self._graph.aget_state({"configurable": {"thread_id": session_id}})
        v: dict[str, Any] = snapshot.values or {}
        slots = v.get("slots")
        return {
            "session_id": session_id,
            "turn": v.get("turn", 0),
            "slots": slots.filled() if slots else {},
            "pending_confirmation": _dump(v.get("pending_confirmation")),
            "pending_relaxation": _dump(v.get("pending_relaxation")),
            "last_results": [r.model_dump(mode="json") for r in v.get("last_results") or []],
            "focused_listing_id": v.get("focused_listing_id"),
        }


def _dump(model: BaseModel | None) -> dict[str, Any] | None:
    return model.model_dump(mode="json") if model is not None else None


def _to_result(session_id: str, text: str, s: dict[str, Any], total_ms: float) -> TurnResult:
    route = s["route"]
    u = s.get("understanding")
    is_follow_up = route.kind == "follow_up"
    ranks = {r.listing_id: r.rank for r in s.get("last_results", [])}
    response = s["response"]
    return TurnResult(
        session_id=session_id,
        turn=s.get("turn", 0),
        text=text,
        intent=u.turn_intent.intent.value if u else None,
        language=u.turn_intent.language.value if u else None,
        route=route.kind,
        slots=s["slots"].filled(),
        slot_diff={k: list(v) for k, v in s.get("slot_diff", {}).items()},
        filters=s["filters"].as_dict() if s.get("filters") else None,
        sql=s.get("executed_sql"),
        sql_params=s.get("sql_params", {}),
        results=s.get("results", []),
        relaxation=s.get("pending_relaxation")
        if route.kind == "search" and not s.get("results")
        else None,
        pending_confirmation=s.get("pending_confirmation"),
        followup_listing_id=route.listing_id if is_follow_up else None,
        followup_rank=ranks.get(route.listing_id) if is_follow_up and route.listing_id else None,
        response=response,
        response_text=response.text(),
        verdict=s["verdict"],
        fallback_used=s.get("fallback_used", []),
        timings_ms={**s.get("timings_ms", {}), "total": total_ms},
        usage=s.get("usage", []),
    )
