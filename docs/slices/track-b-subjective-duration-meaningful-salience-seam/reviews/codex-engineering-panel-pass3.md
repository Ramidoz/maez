# Codex Engineering Panel Review — Subjective-Duration Meaningful-Salience Seam Pass 3

**Prepared:** 2026-05-25
**Artifact reviewed:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` (DRAFT v6, 2110 lines)
**Brief reviewed:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-brief-pass3.md`
**Parent commit:** `fb2f781 feat(felt-time): implement subjective duration substrate`
**Verdict:** **RECONSIDER**

Pass-3 was scoped correctly: verify only the eleven v5 -> v6 tripwire folds. Most folds landed. One load-bearing contradiction remains on the central proof path: the scratch E2E canary is required to write `bond_id="_SCRATCH_FIXTURE"`, while the v6 producer-path validation rejects `bond_id="_SCRATCH_FIXTURE"`. As written, the scratch canary cannot run through the same production path it is supposed to prove.

## Verified Surfaces

| Surface | Evidence | Result |
|---|---:|---|
| Git state | `HEAD fb2f781`; no production code edited in this pass | Verified |
| H1 insert/lookup sentinel consistency | §8.2.1 uses `_SCRATCH_FIXTURE_BOND_ID` for both insert and lookup at lines 1267 and 1278 | Partially fixed |
| H2 aggregate-reader exclusion | §4.2.1 filters `bond_id NOT IN ('_LEGACY', '_SCRATCH_FIXTURE')` and `is_canary = 0` at lines 481-492 | Fixed |
| H2 lookup refusal | §7.1 refuses `_SCRATCH_FIXTURE` at lines 1082-1091 | Fixed |
| H2 producer-path refusal | §6.2.2 refuses `_SCRATCH_FIXTURE` at lines 820-828 | Creates contradiction |
| H3 plain-language readout | §13 describes two canaries, scratch math proof + live-path plumbing proof, lines 1937-1948 | Fixed |
| M8 live-path aggregate assertions | §8.2.2 asserts post residual/count equal pre residual/count at lines 1388-1410 | Fixed |
| M6 durable rollback | Durable backup path is used in §8.3.2 | Fixed |

## High Findings

**H1. Scratch E2E canary is self-contradictory: it uses `_SCRATCH_FIXTURE`, but producer validation refuses `_SCRATCH_FIXTURE`.**
In §8.2.1, the scratch canary calls `sd.record_salience_event(...)` with `bond_id=_SCRATCH_FIXTURE_BOND_ID`, where the prose defines that value as `"_SCRATCH_FIXTURE"` (lines 1226-1228, 1264-1274). In §6.2.2, the producer-path validation rejects `bond_id == "_SCRATCH_FIXTURE"` with `ValueError` (lines 820-828). That means the scratch canary cannot reach the insert, cannot produce `meaningfulness_score > 0`, and cannot prove the score-formula path.

This is not a covenant disagreement; it is a mechanical impossibility in the v6 spec. The fix needs to choose one coherent shape:

- Allow `_SCRATCH_FIXTURE` only under an explicit scratch-mode proof, such as a copied scratch DB path plus a test/smoke-only flag, while refusing it in live DB paths.
- Or change the scratch canary to use a non-reserved scratch-only bond id and rely on scratch DB isolation, while keeping `_SCRATCH_FIXTURE` as a hard production refusal.
- Or make the scratch proof bypass `record_salience_event(...)`, but then it no longer proves the production producer path and should not be called E2E.

**H2. `_SCRATCH_FIXTURE_BOND_ID` is referenced in the runnable Python block but never defined inside that block.**
The prose defines `(_SCRATCH_FIXTURE_BOND_ID = "_SCRATCH_FIXTURE")` at lines 1226-1228, but the Python snippet beginning at line 1240 never assigns `_SCRATCH_FIXTURE_BOND_ID` before using it at lines 1267 and 1278. The pass-3 brief specifically asks whether the scratch canary would run as pasted; it would currently raise `NameError` even before the producer-path refusal.

This is straightforward to amend once H1 chooses the intended scratch-mode shape.

