"""LLM slot extraction via one structured tool call (D1). Prompt vocab comes from the enums (D2)."""

import json
from collections.abc import Mapping

from voice_agent.domain.enums import AliasKind, BodyType, Fuel, Purpose
from voice_agent.domain.ports import LLM, LLMResult
from voice_agent.understanding.schema import ExtractionContext, TurnIntent

_SYSTEM = """You extract search intent for a used commercial-vehicle marketplace in India.
Fill the TurnIntent schema. Rules:
- intent: "search" (new or extra constraints), "correct" (user says a value they gave was wrong,
  e.g. "no, not diesel, CNG"), "follow_up" (question about a vehicle already shown),
  "relax" (user accepts the relaxation the assistant just offered), "reset" (start over),
  "out_of_domain" (anything unrelated to finding a vehicle).
- Only fill slots stated in THIS utterance. Never copy slots from the current state.
- body_type is one of: {body_types}. fuel is one of: {fuels}. purpose is one of: {purposes}.
{hints_line}- city_mention / make_mention / model_mention: copy the words exactly as the user said them.
  Do not correct spelling, translate or guess.
- Money is in rupees as integers (5 lakh = 500000). "under / ke andar / tak X" -> budget_max;
  "around X" -> budget_target only, never budget_max; "X to Y" -> budget_min and budget_max.
- clear_slots: slots the user explicitly drops ("any fuel is fine" -> ["fuel"]). A "correct" turn
  fills the new value and does not list the old slot in clear_slots.
- follow_up: set reference (ordinal 1-3, -1 for the last one; or make/model; or pronoun=true for
  it / uska / that one) and follow_up_field.
- confirmation: "yes" or "no", set only when Context.pending_question is non-null and answered.
- language: "hi-en" if the user speaks Hindi or Hinglish, otherwise "en"."""


def build_system_prompt(alias_map: Mapping[AliasKind, Mapping[str, str]]) -> str:
    def hints(kind: AliasKind) -> str:
        pairs = sorted(alias_map.get(kind, {}).items())
        return ", ".join(f"'{a}'={c}" for a, c in pairs if a != c)

    body_hints, fuel_hints = hints(AliasKind.BODY_TYPE), hints(AliasKind.FUEL)
    hints_line = ""
    if body_hints or fuel_hints:
        hints_line = (
            "- Phrase hints from our alias table: "
            + "; ".join(h for h in (body_hints, fuel_hints) if h)
            + ".\n"
        )
    return _SYSTEM.format(
        body_types=", ".join(b.value for b in BodyType),
        fuels=", ".join(f.value for f in Fuel),
        purposes=", ".join(p.value for p in Purpose),
        hints_line=hints_line,
    )


def build_user_prompt(text: str, ctx: ExtractionContext) -> str:
    context = {
        "current_slots": ctx.slots.filled(),
        "last_results": [
            {"rank": r.rank, "make": r.make, "model": r.model} for r in ctx.last_results
        ],
        "pending_question": ctx.pending_question,
    }
    return f"Context: {json.dumps(context, ensure_ascii=False)}\nUser said: {text}"


class LLMSlotExtractor:
    def __init__(self, llm: LLM, alias_map: Mapping[AliasKind, Mapping[str, str]]) -> None:
        self._llm = llm
        self._system = build_system_prompt(alias_map)

    @property
    def primary_provider(self) -> str:
        return self._llm.name

    async def extract(self, text: str, ctx: ExtractionContext) -> LLMResult[TurnIntent]:
        return await self._llm.structured(self._system, build_user_prompt(text, ctx), TurnIntent)
