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
- [ ] Fallback still works: typed input; ElevenLabs failure or no `ELEVENLABS_API_KEY` → browser TTS (`tts_client`)
- [ ] `npm run lint && npm run build` pass in `ui/`

## Changes touching setup (Docker, deps, env)
- [ ] From a clean clone: `cp .env.example .env` → add keys → `docker compose up --build` → app usable, **≤10 minutes**
- [ ] README updated if any command, key or port changed

## Milestones (project level)
- [x] **M1 — text loop:** typed utterance → slots → SQL → top-3 → validated text; eval ≥ 90% (English) (eval 25/25, 2026-10-19)
- [x] **M2 — voice loop:** PTT → STT → … → streamed TTS; latency panel shows all stages (live mic test in Docker, English and Hindi speech, 2026-10-20; browser speech end → first audio p50 3.3 s)
- [x] **M3 — awkward turns:** correction, zero-result + relaxation, follow-up all pass in eval and live (correction 3/3, zero_result 2/2, follow_up 2/2 in the eval)
- [ ] **M4 — Hinglish:** Sarvam STT path + Hinglish eval cases ≥ 90% (Sarvam path verified live and on the audio clips; Hinglish eval was 7/7 on gpt-oss-120b before N13/N14 and 4/7 on the smaller models; **needs a rerun on gpt-oss-120b**)
- [ ] **M5 — ship:** Docker ≤10-min setup verified, README, eval results committed, latency + cost reports generated (README, reports and results done; clean clone builds with `--no-cache --pull` in 171 s, base images already local, 2026-10-20; a first-boot run from the clone and the gpt-oss-120b eval rerun outstanding)