## Medium Findings

**M1. Column-count residues remain in live spec text.**
Pass-3 brief M4 asked for all 4-column / 17-column residues to be corrected. Several live references remain:

- §9.4 says `Total: 48 RED tests` despite RED #49-#50 existing, and this section describes v4 as the current test total (lines 1650-1653).
- §10 implementation surface says `48+ RED tests` and "will land at 50+" even though v6 already lists #49-#50 (line 1669).
- §10.1 says `~850 LOC across 48 tests` (line 1691).
- §11.2 asks the panel to verify "the 4-column ALTER additions" and "INSERT column count = 17 = existing 13 + new 4" (lines 1752-1755).

The §11.2 text is especially risky because it is in the review-requirements section, not historical recap.

**M2. `canary_row` prose remains in §5.4, even though v6 claims the marker was replaced by `is_canary`.**
The remaining text at lines 656-659 says canary rows are tagged in `is_canary=1` and parenthetically references v3's brittle `metadata_json LIKE '%"canary_row":true%'` matching. That historical reference is understandable, but the fold summary at lines 2084-2085 claims §5.4 `canary_row` prose was replaced. If the intended standard is "no live §5.4 canary_row prose," this did not fully land.

The clean fix is to say only: "Canary rows are tagged in the new `is_canary=1` column." Keep the JSON-LIKE history in the fold recap, not in the normative sunset section.

**M3. H2 wording overclaims "production read site" while §6.2.2 is a write-path validation.**
The v6 fold summary says `_SCRATCH_FIXTURE` refusal lives at every production read site and lists §6.2.2 producer-path validation among those sites. §6.2.2 is not a read site; it is the producer write path. This wording matters because it hides the H1 contradiction. The spec should distinguish:

- producer write path
- bond-scoped lookup path
- aggregate reader paths
- scratch-only canary path

Once that separation is explicit, the `_SCRATCH_FIXTURE` policy becomes testable without tripping over itself.

## Clean Verifications

- The v5 H1 lookup mismatch itself is fixed: the scratch canary no longer inserts under `_SCRATCH_FIXTURE` and looks up under `"scratch_canary_bond"`.
- The v5 H3 plain-language section no longer describes the rejected single live canary that writes positive `meaningfulness_score` into the live DB.
- The live-path canary now includes direct aggregate-reader invariance assertions, not just a pointer to RED #41.
- The rollback path now uses a durable `memory/backups/...` pre-merge snapshot rather than volatile `/tmp`.
- The bond-scoped lookup includes `ORDER BY event_id DESC LIMIT 1`, matching the duplicate-producer-event-id tolerance described elsewhere.

## Amendment Contract

Before canonicalization, v7 should:

1. Resolve the scratch canary / `_SCRATCH_FIXTURE` contradiction with an explicit scratch-mode allowance or a different scratch-bond design.
2. Define `_SCRATCH_FIXTURE_BOND_ID` inside the runnable scratch canary snippet.
3. Update all remaining normative counts to 50 RED tests and 18 INSERT columns / 5 new columns.
4. Remove or relocate the remaining normative `canary_row` prose from §5.4.
5. Reword H2 / §6.2.2 language so write-path, lookup-path, aggregate-reader-path, and scratch-canary-path policies are distinct.
6. Add a RED test that proves the chosen scratch-mode rule: `_SCRATCH_FIXTURE` is allowed only for the scratch E2E canary, and refused on live DB paths.

## Scope Realism

The slice remains properly scoped after these amendments. The required fix is not a new architectural surface; it is a tightening of the canary-policy boundary introduced in v6. Expect a small v7: one scratch-mode rule, one or two RED tests, and residue cleanup.

## Plain-Language Readout

v6 fixed the old bug where the scratch canary looked up a different bond id than it inserted. But the new version accidentally made the canary illegal by its own rules. Maez would be told, "prove this works by writing a scratch row," and then the same spec says, "scratch rows are forbidden to write." That has to be settled before implementation, otherwise the first RED test on the canary will fail for the wrong reason.

Once that is fixed, the seam still looks viable.
