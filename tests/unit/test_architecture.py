"""Hard rule 5: vendor and DB-driver imports live only in providers/."""

import re
from pathlib import Path

SRC = Path(__file__).parents[2] / "src" / "voice_agent"
_DB_DRIVER = re.compile(r"^\s*(?:from|import)\s+psycopg", re.MULTILINE)


def test_db_driver_is_imported_only_in_providers() -> None:
    offenders = sorted(
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if "providers" not in p.parts and _DB_DRIVER.search(p.read_text(encoding="utf-8"))
    )
    assert offenders == []
