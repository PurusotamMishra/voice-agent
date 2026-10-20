from tests.fakes import FakeLLM, FakeNormalizer
from voice_agent.domain.enums import AliasKind, BodyType, Intent, Language
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
        "budget_max": 500_000,
        "budget_target": None,
        "city": "pune",
    }
    assert "mini_truck" in llm.calls[0][0]  # enum values are in the system prompt


async def test_code_decides_reply_language_not_the_llm() -> None:
    llm = FakeLLM([TurnIntent(intent=Intent.SEARCH, language=Language.HINGLISH)])
    u = await understand(
        "Mini truck in Pune under 5 lakh", CTX, LLMSlotExtractor(llm, ALIASES), NORM, ALIASES
    )
    assert u.turn_intent.language == Language.EN


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


async def _updates(text: str, slots: ExtractedSlots | None = None) -> dict[str, object]:
    llm = FakeLLM([TurnIntent(intent=Intent.SEARCH, slots=slots or ExtractedSlots())])
    u = await understand(text, CTX, LLMSlotExtractor(llm, ALIASES), NORM, ALIASES)
    return u.updates


async def test_parser_finds_spelled_out_km_alongside_budget() -> None:
    updates = await _updates("pickup under 5 lakh with less than fifty thousand km")
    assert updates["budget_max"] == 500_000 and updates["max_km"] == 50_000


async def test_hinglish_tens_word_km_and_budget() -> None:
    updates = await _updates("5 lakh tak, pachaas hazaar km ke andar")
    assert updates["budget_max"] == 500_000 and updates["max_km"] == 50_000


async def test_llm_value_kept_for_a_field_the_parser_missed() -> None:
    # Parser finds the budget but not the km (no unit); the LLM's km survives (per-field override).
    updates = await _updates(
        "under 5 lakh, pachaas hazaar se kam chala ho",
        ExtractedSlots(budget_max=400_000, max_km=50_000),
    )
    assert updates == {"budget_max": 500_000, "budget_target": None, "max_km": 50_000}


async def test_llm_value_equal_to_a_parsed_number_is_rejected() -> None:
    updates = await _updates("under 5 lakh", ExtractedSlots(max_km=500_000))
    assert "max_km" not in updates


async def test_parser_wins_on_its_own_fields() -> None:
    updates = await _updates("under 5 lakh, 50k km", ExtractedSlots(max_km=60_000))
    assert updates["max_km"] == 50_000


async def test_llm_budget_ignored_when_parser_found_any_budget_bound() -> None:
    updates = await _updates("at least 3 lakh", ExtractedSlots(budget_max=900_000))
    assert updates == {"budget_min": 300_000}


async def test_budget_writes_only_found_bounds() -> None:
    assert await _updates("under 5 lakh") == {"budget_max": 500_000, "budget_target": None}
    assert await _updates("at least 3 lakh") == {"budget_min": 300_000}
    assert await _updates("4 se 6 lakh") == {
        "budget_min": 400_000,
        "budget_max": 600_000,
        "budget_target": None,
    }
    assert await _updates("around 6 lakh") == {
        "budget_min": None,
        "budget_max": 660_000,
        "budget_target": 600_000,
    }


async def test_llm_budget_writes_only_found_bounds() -> None:
    assert await _updates("minimum budget", ExtractedSlots(budget_min=300_000)) == {
        "budget_min": 300_000
    }


async def test_two_budget_turns_keep_both_walls_through_the_reducer() -> None:
    from voice_agent.state.models import Memory
    from voice_agent.state.reducer import apply_understanding

    mem = Memory()
    for text in ("under 5 lakh", "at least 3 lakh"):
        llm = FakeLLM([TurnIntent(intent=Intent.SEARCH)])
        u = await understand(text, CTX, LLMSlotExtractor(llm, ALIASES), NORM, ALIASES)
        mem, diff, _ = apply_understanding(mem, u)
    assert (mem.slots.budget_min, mem.slots.budget_max) == (300_000, 500_000)
    assert diff == {"budget_min": (None, 300_000)}


async def test_llm_cannot_refill_a_km_the_parser_dropped() -> None:
    # "over 2 lakh km" contradicts max_km; the parser drops it and the LLM's 200000 must not return.
    updates = await _updates("over 2 lakh km", ExtractedSlots(max_km=200_000))
    assert "max_km" not in updates


async def test_llm_cannot_refill_a_payload_the_parser_dropped() -> None:
    updates = await _updates("payload under 2 tons", ExtractedSlots(min_payload_kg=2_000))
    assert "min_payload_kg" not in updates


async def test_payload_after_a_km_limit_is_kept() -> None:
    updates = await _updates("under 50000 km and 1 ton payload")
    assert updates["max_km"] == 50_000 and updates["min_payload_kg"] == 1_000
