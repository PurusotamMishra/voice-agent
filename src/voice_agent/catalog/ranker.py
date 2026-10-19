"""Transparent weighted ranking (E2): every score is a sum of visible per-feature contributions."""

from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml

from voice_agent.domain.enums import BodyType, Fuel, Purpose
from voice_agent.domain.models import Listing, ScoredListing, Slots

DEFAULT_WEIGHTS: dict[str, float] = {
    "price": 0.30,
    "low_km": 0.20,
    "newer_year": 0.20,
    "papers_verified": 0.15,
    "purpose_fit": 0.15,
}
_SMALL_BODIES = {BodyType.THREE_WHEELER, BodyType.MINI_TRUCK, BodyType.PICKUP, BodyType.CARGO_VAN}
_CITY_FUEL = {Fuel.CNG: 1.0, Fuel.ELECTRIC: 1.0, Fuel.PETROL: 0.6, Fuel.DIESEL: 0.4}


def load_weights(path: Path) -> dict[str, float]:
    raw = yaml.safe_load(path.read_text()) or {}
    unknown = set(raw) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise ValueError(f"unknown ranking features: {sorted(unknown)}")
    return {name: float(value) for name, value in raw.items()}


def rank(
    rows: Sequence[Listing], slots: Slots, weights: Mapping[str, float], top_k: int = 3
) -> list[ScoredListing]:
    if not rows:
        return []
    prices = [r.price_inr for r in rows]
    kms = [r.km_driven for r in rows]
    years = [r.year for r in rows]
    scored: list[tuple[float, str, Listing, dict[str, float], dict[str, float]]] = []
    for r in rows:
        features = {
            "price": _price_feature(r.price_inr, prices, slots.budget_target),
            "low_km": _inverted(r.km_driven, kms),
            "newer_year": _scaled(r.year, years),
            "papers_verified": 1.0 if r.papers_verified else 0.0,
            "purpose_fit": purpose_fit(r, slots.purpose),
        }
        contributions = {k: round(weights.get(k, 0.0) * v, 4) for k, v in features.items()}
        scored.append(
            (round(sum(contributions.values()), 4), r.listing_id, r, features, contributions)
        )
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [
        ScoredListing(listing=r, rank=i + 1, score=score, features=f, contributions=c)
        for i, (score, _, r, f, c) in enumerate(scored[:top_k])
    ]


def purpose_fit(listing: Listing, purpose: Purpose | None) -> float:
    if purpose is None:
        return 0.0
    if purpose is Purpose.CITY_DELIVERY:
        size = 1.0 if listing.body_type in _SMALL_BODIES else 0.3
        return round((_CITY_FUEL[listing.fuel] + size) / 2, 4)
    if purpose is Purpose.LONG_HAUL:
        fuel = 1.0 if listing.fuel is Fuel.DIESEL else 0.2
        size = 1.0 if listing.payload_kg >= 3_000 else 0.5 if listing.payload_kg >= 1_000 else 0.0
        return round((fuel + size) / 2, 4)
    if purpose is Purpose.CONSTRUCTION:
        return {BodyType.TIPPER: 1.0, BodyType.ICV: 0.6, BodyType.LCV: 0.6}.get(
            listing.body_type, 0.2
        )
    return {BodyType.PICKUP: 1.0, BodyType.MINI_TRUCK: 0.8, BodyType.THREE_WHEELER: 0.6}.get(
        listing.body_type, 0.4
    )


def _scaled(value: int, values: Sequence[int]) -> float:
    lo, hi = min(values), max(values)
    return 1.0 if hi == lo else round((value - lo) / (hi - lo), 4)


def _inverted(value: int, values: Sequence[int]) -> float:
    lo, hi = min(values), max(values)
    return 1.0 if hi == lo else round((hi - value) / (hi - lo), 4)


def _price_feature(price: int, prices: Sequence[int], target: int | None) -> float:
    if target is None:
        return _inverted(price, prices)
    # E2: distance is normalised by the farthest candidate, so the feature spans [0, 1]
    # within this candidate set rather than being zeroed by a fixed band.
    max_distance = max(abs(p - target) for p in prices)
    if max_distance == 0:
        return 1.0
    return round(1.0 - abs(price - target) / max_distance, 4)
