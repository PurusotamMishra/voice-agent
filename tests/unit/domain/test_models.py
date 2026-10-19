import pytest
from pydantic import ValidationError

from voice_agent.domain.enums import BodyType, City, Fuel, Purpose
from voice_agent.domain.models import Filters, Slots


def test_filters_from_slots_excludes_purpose_and_target() -> None:
    slots = Slots(
        budget_max=500_000,
        budget_target=450_000,
        body_type=BodyType.MINI_TRUCK,
        city=City.PUNE,
        purpose=Purpose.CITY_DELIVERY,
    )
    assert Filters.from_slots(slots).as_dict() == {
        "budget_max": 500_000,
        "body_type": "mini_truck",
        "city": "pune",
    }


def test_slots_reject_out_of_range_budget() -> None:
    with pytest.raises(ValidationError):
        Slots(budget_max=5)


def test_filters_replace_returns_new_object() -> None:
    f = Filters(fuel=Fuel.CNG)
    g = f.replace(fuel=None)
    assert f.fuel is Fuel.CNG and g.fuel is None
