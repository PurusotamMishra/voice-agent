"""Text-to-speech provider (H3): ElevenLabs Flash, one call per sentence (N2)."""

import httpx

from voice_agent.config import Settings, key
from voice_agent.domain.ports import TextToSpeech
from voice_agent.providers.http import post_with_retry

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
OUTPUT_FORMAT = "mp3_44100_64"  # small enough for base64 in NDJSON, fine for speech


def speakable(text: str) -> str:
    """Spoken form of fact-sheet strings. Only symbols change; numbers stay exactly as validated."""
    return text.replace("₹", "rupees ")


class ElevenLabsTTS:
    name = "elevenlabs"

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model: str,
        client: httpx.AsyncClient,
        *,
        backoff: float = 0.5,
    ) -> None:
        self._key, self._voice, self._model = api_key, voice_id, model
        self._client, self._backoff = client, backoff

    async def synthesize(self, text: str) -> bytes:
        resp = await post_with_retry(
            self.name,
            self._client,
            ELEVENLABS_URL.format(voice_id=self._voice),
            backoff=self._backoff,
            params={"output_format": OUTPUT_FORMAT},
            headers={"xi-api-key": self._key},
            json={"text": speakable(text), "model_id": self._model},
        )
        return resp.content


def make_tts(settings: Settings, client: httpx.AsyncClient) -> TextToSpeech | None:
    """None means the browser speaks (H5 fallback, `tts: "client"`)."""
    api_key = key(settings.elevenlabs_api_key)
    if api_key is None:
        return None
    return ElevenLabsTTS(api_key, settings.elevenlabs_voice_id, settings.elevenlabs_model, client)
