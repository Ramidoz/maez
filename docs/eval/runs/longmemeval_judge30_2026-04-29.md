# LongMemEval — Maez subset run

Total questions: 30
Mean score (token-overlap lower bound): 0.6547
Judge accuracy (30 judged): 0.6333

## By question type

| type | n | mean score | judge n | judge accuracy |
|---|---|---|---|---|
| knowledge-update | 5 | 0.6558 | 5 | 0.8 |
| multi-session | 5 | 0.1833 | 5 | 0.2 |
| single-session-assistant | 5 | 1.0 | 5 | 1 |
| single-session-preference | 5 | 0.527 | 5 | 0.8 |
| single-session-user | 5 | 0.8222 | 5 | 1 |
| temporal-reasoning | 5 | 0.74 | 5 | 0 |

## Notes

- Score is a token-overlap heuristic, NOT the official GPT-4o judge.
- Use as a recall-floor signal until the judge wires up (Session 2).
- Each question runs in an isolated tmpdir MemoryManager — the live store is never touched.
