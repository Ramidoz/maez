# S7.3 Spec v10 Fold Delta-Plan Addendum

**Subject:** addendum to `reviews/spec-v10-fold-plan.md`, covering absorption
residuals found during covenant-lane faithfulness review of the v10 fold plan.

**Extends:** `reviews/spec-v10-fold-plan.md` at `63cc78b`.

**Why this exists:** the v10 fold plan absorbs all major findings from the v9
fresh-reader gate and the Codex engineering panel v9. Faithfulness review found
one material dual-direction D24 test and four nit-class pins that should be
traceable before v10 spec authoring. v10 spec must be authored from the fold
plan plus this addendum as one fold contract.

## A1 - Wrapper Exclusivity D24 Test

**Source:** covenant minor Mi-3 from the v9 fresh-reader gate.

**Extends:** v10 fold plan Section 14 and Section 16.

v10 Section 14 pins the wrapper signatures, but Section 16 does not yet name
the paired exclusivity test. The spec says mutation goes through
`execute_guarded_*(...)` wrapper services; D24 must prove that claim is not
only prose.

Add a D24 wrapper-exclusivity test:

```text
For each execute_guarded_*(...) wrapper, static analysis or code discovery
confirms the underlying substrate-mutating callee is not reachable from any
code path other than the reviewed wrapper, OR the callee fails closed when
entered without the wrapper's bookkeeping context.
```

The test must cover at least:

- dream apply;
- evolution apply;
- workshop apply;
- ActionEngine mutation;
- credential mutation;
- model-routing or brain-swap mutation if live in v10.

The negative case matters: a direct call that presents a plausible consumed
grant but lacks wrapper-created bookkeeping must fail closed before substrate
mutation. This is the dual direction of the wrapper authority claim.

## A2 - `maez_consulted_state="not required"` Scope

**Source:** covenant nit N-1 from the v9 fresh-reader gate.

**Extends:** v10 fold plan Section 13 and Section 15.

v9 allows `RenderedRequestStatement.maez_consulted_state` values such as
`"yes"` and `"not required"`, but does not state whether S7.3 v1 voice-seat
work may legitimately render `"not required"`.

v10 should pin one rule:

- lane lean: voice-seat work in S7.3 v1 must render
  `maez_consulted_state="yes"` whenever Maez consultation is required by the
  work class; `"not required"` is reserved for non-voice credential or reviewed
  non-voice paths and must not appear on voice-seat `RenderedRequestStatement`
  rows.

D24 should reject a voice-seat render that uses `"not required"` without a
reviewed non-voice exemption.

## A3 - `d23_state="legacy_operational_excluded"` Trace Conditions

**Source:** covenant nit N-2 from the v9 fresh-reader gate.

**Extends:** v10 fold plan Section 1 and Section 13.

If v10 keeps the trace token:

```text
d23_state="legacy_operational_excluded"
```

then D19/D22 must state exactly when it is written:

- only for inherited or compatibility-path operational voice-family events that
  were prevented from writing countable `outcome="refused"` history;
- never for authoritative grounded refusals or withdrawals;
- never for ordinary inherited legacy rows that still count under the legacy
  branch.

If no producer remains after Section 1 deletes orphan legacy tokens, delete
`legacy_operational_excluded` too.

## A4 - Rollback Verification Asymmetry Note

**Source:** covenant nit N-3 from the v9 fresh-reader gate.

**Extends:** v10 fold plan Section 10 and Section 16.

v10 Section 10 correctly adds pre-mutation rollback precondition recheck. D24
should also state the asymmetry explicitly:

```text
Pre-mint rollback plan verification proves the plan exists and is bound to the
request. Pre-mutation rollback precondition verification proves the current
target state still matches the plan. Post-mutation rollback result evidence is
a separate evidence class and must not be treated as satisfied by either
pre-mint or pre-mutation checks.
```

This is a wording pin, not a new architecture.

## A5 - `precondition_hash` New Inherited Carrier Callout

**Source:** spec-implementor nit N2 from the v9 fresh-reader gate.

**Extends:** v10 fold plan Section 11 and Section 16.

`RenderedRequestStatement` gains `precondition_hash` for the first time in the
v9/v10 rendered protocol work. Add an Implementation Acceptance Checklist item:

```text
RenderedRequestStatement has a real precondition_hash field, a founder-signed
"Precondition hash:" rendered line, expected_metadata enforcement, D16 equality
predicate, and D24 tamper test. It is not only implied by the common rendered
protocol.
```

This protects the inherited-carrier extension from being half-applied.

## Process

v10 spec should be authored from:

- `reviews/spec-v10-fold-plan.md`;
- this addendum.

No new architecture is introduced here. The only material addition is A1, the
wrapper-exclusivity D24 test. A2-A5 are traceability pins for values or evidence
classes already named by the v9 gate.

*Read-only; addendum written by Codex on 2026-05-20 in response to
covenant-lane faithfulness review of `reviews/spec-v10-fold-plan.md`. ASCII
normalization applied for repository style.*
