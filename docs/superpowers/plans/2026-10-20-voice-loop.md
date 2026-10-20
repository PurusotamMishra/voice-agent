# Voice Loop, Hinglish and Ship (Plan 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** turn the working text loop (Plan 1, M1) into the full voice product:
- push-to-talk in a browser → STT → the existing turn pipeline → sentence-streamed TTS, with every panel the brief asks for (M2);
- Hinglish input with eval cases (M4);
- a one-command Docker setup, latency and cost reports, and a README (M5).

**Architecture:**
- STT and TTS stay **outside** the LangGraph graph.
- A plain-Python `api/stream.py` runs one turn as an async generator of NDJSON events: transcript → `TurnRunner.run` → understanding/search → sentence×N (TTS per sentence) → done.
- `api/app.py` is a thin FastAPI layer over it.
- Vendors (Groq Whisper, Sarvam, ElevenLabs) are httpx calls inside `providers/`, behind `SpeechToText` / `TextToSpeech` Protocols in `domain/ports.py`.
- The UI is a Vite + React + TS panel app served by nginx, which also proxies `/api` with buffering off.

**Tech Stack:** Python 3.12, uv, FastAPI, uvicorn, httpx, python-multipart, LangGraph (existing), Postgres 16, Vite 5, React 18, TypeScript 5, nginx, docker compose.

**Spec:** `docs/decisions.md` (binding; groups A–M), `docs/architecture.md` (§10 API, §11 latency, §13 fallbacks), `docs/plan-2-handoff.md` (state after Plan 1, environment facts). `docs/standards.md` and `CLAUDE.md` hard rules bind every task.

## Global Constraints

- The LLM never writes SQL. SQL comes only from `catalog/filters.py`. **Plan 2 does not touch the catalog or SQL code.**
- No invented facts: every spoken sentence is a sentence of `TurnResult.response` (validator-passed or template). TTS speaks exactly those sentences; it never gets other text.
- Vendor SDKs and vendor HTTP calls live only in `src/voice_agent/providers/`. LangChain/LangGraph imports only in `graph/` and `providers/`. `api/` may import `fastapi`/`uvicorn`, but never `httpx` directly (use `providers.http`).
- Every fallback is appended to `fallback_used` and logged at WARNING: `stt_error`, `stt_empty`, `stt_unavailable`, `stt_hinglish_groq`, `tts_client`.
- Money is int INR. Never print, log or commit API keys. `.env` is never committed. `.env.example` gets every new variable, with a blank value for secrets.
- Unit tests make no network calls (`httpx.MockTransport`, hand-written fakes in `tests/fakes.py`). `uv run pytest`, `uv run ruff format --check .`, `uv run ruff check .` and `uv run mypy src` must pass after every task. Strict mypy stays on `domain/ understanding/ catalog/ response/ state/`.
- Windows: any new asyncio entry point goes through `voice_agent.aio.run()` (Selector loop). Postgres for local runs is `localhost:5433`.
- Retries in providers: max 2 retries, exponential backoff with jitter, only on 429/5xx/network errors. After that, raise `ProviderError`. The caller decides the fallback (standards §3).
- One signed commit per task (`git commit`; never `--no-gpg-sign`, never `--no-verify`). Commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push.
- UI: React state only, no router, no state library, no CSS framework, one `styles.css`. `npm run lint` and `npm run build` must pass.
- Keep it thin: build nothing outside this plan and `decisions.md`.

## Plan-level rulings (made while writing this plan; recorded in decisions.md section N in Task 13)

- **N1 — Reply language.** The composer already replies in the detected language (English or Roman-script Hinglish). Templates stay English. A code-switching buyer understands them, and translating them all would be gold-plating. Cost if wrong: Hinglish users hear English on zero-result, confirm and follow-up turns.
- **N2 — Sentence-level TTS.** One vendor call per sentence, returning complete MP3 bytes. Each `sentence` NDJSON event carries `audio_b64`. Setting `TTS_MODE=sentence|whole` lets J5 compare the two. "Whole" means one call for the full text. Cost if wrong: the first sentence still waits for its own full synthesis (~a few hundred ms).
- **N3 — STT chosen per request** by the `language` form field:
  - `en` → `GroqSTT` (whisper-large-v3, `language=en`).
  - `hi-en` → `SarvamSTT` (`saaras:v3`, **mode `translit`**) when `SARVAM_API_KEY` is set.
  - Otherwise `hi-en` → `GroqSTT` with no language and a Roman-script prompt, recording fallback `stt_hinglish_groq`.
  - `translit` replaces the H2 wording "codemix": codemix returns Hindi words in Devanagari, and our parser and aliases are Roman script.
  - Cost if wrong: transliteration spelling variants ("panch") the parser doesn't know.
- **N4 — Understanding and search events are emitted after `TurnRunner.run` returns** (the graph runs atomically). Cost: those panels update a few seconds later than true streaming would. They still arrive before audio.
- **N5 — API logging.** The API builds the runtime with `log_turns=False`. It writes its own richer record (TurnResult + turn_id + STT/TTS timings + tts_mode) to `logs/turns.jsonl`. Browser timings go to `logs/client_timings.jsonl`, keyed by `turn_id`.
- **N6 — LLM latency knobs** (second J5 lever, aimed at the 8k TPM bottleneck):
  - `LLM_REASONING_EFFORT=low` is passed to Groq gpt-oss models.
  - Optional `GROQ_COMPOSE_MODEL` puts the composer on its own model and token bucket. Default unset = same model.
- **N7 — Audio eval clips.**
  - `scripts/make_eval_audio.py` synthesises stand-in clips (one with added noise) via ElevenLabs. They are labelled synthetic in the results.
  - The user may overwrite them with real recordings under the same names.
  - J1 asked for real voice, so the README states which kind was used.
- **N8 — Prices** live in `config/prices.yaml`, with the date they were checked and a "re-verify" note. The cost report converts USD → INR with one rate from that file.

## File structure

```
src/voice_agent/
  config.py                 + STT/TTS/API settings, key() helper (moved from providers/llm.py)
  domain/ports.py           + Usage.audio_seconds/characters, Transcript, SpeechToText, TextToSpeech, SttChoice
  telemetry/timing.py       + Clock (offset stamps from request start)
  providers/http.py         NEW: post_with_retry(), open_http_client()
  providers/stt.py          NEW: GroqSTT, SarvamSTT, make_stt()
  providers/tts.py          NEW: ElevenLabsTTS, speakable(), make_tts()
  providers/llm.py          reasoning_effort, groq model override, uses config.key()
  graph/build.py            Deps.compose_llm (optional)
  graph/runtime.py          compose_llm wiring
  graph/runner.py           + TurnRunner.state()
  api/__init__.py           NEW
  api/stream.py             NEW: TurnInput, VoiceServices, run_turn() → NDJSON events
  api/app.py                NEW: create_app(settings, services_factory)
  api/services.py           NEW: real_services() (wires runtime + STT + TTS)
  api/__main__.py           NEW: python -m voice_agent.api
ui/                         NEW: Vite + React + TS app (Tasks 7–8)
Dockerfile, .dockerignore, ui/Dockerfile, ui/nginx.conf, docker-compose.yml (app + ui)
eval/cases.yaml             + 7 Hinglish cases;  eval/run_eval.py  + --category
eval/audio/cases.yaml, eval/run_audio_eval.py, scripts/make_eval_audio.py
scripts/latency_report.py, scripts/cost_report.py, config/prices.yaml
README.md, docs/* updates
tests/unit/providers/test_stt.py, test_tts.py, test_http.py; tests/unit/api/test_stream.py, test_app.py
```

---

### Task 1: Ports, settings and dependencies for voice

**Files:**
- Modify: `pyproject.toml` / `uv.lock` (via `uv add`)
- Modify: `src/voice_agent/config.py`
- Modify: `src/voice_agent/domain/ports.py`
- Modify: `src/voice_agent/telemetry/timing.py`
- Modify: `src/voice_agent/providers/llm.py` (use `config.key`)
- Modify: `.env.example`
- Test: `tests/unit/test_config.py`, `tests/unit/domain/test_ports.py` (create if missing)

**Interfaces:**
- Produces: `config.key(secret: SecretStr | None) -> str | None`.
- Produces new `Settings` fields (exact names below).
- Produces `Usage.audio_seconds: float`, `Usage.characters: int`, `Transcript`, `SpeechToText`, `TextToSpeech`, `SttChoice`, `telemetry.timing.Clock`.

- [ ] **Step 1: Add dependencies**

```bash
uv add fastapi uvicorn python-multipart httpx
```

- [ ] **Step 2: Write failing tests** in `tests/unit/test_config.py` (append):

```python
from pydantic import SecretStr

from voice_agent.config import key


def test_key_treats_blank_as_missing() -> None:
    assert key(None) is None
    assert key(SecretStr("   ")) is None
    assert key(SecretStr("abc")) == "abc"


def test_voice_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TTS_MODE", "SARVAM_STT_MODE", "LLM_REASONING_EFFORT"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.tts_mode == "sentence"
    assert s.sarvam_stt_mode == "translit"
    assert s.llm_reasoning_effort == "low"
    assert s.groq_compose_model is None
```

And `tests/unit/domain/test_ports.py` (create; add `tests/unit/domain/__init__.py` if missing):

```python
from voice_agent.domain.ports import SttChoice, Transcript, Usage
from voice_agent.telemetry.timing import Clock


def test_usage_has_audio_and_character_counters() -> None:
    u = Usage(provider="groq-stt", audio_seconds=2.5)
    assert u.input_tokens == 0 and u.characters == 0 and u.audio_seconds == 2.5


def test_transcript_defaults() -> None:
    t = Transcript(text="hi", provider="groq")
    assert t.confidence is None and t.language is None and t.audio_seconds == 0.0


def test_stt_choice_defaults_to_no_fallbacks() -> None:
    class _S:
        name = "x"

    assert SttChoice(stt=_S()).fallbacks == ()  # type: ignore[arg-type]


def test_clock_is_monotonic_ms() -> None:
    c = Clock()
    assert 0 <= c.ms() <= c.ms()
```

- [ ] **Step 3: Run them and confirm they fail**

Run: `uv run pytest tests/unit/test_config.py tests/unit/domain/test_ports.py -q`
Expected: FAIL (ImportError for `key`, `Transcript`, `Clock`).

- [ ] **Step 4: Implement**

`src/voice_agent/config.py` (whole file):

```python
"""Runtime settings from env / .env (standards §1: no os.getenv elsewhere)."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://voice:voice@localhost:5433/voice"
    data_dir: Path = Path("data")
    ranking_config: Path = Path("config/ranking.yaml")
    turn_log_path: Path = Path("logs/turns.jsonl")
    client_timings_path: Path = Path("logs/client_timings.jsonl")

    llm_provider: Literal["groq", "gemini"] = "groq"
    llm_fallback_provider: Literal["groq", "gemini", "none"] = "gemini"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_compose_model: str | None = None  # N6: composer on its own token bucket
    llm_reasoning_effort: Literal["low", "medium", "high"] = "low"  # N6: gpt-oss only
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash-lite"

    groq_stt_model: str = "whisper-large-v3"  # H2
    sarvam_api_key: SecretStr | None = None
    sarvam_stt_model: str = "saaras:v3"
    sarvam_stt_mode: Literal["translit", "codemix", "transcribe"] = "translit"  # N3

    elevenlabs_api_key: SecretStr | None = None
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model: str = "eleven_flash_v2_5"  # H3
    tts_mode: Literal["sentence", "whole"] = "sentence"  # N2 / J5

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"


def get_settings() -> Settings:
    return Settings()


def key(secret: SecretStr | None) -> str | None:
    """An empty `KEY=` line in .env yields SecretStr(''): treat it as unset."""
    if secret is None or not secret.get_secret_value().strip():
        return None
    return secret.get_secret_value()
```

In `src/voice_agent/providers/llm.py`, delete `_secret` and use `key`:
- `api_key = key(settings.groq_api_key)`, then pass `api_key=SecretStr(api_key)` to `ChatGroq`.
- Same for Gemini: `google_api_key=api_key`.
- Keep the rest unchanged; Task 4 edits this file again.

`src/voice_agent/domain/ports.py`: replace `Usage` and append the new types:

```python
class Usage(BaseModel):
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    audio_seconds: float = 0.0  # STT (L5)
    characters: int = 0  # TTS (L5)


class Transcript(BaseModel):
    text: str
    provider: str
    language: str | None = None
    confidence: float | None = None  # 0..1, only when the vendor reports something usable
    audio_seconds: float = 0.0  # 0 when the vendor does not report it


class SpeechToText(Protocol):
    name: str

    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> Transcript: ...


class TextToSpeech(Protocol):
    name: str

    async def synthesize(self, text: str) -> bytes: ...


@dataclass(frozen=True)
class SttChoice:
    """The STT used for one input language, plus the fallbacks that choice implies (N3)."""

    stt: SpeechToText
    fallbacks: tuple[str, ...] = ()
```

`src/voice_agent/telemetry/timing.py`: append

```python
class Clock:
    """Offsets from one start point, e.g. 'first audio ready 2.1 s after the request arrived'."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    def ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 1)
```

