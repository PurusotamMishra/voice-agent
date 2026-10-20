# Architecture — Vyngo Voice Vehicle Search

Source of truth for *how* the system is built. *Why* lives in [decisions.md](decisions.md) (IDs like `D1` refer to it).
If code and this document disagree, fix one of them in the same change.

---

## 1. System overview

```
 Browser (ui/: Vite + React)                  app/: FastAPI + LangGraph                         db: Postgres 16
 ┌───────────────────────────┐   POST /api/turn   ┌──────────────────────────────────────────┐   ┌──────────────┐
 │ [1] Push-to-talk recorder ├──────────────────► │ [2] STT ─► [3] Understand ─► [6] State   │   │ listings     │
 │     typed-input fallback  │  audio | text      │                 │                        │   │ aliases      │
 │                           │                    │                 ▼                        │◄─►│ city_neighbors│
 │ Panels: transcript, slots,│ ◄──────────────────┤ [4] Search+Rank (or Relax probe)         │   │ checkpoints  │
 │ SQL, top-3 + scores,      │  NDJSON event      │                 │                        │   │ (LangGraph)  │
 │ validator, latency        │  stream            │ [5] Compose ─► Validate ─► TTS (per sent.)│   │ (turn_log: unused)│
 │ Audio queue player        │                    │                                          │   └──────────────┘
 └───────────────────────────┘                    │ [7] telemetry: timings, usage, turn log   │
                                                  └──────────────────────────────────────────┘
 eval/ ── runs cases through the same graph (text in, TTS off) ──► pass rate per category
```

Status: built. The text loop (understand → state → search/rank/relax → respond) is driven by `cli.py`, `eval/run_eval.py` and the API. The voice loop adds the browser UI, the FastAPI app, STT and TTS. `docker-compose.yml` runs `db` (Postgres 16 with `pg_trgm`, host port 5433), `app` (FastAPI under uvicorn, port 8000) and `ui` (nginx on host port 5173, serving the React build and proxying `/api` → `app`).

## 2. The seven components → code

| # | Component (brief §2) | Package / path | Hides | Swap target |
|---|---|---|---|---|
| 1 | Voice interface | `ui/src/` (`audio/` recorder + audio queue, `panels/`, `api/` NDJSON client) + `src/voice_agent/api/` (`app.py` routes, `stream.py` turn events, `services.py` wiring, `__main__.py` entry). Also `src/voice_agent/cli.py` (text chat) | MediaRecorder, streaming fetch, playback | Twilio/WebRTC client |
| 2 | STT | `SpeechToText` Protocol (`domain/ports.py`); `providers/stt.py` (`GroqSTT`, `SarvamSTT`, `make_stt`), called from `api/stream.py` outside the graph; `providers/http.py` (retry, `json_body`) | Vendor API, audio format | Any STT impl |
| 3 | Understanding | `understanding/` — `pipeline.py` (`understand()`: LLM + number override + normalisation), `numbers.py` (money/units parser), `extractor.py` (LLM structured call), `rules.py` (LLM-outage fallback), `schema.py`. Normaliser: `providers/postgres.py` `PgNormalizer` (alias + `pg_trgm`) | Prompting, LLM vendor, alias fuzziness | Fine-tuned NLU / different LLM |
| 4 | Catalog + search | `catalog/` — `filters.py` (Filters → SQL, plus the `constraint_violations` re-check), `ranker.py`, `relax.py`. Search: `providers/postgres.py` `PgCatalog` | SQL, ranking weights | Elastic/OpenSearch, learned ranker |
| 5 | Response (+ TTS) | `response/` — `factsheet.py`, `formatting.py`, `composer.py`, `validator.py`, `templates.py`, `schema.py`. TTS: `TextToSpeech` Protocol; `providers/tts.py` (`ElevenLabsTTS`, `speakable`, `make_tts`), called per sentence from `api/stream.py` | LLM phrasing, number formatting, TTS vendor | Any TTS impl |
| 6 | Conversation state | `state/` — `models.py` (`Memory`, `Route`), `reducer.py` (merge / one-slot correction / confirm), `references.py`; persisted by the LangGraph Postgres checkpointer | Merge rules, reference resolution | Redis-backed store |
| 7 | Eval + latency | `eval/` (`cases.yaml`, `run_eval.py`, `results/`); `telemetry/` (`timing.py`, `turnlog.py`). `eval/run_audio_eval.py` + `eval/audio/cases.yaml` (STT subset); `scripts/latency_report.py`, `scripts/cost_report.py`, `scripts/make_eval_audio.py`; prices in `config/prices.yaml` | — | — |

