# Eval results (2026-10-20 05:51 UTC)

Models: groq extract=openai/gpt-oss-20b, compose=qwen/qwen3.8-27b

**Overall: 26/32 = 81%**

| Category | Passed |
|---|---|
| adversarial | 2/2 |
| boundary | 1/2 |
| correction | 3/3 |
| english | 9/11 |
| follow_up | 2/2 |
| hinglish | 4/7 |
| other | 3/3 |
| zero_result | 2/2 |

Constraint safety (vs stated constraints): 98.4% of 61 results shown on turns with expect_filters satisfy every constraint the user stated.

Re-check (vs executed filters): 0 of 70 shown results break the pipeline's own executed filters (expected 0: the search node re-checks them).

| Stage | p50 ms | p95 ms |
|---|---|---|
| compose | 7476 | 22175 |
| nlu | 630 | 861 |
| rank | 0 | 0 |
| relax | 5 | 12 |
| search | 2 | 6 |
| total | 8152 | 22891 |

## Failures

- `en-01`: t1: validator not clean on first try (llm, ['regenerated'])
- `en-06`: t1: filters {'body_type': 'mini_truck', 'city': 'pune', 'make': 'Tata', 'model': 'Ace'} != {'make': 'Tata', 'model': 'Ace', 'city': 'pune'}
- `boundary-01`: t1: validator not clean on first try (llm, ['regenerated'])
- `hi-01`: t1: validator not clean on first try (llm, ['regenerated'])
- `hi-02`: t1: validator not clean on first try (template, ['template'])
- `hi-04`: t1: filters {'budget_max': 500000, 'body_type': 'mini_truck', 'city': 'pune'} != {'make': 'Tata', 'model': 'Ace', 'city': 'pune', 'budget_max': 500000}

Known failures, risks and latency caveats: see `known_failures.md`.
