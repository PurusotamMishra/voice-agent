from voice_agent.domain.enums import AliasKind, BodyType, Fuel, Intent
from voice_agent.understanding.rules import rules_extract

ALIASES = {
    AliasKind.BODY_TYPE: {"pickup": "pickup", "chhota truck": "mini_truck"},
    AliasKind.FUEL: {"cng": "cng", "gas wali": "cng"},
    AliasKind.CITY: {"pune": "pune", "bombay": "mumbai"},
    AliasKind.MAKE: {"tata": "Tata"},
    AliasKind.MODEL: {"ace": "Ace"},
}


def test_rules_extract_keywords() -> None:
    ti = rules_extract("Chhota truck chahiye, gas wali, Bombay mein", ALIASES)
    assert ti.intent is Intent.SEARCH
    assert ti.slots.body_type is BodyType.MINI_TRUCK and ti.slots.fuel is Fuel.CNG
    assert ti.slots.city_mention == "bombay"


def test_rules_extract_reset() -> None:
    assert rules_extract("start over please", ALIASES).intent is Intent.RESET


def test_rules_yes_no_with_pending_question() -> None:
    yes = rules_extract("haan", ALIASES, "Did you mean Ace?")
    assert yes.intent is Intent.RELAX and yes.confirmation == "yes"
    no = rules_extract("Nahi.", ALIASES, "Did you mean Ace?")
    assert no.intent is Intent.SEARCH and no.confirmation == "no"
    assert rules_extract("haan", ALIASES).confirmation is None
