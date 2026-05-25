# Codex Engineering Panel Brief — Subjective-Duration Meaningful-Salience Seam Pass 3

**Prepared:** 2026-05-25
**Artifact:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` (DRAFT v6; 2110 lines)
**Parent commit:** `fb2f781`
**Relay from:** Rohit
**Pass shape:** FOCUSED — verify v6 tripwire fixes only; do NOT re-litigate axes already cleared.

---

## What's already cleared

- **Claude council:** pass-1 (6 roles, ~35 folds), pass-2 (tightly scoped, 1 fold-as-text catch), pass-3 (3 roles on canary redesign covenant semantics, Buber NEEDS-AMENDMENT 3 framing + Hume CARRIES-WEIGHT + Locke CARRIES-WEIGHT + 1 optional).
- **Codex panel pass-1:** RECONSIDER on H1 canary-pollution; v4 redesigned (two-canary + is_canary column + aggregate-reader exclusion + rollback redesign).
- **Codex panel pass-2 (this review's predecessor):** RECONSIDER on v5 implementation tripwires; v6 applies all 3 High + 8 Medium fixes.

Pass-3 is focused. Out of scope: re-verifying schema PRAGMA (already verified across passes 1 + 2), re-verifying covenant axes (already cleared by council passes 1-3), re-verifying the architectural shape (already cleared).

## v5 → v6 tripwire fixes (verify each landed)

### H1 — Scratch canary lookup mismatch

**v5 defect:** §8.2.1 INSERTed with `bond_id=_SCRATCH_FIXTURE_BOND_ID` but lookup used the string `"scratch_canary_bond"`. The canary as written would return None.

**v6 fix:** Lookup at §8.2.1 now uses `bond_id=_SCRATCH_FIXTURE_BOND_ID` consistent with the insert. Inline comment names the v5 bug.

**Verify:** §8.2.1 canary snippet — both INSERT and lookup use the same `_SCRATCH_FIXTURE_BOND_ID` constant. The snippet is runnable as pasted.

### H2 — `_SCRATCH_FIXTURE` refusal claimed but not specified

**v5 defect:** §8.2.1 said `_SCRATCH_FIXTURE` is refused at every production read site. Producer-path validation, lookup, and aggregate-reader filters only named `_LEGACY` and wildcards. Empty claim.

**v6 fix:** Three refusal sites:

1. §6.2.2 producer-path Phase 2 Step 1 — `if bond_id == "_SCRATCH_FIXTURE": raise ValueError(...)` (parallel to `_LEGACY` refusal).
2. §7.1 lookup — `if bond_id == "_SCRATCH_FIXTURE": raise ValueError(...)`.
3. §4.2.1 aggregate-reader SQL — `AND bond_id NOT IN ('_LEGACY', '_SCRATCH_FIXTURE')` (replaces v5's `AND bond_id != '_LEGACY'`).

Plus RED #49 (producer-path refusal) and RED #50 (lookup + aggregate-reader exclusion).

**Verify:** Each of the 3 refusal sites has the explicit check. The aggregate-reader SQL change in §4.2.1 names both sentinels in `NOT IN (...)`. RED #49-#50 are mechanically feasible.

### H3 — §13 plain-language readout still described v3 design

**v5 defect:** §13 readout still said "4 new columns" and described live verification as "manual-test-producer canary produces a `meaningfulness_score > 0` on the real DB" — that's the rejected v3 design.

**v6 fix:** §13 rewritten. Now says 5 new columns (including is_canary), describes the two-canary design honestly (scratch E2E proves the math + score>0 on scratch only; live-path proves the plumbing + score=0 with aggregate-reader invariance assertions), and notes that the first real Slice 2 producer event serves the real live-verification role.

**Verify:** §13 readout accurately describes v6 design. No leftover v3 framing.

### M4 — "4 columns" / "17-column INSERT" residues

**v5 defect:** Multiple "4 new columns" / "four new columns" / "17-column INSERT" mentions scattered through the spec.

**v6 fix:** All corrected to 5 and 18 respectively at: architecture summary (line 58), §4.1 title, §4.3 prose, RED #1 description, §13 readout, implementation surface table.

**Verify:** `grep -c "4 new columns\|four new columns\|four-column"` returns 1 (the line that DOCUMENTS the v6 fold). `grep -c "17 columns\|17-column"` returns 1 (same).

### M5 — RED #34 stale on `canary_row` metadata

**v5 defect:** RED #34 expected `{"canary_row": true}` in `metadata_json` — but v4 removed that marker and put canary semantics in the `is_canary` column.

**v6 fix:** RED #34 now asserts `is_canary=1` AND explicitly asserts `metadata_json` does NOT contain `canary_row` (positive verification that the old marker is gone).

**Verify:** §9 RED table — test #34 reads correctly against v6's `is_canary` design.

### M6 — Emergency rollback at `/tmp` is volatile

**v5 defect:** §8.3.2 emergency rollback restored from `/tmp/sd_pre_migration.db`. `/tmp` is volatile across reboots / system clears.

**v6 fix:** §8.3.2 redesigned. Durable backup path: `memory/backups/sd_pre_<git-sha>_<timestamp>.db`. Operator MUST create the durable snapshot BEFORE merge. The §8.1 `/tmp` snapshot remains for the pre-merge smoke test (scratch only); emergency rollback uses the durable path.

**Verify:** §8.3.2 procedure references `memory/backups/` exclusively. Pre-merge durable-snapshot step is named as REQUIRED.

### M7 — Duplicate §8.2.1 numbering

**v5 defect:** §8.2.1 appeared twice — once for the scratch E2E canary, once for the rollback dry-run obligation.

**v6 fix:** Rollback dry-run obligation renumbered to §8.3.0 (introductory subsection of §8.3 rollback procedure). Title explicitly names the renumber.

**Verify:** §8.2.1 appears only once (scratch E2E canary). §8.3.0 is the new home for the dry-run obligation.

### M8 — Live-path canary lacked aggregate-reader assertions

**v5 defect:** §8.2.2 canary printed success after lookup with comment "Test #41 covers aggregate invariance; live-path canary spot-checks." No actual spot-check in the snippet.

**v6 fix:** §8.2.2 now captures `pre_residual` and `pre_count` BEFORE the write, asserts `post_residual == pre_residual` (via `math.isclose`) and `post_count == pre_count` AFTER. Failure messages name the pollution explicitly.

**Verify:** §8.2.2 canary snippet has both pre-capture and post-assertion blocks. The assertions reference real method names (`_residual_resonance`, `_recent_meaningful_event_count_capped`) that exist at `core/evolution/subjective_duration.py:630` and `:656`.

### M9 — Stale "25 RED tests"

**v5 defect:** Two locations still said "25 RED tests" while the actual count is 48 (now 50 in v6 after RED #49-#50 added for `_SCRATCH_FIXTURE`).

**v6 fix:** Both locations updated to 50.

**Verify:** §10 implementation surface + §11 panel-ask text reference 50 RED tests. RED table has tests #1-#50.

### M10 — "v4 (this draft)" stale

**v5 defect:** Review trajectory said "v4 (this draft)" while header said v5.

**v6 fix:** Now reads "v4: applied Codex engineering panel pass-1 folds."

**Verify:** No "this draft" reference points to anything except v6 (current).

### M11 — `canary_row` prose in §5.4

**v5 defect:** §5.4 sunset section still said canary rows were tagged in `metadata_json` with `{"canary_row": true}`, contradicting §6.4 which says that marker is removed.

**v6 fix:** §5.4 prose now describes `is_canary=1` column tagging with explicit v4-promotion note.

**Verify:** §5.4 sunset paragraph references `is_canary=1`, not `canary_row`.

---

## What the panel is asked to verify (pass-3)

Per fix above. For each, render `LANDED-CORRECTLY` / `NEEDS-AMENDMENT` / `FAILED-FOLD`.

Then one final scan:

### Spec-wide residue check

- Run `grep -c` for the patterns Codex pass-2 identified. Confirm all stale instances are now ONLY in fold-history descriptions (which is correct), not in live spec claims.
- Walk §4, §6, §7, §8, §9, §13 for any other v5/v4/v3 language that contradicts v6.
- Confirm version-state hygiene: header v6, footer "End of v6 spec draft", fold trajectory accurate.

## Verdict options

- **RATIFY-CLEAR (PROCEED TO CANONICALIZATION):** all 11 folds LANDED-CORRECTLY; spec is implementation-ready.
- **RATIFY-WITH-AMENDMENTS:** specific text fixes needed; v7 lands them.
- **RECONSIDER:** another tripwire emerged; fold first.

## Out of scope (do NOT re-review)

- Schema PRAGMA (verified across pass-1 + pass-2).
- Covenant axes (cleared by council passes 1-3).
- Architectural shape (cleared).
- Two-canary discipline (cleared by council pass-3).
- Aggregate-reader exclusion mechanics (cleared by Codex pass-2 + council pass-3 Locke).

## Output

Write to `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-pass3.md`.

---

**End of brief.** Rohit relays to Codex; panel review returns at the named output path; Claude verifies firsthand against the returned artifact + git state per [[feedback_review_artifact_provenance]].
