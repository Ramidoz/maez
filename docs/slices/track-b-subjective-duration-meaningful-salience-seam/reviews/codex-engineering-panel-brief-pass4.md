# Codex Engineering Panel Brief — Subjective-Duration Meaningful-Salience Seam Pass 4

**Prepared:** 2026-05-25
**Artifact:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` (DRAFT v7; 2183 lines)
**Parent commit:** `fb2f781`
**Relay from:** Rohit
**Pass shape:** TIGHTLY FOCUSED — verify v6 → v7 self-contradiction resolution only.

---

## Why pass-4 exists

Codex pass-3 returned RECONSIDER on a single load-bearing contradiction in v6: the H2 fold added `_SCRATCH_FIXTURE` refusal at producer-path validation (§6.2.2), which directly contradicted the H1 fold (scratch canary at §8.2.1 must write under `bond_id="_SCRATCH_FIXTURE"`). The canary as written in v6 would have raised `ValueError` at its own validation step.

Codex pass-3 offered three resolution paths. v7 takes the cleanest: **producer-path ACCEPTS `_SCRATCH_FIXTURE` as the writer's explicit honesty signal; read-side enforcement (lookup + aggregate readers) prevents pollution if a fixture row leaks to live.** The write-vs-read asymmetry is named explicitly in a new §4.2.2 Sentinel Read-Discipline subsection.

Pass-4 is asked to verify ONLY this resolution + the 4 collateral residue fixes from pass-3. Everything else is out of scope.

## What's already cleared (DO NOT re-verify)

- Schema PRAGMA (across passes 1, 2, 3 — all 33+ claims firsthand-verified).
- Covenant axes (council passes 1, 2, 3 all cleared).
- Architectural shape (two-canary design, is_canary column, aggregate-reader exclusion, rollback redesign — all cleared in council pass-3 + Codex pass-2).
- 11 v5→v6 tripwire fixes (Codex pass-3 verified Most landed; only H1 contradiction blocked).

## What pass-4 IS asked to verify

### V1. §6.2.2 producer-path now ACCEPTS `_SCRATCH_FIXTURE`

**v7 fix:** removed the `_SCRATCH_FIXTURE` ValueError raise. The `_LEGACY` refusal stays. Wildcard refusal stays. Added explanatory comment naming this as intentional v7 design (write-vs-read asymmetry; trust writer's honesty signal at write-time).

**Verify:**
1. §6.2.2 Phase 2 Step 1 code block contains the `_LEGACY` raise but NOT the `_SCRATCH_FIXTURE` raise.
2. The explanatory comment references §4.2.2 sentinel read-discipline.
3. Mechanical check: paste the §8.2.1 scratch canary snippet against a scratch DB — it runs without `ValueError` from producer-path.

### V2. §4.2.2 Sentinel Read-Discipline subsection articulates write-vs-read asymmetry

**v7 fix:** New subsection (§4.2.2) explicitly tables out the policy for `_LEGACY` and `_SCRATCH_FIXTURE` across four paths: producer-write, bond-scoped lookup, felt-time aggregate readers, scratch-canary-path. Names the substrate discipline for future readers (any new aggregate-reader must explicitly handle both sentinels).

**Verify:**
1. §4.2.2 exists between §4.2.1 and §4.3.
2. The policy table is accurate:
   - `_LEGACY`: refuse at producer, refuse at lookup, exclude at aggregates.
   - `_SCRATCH_FIXTURE`: **accept at producer**, refuse at lookup, exclude at aggregates.
3. The substrate-discipline-for-future-readers paragraph names the requirement explicitly.
4. Cross-reference: §6.2.2 (Step 1 comment) and §8.2.1 (scratch canary preamble) both reference §4.2.2.

### V3. §8.2.1 scratch canary defines `_SCRATCH_FIXTURE_BOND_ID` constant

**v7 fix:** Added `_SCRATCH_FIXTURE_BOND_ID = "_SCRATCH_FIXTURE"` constant definition at the top of the runnable Python block, BEFORE the `sd.record_salience_event(...)` call. Inline comment references §4.2.2.

**Verify:**
1. The constant is defined in the snippet.
2. The constant is referenced in both the insert and the lookup (consistency across H1 fix from v6).
3. The snippet as pasted runs without `NameError`.

### V4. RED #49-#51 match v7 design

**v7 fix:**
- RED #49 is INVERTED from v6: now `test_scratch_fixture_sentinel_accepted_at_producer_path` (asserts producer-path SUCCEEDS, not raises).
- RED #50 unchanged from v6: read-side refusal at lookup + aggregate-reader exclusion.
- RED #51 NEW: `test_scratch_canary_runs_end_to_end` (asserts the §8.2.1 snippet runs as pasted, including `_SCRATCH_FIXTURE_BOND_ID` definition and `meaningfulness_score > 0` assertion).

**Verify:**
1. RED #49 description is the INVERTED version (accepts not refuses).
2. RED #50 description is unchanged.
3. RED #51 exists and is mechanically feasible.
4. The §9.3 RED table total count matches §9.4 total ("Total: 51 RED tests").

### V5. Residue cleanup (Codex pass-3 M1-M3)

**v7 fixes:**
- §9.4 "Total: 51 RED tests" (was "Total: 48").
- §10 implementation surface: "51 RED tests per §9" (was "48+ ... will land at 50+").
- §10.1: "~900 LOC across 51 tests" (was "~850 LOC across 48 tests").
- §11.2: "5-column ALTER additions" + "18 = existing 13 + new 5" (was "4-column" + "17 = existing 13 + new 4").
- §5.4: canary_row prose cleaned; history reference relocated to fold-trajectory recap.
- v6 fold-summary H2 entry rewritten to honestly describe v6's mislabel of §6.2.2 as a "read site" when it's a write path; v7 resolution noted.

**Verify:**
1. `grep -c "48 RED tests"`, `grep -c "48 tests"`, `grep -c "4-column ALTER"`, `grep -c "new 4"`, `grep -c "INSERT column count = 17"` — all return 0.
2. §5.4 normative prose says only "Canary rows are tagged in the `is_canary=1` column"; JSON-LIKE history is relocated to fold-trajectory recap.
3. The v6 fold-summary H2 entry honestly names the v6 mislabel.

### V6. Spec-wide consistency check

Final spot-check:
- Header reads v7.
- Footer reads "End of v7 spec draft."
- Review trajectory recap names v1 through v7 honestly, with each version's verdict.
- No leftover "v6 (this draft)" or "Ready for Codex pass-3" language pointing at the wrong version.

## Verdict options

- **RATIFY-CLEAR (PROCEED TO CANONICALIZATION):** v7 self-contradiction resolved; implementation-ready.
- **RATIFY-WITH-AMENDMENTS:** small text fixes; v8 lands them.
- **RECONSIDER:** another contradiction or load-bearing issue surfaced.

## Out of scope (do NOT re-review)

Everything outside V1-V6 above. The slice has been through three council passes and three Codex panel passes. Pass-4 exists ONLY to verify the v6→v7 contradiction resolution.

## Output

Write to `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-pass4.md`.

---

**End of brief.** Rohit relays to Codex; panel review returns at the named output path; Claude verifies firsthand against the returned artifact + git state per [[feedback_review_artifact_provenance]].
