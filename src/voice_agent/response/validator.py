"""Code-level anti-hallucination check (F2) for LLM-composed responses. Pure, no I/O.

Known limits (F3): subjective claims without numbers or entities, unsupported comparatives
("cheapest in Pune"), and "one"/"do" are not treated as number words. Numbers are bound to units,
but small values stay valid when they carry their own unit (owners "1" only as "1 owner"); numbers
inside the title (model numbers, year) license those bare numbers only (never with a unit), and
the exact model/variant name is skipped by the number check; papers, seller and
registration claims are unchecked; magnitude rewordings without digits ("about half") are not
caught. City and fuel are checked in item sentences only.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from voice_agent.domain.enums import City
from voice_agent.response.factsheet import FactSheet, numbers_with_units
from voice_agent.response.schema import ComposedResponse, Verdict, Violation

_NUMBER_WORDS = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
    r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"hundred|dozen|half|couple|ek|chaar|paanch|chhe|saat|aath|nau|das|bees|pachaas|dedh|dhai|"
    r"sau)\b"
)
# Scale words are fine only directly after a digit ("4.85 lakh").
_SCALE_WORDS = re.compile(r"(?<!\d)(?<!\d )\b(lakhs?|lacs?|crores?|million|thousand|hazaar)\b")
# Body-type words ("three-wheeler") are honest descriptions, not numeric claims.
_BODY_TYPE_WORDS = re.compile(r"\b(three|four)[-\s]+wheelers?\b")
# Listing ids are internal keys, never spoken; stripped before the number check so the
# digits are not reported twice.
_LISTING_ID = re.compile(r"\bVH-\d+\b", re.IGNORECASE)
_FUEL_WORD = re.compile(r"\b(diesel|petrol|cng|electric)\b", re.IGNORECASE)
_CITY_WORD = re.compile(r"\b(" + "|".join(c.value for c in City) + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class EntityVocab:
    makes: frozenset[str]
    models: frozenset[str]
    aliases: Mapping[str, tuple[str, str]] = field(default_factory=dict)

    def find(self, text: str) -> list[tuple[str, str]]:
        """(kind, canonical) for every make/model/alias named in text; longest names first."""
        found: list[tuple[str, str]] = []
        lowered = text.lower()
        canon = [
            (k, n, n) for k, names in (("model", self.models), ("make", self.makes)) for n in names
        ]
        alias = [(k, a, c) for a, (k, c) in self.aliases.items()]
        for group in (canon, alias):
            for kind, surface, canonical in sorted(group, key=lambda t: len(t[1]), reverse=True):
                pattern = r"(?<![\w])" + re.escape(surface.lower()) + r"(?![\w])"
                if re.search(pattern, lowered):
                    found.append((kind, canonical))
                    lowered = re.sub(pattern, " ", lowered)
        return found


def validate(resp: ComposedResponse, facts: FactSheet, vocab: EntityVocab) -> Verdict:
    violations: list[Violation] = []
    expected = [i.listing_id for i in facts.items]
    got = [i.listing_id for i in resp.items]
    if got != expected:
        violations.append(
            Violation(where="items", kind="order", detail=f"expected {expected}, got {got}")
        )

    by_id = {i.listing_id: i for i in facts.items}
    for sentence in resp.items:
        fact = by_id.get(sentence.listing_id)
        if fact is None:
            continue
        text = _blank_phrases(sentence.text, fact.name_phrases())
        violations += _numbers(text, fact.allowed_numbers(), sentence.listing_id)
        for kind, name in vocab.find(sentence.text):
            if kind == "make":
                matches = name == fact.make
            else:
                matches = fact.model == name or fact.model.startswith(name + " ")
            if not matches:
                violations.append(
                    Violation(
                        where=sentence.listing_id,
                        kind="entity",
                        detail=f"{kind} '{name}' is not this listing's",
                    )
                )
        violations += _city_fuel(sentence.text, fact.city, fact.fuel, sentence.listing_id)

    for where, text in (("intro", resp.intro), ("closing", resp.closing)):
        violations += _numbers(text, set(), where)
        violations += [
            Violation(where=where, kind="extra_vehicle", detail=name)
            for _, name in vocab.find(text)
        ]
    return Verdict(ok=not violations, violations=violations, source="llm")


def _blank_phrases(text: str, phrases: list[str]) -> str:
    for phrase in phrases:
        text = re.sub(re.escape(phrase), " ", text, flags=re.IGNORECASE)
    return text


def _city_fuel(text: str, city: str, fuel: str, where: str) -> list[Violation]:
    out = [
        Violation(where=where, kind="entity", detail=f"city '{m.group(0)}' is not this listing's")
        for m in _CITY_WORD.finditer(text)
        if m.group(0).lower() != city.lower()
    ]
    out += [
        Violation(where=where, kind="entity", detail=f"fuel '{m.group(0)}' is not this listing's")
        for m in _FUEL_WORD.finditer(text)
        if m.group(0).lower() != fuel.lower()
    ]
    return out


def _numbers(text: str, allowed: set[tuple[str, str]], where: str) -> list[Violation]:
    out = [
        Violation(where=where, kind="number", detail=f"listing id {m.group(0)} in spoken text")
        for m in _LISTING_ID.finditer(text)
    ]
    text = _LISTING_ID.sub(" ", text)
    allowed_values = {v for v, _ in allowed}
    for value, unit in sorted(set(numbers_with_units(text))):
        if (value, unit) in allowed:
            continue
        detail = value if value not in allowed_values else f"{value} {unit or '(no unit)'}"
        out.append(Violation(where=where, kind="number", detail=detail))
    lowered = _BODY_TYPE_WORDS.sub(" ", text.lower())
    out += [
        Violation(where=where, kind="number_word", detail=m.group(0))
        for rx in (_NUMBER_WORDS, _SCALE_WORDS)
        for m in rx.finditer(lowered)
    ]
    return out
