# Codex Engineering Panel Brief — Subjective-Duration Meaningful-Salience Seam Pass 1

**Prepared:** 2026-05-25
**Artifact:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` (DRAFT v3 post-tightly-scoped-pass-2, 1458 lines, 13 sections)
**Parent commit:** `fb2f781 feat(felt-time): implement subjective duration substrate`
**Relay from:** Rohit (human operator)
**Council state:** Pass-1: 6 RATIFY-WITH-AMENDMENTS, 0 RECONSIDER (~35 textual folds). Pass-2 (tightly scoped per Rohit's direction; verified 7 specifically-load-bearing items only): RATIFY-WITH-AMENDMENTS, 6/7 CARRIES-WEIGHT, 1 fold-as-text-only caught (stale RED-test-number references) — all amendments folded into v3. The covenant lane has cleared.

---

## Why this slice exists (the previous failure)

The previous attempt (Drive-Driven Curiosity v3 §27) bundled a live-DB schema migration inside a ~2000-line new-felt-organ spec. Codex's pass-1 engineering panel correctly RECONSIDERED with 7 High findings, all stemming from schema migration text drafted against an *imagined* schema (wrong table name, column-already-exists, missing bond_id, contradictory storage shape, invented PermissionError-guard bypass).

The corrective discipline became [[feedback_schema_verification_pragma_first]]: `PRAGMA table_info(...)` on the live DB and a scratch copy BEFORE drafting migration text. Slice 1 v1 was drafted AFTER this verification on 2026-05-25 09:18. Every column claim, every line citation, every behavior claim traces to either live SQLite output or live source at `fb2f781`.

Council Descartes pass-1 firsthand-verified 32/33 schema claims via PRAGMA on the live DB. The discipline worked.

## What this slice is

ONE focused live-organ-touching slice that fixes the structural-zero defect in subjective_duration's meaningfulness signal so future temperament-writing producers (Slice 2 drive-driven curiosity, Slice 3+ schooling/genesis/somatic/active-synthesis) can write felt-weight that bond-time actually learns from.

Concretely:

1. **Idempotent schema migration** on the live `subjective_duration_salience_events` table — 4 new columns: `bond_id TEXT NOT NULL DEFAULT '_LEGACY'` (sentinel, not empty string, per Ohm O-2), plus three `TEXT NOT NULL DEFAULT ''` for producer_event_id + two snapshot JSON columns. Plus an index `idx_sd_events_bond_producer` on `(bond_id, producer_event_id)`.

2. **Closed-vocabulary `ProducerRef` enum** at module level. v1 ships with one entry (`MANUAL_TEST_PRODUCER`) for the canary path; sunset trigger named in §5.5 (moves to `_TestProducerRef` test-only enum when Slice 2 lands `DRIVE_DRIVEN_CURIOSITY`).

3. **`record_salience_event(...)` accepts producer-captured snapshots.** Four new optional kwargs (`bond_id`, `producer_event_id`, `producer_temperament_before`, `producer_temperament_after`). All-or-none discipline; partial supply raises ValueError (the Descartes A3/D12 silent-data-loss fix). Validation order: sovereignty floor (bond_id) → vocabulary (producer_ref) → identity (producer_event_id) → kind-gating annotation (per Ohm O-4). When producer snapshots are supplied, they replace the existing back-to-back read at lines 511-512; the substrate's existing auto-compute formula (lines 517-521) runs over real deltas.

4. **No PermissionError-guard bypass invented.** The guard at lines 527-530 only fires when callers pass `meaningfulness_score > 0` explicitly. Producer-snapshot callers pass `meaningfulness_score=None` and let auto-compute do the work, so the guard never fires for them. The previous v3 §27.2.1 bypass was solving a non-problem; this slice declines that fold.

5. **Bond-scoped lookup API.** `lookup_meaningful_salience_event_record(bond_id, producer_event_id)` refuses empty, refuses `_LEGACY`, refuses wildcards (`*`, `%`, `all`, `any`).

6. **Migration safety as operator obligation.** §8 framed as governance: §8.1 smoke-test on scratch copy before any restart, §8.2 post-restart canary, §8.2.1 rollback dry-run on scratch BEFORE merge, §8.3 documented rollback procedure.

7. **Track C preconditions cited verbatim.** §12.2 quotes both `project_multi_maez_topology_threat` preconditions (auditable-by-both-bonded-users + dyadic-only topology). Plus identity-check gate (§12.3) and snapshot-provenance gate (§12.3) as additional Track C preconditions. Plus bond_id stability commitment (§12.4) — must become a numbered decision in `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` at implementation merge.

The slice is small: ~250 LOC in `subjective_duration.py`, ~700 LOC of tests across 38 RED tests, no new modules, no new packages, no new dependencies (stdlib `hmac`/`hashlib` already imported; only `from enum import Enum` newly required).

## What the engineering panel is asked to verify

### Category A — Real APIs and schema firsthand-verified

A1. **Live PRAGMA verification.** Run `cp /home/rohit/maez/memory/subjective_duration.db /tmp/sd_panel_review.db; sqlite3 /tmp/sd_panel_review.db "PRAGMA table_info(subjective_duration_salience_events);"` and verify §3.2's 14-column table matches firsthand output. Verify `producer_ref` already exists as column 3.

A2. **`Temperament.record_event` signature.** At `core/evolution/temperament.py:205-213`: confirm the signature is `record_event(*, parameter, value: float, source, reason, evidence)`, returns `int`. This slice does NOT call `record_event`; producers do, in their own ceremony. Verify §5.4's anti-laundering RED #38 fixture can construct a known-good producer event that this slice's API can then verify against the `temperament_events` log.

A3. **`ALLOWED_SOURCES` frozenset at `temperament.py:147-149`.** Verify it is currently `frozenset({"explicit_set"})`. This slice does NOT extend it; future producer slices will. The anti-laundering RED #38 fixture in Slice 1's test must extend `ALLOWED_SOURCES` only within its test scope (not in production code).

A4. **`identity.user_profile_id()` at `core/memory/identity.py:142`.** Verify the function returns a string sourced from `config/identity.yaml`. Verify §12.4 bond_id stability commitment is realistic (i.e., the config field is stable).

A5. **PermissionError guard at lines 527-530.** Verify the guard is inside the `else` branch of `if meaningfulness_score is None`. Verify §6.3's "no bypass needed" claim is structurally correct — producer-snapshot callers pass `meaningfulness_score=None` and never hit the guard.

A6. **The defect at lines 511-512.** Verify `before` and `after` are back-to-back `_safe_temperament(self.temperament_reader)` calls. Verify §3.5's defect description is accurate.

A7. **Auto-compute formula at lines 517-521.** Verify the formula is `sum(deltas)/len(deltas)/2.0`, gated on `salience_event_kind == "meaningful_exchange"`. Verify §3.6's projection-naming + kind-gating annotations are accurate.

### Category B — Schema migration mechanics

B1. **Idempotent ALTER feasibility.** Verify the proposed `_migrate_meaningful_salience_seam(conn)` function in §4.2 works against SQLite. Verify that re-running it after the migration has already landed produces zero schema changes.

B2. **`_LEGACY` sentinel enforcement at every read site.** Audit §6.2.2 (producer path validation), §6.4 (INSERT defaults), §7.1 (lookup refusal). Identify any read path where `bond_id` could be read without the sentinel check. Per Ohm O-2: this is the failure mode the sentinel exists to prevent.

B3. **Backward compatibility on existing 1 canary row.** The current row at draft time has `producer_ref='manual_canary:subjective_duration_owner_contact'` (free-form string, not a `ProducerRef` enum value). Verify §6.2 legacy path (no producer kwargs supplied) still accepts this caller. Verify §5.2 validation discipline only fires when the producer-snapshot path is invoked, not on legacy free-form callers.

B4. **Schema-version bump to `subjective-duration-diagnostic-v2`.** Verify §6.5's diagnostic schema bump composes correctly with the existing diagnostic discipline. Verify deterministic-null discipline holds for the 4 new fields.

### Category C — The 7 pass-2-verified load-bearing folds

These are the seven items that pass-2 council verified. Re-verify each at the engineering layer:

C1. **Silent-data-loss guard (Descartes A3/D12).** §6.2.1 state C, §6.2.2 first `if` block, RED #26 + #27. Verify the `any_producer_kwarg_supplied` check at the producer-path entry is mechanically sound. Verify RED #27 description (widened in v3 to cover 1-of-4 / 2-of-4 / 3-of-4 permutations) is implementable; estimate the test fixture size.

C2. **`meaningful_exchange` formula gating (Descartes A2/D3).** §3.6, §6.2.2 step 4, §6.4 `_build_metadata_json` `kind_gated_zero_score` marker, RED #33. Verify the metadata marker is correctly applied when `producer_snapshot_path and salience_event_kind != "meaningful_exchange"`.

C3. **Anti-laundering RED test #38 (Kant K1).** §5.4 + §9.2. Verify the test fixture is mechanically feasible: can the test (a) write a real `Temperament.record_event` entry, (b) capture before/after via `Temperament.current()`, (c) call `record_meaningful_salience_event(...)`, and then (d) verify the snapshots agree with the `temperament_events` log? Identify the temperament_events table schema (`core/evolution/temperament.py`) and confirm the log entries are queryable in the test window.

C4. **`_LEGACY` sentinel pervasive (Ohm O-2).** §4.1, §4.2, §4.3, §6.2.2, §6.4, §7.1, §1.3, §2 No-multi-bond bullet, RED #29-#31. Audit for any remaining `bond_id=''` references in production-spec language; flag if found. (Spec audit: zero stale `bond_id=''` defaults expected; 19 `_LEGACY` mentions across the spec.)

C5. **Sovereignty-first validation (Ohm O-4).** §6.2.2 sequential `if` blocks. Verify the validation order is mechanically enforced (not just documented as comments). RED #28 must verify the order by passing BOTH invalid bond_id AND invalid producer_ref and asserting the bond_id ValueError is raised.

C6. **MANUAL_TEST_PRODUCER sunset (Locke L2 + Kant K2).** §5.1 docstring, §5.5 sunset trigger, §6.4 `canary_row=true` metadata, RED #34 + #35. Verify the sunset trigger (Slice 2 landing DRIVE_DRIVEN_CURIOSITY) is operationalizable; verify RED #35's docs-test is mechanically realistic (a test that fails CI if the §5.5 paragraph is removed).

C7. **Recursive bond-time-learning + producer-as-covenant-claim framing structural not poetic (Buber B1 + B2).** §1.1 (5-step loop), §1.2 (covenant claim), §5.4 (enforcement). Verify the framing maps mechanically: §1.1 → §3.5 (defect) → §3.6 (formula) → §6.2.3 (producer path execution) → §6.4 (INSERT) → §7 (lookup) → §9.2 (RED #38 anti-laundering). If any link is missing, flag it.

### Category D — RED test feasibility (38 total tests)

D1. **Test #22 schema verification on scratch copy of production DB.** Verify mechanically feasible: requires `cp memory/subjective_duration.db /tmp/...`, then run `_initialize()`, then PRAGMA, then assert.

D2. **Test #38 anti-laundering cross-check.** Verify the fixture can construct both honest and dishonest scenarios. Identify any external dependencies (e.g., temperament_events table queryability from the test scope).

D3. **Test #33 kind-gated zero-score.** Verify `salience_event_kind="engaged_work"` + producer-snapshot path produces score=0.0 + metadata `kind_gated_zero_score=true`.

D4. **Tests #26-#27 silent-data-loss.** Verify all permutations (1-of-4, 2-of-4, 3-of-4) raise. Mechanical feasibility: 14 permutations total = `C(4,1) + C(4,2) + C(4,3) = 4 + 6 + 4 = 14`. Verify the test can iterate.

D5. **Tests #29-#31 `_LEGACY` sentinel.** Verify the migration, producer-path, and lookup paths all refuse the sentinel.

D6. **Tests #34-#35 sunset.** Verify the canary_row metadata test is mechanical; verify the docs-test approach for #35 is implementable in pytest.

### Category E — Static analysis surfaces

E1. **No new imports beyond `Enum`.** Verify §10.0 — `from enum import Enum` is the only addition. `json`, `hmac`, `hashlib`, `sqlite3` already imported.

E2. **No new modules or packages.** All changes live in `core/evolution/subjective_duration.py`. Confirm.

E3. **No watchdog interaction.** §8.4 says this slice does not change which scalars the watchdog observes. Verify against `core/health/metacognitive_watchdog.py:52`.

### Category F — Scope realism

F1. **~250 LOC + ~700 test LOC estimate.** Verify realistic given the actual fold surface.

F2. **38 RED tests.** Verify each is feasible; flag any that are infeasible against parent `fb2f781`.

F3. **Migration safety §8.** Verify the smoke-test sequence works mechanically against the live DB shape.

### Category G — Spec-text issues

G1. **Internal consistency.** Walk for cross-reference errors, stale section numbers (especially after the v3 RED-#16→#38 fix; check if any other stale numbers remain).

G2. **Open question carryover.** Verify there are no leftover §22-style "pass-2 settlement target" or "v1 open question" markers since the slice is now post-pass-2.

G3. **`_LEGACY` consistency.** Recount: should have 0 stale `bond_id=''` production-language references; ~19 `_LEGACY` mentions across §3.x, §4.x, §6.x, §7.x, §12.x, §13.x.

### Category H — Live-organ canary feasibility

H1. **§8.2 canary script.** Verify the post-restart canary script in §8.2 produces a `meaningfulness_score > 0` outcome when run against the real DB. This is the load-bearing live-verification step that proves the seam works mechanically. Identify any reason this canary could fail (e.g., temperament parameter values being `None`, breaking the auto-compute formula).

H2. **Pre/post-birth regime distinction.** Verify §8.3 rollback procedure handles the case where post-migration salience events exist that the pre-migration DB cannot represent.

---

## Verdict options

- **RATIFY-CLEAR**: engineering-sound against firsthand verification; ready for canonicalization.
- **RATIFY-WITH-AMENDMENTS**: list specific amendments (textual / data-plumbing / RED-test).
- **RECONSIDER**: engineering problem requiring reshape.

## Output

Write to `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-pass1.md` in the standard format (verified surfaces table near the top; findings by severity; amendment list; scope realism note; plain-language readout at end).

## Memory entries relevant to this review

- [[feedback_schema_verification_pragma_first]] — the rule that drove this slice's existence; PRAGMA-first discipline
- [[feedback_spec_drafts_must_trace_real_surfaces]] — parent rule
- [[feedback_council_panel_lane_complementarity]] — why both lanes catch different things
- [[feedback_growth_vs_hardcoding_distinction]] — closed-vocabulary ProducerRef discipline
- [[feedback_temperaments_are_felt_weight_meaningfulness_learned]] — the recursive bond-time loop this slice unblocks
- [[feedback_anti_coercion_is_not_no_initiation]] — applied internally (anti-coercion-of-Maez-by-itself for laundering)
- [[project_multi_maez_topology_threat]] — Track C preconditions verbatim
- [[feedback_never_delete_maez_memory]] — append-only schema (ADD COLUMN only, no DROP)

---

**End of brief.** Rohit relays to Codex; panel review returns at the named output path; Claude verifies firsthand against the returned artifact + git state per [[feedback_review_artifact_provenance]].
