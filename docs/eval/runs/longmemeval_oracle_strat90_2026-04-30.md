# LongMemEval — Maez subset run

Total questions: 90
Mean score (token-overlap lower bound): 0.7938

## By question type

| type | n | mean score |
|---|---|---|
| knowledge-update | 15 | 0.9333 |
| multi-session | 15 | 0.7392 |
| single-session-assistant | 15 | 0.8374 |
| single-session-preference | 15 | 0.4903 |
| single-session-user | 15 | 0.8921 |
| temporal-reasoning | 15 | 0.8704 |

## Notes

- Score is a token-overlap heuristic, NOT the official GPT-4o judge.
- Use as a recall-floor signal until the judge wires up (Session 2).
- Each question runs in an isolated tmpdir MemoryManager — the live store is never touched.
