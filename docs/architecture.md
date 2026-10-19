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
 │ validator, latency        │  stream            │ [5] Compose ─► Validate ─► TTS (per sent.)│   │ turn_log     │
 │ Audio queue player        │                    │                                          │   └──────────────┘
 └───────────────────────────┘                    │ [7] telemetry: timings, usage, turn log   │
                                                  └──────────────────────────────────────────┘
 eval/ ── runs cases through the same graph (text in, TTS off) ──► pass rate per category
```

Containers (`docker-compose.yml`): `ui` (nginx serving the built React app, proxies `/api` → `app`), `app` (FastAPI, uvicorn), `db` (Postgres 16 with `pg_trgm`; `pgvector` optional).

## 2. The seven components → code

| # | Component (brief §2) | Package / path | Hides | Swap target |
|---|---|---|---|---|
| 1 | Voice interface | `ui/src/` (`Recorder`, `AudioQueue`, panels); server side `src/voice_agent/api/` | MediaRecorder, streaming fetch, playback | Twilio/WebRTC client |
| 2 | STT | `src/voice_agent/stt/` (Protocol) + `providers/groq_stt.py`, `providers/sarvam_stt.py` | Vendor API, audio format | Any `SpeechToText` impl |
| 3 | Understanding | `src/voice_agent/understanding/` — `numbers.py` (money/units parser), `extractor.py` (LLM tool call), `normalizer.py` (alias + pg_trgm), `schema.py` | Prompting, LLM vendor, alias fuzziness | Fine-tuned NLU / different LLM |
| 4 | Catalog + search | `src/voice_agent/catalog/` — `filters.py` (slots → SQL), `search.py`, `ranker.py`, `relax.py` | SQL, ranking weights | Elastic/OpenSearch, learned ranker |
| 5 | Response + TTS | `src/voice_agent/response/` — `factsheet.py`, `composer.py`, `templates.py`, `validator.py`; `src/voice_agent/tts/` + `providers/elevenlabs_tts.py` | LLM phrasing, number formatting, TTS vendor | Any `TextToSpeech` impl |
| 6 | Conversation state | `src/voice_agent/state/` — `models.py`, `reducer.py` (slot merge/correction), `references.py` | Merge rules, reference resolution | Redis-backed store |
| 7 | Eval + latency | `eval/` (`cases.yaml`, `run_eval.py`, `audio/`, `results/`); `src/voice_agent/telemetry/`; `scripts/latency_report.py`, `scripts/cost_report.py` | — | — |

Glue: `src/voice_agent/graph/` (LangGraph `StateGraph` wiring only — no business logic).

## 3. Repository layout

```
voice-agent/
├── CLAUDE.md                 # agent guide (start here)
├── README.md                 # run in ≤10 min
├── CITATIONS.md
├── docker-compose.yml
├── Dockerfile                # app image (uv sync --frozen)
├── .env.example
├── pyproject.toml / uv.lock
├── docs/                     # decisions, architecture, standards, definition-of-done
├── data/                     # models.csv, listings.csv, aliases.csv, city_neighbors.csv, README.md
├── scripts/                  # generate_catalog.py, latency_report.py, cost_report.py
├── src/voice_agent/
│   ├── api/                  # FastAPI app, routes, NDJSON event stream
│   ├── config.py             # pydantic-settings; provider selection via env
│   ├── domain/               # enums + shared Pydantic models (Slots, Filters, Listing, ScoredListing…)
│   ├── stt/  understanding/  catalog/  response/  tts/  state/   # components 2–6
│   ├── graph/                # LangGraph nodes + edges
│   ├── providers/            # ONLY place vendor SDKs/HTTP APIs are imported
│   ├── telemetry/            # timers, usage counters, JSON turn logger
│   └── db/                   # schema.sql, seed.py (loads data/*.csv on first boot)
├── tests/unit/               # mirrors src/ layout; no network
├── eval/
└── ui/                       # Vite + React + TS, Dockerfile, nginx.conf
```

## 4. Domain model (`src/voice_agent/domain/`)

All money is **integer INR**. All weights in **kg**. Never floats for money.

```python
class BodyType(StrEnum):  three_wheeler, mini_truck, pickup, cargo_van, lcv, icv, tipper
class Fuel(StrEnum):      diesel, petrol, cng, electric
class City(StrEnum):      mumbai, delhi, bengaluru, pune, hyderabad, chennai, ahmedabad, jaipur, lucknow, kolkata
class Purpose(StrEnum):   city_delivery, long_haul, construction, agriculture, general

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

## 5. Turn pipeline (LangGraph, `src/voice_agent/graph/`)

