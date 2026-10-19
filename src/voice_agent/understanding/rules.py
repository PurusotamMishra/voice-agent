"""Rules-only extractor: the LLM-outage fallback (D3, H5). Exact alias matching, no guessing."""

import re
from collections.abc import Mapping

from voice_agent.domain.enums import AliasKind, BodyType, Fuel, Intent
from voice_agent.understanding.schema import ExtractedSlots, TurnIntent

_YES = frozenset(
    {"haan", "han", "ha", "yes", "yeah", "ok", "okay", "theek hai", "kar do", "do that"}
)
_NO = frozenset({"nahi", "na", "no", "nope"})
_RESET = re.compile(r"\b(start over|reset|naya search|shuru se)\b")


def rules_extract(
    text: str,
    alias_map: Mapping[AliasKind, Mapping[str, str]],
    pending_question: str | None = None,
) -> TurnIntent:
    padded = " " + re.sub(r"[^\w\s]", " ", text.lower()) + " "
    padded = re.sub(r"\s+", " ", padded)
    if pending_question:
        answer = padded.strip()
        if answer in _YES:
            return TurnIntent(intent=Intent.RELAX, confirmation="yes")
        if answer in _NO:
            return TurnIntent(intent=Intent.SEARCH, confirmation="no")
    if _RESET.search(padded):
        return TurnIntent(intent=Intent.RESET)
    body = _hit(padded, alias_map.get(AliasKind.BODY_TYPE, {}))
    fuel = _hit(padded, alias_map.get(AliasKind.FUEL, {}))
    city = _hit(padded, alias_map.get(AliasKind.CITY, {}))
    make = _hit(padded, alias_map.get(AliasKind.MAKE, {}))
    model = _hit(padded, alias_map.get(AliasKind.MODEL, {}))
    slots = ExtractedSlots(
        body_type=BodyType(body[1]) if body else None,
        fuel=Fuel(fuel[1]) if fuel else None,
        city_mention=city[0] if city else None,
        make_mention=make[0] if make else None,
        model_mention=model[0] if model else None,
    )
    return TurnIntent(intent=Intent.SEARCH, slots=slots)


def _hit(padded: str, aliases: Mapping[str, str]) -> tuple[str, str] | None:
    for alias in sorted(aliases, key=len, reverse=True):
        if f" {alias} " in padded:
            return alias, aliases[alias]
    return None
