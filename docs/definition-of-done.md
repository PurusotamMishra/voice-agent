# Definition of Done

A task is done only when every applicable box is true. "Applicable" is decided honestly, not conveniently.

## Every change
- [ ] `uv run ruff format --check .` and `uv run ruff check .` pass
- [ ] `uv run mypy src` passes (strict packages per `standards.md` §1)
- [ ] `uv run pytest` passes; new behaviour has unit tests (fakes, no network)
- [ ] No architecture rule in `standards.md` §2 is broken (vendor imports, LLM-built SQL, unvalidated speech, purpose-as-filter, multi-slot corrections)
- [ ] If a decision changed: `docs/decisions.md` updated (Decision · Rejected · Why); `architecture.md` updated if structure/contracts changed
- [ ] New assumptions added to the **Assumptions** list in `decisions.md`

## Changes touching understanding / search / state / response
- [ ] `uv run python eval/run_eval.py` run with live keys; pass rate **not lower** than the last committed result in `eval/results/`
- [ ] Constraint-safety metric still 100%
- [ ] New failure modes found while working are added as eval cases

## Changes touching the voice path, API or UI
- [ ] Manually exercised once end to end: speak → hear answer, with the slots/SQL/latency panels populated
- [ ] Fallback still works: typed input; `TTS_PROVIDER` failure → browser TTS
- [ ] `npm run lint && npm run build` pass in `ui/`

## Changes touching setup (Docker, deps, env)
- [ ] From a clean clone: `cp .env.example .env` → add keys → `docker compose up --build` → app usable, **≤10 minutes**
- [ ] README updated if any command, key or port changed

## Milestones (project level)
- [ ] **M1 — text loop:** typed utterance → slots → SQL → top-3 → validated text; eval ≥ 90% (English)
- [ ] **M2 — voice loop:** PTT → STT → … → streamed TTS; latency panel shows all stages
- [ ] **M3 — awkward turns:** correction, zero-result + relaxation, follow-up all pass in eval and live
- [ ] **M4 — Hinglish:** Sarvam STT path + Hinglish eval cases ≥ 90%
- [ ] **M5 — ship:** Docker ≤10-min setup verified, README, eval results committed, latency + cost reports generated
