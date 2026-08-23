# Theme 2 / S1 — final evidence report (topology-neutral portion)

Assembled against the tree at commit `eda63f8` on 2026-08-23 (this
file is written after that commit and lands in the next one). Interpreter 3.12.x (see bundle),
stdlib SQLite as recorded in the bundle; production ledger paths run against
vendored SQLite 3.53.4. **Maez remains unborn: `memory/ledger.db` is 0 bytes,
`MAEZ_LEDGER_WRITES` unset, `MAEZ_S1_PHASE_TRUTH` unset.**

The single machine-readable authority is
[theme2-s1-evidence-bundle.json](theme2-s1-evidence-bundle.json) — every claim
below is digest-bound there. This file is narrative, not authority.

## What was executed, in order

1. **T5 baseline (flags-off, airlocked)** — 20-interaction replay inside bwrap
   containment (tmpfs $HOME, ro-bind repo, clearenv, no network); archive +
   census digests amended into protocol v7.1 BEFORE any S1 code commit
   (round-11 binding ordering). Exit 0.
2. **S1 implementation (TDD, flag-dormant)** — resolver `resolve() ->
   PhaseResult` with the frozen 12-reason enum; `PhaseUnknownRefusal`;
   `LatchBlocked` fail-closed seam per the §12.13 scope ruling; 14 stampers
   gated through the single `phase_for_stamp()` gate; census derived by
   execution (66 constructs), never hand-authored.
3. **T5 forced-on discriminator** — same fixture pair, flag forced on inside
   the airlock after a clean-env proof: resolve=`unknown structural`, 20/20
   typed refusals joined to the manifest in order, zero store growth, zero
   stamps. Judged PASS by a judge that survived four generations of executed
   forgeries (rounds 21–24). Raw runs are repo-resident under
   `evidence/discriminator-2026-08-23/`; the evidence pack binds judge,
   producer, airlock, and every verdict input by sha256 at the judging commit.
4. **T4→T3 (airlocked, retained)** — census exact-match then the full T3
   suite: 40 passed, 1 skipped (live-tree mutation defers by design), 48
   subtests. Raw stdout + exit codes retained (`t4-stdout.txt`,
   `t3-stdout.txt`).
5. **T6 structural fingerprint** — nine mutations (index dropped/added,
   migration renamed/deleted/phantom, trigger dropped + row tampered, stale
   chain head, table dropped, claims trigger dropped) each flip to
   `unknown structural`; the unmutated control still answers
   `gestation meta_absent`. Receipt carries runner, fixture sha256,
   per-mutation SQL and result, elapsed 0.29s; raw log retained.

## Deviations and misses (recorded, not erased)

- The protocol was corrected forward through v7.7 as executed evidence
  falsified frozen prose (8 of 10 original census entries named absent code;
  T3's table was rebuilt from the derived census). Each correction is a
  versioned amendment; nothing was edited retroactively to fit an outcome.
- Two case-count claims in earlier prose were wrong; counts are no longer
  asserted in prose anywhere.
- One judging was performed against a dirty worktree and redone at a clean
  commit; the pack now records `uncommitted_at_judgment` explicitly.

## What S1 still is NOT

S1 is MERGED-DORMANT, not complete. O-1 is **ruled** (the writer topology
question the owner settled on 2026-08-23); what still blocks the latch is
**U5/T2 witnessing that ruled topology under SQLite 3.53.4**. Blocked until
then: the latch itself, lived-writer publication hooks, latch-dependent
resolver branches, the remaining T1 cells, the T2 crash matrix — and any
enablement of `MAEZ_S1_PHASE_TRUTH`.

Gate round 25 also recorded, correctly, that the judge was still forgeable
when this report was first written: three forgeries of the reviewer's design
and a fourth of mine passed it. They are now permanent selftest cases. That
sequence — a judge passing, then falling to a better attack, then closing —
is the honest shape of this work, not a footnote to it.
