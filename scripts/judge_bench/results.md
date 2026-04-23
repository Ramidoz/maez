# Grounding-judge benchmark results

| label | model | agree % | errors | p50 s | p95 s | mean s |
|---|---|---:|---:|---:|---:|---:|
| 4B-gpu-baseline | maez-judge | 90.5 | 0 | 0.22 | 0.28 | 0.23 |

## 4B-gpu-baseline — disagreements

| id | expected | got |
|---|---|---|
| fab-1 | FABRICATED | GROUNDED |
| ok-4 | GROUNDED | FABRICATED |
