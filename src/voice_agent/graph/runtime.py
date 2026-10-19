"""Wire real providers into the graph (used by CLI, eval and the API in Plan 2)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from voice_agent.catalog.ranker import load_weights
from voice_agent.config import Settings
from voice_agent.db.seed import seed
from voice_agent.graph.build import Deps, build_graph
from voice_agent.graph.runner import TurnRunner
from voice_agent.graph.state import checkpoint_serde
from voice_agent.providers.llm import make_llm
from voice_agent.providers.postgres import (
    PgCatalog,
    PgNormalizer,
    load_alias_map,
    load_neighbors,
    load_vocab,
)


@asynccontextmanager
async def build_runtime(settings: Settings, log_turns: bool = True) -> AsyncIterator[TurnRunner]:
    async with AsyncConnectionPool(
        settings.database_url, open=False, kwargs={"autocommit": True}
    ) as pool:
        await seed(pool, settings.data_dir)
        deps = Deps(
            llm=make_llm(settings),
            normalizer=PgNormalizer(pool),
            catalog=PgCatalog(pool),
            vocab=await load_vocab(pool),
            neighbors=await load_neighbors(pool),
            weights=load_weights(settings.ranking_config),
            alias_map=await load_alias_map(pool),
        )
        async with AsyncPostgresSaver.from_conn_string(
            settings.database_url, serde=checkpoint_serde()
        ) as saver:
            await saver.setup()
            log_path = settings.turn_log_path if log_turns else None
            yield TurnRunner(build_graph(deps, saver), log_path)
