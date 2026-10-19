"""Hand-written fakes and factories for unit tests (no network, no DB)."""

from datetime import date
from typing import Any

from pydantic import BaseModel

from voice_agent.catalog.filters import constraint_violations
from voice_agent.domain.enums import AliasKind, BodyType, City, Fuel, SellerType
from voice_agent.domain.models import Filters, Listing
from voice_agent.domain.ports import LLMResult, Match, SearchResult, Usage

_DEFAULTS: dict[str, Any] = {
    "listing_id": "VH-0001",
    "model_id": "tata_ace_gold_diesel",
    "make": "Tata",
    "model": "Ace Gold",
    "variant": "Diesel",
    "body_type": BodyType.MINI_TRUCK,
    "fuel": Fuel.DIESEL,
    "year": 2020,
    "price_inr": 400_000,
    "km_driven": 50_000,
    "payload_kg": 750,
    "gvw_kg": 1_750,
    "city": City.PUNE,
    "registration_state": "MH",
    "owners": 1,
    "seller_type": SellerType.DEALER,
    "papers_verified": True,
    "listing_date": date(2026, 9, 1),
    "description": "test listing",
}


def make_listing(**overrides: Any) -> Listing:
    return Listing(**{**_DEFAULTS, **overrides})


class FakeLLM:
    """Returns queued responses in order; an Exception in the queue is raised instead."""

    def __init__(self, responses: list[BaseModel | Exception], name: str = "fake") -> None:
        self.name = name
        self._responses = list(responses)
        self.calls: list[tuple[str, str, type[BaseModel]]] = []

    async def structured(self, system: str, user: str, schema: type[Any]) -> LLMResult[Any]:
        self.calls.append((system, user, schema))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(
            value=item, usage=Usage(provider=self.name, input_tokens=10, output_tokens=5)
        )


class FakeNormalizer:
    """table[(kind, raw_lower)] = (canonical, score); anything else -> no match."""

    def __init__(self, table: dict[tuple[AliasKind, str], tuple[str, float]]) -> None:
        self._table = table

    async def normalize(self, kind: AliasKind, raw: str) -> Match:
        hit = self._table.get((kind, raw.strip().lower()))
        if hit is None:
            return Match(raw=raw, canonical=None, score=0.0, method="none")
        return Match(
            raw=raw,
            canonical=hit[0],
            score=hit[1],
            method="exact" if hit[1] == 1.0 else "trigram",
        )


class FakeCatalog:
    """In-memory Catalog using the same constraint logic as the SQL builder."""

    def __init__(self, listings: list[Listing]) -> None:
        self._listings = listings

    async def search(self, filters: Filters, limit: int = 500) -> SearchResult:
        rows = [x for x in self._listings if not constraint_violations(x, filters)][:limit]
        return SearchResult(rows=rows, sql="-- fake", params=filters.as_dict())

    async def count(self, filters: Filters) -> int:
        return len((await self.search(filters)).rows)

    async def get(self, listing_id: str) -> Listing | None:
        return next((x for x in self._listings if x.listing_id == listing_id), None)
