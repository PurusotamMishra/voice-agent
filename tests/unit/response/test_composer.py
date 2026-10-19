from tests.fakes import FakeLLM, make_listing
from voice_agent.domain.enums import Language
from voice_agent.domain.models import ScoredListing
from voice_agent.domain.ports import ProviderError
from voice_agent.response.composer import compose_results
from voice_agent.response.factsheet import build_fact_sheet
from voice_agent.response.schema import ComposedResponse, ItemSentence
from voice_agent.response.validator import EntityVocab

VOCAB = EntityVocab(makes=frozenset({"Tata"}), models=frozenset({"Ace Gold"}))
FACTS = build_fact_sheet(
    [
        ScoredListing(
            listing=make_listing(listing_id="A", price_inr=485_000),
            rank=1,
            score=1,
            features={},
            contributions={},
        )
    ],
    None,
    Language.EN,
)
GOOD = ComposedResponse(
    intro="Here is a match.",
    closing="Want details?",
    items=[ItemSentence(listing_id="A", text="Tata Ace Gold at ₹4.85 lakh.")],
)
BAD = ComposedResponse(items=[ItemSentence(listing_id="A", text="Tata Ace Gold at ₹4 lakh.")])


async def test_first_attempt_passes() -> None:
    out = await compose_results(FACTS, FakeLLM([GOOD]), VOCAB)
    assert out.verdict.ok and out.attempts == 1 and out.fallbacks == []


async def test_retry_with_violations_then_pass() -> None:
    llm = FakeLLM([BAD, GOOD])
    out = await compose_results(FACTS, llm, VOCAB)
    assert out.verdict.ok and out.attempts == 2 and out.fallbacks == ["regenerated"]
    assert "number" in llm.calls[1][1]  # violations fed back into the retry prompt


async def test_template_after_two_failures_or_outage() -> None:
    out = await compose_results(FACTS, FakeLLM([BAD, BAD]), VOCAB)
    assert out.verdict.source == "template" and "template" in out.fallbacks
    out2 = await compose_results(FACTS, FakeLLM([ProviderError("groq", "down")]), VOCAB)
    assert out2.verdict.source == "template" and out2.response.items[0].listing_id == "A"


async def test_system_prompt_states_unit_rule_and_outage_attempts() -> None:
    llm = FakeLLM([ProviderError("groq", "down")])
    out = await compose_results(FACTS, llm, VOCAB)
    assert "with their unit attached" in llm.calls[0][0]
    assert "no comparatives" in llm.calls[0][0].lower()
    assert out.attempts == 1
