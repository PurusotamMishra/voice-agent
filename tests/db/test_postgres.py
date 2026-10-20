import os

import pytest
from psycopg_pool import AsyncConnectionPool

from voice_agent.catalog.filters import constraint_violations
from voice_agent.config import get_settings
from voice_agent.db.seed import seed
from voice_agent.domain.enums import AliasKind, BodyType, City, Fuel
from voice_agent.domain.models import Filters
from voice_agent.providers.postgres import PgCatalog, PgNormalizer, load_neighbors, load_vocab

pytestmark = pytest.mark.db


@pytest.fixture
async def pool():  # type: ignore[no-untyped-def]
    url = os.environ.get("DATABASE_URL", get_settings().database_url)
    async with AsyncConnectionPool(url, open=False, kwargs={"autocommit": True}) as p:
        await seed(p, get_settings().data_dir)
        yield p


async def test_search_honours_every_filter(pool) -> None:  # type: ignore[no-untyped-def]
    f = Filters(budget_max=500_000, body_type=BodyType.MINI_TRUCK, city=City.PUNE)
    result = await PgCatalog(pool).search(f)
    assert result.rows and all(not constraint_violations(r, f) for r in result.rows)
    assert any(r.price_inr == 500_000 for r in result.rows)  # planted boundary listing


async def test_planted_zero_result(pool) -> None:  # type: ignore[no-untyped-def]
    assert await PgCatalog(pool).count(Filters(fuel=Fuel.CNG, city=City.KOLKATA)) == 0


async def test_model_family_filter(pool) -> None:  # type: ignore[no-untyped-def]
    rows = (await PgCatalog(pool).search(Filters(model="Ace", city=City.PUNE))).rows
    assert len({r.model for r in rows}) >= 2


async def test_normalizer_exact_trigram_none(pool) -> None:  # type: ignore[no-untyped-def]
    n = PgNormalizer(pool)
    assert (await n.normalize(AliasKind.CITY, "Bombay")).canonical == "mumbai"
    fuzzy = await n.normalize(AliasKind.MODEL, "aace")
    assert fuzzy.canonical == "Ace" and 0.3 <= fuzzy.score < 0.6
    assert (await n.normalize(AliasKind.CITY, "Nagpur")).score < 0.3


async def test_neighbors(pool) -> None:  # type: ignore[no-untyped-def]
    assert City.LUCKNOW in (await load_neighbors(pool))[City.KOLKATA]


async def test_vocab_aliases_only_make_and_model(pool) -> None:  # type: ignore[no-untyped-def]
    vocab = await load_vocab(pool)
    assert vocab.aliases["ace"] == ("model", "Ace")
    assert "pickup" not in vocab.aliases
    assert all(kind in ("make", "model") for kind, _ in vocab.aliases.values())


async def test_seed_reloads_aliases_on_every_boot(pool, tmp_path) -> None:  # type: ignore[no-untyped-def]
    data = get_settings().data_dir
    for name in ("listings.csv", "aliases.csv", "city_neighbors.csv"):
        (tmp_path / name).write_bytes((data / name).read_bytes())
    with (tmp_path / "aliases.csv").open("a", encoding="utf-8") as fh:
        fh.write("gaadiwala,Tata,make\n")
    try:
        await seed(pool, tmp_path)
        m = await PgNormalizer(pool).normalize(AliasKind.MAKE, "gaadiwala")
        assert m.canonical == "Tata" and m.method == "exact"
    finally:
        await seed(pool, data)  # put the real aliases back
