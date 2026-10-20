"""Wire real providers into the graph (used by CLI, eval and the API in Plan 2)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
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
    # check= tests each connection on checkout, so one dropped by the network is replaced
    # instead of failing the turn. The checkpointer gets its own small pool because LangGraph
    # needs dict rows and no prepared statements, which the catalog code does not use.
    check = AsyncConnectionPool.check_connection
    async with AsyncConnectionPool(
        settings.database_url, open=False, kwargs={"autocommit": True}, check=check
    ) as pool:
        await seed(pool, settings.data_dir)
        compose_llm = (
            make_llm(settings, settings.groq_compose_model) if settings.groq_compose_model else None
        )
        deps = Deps(
            llm=make_llm(settings),
            normalizer=PgNormalizer(pool),
            catalog=PgCatalog(pool),
            vocab=await load_vocab(pool),
            neighbors=await load_neighbors(pool),
            weights=load_weights(settings.ranking_config),
            alias_map=await load_alias_map(pool),
            compose_llm=compose_llm,
        )
        saver_kwargs = {"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0}
        async with AsyncConnectionPool[AsyncConnection[DictRow]](
            settings.database_url, open=False, max_size=4, kwargs=saver_kwargs, check=check
        ) as saver_pool:
            saver = AsyncPostgresSaver(saver_pool, serde=checkpoint_serde())
            await saver.setup()
            log_path = settings.turn_log_path if log_turns else None
            yield TurnRunner(build_graph(deps, saver), log_path)
