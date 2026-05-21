# Fresh-Reader Gate v13 - S7.3 Spec v13

**Subject:** `spec.md` at `3455b2383aec84e8c518c6fea7dec2a8bfae885a`,
blob `b4e971b3b3175109d5f7ca2bcf2ac74783567261`, SHA256
`1e9f76ae85aeeb6fc7b54c14688e6cdc256697f5babb58d33504037dffe44662`,
5617 lines.

**Ran:** 2026-05-20 as the Section 8.2 fresh-reader gate. Three blank-context
readers reviewed the committed v13 spec at the canonicalization-ready bar:
cold covenant reader, cold spec-implementor, and cold residual-hunter. Each was
walled off from
`docs/slices/s7.3-guarded-self-modification-execution/reviews/`.

**Consolidated verdict: RATIFY-with-fold.** The covenant and spec-implementor
lanes signaled canonicalization-ready. The residual lane found three major
closed-vocabulary / field-name closure breaks, so v13 did not meet the strict
bounded-nit-only canonicalization bar.

## Reader Results

| Reader | Lens | Verdict | Findings |
|---|---|---:|---:|
| Cold covenant reader | Council, dual-direction, Honesty Banner | RATIFY-with-fold, canonicalization-ready | 0 blockers, 0 majors, 0 minors, 1 nit |
| Cold spec-implementor | RED-first ship-today | RATIFY-with-fold, canonicalization-ready | 0 blockers, 0 majors, 1 minor, 3 nits |
| Cold residual-hunter | Closed-value producer/consumer/test accounting | RATIFY-with-fold | 0 blockers, 3 majors, 13 minors, 3 nits |

## Covenant Reader

**Bottom line:** v13 is canonicalization-ready. The S7.3 spec can stop being a
moving target after this read.

**Findings:** 0 blockers, 0 majors, 0 minors, 1 nit.

### N1 - Bridge UNIQUE Grammar

The D19 bridge text says:

```text
The bridge is exactly-once. The request-history table enforces one of these
unique constraint:
```

It should read:

```text
The bridge is exactly-once. The request-history table enforces this unique
constraint:
```

The parallel passage already pins:

```text
UNIQUE(provenance_source_kind, provenance_source_ref)
```

This is grammar only; no covenant load.

### Covenant Affirmations

- Carrier-only consume API is enforced end-to-end, including positive and
  negative D24 tests.
- Storage atomicity is materially folded into one SQLite file with `s7_traces`
  in the same transaction.
- Marker-to-D23 attack surface stays closed: marker-only evidence remains
  operational, blackhole-reader rows block without becoming consent/refusal,
  and semantic grounding remains required for D23 authority.
- Concrete L8 coverage is derivation-based through `S7SurfaceManifest`; parent
  compatibility ids are non-mintable.
- Hand-assembly ban covers the v13 load-bearing carriers.

## Spec-Implementor Reader

**Bottom line:** v13 is the first version where a builder can read fresh and
ship from the spec. Fifty-five RED tests are writable today.

**Findings:** 0 blockers, 0 majors, 1 minor, 3 nits.

### M1 - Credential-Path Invocation Type Inconsistency

`S7GuardedExecutionInvocation` carries non-null voice-seat fields such as
`source_ref_hash` and `reservation_token`, while credential consumers are said
to carry `source_ref_hash=None` and `reservation_token=None`. The credential
wrapper takes `credential_request` and `rendered` directly rather than a
complete invocation carrier, but the live consume API accepts only
`consume_artifact_for_execution(*, invocation:)`.

The spec should choose one credential consume shape:

- widen `S7GuardedExecutionInvocation` fields to permit credential nulls;
- add a sibling `consume_artifact_for_credential_execution(...)`; or
- define `S7GuardedCredentialInvocation` and a sibling verifier.

### Spec-Implementor Nits

- Nonce DDL has both inline uniqueness and a named unique index for the same
  request/consultation/attempt key.
- Failure-code partition labels `invalid_prompt_integrity` and
  `invalid_authority_class_replay` as consume-time D16 replay, while later
  prose says wrapper-side preflight owns the S7.3-specific failures. Tighten to
  `wrapper-owned`.
