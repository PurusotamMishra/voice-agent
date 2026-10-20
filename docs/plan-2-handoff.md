# Plan 2 Handoff (from the Plan 1 "text loop" session, 2026-10-20)

This doc holds what a fresh session needs to write and run **Plan 2**. Read it first, then the four guidance docs it lists. The paste-ready prompt for the new session is in §9.

---

## 1. Where things stand

- **Repo:** `D:\Job\portfolio_projects\voice-agent`. Remote: `origin` = `https://github.com/PurusotamMishra/voice-agent.git`.
- **Branch:** `feat/text-loop`, pushed. All Plan 1 work is on it, as signed commits, one per task, plus the final-review fix commit. `main` holds only the docs and catalog bootstrap commits (9fbb98f, 9adedad). Merging or opening a PR is the user's call; don't do it unasked.
- **Plan 1** is `docs/superpowers/plans/2026-10-19-text-loop.md`, 14 tasks, **all complete**. A final whole-branch review and a fix wave followed, plus one extra fix round for regressions A and B (see §6).
- **Milestone M1 (text loop) is done.** A typed utterance becomes slots, then parameterized SQL, then the ranked top 3, then validated text. Multi-turn state lives in the Postgres checkpointer. M3 (awkward turns) also passes in the text eval.
- **Eval** (`uv run python eval/run_eval.py`, live, about 15 minutes) scored **25/25 = 100%**:
  - Constraint safety against the user's stated constraints: 100% of 44 results.
  - Re-check against the executed filters: 0 of 53 results break them.
  - Latency: nlu p50 5.7 s / p95 16.9 s; compose p50 1.2 s / p95 8.1 s; total p50 8.2 s / p95 18.6 s. Most of this is Groq free-tier rate limiting.
  - Results are in `eval/results/latest.md` and `latest.json`. Context the run cannot write is in `eval/results/known_failures.md`.
- **Tests:** 156 unit tests and 6 DB tests (`-m db`) pass. ruff and mypy (strict on the core packages) are clean. GitHub Actions CI runs ruff, mypy and pytest.

## 2. Read before doing anything
1. `CLAUDE.md`: hard rules (the LLM never writes SQL; a stated constraint is a wall; no invented facts; a correction changes one slot; vendor imports only in `providers/`; money is int INR; every fallback is recorded; never commit `.env`).
2. `docs/decisions.md`: every decision, A–M, with the rejected alternatives. **Don't re-decide.** If you must change one, update it in the same change. Section **M** was added during Plan 1 (M1–M6: unit-bound validator, alias/family entity check, per-field number override, Groq model and TPM, error boundary, template-only follow-ups).
3. `docs/architecture.md`: matches the code as of Plan 1. §10 (API), §11 (latency stamps) and the UI parts are marked **Plan 2**.
4. `docs/standards.md`, then `docs/definition-of-done.md` (milestones M1–M5).

## 3. Plan 1 code map (what Plan 2 builds on)

```
src/voice_agent/
  config.py          pydantic-settings; DATABASE_URL default port 5433; GROQ_MODEL default openai/gpt-oss-120b
  aio.py             aio.run(): forces the Selector event loop on Windows (psycopg async needs it)
  domain/            enums, models (Slots, Listing, Filters, …), ports.py (Protocols: LLM.structured, Normalizer, Catalog)
  understanding/     numbers.py (deterministic parser; overrides LLM numbers per field), extractor.py (one structured
                     LLM call → TurnIntent), rules.py (LLM-outage fallback), pipeline.py (understand())
  catalog/           filters.py (the ONLY SQL builder, parameterized), ranker.py (explainable weighted score,
                     config/ranking.yaml), relax.py (E3 probe: smallest one-slot change with ≥1 row, never auto-applied)
  state/             reducer.py (merge, one-slot correction, pending confirmation/relaxation, reset), references.py
  response/          factsheet.py (pre-formatted numbers), composer.py (LLM → ComposedResponse → validator →
                     regenerate once → template), validator.py, templates.py
  providers/         llm.py (GroqLLM, GeminiLLM, FailoverLLM; empty keys treated as missing), postgres.py (PgCatalog, PgNormalizer)
  db/                schema.sql (listings, aliases with pg_trgm, city_neighbors, turn_log reserved), seed.py (transactional)
  telemetry/         timing.py (timed()/Stopwatch), turnlog.py (append_turn → logs/turns.jsonl)
  graph/             state.py (ConversationState TypedDict), build.py (LangGraph wiring only), runner.py
                     (TurnRunner.run(session_id, text) → TurnResult; error boundary returns route="error"),
                     runtime.py (build_runtime(settings) async context manager → TurnRunner)
  cli.py             text chat loop
```

