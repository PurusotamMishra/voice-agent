# Coding Standards

Applies to every change, human or agent. Short on purpose: if a rule isn't here, match the surrounding code.

## 1. Python

- **Python 3.12**, managed with **uv**. Add deps with `uv add <pkg>` (dev deps: `uv add --dev`). Never edit `uv.lock` by hand.
- **Format + lint:** `ruff format` and `ruff check` (config in `pyproject.toml`). Zero warnings on commit.
- **Types:** full type hints on every function. `mypy --strict` must pass for `domain/`, `understanding/`, `catalog/`, `response/`, `state/`. Other packages: plain `mypy`.
- **Data at boundaries is Pydantic v2** (`BaseModel`), never raw `dict`s, between components. `TypedDict` only for the LangGraph state.
- **Enums** (`StrEnum`) for every closed vocabulary. They live in `domain/` and are the single source for prompts, validation and SQL.
- **Money is `int` INR.** Weights are `int` kg. No floats for money, ever. Formatting for speech happens only in `response/factsheet.py`.
- **Async:** FastAPI handlers, providers and DB access are `async` (`httpx.AsyncClient`, `psycopg` async). Pure logic (ranker, validator, reducer, filter builder, parsers) is **sync and pure**: no I/O, no globals, deterministic. That is what makes it unit-testable.
- **Config** via `pydantic-settings` in `config.py`. No `os.getenv` elsewhere. Secrets come only from env / `.env`.

## 2. Architecture rules (hard)

1. **Vendor SDKs / vendor HTTP calls are imported only in `providers/`.** Components depend on Protocols.
2. **The LLM never writes SQL.** SQL comes only from `catalog/filters.py`, always parameterized.
3. **Every number spoken comes from the fact sheet** and passes `response/validator.py`. No code path sends LLM text to TTS without a passing verdict (or the template fallback).
4. **Purpose never becomes a filter.** Inferred preferences go to the ranker only.
5. **A correction changes exactly one slot.** Enforced in `state/reducer.py` and unit-tested.
6. **LangGraph nodes contain no business logic.** They call one component function and write state.
7. **LangChain/LangGraph imports are allowed only in `graph/` and `providers/`.**
8. Changing a decision means updating `docs/decisions.md` (and `architecture.md` if the structure changes) in the same change.

## 3. Errors

- One base exception per layer: `ProviderError` (vendor failures; carries `provider`, `retryable`), `ValidationFailure` (validator), `CatalogError`.
- Providers retry retryable errors with exponential backoff (max 2 retries, jitter), then raise `ProviderError`. The graph decides the fallback, not the provider.
- Never swallow exceptions silently. Every fallback appends to `state["fallback_used"]` and logs at WARNING.
- User-facing failure messages are templated strings, never exception text.

## 4. Logging & telemetry

- stdlib `logging` with a JSON formatter (`telemetry/logging.py`). No `print` outside scripts.
- One structured **turn record** per turn (see decisions K4) → `logs/turns.jsonl` + `turn_log` table.
- Time stages with the `telemetry.timer("stage_name")` context manager; never hand-roll `time.time()` pairs.
- Never log API keys or raw audio bytes. Transcripts are fine (demo data).

## 5. Naming & layout

- Modules `snake_case.py`, classes `PascalCase`, functions/vars `snake_case`, constants `UPPER_SNAKE`.
- Provider implementations are named `<Vendor><Role>`: `GroqSTT`, `SarvamSTT`, `GroqLLM`, `GeminiLLM`, `ElevenLabsTTS`.
- One component per package; a package's public API is re-exported in its `__init__.py`. Import from the package, not its internals, across components.
- Keep functions small (≲40 lines). Prefer a clear `if` chain to a clever comprehension.

## 6. Comments & docs

- Module docstring on every module: one or two lines on what it owns.
- Comments explain **why**, not what. Reference decision IDs where a rule exists because of one: `# D5: "around X" caps at 1.1·X`.
- No commented-out code.

## 7. Tests

- `pytest`; tests mirror `src/` under `tests/unit/`. File `test_<module>.py`, function `test_<behaviour>_<condition>`.
- Unit tests make **no network calls**. Use hand-written **fakes** implementing the Protocols (`tests/fakes.py`), not deep mocks.
- Required coverage of behaviour (not %): money parser cases (lakh/L/hazaar/Hindi number words/ranges/"around"), filter builder (each slot → exactly one clause; purpose → none), ranker (contributions sum to score; deterministic order), validator (each violation type caught; F3 limits documented as `xfail` tests), reducer (merge, one-slot correction, reset, confirm), relaxation (smallest change chosen; never auto-applied), reference resolver (ordinal, make, pronoun → focused).
- DB-touching tests (if any) are marked `@pytest.mark.db` and skipped in CI unless `DATABASE_URL` is set.

## 8. Frontend (`ui/`)

- Vite + React + TypeScript (strict). Functional components and hooks; React state only, no state library, no router.
- Panels only (see decisions K1b). No CSS framework; one small `styles.css`.
- Types for API events live in `ui/src/api/types.ts` and mirror the backend NDJSON events (architecture §10).
- `npm run lint` and `npm run build` must pass.

## 9. Git

- Small commits, imperative subject (`Add money parser for lakh/hazaar`), body says why if not obvious.
- Never commit `.env`, `logs/`, or audio recorded outside `eval/audio/`.
