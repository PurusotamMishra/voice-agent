"""Shared pytest config."""

import asyncio
import sys
from collections.abc import Mapping
from typing import Any

import pytest


def pytest_asyncio_loop_factories(config: pytest.Config, item: pytest.Item) -> Mapping[str, Any]:
    """psycopg async rejects ProactorEventLoop, the Windows default."""
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}
