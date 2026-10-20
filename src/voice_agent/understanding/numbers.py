"""Deterministic parser for money, km, payload and year mentions (D3: overrides the LLM on numbers)."""

import re
from dataclasses import dataclass

_WORD_NUM: dict[str, float] = {
    "ek": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "chaar": 4,
    "four": 4, "paanch": 5, "panch": 5, "five": 5, "chhe": 6, "cheh": 6, "six": 6,
    "saat": 7, "seven": 7, "aath": 8, "eight": 8, "nau": 9, "nine": 9, "das": 10, "ten": 10,
    "dedh": 1.5, "dhai": 2.5, "dhaai": 2.5, "adhai": 2.5,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}  # fmt: skip
_TENS: dict[str, int] = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "bees": 20, "tees": 30, "chalees": 40, "chaalis": 40,
    "pachaas": 50, "pachas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90,
}  # fmt: skip
_WORD_NUM.update(_TENS)
_ONES_EN = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_MULT: dict[str, int] = {
    "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000, "l": 100_000,
    "k": 1_000, "hazaar": 1_000, "hazar": 1_000, "thousand": 1_000,
    "crore": 10_000_000, "crores": 10_000_000, "cr": 10_000_000,
}  # fmt: skip
_NUM = r"\d+(?:\.\d+)?"
_MONEY_UNIT = r"(?:lakhs?|lacs?|l|k|hazaar|hazar|thousand|crores?|cr)"

# Number words become digits only when a unit follows ("do lakh" yes, "do you" no).
_UNIT_AHEAD = r"(?=\s*(?:lakhs?|lacs?|hazaar|hazar|thousand|crores?|tons?|tonnes?|km))"
_NUM_WORD_RE = re.compile(
    r"\b(" + "|".join(sorted(_WORD_NUM, key=len, reverse=True)) + r")\b" + _UNIT_AHEAD
)
# "twenty five thousand" -> "25 thousand" (English tens + ones; a unit is still required).
_TENS_ONES_RE = re.compile(
    r"\b(" + "|".join(_TENS) + r")[\s-]+(" + "|".join(_ONES_EN) + r")\b" + _UNIT_AHEAD
)
_COMPOUND_RE = re.compile(
    rf"({_NUM})\s*(?:lakhs?|lacs?)\s+({_NUM})\s*(?:hazaar|hazar|thousand|k)\b"
)
_SAADHE_RE = re.compile(r"\bsa+dhe\s+(\d+(?:\.\d+)?)")
_YEAR_RE = re.compile(
    r"(?:after|since|from|newer than)\s+(20\d\d)\b"
    r"|\b(20\d\d)\s*(?:ke baad|ke bad|se naya|se nayi|or newer|or later|onwards|\+)"
)
_KM_RE = re.compile(
    rf"({_NUM})\s*(k|hazaar|hazar|thousand|lakhs?|lacs?|l)?\s*(?:kms?|kilomet\w*)\b"
)
_PAYLOAD_RE = re.compile(rf"({_NUM})\s*(tons?|tonnes?|kgs?)\b")
_RANGE_RE = re.compile(
    rf"(?:rs\.?\s*)?({_NUM})\s*({_MONEY_UNIT})?\s*(?:-|to|se|and)\s*"
    rf"(?:rs\.?\s*)?({_NUM})\s*({_MONEY_UNIT})\b"
)
_BLANK = "\x00"  # fills consumed year/km/payload spans; never in user text (_prepare strips it)
_AMOUNT_RE = re.compile(rf"(?:rs\.?\s*)?({_NUM})\s*({_MONEY_UNIT})\b|rs\.?\s*(\d{{4,}})\b")

_MAX_BEFORE = re.compile(
    r"\b(under|below|within|upto|up to|max|maximum|less than|not more than|no more than|at most"
    r"|not above|not over)\b\D*$"
)
_MAX_AFTER = re.compile(
    r"^\s*(ke andar|ke under|andar|tak|se kam|or less|max|ke neeche"
    r"|se zyada nahi|se jyada nahi|se upar nahi)\b"
)
_MIN_BEFORE = re.compile(r"\b(above|over|more than|at least|minimum|min)\b\D*$")
_MIN_AFTER = re.compile(r"^\s*(se zyada|se jyada|se upar|or more|plus)\b")
_AROUND_BEFORE = re.compile(r"\b(around|about|approx|approximately|roughly|lagbhag|kareeb)\b\D*$")
_AROUND_AFTER = re.compile(r"^\s*(ke aas ?paas|ke around|ke kareeb)\b")


@dataclass(frozen=True)
class NumericSlots:
    budget_min: int | None = None
    budget_max: int | None = None
    budget_target: int | None = None
    max_km: int | None = None
    min_payload_kg: int | None = None
    min_year: int | None = None
    # Fields whose phrase was found but dropped for a contradicting direction ("over 2 lakh km").
    # The pipeline must not re-fill them from the LLM.
    dropped: frozenset[str] = frozenset()

    @property
    def has_budget(self) -> bool:
        return any(v is not None for v in (self.budget_min, self.budget_max, self.budget_target))


