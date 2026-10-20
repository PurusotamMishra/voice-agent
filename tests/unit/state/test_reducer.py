from voice_agent.domain.enums import AliasKind, BodyType, City, FollowUpField, Fuel, Intent
from voice_agent.domain.models import LowConfidence, Relaxation, ResultRef, Slots, Unsupported
from voice_agent.state.models import Memory, PendingConfirmation
from voice_agent.state.reducer import apply_understanding, merge_slots, sanitize_updates
from voice_agent.understanding.schema import Reference, TurnIntent, Understanding


def u(intent: Intent = Intent.SEARCH, **kw: object) -> Understanding:
    ti_fields = {k: kw.pop(k) for k in ("reference", "follow_up_field", "confirmation") if k in kw}
    return Understanding(turn_intent=TurnIntent(intent=intent, **ti_fields), **kw)  # type: ignore[arg-type]


BASE = Memory(slots=Slots(fuel=Fuel.DIESEL, body_type=BodyType.PICKUP, city=City.MUMBAI))


def test_correction_changes_exactly_one_slot() -> None:
    mem, diff, route = apply_understanding(BASE, u(Intent.CORRECT, updates={"fuel": Fuel.CNG}))
    assert diff == {"fuel": ("diesel", "cng")}
    assert mem.slots.city is City.MUMBAI and route.kind == "search"


def test_search_merges_and_reports_diff() -> None:
    mem, diff, _ = apply_understanding(BASE, u(updates={"budget_max": 400_000}))
    assert diff == {"budget_max": (None, 400_000)} and mem.slots.fuel is Fuel.DIESEL


def test_reset_clears_everything() -> None:
    mem, diff, route = apply_understanding(BASE, u(Intent.RESET))
    assert mem.slots == Slots() and route.kind == "reset" and "fuel" in diff


def test_empty_slots_need_info() -> None:
    _, _, route = apply_understanding(Memory(), u(updates={}))
    assert route.kind == "need_info"


def test_low_confidence_defers_updates_until_confirmed() -> None:
    lc = LowConfidence(slot="model", raw="aace", candidate="Ace", score=0.5)
    mem, diff, route = apply_understanding(
        Memory(), u(updates={"city": City.PUNE}, low_confidence=[lc])
    )
    assert route.kind == "confirm" and diff == {} and mem.slots == Slots()
    mem2, _, route2 = apply_understanding(mem, u(confirmation="yes"))
    assert mem2.slots.model == "Ace" and mem2.slots.city is City.PUNE
    assert route2.kind == "search" and mem2.pending_confirmation is None


def test_relax_applies_pending_relaxation_as_one_slot_change() -> None:
    mem = BASE.model_copy(
        update={
            "pending_relaxation": Relaxation(slot="city", old=City.MUMBAI, new=City.PUNE, count=3)
        }
    )
    mem2, diff, route = apply_understanding(mem, u(Intent.RELAX))
    assert diff == {"city": ("mumbai", "pune")} and route.kind == "search"
    assert mem2.pending_relaxation is None


def test_follow_up_resolves_and_focuses() -> None:
    mem = BASE.model_copy(
        update={
            "last_results": [
                ResultRef(listing_id="A", rank=1, make="Tata", model="Ace Gold"),
                ResultRef(listing_id="B", rank=2, make="Tata", model="Intra"),
            ]
        }
    )
    mem2, _, route = apply_understanding(
        mem,
        u(Intent.FOLLOW_UP, reference=Reference(ordinal=2), follow_up_field=FollowUpField.PAYLOAD),
    )
    assert route.kind == "follow_up" and route.listing_id == "B"
    assert mem2.focused_listing_id == "B"