Glue: `graph/` — `build.py` (LangGraph `StateGraph` wiring only), `state.py` (`ConversationState` + checkpoint serde allowlist), `runner.py` (`TurnRunner`: one call = one turn, with an error boundary), `runtime.py` (wires real providers). LLM providers: `providers/llm.py` (`LangChainLLM`, `FailoverLLM`, `make_llm`).

## 3. Repository layout

```
voice-agent/
├── CLAUDE.md                 # agent guide (start here)
├── CITATIONS.md
├── Dockerfile  docker-compose.yml   # db + app + ui
├── pyproject.toml / uv.lock
├── config/                   # ranking.yaml (ranker weights, E2), prices.yaml (N8)
├── docs/                     # decisions, architecture, standards, definition-of-done
├── data/                     # models.csv, listings.csv, aliases.csv, city_neighbors.csv
├── src/voice_agent/
│   ├── config.py  cli.py  aio.py
│   ├── domain/               # enums, shared Pydantic models, Protocols (ports.py)
│   ├── understanding/  catalog/  response/  state/   # components 3–6
│   ├── api/                  # FastAPI app, NDJSON turn stream, wiring (STT/TTS sit here, outside the graph)
│   ├── graph/                # LangGraph wiring, state, TurnRunner, runtime
│   ├── providers/            # ONLY place for vendor calls (llm, stt, tts, http), LangChain chat models and DB queries
│   ├── telemetry/            # timer, JSONL turn log
│   └── db/                   # schema.sql, seed.py (loads data/*.csv on first boot)
├── ui/                       # Vite + React + TS; Dockerfile + nginx.conf
├── scripts/                  # generate_catalog, latency_report, cost_report, make_eval_audio
├── tests/unit/  tests/db/    # unit: no network; db: @pytest.mark.db
└── eval/                     # cases.yaml, run_eval.py, run_audio_eval.py, audio/, results/
```
STT and TTS are not packages of their own: they live in `providers/` and are called from `api/stream.py`.

## 4. Domain model (`src/voice_agent/domain/`)

All money is **integer INR**. All weights in **kg**. Never floats for money.

```python
class BodyType(StrEnum):  three_wheeler, mini_truck, pickup, cargo_van, lcv, icv, tipper
class Fuel(StrEnum):      diesel, petrol, cng, electric
class City(StrEnum):      mumbai, delhi, bengaluru, pune, hyderabad, chennai, ahmedabad, jaipur, lucknow, kolkata
class Purpose(StrEnum):   city_delivery, long_haul, construction, agriculture

class Slots(BaseModel):            # what the buyer has told us (inspectable every turn)
    budget_max: int | None         # hard   (D5)
    budget_min: int | None         # hard
    budget_target: int | None      # soft — "around X" (ranking closeness); budget_max = 1.1·X
    body_type: BodyType | None     # hard   (E1)
    fuel: Fuel | None              # hard
    city: City | None              # hard
    make: str | None               # hard when stated (canonical from aliases)
    model: str | None              # hard when stated
    min_payload_kg: int | None     # hard when stated
    max_km: int | None             # hard when stated
    min_year: int | None           # hard when stated
    purpose: Purpose | None        # SOFT ONLY (B4) — never becomes a filter

class Filters(BaseModel):          # derived from Slots by catalog/filters.py — purpose & budget_target excluded
class Listing(BaseModel):          # one row of listings (see data/README.md for columns)
class ScoredListing(BaseModel):    # listing + score + contributions: dict[str, float] (E2)
```

## 5. Turn pipeline (LangGraph, `src/voice_agent/graph/build.py`)

```
 text ─► understand ─► update_state ─┬─ route=search ─► search ─┬─ rows ───► rank ──┐
         (pipeline.py)  (reducer.py) │                          └─ 0 rows ─► relax ─┤
                                     └─ any other route ────────────────────────────┤
                                                                                    ▼
                                                                                 respond ─► END
```

