from voice_agent.catalog.relax import candidate_changes, propose_relaxation
from voice_agent.domain.enums import BodyType, City, Fuel
from voice_agent.domain.models import Filters

NEIGHBORS = {City.KOLKATA: [City.LUCKNOW, City.HYDERABAD]}


def test_candidate_order_budget_then_city_then_fuel() -> None:
    f = Filters(budget_max=500_000, city=City.KOLKATA, fuel=Fuel.CNG, body_type=BodyType.PICKUP)
    assert candidate_changes(f, NEIGHBORS) == [
        ("budget_max", 600_000),
        ("city", City.LUCKNOW),
        ("city", City.HYDERABAD),
        ("fuel", None),
        ("body_type", BodyType.MINI_TRUCK),
    ]


async def test_proposes_first_change_with_results() -> None:
    f = Filters(city=City.KOLKATA, fuel=Fuel.CNG)

    async def count(g: Filters) -> int:
        return 4 if g.fuel is None else 0

    r = await propose_relaxation(f, count, NEIGHBORS)
    assert r is not None and (r.slot, r.old, r.new, r.count) == ("fuel", Fuel.CNG, None, 4)


async def test_returns_none_when_nothing_helps() -> None:
    async def count(_: Filters) -> int:
        return 0

    assert await propose_relaxation(Filters(fuel=Fuel.CNG), count, NEIGHBORS) is None
