"""Compose the spoken top-k answer: LLM phrasing from the fact sheet, validated in code (F1)."""

import json
import logging

from pydantic import BaseModel, Field

from voice_agent.domain.enums import Language
from voice_agent.domain.ports import LLM, ProviderError, Usage
from voice_agent.response import templates
from voice_agent.response.factsheet import FactSheet
from voice_agent.response.schema import ComposedResponse, Verdict, Violation
from voice_agent.response.validator import EntityVocab, validate

MAX_ATTEMPTS = 2
log = logging.getLogger(__name__)

_SYSTEM = """You write short spoken answers for a used commercial-vehicle voice assistant.
You get a FACT SHEET of vehicles in rank order. Rules:
1. Exactly one item per vehicle, in the given order.
   Put the listing_id only in the item's listing_id field.
   Never write a listing id (such as VH-0077) in intro, item text or closing.
2. Numbers appear only exactly as written in the fact sheet, with their unit attached
   ("₹4.85 lakh", "48,000 km", "750 kg", "1 owner"). Never compute, round or convert numbers,
   never write numbers as words, never add a bare number, an age ("5 years old") or an owner
   count that is not the exact fact string.
3. Copy the vehicle's reasons as written; do not paraphrase them with new numbers.
   Mention only this vehicle's own make, model, city and fuel. No other cities, fuels or
   vehicles, and no comparatives such as "cheapest" or "best in Pune".
4. intro and closing: no numbers and no vehicle names. closing invites a follow-up question.
5. Each item under 30 words; sound natural when spoken.
Language: {language}."""
_LANG = {Language.EN: "English", Language.HINGLISH: "Hinglish in Roman script"}


class ComposeOutcome(BaseModel):
    response: ComposedResponse
    verdict: Verdict
    usage: list[Usage] = Field(default_factory=list)
    fallbacks: list[str] = Field(default_factory=list)
    attempts: int = 0


async def compose_results(facts: FactSheet, llm: LLM, vocab: EntityVocab) -> ComposeOutcome:
    system = _SYSTEM.format(language=_LANG[facts.language])
    usage: list[Usage] = []
    violations: list[Violation] = []
    attempts = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempts = attempt
        try:
            result = await llm.structured(system, _user_prompt(facts, violations), ComposedResponse)
        except ProviderError as exc:
            log.warning("composer LLM failed: %s", exc)
            break
        usage.append(result.usage)
        verdict = validate(result.value, facts, vocab)
        if verdict.ok:
            fallbacks = ["regenerated"] if attempt > 1 else []
            return ComposeOutcome(
                response=result.value,
                verdict=verdict,
                usage=usage,
                fallbacks=fallbacks,
                attempts=attempt,
            )
        violations = verdict.violations
        log.warning("validator rejected attempt %d: %s", attempt, violations)
    return ComposeOutcome(
        response=templates.results(facts),
        verdict=Verdict(ok=True, violations=violations, source="template"),
        usage=usage,
        fallbacks=["template"],
        attempts=attempts,
    )


def _user_prompt(facts: FactSheet, violations: list[Violation]) -> str:
    prompt = "FACT SHEET:\n" + json.dumps(
        facts.model_dump(mode="json")["items"], ensure_ascii=False
    )
    if violations:
        problems = "; ".join(f"{v.where}: {v.kind} {v.detail}" for v in violations)
        prompt += f"\nYour previous answer was rejected for: {problems}. Fix these."
    return prompt
