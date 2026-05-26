# Sandbox Witness Divergence Acknowledgment Seam

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion. This seam is RED-first and must not proceed to production code before the refusal tests fail for the expected reason.

**Goal:** Complete the ADR 0046 divergence path: when a witness's predicted effect and observed effect diverge, ratification must require owner acknowledgment bound to the exact witness generation and predicted/observed digest pair.

**Architecture:** Keep divergence acknowledgment beside the witness substrate in `core/policies/sandbox_witnesses.py`, as a parallel table in `memory/sandbox_witnesses.db`. `core/policies/maintenance_proposals.py` consumes it only at ratification eligibility time. Divergence is not a witness refusal; it is an owner-acknowledgment requirement.

**Tech Stack:** Python dataclasses/enums, SQLite append-only rows, existing maintenance proposal ratification flow, unittest.

---

## Scope

Included:

- `DivergenceAckChannel` closed vocabulary with natural-language and reaction channels.
- Append-only divergence acknowledgment records bound to `(bond_id, proposal_id, witness_generation, predicted_effect_digest, observed_effect_digest)`.
- Ratification refusal before owner preference write when the current witness diverged and lacks an exact acknowledgment.
- Tests for natural-language acknowledgment, reaction acknowledgment, stale old-generation acknowledgment, and no preference/status mutation on missing acknowledgment.

Deferred:

- Consent-card UI rendering for acknowledgment.
- Full subprocess verifier and `MAEZ_SUBSTRATE_ROOT` locus enforcement.
- Live SQLite WAL/fd inspection.
- True cross-DB lock spanning `maintenance_proposals.db`, `autonomy_preferences.db`, and `sandbox_witnesses.db`; this seam binds the final eligibility snapshot immediately before preference write, but full lock-atomicity remains the later hardening layer.

## Files

- Modify: `core/policies/sandbox_witnesses.py`
  - Add divergence acknowledgment dataclass, channel enum, and store.
  - Add helper for exact current-witness acknowledgment checks.
- Modify: `core/policies/maintenance_proposals.py`
  - Add optional divergence acknowledgment store to `ratify_maintenance_proposal`.
  - Require exact acknowledgment before ratifying diverged current witnesses.
- Modify: `tests/test_sandbox_witnesses.py`
  - Add store round-trip and exact-generation tests.
- Modify: `tests/test_maintenance_proposals.py`
  - Add ratification refusal and two-channel acknowledgment tests.

## Task 1: Record Divergence Acknowledgments

- [ ] Write RED tests proving acknowledgments round-trip and are exact-generation/digest-bound.
- [ ] Implement `DivergenceAckChannel`, `DivergenceAcknowledgment`, and `DivergenceAcknowledgments`.
- [ ] Run focused sandbox witness tests.
- [ ] Commit with predicted effect.

## Task 2: Require Exact Acknowledgment at Ratification

- [ ] Write RED tests proving a diverged current witness cannot ratify without acknowledgment and leaves proposal/preferences unchanged.
- [ ] Write RED tests proving natural-language and reaction acknowledgments both ratify the exact generation.
- [ ] Write RED test proving an acknowledgment for generation N does not ratify generation N+1.
- [ ] Implement ratify-time check before preference write/status flip.
- [ ] Run focused maintenance + witness tests.
- [ ] Commit with predicted effect.

## Verification

Run before merge:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_maintenance_proposals tests.test_sandbox_witnesses tests.test_diagnostic_schema
git diff --check
/home/rohit/maez/.venv/bin/python -m py_compile core/policies/maintenance_proposals.py core/policies/sandbox_witnesses.py tests/test_maintenance_proposals.py tests/test_sandbox_witnesses.py
/home/rohit/maez/.venv/bin/ruff check core/policies/maintenance_proposals.py core/policies/sandbox_witnesses.py tests/test_maintenance_proposals.py tests/test_sandbox_witnesses.py
```

After fast-forwarding main, run the broad suite from main and report the current unrelated-failure floor honestly.