- `understand`: `understanding.pipeline.understand()` → `Understanding` (intent, slot updates, low-confidence and unsupported mentions, usage, fallbacks).
- `update_state`: `state.reducer.apply_understanding()` → new memory, `slot_diff`, `Route` (`search | confirm | follow_up | which_one | reset | out_of_domain | unsupported | need_info`).
- `search`: `Filters.from_slots` → `Catalog.search`, then `catalog.filters.constraint_violations` re-checks every row (F2.3); a dropped row is logged and recorded as `constraint_drop`.
- `rank`: `catalog.ranker.rank` → top-3 `ScoredListing` + `last_results`. `relax`: `catalog.relax.propose_relaxation` → `pending_relaxation`.
- `respond`: a search with results → `response.composer.compose_results` (LLM → validator → regenerate once → template); every other route (zero results, follow-up, confirm, unsupported, reset, …) → `response.templates`.
- Nodes are thin; **no LLM decides routing** beyond the intent label. Checkpointer: LangGraph Postgres saver, `thread_id = session_id` (G4).
- `graph/runner.py` `TurnRunner.run(session_id, text) -> TurnResult` is the seam the CLI, the eval and the API call. An exception inside the graph becomes a templated error turn (`route="error"`, `fallback_used=["error"]`) and the session continues.

> STT and TTS sit outside the graph: `audio → STT → TurnRunner.run(text) → TTS per sentence`. The graph is text-in/text-out, so the eval and CLI exercise exactly the graph the voice path will use.

### Graph state (`graph/state.py`)

```python
class ConversationState(TypedDict, total=False):
    # memory (persists across turns via the checkpointer)
    turn: int
    slots: Slots
    pending_confirmation: PendingConfirmation | None   # D6
    pending_relaxation: Relaxation | None              # E3
    last_results: list[ResultRef]                      # ordered (listing_id, rank, make, model)
    focused_listing_id: str | None                     # G3
    # this turn (reset by TURN_RESET at the start of every turn)
    text: str
    understanding: Understanding | None
    slot_diff: dict[str, tuple[Any, Any]]              # key -> (old, new)
    route: Route | None
    filters: Filters | None
    executed_sql: str | None
    sql_params: dict[str, Any]
    candidates: list[Listing]
    results: list[ScoredListing]
    response: ComposedResponse | None
    verdict: Verdict | None
    fallback_used: list[str]   # llm_failover, rules_extractor, regenerated, template, constraint_drop, error
    timings_ms: dict[str, float]
    usage: list[Usage]         # LLM tokens per call and provider (L5)
```
Every Pydantic/Enum type reachable from these annotations is on the checkpoint serde allowlist (`STATE_TYPES`); a unit test enforces it.

## 6. Component contracts (Protocols, `domain/ports.py`)

```python
class LLM(Protocol):            # extractor + composer; Groq primary, Gemini fallback via FailoverLLM (I1)
    name: str
    async def structured(self, system: str, user: str, schema: type[T]) -> LLMResult[T]: ...
    # LLMResult(value: T, usage: Usage); raises ProviderError after the provider's retries

class Normalizer(Protocol):     # PgNormalizer
    async def normalize(self, kind: AliasKind, raw: str) -> Match: ...  # Match(raw, canonical, score, method)

class Catalog(Protocol):        # PgCatalog
    async def search(self, filters: Filters, limit: int = 500) -> SearchResult: ...  # rows + sql + params
    async def count(self, filters: Filters) -> int: ...
    async def get(self, listing_id: str) -> Listing | None: ...
```

Ranking, composing and validating are plain functions, not Protocols (`rank`, `compose_results`, `validate`). The voice loop adds two more Protocols, implemented in `providers/stt.py` and `providers/tts.py`:

```python
class SpeechToText(Protocol):   # GroqSTT, SarvamSTT
    name: str
    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> Transcript: ...

class TextToSpeech(Protocol):   # ElevenLabsTTS; None means the browser speaks
    name: str
    async def synthesize(self, text: str) -> bytes: ...   # complete MP3 bytes (N2)
```

Providers are chosen in `config.py` from env (`LLM_PROVIDER`, `LLM_FALLBACK_PROVIDER`, `GROQ_MODEL`, `GEMINI_MODEL`, and for voice `GROQ_STT_MODEL`, `SARVAM_API_KEY`, `ELEVENLABS_API_KEY`, `TTS_MODE`); STT is Sarvam for every request when keyed, with Groq failover (N14), otherwise picked per request by language (N3); unit tests use the fakes in `tests/fakes.py`.

## 7. Understanding details (D1–D7, `understanding/pipeline.py`)