```
            ┌────────────┐
 audio ───► │ stt        │──┐ (skipped for typed input / eval text cases)
            └────────────┘  ▼
                     ┌──────────────┐
 text ─────────────► │ understand   │  numbers.py + extractor (LLM tool call) + normalizer
                     └──────┬───────┘  → TurnIntent{intent, slot_updates, reference, confidences}
                            ▼
                     ┌──────────────┐
                     │ update_state │  reducer: merge / correct (1-slot diff) / reset / confirm
                     └──────┬───────┘
          ┌───────────┬─────┴───────┬──────────────┬───────────────┐
   needs_confirm   follow_up     search/correct/relax     reset/out_of_domain
          ▼           ▼               ▼                          ▼
   ask_confirm   answer_followup   search ──► 0 rows? ──► relax_probe ──┐
                 (record by ID)       │ ≥1                             │
                                      ▼                                │
                                    rank                               │
          └───────────┴───────────────┴────────────────┬───────────────┘
                                                       ▼
                                   compose ─► validate ─► (fail: regenerate once ─► template)
                                                       ▼
                                                 tts (per sentence, streamed)
```

- Nodes are thin: each calls one component function and writes its result into graph state.
- Conditional edges implement routing; **no LLM decides routing** beyond the intent label from `understand`.
- Checkpointer: LangGraph Postgres checkpointer, `thread_id = session_id` (G4).

### Graph state (`state/models.py`)

```python
class ConversationState(TypedDict):
    session_id: str
    turn: int
    # inputs
    audio: bytes | None
    transcript: str | None
    stt_confidence: float | None
    # understanding
    intent: Intent | None                 # search | correct | follow_up | relax | reset | out_of_domain
    slot_updates: dict[str, Any]
    reference: Reference | None
    # memory (persists across turns)
    slots: Slots
    slot_diff: dict[str, tuple[Any, Any]] # this turn only: key -> (old, new)
    pending_confirmation: PendingConfirmation | None   # D6
    pending_relaxation: Relaxation | None              # E3
    last_results: list[str]               # ordered listing_ids
    focused_listing_id: str | None        # G3
    # search + response (this turn)
    executed_sql: str | None
    sql_params: dict[str, Any]
    results: list[ScoredListing]
    response: ComposedResponse | None
    validator_verdict: Verdict | None
    fallback_used: list[str]              # e.g. ["llm_failover", "template", "client_tts"]
    timings_ms: dict[str, float]
    usage: dict[str, float]               # tokens, audio_s, tts_chars per provider (L5)
```

## 6. Component contracts (Protocols)

```python
class SpeechToText(Protocol):
    async def transcribe(self, audio: bytes, mime: str, lang_hint: str | None) -> Transcript: ...
    # Transcript(text: str, confidence: float | None, provider: str, audio_seconds: float)

class LLM(Protocol):                       # used by extractor + composer; Groq primary, Gemini alt (I1)
    async def call_tool(self, system: str, user: str, tool: type[BaseModel]) -> tuple[BaseModel, Usage]: ...

class SlotExtractor(Protocol):
    async def extract(self, text: str, state: ConversationState) -> TurnIntent: ...

class Normalizer(Protocol):
    async def normalize(self, kind: AliasKind, raw: str) -> Match   # Match(canonical, score, method)

class CatalogSearch(Protocol):
    async def search(self, filters: Filters, limit: int = 50) -> SearchResult  # rows + sql + params
    async def count(self, filters: Filters) -> int

class Ranker(Protocol):
    def rank(self, rows: list[Listing], slots: Slots) -> list[ScoredListing]

class ResponseComposer(Protocol):
    async def compose(self, facts: FactSheet, kind: ResponseKind) -> ComposedResponse

class Validator(Protocol):
    def check(self, response: ComposedResponse, facts: FactSheet, filters: Filters) -> Verdict

class TextToSpeech(Protocol):
    def stream(self, text: str) -> AsyncIterator[bytes]   # raises ProviderError → client TTS fallback
```

Implementations are selected in `config.py` from env (`LLM_PROVIDER`, `LLM_FALLBACK_PROVIDER`, `STT_PROVIDER`, `TTS_PROVIDER`).

## 7. Understanding details (D1–D7)