`.env.example`: append

```
# Voice (Plan 2). Groq key above also powers English STT.
GROQ_COMPOSE_MODEL=                   # optional: composer on its own model / token bucket (N6)
LLM_REASONING_EFFORT=low
GROQ_STT_MODEL=whisper-large-v3
SARVAM_API_KEY=                       # optional: Hinglish STT (falls back to Groq Whisper)
SARVAM_STT_MODEL=saaras:v3
SARVAM_STT_MODE=translit
ELEVENLABS_API_KEY=                   # optional: server TTS (falls back to browser speech)
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
ELEVENLABS_MODEL=eleven_flash_v2_5
TTS_MODE=sentence                     # sentence | whole (J5 comparison)
API_HOST=127.0.0.1
API_PORT=8000
CORS_ORIGINS=http://localhost:5173
```

- [ ] **Step 5: Run the full checks**

Run: `uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run mypy src`
Expected: all pass. The existing `test_llm.py` tests must still pass, because the empty-key behaviour hasn't changed.

- [ ] **Step 6: Commit**

```bash
git add -A pyproject.toml uv.lock src tests .env.example
git commit -m "Add voice ports, settings and HTTP dependencies"
```

---

### Task 2: HTTP helper and STT providers (Groq Whisper, Sarvam)

**Files:**
- Create: `src/voice_agent/providers/http.py`, `src/voice_agent/providers/stt.py`
- Test: `tests/unit/providers/test_http.py`, `tests/unit/providers/test_stt.py`

**Interfaces:**
- Consumes: `Settings`, `key()`, `Transcript`, `SttChoice`, `ProviderError` (Task 1).
- Produces:
  - `post_with_retry(provider: str, client: httpx.AsyncClient, url: str, *, retries: int = 2, backoff: float = 0.5, **kwargs: Any) -> httpx.Response`
  - `open_http_client() -> httpx.AsyncClient` (timeout 20 s)
  - `GroqSTT(api_key, model, client, *, language="en", prompt=None, backoff=0.5)`, `SarvamSTT(api_key, model, mode, client, *, backoff=0.5)`
  - `make_stt(settings, client) -> dict[str, SttChoice]` with keys `"en"` and `"hi-en"`; an empty dict when there's no Groq key and no Sarvam key.

- [ ] **Step 1: Write failing tests**

`tests/unit/providers/test_http.py`:

```python
import httpx
import pytest

from voice_agent.domain.ports import ProviderError
from voice_agent.providers.http import post_with_retry


def _client(statuses: list[int]) -> tuple[httpx.AsyncClient, list[int]]:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(statuses[len(calls) - 1], json={"ok": True})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


async def test_retries_429_then_succeeds() -> None:
    client, calls = _client([429, 200])
    resp = await post_with_retry("v", client, "https://x.test", backoff=0)
    assert resp.status_code == 200 and len(calls) == 2


async def test_gives_up_after_two_retries() -> None:
    client, calls = _client([503, 503, 503])
    with pytest.raises(ProviderError) as err:
        await post_with_retry("v", client, "https://x.test", backoff=0)
    assert err.value.retryable and len(calls) == 3


async def test_client_error_is_not_retried() -> None:
    client, calls = _client([401])
    with pytest.raises(ProviderError) as err:
        await post_with_retry("v", client, "https://x.test", backoff=0)
    assert not err.value.retryable and len(calls) == 1
    assert "401" in str(err.value)


async def test_network_error_becomes_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError):
        await post_with_retry("v", client, "https://x.test", backoff=0)
```

`tests/unit/providers/test_stt.py`:

```python
import httpx
from pydantic import SecretStr

from voice_agent.config import Settings
from voice_agent.providers.stt import GroqSTT, SarvamSTT, make_stt


def _client(body: dict[str, object], seen: list[httpx.Request]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_groq_stt_parses_verbose_json() -> None:
    seen: list[httpx.Request] = []
    body = {
        "text": " Tata Ace in Pune ",
        "language": "english",
        "duration": 2.4,
        "segments": [{"avg_logprob": -0.1}, {"avg_logprob": -0.3}],
    }
    stt = GroqSTT("k", "whisper-large-v3", _client(body, seen))
    t = await stt.transcribe(b"RIFF", "a.webm", "audio/webm")
    assert t.text == "Tata Ace in Pune" and t.provider == "groq"
    assert t.audio_seconds == 2.4 and t.confidence is not None and 0.8 < t.confidence < 0.9
    req = seen[0]
    assert req.headers["Authorization"] == "Bearer k"
    assert b'name="model"' in req.content and b"whisper-large-v3" in req.content
    assert b'name="language"' in req.content


async def test_groq_hinglish_variant_sends_prompt_not_language() -> None:
    seen: list[httpx.Request] = []
    stt = GroqSTT("k", "m", _client({"text": "x"}, seen), language=None, prompt="Roman script")
    await stt.transcribe(b"x", "a.webm", "audio/webm")
    assert b'name="prompt"' in seen[0].content and b'name="language"' not in seen[0].content


async def test_sarvam_stt_sends_mode_and_key() -> None:
    seen: list[httpx.Request] = []
    body = {"request_id": "r", "transcript": "Pune mein paanch lakh tak", "language_code": "hi-IN"}
    stt = SarvamSTT("sk", "saaras:v3", "translit", _client(body, seen))
    t = await stt.transcribe(b"x", "a.webm", "audio/webm")
    assert t.text == "Pune mein paanch lakh tak" and t.language == "hi-IN" and t.provider == "sarvam"
    assert seen[0].headers["api-subscription-key"] == "sk"
    assert b"translit" in seen[0].content and b"saaras:v3" in seen[0].content


def _settings(**kw: object) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg, arg-type]


def test_make_stt_prefers_sarvam_for_hinglish() -> None:
    s = _settings(groq_api_key=SecretStr("g"), sarvam_api_key=SecretStr("s"))
    choices = make_stt(s, httpx.AsyncClient())
    assert choices["en"].stt.name == "groq" and choices["hi-en"].stt.name == "sarvam"
    assert choices["hi-en"].fallbacks == ()


def test_make_stt_falls_back_to_groq_for_hinglish() -> None:
    choices = make_stt(_settings(groq_api_key=SecretStr("g")), httpx.AsyncClient())
    assert choices["hi-en"].stt.name == "groq"
    assert choices["hi-en"].fallbacks == ("stt_hinglish_groq",)


def test_make_stt_without_keys_is_empty() -> None:
    assert make_stt(_settings(groq_api_key=SecretStr(" ")), httpx.AsyncClient()) == {}
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/unit/providers/test_http.py tests/unit/providers/test_stt.py -q`
Expected: FAIL (modules missing).

- [ ] **Step 3: Implement**

`src/voice_agent/providers/http.py`:

```python
"""Shared HTTP plumbing for vendor calls (standards §3: 2 retries, backoff + jitter)."""

import asyncio
import random
from typing import Any

import httpx

from voice_agent.domain.ports import ProviderError


def open_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(20.0))


async def post_with_retry(
    provider: str,
    client: httpx.AsyncClient,
    url: str,
    *,
    retries: int = 2,
    backoff: float = 0.5,
    **kwargs: Any,
) -> httpx.Response:
    """POST; retry 429/5xx/network errors, raise ProviderError on anything else or when out of tries."""
    error = ProviderError(provider, "no attempt made")
    for attempt in range(retries + 1):
        try:
            resp = await client.post(url, **kwargs)
        except httpx.TransportError as exc:
            error = ProviderError(provider, f"network error: {exc}", retryable=True)
        else:
            if resp.status_code < 400:
                return resp
            retryable = resp.status_code == 429 or resp.status_code >= 500
            error = ProviderError(provider, f"HTTP {resp.status_code}: {resp.text[:200]}", retryable)
            if not retryable:
                raise error
        if attempt < retries:
            await asyncio.sleep(backoff * 2**attempt + random.uniform(0, backoff / 2))
    raise error
```

`src/voice_agent/providers/stt.py`:

```python
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
HINGLISH_PROMPT = "Hinglish in Roman script. Mujhe Pune mein paanch lakh tak ka chhota truck chahiye."


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
        self, api_key: str, model: str, mode: str, client: httpx.AsyncClient, *, backoff: float = 0.5
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
```

- [ ] **Step 4: Run checks**

Run: `uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run mypy src`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -A src tests
git commit -m "Add Groq Whisper and Sarvam STT providers with retrying HTTP helper"
```

---

### Task 3: ElevenLabs TTS provider

**Files:**
- Create: `src/voice_agent/providers/tts.py`
- Test: `tests/unit/providers/test_tts.py`

**Interfaces:**
- Consumes: `post_with_retry`, `key`, `Settings` (Tasks 1–2).
- Produces:
  - `ElevenLabsTTS(api_key, voice_id, model, client, *, backoff=0.5)` with `name = "elevenlabs"` and `async synthesize(text) -> bytes` (MP3).
  - `speakable(text: str) -> str`.
  - `make_tts(settings, client) -> TextToSpeech | None`.

- [ ] **Step 1: Write failing tests** in `tests/unit/providers/test_tts.py`:

```python
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
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `uv run pytest tests/unit/providers/test_tts.py -q`. Expected: FAIL (module missing).

- [ ] **Step 3: Implement** `src/voice_agent/providers/tts.py`:

```python
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
```

- [ ] **Step 4: Run checks**

Run: `uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run mypy src`. Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add -A src tests
git commit -m "Add ElevenLabs TTS provider"
```

---

### Task 4: LLM latency knobs (reasoning effort, separate compose model)

**Files:**
- Modify: `src/voice_agent/providers/llm.py`
- Modify: `src/voice_agent/graph/build.py` (Deps + respond node)
- Modify: `src/voice_agent/graph/runtime.py`
- Test: `tests/unit/providers/test_llm.py`, `tests/unit/graph/test_graph.py`

**Interfaces:**
- Consumes: `Settings.llm_reasoning_effort`, `Settings.groq_compose_model` (Task 1).
- Produces:
  - `make_llm(settings: Settings, groq_model: str | None = None) -> LLM`
  - `groq_reasoning_effort(model: str, effort: str) -> str | None`
  - `Deps.compose_llm: LLM | None = None`. A new **last** field with a default, so existing `Deps(...)` calls keep working.

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/providers/test_llm.py`:

```python
from voice_agent.providers.llm import groq_reasoning_effort


def test_reasoning_effort_only_for_gpt_oss() -> None:
    assert groq_reasoning_effort("openai/gpt-oss-120b", "low") == "low"
    assert groq_reasoning_effort("qwen/qwen3.8-27b", "low") is None


def test_make_llm_accepts_a_groq_model_override() -> None:
    from pydantic import SecretStr

    s = Settings(_env_file=None, groq_api_key=SecretStr("k"), llm_fallback_provider="none")  # type: ignore[call-arg]
    llm = make_llm(s, groq_model="qwen/qwen3.8-27b")
    assert llm.name == "groq"
```

Append to `tests/unit/graph/test_graph.py`:

```python
async def test_compose_llm_is_used_for_composition_when_given() -> None:
    extract = FakeLLM(
        [
            TurnIntent(
                intent=Intent.SEARCH,
                slots=ExtractedSlots(fuel=Fuel.CNG, body_type=BodyType.PICKUP, city_mention="Mumbai"),
            )
        ]
    )
    composer = FakeLLM([ProviderError("fake", "composer offline")])
    deps = Deps(
        llm=extract,
        normalizer=FakeNormalizer({(AliasKind.CITY, "mumbai"): ("mumbai", 1.0)}),
        catalog=FakeCatalog(LISTINGS),
        vocab=EntityVocab(frozenset({"Tata"}), frozenset({"Ace Gold"})),
        neighbors={},
        weights=DEFAULT_WEIGHTS,
        alias_map={k: {} for k in AliasKind},
        compose_llm=composer,
    )
    r = TurnRunner(build_graph(deps, InMemorySaver()), turn_log_path=None)
    t = await r.run("s9", "CNG pickup in Mumbai")
    assert t.results and "template" in t.fallback_used  # the composer FakeLLM was the one called
    assert len(composer.calls) == 1  # FakeLLM records each structured() call
    assert len(extract.calls) == 1  # the extractor LLM was not asked to compose
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/unit/providers/test_llm.py tests/unit/graph/test_graph.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement**

In `providers/llm.py`:

```python
def groq_reasoning_effort(model: str, effort: str) -> str | None:
    """N6: gpt-oss spends hidden reasoning tokens against the 8k TPM budget; other models reject the arg."""
    return effort if model.startswith("openai/gpt-oss") else None


def _groq(settings: Settings, model: str | None = None) -> LLM | None:
    api_key = key(settings.groq_api_key)
    if api_key is None:
        return None
    from langchain_groq import ChatGroq

    name = model or settings.groq_model
    chat = ChatGroq(
        model_name=name,
        api_key=SecretStr(api_key),
        temperature=0,
        max_retries=2,
        timeout=15,
        reasoning_effort=groq_reasoning_effort(name, settings.llm_reasoning_effort),
    )
    return LangChainLLM("groq", chat)
