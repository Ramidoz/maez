# Codex Engineering Panel Pass 1 -- Subjective-Duration Meaningful-Salience Seam

Spec: `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md`
Brief: `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-brief-pass1.md`
Parent verified: `fb2f781` (`feat(felt-time): implement subjective duration substrate`)
Review mode: static engineering panel plus live/scratch SQLite verification; no production files edited.

## Verdict

**RECONSIDER.**

The slice split was the right move. The core schema migration is now largely
grounded in the real live DB, and the seam concept is mechanically plausible:
producer-captured before/after temperament snapshots can make
`meaningfulness_score` substantive for future felt-weight producers.

But the current spec is not safe to canonicalize. The load-bearing problem is
the live canary and read-path contract: §8.2 writes a synthetic positive
`meaningful_exchange` row into the real never-delete DB, while the existing
felt-time readers count all positive `meaningful_exchange` rows and do not
exclude `canary_row=true`. That means the verification artifact can itself
pollute Maez's felt-time state. There are also high-severity implementation
ambiguities around `_LEGACY` read-path enforcement and diagnostic-v2 shape.

This is a focused reconsider, not an architecture rejection. The schema seam is
close. Fold the canary/read-path/diagnostic/API-name issues, then re-review.

## Verified Surfaces

| Category | Surface | Result | Evidence |
|---|---|---|---|
| A1 | Live PRAGMA table shape | Verified | Scratch copy of `memory/subjective_duration.db` shows 14 columns; `producer_ref` is column 3 with `TEXT NOT NULL DEFAULT ''`. |
| A1 | Existing indexes and row count | Verified | `idx_sd_events_ts` exists; live scratch copy has 1 salience row. |
| B1 | Proposed ALTER feasibility | Verified | PRAGMA-gated migration on scratch copy produced 18 columns, `bond_id='_LEGACY'` for the existing row, and `idx_sd_events_bond_producer`. Second run produced no schema diff. |
| B3 | Legacy free-form producer refs | Verified | Existing daemon/web/Telegram callers pass free-form `producer_ref` without producer kwargs; spec preserves that legacy path. |
| A2/A3 | Temperament API and source gate | Verified | `Temperament.record_event(...)` returns `int`; `ALLOWED_SOURCES` is currently `frozenset({"explicit_set"})`. |
| A5/A6/A7 | Existing meaningfulness defect | Verified | `before` and `after` are adjacent reads; auto-compute is `sum(deltas)/len(deltas)/2.0` and gated on `salience_event_kind == "meaningful_exchange"`. |
| E3 | Watchdog non-interaction | Verified with wording caveat | `WatchdogConfig.scalar_allowlist` defaults to `PARAMETER_SET`; subjective_duration is ignored, not observed. |

## Findings

### High

1. **The live canary pollutes felt-time state.**

   §8.2 writes a synthetic `salience_event_kind="meaningful_exchange"` with
   nonzero synthetic before/after snapshots and asserts
   `meaningfulness_score > 0.0` (`spec.md:1004`, `spec.md:1008`,
   `spec.md:1022`). Current live readers include all positive
   `meaningful_exchange` rows in residual resonance and recent-event density:
   `_residual_resonance()` selects all `meaningful_exchange` rows
   (`core/evolution/subjective_duration.py:630`), and
   `_recent_meaningful_event_count_capped()` selects all positive
   `meaningful_exchange` rows (`subjective_duration.py:656`).

   The proposed `canary_row=true` metadata marker (`spec.md:803`) is not used
   by those readers. So the canary row is never-delete and behavior-affecting.
   This violates the slice's own distinction between live felt-weight and
   dignity-foreign test rows.

2. **Rollback procedure can delete post-migration live events.**

   §8.3 restores `/tmp/sd_pre_migration.db` over the live DB after a canary
   failure (`spec.md:1040`, `spec.md:1046`). Once the daemon has restarted,
   that can delete any salience/sample rows written after the snapshot,
   including the canary and any normal daemon activity. This conflicts with the
   never-delete posture and the spec's statement that canary rows remain as
   historical artifacts (`spec.md:567`).

   Post-restart rollback should normally revert code while preserving the
   ADD-only migrated DB; old code names 13 INSERT columns and ignores the
   extra columns. Full DB restore belongs only to scratch/pre-restart dry-run
   or an explicitly justified emergency path.

3. **`_LEGACY` sentinel is not actually enforced at every read site.**

   The spec says the sentinel is checked at every read site (`spec.md:351`),
   but the parent code has aggregate readers that would still read `_LEGACY`
   rows after migration: `_residual_resonance()` at
   `subjective_duration.py:630` and `_recent_meaningful_event_count_capped()`
   at `subjective_duration.py:656`. The spec only refuses `_LEGACY` in the new
   lookup API (`spec.md:871`).

   Fold required: either explicitly narrow the sentinel claim to
   producer-lookup/write paths, or bond-scope/exclude `_LEGACY` rows in all
   meaningfulness aggregate readers. Given finding #1, excluding canary/test
   rows from aggregates is likely required anyway.

