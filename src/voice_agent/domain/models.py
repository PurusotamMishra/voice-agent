"""Shared Pydantic models passed between components (architecture §4)."""

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from voice_agent.domain.enums import AliasKind, BodyType, City, Fuel, Purpose, SellerType

HARD_FIELDS: tuple[str, ...] = (
    "budget_min",
    "budget_max",
    "body_type",
    "fuel",
    "city",
    "make",
    "model",
    "min_payload_kg",
    "max_km",
    "min_year",
)


class Slots(BaseModel):
    """What the buyer has told us so far; shown on screen every turn."""

    model_config = ConfigDict(frozen=True)

    budget_min: int | None = Field(default=None, ge=10_000, le=100_000_000)
    budget_max: int | None = Field(default=None, ge=10_000, le=100_000_000)
    budget_target: int | None = Field(
        default=None, ge=10_000, le=100_000_000
    )  # D5: "around X", ranking only
    body_type: BodyType | None = None
    fuel: Fuel | None = None
    city: City | None = None
    make: str | None = None
    model: str | None = None  # canonical model or model family prefix ("Ace")
    min_payload_kg: int | None = Field(default=None, ge=50, le=60_000)
    max_km: int | None = Field(default=None, ge=1_000, le=3_000_000)
    min_year: int | None = Field(default=None, ge=2000, le=2026)
    purpose: Purpose | None = None  # B4: soft signal only, never a filter

    def filled(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class Filters(BaseModel):
    """Hard constraints derived from Slots. Every non-null field becomes one WHERE clause."""

    model_config = ConfigDict(frozen=True)

    budget_min: int | None = None
    budget_max: int | None = None
    body_type: BodyType | None = None
    fuel: Fuel | None = None
    city: City | None = None
    make: str | None = None
    model: str | None = None
    min_payload_kg: int | None = None
    max_km: int | None = None
    min_year: int | None = None

    @classmethod
    def from_slots(cls, slots: Slots) -> "Filters":
        return cls(**{name: getattr(slots, name) for name in HARD_FIELDS})

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    def replace(self, **changes: Any) -> "Filters":
        return Filters.model_validate({**self.model_dump(), **changes})


class Listing(BaseModel):
    """One row of the listings table (data/README.md)."""

    model_config = ConfigDict(frozen=True)

    listing_id: str
    model_id: str
    make: str
    model: str
    variant: str
    body_type: BodyType
    fuel: Fuel
    year: int
    price_inr: int
    km_driven: int
    payload_kg: int
    gvw_kg: int
    city: City
    registration_state: str
    owners: int
    seller_type: SellerType
    papers_verified: bool
    listing_date: date
    description: str


class ScoredListing(BaseModel):
    """A ranked result with the per-feature data behind its score (E2, Q&A #2)."""

    listing: Listing
    rank: int
    score: float
    features: dict[str, float]
    contributions: dict[str, float]

    def top_reasons(self, n: int = 2) -> list[str]:
        positive = [(v, k) for k, v in self.contributions.items() if v > 0]
        return [k for _, k in sorted(positive, key=lambda p: (-p[0], p[1]))[:n]]


class ResultRef(BaseModel):
    """What conversation memory keeps about a shown result (for 'uska' / 'the second one')."""

    listing_id: str
    rank: int
    make: str
    model: str


class Relaxation(BaseModel):
    """A suggested one-slot loosening that returns at least one row (E3)."""

    slot: str
    old: Any
    new: Any
    count: int


class LowConfidence(BaseModel):
    slot: str
    raw: str
    candidate: str
    score: float


class Unsupported(BaseModel):
    kind: AliasKind
    raw: str
