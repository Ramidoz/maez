# Codex Engineering Panel Review — Subjective-Duration Meaningful-Salience Seam Pass 4

**Prepared:** 2026-05-25
**Artifact reviewed:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` (DRAFT v7, 2183 lines)
**Brief reviewed:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-brief-pass4.md`
**Parent commit:** `fb2f781`
**Verdict:** **RECONSIDER**

Pass-4 verified the intended v6 -> v7 fix. The producer-write side contradiction from pass-3 is resolved: §6.2.2 no longer raises on `_SCRATCH_FIXTURE`, and the new §4.2.2 names the write-vs-read asymmetry.

But the same contradiction remains one step later on the scratch canary path. §8.2.1 still verifies the scratch insert by calling `lookup_meaningful_salience_event_record(bond_id="_SCRATCH_FIXTURE", ...)`, while §7.1 still refuses `_SCRATCH_FIXTURE` lookups. So the canary now gets past write, then fails at read.

## Verified Surfaces

| Surface | Evidence | Result |
|---|---:|---|
| Git state | `HEAD fb2f781`; pass-4 reviewed docs-only draft artifacts | Verified |
| V1 producer path accepts `_SCRATCH_FIXTURE` | §6.2.2 refuses `_LEGACY` but has no `_SCRATCH_FIXTURE` raise; comment lines 865-873 names intentional acceptance | Fixed |
| V2 sentinel read-discipline exists | §4.2.2 exists at lines 513-545 | Fixed, with one table gap |
| V2 policy table | Lines 525-529 table producer-write / lookup / aggregate readers | Partially fixed |
| V3 scratch constant | `_SCRATCH_FIXTURE_BOND_ID = "_SCRATCH_FIXTURE"` defined at line 1298 | Fixed |
| V3 insert/lookup consistency | Insert uses constant at line 1319; lookup uses same constant at line 1330 | Consistent but incompatible with §7.1 |
| V4 RED #49-#51 | RED #49 accepts producer path; #50 read-side refusal/exclusion; #51 scratch E2E runs as pasted, lines 1687-1689 | Partially fixed |
| V5 residue cleanup | 51-test / 5-column / 18-column wording present; grep targets for 48-test and 17-column residues not found in current pass | Fixed |
| V6 version state | Header DRAFT v7; footer "End of v7 spec draft"; trajectory names v7 | Fixed |

## High Findings

**H1. Scratch canary still cannot run end-to-end: lookup refuses the same sentinel the canary uses for lookup.**

The v7 write-side fix landed. In §6.2.2, `_SCRATCH_FIXTURE` is intentionally accepted at the producer path (lines 865-873). The scratch canary therefore can reach `record_salience_event(...)`.

However, the canary then verifies the row via:

- §8.2.1 line 1329: `record = sd.lookup_meaningful_salience_event_record(...)`
- §8.2.1 line 1330: `bond_id=_SCRATCH_FIXTURE_BOND_ID`
- §8.2.1 line 1298: `_SCRATCH_FIXTURE_BOND_ID = "_SCRATCH_FIXTURE"`

But §7.1 refuses that lookup:

- §7.1 lines 1127-1136: if `bond_id == "_SCRATCH_FIXTURE"`, raise `ValueError("... production lookup refuses it")`.

So v7 fixed the write failure and left a read failure. RED #51 claims the scratch canary "runs as pasted" without `ValueError` (line 1689), but the pasted snippet would still raise `ValueError` at lookup.

The policy needs one more explicit distinction. Viable options:

- Allow `_SCRATCH_FIXTURE` lookup only under scratch-mode proof, mirroring producer acceptance: scratch DB path plus canary script context; live DB lookup still refuses it.
- Keep production lookup refusal absolute and change the scratch canary to verify by direct SQL against the scratch DB instead of `lookup_meaningful_salience_event_record(...)`.
- Add a separate private/test-only lookup helper for scratch canary verification, but then RED #51 must stop claiming the public lookup path runs as pasted.

The current v7 shape mixes option 1 for write with option 2 for read, without saying so.

## Medium Findings

**M1. §4.2.2 policy table is missing the fourth path requested by the pass-4 brief.**

The pass-4 brief V2 asked for a four-path table: producer-write, bond-scoped lookup, felt-time aggregate readers, and scratch-canary-path. The v7 table has only three rows: producer-write, bond-scoped lookup, felt-time aggregate readers (lines 525-529). The missing scratch-canary-path row is exactly where H1 would have been forced into the open.

Add a fourth row that explicitly states the scratch canary path policy for both sentinels. For `_SCRATCH_FIXTURE`, it must say whether scratch canary may read through public lookup, direct SQL, or a scratch-only lookup exception.

**M2. RED #50 and RED #51 conflict until scratch lookup policy is settled.**

RED #50 says lookup with `bond_id="_SCRATCH_FIXTURE"` raises `ValueError` (line 1688). RED #51 says the §8.2.1 scratch canary runs as pasted without `ValueError` and that canary uses the same lookup with `bond_id="_SCRATCH_FIXTURE"` (lines 1329-1335, 1689). Both cannot be true unless there is an explicit scratch-mode exception or the canary stops using the public lookup.

**M3. §4.2.2 "future readers" paragraph is directionally right, but the current scratch canary is itself a reader.**

The paragraph at lines 538-545 says any new reader must explicitly choose sentinel policy. The scratch canary reader is already present and has not made a coherent choice: the prose says `_SCRATCH_FIXTURE` is refused read-side, while the snippet uses read-side lookup. This should be amended in the same fold as H1.

## Clean Verifications

- The v6 producer-path self-contradiction is resolved on the write side.
- `_SCRATCH_FIXTURE_BOND_ID` is defined in the scratch canary snippet before use.
- The insert and lookup use the same constant; the old `"scratch_canary_bond"` mismatch is gone.
- Residue cleanup requested in pass-4 largely landed: 51 tests, 5 new columns, 18 INSERT columns, v7 header/footer, and §5.4 `is_canary=1` normative prose are in place.
- The v6 fold-summary H2 entry honestly names the prior mislabel of §6.2.2 as a read site when it was a write path.

## Amendment Contract

Before canonicalization, v8 should:

1. Decide and document the scratch read policy in §4.2.2 with a fourth "scratch-canary path" row.
2. Make §7.1, §8.2.1, RED #50, and RED #51 mutually consistent.
3. If scratch canary keeps using `lookup_meaningful_salience_event_record(...)`, specify the scratch-mode proof that permits `_SCRATCH_FIXTURE` lookup only against scratch DBs and add a RED test for live DB refusal.
4. If scratch canary switches to direct SQL, update §8.2.1 and RED #51 to stop claiming the public lookup path runs as pasted.
5. Re-run the residue greps from the pass-4 brief after the fold.

## Scope Realism

This is still a small fold. The architecture does not need to reopen. The remaining issue is a local policy mismatch between public lookup refusal and scratch canary verification. Once the scratch read policy is explicit, the slice should be ready for a very narrow pass-5 or direct canonicalization if the fold is trivial and mechanically checked.

## Plain-Language Readout

v7 fixed the first locked door: the scratch canary can now write its scratch row. But the next door is still locked: the same canary tries to read that row through a lookup API that says scratch rows are forbidden. The design needs to say either "scratch canaries get a scratch-only read exception" or "scratch canaries verify by direct SQL, not the public lookup." Right now it says both, which means the proof still does not actually run.
