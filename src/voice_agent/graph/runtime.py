"""Wire real providers into the graph (used by CLI, eval and the API in Plan 2)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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
    open_checkpointer,
    open_pool,
)


@asynccontextmanager
async def build_runtime(settings: Settings, log_turns: bool = True) -> AsyncIterator[TurnRunner]:
    async with open_pool(settings.database_url) as pool:
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
        async with open_checkpointer(settings.database_url, checkpoint_serde()) as saver:
            log_path = settings.turn_log_path if log_turns else None
            yield TurnRunner(build_graph(deps, saver), log_path)
