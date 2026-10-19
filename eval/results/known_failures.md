# Known failures and risks (hand-maintained)

`run_eval.py` never writes this file. `latest.md` and `latest.json` are regenerated on every run; this file holds the context they cannot.

## Latest full run
25/25 with 100% constraint safety. The first run of the day scored 22/25. Triage of those three failures:

- `en-08` "light commercial vehicle" left `body_type` empty. The LLM did not link the phrase to the `lcv` enum code. Fixed with one rule in the extractor prompt that maps vehicle-class names to `lcv` / `icv`.
- `zero-02` expected a relaxation offer, but no one-slot loosening returns any rows: Chennai has no mini trucks, and the cheapest electric mini truck costs about 6.8 lakh. E3 forbids offering a suggestion that also returns zero, so the expectation now says no offer is made.
- `followup-01` asked about "the second one" after "Diesel pickup in Mumbai", but the seeded catalog (B6) has only 1 such listing, so the system correctly asked "which one?". The case now uses Delhi (10 diesel pickups).

## Known risks: run-to-run LLM variance
Slot extraction is one LLM call (Groq, openai/gpt-oss-120b), so a case that passes today can fail on another run:

- `adversarial-01` ("Tata Aace in Pune"): the prompt tells the LLM to copy mentions verbatim. If it silently corrects "Aace" to "Ace", the alias match is exact, no confirmation is asked, and the case fails on `expect_route: confirm`. The search itself is still correct (model = Ace), so this is a missed clarification, not a wrong result.
- Over- or under-filling a categorical slot from loose phrasing (the `en-08` class of failure). Numbers are safe here because the deterministic parser overrides the LLM on budget, km, payload and year (D3).
- Composer phrasing: a response that fails the validator falls back to regenerate or the template. The answer stays safe (F1), but the eval counts it as a failure ("validator not clean on first try").

## Latency caveat
`nlu` and `compose` are each a single Groq call. The free tier allows 8,000 tokens/min per model, and the SDK waits out 429s, so the eval's p50/p95 (NLU p50 about 9.6 s, total p95 about 25 s) may include rate-limit backoff and reasoning-token time. Treat them as an upper bound, not steady-state latency. Plan 2 (J5) measures the mitigation.
