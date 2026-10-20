"""Create tables, load listings on first boot, and reload the lookup tables on every boot."""

import csv
from pathlib import Path

from voice_agent.aio import run
from voice_agent.catalog.filters import LISTING_COLUMNS
from voice_agent.config import get_settings
from voice_agent.domain.enums import BodyType, City, Fuel
from voice_agent.domain.models import Listing
from voice_agent.providers.postgres import PgPool, open_pool

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_INSERT_LISTING = (
    f"INSERT INTO listings ({', '.join(LISTING_COLUMNS)}) VALUES "
    f"({', '.join(f'%({c})s' for c in LISTING_COLUMNS)})"
)
_INSERT_ALIAS = (
    "INSERT INTO aliases (alias, canonical, kind) VALUES (%(alias)s, %(canonical)s, %(kind)s) "
    "ON CONFLICT DO NOTHING"
)
_INSERT_NEIGHBOR = (
    "INSERT INTO city_neighbors (city, neighbor, distance_km) "
    "VALUES (%(city)s, %(neighbor)s, %(distance_km)s) ON CONFLICT DO NOTHING"
)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _self_aliases(listings: list[Listing]) -> list[dict[str, str]]:
    """Canonical names are aliases of themselves, so exact matches need no special case."""
    rows = [{"alias": x.model.lower(), "canonical": x.model, "kind": "model"} for x in listings]
    rows += [{"alias": x.make.lower(), "canonical": x.make, "kind": "make"} for x in listings]
    rows += [{"alias": c.value, "canonical": c.value, "kind": "city"} for c in City]
    rows += [
        {"alias": b.value.replace("_", " "), "canonical": b.value, "kind": "body_type"}
        for b in BodyType
    ]
    rows += [{"alias": f.value, "canonical": f.value, "kind": "fuel"} for f in Fuel]
    return rows


async def seed(pool: PgPool, data_dir: Path) -> None:
    """Listings load only into an empty table, so listing ids stay stable for the eval. The
    small lookup tables are replaced on every boot, so CSV edits reach an existing DB."""
    async with pool.connection() as conn:
        await conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        cur = await conn.execute("SELECT count(*) FROM listings")
        row = await cur.fetchone()
        listings = [Listing.model_validate(r) for r in _read(data_dir / "listings.csv")]
        # One transaction: a failed load keeps the old rows instead of leaving tables empty.
        async with conn.transaction(), conn.cursor() as c:
            if not (row and row[0]):
                await c.executemany(_INSERT_LISTING, [x.model_dump(mode="json") for x in listings])
            await c.execute("DELETE FROM aliases")
            await c.execute("DELETE FROM city_neighbors")
            await c.executemany(
                _INSERT_ALIAS, _read(data_dir / "aliases.csv") + _self_aliases(listings)
            )
            await c.executemany(_INSERT_NEIGHBOR, _read(data_dir / "city_neighbors.csv"))


async def _main() -> None:
    settings = get_settings()
    async with open_pool(settings.database_url) as pool:
        await seed(pool, settings.data_dir)
    print("seeded")


if __name__ == "__main__":
    run(_main())
