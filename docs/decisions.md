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
6. A bare amount ("budget 5 lakh") means `budget_max`.
7. "Small truck / chhota truck" means body type `mini_truck`.
8. A model-family mention ("Ace", "chhota haathi") filters by family prefix (Ace Gold, Ace CNG, Ace Mega, …), not one variant.
9. Follow-up questions are answered by deterministic templates from the referenced listing (no LLM): zero hallucination risk, lower latency.
10. STT and TTS run in the API layer around the graph; the graph itself is text-in/text-out, so eval and CLI exercise the same graph as voice.
11. Every year phrase includes the year: "after / newer than / 2019 ke baad / since / from 2019" all mean `year >= 2019` (owner decision, 2026-10-20). Buyers often say "after 2019" meaning "2019 or newer"; excluding it would hide listings they meant.
12. …

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
  - *Why over SQLite:* production-like, a natural fit with the Docker preference, and it unlocks **`pg_trgm`** (fuzzy matching of near-misses like "Aace" → "Ace" against the alias table) and optionally **`pgvector`** (semantic alias/RAG lookup) inside the same store. No extra search engine needed.
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
  - **Value normalisation (primary RAG job):** raw mention → canonical value via the alias table, using exact match → `pg_trgm` similarity → (optional) `pgvector` embedding similarity, with a confidence score. Low confidence → clarify (D6). Answers Q&A #1 in part: a near-miss such as "Aace" scores in the confirm band and gets "Did you mean Tata Ace?". A single-letter mishear ("S" for "Ace") has trigram similarity 0 with "ace", so it is reported as not found and the user is asked to repeat. That is a known limit, not something `pg_trgm` fixes.
  - **Schema retrieval:** column descriptions + allowed values for the slot schema are retrieved/injected into the extraction prompt from one source (the enums), so prompt and validator never drift. Low leverage with one table; kept small.
  - **Follow-up grounding:** fetch the referenced listing **by ID** (not vector search) and answer only from its fields.
  - *Not chosen:* few-shot retrieval (static few-shots are enough at this size; revisit if Hinglish eval fails).
- **D3 — Hybrid extractor.** DECIDED
  - Deterministic parsers for money/numbers/units ("5 lakh", "4.5L", "paanch lakh", "50 hazaar km", "1 ton") **override** LLM numeric output, per field (see M3).
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
  - `config/ranking.yaml` must list every feature; an unknown or missing one fails at startup (2026-10-20, review finding 12).
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
  - A bare "no" drops the offer and asks what to change, with no new search (2026-10-20, review finding 2); "no" plus a new value searches with that value. A "yes" accepts even when the LLM labels the turn `search`.
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
  - A spelled-out number with no unit after it ("ek achha option", "a couple of picks") is not checked (2026-10-20, review finding 9). With a unit ("ek lakh", "two owners", "paanch saal") it still fails.
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
  - Enforced in code (2026-10-20, review finding 4): in a `correct` turn, a slot that already had a value and changes is the correction, and empty slots are added as new constraints. If two filled slots would change (budget bounds count as one), nothing is applied and the reply asks which one.
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
- **H2 — STT: Groq `whisper-large-v3` for the English phase; Sarvam Saaras for the Hinglish phase (mode: `translit`, not `codemix`; see N3).** DECIDED
  - Groq: free, very fast, reported ~20 RPM / ~2,000 RPD. Weak spot: Hindi/Hinglish may come back in Devanagari/Urdu script or mistranscribed.
  - Sarvam: built for Indian languages, with several output modes (N3 picks `translit`); reported ₹1,000 free credits, ~₹30/hour of audio.
  - Both implement `SpeechToText`; N3 says how one is chosen per request. The audio eval reports the pass rate per provider.
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
  - Constraint safety is **not** a pass criterion but is **reported as a separate metric**: on turns that declare `expect_filters`, every shown result is checked against the *user's stated constraints* (the case's `expect_filters`), not against the pipeline's own filters, so a dropped or loosened slot shows up. A second count re-checks results against the executed filters; that one is 0 by construction (the search node already runs the same check) and only guards the SQL builder.
- **J3 — ~25 cases, reported per category.** DECIDED. ~10 English single-turn, ~6 Hinglish, ~3 boundary (exactly ₹5L, "around", ranges), ~3 multi-turn correction, ~2 zero-result (expects the correct relaxation suggestion), ~2 follow-up, ~2 adversarial/misheard (a near-miss like "Tata Aace" → expects a confirmation prompt; a single-letter mishear like "S" cannot be matched by trigrams and is a known limit, D2). Cases live in `eval/cases.yaml`.
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
  - `aliases` and `city_neighbors` are replaced from the CSVs on every boot; listings load only into an empty table (2026-10-20, review finding 11).
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

