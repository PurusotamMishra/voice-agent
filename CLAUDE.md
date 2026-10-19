# CLAUDE.md — Vyngo Voice Vehicle Search

Voice-first assistant for finding a used commercial vehicle in India (take-home assignment: `Vyngo_Voice_Search_Assignment.pdf`).
Buyer speaks (English/Hinglish) → STT → slot extraction → hard-filtered SQL search → ranked top-3 → validated response → streamed TTS.

## Read before working
1. `docs/decisions.md` — every decision with its rejected alternative. **Don't re-decide; if you must change one, update it.**
2. `docs/architecture.md` — components, contracts, graph, state, API.
3. `docs/standards.md` — coding rules (§2 = hard architecture rules).
4. `docs/definition-of-done.md` — checklist before calling anything done.

## Map
- `src/voice_agent/` — `api/` · `stt/` · `understanding/` · `catalog/` · `response/` · `tts/` · `state/` · `graph/` (LangGraph wiring only) · `providers/` (only place for vendor SDKs) · `telemetry/` · `db/` · `domain/` (enums + shared models)
- `ui/` — Vite + React + TS (push-to-talk, panels)
- `eval/` — `cases.yaml`, `run_eval.py`, `audio/`, `results/`
- `data/` — `models.csv`, `listings.csv` (generated, seed 42), `aliases.csv`, `city_neighbors.csv`
- `scripts/` — `generate_catalog.py`, `latency_report.py`, `cost_report.py`

## Commands
```bash
uv sync                                   # install
uv run pytest                             # unit tests (no network)
uv run ruff format . && uv run ruff check .
uv run mypy src
uv run python eval/run_eval.py            # live eval (needs GROQ_API_KEY)
python scripts/generate_catalog.py        # regenerate data/listings.csv (deterministic)
docker compose up --build                 # full stack: ui :5173→nginx, app :8000, db :5432
cd ui && npm run dev | npm run lint | npm run build
```

## Hard rules (non-negotiable)
1. **The LLM never writes SQL.** SQL comes only from `catalog/filters.py`, parameterized.
2. **A stated constraint is a wall.** Hard filters: budget, body_type, fuel, city (+ make/model/payload/km/year when stated). `purpose` is ranking-only.
3. **No invented facts.** The LLM sees only the fact sheet; every response passes `response/validator.py` or falls back to `response/templates.py`. Numbers are pre-formatted in code.
4. **A correction changes exactly one slot.**
5. **Vendor imports only in `providers/`; LangChain/LangGraph only in `graph/` and `providers/`.** Business logic is plain Python.
6. **Money = int INR, weights = int kg.**
7. Every fallback is recorded in `fallback_used` and logged; never fail silently.
8. Never commit `.env` or keys.

## Working style
- Build in milestone order (definition-of-done.md: M1 text loop → M2 voice → M3 awkward turns → M4 Hinglish → M5 ship).
- Deterministic core first, with tests; providers and wiring after.
- Keep it thin: the brief says "do not gold-plate". No features outside the decisions doc without asking.
- Explainability matters: the author must be able to explain every line in Q&A. Prefer obvious code over clever code.
