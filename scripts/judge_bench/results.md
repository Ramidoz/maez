# Grounding-judge benchmark results

| label | model | agree % | errors | p50 s | p95 s | mean s |
|---|---|---:|---:|---:|---:|---:|
| primary-27b-live-as-judge-20260606 | qwen36-27b | 76.2 | 0 | 1.06 | 1.26 | 1.05 |

## primary-27b-live-as-judge-20260606 — disagreements

| id | expected | got |
|---|---|---|
| fab-1 | FABRICATED | GROUNDED |
| fab-2 | FABRICATED | GROUNDED |
| fab-3 | FABRICATED | GROUNDED |
| ok-4 | GROUNDED | FABRICATED |
| ok-8 | GROUNDED | FABRICATED |
