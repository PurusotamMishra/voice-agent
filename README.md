# Vyngo Voice Vehicle Search

A voice-first assistant for finding a used commercial vehicle in India. The buyer speaks English or Hinglish. The system turns speech into text, extracts what the buyer wants, runs a hard-filtered SQL search over a synthetic catalog, ranks the top three, checks the written answer against the data, and speaks it back sentence by sentence.

## 1. What it is

Seven components (brief section 2), in the order a turn passes through them:

```
[1] Voice interface   browser: hold-to-talk recorder, typed fallback, audio queue, panels
        |  POST /api/turn (audio or text)          ^ NDJSON events (transcript, understanding, search, sentence, done)
        v                                          |
[2] STT               Sarvam Saaras (both languages), Groq Whisper failover; Groq Whisper only without a Sarvam key
[3] Understanding     LLM slot extraction + deterministic number parser + alias normaliser
[6] Conversation state  slots, one-slot corrections, references ("the second one"), Postgres checkpoints
[4] Catalog + search  Filters -> parameterized SQL -> ranker (or a relaxation probe on zero rows)
[5] Response + TTS    LLM composes from a fact sheet -> validator (or template) -> ElevenLabs per sentence
[7] Eval + latency    eval/ cases, audio subset, per-stage timings, cost report
```

The LLM never writes SQL, and every number it speaks passes a validator or is replaced by a template. Stack: Python 3.12, uv, FastAPI, LangGraph, Postgres 16, Vite + React + TypeScript, Docker Compose.

## 2. Quick start (Docker, about 10 minutes)

```bash
cp .env.example .env
# edit .env: set GROQ_API_KEY (required)
docker compose up --build
```

Then open http://localhost:5173 and allow the microphone.

| Key | Needed | Without it |
|---|---|---|
| `GROQ_API_KEY` | yes (LLM, English STT) | nothing works |
| `ELEVENLABS_API_KEY` | no, server voice | the browser speaks the answer (`tts_client` fallback) |
| `SARVAM_API_KEY` | no, but recommended | With it, Sarvam transcribes all speech, English and Hinglish, so the buyer can switch language mid-conversation; Groq Whisper takes over if Sarvam fails (`stt_failover`). Without it, the dropdown picks Groq Whisper for English or Whisper with a Roman-script prompt for Hinglish (`stt_hinglish_groq`) |
| `GEMINI_API_KEY` | no, LLM failover | no failover when Groq errors; the rules-only extractor still runs |

Compose starts `db` (host port 5433), `app` (port 8000) and `ui` (nginx, port 5173). The catalog is seeded on first boot. `.env` is never committed.

## 3. Local development without Docker

```bash
docker compose up -d db
uv sync
uv run python -m voice_agent.api        # API on http://127.0.0.1:8000
cd ui && npm install && npm run dev     # UI on http://localhost:5173, proxies /api to :8000
```

Checks: `uv run pytest`, `uv run ruff format . && uv run ruff check .`, `uv run mypy src`, `cd ui && npm run lint && npm run build`.

## 4. Using it

- Hold the **Hold to talk** button, speak, release. The transcript, slots, executed SQL, top three with score breakdown, validator verdict and latency stages fill in as events arrive, and the answer plays sentence by sentence.
- The dropdown next to the button picks the input language: **English** or **Hinglish**. With `SARVAM_API_KEY` set it only matters on fallbacks (the browser voice, and how Groq Whisper transcribes if Sarvam fails); you can switch language mid-conversation without touching it. Without the key it decides which STT runs, so switch it before speaking Hindi: Whisper set to English translates Hindi speech into English.
- If the microphone is unavailable, type in the box and press Send. Typed input skips STT.

Example conversation (utterances to try, not recorded output):

1. "I need a small truck under 5 lakh in Pune." Search.
2. "Actually make it Delhi." Correction: only the city changes.
3. "How many kilometres has the second one run?" Follow-up on a listed vehicle.
4. "Diesel mini truck in Chennai." Zero result: the system says so and offers one relaxation, if one returns rows.

