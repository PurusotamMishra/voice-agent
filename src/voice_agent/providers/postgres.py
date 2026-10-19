"""Postgres implementations of Catalog and Normalizer (B5, D2), plus startup loaders."""

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from voice_agent.catalog.filters import build_count_sql, build_search_sql
from voice_agent.domain.enums import AliasKind, City
from voice_agent.domain.models import Filters, Listing
from voice_agent.domain.ports import Match, SearchResult
from voice_agent.response.validator import EntityVocab


class PgCatalog:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def search(self, filters: Filters, limit: int = 500) -> SearchResult:
        sql, params = build_search_sql(filters, limit)
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
        return SearchResult(rows=[Listing.model_validate(r) for r in rows], sql=sql, params=params)

    async def count(self, filters: Filters) -> int:
        sql, params = build_count_sql(filters)
        async with self._pool.connection() as conn:
            cur = await conn.execute(sql, params)
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def get(self, listing_id: str) -> Listing | None:
        result = await self._search_by_id(listing_id)
        return result[0] if result else None

    async def _search_by_id(self, listing_id: str) -> list[Listing]:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM listings WHERE listing_id = %(id)s", {"id": listing_id}
            )
            return [Listing.model_validate(r) for r in await cur.fetchall()]


class PgNormalizer:
    """Raw mention → canonical value: exact alias first, then pg_trgm similarity (D2)."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def normalize(self, kind: AliasKind, raw: str) -> Match:
        q = raw.strip().lower()
        params = {"kind": kind.value, "q": q}
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT canonical FROM aliases WHERE kind = %(kind)s AND alias = %(q)s", params
            )
            row = await cur.fetchone()
            if row:
                return Match(raw=raw, canonical=row[0], score=1.0, method="exact")
            cur = await conn.execute(
                "SELECT canonical, similarity(alias, %(q)s) AS score FROM aliases "
                "WHERE kind = %(kind)s ORDER BY score DESC LIMIT 1",
                params,
            )
            row = await cur.fetchone()
        if row and float(row[1]) > 0:
            return Match(raw=raw, canonical=row[0], score=round(float(row[1]), 3), method="trigram")
        return Match(raw=raw, canonical=None, score=0.0, method="none")


async def load_alias_map(pool: AsyncConnectionPool) -> dict[AliasKind, dict[str, str]]:
    out: dict[AliasKind, dict[str, str]] = {k: {} for k in AliasKind}
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT alias, canonical, kind FROM aliases")
        for alias, canonical, kind in await cur.fetchall():
            out[AliasKind(kind)][alias] = canonical
    return out


async def load_vocab(pool: AsyncConnectionPool) -> EntityVocab:
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT DISTINCT make, model FROM listings")
        rows = await cur.fetchall()
        # Only make/model aliases: body_type/city aliases would be misread as vehicles.
        cur = await conn.execute(
            "SELECT alias, kind, canonical FROM aliases WHERE kind IN ('make', 'model')"
        )
        alias_rows = await cur.fetchall()
    return EntityVocab(
        makes=frozenset(r[0] for r in rows),
        models=frozenset(r[1] for r in rows),
        aliases={a[0]: (a[1], a[2]) for a in alias_rows},
    )


async def load_neighbors(pool: AsyncConnectionPool) -> dict[City, list[City]]:
    out: dict[City, list[City]] = {}
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT city, neighbor FROM city_neighbors ORDER BY city, distance_km"
        )
        for city, neighbor in await cur.fetchall():
            out.setdefault(City(city), []).append(City(neighbor))
    return out
