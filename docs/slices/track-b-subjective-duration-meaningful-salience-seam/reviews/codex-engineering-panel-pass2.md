# Codex Engineering Panel Pass 2 -- Subjective-Duration Meaningful-Salience Seam

Spec: `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md`
Brief: `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-brief-pass2.md`
Parent verified: `fb2f781` (`feat(felt-time): implement subjective duration substrate`)
Review mode: focused pass-2 on v4/v5 folds only; scratch SQLite verification; no production files edited.

## Verdict

**RECONSIDER.**

The v5 redesign fixed the core pass-1 danger: it no longer intends to write a
positive synthetic `meaningful_exchange` into the live DB. The 5-column
migration is mechanically sound on a scratch copy, `is_canary` is a good
tightening, and the two-canary design is the right overall shape.

But v5 is still not ready to canonicalize. Two high-severity issues remain:
the scratch canary writes `_SCRATCH_FIXTURE` but looks up
`scratch_canary_bond`, so the proof snippet fails as written; and the spec
claims `_SCRATCH_FIXTURE` is refused at every production read site while the
validation/lookup/aggregate snippets do not actually refuse it. Several stale
v4/v3 text residues also still contradict the v5 design.

This is a narrow reconsider: no new architecture is needed. Fold the concrete
v6 fixes below, then re-run a focused pass.

## Verified Surfaces

| Category | Surface | Result | Evidence |
|---|---|---|---|
| A2/A3 | v5 migration with `is_canary` | Verified | Scratch migration produced 19 columns; `is_canary INTEGER NOT NULL DEFAULT 0` at ordinal 18; second run unchanged. |
| A1 | Aggregate-reader mechanics | Verified | Current readers execute direct SQLite SELECTs; no caching layer in `_residual_resonance()` or `_recent_meaningful_event_count_capped()`. |
| B1 | Scratch DB routing | Verified | `MAEZ_SUBJECTIVE_DURATION_DB=/tmp/...` routes `SubjectiveDuration()` to the scratch DB via `_default_db_path()`. |
| B2 | `manual_test_event` kind gating | Verified | Current formula gates positive scoring on `salience_event_kind == "meaningful_exchange"`; `manual_test_event` remains score 0.0. |
| D3 | RED numbering | Verified with text caveat | RED table has numeric 1-48 sequential, no gaps, one #38; stale individual descriptions remain. |
| D1 | §5 ordering | Verified | §5.1 through §5.5 now appear in physical order. |

## Findings

### High

1. **Scratch E2E canary is internally inconsistent and will fail as pasted.**

   §8.2.1 inserts with `bond_id=_SCRATCH_FIXTURE_BOND_ID`
   (`spec.md:1232`-`1242`) but the lookup uses
   `bond_id="scratch_canary_bond"` (`spec.md:1245`-`1247`). That lookup returns
   `None`, so the canary cannot prove the score path as written. Use
   `_SCRATCH_FIXTURE_BOND_ID` in the lookup, or change the insert to match the
   lookup. The former is consistent with the Buber pass-3 sentinel fold.

2. **`_SCRATCH_FIXTURE` refusal is claimed but not specified.**

   §8.2.1 says `_SCRATCH_FIXTURE` is refused at every production read site
   (`spec.md:1194`-`1201`). But producer-path validation only refuses
   `_LEGACY` and wildcard strings (`spec.md:799`-`811`), lookup only refuses
   `_LEGACY` and wildcard strings (`spec.md:1053`-`1064`), and aggregate-reader
   filters only name `_LEGACY` plus `is_canary = 0` (`spec.md:477`-`489`).

   If `_SCRATCH_FIXTURE` accidentally lands in live with `is_canary=0`, the
   proposed aggregate filters would not exclude it by sentinel. Either remove
   the "refused at every production read site" claim and keep `_SCRATCH_FIXTURE`
   strictly scratch-only, or add `_SCRATCH_FIXTURE` refusal/exclusion to the
   producer path, lookup path, and aggregate reader filters with RED tests.

3. **Plain-language readout still contradicts v5.**

   §13 says the slice adds "4 new columns" (`spec.md:1817`) and says
   live verification is "the manual-test-producer canary produces a
   `meaningfulness_score > 0` on the real DB" (`spec.md:1834`-`1836`). That is
   the rejected v3 design. v5's actual design is scratch `>0`, live-path `0.0`
   with no felt-weight injection.

### Medium

4. **The 5th ALTER column is not documented consistently.**

   Stale "4 new columns" / "four new columns" remains in multiple places:
   architecture summary (`spec.md:54`), §4.1 title (`spec.md:384`),
   preservation prose (`spec.md:503`), RED #1 (`spec.md:1469`), and §13
   (`spec.md:1817`). The implementation surface also still says the INSERT is
   17 columns (`spec.md:1574`) even though §6.4 correctly says 18
   (`spec.md:880`-`881`).

