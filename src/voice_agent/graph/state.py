"""LangGraph state. Memory fields persist via the checkpointer; turn fields are reset each turn."""

from typing import Any, TypedDict

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from voice_agent.domain.enums import (
    AliasKind,
    BodyType,
    City,
    FollowUpField,
    Fuel,
    Intent,
    Language,
    Purpose,
    SellerType,
)
from voice_agent.domain.models import (
    Filters,
    Listing,
    LowConfidence,
    Relaxation,
    ResultRef,
    ScoredListing,
    Slots,
    Unsupported,
)
from voice_agent.domain.ports import Usage
from voice_agent.response.schema import ComposedResponse, ItemSentence, Verdict, Violation
from voice_agent.state.models import PendingConfirmation, Route
from voice_agent.understanding.schema import ExtractedSlots, Reference, TurnIntent, Understanding


class ConversationState(TypedDict, total=False):
    # memory (persists across turns)
    turn: int
    slots: Slots
    pending_confirmation: PendingConfirmation | None
    pending_relaxation: Relaxation | None
    last_results: list[ResultRef]
    focused_listing_id: str | None
    # this turn
    text: str
    understanding: Understanding | None
    slot_diff: dict[str, tuple[Any, Any]]
    route: Route | None
    filters: Filters | None
    executed_sql: str | None
    sql_params: dict[str, Any]
    candidates: list[Listing]
    results: list[ScoredListing]
    response: ComposedResponse | None
    verdict: Verdict | None
    fallback_used: list[str]
    timings_ms: dict[str, float]
    usage: list[Usage]


TURN_RESET: dict[str, Any] = {
    "understanding": None,
    "slot_diff": {},
    "route": None,
    "filters": None,
    "executed_sql": None,
    "sql_params": {},
    "candidates": [],
    "results": [],
    "response": None,
    "verdict": None,
    "fallback_used": [],
    "timings_ms": {},
    "usage": [],
}

# Memory before the first turn: what a failed first turn rolls back to (N17).
MEMORY_DEFAULTS: dict[str, Any] = {
    "turn": 0,
    "slots": Slots(),
    "pending_confirmation": None,
    "pending_relaxation": None,
    "last_results": [],
    "focused_listing_id": None,
}


# Every class that can sit in a checkpoint. An explicit allowlist keeps checkpoint
# deserialization strict (LangGraph warns on, and will later block, unregistered types).
STATE_TYPES: tuple[type, ...] = (
    AliasKind,
    BodyType,
    City,
    FollowUpField,
    Fuel,
    Intent,
    Language,
    Purpose,
    SellerType,
    Slots,
    Filters,
    Listing,
    ScoredListing,
    ResultRef,
    Relaxation,
    LowConfidence,
    Unsupported,
    Usage,
    PendingConfirmation,
    Route,
    Understanding,
    TurnIntent,
    ExtractedSlots,
    Reference,
    ComposedResponse,
    ItemSentence,
    Verdict,
    Violation,
)


def checkpoint_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=STATE_TYPES)