- `TurnResult` fields: `session_id, turn, text, intent, language, route, slots, slot_diff, filters, sql, sql_params, results (ScoredListing with contributions), relaxation, pending_confirmation, followup_listing_id, followup_rank, response (ComposedResponse), response_text, verdict, fallback_used, timings_ms, usage`. Plan 2's NDJSON events (architecture §10) map almost one-to-one onto it.
- **STT and TTS sit outside the graph** (architecture decision). The API layer does STT, passes the text to `TurnRunner.run`, then sends `response` sentences to TTS.
- Tests: `tests/unit/**` mirrors `src/`. `tests/fakes.py` has `make_listing`, `FakeLLM`, `FakeNormalizer` and `FakeCatalog`. `tests/conftest.py` sets the Selector loop for pytest-asyncio. DB tests are `@pytest.mark.db` and run only when `DATABASE_URL` is set.
- Data: `data/models.csv` (35 real variants), `listings.csv` (180 rows, seed 42, from `scripts/generate_catalog.py`), `aliases.csv`, `city_neighbors.csv`.

## 4. Plan 2 scope (milestones M2, M4, M5; decisions already made)

These are decided. Write the plan from them; don't reopen them.

| Area | Decision IDs | What to build |
|---|---|---|
| API | C4, architecture §10 | FastAPI `api/`: `POST /api/session`, `POST /api/turn` (multipart audio **or** text → `application/x-ndjson` stream: `transcript` → `understanding` → `search` → `sentence`×N → `done`), `POST /api/turn/{id}/client-timings`, `GET /api/session/{id}/state`, `GET /api/health` |
| STT | H2, I3 | `GroqSTT` (whisper-large-v3) for English; `SarvamSTT` (Saaras, codemix) for Hinglish. Both behind an `STT` Protocol in `domain/ports.py`, selected by env |
| TTS | H3, H4, H5 | `ElevenLabsTTS` (Flash, streaming), with a browser `speechSynthesis` fallback (`tts: "client"`). **Sentence-level streaming** (H4) is the J5 latency mitigation, measured before and after |
| UI | K1b, standards §8 | `ui/`: Vite + React + TS strict, push-to-talk, panels only (transcript, active slots + slot diff, executed SQL + params, results with score contributions, latency stage table, fallback badges), typed-input fallback. No CSS framework, no router, no state lib |
| Docker | C4, K2 | `app` (uv sync --frozen) + `ui` (nginx) + `db`; healthchecks gate startup order; seed on first boot; `cp .env.example .env` → add Groq key → `docker compose up` working in ≤10 min |
| Hinglish | A2, D3, J3 | ~6 Hinglish eval cases (target ≥90%); Sarvam path; the number parser already handles lakh/hazaar/Hindi number words |
| Eval audio | J1 | Small audio subset in `eval/audio/` run through STT |
| Latency | J4, J5, arch §11 | Server stamps (`stt_done … tts_first_byte`), browser stamps (`t_speech_end`, `t_first_audio`); headline metric = `t_first_audio − t_speech_end`; `scripts/latency_report.py` |
| Cost | L5 | Log LLM tokens, STT audio-seconds and TTS chars per turn; `scripts/cost_report.py` gives ₹ per conversation |
| Logging | K4, standards §4 | Optionally write the `turn_log` table (reserved); `logs/turns.jsonl` already exists |
| Ship | M5 | README (setup, architecture, eval, limits), committed results |

