from tests.fakes import FakeLLM, FakeNormalizer
from voice_agent.domain.enums import AliasKind, BodyType, Intent
from voice_agent.domain.models import Slots
from voice_agent.domain.ports import ProviderError
from voice_agent.understanding.extractor import LLMSlotExtractor
from voice_agent.understanding.pipeline import understand
from voice_agent.understanding.schema import ExtractedSlots, ExtractionContext, TurnIntent

ALIASES = {k: {} for k in AliasKind} | {AliasKind.BODY_TYPE: {"mini truck": "mini_truck"}}
NORM = FakeNormalizer(
    {
        (AliasKind.CITY, "pune"): ("pune", 1.0),
        (AliasKind.MODEL, "aace"): ("Ace", 0.5),
    }
)
CTX = ExtractionContext(slots=Slots())


async def test_parser_overrides_llm_budget_and_city_is_normalised() -> None:
    llm = FakeLLM(
        [
            TurnIntent(
                intent=Intent.SEARCH,
                slots=ExtractedSlots(
                    budget_max=50_000, body_type=BodyType.MINI_TRUCK, city_mention="Pune"
                ),
            )
        ]
    )
    u = await understand(
        "mini truck under 5 lakh in Pune", CTX, LLMSlotExtractor(llm, ALIASES), NORM, ALIASES
    )
    assert u.updates == {
        "body_type": BodyType.MINI_TRUCK,
        "budget_min": None,
        "budget_max": 500_000,
        "budget_target": None,
        "city": "pune",
    }
    assert "mini_truck" in llm.calls[0][0]  # enum values are in the system prompt


async def test_low_confidence_and_unsupported() -> None:
    llm = FakeLLM(
        [
            TurnIntent(
                intent=Intent.SEARCH,
                slots=ExtractedSlots(model_mention="Aace", city_mention="Nagpur"),
            )
        ]
    )
    u = await understand("Aace in Nagpur", CTX, LLMSlotExtractor(llm, ALIASES), NORM, ALIASES)
    assert [(x.slot, x.candidate) for x in u.low_confidence] == [("model", "Ace")]
    assert [(x.kind, x.raw) for x in u.unsupported] == [(AliasKind.CITY, "Nagpur")]


async def test_llm_outage_falls_back_to_rules() -> None:
    llm = FakeLLM([ProviderError("groq", "down")])
    u = await understand(
        "mini truck under 5 lakh", CTX, LLMSlotExtractor(llm, ALIASES), NORM, ALIASES
    )
    assert u.fallbacks == ["rules_extractor"]
    assert u.updates["body_type"] == "mini_truck" and u.updates["budget_max"] == 500_000


async def test_clear_slots() -> None:
    llm = FakeLLM([TurnIntent(intent=Intent.SEARCH, clear_slots=["fuel", "budget"])])
    u = await understand("any fuel, any budget", CTX, LLMSlotExtractor(llm, ALIASES), NORM, ALIASES)
    assert u.updates == {
        "fuel": None,
        "budget_min": None,
        "budget_max": None,
        "budget_target": None,
    }


async def test_llm_budget_ignored_when_parser_found_other_number() -> None:
    llm = FakeLLM(
        [TurnIntent(intent=Intent.SEARCH, slots=ExtractedSlots(budget_max=80_000, max_km=80_000))]
    )
    u = await understand("80000 km chahiye", CTX, LLMSlotExtractor(llm, ALIASES), NORM, ALIASES)
    assert u.updates == {"max_km": 80_000}


async def test_fallback_passes_pending_question_to_rules() -> None:
    llm = FakeLLM([ProviderError("groq", "down")])
    ctx = ExtractionContext(slots=Slots(), pending_question="Relax the budget?")
    u = await understand("haan", ctx, LLMSlotExtractor(llm, ALIASES), NORM, ALIASES)
    assert u.turn_intent.intent is Intent.RELAX and u.turn_intent.confirmation == "yes"


def test_prompt_omits_empty_hints_line() -> None:
    from voice_agent.understanding.extractor import build_system_prompt

    empty = build_system_prompt({k: {} for k in AliasKind})
    assert "Phrase hints" not in empty
    assert "Phrase hints" in build_system_prompt(ALIASES)
    assert "never budget_max" in empty and "pending_question" in empty


def test_prompt_maps_vehicle_class_names_to_body_type() -> None:
    from voice_agent.understanding.extractor import build_system_prompt

    prompt = build_system_prompt({k: {} for k in AliasKind})
    assert '"light commercial vehicle" -> lcv' in prompt
    assert '"intermediate commercial vehicle" -> icv' in prompt
