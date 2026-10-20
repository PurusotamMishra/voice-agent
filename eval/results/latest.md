# Eval results (2026-10-19 19:50 UTC)

**Overall: 25/25 = 100%**

| Category | Passed |
|---|---|
| adversarial | 2/2 |
| boundary | 2/2 |
| correction | 3/3 |
| english | 11/11 |
| follow_up | 2/2 |
| other | 3/3 |
| zero_result | 2/2 |

Constraint safety (vs stated constraints): 100.0% of 44 results shown on turns with expect_filters satisfy every constraint the user stated.

Re-check (vs executed filters): 0 of 53 shown results break the pipeline's own executed filters (expected 0: the search node re-checks them).

| Stage | p50 ms | p95 ms |
|---|---|---|
| compose | 1213 | 8092 |
| nlu | 5730 | 16896 |
| rank | 0 | 0 |
| relax | 4 | 8 |
| search | 2 | 4 |
| total | 8197 | 18634 |

Known failures, risks and latency caveats: see `known_failures.md`.
