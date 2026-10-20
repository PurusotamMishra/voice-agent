from tests.fakes import make_listing
from voice_agent.domain.enums import BodyType, City, Fuel, Language
from voice_agent.domain.models import Relaxation, ScoredListing, Slots
from voice_agent.response import templates
from voice_agent.response.factsheet import build_fact_sheet


def test_describe_slots() -> None:
    s = Slots(fuel=Fuel.CNG, body_type=BodyType.PICKUP, city=City.KOLKATA, budget_max=500_000)
    assert templates.describe_slots(s) == "CNG pickup in Kolkata under ₹5 lakh"


def test_zero_results_offers_relaxation_with_count() -> None:
    s = Slots(fuel=Fuel.CNG, city=City.KOLKATA)
    r = Relaxation(slot="fuel", old=Fuel.CNG, new=None, count=4)
    text = templates.zero_results(s, r).text()
    assert "couldn't find any CNG vehicle in Kolkata" in text and "4" in text


def test_describe_slots_includes_payload() -> None:
    s = Slots(fuel=Fuel.CNG, city=City.PUNE, min_payload_kg=2_000)
    assert templates.describe_slots(s) == "CNG vehicle in Pune with at least 2,000 kg payload"


def test_results_template_does_not_repeat_km_from_a_reason() -> None:
    s = ScoredListing(
        listing=make_listing(km_driven=64_000),
        rank=1,
        score=0.9,
        features={},
        contributions={"low_km": 0.3, "papers_verified": 0.15},
    )
    text = templates.results(build_fact_sheet([s], None, Language.EN)).text()
    assert text.count("64,000 km") == 1