1. `extractor.py` makes **one** LLM structured call with schema `TurnIntent`. The prompt lists the allowed enum values (from the `domain` enums), phrase hints from the alias table, the current slots, the last results and the pending question. On `ProviderError` the pipeline falls back to `rules.py` (exact alias matching) and records `rules_extractor`.
2. `numbers.py` (deterministic) parses money/km/payload/year: "5 lakh", "4.5L", "paanch lakh", "pachaas hazaar km", "1 ton", "2018 ke baad". Number words convert only when a unit follows. A km/payload phrase whose direction contradicts the slot ("over 2 lakh km", "payload under 2 tons") is dropped, never inverted.
3. Per-field number override (D3): the parser wins on every field it found. For a field it missed, the LLM's value is kept unless it equals a number the parser read this turn. Budget bounds are one group: if the parser found any bound, the LLM's budget is ignored. Only stated bounds are written: a max also clears `budget_target`, a min leaves the max alone, a range or "around X" replaces all three.
4. City/make/model mentions go through `PgNormalizer`: exact alias → `pg_trgm similarity()`; ≥ `TRGM_ACCEPT` (0.6) accepted, ≥ `TRGM_CONFIRM` (0.3) → `pending_confirmation` ("Did you mean Tata Ace?"), below that → reported as not found.
5. `state.reducer.sanitize_updates` validates ranges/enums against `Slots`; invalid values are dropped and logged, never forwarded to SQL.

## 8. Search, ranking, relaxation (E1–E4)

- `catalog/filters.py`: `Filters → (sql, params)`. One `WHERE` clause per non-null hard field, always parameterized (`%(budget_max)s`). `PgCatalog` executes it and returns the SQL + params for display/logging.
- `catalog/ranker.py`: `score = Σ wᵢ·fᵢ`, features normalised to [0,1] within the candidate set: `price` (cheaper, or closer to `budget_target` for "around X"), `low_km`, `newer_year`, `papers_verified`, `purpose_fit`. Weights in `config/ranking.yaml`; per-feature `contributions` are kept per result.
- `catalog/relax.py`: on 0 rows, probe one change at a time with `COUNT(*)`: budget +20% → neighbour cities → any fuel → adjacent body type → drop min_year / max_km / min_payload / model / make / budget_min. The first change with ≥1 row is offered as `pending_relaxation`; it is applied only on a `relax` intent.
- Defense in depth (F2.3): the `search` node re-checks every row with `catalog.filters.constraint_violations`.

## 9. Response + anti-hallucination (F1–F5)

**Fact sheet** (`factsheet.py`): for each top-k listing, pre-formatted display strings (`"₹4.8 lakh"`, `"48,000 km"`, `"1,030 kg"`, `"2019"`), canonical make/model/city, and the top 2 reason features with their display values. This is the only thing the LLM sees.

**Structured composition** (`composer.py`): the LLM returns
```python
class ComposedResponse(BaseModel):
    intro: str                          # no numbers allowed
    items: list[ItemSentence]           # ItemSentence(listing_id, text), in rank order
    closing: str                        # question/suggestion, no numbers allowed
```
Per-item sentences are bound to a `listing_id`, so the validator checks each sentence **only against its own record**. This closes the cross-attribution gap noted in F3.

**Validator** (`validator.py`), pure Python:
1. `items[*].listing_id` == top-k IDs, in order; each sentence names only its own make/model (canonical names, aliases, model-family prefix), city and fuel.
2. Every number in each sentence is read with its unit (`numbers_with_units`) and must match a (value, unit) pair of that record's facts; numbers from the title license the bare number only. Spelled-out number words and stray scale words are rejected.
3. `intro`/`closing` contain no numbers and no vehicle entities.

(The constraint re-check of the records, F2.3, runs earlier, in the `search` node.)

Failure → regenerate once with the violations listed in the prompt → still failing → `templates.py` (deterministic). `fallback_used` records it.

**Follow-ups** are answered without the LLM: the referenced listing is fetched by ID and `templates.follow_up` fills one sentence from its fact item (formatted values only). A field we don't hold (`other`) → templated "That detail isn't in the listing."

**Known limits** (said out loud in the presentation): see decisions F3.

## 10. API (`src/voice_agent/api/`)

