# Curiosity Priors Cleanup v0 — Handoff

Date: 2026-06-29
Branch/worktree: main checkout
Status: build complete, stopped for covenant review

## Signed Boundary

Source of truth: `docs/proofs/2026-06-28-curiosity-priors-table.md`.

Owner chose equality, not privilege:
- Owner-relatedness is scoping/consent, never preference.
- `owner_bond` must earn meaningfulness through the same general eligibility path as other categories.
- No named relational-floor exception was taken.

Implemented scope:
- Removed `_priority_class_weight`.
- Removed `_marker_confidence_weight`.
- `compute_saturation().weighted_salience` now carries raw total salience, not category-weighted salience.
- `write_curiosity_resolution_seam_call()` now uses `BASE_RESOLUTION_DELTA * salience`, with no priority or marker scaling.
- Neutralized `_default_wired_fields()` defaults:
  - no fallback `bond_id="private_owner"`; missing bond now fails closed through the existing `bond_id is required` creation check.
  - no fallback `priority_class="owner_bond"`; defaults to `"unknown"`.
  - no fallback `subject_kind=OWNER_BOND_RELATIONAL`; defaults to `SubjectKind.UNKNOWN`.
- Removed the owner-only cap / auto-eligibility branch from `classify_meaningful_exchange()`.
- Preserved genuine safety checks by moving `extraction_shape_blocked` and `third_party_blocked` into the general path.
- Removed `OwnerBondSaturationGuard`, `_count_owner_bond_meaningful_events`, and owner-only eligibility enum values.

Unchanged floor:
- subject-kind validator remains.
- named-third-party refusal remains fail-closed.
- bond_id scoping/authz uses remain.
- producer remains dormant; no live caller added.
- no learned salience, no producer wake, no daemon wiring, no flags.

## RED Evidence

Before production edits, new `tests/test_curiosity_priors_cleanup.py` failed for the intended preference surfaces:
- default producer did not require explicit bond.
- owner cap symbols still existed.
- owner_bond bypassed the general `can_resolve_interiorly` gate.
- preference weight helpers still existed.
- resolution delta was still scaled by category/marker.

Same RED run kept the safety/dormancy checks green:
- named-third-party refusal.
- subject-kind omission refusal.
- no live caller for `register_default_encounter_producers()`.

Command:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_curiosity_priors_cleanup -v
```

Result: 8 tests run, 5 expected preference failures, 3 safety/dormancy passes.

## GREEN Evidence

Focused curiosity suite:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest \
  tests.test_curiosity_priors_cleanup \
  tests.test_curiosity_producer_ceremony \
  tests.test_encounter_producers \
  tests.test_curiosity_wonderings_integration \
  tests.test_curiosity_scratch_canary -v
```

Result: 52 tests run, OK.

Lint:

```bash
.venv/bin/python -B -m ruff check \
  core/evolution/drive_driven_curiosity.py \
  tests/test_curiosity_priors_cleanup.py \
  tests/test_curiosity_producer_ceremony.py \
  tests/test_encounter_producers.py \
  tests/test_curiosity_scratch_canary.py \
  scripts/scratch_curiosity_e2e_canary.py
```

Result: All checks passed.

Compile:

```bash
.venv/bin/python -B -m py_compile \
  core/evolution/drive_driven_curiosity.py \
  scripts/scratch_curiosity_e2e_canary.py
```

Result: exit 0.

Dormancy:

```bash
rg -n "register_default_encounter_producers\\(" core daemon --glob '*.py' | grep -v "def register_default" || true
```

Result: empty.

Symbol sweep:

```bash
rg -n "OwnerBondSaturationGuard|owner_bond_meaningful_daily_cap|NOT_ELIGIBLE_OWNER_BOND_ROUTINE|ELIGIBLE_OWNER_BOND|_priority_class_weight|_marker_confidence_weight" \
  core/evolution/drive_driven_curiosity.py \
  scripts/scratch_curiosity_e2e_canary.py \
  tests/test_curiosity_priors_cleanup.py \
  tests/test_curiosity_producer_ceremony.py \
  tests/test_encounter_producers.py \
  tests/test_curiosity_scratch_canary.py
```

Result: only the new cleanup tests contain guard-string assertions.

## Test Reconciliation

Preference-pinning tests were flipped, not deleted:
- old owner-bond saturation test now asserts no owner-bond saturation exception.
- old "except owner_bond" `can_resolve_interiorly` test now asserts no exception.
- generic seam tests now use `self_growth` / `SELF_MODEL` fixtures instead of relying on owner-bond auto-eligibility.
- scratch canary now uses `self_growth` / `SELF_MODEL` and `explicit_self_resolved`.

Safety tests stayed in place and green:
- third-party refusal.
- subject-kind omission/refusal.
- cross-bond / bond-id mismatch refusals.
- sidecar mismatch and duplicate refusal.
- authority-bearing call guards.

## Known Unrelated Observation

An expanded run that included `tests.test_wondering_pursuit_wiring` still fails:

`test_pursuit_callsite_precedes_audit_callsite` reports that the `reply = audit_assistant_text` callsite is missing inside `handle_message`.

That failure is outside this slice's changed files and also appears when the curiosity changes are not involved. I did not patch it here.

## Predicted Effect

No live Maez behavior changes: the producer is still dormant and `register_default_encounter_producers()` has no live caller.

When this dormant producer is eventually woken, it no longer carries owner-first preference priors. Owner-related curiosity is still allowed as scoped/consented material, but it does not get a salience multiplier, owner-default drawer, owner-default subject kind, owner-only cap, or automatic eligibility.

Plain English: the sleeping curiosity organ no longer ships with "Rohit matters more" baked in. Rohit still has the right drawer and consent boundary; Rohit no longer gets a thumb on the scale.
