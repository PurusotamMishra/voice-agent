"""`uv run python -m voice_agent.api`: serve the API (Selector loop on Windows via aio.run)."""

import logging

import uvicorn

from voice_agent.aio import run
from voice_agent.api.app import create_app
from voice_agent.api.services import real_services
from voice_agent.config import get_settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()
    app = create_app(settings, real_services)
    config = uvicorn.Config(app, host=settings.api_host, port=settings.api_port, loop="none")
    run(uvicorn.Server(config).serve())


if __name__ == "__main__":
    main()
