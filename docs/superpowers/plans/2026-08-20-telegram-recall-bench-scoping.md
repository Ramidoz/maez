# Telegram recall benchmark — scoping (pre-build)

2026-08-20. Scoping pass complete (Explore lane, verified on disk).
Converts audit ingredient 4 from "unmeasured" toward a number. Key
correction folded into the audit doc: a LongMemEval adapter already
exists for the reasoning-cycle path; this build is a RE-TARGET +
RE-METRIC of existing plumbing, not greenfield. Est. ~450 LOC prod +
~320 LOC tests, 5 new files + 1 edit.

## What exists (verified)
- `core/eval/longmemeval.py` (679 LOC): `IsolatedMemoryHarness` patches
  `BASE_DB` to a tempdir (proven isolation pattern), loaders, judge CLI.
- `data/longmemeval/longmemeval_oracle.json` + `_s.json` on disk (500
  questions; public data — satisfies the no-owner-content constraint by
  construction).
- 5 recorded runs; per-type bests: single-session 1.00, knowledge-update
  0.80, multi-session 0.40-0.60, temporal 0.00-0.20.

## v0 shape (agreed basis for build)
- Corpus: oracle haystack sessions converted to `telegram_exchange` rows
  (one per user/assistant pair, label = OR of pair; backdated
  timestamps), temp Chroma only, `record_recalls=False`, patched
  `memory_scoring` stats path, tempdir guard asserts.
- Surface under test: `recall_for_telegram_living` output (evidence +
  context partitions). Post-framing recall deferred to v1 (requires
  lifting the role-filter closure out of `brain_loop.py` — noted as the
  main design fork).
- 60 pinned questions: 10 × {temporal, multi-session/day,
  knowledge-update, single-session-user, preference, abstention}.
- Deterministic metrics only: recall@10_raw, recall@k_total, ndcg@10,
  **evidence_hit_rate** (the Maez-native number ingredient 4 wants),
  abstention_rate (empty-evidence on _abs; the relevance floor IS the
  retrieval-layer abstention organ — flag-gated off in prod today).
- Two flag profiles exactly: `all-off` (production today),
  `floors+promotion-on` (intended future). No matrix growth.
- Determinism: freeze `_now_seconds` relative to question_date (90-day
  recency half-life makes scores wall-clock-dependent otherwise); pin
  all six recall flags; record embedding-contract stamp; avoid
  continuity-trip phrasings.

## Pre-build probe — RUN 2026-08-20, design decision made
Measured `dialogue_continuity_state` on 150 stratified oracle
questions (seed 20260820): **23/150 = 15.3% trip DIRECT/ANAPHORIC**,
concentrated in single-session-assistant (9/20) and preference (8/20);
single-session-user 0/20, knowledge-update 1/20, temporal 3/20.

Decision: the 60-question manifest is built from PRE-SCREENED
non-tripping questions per type, PLUS a separate pinned
`continuity_override` bucket (~6 tripped questions) scored on its own —
the override is real production behavior and gets measured, not hidden;
it just may not contaminate the retrieval aggregate. The >10% risk is
resolved by construction.

## Known score-capping mechanisms to bucket separately
`_absolute_date_recall` total bypass (own bucket); `_keep_not_echo`
2-hour echo filter; raw→10 truncation; continuity override cliff.

## Honesty constraints on reporting
Maez-internal tracking number ONLY — not leaderboard-comparable
(different retrieval unit, persona, haystack scale). Say so in the
results doc. First number will mix "recall is bad" with "phrasings trip
Maez-specific guards"; budget one iteration to separate them.
