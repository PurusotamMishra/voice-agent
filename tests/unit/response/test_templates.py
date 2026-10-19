from voice_agent.domain.enums import BodyType, City, Fuel
from voice_agent.domain.models import Relaxation, Slots
from voice_agent.response import templates


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