```

Change `_FACTORIES` to plain factories for the fallback, and make `make_llm` take the override:

```python
def make_llm(settings: Settings, groq_model: str | None = None) -> LLM:
    if settings.llm_provider == "groq":
        primary = _groq(settings, groq_model)
    else:
        primary = _gemini(settings)
    if primary is None:
        raise RuntimeError(f"{settings.llm_provider.upper()}_API_KEY is not set (see .env.example)")
    fallback = None
    if settings.llm_fallback_provider not in ("none", settings.llm_provider):
        fallback = _FACTORIES[settings.llm_fallback_provider](settings)
    return FailoverLLM(primary, fallback)
```

(`_FACTORIES` stays as `{"groq": _groq, "gemini": _gemini}`; `_groq`'s second parameter has a default, so it still fits `Callable[[Settings], LLM | None]`.)

In `graph/build.py`: add `compose_llm: LLM | None = None` as the last `Deps` field. In `respond_node`, call `compose_results(facts, deps.compose_llm or deps.llm, deps.vocab)`.

In `graph/runtime.py`:

```python
        llm = make_llm(settings)
        compose_llm = make_llm(settings, settings.groq_compose_model) if settings.groq_compose_model else None
        deps = Deps(llm=llm, ..., compose_llm=compose_llm)
```

- [ ] **Step 4: Run checks**

Run: `uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run mypy src`. Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add -A src tests
git commit -m "Add LLM latency knobs: gpt-oss reasoning effort and optional compose model"
```

---

### Task 5: Voice turn stream (`api/stream.py`) and runner state snapshot

**Files:**
- Create: `src/voice_agent/api/__init__.py` (docstring only), `src/voice_agent/api/stream.py`
- Modify: `src/voice_agent/graph/runner.py` (add `state()`)
- Modify: `tests/fakes.py` (add `FakeSTT`, `FakeTTS`)
- Test: `tests/unit/api/__init__.py`, `tests/unit/api/test_stream.py`, `tests/unit/graph/test_graph.py`

**Interfaces:**
- Consumes: `TurnRunner.run`, `TurnResult`, `SttChoice`, `TextToSpeech`, `Usage`, `Clock`, `timed`, `append_turn`.
- Produces:
  - `TurnRunner.state(session_id: str) -> dict[str, Any]`.
  - `api.stream.Runner` Protocol (`run`, `state`).
  - `TurnInput`, `VoiceServices`, `run_turn(svc, inp) -> AsyncIterator[dict[str, Any]]`, `STT_FAILED_TEXT`.
