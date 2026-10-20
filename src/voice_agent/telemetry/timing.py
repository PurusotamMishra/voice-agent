"""Stage timers for per-turn latency (J4)."""

import time
from collections.abc import Iterator
from contextlib import contextmanager


class Stopwatch:
    def __init__(self) -> None:
        self.ms = 0.0


@contextmanager
def timed() -> Iterator[Stopwatch]:
    sw = Stopwatch()
    start = time.perf_counter()
    try:
        yield sw
    finally:
        sw.ms = round((time.perf_counter() - start) * 1000, 1)


class Clock:
    """Offsets from one start point, e.g. 'first audio ready 2.1 s after the request arrived'."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    def ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 1)
