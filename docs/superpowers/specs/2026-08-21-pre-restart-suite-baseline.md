# Pre-restart suite baseline — 2026-08-21

Purpose: tomorrow's restart flips `MAEZ_HELD_NOW_ENABLED=1` and arms
`MAEZ_ACTION_LANE_SHADOW=1`. Both flips should land on a *known*
baseline, not an assumed one. This records what the suite actually does
at HEAD and how much of it predates this session.

## Result

| Run | Tests | Outcome |
|---|---|---|
| HEAD (`d031bf5`, main worktree) | 9,407 | FAILED — 37 failures, 40 errors, 5 skipped |
| Session start (`bf8621f`, detached worktree) | 9,374 | FAILED — 37 failures, 57 errors, 5 skipped |

Unique failing test names: **88 at baseline, 71 at HEAD.**

## Ledger: introduced vs pre-existing

**Introduced by this session: none.**

Exactly one failing test name appears at HEAD but not at baseline:
`test_fast_backend_cloud_retirement.FastReplyAuditAndStaticBoundaryTests
.test_service_audit_behavior_records_cloud_retirement_without_raw_text`.
Run in isolation at HEAD it **passes** (13 tests, OK). Its full-run
failure is `len(records) == 0`, an audit-record assertion that another
test in the same process had already drained — single-process
cross-contamination, not a regression. Note the repo has a sanctioned
airlock runner (`scripts/dev/worktree_test_airlock.py`) precisely
because a raw 9k-test `discover` run pollutes itself.

**Fixed by this session: one.**
`test_memory_write_bypass_audit.test_no_production_file_writes_directly_to_lived_chroma`
fails at baseline and passes at HEAD (commit 61c6655).

**Baseline-only failures (17 names)** — cuda bench driver, capability
queue rows, disclaimer rendering, etc. — are the worktree-floor
confound: the detached worktree lacks owner-local assets, so it fails
*more*, exactly as the existing doctrine warns. They are not fixes.

## Spot-checks performed before trusting the aggregate

- Six modules adjacent to this session's daemon/brain-loop edits were
  run in isolation at HEAD and at baseline; the failure sets were
  **byte-identical apart from the timing line**.
- `test_brain_preempt_propagation` was investigated individually
  because it inspects `daemon/maez_daemon.py` source, which this
  session edited heavily. It slices between
  `self._mark_cycle_stage("reasoning_model")` and
  `self._mark_cycle_stage("threshold_alerts")` — but in the real file
  those markers appear in the **opposite order** (`:11173` before
  `:11448`), so the slice is empty and the assertion cannot pass.
  `git show bf8621f` confirms the same inversion at session start, and
  `git log -S` dates it to `eb409e6`. **Pre-existing latent defect,
  filed below — the test has been asserting against an empty string.**

## Filed follow-ups (not blocking the restart)

1. `tests/test_brain_preempt_propagation.py:49` slices between markers
   that are inverted in the source, so the block is always empty and
   the test cannot pass. Either reverse the slice bounds or anchor on
   the real enclosing construct.
2. The 39-test cluster in `test_s7_1_ceremony_service` /
   `test_operator_user_boundary_s7` fails in isolation at HEAD **and**
   at baseline. Pre-existing; owner-gated area (S7 trust is
   human-gated) — surfaced, not touched.
3. Consider making the certifying run go through the airlock so
   pollution failures stop masquerading as regressions.

## Bottom line for the restart

Nothing this session added regresses the suite. The failures that exist
predate it, and one of them is now fixed. The two flag flips may
proceed on that basis.