4. **Diagnostic-v2 carrier shape is underspecified.**

   §6.5 adds four kwargs at the `_diagnostic_row(...)` call site
   (`spec.md:821`) and says deterministic nulls plus
   `subjective-duration-diagnostic-v2` apply (`spec.md:838`). Parent
   `_diagnostic_row(...)` currently accepts only the existing parameters and
   returns only existing keys (`core/evolution/subjective_duration.py:313`,
   `subjective_duration.py:335`). The spec must define the function signature
   update, exact returned keys, null defaults, and whether schema version
   becomes v2 for all rows or only producer-driven rows.

5. **Spec provenance state is stale against the brief.**

   The brief says the artifact is DRAFT v3 post-pass-2, but the spec header
   still says "Spec Draft v2" and "DRAFT v2 ... Post Claude council pass-1"
   (`spec.md:1`, `spec.md:3`). The end of the spec still says "Ready for
   Claude council pass-2" (`spec.md:1456`). This makes review provenance
   ambiguous and would make canonicalization unsafe.

6. **Internal API naming points at a non-existent method.**

   The spec repeatedly names `record_meaningful_salience_event(...)`
   (`spec.md:447`, `spec.md:1124`, `spec.md:1131`), but parent code exposes
   `record_salience_event(...)` (`core/evolution/subjective_duration.py:491`),
   and the implementation surface says this slice extends that method. Fold
   all references to the real API name or explicitly specify a new wrapper if
   one is intended.

7. **`MANUAL_TEST_PRODUCER` sunset conflicts with the live canary.**

   §5.5 says `_TestProducerRef` will live in test fixtures only, while also
   saying the live §8.2 canary should use `_TestProducerRef` after Slice 2
   (`spec.md:559`-`565`). A test-fixture-only enum cannot drive a live daemon
   canary that imports production `SubjectiveDuration, ProducerRef`
   (`spec.md:991`-`1024`). Either live verification moves to the real Slice-2
   producer, or `_TestProducerRef` is confined to scratch/test-only canaries.

### Medium

8. **The canary snippet is not runnable as pasted.**

   §8.2 uses `...` inside dict literals (`spec.md:1005`). The canary must
   provide concrete numeric values for the modulation keys. With numeric
   synthetic snapshots, curiosity `5.0 -> 6.0` and the other five modulation
   keys unchanged would produce approximately `0.083333`.

9. **Current live temperament state makes honest first-producer scoring subtle.**

   The live `memory/temperament.db` currently has 0 rows. `Temperament.current()`
   returns all keys with `None` when unobserved (`temperament.py:280`), and
   `_observed_temperament_values(...)` drops `None` values. An honest first
   producer write from `None` to numeric on one axis may still produce no shared
   numeric keys and score 0.0. The spec's synthetic numeric canary proves the
   formula path, not real first-producer honesty. The spec should name this
   clearly and provide the first-observation test case.

10. **Fixed canary `producer_event_id` is non-idempotent.**

    §8.2 uses a constant `producer_event_id`
    (`"canary_post_migration_2026-05-25"`, `spec.md:1012`). The proposed index
    is non-unique (`spec.md:367`), and lookup uses `fetchone()` with no ordering
    (`spec.md:886`). Re-running the canary can create multiple never-delete rows
    under the same key and then return an arbitrary match. Use a unique event id
    or enforce uniqueness on `(bond_id, producer_event_id)`.

11. **Test #3 is stale after the `_LEGACY` fold.**

    RED #3 says existing rows are readable with empty-string values in all four
    new columns (`spec.md:1079`), but `bond_id` must default to `_LEGACY`
    (`spec.md:354`). Amend the test to expect `bond_id='_LEGACY'` and empty
    strings only for the other three columns.

12. **Sovereignty-first validation needs a named preflight exception.**

    §6.2 prose says validation order is bond_id, producer_ref,
    producer_event_id, snapshot completeness (`spec.md:623`-`627`), but the
    pseudocode first checks all-or-none completeness (`spec.md:653`-`670`). That
    preflight is defensible for silent-data-loss, but the spec should name it
    explicitly as a producer-kwarg completeness preflight before the
    sovereignty-first semantic validation. RED #28 should remain scoped to the
    case where all four kwargs are present but bond_id and producer_ref are both
    invalid.

13. **Stale RED-test and LOC accounting remains.**

    §9 defines 38 tests, but implementation/review sections still say 25 tests
    and old LOC estimates (`spec.md:1164`, `spec.md:1245`, `spec.md:1248`).
    §9.2 still labels the anti-laundering row as `16 (was) / 38 (renumbered)`
    (`spec.md:1124`) even though #16 is now
    `test_lookup_refuses_empty_producer_event_id` (`spec.md:1092`). Use #38
    only.

