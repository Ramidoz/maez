# Codex Engineering Panel Brief — Subjective-Duration Meaningful-Salience Seam Pass 5

**Prepared:** 2026-05-25
**Artifact:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` (DRAFT v8)
**Parent commit:** `fb2f781`
**Relay from:** Rohit
**Pass shape:** TIGHTLY FOCUSED — verify v7 → v8 next-step contradiction resolution.

---

## Cycle history (for context only — do NOT re-litigate)

- Council pass-1/2/3 all cleared (covenant axes settled).
- Codex pass-1: RECONSIDER on canary-pollution (H1). v4 redesigned.
- Codex pass-2: RECONSIDER on v5 implementation tripwires. v6 fixed 11.
- Codex pass-3: RECONSIDER on v6 self-contradiction (producer-path refusal of `_SCRATCH_FIXTURE` blocked the canary write). v7 resolved by removing the refusal + naming write-vs-read asymmetry in new §4.2.2.
- Codex pass-4 (just completed): RECONSIDER on v7 next-step contradiction (canary write succeeded but verification via `lookup_meaningful_salience_event_record(bond_id="_SCRATCH_FIXTURE", ...)` would still fail at §7.1 refusal). v8 resolves by moving canary verification to direct SQL.

**Author's note on the 8-step discipline.** Before declaring v8 done, I applied the discipline from the just-written memory `feedback_fold_second_order_contradictions`: dependency-map grep + write-path trace + read-path trace + test-path trace + fold-summary trace + cross-reference trace + RED-test trace. All six paths now consistent with v8 design (verified at end of v8 fold). This pass exists for Codex to confirm the discipline-checked state; not for Codex to catch another fold-as-text-only failure.

## What v8 changed

### Single load-bearing fix: scratch canary verifies via direct SQL

**The contradiction v7 left:** §8.2.1 canary wrote under `_SCRATCH_FIXTURE_BOND_ID` (producer-path accepted in v7), then verified via `lookup_meaningful_salience_event_record(bond_id=_SCRATCH_FIXTURE_BOND_ID, ...)` — but §7.1 refused that lookup. Canary got past write, failed at read.

**The v8 design choice (of Codex pass-4's three options, I picked #2):** keep the public lookup API absolute on refusing sentinels (the API is production-only surface; sentinels are misuse-shaped); the canary uses direct `sqlite3.connect(scratch_db_path)` SELECT for verification.

**Why option 2 over the alternatives:**
- Option 1 (lookup permits sentinel only under "scratch-mode proof"): brittle. Either an env-var check or a `db_path != _default_db_path()` check, both fragile and tied to deployment convention.
- Option 3 (private test-only lookup helper): couples production module to test-only paths.
- Option 2: clean separation. Public lookup is production API only. Substrate self-test fixtures use the lower-level SQL path. Articulated in §4.2.2's new 4th row.

### Six surfaces touched in v8

1. **§8.2.1 canary script:** replaced `record = sd.lookup_meaningful_salience_event_record(...)` block with `sqlite3.connect(scratch_db_path).execute("SELECT ...")` + `fetchone()`. Assertions updated to use row dict-style access (`row["meaningfulness_score"]`).
2. **§4.2.2 policy table:** gained the 4th "Scratch-canary-path (§8.2.1; v8 row)" row explicitly stating: VERIFIES VIA DIRECT SQL, with rationale and the exact SQL pattern.
3. **§4.2.2 substrate-discipline-for-future-readers paragraph:** rewritten to distinguish (a) production readers (must exclude sentinels) from (b) substrate self-test readers (may use direct SQL to verify their own writes).
4. **RED #51 description:** rewritten to specify direct SQL verification, not public lookup API. Includes explicit non-conflict note with RED #50 ("RED #50 = public lookup refuses sentinel; RED #51 = canary uses direct SQL").
5. **Header + footer:** bumped to v8 with review trajectory recap covering all 8 versions and 7 review-cycle catches.
6. **v8 fold summary block:** added at top of spec describing v7→v8 fix.

### Surfaces verified UNCHANGED (intentionally) via 6-path trace

- §6.2.2 producer-path: still ACCEPTS `_SCRATCH_FIXTURE` (v7 design preserved).
- §7.1 lookup: still REFUSES `_SCRATCH_FIXTURE` (v6 design preserved; v8 keeps).
- §4.2.1 aggregate readers: still EXCLUDE both sentinels via `NOT IN (...)` clause.
- §8.2.2 live-path canary: still uses public lookup with Rohit's REAL bond_id (not sentinel). Real bond_ids aren't refused. Fine.
- RED #14 (lookup returns producer-driven record): unchanged. Tests lookup with real bond_id.
- RED #49 (producer-path accepts sentinel): unchanged from v7.
- RED #50 (lookup refuses sentinel): unchanged from v6/v7.
- All column counts (5 new ALTER columns, 18 INSERT columns).
- All test counts (51 RED tests).

## What pass-5 is asked to verify

### V1. §8.2.1 canary uses direct SQL, not public lookup

**Verify:**
1. The `record = sd.lookup_meaningful_salience_event_record(...)` block is GONE from §8.2.1.
2. A `sqlite3.connect(scratch_db_path).execute(...)` SELECT block is present.
3. The SELECT WHERE clause matches `(bond_id = ? AND producer_event_id = ?)` with `_SCRATCH_FIXTURE_BOND_ID` and `event_id_str`.
4. Assertions use row dict-style access and assert `meaningfulness_score > 0`, `is_canary == 1`, etc.
5. The pasted snippet runs end-to-end against a scratch DB without `ValueError`, `NameError`, or `LookupError`. **Mechanical test recommended:** run the snippet against a fresh scratch DB and observe success.

### V2. §4.2.2 policy table has 4 rows

**Verify the table has rows for:** producer-write, bond-scoped lookup, felt-time aggregate readers, AND scratch-canary-path. The 4th row's `_SCRATCH_FIXTURE` policy explicitly says "VERIFIES VIA DIRECT SQL" with the SQL pattern.

### V3. §4.2.2 substrate-discipline-for-future-readers paragraph distinguishes reader classes

**Verify the paragraph names TWO reader classes:** (1) production readers must exclude sentinels; (2) substrate self-test readers (canaries) may use direct SQL. The canary's status as a self-test reader is explicit.

### V4. RED #50 and RED #51 are mutually non-conflicting

**Verify:**
- RED #50 description says public lookup refuses `_SCRATCH_FIXTURE` → ValueError.
- RED #51 description says canary uses direct SQL → no ValueError.
- The RED #51 description explicitly references the non-conflict with RED #50.

### V5. No regression in v7 surfaces

**Verify the 6-path trace's "unchanged" claims:**
- §6.2.2 producer-path still has no `_SCRATCH_FIXTURE` raise.
- §7.1 lookup still has the `_SCRATCH_FIXTURE` raise.
- §4.2.1 aggregate readers still have `NOT IN ('_LEGACY', '_SCRATCH_FIXTURE')`.
- §8.2.2 live-path canary still uses public lookup (with real bond_id).

### V6. Spec-wide consistency

- Header reads v8, footer reads "End of v8 spec draft."
- Review trajectory names v1 through v8 with each version's verdict.
- No leftover "v7 (this draft)" or "Ready for Codex pass-4" markers.

## Verdict options

- **RATIFY-CLEAR (PROCEED TO CANONICALIZATION):** v8 resolves the next-step contradiction without introducing a new one; implementation-ready.
- **RATIFY-WITH-AMENDMENTS:** small text fixes; v9 lands them.
- **RECONSIDER:** another contradiction surfaced.

If RATIFY-CLEAR, the slice is ready for v8 → v1 CANONICAL.

## Out of scope (do NOT re-review)

- Any v1-v7 axis already cleared.
- Architectural shape, schema design, two-canary discipline, aggregate-reader exclusion, rollback design, sentinel semantics for `_LEGACY`, producer-path acceptance of `_SCRATCH_FIXTURE`.
- Everything outside V1-V6 above.

## Output

Write to `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-pass5.md`.

---

**End of brief.** Rohit relays to Codex; panel review returns at the named output path; Claude verifies firsthand against the returned artifact + git state per [[feedback_review_artifact_provenance]].
