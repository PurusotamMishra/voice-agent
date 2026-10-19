"""Fact sheet: the only data the response LLM sees, with numbers pre-formatted in code (F1, F4)."""

import re
from collections.abc import Sequence

from pydantic import BaseModel

from voice_agent.domain.enums import BodyType, Language, Purpose, SellerType
from voice_agent.domain.models import Listing, ScoredListing
from voice_agent.response.formatting import format_kg, format_km, format_price

NUM_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?")
BODY_LABEL: dict[BodyType, str] = {
    BodyType.THREE_WHEELER: "three-wheeler",
    BodyType.MINI_TRUCK: "mini truck",
    BodyType.PICKUP: "pickup",
    BodyType.CARGO_VAN: "cargo van",
    BodyType.LCV: "light truck",
    BodyType.ICV: "medium truck",
    BodyType.TIPPER: "tipper",
}
SELLER_LABEL = {SellerType.DEALER: "a dealer", SellerType.INDIVIDUAL: "an individual seller"}
PURPOSE_REASON: dict[Purpose, str] = {
    Purpose.CITY_DELIVERY: "suits city delivery",
    Purpose.LONG_HAUL: "suits long-distance runs",
    Purpose.CONSTRUCTION: "built for construction work",
    Purpose.AGRICULTURE: "handy for farm use",
}


def numeric_tokens(text: str) -> set[str]:
    return {t.replace(",", "") for t in NUM_TOKEN.findall(text)}


_NUM_UNIT = re.compile(
    r"(?P<cur>₹\s*|\brs\.?\s*)?(?P<val>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*(?P<unit>lakhs?|lacs?|crores?|cr|l|kms?|kilomet(?:re|er)s?|kg|owners?)\b"
    r"(?:\s+(?P<unit2>kms?|kilomet(?:re|er)s?|kg|owners?)\b)?)?",
    re.IGNORECASE,
)
_UNIT_CANON = {
    "lakh": "lakh",
    "lac": "lakh",
    "l": "lakh",
    "crore": "crore",
    "cr": "crore",
    "km": "km",
    "kilometre": "km",
    "kilometer": "km",
    "kg": "kg",
    "owner": "owner",
}


def _canon_unit(raw: str) -> str:
    low = raw.lower()
    if low.endswith("s") and low not in _UNIT_CANON:
        low = low[:-1]
    return _UNIT_CANON.get(low, low)


def numbers_with_units(text: str) -> list[tuple[str, str]]:
    """(value, unit) for every number in text; commas stripped, unit bound to the adjacent word."""
    out: list[tuple[str, str]] = []
    for m in _NUM_UNIT.finditer(text):
        val = m.group("val").replace(",", "").rstrip(".")
        if m.group("unit"):
            unit = _canon_unit(m.group("unit"))
            if m.group("unit2"):  # e.g. "4.85 lakh km": a compound that matches no fact field
                unit += " " + _canon_unit(m.group("unit2"))
        else:
            unit = "rupee" if m.group("cur") else ""
        out.append((val, unit))
    return out


class FactItem(BaseModel):
    listing_id: str
    rank: int
    title: str
    make: str
    model: str
    city: str
    price: str
    km: str
    payload: str
    gvw: str
    year: str
    fuel: str
    body_type: str
    owners: str
    papers: str
    seller: str
    registration: str
    reasons: list[str]

    def allowed_numbers(self) -> set[tuple[str, str]]:
        fields = [self.title, self.price, self.km, self.payload, self.gvw, self.year, self.owners]
        return set(numbers_with_units(" ".join([*fields, *self.reasons])))


class FactSheet(BaseModel):
    language: Language
    items: list[FactItem]


def build_fact_item(
    listing: Listing, rank: int, reason_features: Sequence[str], purpose: Purpose | None
) -> FactItem:
    item = FactItem(
        listing_id=listing.listing_id,
        rank=rank,
        title=f"{listing.year} {listing.make} {listing.model} {listing.variant}",
        make=listing.make,
        model=listing.model,
        city=listing.city.value.title(),
        price=format_price(listing.price_inr),
        km=format_km(listing.km_driven),
        payload=format_kg(listing.payload_kg),
        gvw=format_kg(listing.gvw_kg),
        year=str(listing.year),
        fuel="CNG" if listing.fuel.value == "cng" else listing.fuel.value,
        body_type=BODY_LABEL[listing.body_type],
        owners=f"{listing.owners} owner" + ("" if listing.owners == 1 else "s"),
        papers="papers verified" if listing.papers_verified else "papers not verified",
        seller=SELLER_LABEL[listing.seller_type],
        registration=listing.registration_state,
        reasons=[],
    )
    reasons = [_reason(f, item, purpose) for f in reason_features]
    return item.model_copy(update={"reasons": [r for r in reasons if r]})


def build_fact_sheet(
    results: Sequence[ScoredListing], purpose: Purpose | None, language: Language
) -> FactSheet:
    return FactSheet(
        language=language,
        items=[build_fact_item(s.listing, s.rank, s.top_reasons(), purpose) for s in results],
    )


def _reason(feature: str, item: FactItem, purpose: Purpose | None) -> str:
    if feature == "price":
        return f"priced at {item.price}"
    if feature == "low_km":
        return f"only {item.km} driven"
    if feature == "newer_year":
        return f"a {item.year} model"
    if feature == "papers_verified":
        return "papers verified"
    if feature == "purpose_fit" and purpose is not None:
        return PURPOSE_REASON[purpose]
    return ""
