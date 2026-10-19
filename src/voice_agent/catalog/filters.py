"""Slots-derived Filters → parameterized SQL (D1, E1). The only place WHERE clauses are built."""

from typing import Any

from voice_agent.domain.models import Filters, Listing

LISTING_COLUMNS: tuple[str, ...] = (
    "listing_id",
    "model_id",
    "make",
    "model",
    "variant",
    "body_type",
    "fuel",
    "year",
    "price_inr",
    "km_driven",
    "payload_kg",
    "gvw_kg",
    "city",
    "registration_state",
    "owners",
    "seller_type",
    "papers_verified",
    "listing_date",
    "description",
)
_SELECT = "SELECT " + ", ".join(LISTING_COLUMNS) + " FROM listings"


def _where(f: Filters) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}

    def add(sql: str, **values: Any) -> None:
        clauses.append(sql)
        params.update(values)

    if f.budget_min is not None:
        add("price_inr >= %(budget_min)s", budget_min=f.budget_min)
    if f.budget_max is not None:
        add("price_inr <= %(budget_max)s", budget_max=f.budget_max)
    if f.body_type is not None:
        add("body_type = %(body_type)s", body_type=f.body_type.value)
    if f.fuel is not None:
        add("fuel = %(fuel)s", fuel=f.fuel.value)
    if f.city is not None:
        add("city = %(city)s", city=f.city.value)
    if f.make is not None:
        add("make = %(make)s", make=f.make)
    if f.model is not None:
        # A family alias like "Ace" covers "Ace Gold", "Ace Mega", ... (stated, not narrowed).
        add(
            "(model = %(model)s OR model LIKE %(model_prefix)s)",
            model=f.model,
            model_prefix=f"{f.model} %",
        )
    if f.min_payload_kg is not None:
        add("payload_kg >= %(min_payload_kg)s", min_payload_kg=f.min_payload_kg)
    if f.max_km is not None:
        add("km_driven <= %(max_km)s", max_km=f.max_km)
    if f.min_year is not None:
        add("year >= %(min_year)s", min_year=f.min_year)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def build_search_sql(f: Filters, limit: int = 500) -> tuple[str, dict[str, Any]]:
    where, params = _where(f)
    return f"{_SELECT}{where} ORDER BY listing_id LIMIT %(limit)s", {**params, "limit": limit}


def build_count_sql(f: Filters) -> tuple[str, dict[str, Any]]:
    where, params = _where(f)
    return f"SELECT count(*) FROM listings{where}", params


def constraint_violations(listing: Listing, f: Filters) -> list[str]:
    """F2.3: independent Python re-check of every hard filter (defense in depth vs SQL bugs)."""
    checks: list[tuple[str, bool]] = [
        ("budget_min", f.budget_min is not None and listing.price_inr < f.budget_min),
        ("budget_max", f.budget_max is not None and listing.price_inr > f.budget_max),
        ("body_type", f.body_type is not None and listing.body_type != f.body_type),
        ("fuel", f.fuel is not None and listing.fuel != f.fuel),
        ("city", f.city is not None and listing.city != f.city),
        ("make", f.make is not None and listing.make != f.make),
        (
            "model",
            f.model is not None
            and not (listing.model == f.model or listing.model.startswith(f"{f.model} ")),
        ),
        ("min_payload_kg", f.min_payload_kg is not None and listing.payload_kg < f.min_payload_kg),
        ("max_km", f.max_km is not None and listing.km_driven > f.max_km),
        ("min_year", f.min_year is not None and listing.year < f.min_year),
    ]
    return [name for name, violated in checks if violated]
