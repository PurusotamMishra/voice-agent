"""Real wiring for the API: Postgres-backed runtime + STT + TTS sharing one HTTP client."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from voice_agent.api.stream import VoiceServices
from voice_agent.config import Settings
from voice_agent.graph.runtime import build_runtime
from voice_agent.providers.http import open_http_client
from voice_agent.providers.stt import make_stt
from voice_agent.providers.tts import make_tts


@asynccontextmanager
async def real_services(settings: Settings) -> AsyncIterator[VoiceServices]:
    async with open_http_client() as client, build_runtime(settings, log_turns=False) as runner:
        yield VoiceServices(
            runner=runner,
            stt=make_stt(settings, client),
            tts=make_tts(settings, client),
            tts_mode=settings.tts_mode,
            turn_log_path=settings.turn_log_path,  # N5: the API writes the richer record
        )
