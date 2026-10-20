import httpx
import pytest
from pydantic import SecretStr

from voice_agent.config import Settings
from voice_agent.domain.ports import ProviderError
from voice_agent.providers.stt import GroqSTT, SarvamSTT, make_stt


def _client(body: dict[str, object], seen: list[httpx.Request]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _raw_client(content: bytes) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_groq_stt_parses_verbose_json() -> None:
    seen: list[httpx.Request] = []
    body = {
        "text": " Tata Ace in Pune ",
        "language": "english",
        "duration": 2.4,
        "segments": [{"avg_logprob": -0.1}, {"avg_logprob": -0.3}],
    }
    async with _client(body, seen) as client:
        stt = GroqSTT("k", "whisper-large-v3", client)
        t = await stt.transcribe(b"RIFF", "a.webm", "audio/webm")
    assert t.text == "Tata Ace in Pune" and t.provider == "groq"
    assert t.audio_seconds == 2.4 and t.confidence is not None and 0.8 < t.confidence < 0.9
    req = seen[0]
    assert req.headers["Authorization"] == "Bearer k"
    assert b'name="model"' in req.content and b"whisper-large-v3" in req.content
    assert b'name="language"' in req.content


async def test_groq_hinglish_variant_sends_prompt_not_language() -> None:
    seen: list[httpx.Request] = []
    async with _client({"text": "x"}, seen) as client:
        stt = GroqSTT("k", "m", client, language=None, prompt="Roman script")
        await stt.transcribe(b"x", "a.webm", "audio/webm")
    assert b'name="prompt"' in seen[0].content and b'name="language"' not in seen[0].content


async def test_sarvam_stt_sends_mode_and_key() -> None:
    seen: list[httpx.Request] = []
    body = {"request_id": "r", "transcript": "Pune mein paanch lakh tak", "language_code": "hi-IN"}
    async with _client(body, seen) as client:
        stt = SarvamSTT("sk", "saaras:v3", "translit", client)
        t = await stt.transcribe(b"x", "a.webm", "audio/webm")
    assert (
        t.text == "Pune mein paanch lakh tak" and t.language == "hi-IN" and t.provider == "sarvam"
    )
    assert seen[0].headers["api-subscription-key"] == "sk"
    assert b"translit" in seen[0].content and b"saaras:v3" in seen[0].content


async def test_groq_non_json_body_raises_provider_error() -> None:
    async with _raw_client(b"<html>oops</html>") as client:
        stt = GroqSTT("k", "m", client)
        with pytest.raises(ProviderError) as err:
            await stt.transcribe(b"x", "a.webm", "audio/webm")
    assert not err.value.retryable


async def test_sarvam_non_json_body_raises_provider_error() -> None:
    async with _raw_client(b"<html>oops</html>") as client:
        stt = SarvamSTT("sk", "saaras:v3", "translit", client)
        with pytest.raises(ProviderError) as err:
            await stt.transcribe(b"x", "a.webm", "audio/webm")
    assert not err.value.retryable


async def test_groq_non_numeric_duration_raises_provider_error() -> None:
    async with _client({"text": "x", "duration": "abc"}, []) as client:
        stt = GroqSTT("k", "m", client)
        with pytest.raises(ProviderError):
            await stt.transcribe(b"x", "a.webm", "audio/webm")


async def test_groq_non_numeric_logprob_raises_provider_error() -> None:
    async with _client({"text": "x", "segments": [{"avg_logprob": "bad"}]}, []) as client:
        stt = GroqSTT("k", "m", client)
        with pytest.raises(ProviderError):
            await stt.transcribe(b"x", "a.webm", "audio/webm")


def _settings(**kw: object) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg, arg-type]


async def test_make_stt_prefers_sarvam_for_hinglish() -> None:
    s = _settings(groq_api_key=SecretStr("g"), sarvam_api_key=SecretStr("s"))
    async with httpx.AsyncClient() as client:
        choices = make_stt(s, client)
    assert choices["en"].stt.name == "groq" and choices["hi-en"].stt.name == "sarvam"
    assert choices["hi-en"].fallbacks == ()


async def test_make_stt_falls_back_to_groq_for_hinglish() -> None:
    async with httpx.AsyncClient() as client:
        choices = make_stt(_settings(groq_api_key=SecretStr("g")), client)
    assert choices["hi-en"].stt.name == "groq"
    assert choices["hi-en"].fallbacks == ("stt_hinglish_groq",)


async def test_make_stt_without_keys_is_empty() -> None:
    async with httpx.AsyncClient() as client:
        assert make_stt(_settings(groq_api_key=SecretStr(" ")), client) == {}
