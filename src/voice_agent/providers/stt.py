"""Speech-to-text providers (H2, N3): Groq Whisper for English, Sarvam Saaras for Hinglish."""

import math
from typing import Any

import httpx

from voice_agent.config import Settings, key
from voice_agent.domain.ports import SttChoice, Transcript
from voice_agent.providers.http import post_with_retry

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
# Without a hint Whisper writes Hindi words in Devanagari; our parser and aliases are Roman script.
HINGLISH_PROMPT = (
    "Hinglish in Roman script. Mujhe Pune mein paanch lakh tak ka chhota truck chahiye."
)


class GroqSTT:
    name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.AsyncClient,
        *,
        language: str | None = "en",
        prompt: str | None = None,
        backoff: float = 0.5,
    ) -> None:
        self._key, self._model, self._client = api_key, model, client
        self._language, self._prompt, self._backoff = language, prompt, backoff

    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> Transcript:
        data = {"model": self._model, "response_format": "verbose_json", "temperature": "0"}
        if self._language:
            data["language"] = self._language
        if self._prompt:
            data["prompt"] = self._prompt
        resp = await post_with_retry(
            self.name,
            self._client,
            GROQ_URL,
            backoff=self._backoff,
            headers={"Authorization": f"Bearer {self._key}"},
            data=data,
            files={"file": (filename, audio, content_type)},
        )
        body: dict[str, Any] = resp.json()
        return Transcript(
            text=str(body.get("text", "")).strip(),
            provider=self.name,
            language=body.get("language"),
            confidence=_confidence(body.get("segments") or []),
            audio_seconds=float(body.get("duration") or 0.0),
        )


def _confidence(segments: list[dict[str, Any]]) -> float | None:
    """exp(mean avg_logprob): a rough 0..1 score, shown on screen, never used as a gate."""
    if not segments:
        return None
    mean = sum(float(s.get("avg_logprob", 0.0)) for s in segments) / len(segments)
    return round(math.exp(mean), 3)


class SarvamSTT:
    name = "sarvam"

    def __init__(
        self,
        api_key: str,
        model: str,
        mode: str,
        client: httpx.AsyncClient,
        *,
        backoff: float = 0.5,
    ) -> None:
        self._key, self._model, self._mode = api_key, model, mode
        self._client, self._backoff = client, backoff

    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> Transcript:
        resp = await post_with_retry(
            self.name,
            self._client,
            SARVAM_URL,
            backoff=self._backoff,
            headers={"api-subscription-key": self._key},
            data={"model": self._model, "mode": self._mode, "language_code": "hi-IN"},
            files={"file": (filename, audio, content_type)},
        )
        body: dict[str, Any] = resp.json()
        return Transcript(
            text=str(body.get("transcript", "")).strip(),
            provider=self.name,
            language=body.get("language_code"),
        )


def make_stt(settings: Settings, client: httpx.AsyncClient) -> dict[str, SttChoice]:
    """Input language -> STT (N3). Missing keys shrink the map; the UI's typed input still works."""
    choices: dict[str, SttChoice] = {}
    groq_key, sarvam_key = key(settings.groq_api_key), key(settings.sarvam_api_key)
    if groq_key:
        choices["en"] = SttChoice(GroqSTT(groq_key, settings.groq_stt_model, client))
    if sarvam_key:
        sarvam = SarvamSTT(sarvam_key, settings.sarvam_stt_model, settings.sarvam_stt_mode, client)
        choices["hi-en"] = SttChoice(sarvam)
    elif groq_key:
        groq_hinglish = GroqSTT(
            groq_key, settings.groq_stt_model, client, language=None, prompt=HINGLISH_PROMPT
        )
        choices["hi-en"] = SttChoice(groq_hinglish, ("stt_hinglish_groq",))
    return choices