- `marker_text_hash` appears on the draft carrier but is absent from the final
  bundle by design; state that draft replay uses the raw response / parser /
  attempt evidence path and final bundle drops the field.

### Spec-Implementor Affirmations

- Trace-DB unification is unambiguous.
- Invocation as carrier-only consume is enforced by signature shape.
- Failure-code seam partition is concrete.
- ActionEdgeGrantUse persistence domain is complete.
- Protective-reason canonicalization uses string `"none"` system-wide.

## Residual-Hunter Reader

**Findings:** 0 blockers, 3 majors, 13 minors, 3 nits.

### M1 - `D23_STATES` Vocabulary Closure Break

`D23_STATES` declares seven closed values:

```text
none
authorized
operational_block
authoritative_refusal
authoritative_withdrawal
legacy_operational_excluded
bridge_failed
```

Only `legacy_operational_excluded` has an explicit producer seam. The other
values appear in the closed set but lack a D-bullet writer. A future reader
would not know when a trace gets `d23_state="authoritative_refusal"`.

**Fold direction:** Add a deterministic `d23_state_for(...)` producer table or
remove unreachable values.

### M2 - `TRACE_STATUSES` Vocabulary Closure Break

`TRACE_STATUSES` declares:

```text
pending
finalized
failed
rollback_invoked
rollback_failed
manual_review_required
blocked_pre_mutation_state_changed
```

Producers are explicit for `pending`, `finalized`, and
`blocked_pre_mutation_state_changed`. The other values lack explicit
per-writer transitions.

**Fold direction:** Add a per-`S7TraceWriter` transition table and D24 coverage
for every closed value.

### M3 - `target_refs` / `target_paths` Field-Name Break

Action-edge derivation uses `rollback_plan.target_refs`, while
`RollbackPlanEvidence` declares `target_paths`. Replay over
`target_ref_hashes_before_mutation_hash` cannot run as written.

**Fold direction:** Rename one field to match or add an explicit alias /
normalization function.

### Residual Minor Cluster

- `manifest_hash` vs `surface_manifest_hash` terminology jitter.
- `proposal_origin` vs `proposal_origin_label` relationship unstated.
- `affected_refs`, `preview_affected_paths`, `target_paths`, and `target_refs`
  naming jitter.
- `CovenantCeremonyEvidence` referenced once but not defined.
- `manual_review_status` has no closed vocabulary.
- `superseded_request_ids` is tuple in invocation but set in inherited consume.
- DDL uses `reservation_token_hash` while carrier carries raw
  `reservation_token`.
- `credential_request_method_for_surface(...)` return type is not precise for
  a begin/finish pair.
- Grep checklist case sensitivity around `wrapper-side`.
- `attempt_input_hash` includes `attempt_started_at`, mixing audit timing into
  classifier input.
- Honesty Banner still carries a v9/v11 label in normative wording.
- Bridge UNIQUE grammar overlaps covenant nit.

### Residual Affirmations

- v12 fold-contract landed mechanically; the v12 grep checklist was present in
  v13.
- D13 reducer table is concretely complete.
- `S7ConsumeFailureReasonCode` partition is exhaustive.
- Min-cap expiry lattice is end-to-end.
- Voice-evidence honesty remains explicit.

## Consolidated v14 Fold Surface From Fresh-Reader Gate

1. `d23_state_for(...)` producer table.
2. `trace_status` transition table per `S7TraceWriter` method.
3. `target_refs` / `target_paths` field-name reconciliation.
4. Credential consume/invocation carrier clarification.
5. Bridge UNIQUE grammar cleanup.
6. Spec-implementor nit cleanup: nonce uniqueness duplication,
   wrapper-owned failure labels, and draft marker replay wording.
7. Residual minor cleanup: terminology jitter, undeclared types, type
   mismatches, return-type precision, grep-case stability, and audit-vs-input
   hash wording.

## Plain English

The covenant reader said v13 can be trusted. The implementor reader said a
fresh engineer can start writing tests from it. The residual reader caught
three final closure breaks: closed D23 states without producer rows, closed
trace statuses without transition rows, and a target field name mismatch.
Those are real canonicalization findings, but they are bookkeeping, not
architecture.
