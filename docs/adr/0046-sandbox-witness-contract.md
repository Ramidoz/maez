# 0046 — Sandbox-Witness Contract

**Status:** Accepted
**Date:** 2026-05-26

## Context

ADR 0045 gave Maez a ratifiable `MaintenanceProposal` form, but its optional
`sandbox_witness` still had the legacy four-boolean shape:
`red_tests_passed`, `focused_tests_passed`, `scratch_canary_passed`, and
`witness_digest`. Those booleans were caller-asserted verdicts. Without a
separable witness contract, the maintenance loop could become a self-claim
engine wearing the proposal form's clothes.

The contract was reviewed through the full ladder: council pass-1 folded to
v1.1, Codex engineering pass-1 blocked v1.1 and folded to v1.2, Codex pass-2
found narrow remaining engineering holes and folded to v1.3, and Codex pass-3
ratified v1.3 with typographical nits that were folded before
canonicalization.

## Decision

Sandbox witnesses attached to maintenance proposals must be re-verifiable
artifacts, not caller-asserted strings or booleans.

When proof changes, do not overwrite it; when permission moves, do not leave a
timing crack.

## Surface Contract

The witness surface attaches to ADR 0045's maintenance-proposal lifecycle. It
does not change the proposal's owner-ratification authority or grant autonomous
live merge / live crossing.

V1 witness kinds are closed vocabulary:

- `WORKTREE_RED_TEST`
- `WORKTREE_SCHEMA_DIFF`
- `SCRATCH_DB_TRANSFORM`
- `DRY_RUN_OBSERVATION`

Each kind declares deterministic `observed_effect = f(artifacts)`. Any kind
without a deterministic projection is deferred.

Legacy four-boolean witnesses are read-only compatibility state. New
append/update/emit/ratify paths refuse legacy witness input with
`LEGACY_WITNESS_SHAPE_REFUSED`.

## Patterns Introduced

### Monotonic generation as identity, semantic key as index

If evidence can be re-stated, stale, superseded, or refreshed, the new
statement gets a new identity. The semantic key locates the family; it is not
the row identity.

Applied here: sandbox witnesses use immutable `witness_id` / monotonic
generation. `(bond_id, proposal_id)` is an index over the witness family.
Re-witnessing appends a generation and preserves the old one.

### Atomic authority-transition snapshot

If a transition records authority, every fact that makes it eligible must be
checked and bound inside one critical section, then written in the same ordered
transition.

Applied here: ratification binds proposal id, witness generation, anchor
snapshot, re-verification result, divergence acknowledgment id, `WitnessStatus`,
owner preference write, and proposal status transition atomically.

## Consequences

- Witness objects are durable, append-only, and join the never-delete family.
- Staleness anchors must be concrete and race-safe, including transactionally
  coherent DB cursor behavior under SQLite WAL/concurrent writes.
- Narrative external-LLM input is scanned through `injection_patterns.py`;
  digest fields use digest validation plus substrate-computed provenance.
- Re-verification runs in isolated scratch context and refuses live substrate
  mutation.
- Ratification performs a cheap final eligibility snapshot and does not rerun
  the full witness subprocess unless a future closed policy explicitly allows
  it.
- Divergence between predicted and observed effect is surfaced as honest signal;
  it is not a refusal and can ratify only with exact-generation owner
  acknowledgment.

If reversed, Maez could launder "I checked my work" into owner-ratified
maintenance authority without a re-verifiable proof object.

## References

- Governance: Decision 41 in
  [`BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- Spec brief: [`docs/slices/sandbox-witness-contract/spec-brief.md`](../slices/sandbox-witness-contract/spec-brief.md)
- Council pass-1 records:
  `docs/slices/sandbox-witness-contract/reviews/claude-council-*-pass1.md`
- Codex engineering records:
  `docs/slices/sandbox-witness-contract/reviews/codex-*-pass1.md`,
  `docs/slices/sandbox-witness-contract/reviews/codex-*-pass2.md`, and
  `docs/slices/sandbox-witness-contract/reviews/codex-pass3-*.md`
