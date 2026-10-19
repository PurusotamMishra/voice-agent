"""Hand-written fakes and factories for unit tests (no network, no DB)."""

from datetime import date
from typing import Any

from voice_agent.domain.enums import BodyType, City, Fuel, SellerType
from voice_agent.domain.models import Listing

_DEFAULTS: dict[str, Any] = {
    "listing_id": "VH-0001",
    "model_id": "tata_ace_gold_diesel",
    "make": "Tata",
    "model": "Ace Gold",
    "variant": "Diesel",
    "body_type": BodyType.MINI_TRUCK,
    "fuel": Fuel.DIESEL,
    "year": 2020,
    "price_inr": 400_000,
    "km_driven": 50_000,
    "payload_kg": 750,
    "gvw_kg": 1_750,
    "city": City.PUNE,
    "registration_state": "MH",
    "owners": 1,
    "seller_type": SellerType.DEALER,
    "papers_verified": True,
    "listing_date": date(2026, 9, 1),
    "description": "test listing",
}


def make_listing(**overrides: Any) -> Listing:
    return Listing(**{**_DEFAULTS, **overrides})
