# Decision Register — Vyngo Voice Vehicle Search

Status legend: `OPEN` · `LEANING` · `DECIDED`
Each decision, once answered, records: **Decision · Rejected alternative · Why**. This is the same format the presentation asks for (§6.3), so the slides can be built from this file.

---

## A. Framing & scope

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| A1 | Which role is this submission for (intern / SDE / tech lead)? | Sets the bar: tech lead needs ≥80 and ≥17/20 on tradeoffs, plus answers on outages, 200 concurrent sessions and ₹/conversation. | DECIDED |
| A2 | Language scope: English only, Hinglish input, Hinglish spoken output? | Affects the STT vendor, slot normalisation, TTS voice and eval utterances. | DECIDED |
| A3 | Which stretch goals (max 2)? Options: Hinglish, noisy audio, streaming, explainable reranker, cross-turn memory, ₹ cost estimate. | Each one costs hours. Some are almost free given other choices (e.g. the explainable reranker). | DECIDED |
| A4 | How do the ~12–16 h get split across build, eval, slides and rehearsal? | The demo has to work first time, so rehearsal time is not optional. | LEANING |
| A5 | What clarifying questions do we send Vyngo? (They say questions are free.) | Avoids "wrong assumptions silently baked in". | DECIDED |

### A — Answers

- **A1 — SDE.** The bar sits between intern (≥60 + live demo) and tech lead (≥80, ≥17/20 tradeoffs). Target: ≥80 overall, with a credible 3-tradeoff section and a concrete scale answer. Treat the tech-lead Q&A topics (outage, 200 sessions, ₹/conv) as "prepared answers", not built features.
- **A2 — English first, Hinglish second.** Phase 1: English end to end, including eval. Phase 2: Hinglish input (transcription + slot normalisation + eval utterances). Spoken output language is decided under H3.
  - *Consequence:* the design must not block Hinglish later. Pick an STT with Hinglish support from day one (H2), and keep normalisation/alias tables language-agnostic (D2).
- **A3 — Claimed stretch goals: Hinglish + explainable reranker.** (Final, decided 2026-10-19.)
  - Chosen: **Hinglish + explainable reranker.** Hinglish is already a named "plus" in the core task. The reranker comes almost free from E2 and directly answers Q&A #2.
  - Streaming TTS can still be built as our **latency mitigation (J5)** without claiming it as a stretch goal.
  - Noisy audio: lowest priority. Prepare a verbal answer only.
- **A4 — 2 days for coding + development; slides optional within that window.** Note: the brief requires slides (PDF) at submission, so if they aren't made in these 2 days, they still need a slot before the 24h-before deadline. Proposed split (to be confirmed):
  - **Day 1, core correctness (text-in/text-out):** catalog generation, slot extraction, filter builder + ranking, conversation state, response composer + validator, text eval harness at ≥90%.
  - **Day 2, voice + delivery:** STT/TTS, browser push-to-talk, latency instrumentation + one mitigation, Docker + README, Hinglish pass, slides, **≥2 full rehearsals**.
  - Rule: if Day 1 overruns, cut the stretch goals, never rehearsal.
- **A5 — Send no questions.** *Consequence:* every assumption must be written down explicitly (see "Assumptions" below) and surfaced in the README and slides. That turns "silently baked in" into "stated and defended".

### Assumptions (stated, not asked)

Fill this in as decisions are made; it goes into the README verbatim.

1. Prices are in INR; "5 lakh ke andar / under 5 lakh" means `price <= 500000` (to confirm under D5).
2. A localhost demo on the presenter's machine is acceptable; evaluators run it via Docker + README.
3. "Around X" means a hard cap of X + 10%, ranked by closeness to X.
4. "Purpose" never filters; it only boosts ranking and appears as a spoken reason.
5. Catalog listings are synthetic; model specs come from public spec pages (see CITATIONS.md) and may differ slightly from manufacturer data.
6. …

## B. Data / catalog

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| B1 | Source: an open dataset (Kaggle etc.), fully synthetic, or a hybrid (real make/model specs + synthetic listings)? | Needs ≥100 rows with all required fields. Public Indian *commercial* vehicle datasets are rare; most are passenger cars. | OPEN |
| B2 | Schema: required fields + extras (variant, owners, seller type, listing date, description, image?) | Extras give follow-up questions something to answer, and give the reranker signals. | OPEN |
| B3 | Canonical vocabularies for body type, fuel, city, purpose. | Filters need closed sets; "chhota truck" and "pickup" must map to a canonical value. | OPEN |
| B4 | How does "purpose" (city delivery, long haul, construction…) map to hard filters vs ranking signals? | "Purpose" is fuzzy. Deciding whether it is a wall or a preference is a correctness question. | OPEN |
| B5 | Store: SQLite, DuckDB, Postgres, or a search engine (Meilisearch/Typesense/Elastic)? | This is one of the example tradeoffs in the brief. | OPEN |
| B6 | Is generation reproducible (seeded script checked into the repo)? | Evaluators re-run the eval, so expected results must stay stable. | OPEN |
| B7 | Do we deliberately seed edge cases (e.g. a 5.0L-exact truck, zero CNG trucks in a city, near-duplicate models like Ace / Ace Gold)? | Makes the zero-result and boundary demos predictable. | OPEN |