def test_unsupported_mention_keeps_other_updates_without_search() -> None:
    pending = PendingConfirmation(slot="model", raw="aace", candidate="Ace", score=0.5)
    mem0 = BASE.model_copy(update={"pending_confirmation": pending})
    bad = Unsupported(kind=AliasKind.CITY, raw="Nagpur")
    mem, diff, route = apply_understanding(
        mem0, u(updates={"make": "Tata", "budget_max": 500_000}, unsupported=[bad])
    )
    assert route.kind == "unsupported" and route.unsupported == [bad]
    assert mem.slots.make == "Tata" and mem.slots.budget_max == 500_000
    assert mem.slots.city is City.MUMBAI  # the unknown city never replaces the old one
    assert diff == {"make": (None, "Tata"), "budget_max": (None, 500_000)}
    assert mem.pending_confirmation is None and mem.pending_relaxation is None


def test_sanitize_drops_invalid_values() -> None:
    valid, dropped = sanitize_updates({"budget_max": 5, "city": "pune", "colour": "red"})
    assert valid == {"city": "pune"} and sorted(dropped) == ["budget_max", "colour"]


def test_merge_slots_validates_enums() -> None:
    slots, diff = merge_slots(Slots(), {"city": "pune"})
    assert slots.city is City.PUNE and diff == {"city": (None, "pune")}


def _pending_mem() -> Memory:
    lc = LowConfidence(slot="model", raw="aace", candidate="Ace", score=0.5)
    mem, _, _ = apply_understanding(Memory(), u(updates={"city": City.PUNE}, low_confidence=[lc]))
    assert mem.pending_confirmation is not None
    return mem


def test_out_of_domain_clears_pending_confirmation() -> None:
    mem, _, _ = apply_understanding(_pending_mem(), u(Intent.OUT_OF_DOMAIN))
    assert mem.pending_confirmation is None
    mem2, _, _ = apply_understanding(mem, u(confirmation="yes"))
    assert mem2.slots == Slots()


def test_follow_up_clears_pending_confirmation() -> None:
    mem = _pending_mem().model_copy(
        update={"last_results": [ResultRef(listing_id="A", rank=1, make="Tata", model="Ace")]}
    )
    mem2, _, route = apply_understanding(mem, u(Intent.FOLLOW_UP, reference=Reference(ordinal=1)))
    assert route.kind == "follow_up" and mem2.pending_confirmation is None
    mem3, _, route3 = apply_understanding(_pending_mem(), u(Intent.FOLLOW_UP))
    assert route3.kind == "which_one" and mem3.pending_confirmation is None


def test_search_with_invalid_updates_does_not_raise() -> None:
    mem, diff, _ = apply_understanding(BASE, u(updates={"budget_max": 5, "city": "pune"}))
    assert mem.slots.city is City.PUNE and mem.slots.budget_max is None
    assert diff == {"city": ("mumbai", "pune")}


def test_budget_bounds_from_two_turns_are_both_kept() -> None:
    # Turn 1 "under 5 lakh" writes only the max; turn 2 "at least 3 lakh" only the min.
    mem, _, _ = apply_understanding(
        Memory(), u(updates={"budget_max": 500_000, "budget_target": None})
    )
    mem2, diff, _ = apply_understanding(mem, u(updates={"budget_min": 300_000}))
    assert (mem2.slots.budget_min, mem2.slots.budget_max) == (300_000, 500_000)
    assert diff == {"budget_min": (None, 300_000)}


RELAX_MEM = BASE.model_copy(
    update={"pending_relaxation": Relaxation(slot="city", old=City.MUMBAI, new=City.PUNE, count=3)}
)


def test_no_declines_relaxation_without_searching() -> None:
    mem, diff, route = apply_understanding(RELAX_MEM, u(confirmation="no"))
    assert route.kind == "relax_declined" and diff == {}
    assert mem.pending_relaxation is None and mem.slots == BASE.slots


def test_no_with_a_new_value_searches_with_it() -> None:
    mem, diff, route = apply_understanding(
        RELAX_MEM, u(confirmation="no", updates={"fuel": Fuel.CNG})
    )
    assert route.kind == "search" and diff == {"fuel": ("diesel", "cng")}
    assert mem.pending_relaxation is None


def test_yes_labelled_search_accepts_relaxation() -> None:
    _, diff, route = apply_understanding(RELAX_MEM, u(Intent.SEARCH, confirmation="yes"))
    assert route.kind == "search" and diff == {"city": ("mumbai", "pune")}
