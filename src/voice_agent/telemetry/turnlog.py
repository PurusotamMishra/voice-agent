"""Append one JSON record per turn to logs/turns.jsonl (K4)."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def append_turn(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
