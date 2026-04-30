# LongMemEval — Maez subset run

Total questions: 30
Mean score (token-overlap lower bound): 0.6990
Judge accuracy (30 judged): 0.7667

## By question type

| type | n | mean score | judge n | judge accuracy |
|---|---|---|---|---|
| knowledge-update | 5 | 0.6558 | 5 | 0.6 |
| multi-session | 5 | 0.3833 | 5 | 0.6 |
| single-session-assistant | 5 | 1.0 | 5 | 1 |
| single-session-preference | 5 | 0.5302 | 5 | 0.8 |
| single-session-user | 5 | 0.8444 | 5 | 1 |
| temporal-reasoning | 5 | 0.78 | 5 | 0.6 |

## Notes

- Score is a token-overlap heuristic, NOT the official GPT-4o judge.
- Use as a recall-floor signal until the judge wires up (Session 2).
- Each question runs in an isolated tmpdir MemoryManager — the live store is never touched.
