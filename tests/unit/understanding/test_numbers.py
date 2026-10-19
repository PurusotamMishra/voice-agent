import pytest

from voice_agent.understanding.numbers import NumericSlots, parse_numeric


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("small truck under 5 lakh", NumericSlots(budget_max=500_000)),
        ("5 lakh ke andar chahiye", NumericSlots(budget_max=500_000)),
        ("budget 4.5L", NumericSlots(budget_max=450_000)),
        ("paanch lakh tak", NumericSlots(budget_max=500_000)),
        ("saadhe chaar lakh", NumericSlots(budget_max=450_000)),
        ("around 6 lakh", NumericSlots(budget_max=660_000, budget_target=600_000)),
        ("between 4 and 6 lakh", NumericSlots(budget_min=400_000, budget_max=600_000)),
        ("4 se 6 lakh", NumericSlots(budget_min=400_000, budget_max=600_000)),
        ("above 10 lakh", NumericSlots(budget_min=1_000_000)),
        ("rs 450000", NumericSlots(budget_max=450_000)),
        ("₹4,50,000 tak", NumericSlots(budget_max=450_000)),
        ("up to 5.2 lakh", NumericSlots(budget_max=520_000)),
        ("under 50,000 km", NumericSlots(max_km=50_000)),
        ("50 hazaar km chala ho", NumericSlots(max_km=50_000)),
        ("at least 1 ton payload", NumericSlots(min_payload_kg=1_000)),
        ("1.5 tonne", NumericSlots(min_payload_kg=1_500)),
        ("2018 ke baad ka", NumericSlots(min_year=2018)),
        ("2018 or newer", NumericSlots(min_year=2018)),
        ("not more than 5 lakh", NumericSlots(budget_max=500_000)),
        ("no more than 5 lakh", NumericSlots(budget_max=500_000)),
        ("9 lakh se zyada nahi", NumericSlots(budget_max=900_000)),
        ("2 lakh se jyada nahi", NumericSlots(budget_max=200_000)),
        ("5 lakh se upar nahi", NumericSlots(budget_max=500_000)),
        ("4 lakh 50 hazaar", NumericSlots(budget_max=450_000)),
        ("4 lakh 50 thousand", NumericSlots(budget_max=450_000)),
        ("under 5 lakh, above 3 lakh", NumericSlots(budget_min=300_000, budget_max=500_000)),
        ("do you have pickups", NumericSlots()),
        ("diesel pickup in Mumbai", NumericSlots()),
    ],
)
def test_parse_numeric(text: str, expected: NumericSlots) -> None:
    assert parse_numeric(text) == expected


def test_km_and_budget_in_one_sentence() -> None:
    r = parse_numeric("under 5 lakh with less than 50k km")
    assert (r.budget_max, r.max_km) == (500_000, 50_000)


def test_has_budget() -> None:
    assert parse_numeric("under 5 lakh").has_budget
    assert not parse_numeric("under 50000 km").has_budget
