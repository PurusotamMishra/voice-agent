from voice_agent.response.formatting import format_kg, format_km, format_price, group_indian


def test_group_indian() -> None:
    assert group_indian(950) == "950"
    assert group_indian(48_000) == "48,000"
    assert group_indian(125_000) == "1,25,000"


def test_format_price() -> None:
    assert format_price(500_000) == "₹5 lakh"
    assert format_price(485_000) == "₹4.85 lakh"
    assert format_price(85_000) == "₹85,000"
    assert format_price(3_895_000) == "₹38.95 lakh"


def test_units() -> None:
    assert format_km(48_000) == "48,000 km"
    assert format_kg(1_030) == "1,030 kg"
