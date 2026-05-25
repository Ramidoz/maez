# Codex Engineering Panel Brief — Subjective-Duration Meaningful-Salience Seam Pass 2

**Prepared:** 2026-05-25
**Artifact:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` (DRAFT v5; 1942 lines)
**Parent commit:** `fb2f781 feat(felt-time): implement subjective duration substrate`
**Relay from:** Rohit (human operator)
**Council state:** Pass-1 (6 roles): RATIFY-WITH-AMENDMENTS, 0 RECONSIDER (~35 folds). Pass-2 (tightly scoped): RATIFY-WITH-AMENDMENTS, 1 fold-as-text-only catch. Pass-3 (tightly scoped on v4 canary redesign covenant semantics): Buber NEEDS-AMENDMENT 3 small framing folds + Hume CARRIES-WEIGHT + Locke CARRIES-WEIGHT + 1 optional Locke fold — all applied in v5. The covenant lane has cleared three review cycles.

---

## What changed between v3 → v5

Codex pass-1 returned RECONSIDER on v3 (load-bearing H1: canary writes positive `meaningful_exchange` to live never-delete DB; aggregate readers would count it as real resonance). v5 applies all Codex pass-1 folds + Claude council pass-3 folds.

**v4 changes (Codex pass-1 amendments):**

1. **Two-canary redesign (Codex H1 + Rohit v4 tightening).**
   - §8.2.1 Scratch E2E canary: `meaningful_exchange` + synthetic snapshots, scratch DB only, asserts `meaningfulness_score > 0`. Never touches live DB.
   - §8.2.2 Live-path canary: `salience_event_kind="manual_test_event"` + producer kwargs + `is_canary=True`. Auto-compute formula returns 0.0 because kind is gated. Aggregate readers structurally exclude the row (kind gate + `bond_id != '_LEGACY'` + `is_canary = 0`). Three-layer defense.

2. **New 5th ALTER column: `is_canary INTEGER NOT NULL DEFAULT 0`** (Rohit's v4 tightening). Replaces v3's brittle `metadata_json LIKE '%"canary_row":true%'` matching with a real queryable column. The column is set via explicit kwarg, decoupled from `producer_ref`, queryable from SQL.

3. **Aggregate-reader exclusion (Codex H1+H3 load-bearing fold).** `_residual_resonance()` and `_recent_meaningful_event_count_capped()` gain `AND bond_id != '_LEGACY' AND is_canary = 0` filters at `core/evolution/subjective_duration.py:630` and `:656`. The slice now structurally ensures pre-bond-substrate rows AND canary rows are excluded from felt-time computation while remaining in the DB (never-delete preserved).

4. **Rollback redesign (Codex H2).** §8.3 default is now code-revert preserving the ADD-only migrated DB; old code names 13 columns explicitly and ignores extras. DB-restore is reserved for explicitly-justified emergency. RED #48 verifies forward-compatibility.

5. **Diagnostic-v2 signature specified (Codex H4).** §6.5 names the `_diagnostic_row(...)` signature update, 5 new return keys, `schema_version="subjective-duration-diagnostic-v2"` unconditional on all post-migration rows. RED #43 verifies.

6. **API name corrected (Codex H6).** All references to `record_meaningful_salience_event(...)` corrected to `record_salience_event(...)` — the existing method is extended, not replaced. RED #47 verifies via introspection.

7. **MANUAL_TEST_PRODUCER sunset clarified (Codex H7).** §5.4 sunset trigger removes production `MANUAL_TEST_PRODUCER` AND retires §8.2.2 live-path canary when Slice 2 lands `DRIVE_DRIVEN_CURIOSITY` (Slice 2's first real producer event serves the verification role).

8. **§5 section ordering corrected (Codex M16).** §5.3/§5.4/§5.5 now in physical order; all cross-references updated.

9. **9 Medium folds applied:** concrete dicts in canary scripts (Codex M8), first-observation None test #45 (M9), UUID-based producer_event_id (M10), RED #3 expects `bond_id='_LEGACY'` (M11), completeness preflight + sovereignty-first explicit (M12), 48-test + LOC counts updated (M13), watchdog non-interaction wording (M14), implementation scope wording widened (M15).

**v5 changes (Claude council pass-3 amendments on the v4 canary redesign):**

10. **Buber A1:** §8.2.1 scratch canary uses explicit `_SCRATCH_FIXTURE_BOND_ID = "_SCRATCH_FIXTURE"` sentinel instead of fabricated `"scratch_canary_bond"` string. Sentinel is refused at every production read site (same pattern as `_LEGACY`).

11. **Buber A2:** §8.2.2 gains a paragraph naming the live-path row as substrate-self-verification artifact, NOT a felt-event. Explicit dual acknowledgment: yes in the bond's record AND yes structurally non-felt.

12. **Buber A3:** §8.2.2 quotes the §5.4 retirement commitment at the canary site so neither can drift independently.

13. **Locke optional fold:** §5.4 sunset actions now list 5 bullets (was 4); the 5th bullet retires the §8.2.2 live-path canary entirely at Slice 2 merge.

## Pass-2 verification request (focused)

The covenant lane has cleared three cycles. Pass-2 is asked to verify ONLY:

### Category A — The v4 + v5 changes against live code

A1. **Aggregate-reader exclusion mechanics.** Verify the proposed SQL changes at `core/evolution/subjective_duration.py:630` (`_residual_resonance`) and `:656` (`_recent_meaningful_event_count_capped`) integrate cleanly with the existing WHERE clauses. Specifically: do the existing queries use prepared statements? Are there any caching layers that would skip the new filters?

A2. **5th ALTER column `is_canary`.** Re-run PRAGMA after applying the v5 migration script on a scratch copy:
   ```bash
   cp /home/rohit/maez/memory/subjective_duration.db /tmp/sd_v5_pass2.db
   # Run the v5 _migrate_meaningful_salience_seam against /tmp/sd_v5_pass2.db
   sqlite3 /tmp/sd_v5_pass2.db "PRAGMA table_info(subjective_duration_salience_events);"
   ```
   Verify 19 columns total (14 original + 5 new) with `is_canary INTEGER NOT NULL DEFAULT 0` as column 18.

A3. **Idempotent re-migration.** Run the migration twice. Verify zero schema changes between runs.

A4. **`_SCRATCH_FIXTURE` sentinel enforcement.** Verify the v5 §8.2.1 scratch canary's `_SCRATCH_FIXTURE_BOND_ID = "_SCRATCH_FIXTURE"` sentinel is documented for refusal at production read sites (§6.2.2 producer-path validation, §7.1 lookup) parallel to the `_LEGACY` refusal pattern. Flag any read site that should refuse the sentinel but doesn't.

A5. **API name in spec.** Confirm zero remaining `record_meaningful_salience_event(...)` references except (a) the explicit "this was the wrong name; v4 corrected it" mentions and (b) RED #47 test that asserts the method doesn't exist.

### Category B — Two-canary design mechanical feasibility

B1. **Scratch E2E canary runnability.** Verify `/tmp/scratch_canary.db` workflow per §8.2.1 actually runs against current SubjectiveDuration class. Specifically: does setting `MAEZ_SUBJECTIVE_DURATION_DB=/tmp/scratch_canary.db` in the environment correctly route the substrate to the scratch DB without affecting the live DB?

B2. **Live-path canary kind-gating proof.** Verify §8.2.2's claim that `salience_event_kind="manual_test_event"` produces `meaningfulness_score=0.0` deterministically (via the auto-compute formula's gate at `subjective_duration.py:518`). Test fixture: pass synthetic snapshots with non-zero delta; assert score is exactly 0.0.

B3. **Aggregate-reader exclusion three-layer defense.** Verify that even if the kind gate were removed, the aggregate readers would STILL exclude the canary row via `is_canary = 0` filter. And even if the is_canary filter were removed, the bond_id filter would still exclude `_LEGACY` rows. Three independent defenses.

B4. **RED #41 mechanical feasibility.** End-to-end test: write a live-path canary; assert `_residual_resonance()` and `_recent_meaningful_event_count_capped()` return identical values before and after the write. This is the load-bearing canary-pollution-prevention test.

### Category C — Rollback design integrity

C1. **§8.3.1 default rollback (code-revert preserving DB).** Verify the claim that reverted code SELECTing 13 explicit columns will work on a DB with 19 columns. Test: revert the slice code, run an existing daemon SELECT, assert no error.

C2. **§8.3.2 emergency DB-restore.** Verify the `.corrupt.` snapshot procedure preserves forensic data. Verify the explicit-operator-acceptance step is documented.

C3. **RED #48 default-rollback DB-preservation.** Verify the test fixture can construct the post-merge state, revert code, and verify old-code SELECTs still work.

### Category D — Spec internal consistency

D1. **§5 section ordering.** Confirm physical order matches labels: §5.1 → §5.2 → §5.3 → §5.4 → §5.5.

D2. **Cross-references.** Walk all `§5.x` references in v5 and verify each points at content matching its claim.

D3. **RED test numbering.** v5 has 48 tests. Confirm numbering is sequential 1-48 with no gaps and no duplicates. Confirm RED #38 (anti-laundering) is the only #38.

D4. **Version-state hygiene.** Header says v5. Footer says ready for Codex pass-2. No leftover "v2" or "v3" status text except in the review trajectory section.

D5. **5th ALTER column documented across all surfaces.** §1.3 schema summary lists 5 columns. §4.1 ALTER block lists 5 columns. §4.2 migrations list lists 5 columns. §6.4 INSERT statement lists 18 columns total. §7.2 dataclass includes `is_canary`. §10.1 LOC estimate accounts for the column.

### Category E — Scope realism

E1. **~310 LOC estimate.** Verify v5's LOC estimate is realistic given the v4+v5 surface (was ~250 in v3; +60 for is_canary + aggregate-reader changes + diagnostic-v2 signature + first-observation None handling). Two added scripts (smoke + scratch_e2e_canary.py).

E2. **48 RED tests.** Verify each test is feasible against parent `fb2f781`. Flag any infeasible.

E3. **Single slice or split?** Confirm the slice does not need further decomposition. The v4 redesign added scope (aggregate-reader exclusion) but stayed coherent.

### Category F — Any new spec-text issues

F1. **Walk for remaining stale references** (any v2/v3/v4 numbering that should be v5; any prior-version sectionrefs).

F2. **Plain-language readout (§13)** — confirm it accurately describes v5's two-canary design, not v3's single canary.

---

## What is NOT in scope for pass-2

- Re-litigating the covenant axes already cleared (pass-1, pass-2, pass-3 on canary redesign).
- Re-verifying the 32/33 schema claims Descartes pass-1 already firsthand-verified.
- Re-verifying the 7 pass-2-verified load-bearing folds Claude council already CARRIES-WEIGHT'd.

The covenant lane is closed for this slice unless v5 introduces NEW covenant concerns.

## Verdict options

- **RATIFY-CLEAR (PROCEED TO CANONICALIZATION):** v5 is engineering-sound; ready for implementation.
- **RATIFY-WITH-AMENDMENTS:** specific amendments; v6 lands them; pass-3 not required unless covenant axes touched.
- **RECONSIDER:** another engineering issue. Fold first.

## Output

Write to `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-pass2.md` in the standard format.

---

## Memory entries relevant to this review

- [[feedback_schema_verification_pragma_first]] — the rule that drove this slice's existence
- [[feedback_spec_drafts_must_trace_real_surfaces]] — parent rule
- [[feedback_council_panel_lane_complementarity]] — why both lanes catch different things
- [[feedback_growth_vs_hardcoding_distinction]] — closed-vocabulary ProducerRef + is_canary semantics
- [[feedback_never_delete_maez_memory]] — append-only schema (ADD COLUMN only; rollback preserves DB by default)
- [[feedback_anti_coercion_is_not_no_initiation]] — applied internally to canary-as-substrate-self-verification

---

**End of brief.** Rohit relays to Codex; panel review returns at the named output path; Claude verifies firsthand against the returned artifact + git state per [[feedback_review_artifact_provenance]].