**Latency candidates already identified:**
- Put the extractor and composer on different Groq models (separate 8,000 TPM buckets).
- `qwen/qwen3.8-27b` measured ~0.7 s vs gpt-oss-120b ~1.3 s on a TurnIntent call.
- `reasoning_effort=low`.
- Fail over on 429 instead of waiting.
- Sentence streaming (H4).
- J5 second option: a rules fast-path that skips the LLM for pure-slot utterances.

**Deferred:** section L (presentation and Q&A prep, L1–L6) waits until the build is done. Slides are optional.

## 5. Environment facts (Windows-specific; these cost time in Plan 1)

- **OS:** Windows 11. Tools: the Bash tool is Git Bash, plus PowerShell 5.1. `uv` lives at `~/.local/bin`. Python 3.12.
- **Postgres:** docker compose runs inside **WSL** and is reachable from Windows on **localhost:5433**, because a native Windows Postgres holds 5432. The user starts it (`docker compose up -d` in WSL). `docker-compose.yml` maps `"5433:5432"`.
- **Event loop:** psycopg async fails on the Windows Proactor loop. Always go through `aio.run()` (scripts and CLI); tests use the conftest hook. New FastAPI/uvicorn entry points need the same: run uvicorn with `loop="asyncio"` under a Selector policy on Windows, or run inside Docker/Linux.
- **Keys** (`.env`, never print or commit it):
  - `GROQ_API_KEY` is set.
  - `GEMINI_API_KEY` is **empty**, so the fallback LLM is effectively off. Empty values count as missing.
  - **ElevenLabs and Sarvam keys are not in `.env` or `.env.example` yet.** Plan 2 must add `ELEVENLABS_API_KEY`, `SARVAM_API_KEY` and model/voice variables to both (blank in the example) and ask the user to fill them.
- **Groq free tier:** **8,000 tokens per minute per model.** One turn is about 2.5k tokens, so about 3 turns/min. This is the first latency and scale bottleneck. `llama-3.3-70b-versatile` returns 404 (retired).
- **Commits:** the SSH signing key sits in the Windows ssh-agent and git uses `github_signing.pub`, so plain `git commit` signs with no prompt. **Never** use `--no-gpg-sign` or skip hooks. **Push only when the user says so.** Commit attribution trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Gotchas:**
  - A Python heredoc writing the string `"\x00"` put a real NUL byte into a source file once. Write escape sequences with the Edit tool.
  - Git prints LF→CRLF warnings on every add; they're harmless.
  - Add stray `*.stackdump` files to `.gitignore` (already done).
  - The live eval takes about 15 minutes because of the TPM limit.

## 6. Known issues and limits (already documented; don't rediscover them)

- **Run-to-run LLM variance** (known_failures.md): `adversarial-01` may skip the "did you mean" prompt if the LLM silently fixes "Aace"; loose phrasing can over- or under-fill a categorical slot; validator regenerations count as failures.
- **Single-letter mishears** ("S" for "Ace") can't be caught by trigrams (D2, J3). This is a stated limit.
- **Parser:** only the first km and the first payload phrase are read. "over 2 lakh km, under 50000 km" loses the km wall (logged; contrived input).
- **F3 limits:** the validator doesn't check papers, seller or registration claims. These are documented as xfail tests.
- **Regressions A and B from the final review are FIXED:**
  - A: a direction word leaked across a consumed span. Consumed spans are now filled with the sentinel `_BLANK`, and contexts are clipped at it.
  - B: a dropped contradictory km/payload was re-filled by the LLM. `NumericSlots.dropped` now blocks it. decisions.md M3 is updated.
  - Not re-measured by the live eval (no case uses those phrasings). Unit tests cover them.

## 7. Process that worked (repeat it)