## M. Implementation decisions (taken while building the text loop)

- **M1 — The validator binds every number to its unit.** DECIDED. A number in a sentence is read together with the word after it ("4.85 lakh", "48,000 km", "1 owner") and must match a (value, unit) pair of that sentence's record. Numbers from the title (variant "HD 1.7L VXi", "407 Gold", "Pro 2049") license the bare number only, never "1.7 lakh"; the exact model/variant name is skipped by the number check.
  - *Rejected:* a bag of allowed numbers without units. "₹48,000" would pass because 48,000 is the km value, and "4.85 lakh km" would pass because 4.85 is the price.
  - *Why:* a cheap, code-level way to close unit-swap hallucinations without spelling every number out.
- **M2 — Entity check covers aliases and model families.** DECIDED. The validator scans each sentence for canonical makes/models *and* alias-table surfaces ("Leyland", "AL", "Suzuki", "Benz"); a model name matches the record exactly or as a family prefix ("Ace" for "Ace Gold"). City and fuel words must also be the record's.
  - *Rejected:* canonical names only. "Suzuki Ace Gold" or "the Benz" would slip through.
  - *Why:* the alias table already exists (D2), so the same vocabulary drives both understanding and validation.
- **M3 — Per-field number override.** DECIDED. The parser wins on the fields it found. For a field it missed, the LLM's value is kept unless it equals a number the parser read this turn (the LLM mis-assigned that number, e.g. "80000 km" also returned as `budget_max=80000`). Budget bounds are one group: if the parser found any bound, the LLM's budget is ignored. Only stated bounds are written: a max also clears `budget_target`, a min leaves the max alone, a range or "around X" replaces all three. A km/payload phrase whose direction contradicts the slot ("over 2 lakh km") is dropped, never inverted, and recorded in `NumericSlots.dropped` so the LLM's value for that field cannot re-fill it. A consumed year/km/payload span ends the direction context of the next number, so in "under 50000 km and 1 ton" the "under" binds to the km only.
  - *Rejected:* "parser found any number → drop every LLM number" (the first version). "under 5 lakh, pachaas hazaar se kam chala ho" lost the km wall. Also rejected: always writing all three budget keys, which made "at least 3 lakh" wipe an earlier "under 5 lakh".
  - *Why:* a stated constraint is a wall (hard rule 2); losing one silently is the worst failure.
- **M4 — LLM: Groq `openai/gpt-oss-120b`.** DECIDED (fills in I1). The planned `llama-3.3-70b-versatile` is retired on Groq (404). A `TurnIntent` benchmark on a Hinglish turn: gpt-oss-120b ~1.3 s ok, gpt-oss-20b ~1.2 s ok, qwen3.8-27b ~0.7 s ok. Gemini `gemini-2.5-flash-lite` stays the configured fallback (`FailoverLLM`).
  - *Rejected (for now):* qwen3.8-27b as default. Faster, but chosen as the latency-mitigation candidate rather than the eval default; cost if wrong is ~600 ms per LLM call.
  - *Why / cost:* quality first for the eval. The free tier allows **8,000 tokens/min per model**; at ~2.5k tokens per turn that is ~3 turns/min, so it is the first bottleneck (it explains the 7–20 s waits in eval latency) and the first line of the L4 scale answer. Mitigations: extractor and composer on different models (separate token buckets), low reasoning effort, failover on 429 instead of waiting.
- **M5 — `TurnRunner` is the error boundary.** DECIDED. `TurnRunner.run` catches any exception from the graph, logs it, and returns a templated error turn (`route="error"`, `fallback_used=["error"]`) built from the latest checkpoint; the session continues. The eval counts an error turn as a failure.
  - *Rejected:* letting exceptions reach the CLI/API (one bad turn ends the session), or try/except in every node (business logic buried in error handling).
  - *Why:* one seam, one place to reason about failure; hard rule 7 (no silent failure) still holds through the log and `fallback_used`.
- **M6 — Follow-ups are answered by template.** DECIDED (narrows F5). The referenced listing is fetched by ID and `templates.follow_up` fills one sentence from its formatted fact item; no LLM call.
  - *Rejected:* LLM phrasing + validator for follow-ups. A second LLM call per turn for a one-fact answer, with hallucination risk to manage.
  - *Why:* zero hallucination risk, lower latency and quota use (Assumption 9). Cost: follow-up answers are English-only and less varied in phrasing.

## N. Implementation decisions (taken while building the voice loop)

- **N1 — Reply language.** DECIDED. The composer already replies in the detected language (English or Roman-script Hinglish). Templates stay English.
  - *Rejected:* translating every template into Hinglish.
  - *Why:* a code-switching buyer understands the English templates, and translating them all would be gold-plating. Cost if wrong: Hinglish users hear English on zero-result, confirm and follow-up turns.
