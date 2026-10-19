"""Resolve 'the second one' / 'the Mahindra' / 'uska' to a listing id (G3)."""

from collections.abc import Sequence

from voice_agent.domain.models import ResultRef
from voice_agent.understanding.schema import Reference


def resolve_reference(
    ref: Reference | None, last: Sequence[ResultRef], focused: str | None
) -> str | None:
    if not last:
        return None
    if ref is not None and ref.ordinal is not None:
        idx = len(last) - 1 if ref.ordinal == -1 else ref.ordinal - 1
        return last[idx].listing_id if 0 <= idx < len(last) else None
    if ref is not None and (ref.make or ref.model):
        matches = [r for r in last if _matches(r, ref)]
        return matches[0].listing_id if len(matches) == 1 else None  # ambiguous → ask
    if focused is not None and any(r.listing_id == focused for r in last):
        return focused
    return last[0].listing_id


def _matches(r: ResultRef, ref: Reference) -> bool:
    if ref.make and ref.make.lower() not in r.make.lower():
        return False
    return not (ref.model and ref.model.lower() not in r.model.lower())