### B — Answers

- **B1 — Hybrid: curated real-model spec table + seeded listing generator.** DECIDED
  - *Rejected:* public dataset. A Kaggle/web search (2026-10-19) found no free Indian used-commercial-vehicle dataset. Hits were paid databanks (Autobei/ACG) or passenger-car sets, and none had payload/GVW + papers flag.
  - *Rejected:* fully synthetic models. Fake makes/models fail the sniff test in a live demo.
  - *How:* `data/models.csv` holds ~25–35 real variants (Tata Ace family, Mahindra Bolero Pik-Up/Maxx, Ashok Leyland Dost, Maruti Super Carry, Eicher Pro, Tata Intra/Yodha, Piaggio Ape…) with spec values (payload, GVW, fuel options, body type, new-price band) sourced from public spec pages such as trucksbuses.com and cited in `CITATIONS.md`. A seeded script (`fixed seed`) generates 150–200 listings: year, km, price (depreciated from new price + noise), city, owners, papers flag.
- **B2/B7 — Extras: follow-up fields, planted edge cases, alias table, free-text description.** DECIDED
  - Follow-up fields: `variant, owners, registration_state, seller_type, listing_date`.
  - Planted edge cases: listings at exactly ₹5,00,000; one city with zero CNG trucks; near-duplicates (Ace / Ace Gold / Ace Mega).
  - Alias table: `aliases(alias, canonical, kind)` for make/model/city/body type/fuel, including Hinglish ("chhota haathi" → Tata Ace, "Bombay" → Mumbai). Feeds normalisation (D2).
  - Free-text description: **generated from the row's own structured fields by template**, so it contains no fact that isn't in a column. It is **never spoken verbatim** by the response layer (F1). Reason: free text is unverifiable by the validator (F3).
- **B4 — Purpose is a soft ranking signal, never a filter.** DECIDED
  - Purpose → ranking boosts (e.g. city delivery → lower payload/GVW, CNG/EV, smaller body; long haul → diesel, higher payload). The matched boost is spoken as a reason.
  - *Rejected:* purpose → inferred hard filters. An inferred constraint is not a stated one; it would create avoidable zero-results and breaks "only stated constraints are walls".
- **B5 — Postgres in Docker.** DECIDED
  - *Why over SQLite:* production-like, a natural fit with the Docker preference, and it unlocks **`pg_trgm`** (fuzzy matching for "S" → "Ace" against the alias table) and optionally **`pgvector`** (semantic alias/RAG lookup) inside the same store. No extra search engine needed.
  - *Rejected:* SQLite (no trigram/vector without extensions; weaker scale story). Meilisearch/Typesense (splits filtering and ranking across an engine and code; one more container).
  - *Cost:* one more container + startup ordering (healthcheck) + seeding on boot. Must still meet the ≤10-min README target.
- **B3 / B6 —** canonical vocabularies are defined in code (enums) and mirrored in the alias table; generation is deterministic (fixed seed, checked-in CSV output) so eval expectations stay stable. DECIDED (follows from B1/B2)

## C. Overall architecture

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| C1 | Cascaded STT → LLM → TTS vs speech-to-speech (e.g. Gemini Live / OpenAI Realtime)? | Named tradeoff in the brief. Cascaded keeps slot state and filters inspectable. | OPEN |
| C2 | Orchestration: plain Python pipeline, LangChain, LangGraph, or another framework (Pipecat, LiveKit Agents)? | Every component must be "findable in code" and explainable line by line. Framework abstraction can hide the seams. | OPEN |
| C3 | Turn model: push-to-talk, file upload per turn (simple), or streaming websocket? | Drives latency, complexity, and how well the demo holds up. | OPEN |
| C4 | Process layout: one FastAPI service, or several containers (app / STT / DB)? | "One process is fine." Docker-compose is still useful for a ≤10-min setup. | OPEN |
| C5 | Component interfaces: what does each seam look like (e.g. `STT.transcribe(audio) -> Transcript`)? | Q&A #3: "what's the interface that makes replacing it cheap?" | OPEN |

### C — Answers

