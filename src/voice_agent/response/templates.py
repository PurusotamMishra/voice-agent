"""Deterministic responses: the fallback for LLM composition and the only path for all other turns.

Templates render only catalog fields (via the fact sheet) and the user's own slots, so they are
trusted by construction. English only in Plan 1; Hinglish variants arrive in Plan 2.
"""

from collections.abc import Sequence

from voice_agent.domain.enums import AliasKind, BodyType, City, FollowUpField, Fuel
from voice_agent.domain.models import Relaxation, Slots, Unsupported
from voice_agent.response.factsheet import BODY_LABEL, FactItem, FactSheet
from voice_agent.response.formatting import format_kg, format_km, format_price
from voice_agent.response.schema import ComposedResponse, ItemSentence
from voice_agent.state.models import PendingConfirmation

ORDINALS = ("First", "Second", "Third")
SLOT_LABEL = {
    "min_year": "model year",
    "max_km": "kilometre",
    "min_payload_kg": "payload",
    "model": "model",
    "make": "brand",
    "budget_min": "minimum budget",
}
_SIMPLE = {
    "reset": "Okay, starting fresh. What vehicle are you looking for?",
    "out_of_domain": "I can help you find a used commercial vehicle. What are you looking for?",
    "need_info": "Tell me what you need: vehicle type, budget, city or fuel.",
    "which_one": "Which one do you mean: the first, second or third?",
    "relax_declined": "Okay. Tell me what to change: budget, city, fuel or vehicle type.",
    "error": "Sorry, something went wrong on my side. Could you say that again?",
}


def _say(text: str) -> ComposedResponse:
    return ComposedResponse(intro=text)


def simple(kind: str) -> ComposedResponse:
    return _say(_SIMPLE[kind])


def results(facts: FactSheet) -> ComposedResponse:
    items = []
    for i in facts.items:
        # The sentence already states price and km; skip reasons that would repeat them.
        reasons = [r for r in i.reasons if i.price not in r and i.km not in r]
        tail = f", {', '.join(reasons)}" if reasons else ""
        text = f"{ORDINALS[i.rank - 1]}, the {i.title} in {i.city} at {i.price}, {i.km}{tail}."
        items.append(ItemSentence(listing_id=i.listing_id, text=text))
    return ComposedResponse(
        intro="Here are the best matches.", items=items, closing="Want details on any of these?"
    )


def describe_slots(slots: Slots) -> str:
    noun = BODY_LABEL[slots.body_type] if slots.body_type else "vehicle"
    parts = []
    if slots.fuel:
        parts.append("CNG" if slots.fuel is Fuel.CNG else slots.fuel.value)
    if slots.make:
        parts.append(slots.make)
    if slots.model:
        parts.append(slots.model)
    parts.append(noun)
    if slots.city:
        parts.append(f"in {slots.city.value.title()}")
    if slots.budget_min and slots.budget_max:
        lo, hi = format_price(slots.budget_min), format_price(slots.budget_max)
        parts.append(f"between {lo} and {hi}")
    elif slots.budget_max:
        parts.append(f"under {format_price(slots.budget_max)}")
    elif slots.budget_min:
        parts.append(f"above {format_price(slots.budget_min)}")
    if slots.max_km:
        parts.append(f"under {format_km(slots.max_km)}")
    if slots.min_year:
        parts.append(f"from {slots.min_year} or newer")
    if slots.min_payload_kg:
        parts.append(f"with at least {format_kg(slots.min_payload_kg)} payload")
    return " ".join(parts)


def zero_results(slots: Slots, relaxation: Relaxation | None) -> ComposedResponse:
    intro = f"I couldn't find any {describe_slots(slots)}."
    closing = _offer(relaxation) if relaxation else "Try changing the budget, city or fuel."
    return ComposedResponse(intro=intro, closing=closing)


def _offer(r: Relaxation) -> str:
    n = r.count
    are, s = ("is", "") if n == 1 else ("are", "s")
    if r.slot == "budget_max":
        return (
            f"If you can go up to {format_price(int(r.new))}, there {are} {n} option{s}. "
            "Shall I show them?"
        )
    if r.slot == "city":
        return f"There {are} {n} in {City(r.new).value.title()}. Want to see those?"
    if r.slot == "fuel":
        return f"With any fuel, there {are} {n}. Shall I include all fuels?"
    if r.slot == "body_type":
        return f"I found {n} {BODY_LABEL[BodyType(r.new)]} option{s} instead. Want to see them?"
    return f"Without the {SLOT_LABEL.get(r.slot, r.slot)} limit, there {are} {n}. Shall I drop it?"


def confirm(pending: PendingConfirmation) -> ComposedResponse:
    return _say(f"Just to check, did you mean {pending.candidate}?")


def unsupported(items: Sequence[Unsupported]) -> ComposedResponse:
    first = items[0]
    if first.kind is AliasKind.CITY:
        cities = ", ".join(c.value.title() for c in City)
        return _say(f"Sorry, I don't have listings in {first.raw.title()}. I cover {cities}.")
    return _say(f"Sorry, I couldn't find {first.raw} in the catalog.")


def follow_up(item: FactItem, field: FollowUpField) -> ComposedResponse:
    papers = (
        f"Its {item.papers}."
        if item.papers.startswith("papers verified")
        else "Its papers are not verified yet."
    )
    answers = {
        FollowUpField.PRICE: f"The {item.title} is priced at {item.price}.",
        FollowUpField.KM: f"It has done {item.km}.",
        FollowUpField.PAYLOAD: f"Its payload is {item.payload}.",
        FollowUpField.GVW: f"Its gross vehicle weight is {item.gvw}.",
        FollowUpField.YEAR: f"It's a {item.year} model.",
        FollowUpField.FUEL: f"It runs on {item.fuel}.",
        FollowUpField.OWNERS: f"It has had {item.owners}.",
        FollowUpField.PAPERS: papers,
        FollowUpField.CITY: f"It's listed in {item.city}.",
        FollowUpField.SELLER: f"It's sold by {item.seller}.",
        FollowUpField.REGISTRATION: f"It's registered in {item.registration}.",
        FollowUpField.SUMMARY: (
            f"The {item.title} in {item.city}: {item.price}, {item.km}, "
            f"{item.payload} payload, {item.owners}, {item.papers}."
        ),
    }
    text = answers.get(field)
    if text is None:
        text = (
            "That detail isn't in the listing. I can tell you the price, km, payload, year, "
            "fuel, owners, papers or location."
        )
    return ComposedResponse(items=[ItemSentence(listing_id=item.listing_id, text=text)])
