from voice_agent.domain.models import ResultRef
from voice_agent.state.references import resolve_reference
from voice_agent.understanding.schema import Reference

LAST = [
    ResultRef(listing_id="A", rank=1, make="Tata", model="Ace Gold"),
    ResultRef(listing_id="B", rank=2, make="Mahindra", model="Jeeto"),
    ResultRef(listing_id="C", rank=3, make="Tata", model="Intra"),
]


def test_ordinal_and_last() -> None:
    assert resolve_reference(Reference(ordinal=2), LAST, None) == "B"
    assert resolve_reference(Reference(ordinal=-1), LAST, None) == "C"
    assert resolve_reference(Reference(ordinal=7), LAST, None) is None


def test_make_unique_vs_ambiguous() -> None:
    assert resolve_reference(Reference(make="mahindra"), LAST, None) == "B"
    assert resolve_reference(Reference(make="Tata"), LAST, None) is None


def test_pronoun_uses_focus_then_first() -> None:
    assert resolve_reference(Reference(pronoun=True), LAST, "C") == "C"
    assert resolve_reference(Reference(pronoun=True), LAST, None) == "A"
    assert resolve_reference(None, [], None) is None


def test_pronoun_ignores_stale_focus() -> None:
    assert resolve_reference(Reference(pronoun=True), LAST, "Z") == "A"
