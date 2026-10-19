from tests.fakes import make_listing
from voice_agent.domain.enums import Language, Purpose
from voice_agent.domain.models import ScoredListing
from voice_agent.response.factsheet import build_fact_sheet, numeric_tokens


def test_numeric_tokens_strip_commas() -> None:
    assert numeric_tokens("₹4.85 lakh, 48,000 km, 2019.") == {"4.85", "48000", "2019"}


def test_fact_sheet_preformats_and_explains() -> None:
    s = ScoredListing(
        listing=make_listing(price_inr=485_000, km_driven=48_000, year=2019),
        rank=1,
        score=0.5,
        features={},
        contributions={"low_km": 0.2, "papers_verified": 0.15, "price": 0.1},
    )
    item = build_fact_sheet([s], Purpose.CITY_DELIVERY, Language.EN).items[0]
    assert (item.price, item.km, item.year) == ("₹4.85 lakh", "48,000 km", "2019")
    assert item.reasons == ["only 48,000 km driven", "papers verified"]
    assert {
        ("4.85", "lakh"),
        ("48000", "km"),
        ("2019", ""),
        ("750", "kg"),
        ("1", "owner"),
    } <= item.allowed_numbers()