- **C1 — Cascaded STT → understanding → search → response → TTS.** DECIDED
  - *Rejected:* speech-to-speech (Gemini Live / OpenAI Realtime). It is lower latency, but slots, executed filters and spoken numbers become hard to inspect and impossible to validate before audio is produced, which hits hard requirements #2 and #3.
  - *Cost we accept:* extra latency from serial stages. Mitigated by streaming TTS (C3) and measured per stage (J4).
- **C2 — LangGraph for orchestration; LangChain only for model/provider wrappers.** DECIDED
  - Graph nodes map 1:1 to the brief's components: `stt → understand → update_state → search → (zero_result_relax | rank) → compose → validate → tts`, plus a `follow_up` branch. The typed graph state *is* the conversation state (G1) and is dumped every turn.
  - *Rejected:* a LangChain tool-calling agent (the LLM decides whether and how to search, which is non-deterministic and hides seams). Plain Python is the runner-up: equally explainable, but we'd hand-roll the conditional routing.
  - *Rule:* business logic (filter builder, ranker, validator) lives in plain Python modules with no LangChain imports; LangGraph only wires them. Keeps every line explainable and the components swappable.
- **C3 — Push-to-talk upload; TTS streamed back.** DECIDED
  - Browser records while the button is held; on release it POSTs the clip and stamps `t_speech_end`. The backend streams TTS audio chunks; the browser plays from the first chunk and stamps `t_first_audio`. Slots/filters/results/timings are returned as JSON alongside (or via a separate response) for on-screen display.
  - *Rejected:* full-file response (worse time-to-first-audio); bidirectional websocket streaming (too many failure modes for 2 days).
- **C4 — docker-compose: `ui` + `app` (FastAPI) + `db` (Postgres).** DECIDED
  - UI kept deliberately thin (a static build served by nginx, or a minimal Vite app): PTT button, audio playback, transcript, a slot-state panel, executed SQL, top-3 with score breakdown, latency table, typed-input fallback.
  - *Cost:* a third container + CORS config. *Guardrail:* no UI framework work beyond the panels above ("zero polish required").
- **C5 — Component interfaces.** LEANING. Each seam is a Python `Protocol` with one implementation per vendor, chosen by config:
  - `SpeechToText.transcribe(audio: bytes, lang_hint) -> Transcript(text, confidence, latency_ms)`
  - `SlotExtractor.extract(text, state) -> TurnIntent(intent, slot_updates, reference)`
  - `CatalogSearch.search(filters: Filters) -> list[Listing]` · `Ranker.rank(listings, prefs) -> list[Scored]`
  - `ResponseComposer.compose(results, state) -> Response(text, facts_used)` · `Validator.check(response, records) -> Verdict`
  - `TextToSpeech.stream(text) -> AsyncIterator[bytes]`

## D. Understanding (NL → filters)

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| D1 | LLM-generated SQL (text-to-SQL) vs LLM → typed slot JSON → deterministic SQL builder? | Hard requirement #2: a stated constraint is a wall. Free-form SQL from an LLM can silently drop a `WHERE`. | OPEN |
| D2 | Where does RAG actually help? Candidates: schema/few-shot retrieval, value normalisation (make/model/city aliases), fuzzy entity matching ("S" → "Ace"), FAQ/spec lookup for follow-ups. | We need a concrete job for RAG, not RAG for its own sake. | OPEN |
| D3 | Rules vs LLM vs a hybrid (rules for numbers like "5 lakh", LLM for the rest)? | Latency, cost, determinism, Hinglish coverage. | OPEN |
| D4 | Intent taxonomy: new_search, refine, correct, follow_up, relax, reset, chit-chat/out-of-domain? | Corrections and follow-ups are hard requirements. | OPEN |
| D5 | Budget semantics: is "5 lakh ke andar" `<=` or `<`? What about "around 5 lakh" or "5–7 lakh"? | Boundary bugs here are exactly what the eval will catch. | OPEN |
| D6 | Low-confidence handling: when do we ask a clarifying question instead of searching? | Q&A #1 (STT mishearing). | OPEN |
| D7 | Slot validation layer: Pydantic schema plus canonical-value checks after the LLM? | The mechanism that catches bad extractions before they hit SQL. | OPEN |

### D — Answers

- **D1 — LLM fills a typed slot schema (function calling) → deterministic, parameterized SQL builder.** DECIDED
  - Options considered (kept for the tradeoff slide):
    1. **Slots JSON → SQL builder** ✅ chosen. One source of truth (the slot state); every stated constraint maps to exactly one `WHERE` clause by code; the eval compares filter dicts exactly; no SQL injection surface.
    2. **Text-to-SQL + guard** ✗ rejected. LLM writes SQL (RAG over schema + few-shot); a parser verifies the `WHERE` clauses match the extracted slots. Looks more "AI", but gives two sources of truth that can disagree, plus SQL parsing edge cases, and the guard ends up re-implementing the builder anyway.
    3. **Pure text-to-SQL** ✗ rejected. The LLM can silently drop or loosen a constraint ("under 5 lakh" → no price filter), which is the cap-at-40 failure mode; also needs read-only DB roles and statement sandboxing.
  - *Where text-to-SQL would win:* many tables and open-ended analytical questions ("average price of diesel pickups in Pune by year"). Not our problem shape: one table, five slots.