- **Plan:** `superpowers:writing-plans` → `docs/superpowers/plans/2026-10-2x-<name>.md`, bite-sized TDD tasks with exact code, a Global Constraints section, and Interfaces blocks.
- **Execution:** `superpowers:subagent-driven-development`.
  - Each task gets a fresh implementer, then a task review covering spec and quality, then fix rounds with scoped re-reviews.
  - Ledger at `.superpowers/sdd/<plan-basename>/progress.md` (git-ignored); briefs, reports and review diffs live as files there.
  - Model choice: cheapest tier for transcription tasks, sonnet for reviewers and judgment, the most capable model for the final whole-branch review.
  - One signed commit per task. Stop only for destructive, security-sensitive or outward-facing actions (a push), or when the plan is broken.
- **Order:** deterministic core first, with tests; providers and wiring after. Keep it thin ("do not gold-plate"). The author must be able to explain every line in Q&A, so prefer obvious code over clever code.
- **User preferences:**
  - The user is applying for an SDE role and works in English first, Hinglish later.
  - The user likes AskUserQuestion for multi-option decisions.
  - The user wants assumptions written down, since no questions go to Vyngo.
  - Stretch goals claimed: **Hinglish + explainable reranker** (A3).

## 8. Plan 1 rulings (for reference; each is in decisions.md or the code)

- `"tempo"` alias maps to `lcv` (the user confirmed).
- "no" to a confirmation re-searches with the existing slots and drops the deferred update (D6).
- The validator checks city and fuel in item sentences only; intro and closing may echo the user's slots.
- Papers, seller and registration stay unchecked (F3).
- Hyphenated body-type words ("three-wheeler") are exempt from the number-word check.
- In the rules fallback, "yes" becomes intent RELAX with confirmation "yes", and "no" becomes SEARCH with confirmation "no".
- The default model is gpt-oss-120b for quality; qwen3.8-27b is the latency candidate (M4).
- The exception boundary lives in `TurnRunner` (M5).
- The validator rejects `VH-\d+` IDs in any spoken text.
- Eval case changes:
  - `zero-02` now expects no relaxation (none exists in the catalog).
  - `followup-01` now uses Delhi (Mumbai has only 1 diesel pickup).
- Per-field number override (M3).
  - Only the stated budget bounds are written. A max clears the target; a range or "around X" replaces all three.
  - A contradictory km/payload direction is dropped, never inverted.
- The first-match-only km/payload limit is accepted and logged.

## 9. Prompt for the new session

Paste this into the new session:

```
We're continuing the Vyngo take-home "Voice-Based Vehicle Search" in D:\Job\portfolio_projects\voice-agent.
Plan 1 (text loop, milestone M1) is complete on branch feat/text-loop (pushed; eval 25/25).

First read docs/plan-2-handoff.md fully, then CLAUDE.md, docs/decisions.md, docs/architecture.md,
docs/standards.md and docs/definition-of-done.md. Don't re-decide anything in decisions.md; if a
change is unavoidable, update the doc in the same change.

Task: write Plan 2 with superpowers:writing-plans, covering milestones M2 (voice loop: FastAPI NDJSON
API, GroqSTT, ElevenLabsTTS with sentence-level streaming and browser fallback, Vite+React push-to-talk
UI with panels and latency table), M4 (Hinglish: SarvamSTT + ~6 Hinglish eval cases ≥90%, small audio
eval subset), and M5 (Docker app+ui+db with healthchecks and ≤10-min setup, latency_report.py,
cost_report.py, README). Scope is in handoff §4; environment gotchas (Windows Selector loop, Postgres on
5433 via WSL, Groq 8k TPM, missing ElevenLabs/Sarvam keys) are in §5.

Before writing tasks, check the handoff's open items with me via AskUserQuestion only where a real
choice remains (e.g. whether to branch Plan 2 off feat/text-loop or merge it to main first, and
whether the ElevenLabs/Sarvam keys are ready). Save the plan to docs/superpowers/plans/, then I'll
choose the execution mode. Execute with subagent-driven-development, one signed commit per task,
and never push without my say-so.
```
