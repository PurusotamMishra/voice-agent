"""Typed output of the understanding stage. TurnIntent is the LLM's tool schema (D1)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from voice_agent.domain.enums import BodyType, FollowUpField, Fuel, Intent, Language, Purpose
from voice_agent.domain.models import LowConfidence, ResultRef, Slots, Unsupported
from voice_agent.domain.ports import Usage

ClearableSlot = Literal[
    "budget",
    "body_type",
    "fuel",
    "city",
    "make",
    "model",
    "min_payload_kg",
    "max_km",
    "min_year",
    "purpose",
]


class ExtractedSlots(BaseModel):
    budget_min: int | None = Field(
        default=None, description="Minimum budget in rupees, e.g. 400000"
    )
    budget_max: int | None = Field(
        default=None, description="Maximum budget in rupees, e.g. 500000"
    )
    budget_target: int | None = Field(default=None, description="'around X' budget in rupees")
    body_type: BodyType | None = None
    fuel: Fuel | None = None
    purpose: Purpose | None = None
    city_mention: str | None = Field(default=None, description="City exactly as the user said it")
    make_mention: str | None = Field(default=None, description="Manufacturer exactly as said")
    model_mention: str | None = Field(default=None, description="Model exactly as said")
    min_payload_kg: int | None = None
    max_km: int | None = None
    min_year: int | None = None


class Reference(BaseModel):
    ordinal: int | None = Field(default=None, description="1-based result position; -1 = last one")
    make: str | None = None
    model: str | None = None
    pronoun: bool = Field(default=False, description="True for it / uska / that one")


class TurnIntent(BaseModel):
    intent: Intent
    language: Language = Language.EN
    slots: ExtractedSlots = Field(default_factory=ExtractedSlots)
    clear_slots: list[ClearableSlot] = Field(default_factory=list)
    reference: Reference | None = None
    follow_up_field: FollowUpField | None = None
    confirmation: Literal["yes", "no"] | None = None


class ExtractionContext(BaseModel):
    slots: Slots
    last_results: list[ResultRef] = Field(default_factory=list)
    pending_question: str | None = None


class Understanding(BaseModel):
    turn_intent: TurnIntent
    updates: dict[str, Any] = Field(default_factory=dict)
    low_confidence: list[LowConfidence] = Field(default_factory=list)
    unsupported: list[Unsupported] = Field(default_factory=list)
    usage: list[Usage] = Field(default_factory=list)
    fallbacks: list[str] = Field(default_factory=list)