- **D2 — Retrieval is used for: value normalisation, schema retrieval, follow-up grounding.** DECIDED
  - **Value normalisation (primary RAG job):** raw mention → canonical value via the alias table, using exact match → `pg_trgm` similarity → (optional) `pgvector` embedding similarity, with a confidence score. Low confidence → clarify (D6). Answers Q&A #1 ("Ace" heard as "S").
  - **Schema retrieval:** column descriptions + allowed values for the slot schema are retrieved/injected into the extraction prompt from one source (the enums), so prompt and validator never drift. Low leverage with one table; kept small.
  - **Follow-up grounding:** fetch the referenced listing **by ID** (not vector search) and answer only from its fields.
  - *Not chosen:* few-shot retrieval (static few-shots are enough at this size; revisit if Hinglish eval fails).
- **D3 — Hybrid extractor.** DECIDED
  - Deterministic parsers for money/numbers/units ("5 lakh", "4.5L", "paanch lakh", "50 hazaar km", "1 ton") **override** LLM numeric output.
  - LLM (function calling) handles intent, body type, fuel, city, purpose, corrections, references.
  - Normaliser (D2) maps every categorical value to canonical form; Pydantic rejects anything outside the enums.
  - Bonus: a rules-only mode doubles as the **LLM-outage fallback** and a key-free eval path (I4).
- **D5 — Budget semantics.** DECIDED
  - "under / andar / tak / max / below X" → `price <= X`.
  - "X–Y" / "between X and Y" → `price BETWEEN X AND Y`.
  - "around / lagbhag / approx X" → hard `price <= 1.10·X`, ranking prefers closeness to X. (Stated in Assumptions.)
  - "above / se zyada X" → `price >= X`.
- **D7 — Slot validation.** DECIDED. Pydantic models with enum-typed fields + range checks (price 50k–50L, year 2005–2026); invalid → slot dropped and logged, never passed to SQL.

## E. Search & ranking

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| E1 | Which slots are hard filters, and which are soft preferences? | Rubric: "filters honored". | OPEN |
| E2 | Ranking function: weighted score (price fit, km, year, papers_verified, payload fit) with weights exposed? | Q&A #2: "show me the reason in data." | OPEN |
| E3 | Zero-result policy: which slot do we suggest relaxing first, and do we pre-compute the result count for each relaxation? | Hard requirement #4. A suggestion that also returns zero is embarrassing. | OPEN |
| E4 | Is the executed filter/SQL logged and returned to the UI every turn? | Hard requirement #2: extraction must be visible. | OPEN |

### D (cont.) / E — Answers

- **D4 — Six intents:** `search` (new or refine), `correct`, `follow_up`, `relax` (accept a suggested relaxation), `reset`, `out_of_domain`. DECIDED
  - *Rejected:* adding `compare` (+1–2h, not required); a minimal 3-intent set (corrections handled clumsily, which costs search-correctness points).
