"""Zero-result relaxation (E3): find the smallest one-slot loosening with ≥1 row. Never auto-applied."""

import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from voice_agent.domain.enums import BodyType, City
from voice_agent.domain.models import Filters, Relaxation

CountFn = Callable[[Filters], Awaitable[int]]

ADJACENT_BODY: dict[BodyType, BodyType] = {
    BodyType.MINI_TRUCK: BodyType.PICKUP,
    BodyType.PICKUP: BodyType.MINI_TRUCK,
    BodyType.THREE_WHEELER: BodyType.MINI_TRUCK,
    BodyType.CARGO_VAN: BodyType.MINI_TRUCK,
    BodyType.LCV: BodyType.ICV,
    BodyType.ICV: BodyType.LCV,
    BodyType.TIPPER: BodyType.ICV,
}
_DROPPABLE = ("min_year", "max_km", "min_payload_kg", "model", "make", "budget_min")


def candidate_changes(
    f: Filters, neighbors: Mapping[City, Sequence[City]]
) -> list[tuple[str, Any]]:
    """Ordered smallest-change first: +20% budget, nearby city, any fuel, adjacent body, drop extras."""
    changes: list[tuple[str, Any]] = []
    if f.budget_max is not None:
        changes.append(("budget_max", _round_up(f.budget_max * 1.2, 10_000)))
    if f.city is not None:
        changes.extend(("city", n) for n in neighbors.get(f.city, []))
    if f.fuel is not None:
        changes.append(("fuel", None))
    if f.body_type is not None:
        changes.append(("body_type", ADJACENT_BODY[f.body_type]))
    changes.extend((name, None) for name in _DROPPABLE if getattr(f, name) is not None)
    return changes


async def propose_relaxation(
    f: Filters, count: CountFn, neighbors: Mapping[City, Sequence[City]]
) -> Relaxation | None:
    for slot, new in candidate_changes(f, neighbors):
        n = await count(f.replace(**{slot: new}))
        if n > 0:
            return Relaxation(slot=slot, old=getattr(f, slot), new=new, count=n)
    return None


def _round_up(value: float, step: int) -> int:
    return int(math.ceil(value / step) * step)