## 5. Eval

```bash
uv run python eval/run_eval.py                      # 32 cases, live; needs GROQ_API_KEY only (STT and TTS are not used)
uv run python eval/run_eval.py --category hinglish  # one category; results files are not written
uv run python scripts/make_eval_audio.py            # synthesise the audio clips (needs ELEVENLABS_API_KEY)
uv run python eval/run_audio_eval.py                # 5 audio clips through STT, then the pipeline
```

A full run takes about 15 minutes because the Groq free tier allows 8,000 tokens per minute per model. A case passes when the executed filters match, the expected slot changed (for corrections) or the follow-up resolved to the right listing, and the validator passed on the first generation. Constraint safety is reported separately.

Results: `eval/results/latest.md` and `latest.json` (text eval), `audio_latest.md` (audio eval). Context the files cannot hold is in `eval/results/known_failures.md`.

Numbers so far:
- Text loop, 25 cases: 25/25, constraint safety 100% (2026-10-19).
- Hinglish category, 7 cases: 7/7 on the first run.
- Full 32-case run on the smaller models (`GROQ_MODEL=openai/gpt-oss-20b`, `GROQ_COMPOSE_MODEL=qwen/qwen3.8-27b`, used because the day's `gpt-oss-120b` token allowance was spent): 26/32 = 81%, constraint safety 98.4% (2026-10-20, `eval/results/alt-models-2026-10-20.md`). Four failures are replies that passed the validator only on regeneration (safe, but the eval wants a clean first try); two are "Tata Ace" read as a body type, one of which also dropped the make. The NLU p50 fell from 5.7 s to 0.63 s.
- Audio eval (5 ElevenLabs Flash clips, synthetic stand-ins, not real recordings), 2026-10-20: 4/7 clip × provider runs. English 3/3 through Groq, including the noisy clip. Hinglish through Sarvam: both transcripts in Roman script (WER 0.11 and 0.0); `hi-01` passes, `hi-02` has the right filters but its reply passed the validator only on regeneration. Hinglish through Groq Whisper 0/2: Devanagari and Urdu script, so no slots were parsed. Sarvam on the English clips (outside the harness): 3/3 transcribed correctly, 120–300 ms against Whisper's 220–570 ms (N14).

## 6. Latency and cost

The UI latency panel shows the stages of the last turn (STT, NLU, search, compose, first audio ready, TTS, server total) and the browser-measured time from button release to first audio. The API writes one record per turn to `logs/turns.jsonl`, and the browser posts its timings to `logs/client_timings.jsonl`.

```bash
uv run python scripts/latency_report.py --out eval/results/latency.md   # p50/p95 per stage, split by TTS mode
uv run python scripts/cost_report.py --out eval/results/cost.md         # INR per conversation and per 100k conversations/month
```

Mitigations in place for the slow LLM stage (J5):
- **Sentence-level TTS** (`TTS_MODE=sentence`, default): one TTS call per validated sentence, so the first sentence plays while the rest are synthesised. `TTS_MODE=whole` makes one call for the full text, for comparison.
- **Low reasoning effort** (`LLM_REASONING_EFFORT=low`) for the Groq gpt-oss models.
- **Separate compose model** (`GROQ_COMPOSE_MODEL`, optional) so the composer uses its own model and token bucket.

Prices come from `config/prices.yaml` (checked 2026-10-20; the ElevenLabs row and the USD to INR rate are unverified).

Measured on 2026-10-20 (`eval/results/latency.md`; 19 sentence-mode turns, 7 of them from the browser mic test, and 5 whole-mode turns, Groq free tier):
- **Headline, browser-measured speech end to first audio: p50 3.3 s, p95 4.6 s** (7 mic turns, sentence TTS).
- Server total p50/p95: 3.9 s / 10.2 s with sentence TTS, 13.5 s / 24.5 s with whole TTS. The whole-mode turns ran into Groq rate limiting on compose, so compare the TTS gap below, not the totals.
- **Dominant stage: compose** (one LLM call, p50 0.8 s, p95 8.7 s, rate-limit waits included). STT p50 1.2 s (real mic turns are longer than the eval clips), NLU 0.8 s, search under 5 ms.
- **Mitigation measured:** time from finished reply to first audio ready, per-turn median on the first 8 sentence-mode turns: **0.37 s with sentence TTS vs 1.13 s with whole TTS**, so sentence streaming wins back about 0.8 s.
- Cost: **₹1.51 per turn** (13 one-turn conversations), about **₹6 for a 4-turn conversation**, so about ₹6 lakh a month at 100k conversations. ElevenLabs TTS is about 95% of it; Groq LLM and STT are under ₹0.07 a turn (`eval/results/cost.md`).

## 7. Design in one screen

- **Filters, not vibes.** A stated budget, body type, fuel or city (and make, model, payload, km, year when stated) is a hard SQL filter. `purpose` only affects ranking. SQL comes from `catalog/filters.py`, parameterized.
- **No invented facts.** The LLM sees only a fact sheet with pre-formatted numbers. Each sentence is bound to one listing and checked by `response/validator.py`. A failure regenerates once, then falls back to `response/templates.py`.
- **A correction changes one slot.** "Actually make it Delhi" changes the city and nothing else.
- **Every fallback is recorded** in `fallback_used` and logged.
- Vendor SDKs and LangChain stay in `providers/` and `graph/`. Business logic is plain Python.

Why each choice was made, with the rejected alternative: [docs/decisions.md](docs/decisions.md). Components, contracts and the API: [docs/architecture.md](docs/architecture.md). Rules: [docs/standards.md](docs/standards.md), [CLAUDE.md](CLAUDE.md).

## 8. Known limits

- See [eval/results/known_failures.md](eval/results/known_failures.md): run-to-run LLM variance, the one-km-phrase parser limit, and Hinglish users hearing English templates (N1).
- A single-letter mishear (for example "S" for "Ace") cannot be matched by trigrams (decisions D2, F3).
- Groq free tier: 8,000 tokens per minute per model, about 3 turns a minute. This is the first bottleneck and part of why eval latency is high (decisions M4).
- The audio eval clips are synthetic stand-ins (N7), so STT results will be optimistic. WER is brittle for Devanagari output and digits versus words.
- Without `SARVAM_API_KEY` (or during a Sarvam outage), Hinglish speech goes to Groq Whisper, which often returns Devanagari or Urdu script; the parser and aliases are Roman script, so those turns lose their slots. Typed Hinglish works.
- Groq free tier also caps each model at 200,000 tokens a day. One full eval uses 100–150k, so a second run in a day can fall back to rules and templates.
- The listing catalog is synthetic (see `CITATIONS.md`).
- `/api/health` does not ping the database after startup (N10).

## 9. Repo map

- `src/voice_agent/`: `api/` (FastAPI, NDJSON turn stream), `understanding/`, `catalog/`, `response/`, `state/`, `graph/` (LangGraph wiring), `providers/` (LLM, STT, TTS, HTTP, Postgres), `telemetry/`, `db/`, `domain/`
- `ui/`: Vite + React + TypeScript (push-to-talk, panels)
- `eval/`: `cases.yaml`, `run_eval.py`, `run_audio_eval.py`, `audio/`, `results/`
- `data/`: `models.csv`, `listings.csv` (generated, seed 42), `aliases.csv`, `city_neighbors.csv`
- `scripts/`: `generate_catalog.py`, `make_eval_audio.py`, `latency_report.py`, `cost_report.py`
- `config/`: `ranking.yaml`, `prices.yaml`
- `docs/`: decisions, architecture, standards, definition of done
