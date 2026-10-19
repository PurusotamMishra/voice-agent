"""understand(): LLM intent + deterministic number override + alias normalisation (D2, D3, D6)."""

import logging
from collections.abc import Mapping
from typing import Any

from voice_agent.domain.enums import AliasKind
from voice_agent.domain.models import LowConfidence, Unsupported
from voice_agent.domain.ports import Normalizer, ProviderError, Usage
from voice_agent.state.reducer import sanitize_updates
from voice_agent.understanding.extractor import LLMSlotExtractor
from voice_agent.understanding.numbers import NumericSlots, parse_numeric
from voice_agent.understanding.rules import rules_extract
from voice_agent.understanding.schema import ExtractionContext, TurnIntent, Understanding

TRGM_ACCEPT = 0.6  # D6: at or above -> accept silently
TRGM_CONFIRM = 0.3  # D6: between CONFIRM and ACCEPT -> ask "did you mean ...?"
_BUDGET = ("budget_min", "budget_max", "budget_target")
log = logging.getLogger(__name__)


async def understand(
    text: str,
    ctx: ExtractionContext,
    extractor: LLMSlotExtractor,
    normalizer: Normalizer,
    alias_map: Mapping[AliasKind, Mapping[str, str]],
) -> Understanding:
    usage: list[Usage] = []
    fallbacks: list[str] = []
    try:
        result = await extractor.extract(text, ctx)
        ti = result.value
        usage.append(result.usage)
        if result.usage.provider != extractor.primary_provider:
            fallbacks.append("llm_failover")
    except ProviderError as exc:
        log.warning("extractor failed, using rules: %s", exc)
        ti = rules_extract(text, alias_map, ctx.pending_question)
        fallbacks.append("rules_extractor")

    updates = _slot_updates(ti, parse_numeric(text))
    low: list[LowConfidence] = []
    unsupported: list[Unsupported] = []
    mentions = (
        (AliasKind.CITY, "city", ti.slots.city_mention),
        (AliasKind.MAKE, "make", ti.slots.make_mention),
        (AliasKind.MODEL, "model", ti.slots.model_mention),
    )
    for kind, slot, mention in mentions:
        if not mention:
            continue
        m = await normalizer.normalize(kind, mention)
        if m.canonical and m.score >= TRGM_ACCEPT:
            updates[slot] = m.canonical
        elif m.canonical and m.score >= TRGM_CONFIRM:
            low.append(LowConfidence(slot=slot, raw=mention, candidate=m.canonical, score=m.score))
        else:
            unsupported.append(Unsupported(kind=kind, raw=mention))

    valid, dropped = sanitize_updates(updates)
    if dropped:
        log.warning("dropped invalid slot values: %s", dropped)
    return Understanding(
        turn_intent=ti,
        updates=valid,
        low_confidence=low,
        unsupported=unsupported,
        usage=usage,
        fallbacks=fallbacks,
    )


def _slot_updates(ti: TurnIntent, numeric: NumericSlots) -> dict[str, Any]:
    s = ti.slots
    updates: dict[str, Any] = {}
    for name in ("body_type", "fuel", "purpose"):
        value = getattr(s, name)
        if value is not None:
            updates[name] = value
    parser_found = numeric.has_budget or any(
        getattr(numeric, n) is not None for n in ("max_km", "min_payload_kg", "min_year")
    )
    if numeric.has_budget:  # D3: the parser wins on numbers
        updates.update(
            budget_min=numeric.budget_min,
            budget_max=numeric.budget_max,
            budget_target=numeric.budget_target,
        )
    elif not parser_found and any(getattr(s, b) is not None for b in _BUDGET):
        cap = round(s.budget_target * 1.1) if s.budget_target else s.budget_max
        updates.update(budget_min=s.budget_min, budget_max=cap, budget_target=s.budget_target)
    for name in ("max_km", "min_payload_kg", "min_year"):
        value = getattr(numeric, name)
        if value is None and not parser_found:
            value = getattr(s, name)
        if value is not None:
            updates[name] = value
    for name in ti.clear_slots:
        if name == "budget":
            updates.update(dict.fromkeys(_BUDGET))
        else:
            updates[name] = None
    return updates