- **D6 — Low confidence → confirm before searching.** DECIDED
  - If any slot's normalisation score < threshold (or STT confidence < threshold on the token that produced it), ask one short confirmation ("Did you mean Tata Ace?"). High-confidence slots pass straight through. The pending confirmation is stored in state; "haan/yes" commits it, "nahi/no" drops it.
  - *Rejected:* search on the best guess (risks showing wrong results); silently dropping the slot (the user's constraint vanishes).
- **E1 — Hard filters: budget, body type, fuel, city.** DECIDED
  - *Also hard when explicitly stated:* make/model, min payload, max km, min year. Rule: **anything the buyer states as a constraint is a wall; anything inferred (purpose) is a preference.**
  - City is an exact match; nearby-city expansion is only ever offered as a relaxation (E3), never applied silently.
- **E2 — Transparent weighted score.** DECIDED
  - `score = Σ wᵢ · fᵢ` over normalised features in [0,1]: price headroom vs budget, low km, newer year, papers_verified, purpose fit (B4), payload fit. Weights live in `config/ranking.yaml`.
  - Every result carries its per-feature contribution breakdown, shown on screen (Q&A #2: "the reason in data"). The spoken reason is generated from the top 1–2 contributing features plus their raw catalog values.
  - Counts as the **explainable reranker** stretch goal.
  - *Rejected:* single-key sort (weak reasons); LLM rerank (not explainable in data, adds latency/cost).
- **E4 — Executed filters and SQL are logged and shown every turn.** DECIDED (hard requirement #2).

## F. Response & anti-hallucination

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| F1 | Pure template responses, LLM phrasing over record IDs, or LLM + validator? | 15 pts. "A prompt alone is not a mechanism." | OPEN |
| F2 | Validator design: extract every number/entity from the output and check it against the returned records; on failure, regenerate or fall back to the template? | This is the code-level mechanism. | OPEN |
| F3 | What does the mechanism *not* catch? (e.g. qualitative claims like "great condition", unit confusion, numbers spoken as words in Hindi.) | The rubric rewards stating limits precisely. | OPEN |
| F4 | How are numbers spoken (₹4.8 lakh, "48 hazaar km")? Formatting happens in code, not in the LLM. | Keeps the numbers checkable and makes TTS sound natural. | OPEN |
| F5 | How are follow-up answers ("uska payload kitna hai?") grounded: only from the referenced record's fields? | Hard requirement #4 (follow-up). | OPEN |

### E (cont.) / F — Answers

- **E3 — Zero results: probe relaxations, suggest the smallest one that works.** DECIDED
  - On 0 rows, re-run `COUNT(*)` with each hard slot loosened one at a time: budget +20%, nearby cities (static neighbour map), any fuel, adjacent body type, drop explicit make. Pick the candidate with the smallest change and ≥1 result, and say it with the count: "Pune mein CNG pickup 5 lakh ke andar nahi mila. Budget 6 lakh tak karein toh 4 options hain. Karein?"
  - **Never auto-applied.** Only a `relax` intent ("haan") commits it, as a one-slot update.
  - Cost: up to ~5 extra `COUNT` queries on zero-result turns only (<10 ms each on 200 rows).
- **F1 — LLM phrases from a fact sheet → validator → regenerate once → deterministic template fallback.** DECIDED
  - The LLM receives only a fact sheet: top-3 records (IDs, pre-formatted values, top reason features). No raw catalog, no free-text description.
  - *Rejected:* templates only (robotic; Hinglish templates by hand). Kept as the fallback, so we *do* write them, just as the safety net. Also rejected: placeholder generation (numbers safe, qualitative claims still free).
  - *Latency note:* validation needs the full text before TTS starts, so we validate per sentence and stream TTS sentence by sentence (H4).
- **F2 — Validator checks (all four).** DECIDED
  1. **Numbers:** every numeric token in the output (digits and spoken forms like "4.8 lakh", "48 hazaar", "paanch") is normalised and must equal a value in the fact sheet.
  2. **Entities:** every make/model/city/fuel/body-type term (matched against the alias table) must belong to a returned record.
  3. **Constraint re-check:** before composing, assert every returned record satisfies the active hard filters in Python, as a second, independent check of the SQL builder. Failure → drop the record + log an error.
  4. **Count/order:** exactly the top-k IDs, in rank order; no extra vehicle mentioned.
  - Verdict + violations are logged per turn and shown in the UI debug panel.
- **F3 — What the validator does NOT catch (presented honestly).** DECIDED
  - Qualitative or subjective claims ("well maintained", "great for hills") that contain no number or entity.
  - Wrong attribution *across* the 3 records (vehicle A's km spoken with vehicle B), unless we enforce per-sentence record binding. **Mitigation adopted:** the composer returns structured output (`items: [{listing_id, text}]`, see architecture §9), and each sentence is checked only against its own record. The residual risk is a sentence that mentions a second vehicle, which the entity check catches.
  - Numbers that coincidentally equal another valid field value.
  - Unsupported comparatives ("cheapest in Pune") that sound factual but aren't checked.
  - TTS mispronunciation of a correct number, and STT errors upstream (D6 handles those).
- **F4 — Code pre-formats all numbers for speech.** DECIDED. The fact sheet carries display strings ("₹4.8 lakh", "48,000 km", "1,030 kg payload", "2019 model"); the LLM is told to copy them verbatim; the validator matches exact strings first and falls back to numeric parsing.
- **F5 — Follow-ups are answered only from the referenced record, fetched by ID.** DECIDED. Same validator, with the fact sheet = that one record. A field we don't have (e.g. "service history") → "That's not in the listing" (templated), never guessed.

## G. Conversation state

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| G1 | State shape: slots, last results (ordered IDs), focused vehicle, history, turn log? | Must be inspectable every turn. | OPEN |
| G2 | Correction semantics: replace one slot vs clear dependent slots? | "Update exactly one slot." | OPEN |
| G3 | Reference resolution: "uska", "doosra wala", "the Tata one", mapped to a record ID. Rules or LLM? | Follow-up requirement. | OPEN |
| G4 | Storage: in-memory dict keyed by session vs Redis? | Scale answer (session concurrency). | OPEN |

### G — Answers

- **G1 — Slots carry over unless contradicted; `reset` clears.** DECIDED. A new utterance merges into the slots, and contradicting values replace old ones. "Naya search / start over" → `reset`. Active slots are always on screen so carry-over is visible, never hidden.
  - State shape: `session_id, slots (with source turn + confidence each), pending_confirmation, pending_relaxation, last_results (ordered IDs), focused_listing_id, turn_log`.
- **G2 — A correction replaces exactly one slot.** DECIDED. Diff logged and shown (`fuel: diesel → CNG`); the eval asserts that only that key changed.
  - *Rejected:* clearing dependent slots (theoretically tidier, but violates the rubric's "update exactly one slot").
- **G3 — LLM extracts a reference descriptor; code resolves it to an ID.** DECIDED
  - The extraction call returns `reference: {kind: ordinal|make|model|pronoun, value}`. Code maps it against `last_results`. A bare pronoun ("uska", "it") → `focused_listing_id` (last discussed), else result #1. The resolved ID must be in `last_results`, else ask "Which one: 1, 2 or 3?"
  - *Rejected:* rules only (misses phrasing variety); the LLM returning raw IDs (an invented-ID risk; still needs validation).
- **G4 — LangGraph Postgres checkpointer.** DECIDED
  - Session state persists in Postgres per `thread_id = session_id`: it survives an app restart mid-demo, any app replica can serve any session (scale story), and it gives a full turn history for inspection.
  - *Rejected:* in-memory dict (lost on restart, single-process only); Redis (extra container, no demo benefit; named as the hot-path optimisation if checkpoint writes show up in latency).
  - *Cost:* a checkpoint write per graph step. Measure it in J4; if noticeable, checkpoint only at turn end.

## H. Voice I/O

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| H1 | Interface: browser page or CLI? Note: **mic access from inside Docker is painful for a CLI**; a browser captures audio on the host. | Docker preference + "runs live first attempt". | OPEN |
| H2 | STT vendor: Gemini (audio input), Groq Whisper, Deepgram, Sarvam (Indic), local faster-whisper? | Hinglish quality, latency, free-tier limits. | OPEN |
| H3 | TTS vendor: ElevenLabs, Sarvam, Google TTS, browser `speechSynthesis`, Piper (local)? | Latency to first audio, Hindi voice quality, free-tier quota. | OPEN |
| H4 | Streaming TTS (start playback on the first chunk) vs whole file? | The main latency lever for "first audio back". | OPEN |
| H5 | Fallback path: typed text input if the mic fails; a fallback TTS if the vendor quota runs out? | The rubric still gives 15–21 for "one stage falls back but recovers". | OPEN |

## I. LLM & vendors / keys

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| I1 | Primary LLM: Gemini Flash (free tier) vs Groq-hosted Llama vs others? | Latency, function-calling reliability, rate limits. | OPEN |
| I2 | Free-tier limits: RPM/RPD for Gemini, ElevenLabs monthly characters. Will dev + eval runs + their eval run exhaust them? | They will run the eval; a 429 during grading is a fail. | OPEN |
| I3 | Vendor abstraction: can each vendor be swapped through config? | Q&A #3, and tech-lead Q&A on outages. | OPEN |
| I4 | Can the eval run without keys (recorded LLM responses / rules-only mode), or does it always need live keys? | "We will run it." Setup must be ≤10 min. | OPEN |

### H / I — Answers

Vendor limits below were checked on 2026-10-19 via third-party sources and **must be re-verified on each vendor's own dashboard at signup**.

- **H1 — Browser UI (the `ui` container); mic captured on the host by the browser.** DECIDED (follows from C4). Avoids passing a mic into Docker.
- **H2 — STT: Groq `whisper-large-v3` for the English phase; Sarvam Saaras (codemix mode) for the Hinglish phase.** DECIDED
  - Groq: free, very fast, reported ~20 RPM / ~2,000 RPD. Weak spot: Hindi/Hinglish may come back in Devanagari/Urdu script or mistranscribed.
  - Sarvam: built for Indian languages, with a `codemix` output mode; reported ₹1,000 free credits, ~₹30/hour of audio.
  - Both implement `SpeechToText`; selected by `STT_PROVIDER` env var. The eval reports the pass rate per provider.
  - *Rejected:* Gemini audio input (burns scarce LLM quota); local faster-whisper (slow on CPU in Docker, large image).
- **H3 — TTS: ElevenLabs Flash (streaming) with browser `speechSynthesis` fallback.** DECIDED
  - ElevenLabs docs cite ~75 ms model inference for Flash (network excluded). The free tier is reported at ~10k credits/month, so **TTS is off during eval runs** (the eval checks filters/responses, not audio) to keep the quota for dev + demo.
  - Fallback: on quota/429/outage, the backend returns text with a `tts: "client"` flag and the browser speaks it. This is the rubric's "one stage falls back but recovers" path.
  - Sarvam Bulbul is noted as the Hinglish-voice alternative if ElevenLabs' Hindi pronunciation is poor.
- **H4 — Sentence-level streaming:** compose → validate sentence 1 → TTS sentence 1 streams while sentence 2 is validated. DECIDED (from C3 + F1). This is our measured latency mitigation (J5).
- **H5 — Fallbacks:** typed text input in the UI (skips STT); browser TTS (skips ElevenLabs); rules-only extractor (skips LLM, D3). DECIDED
- **I1 — LLM: a Groq-hosted open model with tool calling as primary; Gemini Flash-Lite as configured alternate/outage fallback.** DECIDED
  - *Why not Gemini primary (your initial preference):* the 2026 free tier is reported to be sharply reduced (~20 RPD on 3.x Flash, more on Flash-Lite; unconfirmed). At ~2 LLM calls per turn, one eval run plus dev would exhaust it, and a 429 during grading is a failed run.
  - The exact Groq model ID is chosen at implementation time from Groq's current list (requirement: reliable tool/JSON calling).
- **I2 — Quota hygiene.** DECIDED. Retry with exponential backoff on 429; one automatic failover to the alternate LLM provider; quota/usage counters logged per turn.
- **I3 — Every vendor is behind its Protocol (C5) and selected by env var;** no vendor SDK imports outside `providers/`. DECIDED
- **I4 — Eval runs live only (real keys).** DECIDED
  - *Consequence / risk:* evaluators must create Groq (+ optionally ElevenLabs/Sarvam) keys, and quota or outages can fail their run.
  - *Mitigations:* the README lists exactly which keys the eval needs (**Groq only**: STT is skipped for text utterances, TTS is off); a preflight check fails fast with a clear message if a key is missing; backoff + failover (I2); each eval result records the provider used.
  - *Rejected:* replay cassettes (not "the real pipeline"); rules-only mode (a different pipeline from the demo).

## J. Eval & latency

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| J1 | Eval input: text utterances, recorded audio, or TTS-generated audio fed back into STT? | "Through the real pipeline." Audio tests STT too. | OPEN |
| J2 | What is checked: executed filters (required), multi-turn sequences (corrections), hallucination validator pass, response contains only catalog numbers? | Pass-rate definition. | OPEN |
| J3 | Eval set size and composition: plain, Hinglish, boundary, correction, zero-result, follow-up, adversarial ("Ace" misheard)? | ≥90% target for the top band. | OPEN |
| J4 | Latency instrumentation: timestamps per stage (speech end, STT done, NLU done, search done, first TTS byte, playback start) and where they're shown? | 10 pts: per-stage breakdown + one mitigation tried. | OPEN |
| J5 | Which latency mitigation do we try and measure (streaming TTS, parallel calls, rules fast-path, smaller model, connection reuse)? | Rubric requires at least one. | OPEN |

### J — Answers

- **J1 — Main suite is text in; a small audio subset goes through STT.** DECIDED
  - Text cases run understanding → state → search → rank → compose → validate (live Groq LLM; TTS off).
  - 3–5 recorded `.wav` clips (real voice, English + Hinglish, one with background noise) also run through STT; STT-induced failures are reported separately, which supports the Q&A #1 discussion.
- **J2 — A case passes when all applicable checks pass:** DECIDED
  1. executed filters == expected (exact dict compare, after canonicalisation);
  2. multi-turn: only the expected slot changed / the follow-up resolved to the expected listing ID;
  3. the validator passed on the first generation (no regenerate, no template fallback).
  - Constraint safety (no returned record breaks a hard filter) is **not** a pass criterion but is **reported as a separate metric**. It should be 100% by construction, and showing it is cheap evidence for "filters, not vibes".
- **J3 — ~25 cases, reported per category.** DECIDED. ~10 English single-turn, ~6 Hinglish, ~3 boundary (exactly ₹5L, "around", ranges), ~3 multi-turn correction, ~2 zero-result (expects the correct relaxation suggestion), ~2 follow-up, ~2 adversarial/misheard ("S" for "Ace" → expects a confirmation prompt). Cases live in `eval/cases.yaml`.
- **J4 — Latency: UI stage table + JSONL log + summary script.** DECIDED
  - Timestamps: `t_speech_end` (browser) → `stt_done` → `nlu_done` → `search_done` → `first_sentence_validated` → `tts_first_byte` → `t_first_audio` (browser). Browser timestamps are posted back so the full speech-end → first-audio number is real, not estimated.
  - `scripts/latency_report.py` prints p50/p95 per stage for the slides.
- **J5 — Mitigation to try and measure: sentence-level streaming TTS (H4), measured before/after.** DECIDED. Second candidate if time permits: run reference resolution / normalisation in parallel with the LLM call, or a rules fast-path that skips the LLM for pure-slot utterances.

## K. Engineering & delivery

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| K1 | Python version, package manager (uv / poetry / pip), project layout. | README in ≤10 min. | OPEN |
| K2 | Docker: single image + compose? Secrets via `.env`? | Setup friction. | OPEN |
| K3 | Testing: unit tests per component, eval as an integration test, CI (GitHub Actions) running lint + tests + key-free eval? | Code quality points. | OPEN |
| K4 | Logging/observability: structured JSON logs per turn (transcript, slots, SQL, record IDs, validator result, timings)? | Visibility requirements + debugging. | OPEN |
| K5 | Agentic-dev guidance docs: CLAUDE.md, ADRs (this file), coding standards, component contracts, definition of done. | Your stated build approach. | OPEN |
| K6 | Citations file for borrowed models, repos, datasets. | Rule #8. | OPEN |

### K — Answers

- **K1 — Python 3.12 + uv; ruff (lint + format); mypy; pytest.** DECIDED. `uv.lock` committed; Docker uses `uv sync --frozen`.
- **K1b — UI: Vite + React (TypeScript), built and served by nginx in the `ui` container.** DECIDED
  - *Guardrail:* functional panels only (PTT, playback, transcript, slots + diff, executed SQL, top-3 with score breakdown, latency table, typed fallback, validator verdict). No design system, no routing, no state library beyond React state.
  - *Rejected:* vanilla JS (less structured as panels grow); Streamlit (awkward for push-to-talk and streamed audio).
- **K2 — docker-compose (`ui`, `app`, `db`); secrets via `.env` (with `.env.example` committed); DB seeded on first boot; healthchecks gate startup order.** DECIDED. Target: `cp .env.example .env` → add Groq key → `docker compose up` → working in ≤10 min.
- **K3 — pytest unit tests for the deterministic core + GitHub Actions (ruff, mypy, pytest) on push.** DECIDED
  - Unit-tested: money/number parser, normaliser, filter builder, ranker, validator, state reducer (correction = one-slot diff), relaxation prober, reference resolver.
  - The live eval runs manually (needs keys); its latest results are committed to `eval/results/`.
- **K4 — Structured JSON logs, one record per turn:** `session_id, turn, transcript, stt_conf, intent, slot_diff, slots, sql, params, result_ids, scores, validator_verdict, fallback_used, timings`. DECIDED
- **K5 — Agent-guidance docs written before coding:** DECIDED
  - `CLAUDE.md`: project map, commands, hard rules (no vendor SDK imports outside `providers/`; the LLM never writes SQL; every spoken number comes from the fact sheet; update `decisions.md` when a decision changes).
  - `docs/architecture.md`: the 7 components, Protocols (C5), graph, state schema, data flow.
  - `docs/standards.md`: layout, typing, error handling, logging format, naming, test conventions.
  - `docs/definition-of-done.md`: tests + types + lint green, eval not regressed, decisions/assumptions updated.
  - CI tests and further rules to be added by you later.
- **K6 — `CITATIONS.md`:** spec sources for `models.csv`, models/vendors used, any borrowed code. DECIDED

## L. Presentation & Q&A prep — DEFERRED (revisit after the build)

One item already answered because it affects instrumentation:
- **L5 — ₹-per-conversation computed from logged usage.** DECIDED. Each turn logs LLM tokens (in/out), STT audio-seconds and TTS characters per provider (added to the K4 log record); `scripts/cost_report.py` converts them to ₹ at paid-tier prices. Feeds the 100k-conversations/month scale answer.


| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| L1 | Demo script: which exact utterances, including correction, zero-result and follow-up? | First-attempt success. | OPEN |
| L2 | Architecture diagram: what, why, hides, replaced-by for each of the 7 boxes. | §6.2. | OPEN |
| L3 | The ≥3 tradeoffs we'll present (picked from C1, C2, D1, B5, H2/H3, F1). | 20 pts. | OPEN |
| L4 | Scale answer at 100k conv/month: first bottleneck, in order (vendor rate limits → serial LLM calls → session state → …), with ₹ numbers. | Rubric names this explicitly. | OPEN |
| L5 | ₹-per-conversation estimate for our stack. | Tech-lead Q&A; also a stretch goal. | OPEN |
| L6 | Prepared answers for the 4 published Q&A questions + noisy audio / vendor outage / 200 concurrent sessions. | They've told us what they'll ask. | OPEN |