def parse_numeric(text: str) -> NumericSlots:
    t = _prepare(text)
    # Order matters: remove year/km/payload spans so they are not read as money.
    min_year, t = _take_year(t)
    max_km, t, km_dropped = _take_km(t)
    min_payload_kg, t, payload_dropped = _take_payload(t)
    budget_min, budget_max, budget_target = _take_budget(t)
    dropped = {"max_km"} if km_dropped else set()
    if payload_dropped:
        dropped.add("min_payload_kg")
    return NumericSlots(
        budget_min, budget_max, budget_target, max_km, min_payload_kg, min_year, frozenset(dropped)
    )


def _prepare(text: str) -> str:
    t = text.lower().replace("₹", " rs ").replace(_BLANK, " ")
    t = re.sub(r"(?<=\d),(?=\d)", "", t)
    t = _TENS_ONES_RE.sub(lambda m: _fmt(_WORD_NUM[m.group(1)] + _WORD_NUM[m.group(2)]), t)
    t = _NUM_WORD_RE.sub(lambda m: _fmt(_WORD_NUM[m.group(1)]), t)
    t = _SAADHE_RE.sub(lambda m: _fmt(float(m.group(1)) + 0.5), t)
    # "4 lakh 50 hazaar" -> "4.5 lakh"
    return _COMPOUND_RE.sub(
        lambda m: (
            _fmt((float(m.group(1)) * 100_000 + float(m.group(2)) * 1_000) / 100_000) + " lakh"
        ),
        t,
    )


def _fmt(x: float) -> str:
    return str(int(x)) if x == int(x) else str(x)


def _blank(t: str, m: re.Match[str]) -> str:
    """Replace a consumed span with _BLANK so later contexts stop at it: in "under 50000 km
    and 1 ton", "under" belongs to the km and must not reach the payload."""
    return t[: m.start()] + _BLANK * (m.end() - m.start()) + t[m.end() :]


def _clip(before: str, after: str) -> tuple[str, str]:
    return before.rsplit(_BLANK, 1)[-1], after.split(_BLANK, 1)[0]


def _take_year(t: str) -> tuple[int | None, str]:
    m = _YEAR_RE.search(t)
    if m is None:
        return None, t
    return int(m.group(1) or m.group(2)), _blank(t, m)


def _direction(before: str, after: str) -> str | None:
    """'max', 'min' or None for the words around a number. Max is checked first so that
    negated forms ("not more than", "se zyada nahi") are not read as a minimum."""
    if _MAX_BEFORE.search(before) or _MAX_AFTER.search(after):
        return "max"
    if _MIN_BEFORE.search(before) or _MIN_AFTER.search(after):
        return "min"
    return None


def _context(t: str, m: re.Match[str]) -> tuple[str, str]:
    return _clip(t[: m.start()][-40:], t[m.end() : m.end() + 25])


def _take_km(t: str) -> tuple[int | None, str, bool]:
    """(max_km, text with the span blanked, dropped-for-contradiction)."""
    m = _KM_RE.search(t)
    if m is None:
        return None, t, False
    if _direction(*_context(t, m)) == "min":
        return None, _blank(t, m), True  # "over 2 lakh km" contradicts max_km: drop, never invert
    return round(float(m.group(1)) * _MULT.get(m.group(2) or "", 1)), _blank(t, m), False


def _take_payload(t: str) -> tuple[int | None, str, bool]:
    """(min_payload_kg, text with the span blanked, dropped-for-contradiction)."""
    m = _PAYLOAD_RE.search(t)
    if m is None:
        return None, t, False
    if _direction(*_context(t, m)) == "max":
        return None, _blank(t, m), True  # "payload under 2 tons" contradicts min_payload: drop
    per_unit = 1 if m.group(2).startswith("kg") else 1_000
    return round(float(m.group(1)) * per_unit), _blank(t, m), False


def _amount(num: str, unit: str) -> int:
    return round(float(num) * _MULT[unit])


def _take_budget(t: str) -> tuple[int | None, int | None, int | None]:
    m = _RANGE_RE.search(t)
    if m is not None:
        unit_b = m.group(4)
        low, high = _amount(m.group(1), m.group(2) or unit_b), _amount(m.group(3), unit_b)
        return min(low, high), max(low, high), None
    lo: int | None = None
    hi: int | None = None
    target: int | None = None
    prev_end = 0
    for m in _AMOUNT_RE.finditer(t):
        value = _amount(m.group(1), m.group(2)) if m.group(1) else int(m.group(3))
        before, after = _clip(t[prev_end : m.start()][-40:], t[m.end() : m.end() + 25])
        prev_end = m.end()
        if _AROUND_BEFORE.search(before) or _AROUND_AFTER.search(after):
            if hi is None:
                hi, target = round(value * 1.1), value  # D5: "around X" caps at 1.1*X
        elif _direction(before, after) == "max":
            hi = value if hi is None else hi
        elif _direction(before, after) == "min":
            lo = value if lo is None else lo
        elif hi is None:
            hi = value  # bare amount -> max (Assumption)
    return lo, hi, target