- **N2 — Sentence-level TTS.** DECIDED. One vendor call per sentence, returning complete MP3 bytes. Each `sentence` NDJSON event carries `audio_b64`. `TTS_MODE=sentence|whole` lets J5 compare the two; "whole" means one call for the full text.
  - *Rejected:* streaming raw audio chunks over the NDJSON channel.
  - *Why:* complete MP3 per sentence is simple to queue in the browser and keeps the validator-then-speak order (H4). Cost if wrong: the first sentence still waits for its own full synthesis (a few hundred ms).
- **N3 — STT is chosen per request by the `language` form field.** DECIDED. *Superseded by N14 when `SARVAM_API_KEY` is set; it still holds without one.*
  - `en` → `GroqSTT` (`whisper-large-v3`, `language=en`).
  - `hi-en` → `SarvamSTT` (`saaras:v3`, mode `translit`) when `SARVAM_API_KEY` is set.
  - Otherwise `hi-en` → `GroqSTT` with no language and a Roman-script prompt, recording fallback `stt_hinglish_groq`.
  - *Rejected:* Sarvam `codemix` mode (the H2 wording), and a global `STT_PROVIDER` switch.
  - *Why:* codemix returns Hindi words in Devanagari, and our parser and aliases are Roman script. A per-request choice lets one server handle both languages. Cost if wrong: transliteration spelling variants ("panch") the parser doesn't know.
- **N4 — Understanding and search events are emitted after `TurnRunner.run` returns.** DECIDED. The graph runs atomically.
  - *Rejected:* streaming node-by-node events out of the graph.
  - *Why:* it keeps `graph/` text-in/text-out. Cost: those panels update a few seconds later than true streaming would. They still arrive before audio.
- **N5 — API logging.** DECIDED. The API builds the runtime with `log_turns=False` and writes its own richer record (TurnResult + turn_id + STT/TTS timings + tts_mode) to `logs/turns.jsonl`. Browser timings go to `logs/client_timings.jsonl`, keyed by `turn_id`.
  - *Rejected:* two records per turn from the runner and the API.
  - *Why:* one record per turn (K4) with the stages only the API sees.
- **N6 — LLM latency knobs** (second J5 lever, aimed at the 8k TPM bottleneck from M4). DECIDED.
  - `LLM_REASONING_EFFORT=low` is passed to Groq gpt-oss models.
  - Optional `GROQ_COMPOSE_MODEL` puts the composer on its own model and token bucket. Default unset = same model.
  - *Rejected:* a rules fast-path that skips the LLM (J5 second candidate), as more code for this scope.
  - *Why:* both are config only. Cost if wrong: lower reasoning effort may cost some extraction quality.
- **N7 — Audio eval clips.** DECIDED. `scripts/make_eval_audio.py` synthesises stand-in clips (one with added noise) via ElevenLabs. They are labelled `synthetic: true` in `eval/audio/cases.yaml` and in the results. The user may overwrite them with real recordings under the same names.
  - *Rejected:* committing only real recordings (none exist yet).
  - *Why:* the audio path needs an eval now. J1 asked for real voice, so the README says which kind was used. Cost: synthetic speech is cleaner than a buyer in a truck yard, so STT results are optimistic.
- **N8 — Prices** live in `config/prices.yaml`, with the date they were checked and a "re-verify" note. DECIDED. The cost report converts USD → INR with one rate from that file.
  - *Rejected:* prices hard-coded in the script.
  - *Why:* the numbers change and some are unverified (ElevenLabs Flash row, the USD→INR rate).
- **N9 — Compose sets `API_HOST=0.0.0.0` and `API_PORT=8000` under `environment:`.** DECIDED. `.env.example` has `API_HOST=127.0.0.1` for local runs, and `env_file` would inject it into the container, where nginx could not reach the app.
  - *Rejected:* editing `.env.example`, which breaks local dev.
  - *Why:* `environment:` wins over `env_file`.
- **N10 — `/api/health` is static.** DECIDED. The lifespan opens the DB and fails fast at startup if it is down, so `ok: true` means the DB was up when the app started. The body reports the LLM provider, the STT provider per language, the TTS provider (or `client`) and `tts_mode`. There is no per-request DB ping and no 503.
  - *Rejected:* a DB ping on each health call.
  - *Why:* the compose healthcheck only needs "the app started". A DB lost after startup surfaces as error turns (M5), not as a health failure. Cost: health does not notice a DB that dies later.
- **N11 — Every vendor response body is parsed through `providers.http.json_body`.** DECIDED. A malformed 2xx body (not JSON, not an object, bad field types) becomes `ProviderError`.
  - *Rejected:* letting `resp.json()` errors propagate.
  - *Why:* `ProviderError` is the vendor-failure exception callers catch (standards §3); anything else would crash the turn.
