from tests.fakes import make_listing
from voice_agent.catalog.filters import build_count_sql, build_search_sql, constraint_violations
from voice_agent.domain.enums import BodyType, City, Fuel
from voice_agent.domain.models import Filters


def test_no_filters_means_no_where() -> None:
    sql, params = build_search_sql(Filters())
    assert "WHERE" not in sql and params == {"limit": 500}


def test_each_filter_is_one_parameterized_clause() -> None:
    f = Filters(budget_max=500_000, body_type=BodyType.PICKUP, fuel=Fuel.CNG, city=City.PUNE)
    sql, params = build_search_sql(f)
    assert sql.count(" AND ") == 3
    assert "price_inr <= %(budget_max)s" in sql
    assert params["budget_max"] == 500_000 and params["city"] == "pune"
    assert "500000" not in sql  # values never inlined


def test_model_filter_matches_family_prefix() -> None:
    sql, params = build_count_sql(Filters(model="Ace"))
    assert "model LIKE %(model_prefix)s" in sql and params["model_prefix"] == "Ace %"


def test_constraint_violations_catches_budget_slip() -> None:
    f = Filters(budget_max=500_000, city=City.PUNE)
    assert constraint_violations(make_listing(price_inr=600_000), f) == ["budget_max"]
    assert constraint_violations(make_listing(price_inr=500_000), f) == []


def test_constraint_violations_model_family() -> None:
    assert constraint_violations(make_listing(model="Ace Gold"), Filters(model="Ace")) == []
    assert constraint_violations(make_listing(model="Dost"), Filters(model="Ace")) == ["model"]