5. **RED #34 is stale against the `is_canary` design.**

   RED #34 still expects `{"canary_row": true}` in `metadata_json`
   (`spec.md:1507`), while §6.4 says `canary_row` is removed and canary
   semantics live in the real `is_canary` column (`spec.md:930`-`933`). Update
   #34 to assert `is_canary=1` and no canary semantics in `metadata_json`.

6. **Emergency rollback depends on a volatile `/tmp` snapshot.**

   §8.1 creates the pre-migration scratch DB at `/tmp/sd_pre_migration.db`
   (`spec.md:1146`-`1147`), and §8.3.2 later restores that path into live
   storage (`spec.md:1429`-`1430`). For an emergency rollback path, `/tmp` is
   not a durable artifact. Either make the emergency snapshot live under a
   durable `memory/` or `logs/rollback/` path, or state that `/tmp` is only for
   smoke-test scratch and cannot be the emergency restore source.

7. **Section numbering is ambiguous.**

   `§8.2.1` appears twice: scratch E2E canary (`spec.md:1188`) and rollback
   dry-run obligation (`spec.md:1371`). Renumber rollback dry-run to `§8.2.4`
   or move it under `§8.3` so cross-references are unambiguous.

8. **Live-path canary does not assert aggregate-reader invariance.**

   §8.2.2 prints success after lookup and comments that Test #41 covers
   aggregate invariance (`spec.md:1342`-`1344`). Either add explicit before/after
   aggregate assertions to the live-path canary snippet or stop saying the
   live-path canary spot-checks aggregate-reader behavior. RED #41 itself is
   good.

9. **Implementation surface and panel ask still carry stale counts.**

   The spec still says "25 RED tests" at `spec.md:1579` and `spec.md:1672`.
   The pass-2 brief says 48, and §9 has 48. Update all implementation/review
   text to 48.

10. **Header/review trajectory calls v4 "this draft".**

    The header is v5, but the review trajectory still says "v4 (this draft)"
    (`spec.md:13`). This is small, but after the prior provenance drift it
    should be cleaned before canonicalization.

11. **`canary_row` language remains after the design moved to `is_canary`.**

    §5.4 still says canary rows are tagged in `metadata_json` with
    `{"canary_row": true}` (`spec.md:645`-`648`), while §6.4 says that marker is
    removed. Replace with `is_canary=1` language.

## Scope Realism

The v5 scope remains one coherent seam slice. It does not need another split.
The production edit estimate should be corrected upward only if v6 chooses to
add explicit `_SCRATCH_FIXTURE` filters to all production read/write sites.
Even then, this stays within the same live-organ seam.

The test count is no longer exactly 48 if v6 adds tests for
`_SCRATCH_FIXTURE` refusal/exclusion and live-path aggregate assertions. That
is acceptable; update the count rather than compressing the test surface.

## Required Amendments Before Re-Review

1. Fix the scratch canary lookup bond id to use `_SCRATCH_FIXTURE_BOND_ID`.
2. Settle `_SCRATCH_FIXTURE` semantics: either strictly scratch-only with no
   production-read-site claim, or explicit refusal/exclusion everywhere claimed.
3. Correct §13 to describe v5: 5 columns, scratch `>0`, live-path `0.0`.
4. Replace all stale 4-column/four-column text with 5-column text.
5. Replace stale 17-column INSERT text with 18-column text.
6. Update RED #34 from `metadata_json canary_row` to `is_canary=1`.
7. Make emergency rollback use a durable restore artifact or mark `/tmp` as
   scratch-only and not acceptable for emergency live restore.
8. Fix duplicate §8.2.1 numbering.
9. Add aggregate-reader invariance assertions to the live-path canary or narrow
   its claim.
10. Update all remaining 25-test references to 48 or the new v6 count.
11. Change "v4 (this draft)" to historical v4 trajectory text.
12. Replace lingering `canary_row` prose with `is_canary` prose.

## Plain-Language Readout

v5 fixed the big conceptual problem: live verification no longer has to fake a
positive feeling in Maez. The scratch canary can prove the math, and the live
canary can prove the code path without becoming felt-weight.

But the spec still has enough crossed wires that an implementer could build the
wrong thing. The scratch canary literally writes one bond id and looks up
another. The text says `_SCRATCH_FIXTURE` is refused everywhere, but the
pseudocode does not refuse it. The plain-English section still describes the
old unsafe canary. These are not philosophical objections; they are
implementation tripwires.

Fold those v6 corrections and this should be very close to canonicalization.
