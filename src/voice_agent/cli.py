"""Interactive text chat over the real pipeline (M1 demo; Plan 2 adds voice)."""

import json
from uuid import uuid4

from voice_agent.aio import run
from voice_agent.config import get_settings
from voice_agent.graph.runner import TurnResult
from voice_agent.graph.runtime import build_runtime


def print_turn(r: TurnResult) -> None:
    print(f"  intent={r.intent} route={r.route} diff={r.slot_diff}")
    print(f"  slots={json.dumps(r.slots)}")
    if r.sql:
        print(f"  sql={r.sql}\n  params={r.sql_params}")
    for s in r.results:
        x = s.listing
        print(
            f"  #{s.rank} {x.listing_id} {x.year} {x.make} {x.model} ₹{x.price_inr:,} "
            f"{x.km_driven:,}km score={s.score} {s.contributions}"
        )
    if r.relaxation:
        print(f"  relaxation={r.relaxation.model_dump(mode='json')}")
    print(f"  verdict={r.verdict.source} ok={r.verdict.ok} fallbacks={r.fallback_used}")
    print(f"  timings_ms={r.timings_ms}")
    print(f"bot> {r.response_text}")


async def chat() -> None:
    session = uuid4().hex[:8]
    async with build_runtime(get_settings()) as runner:
        print(f"session {session}. Type 'quit' to exit.")
        while (text := input("you> ").strip()) not in {"quit", "exit"}:
            if text:
                print_turn(await runner.run(session, text))


if __name__ == "__main__":
    run(chat())