Implemented. `create_app(settings, services)` in `app.py` is thin: it parses the request and streams the events from `stream.run_turn`. `services.py` wires the real runtime, STT and TTS around one shared `httpx` client. `python -m voice_agent.api` serves it with uvicorn.

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/session` | none | `{session_id}` |
| POST | `/api/turn` | multipart: `session_id`, `language` (`en` or `hi-en`, default `en`), `audio` (webm/opus) **or** `text`, optional `audio_seconds` | `application/x-ndjson` event stream; 400 if neither audio nor text |
| POST | `/api/turn/{turn_id}/client-timings` | `{t_speech_end, t_first_audio}` (epoch ms) | 204; appended to `logs/client_timings.jsonl` |
| GET | `/api/session/{id}/state` | none | current graph state from `TurnRunner.state` |
| GET | `/api/health` | none | static: `ok`, `llm`, `stt` provider per language, `tts` provider (or `client`), `tts_mode` (N10) |

NDJSON events, in order (each line is `{"type": ..., ...}`):
`transcript` (`text`, `source` = `typed` or `stt`, `provider`, `confidence`, `language`) → `understanding` (`turn`, `intent`, `language`, `route`, `slots`, `slot_diff`, `pending_confirmation`) → `search` (`filters`, `sql`, `params`, `results` with scores/contributions, `relaxation`) → `sentence`×N (`index`, `text`, `audio_b64` | `null`, `tts: "server"|"client"`) → `done` (`turn_id`, `turn`, `response_text`, `verdict`, `fallback_used`, `timings_ms`, `usage`).

STT failure (error, no STT configured for the language, or an empty transcript) sequence: `transcript` (empty `text`) → one `sentence` ("Sorry, I didn't catch that. Could you say it again, or type it?") → `done` with `turn: null` and `verdict: null`. No `understanding` or `search` event is sent, and the graph does not run, so session state is unchanged. `fallback_used` carries `stt_error`, `stt_unavailable` or `stt_empty`.

`understanding` and `search` are emitted after `TurnRunner.run` returns (N4), so they arrive together, before the first `sentence`. The browser plays `sentence` audio in a queue as each one arrives and stamps `t_first_audio` on the first playback start. Each turn is logged once to `logs/turns.jsonl` by the API (N5).

## 11. Latency instrumentation (J4)

Implemented. The `done` event carries `timings_ms`:
- from the graph: `nlu`, `search`, `rank` or `relax`, `compose`, and the graph total as `pipeline`;
- from the API: `stt` (audio turns), `first_audio_ready` (clock from request start to the first `sentence` event), `tts` (sum of TTS calls) and `server_total`.

The browser stamps `t_speech_end` (button release, or typed submit) and `t_first_audio`, and posts them to `/api/turn/{turn_id}/client-timings`. Headline metric = `t_first_audio − t_speech_end`, written to `logs/client_timings.jsonl` as `speech_end_to_first_audio_ms`. The UI latency panel shows the stages. `scripts/latency_report.py` joins the two logs by `turn_id` and prints p50/p95 per stage, split by `tts_mode`.

## 12. Data store (`src/voice_agent/db/schema.sql`)

Tables: `listings` (index on `(body_type, fuel, city, price_inr)`), `aliases(alias, canonical, kind)` with a `gin (alias gin_trgm_ops)` index, `city_neighbors`, plus the LangGraph checkpoint tables (created by the saver's `setup()`). `seed.py` loads the CSVs if `listings` is empty. The turn log is `logs/turns.jsonl` (one JSON record per turn: the runner's `TurnResult` from the CLI and eval, the API's richer record from the server) and browser timings go to `logs/client_timings.jsonl`; the `turn_log` table exists in the schema but is reserved and not written: the JSONL files are the log (N5).

## 13. Failure modes & fallbacks (H5, I2)

| Failure | Detection | Behaviour |
|---|---|---|
| Mic denied / broken | browser error | typed input box |
| STT error/timeout/empty | `ProviderError` or empty text | spoken "Sorry, I didn't catch that" (`transcript` → `sentence` → `done`, see §10); state unchanged; `stt_error` / `stt_empty` |
| Sarvam STT error/timeout | `ProviderError` in `FailoverSTT` | same audio to Groq Whisper (dropdown picks English or Roman-script Hinglish prompt); `stt_failover` (N14) |
| No Sarvam key | `make_stt` | Groq Whisper for English; Hinglish gets a Roman-script prompt; `stt_hinglish_groq` |
| Postgres connection dropped | pool `check` on checkout | broken connection replaced before use; the turn runs normally (N15) |
| LLM 429/5xx/timeout | `ProviderError` after backoff | failover to alternate LLM → else rules-only extractor / template composer |
| Validator fails twice | `Verdict.ok == False` | deterministic template response |
| TTS quota/outage, empty audio, or no key | `ProviderError` / empty bytes / `tts is None` | `tts: "client"` → browser `speechSynthesis`; `tts_client` (N12) |
| DB down at startup | lifespan opens the DB | the app fails to start; compose `depends_on: service_healthy` prevents start-up races |
| DB lost after startup | exception in the graph | error turn (`route="error"`, M5); `/api/health` stays `ok` (N10) |
