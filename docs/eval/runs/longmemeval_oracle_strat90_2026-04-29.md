# LongMemEval — Maez subset run

Total questions: 90
Mean score (token-overlap lower bound): 0.7168

## By question type

| type | n | mean score |
|---|---|---|
| knowledge-update | 15 | 0.8667 |
| multi-session | 15 | 0.4021 |
| single-session-assistant | 15 | 0.8374 |
| single-session-preference | 15 | 0.483 |
| single-session-user | 15 | 0.8921 |
| temporal-reasoning | 15 | 0.8196 |

## Notes

- Score is a token-overlap heuristic, NOT the official GPT-4o judge.
- Use as a recall-floor signal until the judge wires up (Session 2).
- Each question runs in an isolated tmpdir MemoryManager — the live store is never touched.
