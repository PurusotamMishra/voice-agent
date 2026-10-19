from pathlib import Path

import pytest

from tests.fakes import make_listing
from voice_agent.catalog.ranker import DEFAULT_WEIGHTS, load_weights, purpose_fit, rank
from voice_agent.domain.enums import Fuel, Purpose
from voice_agent.domain.models import Slots


def test_contributions_sum_to_score() -> None:
    rows = [make_listing(listing_id="A", price_inr=300_000), make_listing(listing_id="B")]
    for r in rank(rows, Slots(), DEFAULT_WEIGHTS):
        assert r.score == pytest.approx(sum(r.contributions.values()), abs=1e-3)


def test_cheaper_wins_when_all_else_equal() -> None:
    rows = [
        make_listing(listing_id="A", price_inr=450_000),
        make_listing(listing_id="B", price_inr=300_000),
    ]
    assert [r.listing.listing_id for r in rank(rows, Slots(), DEFAULT_WEIGHTS)] == ["B", "A"]


def test_around_target_prefers_closest_price() -> None:
    rows = [
        make_listing(listing_id="A", price_inr=300_000),
        make_listing(listing_id="B", price_inr=590_000),
    ]
    slots = Slots(budget_target=600_000, budget_max=660_000)
    assert rank(rows, slots, DEFAULT_WEIGHTS)[0].listing.listing_id == "B"


def test_around_target_normalises_within_candidates() -> None:
    # Both are >10% from target; the closer one must still win (E2 normalisation).
    # "A" is the far listing, so a tie-break on listing_id would wrongly pick it.
    rows = [
        make_listing(listing_id="A", price_inr=100_000),
        make_listing(listing_id="B", price_inr=300_000),
    ]
    slots = Slots(budget_target=600_000, budget_max=660_000)
    assert [r.listing.listing_id for r in rank(rows, slots, DEFAULT_WEIGHTS)] == ["B", "A"]


def test_purpose_city_delivery_prefers_cng() -> None:
    cng, diesel = make_listing(fuel=Fuel.CNG), make_listing(fuel=Fuel.DIESEL)
    assert purpose_fit(cng, Purpose.CITY_DELIVERY) > purpose_fit(diesel, Purpose.CITY_DELIVERY)
    assert purpose_fit(cng, None) == 0.0


def test_ties_break_by_listing_id_and_top_k() -> None:
    rows = [make_listing(listing_id=f"VH-{i}") for i in (3, 1, 2, 4)]
    out = rank(rows, Slots(), DEFAULT_WEIGHTS, top_k=3)
    assert [r.listing.listing_id for r in out] == ["VH-1", "VH-2", "VH-3"]
    assert [r.rank for r in out] == [1, 2, 3]


def test_load_weights(tmp_path: Path) -> None:
    p = tmp_path / "w.yaml"
    p.write_text("price: 1.0\nlow_km: 0\n")
    assert load_weights(p) == {"price": 1.0, "low_km": 0.0}
    p.write_text("nonsense: 1\n")
    with pytest.raises(ValueError):
        load_weights(p)
