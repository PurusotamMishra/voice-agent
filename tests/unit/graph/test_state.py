from typing import Any

from tests.fakes import make_listing
from voice_agent.domain.enums import (
    AliasKind,
    BodyType,
    City,
    FollowUpField,
    Fuel,
    Intent,
    Language,
    Purpose,
)
from voice_agent.domain.models import (
    Filters,
    LowConfidence,
    Relaxation,
    ResultRef,
    ScoredListing,
    Slots,
    Unsupported,
)
from voice_agent.domain.ports import Usage
from voice_agent.graph.state import checkpoint_serde
from voice_agent.response.schema import ComposedResponse, ItemSentence, Verdict, Violation
from voice_agent.state.models import PendingConfirmation, Route
from voice_agent.understanding.schema import ExtractedSlots, Reference, TurnIntent, Understanding


def _full_state() -> dict[str, Any]:
    slots = Slots(
        budget_max=500_000,
        body_type=BodyType.PICKUP,
        fuel=Fuel.CNG,
        city=City.PUNE,
        purpose=Purpose.CITY_DELIVERY,
    )
    listing = make_listing()
    return {
        "turn": 3,
        "slots": slots,
        "pending_confirmation": PendingConfirmation(
            slot="city", raw="pun", candidate="pune", score=0.4, deferred_updates={"fuel": Fuel.CNG}
        ),
        "pending_relaxation": Relaxation(slot="fuel", old=Fuel.CNG, new=None, count=3),
        "last_results": [ResultRef(listing_id="VH-0001", rank=1, make="Tata", model="Ace Gold")],
        "understanding": Understanding(
            turn_intent=TurnIntent(
                intent=Intent.FOLLOW_UP,
                language=Language.HINGLISH,
                slots=ExtractedSlots(fuel=Fuel.CNG),
                reference=Reference(ordinal=2),
                follow_up_field=FollowUpField.PAYLOAD,
            ),
            low_confidence=[LowConfidence(slot="city", raw="pun", candidate="pune", score=0.4)],
            unsupported=[Unsupported(kind=AliasKind.CITY, raw="Goa")],
            usage=[Usage(provider="groq", input_tokens=1, output_tokens=2)],
        ),
        "slot_diff": {"fuel": (None, "cng")},
        "route": Route(
            kind="follow_up",
            listing_id="VH-0001",
            follow_up_field=FollowUpField.PAYLOAD,
            unsupported=[Unsupported(kind=AliasKind.MAKE, raw="Ferrari")],
        ),
        "filters": Filters.from_slots(slots),
        "candidates": [listing],
        "results": [
            ScoredListing(
                listing=listing,
                rank=1,
                score=0.5,
                features={"price": 1.0},
                contributions={"price": 0.3},
            )
        ],
        "response": ComposedResponse(items=[ItemSentence(listing_id="VH-0001", text="Hi.")]),
        "verdict": Verdict(
            ok=False, source="llm", violations=[Violation(where="intro", kind="number", detail="5")]
        ),
        "usage": [Usage(provider="groq")],
    }


def test_checkpoint_serde_round_trips_every_state_type() -> None:
    serde = checkpoint_serde()
    state = _full_state()
    loaded = serde.loads_typed(serde.dumps_typed(state))
    # msgpack has no tuple type; slot_diff is per-turn and TurnResult lists it anyway
    assert loaded.pop("slot_diff") == {"fuel": [None, "cng"]}
    state.pop("slot_diff")
    assert loaded == state
