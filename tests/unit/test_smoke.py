from voice_agent.aio import run


async def _answer() -> int:
    return 42


def test_run_executes_coroutine() -> None:
    assert run(_answer()) == 42
