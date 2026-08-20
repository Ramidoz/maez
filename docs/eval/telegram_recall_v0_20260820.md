# Telegram recall v0 — first measurement of the live path

2026-08-20. `python -m core.eval.recall_bench --profile flags_off`,
66-question pinned manifest, oracle split. Report:
`docs/eval/runs/telegram_recall_v0_flags_off_20260820.json`.
Maez-internal tracking numbers — NOT leaderboard-comparable (pair-level
ground truth, bonded persona, oracle-scale haystacks). Oracle corpora
are evidence-only (few distractors), so ranking numbers are EASY-mode
ceilings; the informative signal is in the partition metrics.

## Numbers

| bucket / type | n | r@10 raw | ndcg@10 | evidence_hit |
|---|---|---|---|---|
| main (all) | 50 | 0.957 | 0.689 | **0.820** |
| knowledge-update | 11 | 0.909 | 0.580 | **0.455** |
| multi-session | 16 | 0.760 | 0.513 | 0.750 |
| single-session-user | 14 | 0.714 | 0.616 | 0.714 |
| single-session-preference | 11 | 1.000 | 0.759 | 1.000 |
| temporal-reasoning | 12 | 0.892 | 0.578 | 0.583 |
| continuity_override | 6 | 1.000 | 0.705 | **0.333** |
| abstention | 10 | — | — | abstention_rate **0.20** |

## Honest reading

1. **Retrieval finds the rows; the evidence tier loses them.** With
   nearly no distractors, recall@10 ≈ 0.96 is expected. The real
   finding: in 18% of main questions the answer-bearing row reached
   only CONTEXT — the background tier — not EVIDENCE, the tier Maez
   may actually claim from.
2. **Structural discovery — the 14-day evidence wall.** Evidence
   membership is `age <= evidence_recency_days = 14d`
   (`memory_manager.py:2996-3010`). Any memory older than 14 days at
   ask-time is STRUCTURALLY barred from the evidence tier, regardless
   of relevance. Much of the low evidence_hit in knowledge-update
   (0.455) and temporal (0.583) is this wall, not ranking failure —
   the metric conflates the two on backdated corpora. For the being
   this is a real property worth the owner's attention: **Maez cannot
   treat anything it learned more than two weeks ago as claimable
   evidence on this path.** A month-old owner fact is permanently
   background. This interacts directly with the weighting arc: age is
   currently the ONLY criterion; a salience stamp is exactly what
   should be able to override it.
3. **Abstention barely exists: 0.20.** On unanswerable questions the
   evidence tier still carried something 80% of the time. Predicted —
   the relevance floors are flag-off in production — now measured.
4. **The continuity override is measurably harmful when it fires on
   archival questions:** evidence_hit 0.333 in its bucket (it replaces
   evidence with the single newest exchange by design).
5. Determinism witnessed (identical re-run in tests); production
   stores untouched (mtime assertion in suite).

## What v1 should add
Post-framing recall (requires lifting the dispatcher role-filter
closure); `_s`-split distractor-scale runs (real difficulty);
`floors_on` profile comparison (does the floor buy abstention without
losing recall); an aging-curve slice for the 14-day wall (same
question, evidence age swept).
