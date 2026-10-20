import json

import httpx
from pydantic import SecretStr

from voice_agent.config import Settings
from voice_agent.providers.tts import ElevenLabsTTS, make_tts, speakable


def test_speakable_reads_rupee_sign() -> None:
    assert speakable("at ₹4.8 lakh") == "at rupees 4.8 lakh"


async def test_elevenlabs_posts_text_and_returns_audio() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"ID3mp3")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tts = ElevenLabsTTS("xk", "voice1", "eleven_flash_v2_5", client)
    audio = await tts.synthesize("First, ₹4.8 lakh.")
    assert audio == b"ID3mp3"
    req = seen[0]
    assert req.url.path == "/v1/text-to-speech/voice1"
    assert req.url.params["output_format"] == "mp3_44100_64"
    assert req.headers["xi-api-key"] == "xk"
    assert json.loads(req.content) == {
        "text": "First, rupees 4.8 lakh.",
        "model_id": "eleven_flash_v2_5",
    }


def test_make_tts_needs_a_key() -> None:
    s = Settings(_env_file=None, elevenlabs_api_key=SecretStr(""))  # type: ignore[call-arg]
    assert make_tts(s, httpx.AsyncClient()) is None
    s = Settings(_env_file=None, elevenlabs_api_key=SecretStr("k"))  # type: ignore[call-arg]
    tts = make_tts(s, httpx.AsyncClient())
    assert tts is not None and tts.name == "elevenlabs"