- **N12 — Empty TTS audio is a TTS failure.** DECIDED. `_speak` raises `ProviderError` on empty bytes, records `tts_client` and the browser speaks the rest of the turn.
  - *Rejected:* sending an empty `audio_b64`.
  - *Why:* the browser would play silence and the user would hear nothing (hard rule 7: no silent failure).
- **N13 — Reply language is decided in code, not by the LLM.** DECIDED. `understanding/language.py` marks a turn Hinglish if it contains Devanagari or a Roman-script Hindi grammar word ("mein", "chahiye", "dikhao", "nahi", ...); otherwise English. The pipeline overwrites the LLM's `language` field with it, also on the rules fallback.
  - *Rejected:* the LLM's own `language` field (with a sharper prompt).
  - *Why:* in live runs the LLM tagged plain English with "lakh" or an Indian city ("Diesel pickup in Delhi under 8 lakh") as Hinglish and replied in Hinglish. A word list is deterministic, unit-tested and explainable, and the rules fallback previously always said English. Cost if wrong: a Hinglish turn with no listed Hindi word (e.g. "Pune, 5 lakh, Tata Ace") gets an English reply, which a code-switching buyer still understands (N1).
  - Note: this works on the transcript. If STT translates Hindi speech to English (Whisper with `language=en` does), the reply is English; N14 removes that case when Sarvam is keyed.
- **N14 — With a Sarvam key, Sarvam transcribes all speech; Groq Whisper is the failover.** DECIDED (2026-10-20, after the live mic test).
  - `make_stt` maps both `en` and `hi-en` to `FailoverSTT(SarvamSTT, GroqSTT)`; the Groq side keeps the N3 flavour for the chosen language. A turn served by Groq records `stt_failover`. Without a Sarvam key, N3 applies unchanged.
  - *Rejected:* (a) keeping the UI dropdown as the STT switch; (b) Whisper with no forced language first, re-sending Hindi/Urdu turns to Sarvam.
  - *Why:* in the mic test the buyer switched to Hindi with the dropdown still on English. Whisper with `language=en` translated the Hindi into English, so the slots and reply were English and nothing flagged it. On the 5 eval clips Sarvam `translit` got all 3 English clips right (better than Whisper on "five lakh") and both Hinglish clips in Roman script, at 120–300 ms against Whisper's 220–570 ms. (b) costs two STT calls on Hindi turns and rests on Whisper's language guess. Cost if wrong: Sarvam is paid (about ₹0.04 a 5-second turn) and the English comparison is 3 synthetic clips; on a Sarvam outage the dropdown again decides how Groq transcribes.
  - *Update (2026-10-20):* the UI dropdown is removed. The UI always sends `hi-en`, so the Groq failover auto-detects (Roman-script prompt) instead of translating Hindi into English; the browser voice follows the turn's code-decided language (N13). Without a Sarvam key every turn is then Groq auto-detect and records `stt_hinglish_groq`. The API still accepts `language=en`.
- **N15 — Checkpointer on its own checked pool; every pool checks connections on checkout.** DECIDED (2026-10-20).
  - `build_runtime` gives `AsyncPostgresSaver` a small `AsyncConnectionPool` (max 4, dict rows, `prepare_threshold=0`, as LangGraph requires) and passes `check=AsyncConnectionPool.check_connection` to both pools.
  - *Rejected:* `AsyncPostgresSaver.from_conn_string` (one long-lived connection), and sharing the catalog pool (its code reads tuple rows).
  - *Why:* in a live run the checkpointer's single connection was dropped (WinError 10053) and every later turn failed until a restart. Verified: after `pg_terminate_backend` on all app connections the next turn succeeds and keeps its slots. Cost: one extra round trip to Postgres per checkout (under 1 ms locally).
- **N16 — An unsupported city, make or model keeps the rest of the turn.** DECIDED (2026-10-20, code review finding 1). The turn's other valid updates are saved and any pending confirmation or relaxation is cleared, but no search runs; the reply names what is not covered. *Rejected:* dropping the whole turn (the buyer's budget and make vanished); searching without the unknown value (shows vehicles from places the buyer did not ask for).
- **N17 — A failed turn rolls back.** DECIDED (2026-10-20, review finding 5). `TurnRunner` reads the checkpoint before the turn; if the graph raises, it writes that state back with `aupdate_state` (or `MEMORY_DEFAULTS` on a first turn), so "say that again" repeats cleanly. *Rejected:* `durability="exit"` (LangGraph 1.2 still saves on an exception); keeping the change and naming it in the reply. *Cost:* one checkpoint read per turn.