1. `numbers.py` (deterministic) extracts money/units first: "5 lakh", "4.5L", "paanch lakh", "50 hazaar km", "1 ton", "2018 ke baad". Its numeric results **override** the LLM's.
2. `extractor.py` makes **one** LLM tool call with schema `TurnIntent`. The prompt includes the allowed enum values (generated from `domain` enums — single source), the current slots, the last results (ID + make/model/ordinal), and the pending confirmation/relaxation if any.
3. `normalizer.py` maps every categorical value: exact alias → `pg_trgm similarity()` ≥ `TRGM_ACCEPT` (0.6) → else **low confidence**. Below the accept threshold but ≥ `TRGM_CONFIRM` (0.3) → `pending_confirmation` ("Did you mean Tata Ace?"). Below that → slot dropped and the user is told what wasn't understood.
4. Pydantic validates ranges/enums. Invalid values are dropped and logged, never forwarded to SQL.

## 8. Search, ranking, relaxation (E1–E4)

- `filters.py`: `Slots → Filters → (sql, params)`. One `WHERE` clause per non-null hard field, always parameterized (`%(budget_max)s`). The SQL text + params are returned for display/logging.
- `ranker.py`: `score = Σ wᵢ·fᵢ`, features normalised to [0,1] within the candidate set:
  `price_headroom` (or `price_closeness` when `budget_target`), `low_km`, `newer_year`, `papers_verified`, `purpose_fit`, `payload_fit`. Weights in `config/ranking.yaml`. `contributions` are kept per result.
- `relax.py`: on 0 rows, probe in this order and collect counts: budget +20% → neighbour cities → any fuel → adjacent body type → drop make/model. Suggest the smallest change with ≥1 result. Stored as `pending_relaxation`; applied only on a `relax` intent.
- Defense in depth (F2.3): after SQL, `validator.assert_constraints(rows, filters)` re-checks every row in Python.

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
1. `items[*].listing_id` == top-k IDs, in order; no other make/model mentioned (alias-table scan).
2. Every number token in each sentence (digits + spoken forms via `numbers.py`) ∈ that record's fact values.
3. `intro`/`closing` contain no numbers and no vehicle entities.
4. Constraint re-check of the records (F2.3).

Failure → regenerate once with the violations listed in the prompt → still failing → `templates.py` (deterministic). `fallback_used` records it.

**Follow-ups**: fact sheet = the single referenced listing (fetched by ID). Asked field not in the listing → templated "That isn't in the listing."

**Known limits** (said out loud in the presentation): see decisions F3.

## 10. API (`src/voice_agent/api/`)

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/session` | — | `{session_id}` |
| POST | `/api/turn` | multipart: `session_id`, `audio` (webm/opus) **or** `text` | `application/x-ndjson` event stream |
| POST | `/api/turn/{turn_id}/client-timings` | `{t_speech_end, t_first_audio}` (epoch ms) | 204 |
| GET | `/api/session/{id}/state` | — | current `ConversationState` (minus audio) |
| GET | `/api/health` | — | db + provider key presence |

NDJSON events, in order (each line is `{"type": ..., ...}`):
`transcript` → `understanding` (intent, slots, slot_diff, confidences, pending_confirmation) → `search` (sql, params, results with scores/contributions, relaxation) → `sentence`×N (`text`, `audio_b64` | `null`, `tts: "server"|"client"`) → `done` (validator verdict, fallback_used, timings_ms, usage, turn_id).

The browser plays `sentence` audio in a queue as each one arrives and stamps `t_first_audio` on the first playback start.

## 11. Latency instrumentation (J4)

Server stamps (monotonic): `request_received, stt_done, nlu_done, state_done, search_done, compose_done, validate_done, tts_first_byte, done`. Browser stamps: `t_speech_end` (button release), `t_first_audio`. Headline metric = `t_first_audio − t_speech_end`. Everything goes into the JSONL turn log (`logs/turns.jsonl`) and the UI latency panel.

## 12. Data store (`src/voice_agent/db/schema.sql`)

Tables: `listings` (columns per `data/README.md`, indexes on `(body_type, fuel, city, price_inr)`), `aliases(alias, canonical, kind)` with a `gin (alias gin_trgm_ops)` index, `city_neighbors`, `turn_log` (JSONB per turn), plus LangGraph checkpoint tables (created by the checkpointer's `setup()`). `seed.py` loads the CSVs if `listings` is empty.

## 13. Failure modes & fallbacks (H5, I2)

| Failure | Detection | Behaviour |
|---|---|---|
| Mic denied / broken | browser error | typed input box |
| STT error/timeout | `ProviderError` | spoken/text "Sorry, didn't catch that"; state unchanged |
| LLM 429/5xx/timeout | `ProviderError` after backoff | failover to alternate LLM → else rules-only extractor / template composer |
| Validator fails twice | `Verdict.ok == False` | deterministic template response |
| TTS quota/outage | `ProviderError` | `tts: "client"` → browser `speechSynthesis` |
| DB down | health check | 503 with message; compose healthcheck prevents start-up races |
