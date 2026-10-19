from tests.fakes import make_listing
from voice_agent.domain.enums import Language
from voice_agent.domain.models import ScoredListing
from voice_agent.response.factsheet import build_fact_sheet
from voice_agent.response.schema import ComposedResponse, ItemSentence
from voice_agent.response.validator import EntityVocab, validate

VOCAB = EntityVocab(
    makes=frozenset({"Tata", "Mahindra"}), models=frozenset({"Ace Gold", "Ace CNG", "Jeeto"})
)
FACTS = build_fact_sheet(
    [
        ScoredListing(
            listing=make_listing(listing_id="A", price_inr=485_000, km_driven=48_000),
            rank=1,
            score=1.0,
            features={},
            contributions={},
        ),
        ScoredListing(
            listing=make_listing(listing_id="B", make="Mahindra", model="Jeeto", price_inr=300_000),
            rank=2,
            score=0.5,
            features={},
            contributions={},
        ),
    ],
    None,
    Language.EN,
)


def resp(a: str, b: str, intro: str = "Here are the best matches.") -> ComposedResponse:
    return ComposedResponse(
        intro=intro,
        closing="Want details?",
        items=[ItemSentence(listing_id="A", text=a), ItemSentence(listing_id="B", text=b)],
    )


def test_clean_response_passes() -> None:
    v = validate(
        resp("The 2020 Tata Ace Gold at ₹4.85 lakh, 48,000 km.", "The Mahindra Jeeto at ₹3 lakh."),
        FACTS,
        VOCAB,
    )
    assert v.ok, v.violations


def test_invented_number_is_caught() -> None:
    v = validate(resp("Tata Ace Gold at ₹4.5 lakh.", "Jeeto at ₹3 lakh."), FACTS, VOCAB)
    assert [(x.where, x.kind, x.detail) for x in v.violations] == [("A", "number", "4.5")]


def test_cross_attribution_is_caught() -> None:
    v = validate(resp("Tata Ace Gold at ₹3 lakh.", "Jeeto at ₹3 lakh."), FACTS, VOCAB)
    assert any(x.kind == "number" and x.where == "A" for x in v.violations)


def test_wrong_vehicle_and_number_words_are_caught() -> None:
    v = validate(resp("A Tata Ace CNG, five years old.", "Jeeto at ₹3 lakh."), FACTS, VOCAB)
    kinds = {x.kind for x in v.violations}
    assert {"entity", "number_word"} <= kinds


def test_order_and_intro_rules() -> None:
    swapped = ComposedResponse(
        intro="I found 2 trucks.",
        items=[
            ItemSentence(listing_id="B", text="Jeeto."),
            ItemSentence(listing_id="A", text="Ace Gold."),
        ],
    )
    kinds = {x.kind for x in validate(swapped, FACTS, VOCAB).violations}
    assert {"order", "number"} <= kinds


ALIAS_VOCAB = EntityVocab(
    makes=frozenset({"Tata", "Mahindra", "Maruti", "Ashok Leyland"}),
    models=frozenset({"Ace Gold", "Ace CNG", "Ace", "Jeeto"}),
    aliases={
        "benz": ("make", "Mercedes-Benz"),
        "leyland": ("make", "Ashok Leyland"),
        "al": ("make", "Ashok Leyland"),
        "suzuki": ("make", "Maruti"),
    },
)


def _bad(
    a: str,
    b: str = "The Mahindra Jeeto at ₹3 lakh.",
    vocab: EntityVocab = VOCAB,
    intro: str = "Here are the best matches.",
    closing: str = "Want details?",
) -> bool:
    r = ComposedResponse(
        intro=intro,
        closing=closing,
        items=[ItemSentence(listing_id="A", text=a), ItemSentence(listing_id="B", text=b)],
    )
    return not validate(r, FACTS, vocab).ok


def test_unit_bound_numbers_bypasses_fail() -> None:
    for s in [
        "Tata Ace Gold at ₹4.85 crore.",
        "Tata Ace Gold at ₹48,000.",
        "Tata Ace Gold at ₹4.85 lakh, 4.85 lakh km.",
        "Tata Ace Gold at ₹750.",
        "Tata Ace Gold, 2020 km.",
        "Tata Ace Gold, just 1 year old.",
        "Tata Ace Gold at ₹4.85 lac, 48,000 kg.",
    ]:
        assert _bad(s), s


def test_alias_and_family_entities() -> None:
    for s in [
        "Maruti Ace Gold at ₹4.85 lakh.",
        "Benz Ace Gold.",
        "Leyland Ace Gold.",
        "AL Ace Gold.",
        "Suzuki Ace Gold.",
    ]:
        assert _bad(s, vocab=ALIAS_VOCAB), s
    assert _bad("Tata Ace Gold at ₹4.85 lakh.", "The Ace at ₹3 lakh.", vocab=ALIAS_VOCAB)
    assert not _bad("The Ace at ₹4.85 lakh.", vocab=ALIAS_VOCAB)
    assert _bad("Tata Ace Gold.", intro="Try the Suzuki.", vocab=ALIAS_VOCAB)
    assert _bad("Tata Ace Gold.", closing="Want the Jeeto?", vocab=ALIAS_VOCAB)


def test_city_and_fuel_mismatch_fail() -> None:
    assert _bad("Tata Ace Gold in Mumbai.")
    assert _bad("A CNG Tata Ace Gold.")
    assert not _bad("Tata Ace Gold in Pune, diesel.")


def test_extra_number_words_fail() -> None:
    for s in [
        "Tata Ace Gold, sixty kilometres.",
        "Tata Ace Gold, a dozen owners.",
        "Tata Ace Gold at half a lakh.",
        "Tata Ace Gold, a couple of picks.",
        "Tata Ace Gold, eighty-five thousand.",
        "Tata Ace Gold, das hazaar.",
        "Tata Ace Gold at ₹4.85 million.",
        "Tata Ace Gold, bees.",
    ]:
        assert _bad(s), s


def test_wheeler_body_type_words_are_not_number_words() -> None:
    assert not _bad(
        "The Tata Ace Gold at ₹4.85 lakh.", "The Mahindra Jeeto three-wheeler at ₹3 lakh."
    )
    assert not _bad("Tata Ace Gold at ₹4.85 lakh.", "The Mahindra Jeeto four wheeler at ₹3 lakh.")
    assert _bad("Tata Ace Gold at ₹4.85 lakh.", "The Mahindra Jeeto, three owners, ₹3 lakh.")
    assert _bad("Tata Ace Gold at ₹4.85 lakh.", "The Mahindra Jeeto three-wheeler, two owners.")


def test_listing_id_in_spoken_text_is_caught() -> None:
    v = validate(
        resp("VH-0077: the Tata Ace Gold at ₹4.85 lakh.", "The Mahindra Jeeto at ₹3 lakh."),
        FACTS,
        VOCAB,
    )
    assert [(x.where, x.kind, x.detail) for x in v.violations] == [
        ("A", "number", "listing id VH-0077 in spoken text")
    ]
    v2 = validate(resp("Tata Ace Gold.", "Jeeto.", intro="Options vh-12 here."), FACTS, VOCAB)
    assert [(x.where, x.kind) for x in v2.violations] == [("intro", "number")]
