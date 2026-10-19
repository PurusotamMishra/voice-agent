"""Pure conversation-state transitions (G1-G3, D6, E3). No I/O."""

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import ValidationError

from voice_agent.domain.enums import FollowUpField, Intent
from voice_agent.domain.models import Slots
from voice_agent.state.models import Memory, PendingConfirmation, Route, SlotDiff
from voice_agent.state.references import resolve_reference
from voice_agent.understanding.schema import Understanding


def sanitize_updates(updates: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """D7: drop unknown keys and out-of-range/invalid values instead of passing them on."""
    valid: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in updates.items():
        if key not in Slots.model_fields:
            dropped.append(key)
            continue
        try:
            Slots.model_validate({key: value})
        except ValidationError:
            dropped.append(key)
            continue
        valid[key] = value
    return valid, dropped


def merge_slots(old: Slots, updates: Mapping[str, Any]) -> tuple[Slots, SlotDiff]:
    new = Slots.model_validate({**old.model_dump(), **updates})
    diff = {
        name: (_plain(getattr(old, name)), _plain(getattr(new, name)))
        for name in Slots.model_fields
        if getattr(old, name) != getattr(new, name)
    }
    return new, diff


def apply_understanding(mem: Memory, u: Understanding) -> tuple[Memory, SlotDiff, Route]:
    ti = u.turn_intent
    if u.unsupported:
        return mem, {}, Route(kind="unsupported", unsupported=u.unsupported)

    if mem.pending_confirmation is not None and ti.confirmation is not None:
        pending = mem.pending_confirmation
        updates = dict(u.updates)
        if ti.confirmation == "yes":
            updates = {**pending.deferred_updates, pending.slot: pending.candidate, **updates}
        return _search_with(mem, updates)

    if u.low_confidence:
        lc = u.low_confidence[0]
        pending = PendingConfirmation(
            slot=lc.slot,
            raw=lc.raw,
            candidate=lc.candidate,
            score=lc.score,
            deferred_updates=u.updates,
        )
        return mem.model_copy(update={"pending_confirmation": pending}), {}, Route(kind="confirm")

    if ti.intent is Intent.RESET:
        diff = {k: (v, None) for k, v in mem.slots.filled().items()}
        return Memory(), diff, Route(kind="reset")

    if ti.intent is Intent.OUT_OF_DOMAIN:
        return _clear_pending(mem), {}, Route(kind="out_of_domain")

    if ti.intent is Intent.FOLLOW_UP:
        listing_id = resolve_reference(ti.reference, mem.last_results, mem.focused_listing_id)
        if listing_id is None:
            return _clear_pending(mem), {}, Route(kind="which_one")
        return (
            _clear_pending(mem).model_copy(update={"focused_listing_id": listing_id}),
            {},
            Route(
                kind="follow_up",
                listing_id=listing_id,
                follow_up_field=ti.follow_up_field or FollowUpField.SUMMARY,
            ),
        )

    if ti.intent is Intent.RELAX and mem.pending_relaxation is not None:
        r = mem.pending_relaxation
        return _search_with(mem, {r.slot: r.new})

    return _search_with(mem, u.updates)


def _search_with(mem: Memory, updates: Mapping[str, Any]) -> tuple[Memory, SlotDiff, Route]:
    valid, _ = sanitize_updates(updates)
    slots, diff = merge_slots(mem.slots, valid)
    new_mem = mem.model_copy(
        update={"slots": slots, "pending_confirmation": None, "pending_relaxation": None}
    )
    if not slots.filled():
        return new_mem, diff, Route(kind="need_info")
    return new_mem, diff, Route(kind="search")


def _clear_pending(mem: Memory) -> Memory:
    if mem.pending_confirmation is None:
        return mem
    return mem.model_copy(update={"pending_confirmation": None})


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value