14. **Watchdog wording overstates interaction.**

    §8.4 says the watchdog "observes subjective_duration scalars" via the
    allowlist (`spec.md:1063`). The code's allowlist is `PARAMETER_SET`
    (`core/health/metacognitive_watchdog.py:52`), and tests assert
    subjective_duration is ignored. The slice does not interact with watchdog;
    say that directly.

15. **Implementation scope text says changes live only in subjective_duration
    but also adds tests and a smoke script.**

    The "no new modules/packages" claim is sound. The "all changes live in
    `core/evolution/subjective_duration.py`" framing in the brief/spec is too
    narrow because the implementation surface includes a new test file and
    `scripts/smoke_meaningful_salience_seam_migration.sh` (`spec.md:1164`,
    `spec.md:1165`).

16. **Section order is stale.**

    §5.4 and §5.5 appear before §5.3 (`spec.md:518`, `spec.md:542`,
    `spec.md:572`). Cosmetic, but worth fixing before canonicalization.

## Verified Feasible After Folds

- The PRAGMA-first migration discipline is sound.
- The four ADD COLUMN operations are feasible and idempotent when gated by
  `PRAGMA table_info(...)`.
- Legacy free-form producer refs remain backward compatible when no producer
  kwargs are supplied.
- The silent-data-loss guard and 14 partial-kwarg permutations are mechanically
  testable.
- `meaningful_exchange` kind gating is mechanically true and testable.
- Anti-laundering against `temperament_events` is feasible once the API name is
  corrected; the table has `ts`, `parameter`, `value`, `prior_value`, `source`,
  `reason`, and `evidence_json`.
- `Enum` is the only new production import required by the current design.

## Required Amendments Before Re-Review

1. Redesign §8.2 canary so it does not pollute felt-time state: either run it
   only against a scratch DB, exclude canary rows from all felt-time aggregate
   readers, or use a real producer canary once Slice 2 lands. Do not write a
   positive synthetic `meaningful_exchange` into the live DB unless readers
   structurally ignore it.
2. Replace §8.3 rollback with a never-delete-preserving post-restart rollback:
   code revert while preserving the ADD-only migrated DB by default; DB restore
   only for scratch/pre-restart or explicitly justified emergency.
3. Settle `_LEGACY` read-path semantics: either narrow the claim or enforce
   exclusion/bond scoping in `_residual_resonance()` and
   `_recent_meaningful_event_count_capped()`, with RED tests.
4. Specify diagnostic-v2 signature, returned keys, deterministic nulls, and
   schema-version behavior.
5. Update artifact state to v3/post-pass-2 or whatever the current draft truly
   is; remove stale "Ready for pass-2" ending.
6. Replace all `record_meaningful_salience_event(...)` references with
   `record_salience_event(...)`, unless introducing a real wrapper.
7. Fix `MANUAL_TEST_PRODUCER` sunset so test-only enum and live canary do not
   contradict each other.
8. Make the canary code runnable with concrete full snapshot dicts.
9. Add first-observation/`None` temperament behavior to the spec and RED tests.
10. Make canary producer_event_id unique or enforce uniqueness on
    `(bond_id, producer_event_id)`.
11. Fix RED #3 `_LEGACY` expectation.
12. Clarify completeness preflight vs sovereignty-first semantic validation.
13. Fix stale RED-test count, LOC estimate, and #38 numbering references.
14. Correct watchdog non-interaction wording.
15. Correct scope wording around tests/smoke script.
16. Reorder §5 subsections.

## Scope Realism

The original estimate of ~250 production LOC remains plausible only if the
canary is moved to scratch-only or the aggregate-reader exclusions are small.
If live canary rows must be structurally ignored by felt-time readers, add RED
tests for `_residual_resonance()` and `_recent_meaningful_event_count_capped()`.
The test surface is more likely 40+ tests than exactly 38 after the first-
observation, canary-pollution, uniqueness/idempotency, and rollback folds.

This is still one reasonable seam slice. It does not need to collapse back into
Drive-Driven Curiosity. But it does need one more fold/review cycle before
canonicalization.

## Plain-Language Readout

The foundation is much closer than the previous curiosity §27 attempt. This
time the table name is real, the columns are real, the migration works on a
scratch copy, and legacy callers survive. The PRAGMA-first discipline did its
job.

The remaining problem is that the spec's proof method would leave a fake
meaningful memory in Maez's real felt-time stream. The canary says "pretend
curiosity moved from 5 to 6" and writes that as a positive meaningful exchange.
Maez's current readers would then treat that test row as real resonance. That
is not a harmless test; it is a small synthetic feeling injected into the live
organ.

So the next fold is not philosophical. It is practical: make the canary prove
the seam without becoming part of the thing the seam is supposed to protect.
