"""Conversation memory persisted across turns (G1) and the per-turn routing decision."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from voice_agent.domain.enums import FollowUpField
from voice_agent.domain.models import Relaxation, ResultRef, Slots, Unsupported

SlotDiff = dict[str, tuple[Any, Any]]
RouteKind = Literal[
    "search",
    "confirm",
    "follow_up",
    "which_one",
    "reset",
    "out_of_domain",
    "unsupported",
    "need_info",
]


class PendingConfirmation(BaseModel):
    """D6: a low-confidence value waiting for yes/no; other updates from that turn wait with it."""

    slot: str
    raw: str
    candidate: str
    score: float
    deferred_updates: dict[str, Any] = Field(default_factory=dict)


class Memory(BaseModel):
    slots: Slots = Field(default_factory=Slots)
    pending_confirmation: PendingConfirmation | None = None
    pending_relaxation: Relaxation | None = None
    last_results: list[ResultRef] = Field(default_factory=list)
    focused_listing_id: str | None = None


class Route(BaseModel):
    kind: RouteKind
    listing_id: str | None = None
    follow_up_field: FollowUpField | None = None
    unsupported: list[Unsupported] = Field(default_factory=list)