- NDJSON event shapes (Task 7's UI types mirror them exactly):
  - `{"type":"transcript","text","source":"stt"|"typed","provider","confidence","language"}`
  - `{"type":"understanding","turn","intent","language","route","slots","slot_diff","pending_confirmation"}`
  - `{"type":"search","filters","sql","params","results","relaxation"}`
  - `{"type":"sentence","index","text","audio_b64","tts":"server"|"client"}`
  - `{"type":"done","turn_id","turn","response_text","verdict","fallback_used","timings_ms","usage"}`
  - STT failure: transcript (empty text) → one sentence (`STT_FAILED_TEXT`) → done (`turn: null`, `verdict: null`). The runner is not called, so state stays unchanged (architecture §13).

- [ ] **Step 1: Add fakes** to `tests/fakes.py`:

```python
class FakeSTT:
    def __init__(self, text: str = "", error: Exception | None = None, name: str = "fake-stt") -> None:
        self.name, self._text, self._error = name, text, error

    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> Transcript:
        if self._error:
            raise self._error
        return Transcript(text=self._text, provider=self.name, confidence=0.9, audio_seconds=1.5)


class FakeTTS:
    def __init__(self, fail_after: int | None = None) -> None:
        self.name, self.spoken, self._fail_after = "fake-tts", [], fail_after

    async def synthesize(self, text: str) -> bytes:
        if self._fail_after is not None and len(self.spoken) >= self._fail_after:
            raise ProviderError("fake-tts", "quota")
        self.spoken.append(text)
        return b"mp3:" + text.encode()
```

Import `Transcript` and `ProviderError` from `voice_agent.domain.ports`, and annotate `self.spoken: list[str]`.

- [ ] **Step 2: Write failing tests**

Append to `tests/unit/graph/test_graph.py`:

```python
async def test_state_snapshot_is_json_safe() -> None:
    llm = FakeLLM(
        [
            TurnIntent(
                intent=Intent.SEARCH,
                slots=ExtractedSlots(fuel=Fuel.CNG, body_type=BodyType.PICKUP, city_mention="Mumbai"),
            ),
            ProviderError("fake", "composer offline"),
        ]
    )
    r = runner(llm)
    await r.run("s7", "CNG pickup in Mumbai")
    snap = await r.state("s7")
    assert snap["turn"] == 1 and snap["slots"]["fuel"] == "cng"
    assert snap["last_results"][0]["listing_id"] == "A"
    import json

    json.dumps(snap)  # must not raise
    assert (await r.state("never-seen"))["slots"] == {}
```

`tests/unit/api/test_stream.py`:

```python
import base64
from typing import Any

from tests.fakes import FakeSTT, FakeTTS
from voice_agent.api.stream import STT_FAILED_TEXT, TurnInput, VoiceServices, run_turn
from voice_agent.domain.ports import ProviderError, SttChoice
from voice_agent.graph.runner import TurnResult
from voice_agent.response.schema import ComposedResponse, ItemSentence, Verdict


def _result(session_id: str, text: str) -> TurnResult:
    response = ComposedResponse(
        intro="Here are the best matches.",
        items=[ItemSentence(listing_id="A", text="First, the Tata Ace at ₹4 lakh.")],
        closing="Want details?",
    )
    return TurnResult(
        session_id=session_id, turn=1, text=text, intent="search", language="en", route="search",
        slots={"city": "pune"}, slot_diff={"city": [None, "pune"]}, filters={"city": "pune"},
        sql="SELECT 1", sql_params={}, results=[], relaxation=None, pending_confirmation=None,
        followup_listing_id=None, followup_rank=None, response=response,
        response_text=response.text(), verdict=Verdict(ok=True, source="llm"),
        fallback_used=[], timings_ms={"nlu": 10.0, "compose": 5.0, "total": 20.0},
    )  # fmt: skip


class FakeRunner:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def run(self, session_id: str, text: str) -> TurnResult:
        self.texts.append(text)
        return _result(session_id, text)

    async def state(self, session_id: str) -> dict[str, Any]:
        return {"session_id": session_id}


async def _events(svc: VoiceServices, inp: TurnInput) -> list[dict[str, Any]]:
    return [e async for e in run_turn(svc, inp)]


def _svc(**kw: Any) -> VoiceServices:
    base: dict[str, Any] = {"runner": FakeRunner(), "stt": {}, "tts": FakeTTS()}
    return VoiceServices(**{**base, **kw})


async def test_typed_turn_event_order_and_sentence_audio() -> None:
    svc = _svc()
    ev = await _events(svc, TurnInput(session_id="s", text="Tata Ace in Pune"))
    assert [e["type"] for e in ev] == [
        "transcript", "understanding", "search", "sentence", "sentence", "sentence", "done",
    ]  # fmt: skip
    assert ev[0]["source"] == "typed" and ev[0]["text"] == "Tata Ace in Pune"
    first = ev[3]
    assert first["tts"] == "server" and base64.b64decode(first["audio_b64"]).startswith(b"mp3:")
    done = ev[-1]
    assert done["timings_ms"]["pipeline"] == 20.0 and "first_audio_ready" in done["timings_ms"]
    assert "total" not in done["timings_ms"]
    assert {u["provider"] for u in done["usage"]} == {"fake-tts-tts"}


async def test_audio_turn_uses_stt_for_the_chosen_language() -> None:
    runner = FakeRunner()
    stt = {"en": SttChoice(FakeSTT("english")), "hi-en": SttChoice(FakeSTT("hinglish"), ("x",))}
    svc = _svc(runner=runner, stt=stt)
    ev = await _events(svc, TurnInput(session_id="s", audio=b"a", language="hi-en"))
    assert runner.texts == ["hinglish"] and ev[0]["source"] == "stt"
    assert "x" in ev[-1]["fallback_used"] and "stt" in ev[-1]["timings_ms"]


async def test_stt_failure_speaks_apology_and_skips_runner() -> None:
    runner = FakeRunner()
    stt = {"en": SttChoice(FakeSTT(error=ProviderError("fake-stt", "down")))}
    ev = await _events(_svc(runner=runner, stt=stt), TurnInput(session_id="s", audio=b"a"))
    assert runner.texts == []
    assert [e["type"] for e in ev] == ["transcript", "sentence", "done"]
    assert ev[1]["text"] == STT_FAILED_TEXT and "stt_error" in ev[-1]["fallback_used"]
    assert ev[-1]["turn"] is None and ev[-1]["verdict"] is None


async def test_empty_transcript_is_a_recorded_fallback() -> None:
    stt = {"en": SttChoice(FakeSTT(""))}
    ev = await _events(_svc(stt=stt), TurnInput(session_id="s", audio=b"a"))
    assert "stt_empty" in ev[-1]["fallback_used"]


async def test_tts_failure_hands_remaining_sentences_to_browser() -> None:
    ev = await _events(_svc(tts=FakeTTS(fail_after=1)), TurnInput(session_id="s", text="x"))
    sentences = [e for e in ev if e["type"] == "sentence"]
    assert [s["tts"] for s in sentences] == ["server", "client", "client"]
    assert ev[-1]["fallback_used"].count("tts_client") == 1


async def test_no_tts_configured_means_client_speech() -> None:
    ev = await _events(_svc(tts=None), TurnInput(session_id="s", text="x"))
    assert all(e["audio_b64"] is None for e in ev if e["type"] == "sentence")
    assert "tts_client" in ev[-1]["fallback_used"]


async def test_whole_mode_sends_one_sentence() -> None:
    ev = await _events(_svc(tts_mode="whole"), TurnInput(session_id="s", text="x"))
    sentences = [e for e in ev if e["type"] == "sentence"]
    assert len(sentences) == 1 and sentences[0]["text"].startswith("Here are")


async def test_turn_is_logged_with_turn_id(tmp_path: Any) -> None:
    import json

    log = tmp_path / "turns.jsonl"
    ev = await _events(_svc(turn_log_path=log), TurnInput(session_id="s", text="x"))
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert record["turn_id"] == ev[-1]["turn_id"] and record["tts_mode"] == "sentence"
    assert record["input"] == "typed" and record["sql"] == "SELECT 1"
```

- [ ] **Step 3: Run them and confirm they fail**

Run: `uv run pytest tests/unit/api tests/unit/graph/test_graph.py -q`. Expected: FAIL.

- [ ] **Step 4: Implement**

`graph/runner.py`: add this method to `TurnRunner`, plus a module helper:

```python
    async def state(self, session_id: str) -> dict[str, Any]:
        """JSON-safe conversation memory (GET /api/session/{id}/state)."""
        snapshot = await self._graph.aget_state({"configurable": {"thread_id": session_id}})
        v: dict[str, Any] = snapshot.values or {}
        slots = v.get("slots")
        return {
            "session_id": session_id,
            "turn": v.get("turn", 0),
            "slots": slots.filled() if slots else {},
            "pending_confirmation": _dump(v.get("pending_confirmation")),
            "pending_relaxation": _dump(v.get("pending_relaxation")),
            "last_results": [r.model_dump(mode="json") for r in v.get("last_results") or []],
            "focused_listing_id": v.get("focused_listing_id"),
        }


def _dump(model: BaseModel | None) -> dict[str, Any] | None:
    return model.model_dump(mode="json") if model is not None else None
```

`src/voice_agent/api/__init__.py`:

```python
"""HTTP API (architecture §10): FastAPI over the voice turn stream."""
```

`src/voice_agent/api/stream.py`:

```python
"""One turn as NDJSON events (architecture §10, H4, J4). STT and TTS sit outside the graph:
transcribe -> TurnRunner.run -> speak each validated sentence. Plain Python, no FastAPI here."""

import base64
import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

from voice_agent.domain.ports import ProviderError, SttChoice, TextToSpeech, Usage
from voice_agent.graph.runner import TurnResult
from voice_agent.telemetry.timing import Clock, timed
from voice_agent.telemetry.turnlog import append_turn

log = logging.getLogger(__name__)

STT_FAILED_TEXT = "Sorry, I didn't catch that. Could you say it again, or type it?"


class Runner(Protocol):
    async def run(self, session_id: str, text: str) -> TurnResult: ...

    async def state(self, session_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class TurnInput:
    session_id: str
    text: str | None = None
    audio: bytes | None = None
    filename: str = "speech.webm"
    content_type: str = "audio/webm"
    language: str = "en"
    audio_seconds: float = 0.0  # client-measured clip length; Sarvam reports none (L5)


@dataclass(frozen=True)
class VoiceServices:
    runner: Runner
    stt: Mapping[str, SttChoice]
    tts: TextToSpeech | None
    tts_mode: Literal["sentence", "whole"] = "sentence"
    turn_log_path: Path | None = None


@dataclass
class _Turn:
    """Mutable bookkeeping for one request."""

    clock: Clock
    timings: dict[str, float]
    fallbacks: list[str]
    usage: list[Usage]


async def run_turn(svc: VoiceServices, inp: TurnInput) -> AsyncIterator[dict[str, Any]]:
    t = _Turn(Clock(), {}, [], [])
    text, transcript = await _transcribe(svc, inp, t)
    yield transcript
    result: TurnResult | None = None
    if text:
        result = await svc.runner.run(inp.session_id, text)
        dumped = result.model_dump(mode="json")
        yield _understanding_event(dumped)
        yield _search_event(dumped)
        t.fallbacks += result.fallback_used
        t.usage += result.usage
        stages = dict(result.timings_ms)
        t.timings["pipeline"] = stages.pop("total", 0.0)
        t.timings.update(stages)
        sentences = _sentences(result, svc.tts_mode)
    else:
        sentences = [STT_FAILED_TEXT]
    async for event in _speak(svc, sentences, t):
        yield event
    t.timings["server_total"] = t.clock.ms()
    done = {
        "type": "done",
        "turn_id": uuid4().hex,
        "turn": result.turn if result else None,
        "response_text": result.response_text if result else STT_FAILED_TEXT,
        "verdict": result.verdict.model_dump(mode="json") if result else None,
        "fallback_used": t.fallbacks,
        "timings_ms": t.timings,
        "usage": [u.model_dump(mode="json") for u in t.usage],
    }
    _log_turn(svc, inp, transcript, result, done)
    yield done


async def _transcribe(svc: VoiceServices, inp: TurnInput, t: _Turn) -> tuple[str, dict[str, Any]]:
    if inp.audio is None:
        text = (inp.text or "").strip()
        return text, _transcript_event(text, "typed", None, None, None)
    choice = svc.stt.get(inp.language) or svc.stt.get("en")
    if choice is None:
        log.warning("no STT configured for %s", inp.language)
        t.fallbacks.append("stt_unavailable")
        return "", _transcript_event("", "stt", None, None, None)
    t.fallbacks += choice.fallbacks
    try:
        with timed() as sw:
            tr = await choice.stt.transcribe(inp.audio, inp.filename, inp.content_type)
    except ProviderError as exc:
        log.warning("stt failed: %s", exc)
        t.timings["stt"] = sw.ms
        t.fallbacks.append("stt_error")
        return "", _transcript_event("", "stt", choice.stt.name, None, None)
    t.timings["stt"] = sw.ms
    seconds = tr.audio_seconds or inp.audio_seconds
    t.usage.append(Usage(provider=f"{tr.provider}-stt", audio_seconds=seconds))
    if not tr.text:
        log.warning("stt returned an empty transcript (%s)", tr.provider)
        t.fallbacks.append("stt_empty")
    return tr.text, _transcript_event(tr.text, "stt", tr.provider, tr.confidence, tr.language)


async def _speak(
    svc: VoiceServices, sentences: list[str], t: _Turn
) -> AsyncIterator[dict[str, Any]]:
    tts = svc.tts
    if tts is None:
        t.fallbacks.append("tts_client")
    tts_ms = 0.0
    for index, text in enumerate(sentences):
        audio: bytes | None = None
        if tts is not None:
            try:
                with timed() as sw:
                    audio = await tts.synthesize(text)
                tts_ms += sw.ms
                t.usage.append(Usage(provider=f"{tts.name}-tts", characters=len(text)))
            except ProviderError as exc:  # H5: the browser speaks the rest of this turn
                log.warning("tts failed, switching to browser speech: %s", exc)
                t.fallbacks.append("tts_client")
                tts = None
        if index == 0:
            t.timings["first_audio_ready"] = t.clock.ms()
        yield {
            "type": "sentence",
            "index": index,
            "text": text,
            "audio_b64": base64.b64encode(audio).decode("ascii") if audio else None,
            "tts": "server" if audio else "client",
        }
    if tts_ms:
        t.timings["tts"] = round(tts_ms, 1)


def _sentences(result: TurnResult, mode: str) -> list[str]:
    if mode == "whole":
        return [result.response_text]
    return result.response.sentences() or [result.response_text]


def _transcript_event(
    text: str, source: str, provider: str | None, confidence: float | None, language: str | None
) -> dict[str, Any]:
    return {
        "type": "transcript",
        "text": text,
        "source": source,
        "provider": provider,
        "confidence": confidence,
        "language": language,
    }


def _understanding_event(d: dict[str, Any]) -> dict[str, Any]:
    keys = ("turn", "intent", "language", "route", "slots", "slot_diff", "pending_confirmation")
    return {"type": "understanding", **{k: d[k] for k in keys}}


def _search_event(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "search",
        "filters": d["filters"],
        "sql": d["sql"],
        "params": d["sql_params"],
        "results": d["results"],
        "relaxation": d["relaxation"],
    }


def _log_turn(
    svc: VoiceServices,
    inp: TurnInput,
    transcript: dict[str, Any],
    result: TurnResult | None,
    done: dict[str, Any],
) -> None:
    """N5: one record per API turn, richer than the runner's own (adds STT/TTS stages)."""
    if svc.turn_log_path is None:
        return
    record: dict[str, Any] = result.model_dump(mode="json") if result else {}
    record.update(
        turn_id=done["turn_id"],
        session_id=inp.session_id,
        input="audio" if inp.audio is not None else "typed",
        input_language=inp.language,
        transcript=transcript,
        tts_mode=svc.tts_mode,
        timings_ms=done["timings_ms"],
        fallback_used=done["fallback_used"],
        usage=done["usage"],
    )
    append_turn(svc.turn_log_path, record)
```

The understanding/search events copy `turn`, `intent`, `slots` etc. from `TurnResult.model_dump(mode="json")`, so the JSON shapes match the CLI and eval.

- [ ] **Step 5: Run checks**

Run: `uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run mypy src`. Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add -A src tests
git commit -m "Add voice turn stream: STT, pipeline, sentence TTS with fallbacks, NDJSON events"
```

---

### Task 6: FastAPI app and server entry point

**Files:**
- Create: `src/voice_agent/api/app.py`, `src/voice_agent/api/services.py`, `src/voice_agent/api/__main__.py`
- Test: `tests/unit/api/test_app.py`

**Interfaces:**
- Consumes: `run_turn`, `TurnInput`, `VoiceServices` (Task 5); `make_stt`, `make_tts`, `open_http_client` (Tasks 2–3); `build_runtime`; `aio.run`.
- Produces:
  - `create_app(settings: Settings, services: ServicesFactory) -> FastAPI`, where `ServicesFactory = Callable[[Settings], AbstractAsyncContextManager[VoiceServices]]`.
  - `real_services(settings)`.
  - `python -m voice_agent.api`.
- Routes (architecture §10):
  - `POST /api/session`
  - `POST /api/turn` (multipart: `session_id`, optional `text`, optional `audio`, `language` = `en`|`hi-en`, `audio_seconds`)
  - `POST /api/turn/{turn_id}/client-timings`
  - `GET /api/session/{id}/state`
  - `GET /api/health`

- [ ] **Step 1: Write failing tests** in `tests/unit/api/test_app.py`:

```python
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.fakes import FakeSTT, FakeTTS
from tests.unit.api.test_stream import FakeRunner
from voice_agent.api.app import create_app
from voice_agent.api.stream import VoiceServices
from voice_agent.config import Settings
from voice_agent.domain.ports import SttChoice


def _app(tmp_path: Path) -> TestClient:
    settings = Settings(_env_file=None, client_timings_path=tmp_path / "ct.jsonl")  # type: ignore[call-arg]

    @asynccontextmanager
    async def services(_: Settings) -> AsyncIterator[VoiceServices]:
        yield VoiceServices(
            runner=FakeRunner(), stt={"en": SttChoice(FakeSTT("Tata Ace in Pune"))}, tts=FakeTTS()
        )

    return TestClient(create_app(settings, services))


def _lines(body: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def test_session_then_typed_turn_streams_ndjson(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        sid = client.post("/api/session").json()["session_id"]
        resp = client.post("/api/turn", data={"session_id": sid, "text": "Tata Ace in Pune"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/x-ndjson")
        events = _lines(resp.text)
        assert events[0]["type"] == "transcript" and events[-1]["type"] == "done"


def test_audio_turn(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        files = {"audio": ("speech.webm", b"webm-bytes", "audio/webm")}
        resp = client.post("/api/turn", data={"session_id": "s1", "language": "en"}, files=files)
        assert _lines(resp.text)[0]["text"] == "Tata Ace in Pune"


def test_turn_without_audio_or_text_is_400(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        assert client.post("/api/turn", data={"session_id": "s1", "text": "  "}).status_code == 400


def test_bad_language_is_422(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        resp = client.post("/api/turn", data={"session_id": "s", "text": "x", "language": "fr"})
        assert resp.status_code == 422


def test_client_timings_are_logged(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        body = {"t_speech_end": 1000.0, "t_first_audio": 3500.0}
        assert client.post("/api/turn/abc/client-timings", json=body).status_code == 204
    record = json.loads((tmp_path / "ct.jsonl").read_text(encoding="utf-8"))
    assert record == {
        "turn_id": "abc",
        "t_speech_end": 1000.0,
        "t_first_audio": 3500.0,
        "speech_end_to_first_audio_ms": 2500.0,
    }


def test_state_and_health(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        assert client.get("/api/session/s9/state").json() == {"session_id": "s9"}
        health = client.get("/api/health").json()
        assert health["ok"] is True and health["stt"] == {"en": "fake-stt"}
        assert health["tts"] == "fake-tts" and health["tts_mode"] == "sentence"
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/unit/api/test_app.py -q`. Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`src/voice_agent/api/app.py`:

```python
"""FastAPI layer (architecture §10). Thin on purpose: parse the request, stream run_turn's events."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from voice_agent.api.stream import TurnInput, VoiceServices, run_turn
from voice_agent.config import Settings
from voice_agent.telemetry.turnlog import append_turn

ServicesFactory = Callable[[Settings], AbstractAsyncContextManager[VoiceServices]]


class ClientTimings(BaseModel):
    """Browser stamps, epoch ms (J4). t_speech_end is the button release (or typed submit)."""

    t_speech_end: float | None = None
    t_first_audio: float


def create_app(settings: Settings, services: ServicesFactory) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with services(settings) as svc:
            app.state.svc = svc
            yield

    app = FastAPI(title="Vyngo voice vehicle search", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/api/session")
    async def new_session() -> dict[str, str]:
        return {"session_id": uuid4().hex[:12]}

    @app.post("/api/turn")
    async def turn(
        request: Request,
        session_id: str = Form(...),
        text: str | None = Form(None),
        language: Literal["en", "hi-en"] = Form("en"),
        audio_seconds: float = Form(0.0),
        audio: UploadFile | None = File(None),
    ) -> StreamingResponse:
        if audio is None and not (text and text.strip()):
            raise HTTPException(status_code=400, detail="send audio or text")
        inp = TurnInput(
            session_id=session_id,
            text=text,
            audio=await audio.read() if audio is not None else None,
            filename=(audio.filename if audio is not None else None) or "speech.webm",
            content_type=(audio.content_type if audio is not None else None) or "audio/webm",
            language=language,
            audio_seconds=audio_seconds,
        )
        events = run_turn(request.app.state.svc, inp)
        return StreamingResponse(_ndjson(events), media_type="application/x-ndjson")

    @app.post("/api/turn/{turn_id}/client-timings", status_code=204)
    async def client_timings(turn_id: str, body: ClientTimings) -> Response:
        first_audio = None
        if body.t_speech_end is not None:
            first_audio = round(body.t_first_audio - body.t_speech_end, 1)
        record = {"turn_id": turn_id, **body.model_dump(), "speech_end_to_first_audio_ms": first_audio}
        append_turn(settings.client_timings_path, record)
        return Response(status_code=204)

    @app.get("/api/session/{session_id}/state")
    async def session_state(session_id: str, request: Request) -> dict[str, Any]:
        state: dict[str, Any] = await request.app.state.svc.runner.state(session_id)
        return state

    @app.get("/api/health")
    async def health(request: Request) -> dict[str, Any]:
        svc: VoiceServices = request.app.state.svc  # the lifespan opened the DB, so it is up
        return {
            "ok": True,
            "llm": settings.llm_provider,
            "stt": {lang: choice.stt.name for lang, choice in svc.stt.items()},
            "tts": svc.tts.name if svc.tts is not None else "client",
            "tts_mode": svc.tts_mode,
        }

    return app


async def _ndjson(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[bytes]:
    async for event in events:
        yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
```

`src/voice_agent/api/services.py`:

```python
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
```

`src/voice_agent/api/__main__.py`:

```python
"""`uv run python -m voice_agent.api`: serve the API (Selector loop on Windows via aio.run)."""

import logging

import uvicorn

from voice_agent.aio import run
from voice_agent.api.app import create_app
from voice_agent.api.services import real_services
from voice_agent.config import get_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    app = create_app(settings, real_services)
    config = uvicorn.Config(app, host=settings.api_host, port=settings.api_port, loop="none")
    run(uvicorn.Server(config).serve())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run checks**

Run: `uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run mypy src`. Expected: pass.

- [ ] **Step 5: Live smoke** (needs Postgres on 5433 and the Groq key)

Run in the background: `uv run python -m voice_agent.api`. Then:

```bash
curl -s localhost:8000/api/health
curl -s -X POST localhost:8000/api/turn -F session_id=smoke1 -F "text=Diesel pickup in Mumbai under 6 lakh"
```

Expected: the health JSON, then NDJSON lines ending in a `done` event with `fallback_used` (it contains `tts_client` when no ElevenLabs key is set). Stop the server afterwards. If the DB is down, note it in the report and continue.

- [ ] **Step 6: Commit**

```bash
git add -A src tests
git commit -m "Add FastAPI app with NDJSON turn stream, client timings, state and health"
```

---

### Task 7: UI scaffold, API client, recorder and audio queue

**Files (all new under `ui/`):** `package.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js`, `index.html`, `src/main.tsx`, `src/vite-env.d.ts`, `src/api/types.ts`, `src/api/client.ts`, `src/audio/useRecorder.ts`, `src/audio/AudioQueue.ts`, `src/styles.css`, `src/App.tsx` (placeholder; Task 8 replaces it), and `package-lock.json` (generated by `npm install`).

**Interfaces:**
- Consumes: the NDJSON event shapes from Task 5 and the routes from Task 6.
- Produces:
  - `types.ts`: all event types.
  - `client.ts`: `createSession()`, `sendTurn(form, onEvent)`, `postClientTimings(turnId, body)`.
  - `useRecorder()`: `{recording, start, stop}`.
  - `AudioQueue`: `enqueue(SentenceEvent)`, `onFirstPlay`, `reset()`.

- [ ] **Step 1: Create the files**

`ui/package.json`:

```json
{
  "name": "voice-agent-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@eslint/js": "9.17.0",
    "@types/react": "18.3.18",
    "@types/react-dom": "18.3.5",
    "@vitejs/plugin-react": "4.3.4",
    "eslint": "9.17.0",
    "eslint-plugin-react-hooks": "5.1.0",
    "globals": "15.14.0",
    "typescript": "5.7.2",
    "typescript-eslint": "8.18.2",
    "vite": "5.4.11"
  }
}
```

`ui/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["src", "vite.config.ts"]
}
```

`ui/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: the API runs on :8000 (`uv run python -m voice_agent.api`); in Docker nginx proxies /api.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
```

`ui/eslint.config.js`:

```js
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  },
);
```

`ui/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Vyngo Voice Search</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`ui/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
```

`ui/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`ui/src/api/types.ts` (mirrors `api/stream.py`; keep the two in sync):

```ts
// Mirrors the NDJSON events in src/voice_agent/api/stream.py (architecture §10).
export type Language = "en" | "hi-en";

export interface Listing {
  listing_id: string;
  make: string;
  model: string;
  variant: string;
  body_type: string;
  fuel: string;
  year: number;
  price_inr: number;
  km_driven: number;
  payload_kg: number;
  city: string;
  owners: number;
  seller_type: string;
  papers_verified: boolean;
}

export interface ScoredListing {
  listing: Listing;
  rank: number;
  score: number;
  contributions: Record<string, number>;
}

export interface PendingConfirmation {
  slot: string;
  raw: string;
  candidate: string;
  score: number;
}

export interface Relaxation {
  slot: string;
  old: unknown;
  new: unknown;
  count: number;
}

export interface Usage {
  provider: string;
  input_tokens: number;
  output_tokens: number;
  audio_seconds: number;
  characters: number;
}

export interface Verdict {
  ok: boolean;
  source: "llm" | "template";
  violations: { where: string; kind: string; detail: string }[];
}

export interface TranscriptEvent {
  type: "transcript";
  text: string;
  source: "stt" | "typed";
  provider: string | null;
  confidence: number | null;
  language: string | null;
}

export interface UnderstandingEvent {
  type: "understanding";
  turn: number;
  intent: string | null;
  language: string | null;
  route: string;
  slots: Record<string, unknown>;
  slot_diff: Record<string, [unknown, unknown]>;
  pending_confirmation: PendingConfirmation | null;
}

export interface SearchEvent {
  type: "search";
  filters: Record<string, unknown> | null;
  sql: string | null;
  params: Record<string, unknown>;
  results: ScoredListing[];
  relaxation: Relaxation | null;
}

export interface SentenceEvent {
  type: "sentence";
  index: number;
  text: string;
  audio_b64: string | null;
  tts: "server" | "client";
}

export interface DoneEvent {
  type: "done";
  turn_id: string;
  turn: number | null;
  response_text: string;
  verdict: Verdict | null;
  fallback_used: string[];
  timings_ms: Record<string, number>;
  usage: Usage[];
}

export type TurnEvent =
  | TranscriptEvent
  | UnderstandingEvent
  | SearchEvent
  | SentenceEvent
  | DoneEvent;
```

`ui/src/api/client.ts`:

```ts
import type { TurnEvent } from "./types";

export async function createSession(): Promise<string> {
  const res = await fetch("/api/session", { method: "POST" });
  if (!res.ok) throw new Error(`session: HTTP ${res.status}`);
  return ((await res.json()) as { session_id: string }).session_id;
}

/** POST one turn and call onEvent for each NDJSON line as it arrives. */
export async function sendTurn(form: FormData, onEvent: (e: TurnEvent) => void): Promise<void> {
  const res = await fetch("/api/turn", { method: "POST", body: form });
  if (!res.ok || !res.body) throw new Error(`turn: HTTP ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) onEvent(JSON.parse(line) as TurnEvent);
      newline = buffer.indexOf("\n");
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as TurnEvent);
}

export async function postClientTimings(
  turnId: string,
  body: { t_speech_end: number | null; t_first_audio: number },
): Promise<void> {
  await fetch(`/api/turn/${turnId}/client-timings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
```

`ui/src/audio/useRecorder.ts`:

```ts
import { useCallback, useRef, useState } from "react";

export interface Recording {
  blob: Blob;
  durationMs: number;
  speechEndMs: number; // epoch ms at button release (J4 t_speech_end)
}

/** Push-to-talk recorder (C3): start on press, stop on release. */
export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const startedAt = useRef(0);

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunks.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.current.push(e.data);
    };
    rec.start();
    recorder.current = rec;
    startedAt.current = Date.now();
    setRecording(true);
  }, []);

  const stop = useCallback(
    () =>
      new Promise<Recording | null>((resolve) => {
        const rec = recorder.current;
        if (!rec) return resolve(null);
        const speechEndMs = Date.now();
        rec.onstop = () => {
          rec.stream.getTracks().forEach((t) => t.stop());
          recorder.current = null;
          setRecording(false);
          const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
          resolve({ blob, durationMs: speechEndMs - startedAt.current, speechEndMs });
        };
        rec.stop();
      }),
    [],
  );

  return { recording, start, stop };
}
```

`ui/src/audio/AudioQueue.ts`:

```ts
import type { SentenceEvent } from "../api/types";

/** Plays sentences in order: server MP3 when present, browser speech otherwise (H5). */
export class AudioQueue {
  private chain: Promise<void> = Promise.resolve();
  private generation = 0;
  private firstPlayed = false;
  onFirstPlay: ((epochMs: number) => void) | null = null;
  lang = "en-IN";

  reset(): void {
    this.generation += 1;
    this.chain = Promise.resolve();
    this.firstPlayed = false;
    window.speechSynthesis?.cancel();
  }

  enqueue(sentence: SentenceEvent): void {
    const gen = this.generation;
    this.chain = this.chain.then(() => (gen === this.generation ? this.play(sentence) : undefined));
  }

  private markFirst(): void {
    if (!this.firstPlayed) {
      this.firstPlayed = true;
      this.onFirstPlay?.(Date.now());
    }
  }

  private play(s: SentenceEvent): Promise<void> {
    return new Promise((resolve) => {
      if (s.audio_b64) {
        const audio = new Audio(`data:audio/mpeg;base64,${s.audio_b64}`);
        audio.onplaying = () => this.markFirst();
        audio.onended = () => resolve();
        audio.onerror = () => resolve();
        audio.play().catch(() => resolve());
        return;
      }
      if (!window.speechSynthesis) return resolve();
      const u = new SpeechSynthesisUtterance(s.text.replace(/₹/g, "rupees "));
      u.lang = this.lang;
      u.onstart = () => this.markFirst();
      u.onend = () => resolve();
      u.onerror = () => resolve();
      window.speechSynthesis.speak(u);
    });
  }
}
```

`ui/src/styles.css`:

```css
:root { font-family: system-ui, sans-serif; color: #1d232a; background: #f4f5f7; }
body { margin: 0; }
.app { max-width: 1200px; margin: 0 auto; padding: 16px; display: grid; gap: 12px; }
.controls { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.ptt { padding: 14px 22px; font-size: 16px; border-radius: 999px; border: 0; background: #1f6feb; color: white; cursor: pointer; user-select: none; }
.ptt.recording { background: #d1242f; }
.ptt:disabled { background: #8c959f; }
input[type="text"] { flex: 1; min-width: 200px; padding: 10px; font-size: 15px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 12px; }
.panel { background: white; border-radius: 8px; padding: 12px; box-shadow: 0 1px 2px rgba(0,0,0,.08); overflow-x: auto; }
.panel h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: #57606a; margin: 0 0 8px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
td, th { text-align: left; padding: 3px 6px; border-bottom: 1px solid #eaeef2; vertical-align: top; }
pre { white-space: pre-wrap; font-size: 12px; margin: 0; }
.diff { color: #9a6700; font-weight: 600; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; margin: 2px; background: #fff8c5; }
.badge.ok { background: #dafbe1; }
.badge.bad { background: #ffebe9; }
.turn { margin: 6px 0; }
.turn .you { color: #57606a; }
.error { color: #d1242f; }
```

`ui/src/App.tsx` (placeholder, so build and lint pass; Task 8 replaces it):

```tsx
export default function App() {
  return <div className="app">Vyngo voice search</div>;
}
```

- [ ] **Step 2: Install and verify**

```bash
cd ui && npm install && npm run lint && npm run build
```

Expected: lint passes and `dist/` is built. Add `ui/node_modules/` and `ui/dist/` to the root `.gitignore`. If a pinned version fails to resolve, use the nearest existing patch of the same minor version, and say so in the report.

- [ ] **Step 3: Commit**

```bash
git add -A ui .gitignore
git commit -m "Add UI scaffold: Vite React TS, NDJSON client, push-to-talk recorder, audio queue"
```

---

### Task 8: UI panels, App and CI job

**Files:**
- Create: `ui/src/panels/Conversation.tsx`, `ui/src/panels/SlotsPanel.tsx`, `ui/src/panels/SqlPanel.tsx`, `ui/src/panels/ResultsPanel.tsx`, `ui/src/panels/LatencyPanel.tsx`, `ui/src/panels/VerdictPanel.tsx`
- Replace: `ui/src/App.tsx`
- Modify: `.github/workflows/ci.yml` (add a `ui` job)

**Interfaces:**
- Consumes: everything from Task 7.
- Produces the panels (decisions K1b): PTT, playback, transcript, slots + diff, executed SQL, top 3 with score breakdown, latency table, typed fallback, validator verdict and fallback badges, and an EN/Hinglish toggle.

- [ ] **Step 1: Create the panels**

`ui/src/panels/Conversation.tsx`:

```tsx
export interface ChatTurn {
  you: string;
  source: "stt" | "typed";
  bot: string;
}

export function Conversation({ turns }: { turns: ChatTurn[] }) {
  return (
    <section className="panel">
      <h2>Conversation</h2>
      {turns.length === 0 && <p>Hold the button and speak, or type below.</p>}
      {turns.map((t, i) => (
        <div className="turn" key={i}>
          <div className="you">
            you{t.source === "stt" ? " (voice)" : ""}: {t.you || "…"}
          </div>
          <div>bot: {t.bot}</div>
        </div>
      ))}
    </section>
  );
}
```

`ui/src/panels/SlotsPanel.tsx`:

```tsx
import type { UnderstandingEvent } from "../api/types";

export function SlotsPanel({ u }: { u: UnderstandingEvent | null }) {
  return (
    <section className="panel">
      <h2>Active slots</h2>
      {!u ? (
        <p>None yet.</p>
      ) : (
        <>
          <p>
            intent <b>{u.intent ?? "?"}</b> · route <b>{u.route}</b> · language <b>{u.language ?? "?"}</b>
          </p>
          <table>
            <tbody>
              {Object.entries(u.slots).map(([k, v]) => (
                <tr key={k} className={k in u.slot_diff ? "diff" : undefined}>
                  <td>{k}</td>
                  <td>{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {Object.keys(u.slot_diff).length > 0 && (
            <p className="diff">
              changed:{" "}
              {Object.entries(u.slot_diff)
                .map(([k, [a, b]]) => `${k}: ${String(a)} → ${String(b)}`)
                .join(", ")}
            </p>
          )}
          {u.pending_confirmation && (
            <p>
              waiting for yes/no: {u.pending_confirmation.slot} = {u.pending_confirmation.candidate}?
            </p>
          )}
        </>
      )}
    </section>
  );
}
```

`ui/src/panels/SqlPanel.tsx`:

```tsx
import type { SearchEvent } from "../api/types";

export function SqlPanel({ s }: { s: SearchEvent | null }) {
  return (
    <section className="panel">
      <h2>Executed filters &amp; SQL</h2>
      {!s?.sql ? (
        <p>No search this turn.</p>
      ) : (
        <>
          <pre>{JSON.stringify(s.filters, null, 1)}</pre>
          <pre>{s.sql}</pre>
          <pre>params: {JSON.stringify(s.params)}</pre>
        </>
      )}
    </section>
  );
}
```

`ui/src/panels/ResultsPanel.tsx`:

```tsx
import type { SearchEvent } from "../api/types";

const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export function ResultsPanel({ s }: { s: SearchEvent | null }) {
  return (
    <section className="panel">
      <h2>Top results (score breakdown)</h2>
      {!s && <p>No search yet.</p>}
      {s && s.results.length === 0 && (
        <p>
          No matches.
          {s.relaxation &&
            ` Suggested: ${s.relaxation.slot} ${String(s.relaxation.old)} → ${String(s.relaxation.new)} (${s.relaxation.count} found)`}
        </p>
      )}
      {s?.results.map((r) => (
        <div key={r.listing.listing_id} className="turn">
          <b>
            #{r.rank} {r.listing.year} {r.listing.make} {r.listing.model}
          </b>{" "}
          · {r.listing.city} · {inr(r.listing.price_inr)} · {r.listing.km_driven.toLocaleString("en-IN")} km ·{" "}
          {r.listing.payload_kg} kg · score {r.score.toFixed(3)}
          <table>
            <tbody>
              {Object.entries(r.contributions).map(([k, v]) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td>{v.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
}
```

`ui/src/panels/LatencyPanel.tsx`:

```tsx
const ORDER = ["stt", "nlu", "search", "rank", "relax", "compose", "pipeline", "first_audio_ready", "tts", "server_total"];

export function LatencyPanel({ timings, firstAudioMs }: { timings: Record<string, number>; firstAudioMs: number | null }) {
  const keys = [...ORDER.filter((k) => k in timings), ...Object.keys(timings).filter((k) => !ORDER.includes(k))];
  return (
    <section className="panel">
      <h2>Latency (ms)</h2>
      <table>
        <tbody>
          {keys.map((k) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{Math.round(timings[k])}</td>
            </tr>
          ))}
          <tr>
            <td>
              <b>speech end → first audio (browser)</b>
            </td>
            <td>
              <b>{firstAudioMs === null ? "–" : Math.round(firstAudioMs)}</b>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}
```

`ui/src/panels/VerdictPanel.tsx`:

```tsx
import type { DoneEvent, TranscriptEvent } from "../api/types";

export function VerdictPanel({ done, transcript }: { done: DoneEvent | null; transcript: TranscriptEvent | null }) {
  return (
    <section className="panel">
      <h2>Validator &amp; fallbacks</h2>
      {transcript?.source === "stt" && (
        <p>
          STT: {transcript.provider ?? "none"}
          {transcript.confidence !== null && ` · confidence ${transcript.confidence}`}
        </p>
      )}
      {!done ? (
        <p>–</p>
      ) : (
        <>
          {done.verdict && (
            <span className={`badge ${done.verdict.ok ? "ok" : "bad"}`}>
              validator: {done.verdict.ok ? "pass" : "fail"} ({done.verdict.source})
            </span>
          )}
          {done.fallback_used.map((f, i) => (
            <span className="badge" key={i}>
              {f}
            </span>
          ))}
          {done.verdict?.violations.map((v, i) => (
            <div key={i} className="error">
              {v.kind}: {v.detail}
            </div>
          ))}
        </>
      )}
    </section>
  );
}
```

`ui/src/App.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { createSession, postClientTimings, sendTurn } from "./api/client";
import type { DoneEvent, Language, SearchEvent, TranscriptEvent, TurnEvent, UnderstandingEvent } from "./api/types";
import { AudioQueue } from "./audio/AudioQueue";
import { useRecorder } from "./audio/useRecorder";
import { Conversation, type ChatTurn } from "./panels/Conversation";
import { LatencyPanel } from "./panels/LatencyPanel";
import { ResultsPanel } from "./panels/ResultsPanel";
import { SlotsPanel } from "./panels/SlotsPanel";
import { SqlPanel } from "./panels/SqlPanel";
import { VerdictPanel } from "./panels/VerdictPanel";

interface Pending {
  speechEnd: number;
  turnId: string | null;
  firstAudio: number | null;
  posted: boolean;
}

export default function App() {
  const [session, setSession] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language>("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [transcript, setTranscript] = useState<TranscriptEvent | null>(null);
  const [understanding, setUnderstanding] = useState<UnderstandingEvent | null>(null);
  const [search, setSearch] = useState<SearchEvent | null>(null);
  const [done, setDone] = useState<DoneEvent | null>(null);
  const [firstAudioMs, setFirstAudioMs] = useState<number | null>(null);
  const queue = useRef(new AudioQueue());
  const pending = useRef<Pending | null>(null);
  const { recording, start, stop } = useRecorder();

  useEffect(() => {
    createSession().then(setSession, (e: Error) => setError(e.message));
  }, []);

  // Post browser timings once both the turn id (done event) and first playback are known (J4).
  const maybePostTimings = () => {
    const p = pending.current;
    if (!p || p.posted || !p.turnId || p.firstAudio === null) return;
    p.posted = true;
    setFirstAudioMs(p.firstAudio - p.speechEnd);
    void postClientTimings(p.turnId, { t_speech_end: p.speechEnd, t_first_audio: p.firstAudio });
  };

  const onEvent = (e: TurnEvent) => {
    switch (e.type) {
      case "transcript":
        setTranscript(e);
        setTurns((t) => [...t, { you: e.text, source: e.source, bot: "" }]);
        break;
      case "understanding":
        setUnderstanding(e);
        break;
      case "search":
        setSearch(e);
        break;
      case "sentence":
        queue.current.enqueue(e);
        setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, bot: `${x.bot} ${e.text}`.trim() } : x)));
        break;
      case "done":
        setDone(e);
        if (pending.current) pending.current.turnId = e.turn_id;
        maybePostTimings();
        break;
    }
  };

  const runTurn = async (form: FormData, speechEnd: number) => {
    if (!session) return;
    form.append("session_id", session);
    form.append("language", language);
    queue.current.reset();
    queue.current.lang = language === "hi-en" ? "hi-IN" : "en-IN";
    pending.current = { speechEnd, turnId: null, firstAudio: null, posted: false };
    queue.current.onFirstPlay = (ms) => {
      if (pending.current) pending.current.firstAudio = ms;
      maybePostTimings();
    };
    setBusy(true);
    setError(null);
    setSearch(null);
    setFirstAudioMs(null);
    try {
      await sendTurn(form, onEvent);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onPress = async () => {
    if (busy || recording) return;
    try {
      await start();
    } catch {
      setError("Microphone unavailable: type your request instead.");
    }
  };

  const onRelease = async () => {
    const rec = await stop();
    if (!rec || rec.blob.size === 0) return;
    const form = new FormData();
    form.append("audio", rec.blob, "speech.webm");
    form.append("audio_seconds", String(rec.durationMs / 1000));
    await runTurn(form, rec.speechEndMs);
  };

  const onType = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const text = typed.trim();
    if (!text || busy) return;
    setTyped("");
    const form = new FormData();
    form.append("text", text);
    await runTurn(form, Date.now());
  };

  return (
    <div className="app">
      <h1>Vyngo voice vehicle search</h1>
      <div className="controls">
        <button
          className={`ptt ${recording ? "recording" : ""}`}
          disabled={!session || busy}
          onPointerDown={onPress}
          onPointerUp={onRelease}
          onPointerLeave={() => recording && onRelease()}
        >
          {recording ? "Listening… release to send" : busy ? "Working…" : "Hold to talk"}
        </button>
        <select value={language} onChange={(e) => setLanguage(e.target.value as Language)}>
          <option value="en">English</option>
          <option value="hi-en">Hinglish</option>
        </select>
        <form onSubmit={onType} style={{ display: "flex", flex: 1, gap: 8 }}>
          <input type="text" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="…or type here" />
          <button type="submit" disabled={!session || busy}>
            Send
          </button>
        </form>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="grid">
        <Conversation turns={turns} />
        <SlotsPanel u={understanding} />
        <ResultsPanel s={search} />
        <SqlPanel s={search} />
        <LatencyPanel timings={done?.timings_ms ?? {}} firstAudioMs={firstAudioMs} />
        <VerdictPanel done={done} transcript={transcript} />
      </div>
    </div>
  );
}
```

If `react-hooks/exhaustive-deps` or the TS `React.FormEvent` namespace complains, import `type FormEvent` from `react` and keep the logic identical.

- [ ] **Step 2: Add the CI job.** Append to the `jobs:` block of `.github/workflows/ci.yml`:

```yaml
  ui:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ui
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: ui/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run build
```

- [ ] **Step 3: Verify**

Run: `cd ui && npm run lint && npm run build`. Expected: pass.

Optional live check: run the API (Task 6 step 5) and `npm run dev`, open http://localhost:5173, then type "Diesel pickup in Mumbai under 6 lakh". The panels fill in and speech plays.

- [ ] **Step 4: Commit**

```bash
git add -A ui .github
git commit -m "Add UI panels: conversation, slots and diff, SQL, scored results, latency, verdict; UI CI job"
```

---

### Task 9: Docker (app + ui + db) with healthchecks

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `ui/Dockerfile`, `ui/nginx.conf`, `ui/.dockerignore`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `python -m voice_agent.api` (Task 6), `ui` build (Task 8).
- Produces: `docker compose up --build`, with UI on http://localhost:5173, API on :8000 and DB on host :5433.

- [ ] **Step 1: Create the files**

`Dockerfile`:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY config ./config
COPY data ./data
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" API_HOST=0.0.0.0 API_PORT=8000
EXPOSE 8000
CMD ["python", "-m", "voice_agent.api"]
```

`.dockerignore`:

```
.git
.venv
.env
logs
.superpowers
**/__pycache__
.mypy_cache
.ruff_cache
.pytest_cache
ui
eval/audio
docs
tests
```

`ui/.dockerignore`:

```
node_modules
dist
```

`ui/Dockerfile`:

```dockerfile
FROM node:22-alpine AS build
WORKDIR /ui
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ui/dist /usr/share/nginx/html
```

`ui/nginx.conf`:

```nginx
server {
  listen 80;
  root /usr/share/nginx/html;

  location /api/ {
    proxy_pass http://app:8000;
    proxy_http_version 1.1;
    proxy_buffering off;          # NDJSON events must reach the browser as they are written
    proxy_read_timeout 120s;
    client_max_body_size 10m;     # push-to-talk clips
  }

  location / {
    try_files $uri /index.html;
  }
}
```

`docker-compose.yml` (whole file):

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: voice
      POSTGRES_PASSWORD: voice
      POSTGRES_DB: voice
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U voice -d voice"]
      interval: 2s
      timeout: 3s
      retries: 30
    volumes:
      - pgdata:/var/lib/postgresql/data

  app:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgresql://voice:voice@db:5432/voice
      CORS_ORIGINS: http://localhost:5173
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 5s
      timeout: 3s
      retries: 30
    volumes:
      - ./logs:/app/logs

  ui:
    build: ./ui
    ports:
      - "5173:80"
    depends_on:
      app:
        condition: service_healthy

volumes:
  pgdata: {}
```

- [ ] **Step 2: Build and run** (Docker runs in WSL on this machine)

```bash
wsl -e bash -lc "cd /mnt/d/Job/portfolio_projects/voice-agent && docker compose up --build -d && docker compose ps"
curl -s localhost:8000/api/health
curl -s -X POST localhost:5173/api/turn -F session_id=docker1 -F "text=Tata Ace in Pune"
```

Expected:
- All three services report healthy.
- Health returns JSON.
- The turn through nginx streams NDJSON ending in `done`.

If WSL ports aren't reachable from Windows, run the curls inside WSL instead. Leave the stack running only if it was running before; otherwise run `docker compose stop app ui`. If Docker is unavailable to the subagent, report DONE_WITH_CONCERNS with the exact error. The controller will run the check.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile .dockerignore ui/Dockerfile ui/nginx.conf ui/.dockerignore docker-compose.yml
git commit -m "Add Docker images for app and ui; compose with healthchecks and nginx /api proxy"
```

---

### Task 10: Hinglish eval cases and fixes

**Files:**
- Modify: `eval/cases.yaml` (append 7 cases), `eval/run_eval.py` (`--category`)
- Modify (only if the live run shows a need): `src/voice_agent/understanding/extractor.py` prompt, `src/voice_agent/response/composer.py` prompt, `src/voice_agent/response/validator.py`. Add unit tests for any change.
- Test: `tests/unit/test_eval_checks.py`

**Interfaces:**
- Consumes: the existing eval harness.
- Produces: the `hinglish` category with ≥90% passing (≥7/7 is the goal; 6/7 meets the bar), and `run_eval.py --category <name>`. With `--category`, it runs only that category, prints the summary, and writes **nothing** to `eval/results/`.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_eval_checks.py`:

```python
def test_select_cases_by_category() -> None:
    select_cases = _load_run_eval().select_cases  # use the file's existing importlib loader helper

    cases = [{"id": "a", "category": "hinglish"}, {"id": "b", "category": "english"}]
    assert [c["id"] for c in select_cases(cases, "hinglish")] == ["a"]
    assert select_cases(cases, None) == cases
```

`eval/` is not a package: the file already loads `eval/run_eval.py` with `importlib`. Reuse that helper (rename `_load_run_eval` above to whatever the file calls it).

- [ ] **Step 2: Implement `--category`** in `eval/run_eval.py`:

```python
def select_cases(cases: list[dict[str, Any]], category: str | None) -> list[dict[str, Any]]:
    return [c for c in cases if c["category"] == category] if category else cases
```

In `main()`:
- add `parser.add_argument("--category", default=None, help="run one category; results files are not written")`;
- apply `cases = select_cases(cases, args.category)`;
- when `args.category` is set, print the summary and `return 0 if pass_rate(result) >= PASS_TARGET else 1` **before** writing `latest.*`.

- [ ] **Step 3: Append the cases** to `eval/cases.yaml`:

```yaml
- id: hi-01
  category: hinglish
  turns:
    - say: "Pune mein paanch lakh tak ka chhota truck chahiye"
      expect_filters: {budget_max: 500000, body_type: mini_truck, city: pune}
- id: hi-02
  category: hinglish
  turns:
    - say: "Mumbai mein diesel pickup dikhao"
      expect_filters: {fuel: diesel, body_type: pickup, city: mumbai}
- id: hi-03
  category: hinglish
  turns:
    - say: "Delhi mein CNG wali gaadi chahiye, chaar lakh se kam"
      expect_filters: {fuel: cng, city: delhi, budget_max: 400000}
- id: hi-04
  category: hinglish
  turns:
    - say: "Tata Ace chahiye Pune mein, paanch lakh ke andar"
      expect_filters: {make: Tata, model: Ace, city: pune, budget_max: 500000}
- id: hi-05
  category: hinglish
  turns:
    - say: "Chennai mein diesel mini truck jo pachaas hazaar km se kam chala ho"
      expect_filters: {fuel: diesel, body_type: mini_truck, max_km: 50000, city: chennai}
- id: hi-06
  category: hinglish
  turns:
    - say: "Jaipur mein diesel pickup chahiye, chhe lakh tak"
      expect_filters: {fuel: diesel, body_type: pickup, city: jaipur, budget_max: 600000}
    - say: "diesel nahi, CNG wala dikhao"
      expect_changed: [fuel]
- id: hi-07
  category: hinglish
  turns:
    - say: "Delhi mein diesel pickup dikhao"
      expect_filters: {fuel: diesel, body_type: pickup, city: delhi}
    - say: "doosre wale ka payload kitna hai?"
      expect_route: follow_up
      expect_followup_rank: 2
```

Before running, confirm each first turn returns ≥1 listing in the seeded catalog. Use a quick psql query or `PgCatalog.count`. Adjust a city or budget only when a case would otherwise be a zero-result case by accident, and note the change in the report.

- [ ] **Step 4: Run live**

Run: `uv run python eval/run_eval.py --category hinglish` (Postgres up, Groq key set; about 3–5 minutes).

For each failure:
- Find the cause: extractor (slots), parser (numbers), normaliser (aliases), composer or validator (first-try validation).
- Fix it within the hard rules, with a unit test for any deterministic change. Prompt-only changes need no unit test but must be described in the report.
- Never weaken a validator check to make a case pass.
- If a failure is LLM variance (passes on rerun with no change), record it under "Known risks" in `eval/results/known_failures.md` instead of "fixing" it.
- Stop after two fix-and-rerun cycles. Report what remains.

- [ ] **Step 5: Run checks**

Run: `uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run mypy src`. Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add -A eval src tests
git commit -m "Add 7 Hinglish eval cases and --category; fixes from the Hinglish run"
```

---

### Task 11: Audio eval subset (STT through the real pipeline)

**Files:**
- Create: `eval/audio/cases.yaml`, `eval/run_audio_eval.py`, `scripts/make_eval_audio.py`
- Test: `tests/unit/test_audio_eval.py`

**Interfaces:**
- Consumes: `GroqSTT`, `SarvamSTT`, `HINGLISH_PROMPT`, `open_http_client` (Task 2); `build_runtime`; `check_turn` from `eval/run_eval.py`.
- Produces:
  - `word_error_rate(ref: str, hyp: str) -> float` in `eval/run_audio_eval.py`.
  - A results file `eval/results/audio_latest.md`.
  - `scripts/make_eval_audio.py` (ElevenLabs → 16 kHz WAV, plus one noisy copy).

- [ ] **Step 1: Write the failing test** in `tests/unit/test_audio_eval.py`:

```python
import importlib
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
sys.path.insert(0, str(EVAL_DIR))  # eval/ is a script directory, not a package
audio_eval = importlib.import_module("run_audio_eval")
normalise, word_error_rate = audio_eval.normalise, audio_eval.word_error_rate


def test_wer_identical_is_zero() -> None:
    assert word_error_rate("tata ace in pune", "Tata Ace in Pune.") == 0.0


def test_wer_counts_substitution_and_deletion() -> None:
    assert word_error_rate("a b c d", "a x c") == 0.5


def test_normalise_strips_punctuation_and_case() -> None:
    assert normalise("Pune, 5 lakh!") == "pune 5 lakh"
```

- [ ] **Step 2: Implement**

`eval/audio/cases.yaml`:

```yaml
# Audio subset (J1). Clips live next to this file. `synthetic: true` marks ElevenLabs stand-ins
# (scripts/make_eval_audio.py); replace them with real recordings under the same names when you can.
- file: en-01.wav
  language: en
  synthetic: true
  say: "I need a small truck under 5 lakh in Pune"
  expect_filters: {budget_max: 500000, body_type: mini_truck, city: pune}
- file: en-02.wav
  language: en
  synthetic: true
  say: "Show me diesel pickups in Mumbai"
  expect_filters: {fuel: diesel, body_type: pickup, city: mumbai}
- file: en-03-noisy.wav
  language: en
  synthetic: true
  noisy: true
  say: "Any CNG vehicle in Delhi below 4 lakh"
  expect_filters: {fuel: cng, city: delhi, budget_max: 400000}
- file: hi-01.wav
  language: hi-en
  synthetic: true
  say: "Pune mein paanch lakh tak ka chhota truck chahiye"
  expect_filters: {budget_max: 500000, body_type: mini_truck, city: pune}
- file: hi-02.wav
  language: hi-en
  synthetic: true
  say: "Mumbai mein diesel pickup dikhao"
  expect_filters: {fuel: diesel, body_type: pickup, city: mumbai}
```

`scripts/make_eval_audio.py`:

```python
"""Synthesise stand-in eval clips with ElevenLabs (N7): 16 kHz mono WAV, plus white noise for `noisy`.

Usage: uv run python scripts/make_eval_audio.py [--force]
Needs ELEVENLABS_API_KEY. Existing files are kept unless --force (real recordings win).
"""

import argparse
import array
import random
import sys
import wave
from pathlib import Path

import httpx
import yaml

from voice_agent.config import get_settings, key

AUDIO_DIR = Path(__file__).resolve().parents[1] / "eval" / "audio"
URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
NOISE_RMS = 1500  # on int16 samples: clearly audible hiss, speech still intelligible


def synthesise(text: str, api_key: str, voice: str, model: str) -> bytes:
    resp = httpx.post(
        URL.format(voice=voice),
        params={"output_format": "pcm_16000"},
        headers={"xi-api-key": api_key},
        json={"text": text, "model_id": model},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content


def add_noise(pcm: bytes, seed: int = 7) -> bytes:
    rng = random.Random(seed)
    samples = array.array("h", pcm)
    for i, s in enumerate(samples):
        samples[i] = max(-32768, min(32767, s + int(rng.gauss(0, NOISE_RMS))))
    return samples.tobytes()


def write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        w.writeframes(pcm)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    api_key = key(settings.elevenlabs_api_key)
    if api_key is None:
        print("ELEVENLABS_API_KEY is not set", file=sys.stderr)
        return 2
    cases = yaml.safe_load((AUDIO_DIR / "cases.yaml").read_text(encoding="utf-8"))
    for case in cases:
        path = AUDIO_DIR / case["file"]
        if path.exists() and not args.force:
            print(f"keep  {path.name}")
            continue
        pcm = synthesise(case["say"], api_key, settings.elevenlabs_voice_id, settings.elevenlabs_model)
        write_wav(path, add_noise(pcm) if case.get("noisy") else pcm)
        print(f"wrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

(This script is outside `src/`. Scripts may call vendors directly, like `eval/` uses the runtime. Note it in the report.)

`eval/run_audio_eval.py`:

```python
"""Audio subset (J1): clip -> STT -> the real pipeline -> filter check. STT errors reported apart.

Usage: uv run python eval/run_audio_eval.py
Runs each clip through every STT valid for its language: en -> Groq; hi-en -> Sarvam (if keyed)
and Groq with the Roman-script prompt. Writes eval/results/audio_latest.md.
"""

import re
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from run_eval import check_turn  # same directory: the script runs as eval/run_audio_eval.py
from voice_agent.aio import run
from voice_agent.config import Settings, get_settings, key
from voice_agent.domain.ports import SpeechToText
from voice_agent.graph.runtime import build_runtime
from voice_agent.providers.http import open_http_client
from voice_agent.providers.stt import HINGLISH_PROMPT, GroqSTT, SarvamSTT

AUDIO_DIR = Path(__file__).parent / "audio"
RESULTS = Path(__file__).parent / "results" / "audio_latest.md"


def normalise(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def word_error_rate(ref: str, hyp: str) -> float:
    r, h = normalise(ref).split(), normalise(hyp).split()
    dist = list(range(len(h) + 1))
    for i, rw in enumerate(r, start=1):
        prev, dist[0] = dist[0], i
        for j, hw in enumerate(h, start=1):
            prev, dist[j] = dist[j], min(dist[j] + 1, dist[j - 1] + 1, prev + (rw != hw))
    return round(dist[len(h)] / max(1, len(r)), 3)


def stts_for(language: str, settings: Settings, client: Any) -> list[SpeechToText]:
    groq, sarvam = key(settings.groq_api_key), key(settings.sarvam_api_key)
    out: list[SpeechToText] = []
    if language == "en" and groq:
        out.append(GroqSTT(groq, settings.groq_stt_model, client))
    if language == "hi-en":
        if sarvam:
            out.append(SarvamSTT(sarvam, settings.sarvam_stt_model, settings.sarvam_stt_mode, client))
        if groq:
            out.append(
                GroqSTT(groq, settings.groq_stt_model, client, language=None, prompt=HINGLISH_PROMPT)
            )
    return out


async def run_all(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    settings = get_settings()
    rows: list[dict[str, Any]] = []
    async with open_http_client() as client, build_runtime(settings, log_turns=False) as runner:
        for case in cases:
            path = AUDIO_DIR / case["file"]
            if not path.exists():
                rows.append({"file": case["file"], "provider": "-", "status": "missing clip"})
                continue
            for stt in stts_for(case["language"], settings, client):
                tr = await stt.transcribe(path.read_bytes(), path.name, "audio/wav")
                result = await runner.run(f"audio-{uuid4().hex[:6]}", tr.text)
                failures = check_turn({"expect_filters": case["expect_filters"]}, result)
                rows.append(
                    {
                        "file": case["file"],
                        "provider": stt.name,
                        "synthetic": case.get("synthetic", False),
                        "transcript": tr.text,
                        "wer": word_error_rate(case["say"], tr.text),
                        "status": "PASS" if not failures else "FAIL: " + "; ".join(failures),
                    }
                )
                print(f"{rows[-1]['status'][:4]}  {case['file']:<18} {stt.name:<7} {tr.text}")
    return rows


def summarise(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Audio eval (STT subset, J1)",
        "",
        "| Clip | STT | Synthetic | WER | Transcript | Result |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['file']} | {r['provider']} | {r.get('synthetic', '')} | {r.get('wer', '')} "
            f"| {r.get('transcript', '')} | {r['status']} |"
        )
    passed = sum(r["status"] == "PASS" for r in rows)
    lines += ["", f"**{passed}/{len(rows)} clip×provider runs passed.**"]
    lines += ["A failure with high WER is an STT miss; low WER plus FAIL is an understanding miss."]
    return "\n".join(lines) + "\n"


def main() -> int:
    cases = yaml.safe_load((AUDIO_DIR / "cases.yaml").read_text(encoding="utf-8"))
    rows = run(run_all(cases))
    text = summarise(rows)
    print("\n" + text)
    RESULTS.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run the unit test and checks**

Run: `uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run mypy src`. Expected: pass.

- [ ] **Step 4: Generate clips and run live (if keys allow)**

```bash
uv run python scripts/make_eval_audio.py
uv run python eval/run_audio_eval.py
```

If `ELEVENLABS_API_KEY` is missing, skip both. Say so in the report. Task 14 handles it.

- [ ] **Step 5: Commit** (WAV clips are small; commit them under `eval/audio/` per standards §9)

```bash
git add -A eval scripts tests
git commit -m "Add audio eval subset: STT through the real pipeline, WER, synthetic clip generator"
```

---

### Task 12: Latency and cost reports

**Files:**
- Create: `scripts/latency_report.py`, `scripts/cost_report.py`, `config/prices.yaml`
- Test: `tests/unit/test_reports.py`

**Interfaces:**
- Consumes: `logs/turns.jsonl` (API records: `turn_id`, `session_id`, `tts_mode`, `timings_ms`, `usage`) and `logs/client_timings.jsonl` (Tasks 5–6).
- Produces:
  - `latency_table(turns, client) -> str`
  - `cost_summary(turns, prices) -> dict`
  - CLIs printing markdown, with an optional `--out PATH`.

- [ ] **Step 1: Write failing tests** in `tests/unit/test_reports.py`:

```python
import importlib.util
from pathlib import Path
from types import ModuleType


def _load(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_latency_table_groups_by_tts_mode_and_joins_client_timings() -> None:
    lat = _load("latency_report")
    turns = [
        {"turn_id": "a", "tts_mode": "sentence", "timings_ms": {"stt": 300, "first_audio_ready": 2000}},
        {"turn_id": "b", "tts_mode": "whole", "timings_ms": {"stt": 320, "first_audio_ready": 3000}},
    ]
    client = [{"turn_id": "a", "speech_end_to_first_audio_ms": 2400.0}]
    table = lat.latency_table(turns, client)
    assert "## tts_mode = sentence" in table and "## tts_mode = whole" in table
    assert "| speech_end_to_first_audio | 2400 | 2400 | 1 |" in table


def test_cost_summary_per_conversation() -> None:
    cost = _load("cost_report")
    prices = {
        "usd_to_inr": 100.0,
        "llm": {"groq": {"input": 1.0, "output": 2.0}},
        "stt": {"groq-stt": 3.6},
        "tts": {"elevenlabs-tts": 0.1},
    }
    turns = [
        {"session_id": "s1", "usage": [
            {"provider": "groq", "input_tokens": 1_000_000, "output_tokens": 0},
            {"provider": "groq-stt", "audio_seconds": 3600},
            {"provider": "elevenlabs-tts", "characters": 1000},
        ]},
        {"session_id": "s2", "usage": [{"provider": "groq", "input_tokens": 0, "output_tokens": 500_000}]},
    ]  # fmt: skip
    s = cost.cost_summary(turns, prices)
    assert s["conversations"] == 2 and s["turns"] == 2
    assert s["inr_total"] == 100.0 * (1.0 + 3.6 + 0.1 + 1.0)
    assert s["inr_per_conversation"] == s["inr_total"] / 2
    assert s["unpriced"] == []
```

- [ ] **Step 2: Implement**

`scripts/latency_report.py`:

```python
"""p50/p95 per stage from logs/turns.jsonl (+ browser timings), split by TTS mode (J4, J5).

Usage: uv run python scripts/latency_report.py [--out eval/results/latency.md]
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

STAGES = ["stt", "nlu", "search", "rank", "relax", "compose", "pipeline", "first_audio_ready", "tts", "server_total"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _p(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def latency_table(turns: list[dict[str, Any]], client: list[dict[str, Any]]) -> str:
    browser = {c["turn_id"]: c["speech_end_to_first_audio_ms"] for c in client if c.get("speech_end_to_first_audio_ms") is not None}
    groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for t in turns:
        if "turn_id" not in t:  # CLI/runner records have no API stages
            continue
        stages = groups[t.get("tts_mode", "unknown")]
        for name, ms in t.get("timings_ms", {}).items():
            stages[name].append(float(ms))
        if t["turn_id"] in browser:
            stages["speech_end_to_first_audio"].append(float(browser[t["turn_id"]]))
    lines = ["# Latency report", ""]
    for mode, stages in sorted(groups.items()):
        lines += [f"## tts_mode = {mode}", "", "| Stage | p50 ms | p95 ms | n |", "|---|---|---|---|"]
        order = [s for s in [*STAGES, "speech_end_to_first_audio"] if s in stages]
        for name in order:
            v = stages[name]
            lines.append(f"| {name} | {statistics.median(v):.0f} | {_p(v, 0.95):.0f} | {len(v)} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=Path, default=Path("logs/turns.jsonl"))
    parser.add_argument("--client", type=Path, default=Path("logs/client_timings.jsonl"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    text = latency_table(read_jsonl(args.turns), read_jsonl(args.client))
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
```

`scripts/cost_report.py`:

```python
"""₹ per conversation from logged usage (L5), priced with config/prices.yaml.

Usage: uv run python scripts/cost_report.py [--out eval/results/cost.md] [--monthly 100000]
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def usd(u: dict[str, Any], prices: dict[str, Any]) -> float | None:
    p = u["provider"]
    if p in prices["llm"]:
        rate = prices["llm"][p]
        return (u.get("input_tokens", 0) * rate["input"] + u.get("output_tokens", 0) * rate["output"]) / 1e6
    if p in prices["stt"]:
        return u.get("audio_seconds", 0.0) / 3600 * prices["stt"][p]
    if p in prices["tts"]:
        return u.get("characters", 0) / 1000 * prices["tts"][p]
    return None


def cost_summary(turns: list[dict[str, Any]], prices: dict[str, Any]) -> dict[str, Any]:
    by_provider: dict[str, float] = defaultdict(float)
    sessions: set[str] = set()
    unpriced: set[str] = set()
    for t in turns:
        sessions.add(t.get("session_id", "?"))
        for u in t.get("usage", []):
            cost = usd(u, prices)
            if cost is None:
                unpriced.add(u["provider"])
            else:
                by_provider[u["provider"]] += cost
    inr_total = sum(by_provider.values()) * prices["usd_to_inr"]
    n = max(1, len(sessions))
    return {
        "turns": len(turns),
        "conversations": len(sessions),
        "inr_by_provider": {k: v * prices["usd_to_inr"] for k, v in sorted(by_provider.items())},
        "inr_total": inr_total,
        "inr_per_conversation": inr_total / n,
        "unpriced": sorted(unpriced),
    }


def render(s: dict[str, Any], monthly: int, checked: str) -> str:
    lines = [
        "# Cost report (L5)",
        "",
        f"Prices: config/prices.yaml (checked {checked}; re-verify before quoting).",
        f"{s['turns']} turns in {s['conversations']} conversations.",
        "",
        "| Provider | ₹ total |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v:.4f} |" for k, v in s["inr_by_provider"].items()]
    per = s["inr_per_conversation"]
    lines += [
        "",
        f"**₹ per conversation: {per:.3f}**. At {monthly:,} conversations/month: ₹{per * monthly:,.0f}.",
    ]
    if s["unpriced"]:
        lines.append(f"Unpriced providers (add to prices.yaml): {', '.join(s['unpriced'])}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=Path, default=Path("logs/turns.jsonl"))
    parser.add_argument("--prices", type=Path, default=Path("config/prices.yaml"))
    parser.add_argument("--monthly", type=int, default=100_000)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    prices = yaml.safe_load(args.prices.read_text(encoding="utf-8"))
    text = render(cost_summary(read_jsonl(args.turns), prices), args.monthly, prices.get("checked", "?"))
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
```

`config/prices.yaml`: **verify each number with a web search of the vendor's pricing page before committing.** Set `checked:` to the date you verified. If a price can't be confirmed, keep the value below, mark it `# unverified`, and say so in the report.

```yaml
# Paid-tier list prices used by scripts/cost_report.py (L5). Re-verify before quoting.
checked: "2026-10-20"
usd_to_inr: 88.0
llm:        # USD per 1M tokens
  groq: {input: 0.15, output: 0.75}       # openai/gpt-oss-120b on Groq
  gemini: {input: 0.10, output: 0.40}     # gemini-2.5-flash-lite
stt:        # USD per audio hour (Groq bills a 10 s minimum per request)
  groq-stt: 0.111                         # whisper-large-v3
  sarvam-stt: 0.34                        # ~₹30 / hour
tts:        # USD per 1k characters
  elevenlabs-tts: 0.05                    # Flash v2.5
```

- [ ] **Step 3: Run checks**

Run: `uv run pytest -q && uv run ruff format . && uv run ruff check . && uv run mypy src`. Expected: pass.

If `logs/turns.jsonl` exists, also run both scripts once to see the real output. They must not crash on CLI-only records, which have no `turn_id`.

- [ ] **Step 4: Commit**

```bash
git add -A scripts config tests
git commit -m "Add latency report (by TTS mode, with browser timings) and cost report"
```

---

### Task 13: Docs: README, decisions N, architecture, definition of done

**Files:**
- Create: `README.md`
- Modify: `docs/decisions.md` (add section **N** = rulings N1–N8 from this plan, plus any Task 10 changes; update H2's Sarvam mode wording to point to N3)
- Modify: `docs/architecture.md` (§10 and §11 now implemented: drop the "Plan 2" markers, add `api/` and `providers/{http,stt,tts}.py` to §2/§3, add the NDJSON STT-failure sequence; §12 `turn_log` table stays reserved and unused)
- Modify: `docs/definition-of-done.md` (tick M1; tick M2/M4/M5 only for items verified so far, else leave them for Task 14)
- Modify: `CLAUDE.md` (commands: `uv run python -m voice_agent.api`, `uv run python eval/run_audio_eval.py`, report scripts)
- Modify: `CITATIONS.md` (Groq Whisper, Sarvam Saaras, ElevenLabs Flash, FastAPI, Vite/React)
- Modify: `eval/results/known_failures.md` (Hinglish template-language note N1; synthetic audio note N7)

**README.md sections** (concise; no marketing):
1. What it is: one paragraph, plus the seven-component diagram in text form.
2. **Quick start (Docker, ≤10 min):** `cp .env.example .env`, set `GROQ_API_KEY` (required). Optional keys: `ELEVENLABS_API_KEY` (server voice; otherwise the browser speaks) and `SARVAM_API_KEY` (Hinglish STT; otherwise Groq Whisper). Then `docker compose up --build`, open http://localhost:5173 and allow the mic.
3. Local dev without Docker: `docker compose up -d db`, `uv sync`, `uv run python -m voice_agent.api`, `cd ui && npm install && npm run dev`.
4. Using it: hold to talk, the EN/Hinglish toggle, typed fallback. Example script: search → correction → follow-up → zero result.
5. Eval: `uv run python eval/run_eval.py` (Groq key only; ~15 min because of the free-tier 8k TPM), `--category`, the audio eval, and where results live. Paste the latest headline numbers.
6. Latency and cost: what the panel shows, `scripts/latency_report.py`, `scripts/cost_report.py`, and the J5 mitigations (sentence TTS, reasoning effort, compose model).
7. Design in one screen: hard rules (filters not vibes, validator + template, one-slot correction), with links to `docs/decisions.md` and `docs/architecture.md`.
8. Known limits: link to `eval/results/known_failures.md`, F3, the Groq TPM limit, synthetic audio clips.
9. Repo map (from CLAUDE.md).

- [ ] **Step 1:** Write and edit the docs above. Keep every claim true to the code as it stands. Where Task 14 numbers aren't in yet, write `TBD after live run` **only** in README sections 5–6. Task 14 replaces them.
- [ ] **Step 2:** Run `uv run ruff check . && uv run pytest -q`. Expected: pass (docs are excluded from ruff).
- [ ] **Step 3: Commit**

```bash
git add -A README.md docs CLAUDE.md CITATIONS.md eval/results/known_failures.md
git commit -m "Add README; record Plan 2 decisions (N1-N8); sync architecture and definition of done"
```

---

### Task 14: Live verification and results (controller-run, not a subagent)

The controller runs this task itself. It needs the user's environment (WSL Docker, keys, browser).

- [ ] Full text eval: `uv run python eval/run_eval.py` (32 cases). Target ≥90% overall and in hinglish. Commit `eval/results/latest.*`.
- [ ] Audio eval: `scripts/make_eval_audio.py` (if the ElevenLabs key exists), then `eval/run_audio_eval.py`. Commit the clips and `audio_latest.md`.
- [ ] Docker: `docker compose up --build -d` in WSL. Check health, run one typed turn through nginx :5173, then `docker compose stop app ui`.
- [ ] UI smoke through the browser (claude-in-chrome): typed turns covering search → correction → follow-up → zero result. Panels must fill in. A mic test is manual for the user.
- [ ] J5 measurement: run ~5 identical typed turns through the API with `TTS_MODE=sentence` and ~5 with `TTS_MODE=whole` (needs an ElevenLabs key; otherwise compare `first_audio_ready` with TTS off and say so). Then run `scripts/latency_report.py --out eval/results/latency.md` and `scripts/cost_report.py --out eval/results/cost.md`.
- [ ] Fill the README "TBD after live run" numbers, tick the definition-of-done milestones that are verified, commit, and run the final whole-branch review (most capable model). One fix wave, then delete `.superpowers/` (the user approved this) and finish the branch. Push only on the user's say-so.
