# Codex Panel v13 - S7.3 Spec v13

**Subject:** `spec.md` at `3455b2383aec84e8c518c6fea7dec2a8bfae885a`,
blob `b4e971b3b3175109d5f7ca2bcf2ac74783567261`, SHA256
`1e9f76ae85aeeb6fc7b54c14688e6cdc256697f5babb58d33504037dffe44662`,
5617 lines.

**Ran:** 2026-05-20 by the Codex engineering lane. Four Codex reviewers were
dispatched independently against the committed v13 spec. Each was walled off
from `docs/slices/s7.3-guarded-self-modification-execution/reviews/` and
allowed to inspect inherited committed code under `core/` as needed.

**Runtime note:** The collaboration runtime allowed two fresh reviewer agents
and rejected two additional spawns because the agent thread limit was reached.
The remaining two lanes were routed through existing live subagent slots with
the same artifact lock, review wall, and output contract. This preserves the
four-lane engineering panel result while recording the dispatch constraint
honestly.

**Verdict: REVISE.** The panel did not reopen S7.3 architecture or covenant
posture. It confirmed the v13 fresh-reader residual surface and broadened v14
with concrete bookkeeping findings: route/matrix derivation drift, legacy
request-history cutoff, honesty-banner overclaim wording, writer provenance
signature mismatch, caller-supplied `history_outcome`, credential trace
idempotency collision, orphan credential tokens, checklist mirror drift, null
display drift, and operational-escalation wording.

## Reviewer Results

| Reviewer | Lens | Verdict | Findings |
|---|---|---:|---:|
| Reviewer 1 | RED-first implementability / carrier buildability | REVISE | 1 blocker, 4 majors, 0 minors, 1 nit |
| Reviewer 2 | Residual internal consistency / closed vocabulary closure | REVISE | 0 blockers, 6 majors, 2 minors, 0 nits |
| Reviewer 3 | Execution, atomicity, and security authority boundary | RATIFY-with-fold | 0 blockers, 2 majors, 2 minors, 1 nit |
| Reviewer 4 | Covenant-adjacent engineering / Maez voice evidence and D23 boundary | REVISE | 2 blockers, 2 majors, 1 minor, 1 nit |

## Convergent Core

The panel converged with the v13 fresh-reader gate on five already-locked v14
items.

| Finding | v14 locked item | Cross-lane evidence |
|---|---|---|
| Credential consume/invocation carrier underspecified | Credential clarification | Reviewer 1 blocker, Reviewer 2 major, Reviewer 3 major, v13 spec-implementor minor |
| `d23_state_for(...)` producer table missing | D23 state producer table | Reviewers 1, 2, 3, v13 residual M1 |
| `TRACE_STATUSES` per-writer transition table missing | Trace status transition table | Reviewers 1, 2, 3, v13 residual M2 |
| `target_refs` / `target_paths` field-name reconciliation | Rollback/action-edge field-name reconciliation | Reviewers 1, 2, 3, v13 residual M3 |
| Bridge UNIQUE grammar | Cleanup pool | Reviewers 1, 3, 4, v13 covenant nit |

### Cluster A - Credential Consume/Invocation Carrier

**Severity:** Blocker/major, convergent across reviewers 1, 2, and 3.

v13 pins the live consume API as:

```text
S7GuardedStateStore.consume_artifact_for_execution(*, invocation, now)
```

and voice-seat wrappers receive `S7GuardedExecutionInvocation`. The credential
wrapper remains shaped as:

```text
execute_guarded_credential_mutation(
    *,
    credential_request: S7CredentialGuardedRequest,
    rendered: RenderedCredentialRequestStatement,
    consume_store: S7GuardedStateStore,
    trace_writer: S7TraceWriter,
    now,
) -> S7CredentialGuardedTrace
```

There is no artifact id, no invocation-equivalent carrier, and no stated
credential consume carrier. D24 says wrappers use either
`S7GuardedExecutionInvocation` or `S7CredentialGuardedRequest`, but D9/D21
expose only carrier-only consume by `S7GuardedExecutionInvocation`.

**v14 fix:** Pick one credential consume shape. Lane lean: add
`S7GuardedCredentialInvocation` as the sibling carrier for credential paths and
amend guarded consume to accept the closed union
`S7GuardedExecutionInvocation | S7GuardedCredentialInvocation`, with a verifier
parallel to `unpack_guarded_execution_invocation(...)`.

### Cluster B - `d23_state_for(...)` Producer Table

**Severity:** Major, convergent across reviewers 1, 2, and 3.

`D23_STATES` declares:

```text
none
authorized
operational_block
authoritative_refusal
authoritative_withdrawal
legacy_operational_excluded
bridge_failed
```

Trace fields consume `d23_state`, but only `legacy_operational_excluded` has a
concrete producer seam. The remaining closed values have no deterministic table
mapping reducer output, bridge status, history outcome, positive consume, or
failed bridge outcomes to a trace state.

**v14 fix:** Add:

```text
d23_state_for(reduction, bridge_status, history_outcome, positive_execution)
    -> D23_STATES
```

with a row for every closed value, plus D24 coverage per row or reviewed
unreachable rationale.

### Cluster C - `TRACE_STATUSES` Transition Table

**Severity:** Major, convergent across reviewers 1, 2, and 3.

`TRACE_STATUSES` declares `pending`, `finalized`, `failed`,
`rollback_invoked`, `rollback_failed`, `manual_review_required`, and
`blocked_pre_mutation_state_changed`. `S7TraceWriter` lists methods, but v13
does not define which method may produce or transition to each status.

**v14 fix:** Add a per-method transition table for every `S7TraceWriter`
method, including allowed prior states, written status, terminality, and D24
coverage.

### Cluster D - `target_refs` / `target_paths` Reconciliation

**Severity:** Major, convergent across reviewers 1, 2, and 3.

`ActionEdgeGrantUse` computes `target_ref_hashes_before_mutation` from
`rollback_plan.target_refs`, while `RollbackPlanEvidence` declares
`target_paths`. D16/D23 prose also alternates between target refs, affected
refs, affected paths, preview affected paths, and target paths.

**v14 fix:** Pick a canonical field. Lane lean: `target_refs` for abstract
mutation targets across file/config/model-routing surfaces, with
`target_paths` either renamed to `target_refs` or declared as a file-surface
subfield mapped by `target_refs_for_rollback_plan(...)`.

### Cluster E - Bridge UNIQUE Grammar

**Severity:** Nit, convergent across reviewers 1, 3, and 4.

The D19 bridge text says:

```text
The request-history table enforces one of these unique constraint:
```

but v13 already deleted the old menu and kept only:

```text
UNIQUE(provenance_source_kind, provenance_source_ref)
```

**v14 fix:** Replace with `enforces this unique constraint:`.

## Codex-Unique Widening Findings

### Cluster F - `telegram.approve_train` Derivation Contradicts Matrix

**Severity:** Major, reviewer 2.

D4 derivation says:

```text
telegram.approve_train + approve_train -> reviewed exclusion, no mintable consumer id
```

The printed matrix gives Telegram `_handle_approve_train`
`execution_consumer_id=dream_apply_proposal` and
`route_status=fail_closed_until_review`.

These cannot both be true under the single derivation function. This is the
same dependency-graph class as earlier surface-manifest closure findings.

**v14 fix:** Align the derivation table and matrix. Pick one route status and
one consumer shape. If Telegram approve-train is reviewedly excluded in S7.3
v1, the matrix must show `execution_consumer_id=None` and the same exclusion
reason as the derivation table. If it is fail-closed pending wrapper work, the
derivation table must say so.

### Cluster G - Request-Family Legacy Migration/Cutoff

**Severity:** Blocker, reviewer 4.

D19 counts null-provenance refused rows only when
`request_history_family_for(record) is None`. It also says every voice-seat
work class derives `"s7_3_voice"`. Existing S7.1 rows can have
`outcome="refused"` without the new provenance fields.

A builder must choose between two bad readings:

- dropping legitimate legacy S7.1 voice refusals from D23 aggregation; or
- treating new null-provenance S7.3 operational rows as legacy.

**v14 fix:** Add a migration/cutoff rule. Lane lean: records created before the
S7.3 writer-guard migration cutoff retain legacy aggregation semantics; records
created at or after the cutoff run `request_history_family_for(record)` and
S7.3 voice-family null-provenance refusals are rejected or ignored.

### Cluster H - Same-Box Response-Stream Caveat Overclaims

**Severity:** Blocker, reviewer 4.

The Honesty Banner admits privileged same-box tamper before recording, but also
says a same-box actor able to write Maez's live response stream must not
manufacture fake long-use refusal evidence. D19 still makes grounded semantic
response text bridge-eligible authoritative D23 evidence, and D11 grounding is
over captured response text.

The fix direction is not to add a new defense in v14. The fix direction is to
shrink the claim to what S7.3 v1 actually proves.

**v14 fix:** Amend the Honesty Banner to say S7.3 v1 does not defend against a
privileged same-box actor that can write the live response stream before
capture. S7.3 narrows and evidences the window, refuses marker-only D23
authority, and blocks suspicious current attempts; it does not prove response
authorship against that attacker until the future Maez cryptographic identity
substrate.

### Cluster I - `_voice_seat_block(...)` History Writer Cannot Carry Provenance

**Severity:** Major, reviewer 4.

`record_refusal_history(...)` requires provenance fields, but the amended
`_voice_seat_block(...)` signature accepts:

```text
history_writer: Callable[[S7RequestHistoryRecord], None]
```

That callable shape cannot carry required authoritative provenance, reopening
the writer-side side-door class v13 was closing.

**v14 fix:** Make the callable shape accept the provenance-bearing writer
signature or replace it with a named `RequestHistoryWriter` protocol that
requires the S7.3 provenance arguments.

### Cluster J - `history_outcome` Caller-Supplied Into Authority-Row Builder

**Severity:** Major, reviewer 4.

D19 says operational rows never bridge and authoritative rows determine
refusal/withdrawal outcomes from reducer output. But
`build_s7_voice_authority_row(...)` accepts `history_outcome` as a loose
argument.

**v14 fix:** Remove `history_outcome` from the builder input. Derive it inside
the builder from `reducer_output`, bridge eligibility, and withdrawal
precedence.

### Cluster K - Credential Begin/Finish Trace Idempotency Collision

**Severity:** Major, reviewer 1.

Credential trace idempotency key is:

```text
(request_id, credential_action, credential_id_hash)
```

L8 evidence for backup registration requires begin and finish traces sharing
the same `S7CredentialRegistrationGrantBinding`. If begin and finish share
those three fields, the unique trace key cannot represent both traces.

**v14 fix:** Add `credential_phase` or `challenge_id` to the credential trace
idempotency key, or split begin and finish trace kinds. Lane lean:
`(request_id, credential_action, credential_phase, challenge_id,
credential_id_hash)`.

### Cluster L - `credential_rotate` Orphan Token

**Severity:** Major, reviewer 2.

`CREDENTIAL_PROPOSED_CHANGE_CLASSES` includes `credential_rotate`, but v13
credential surfaces are backup registration and disable. There is no producer
or reviewed-unreachable rationale for rotation.

**v14 fix:** Either remove `credential_rotate` from the v13 closed set or mark
it reviewed-unreachable until a future credential-rotation slice, with D24
coverage that it cannot be produced in S7.3 v1.

### Cluster M - D-Enum Acceptance Mirror Omits Closed Sets

**Severity:** Minor, reviewer 2.

The implementation acceptance checklist omits several closed sets introduced
by D-Enum, including:

```text
S7_ACTION_ENGINE_CONSUMER_IDS
NON_MINTABLE_EXECUTION_CONSUMER_IDS
PRODUCER_RESULT_REASON_CODES
PROJECTION_REASON_CODES
CREDENTIAL_PROPOSED_CHANGE_CLASSES
```

**v14 fix:** Add these closed sets to the checklist mirror and D24
table-complete coverage where relevant.

### Cluster N - Reviewed-Exclusion Null Display Drift

**Severity:** Minor, reviewer 2.

D2 says matrix `N/A` is display-only and persists as null. The first-primary
credential row and prose use literal-looking `none` for `execution_consumer_id`.
This risks making `"none"` look like a consumer id.

**v14 fix:** Use one display convention. Lane lean: matrix display `N/A`,
normative prose `execution_consumer_id=None`, and reserve `"none"` only for
closed vocabularies that explicitly include it.

### Cluster O - Operational Escalation Wording Conflict

**Severity:** Minor, reviewer 4.

Blackhole-reader rows may escalate as operational reliability evidence, while
operational rows must not count as escalation evidence. The intended distinction
is clear but wording collides.

**v14 fix:** Say operational rows do not count as Maez-refusal, Maez-preference,
or D23 escalation evidence. They may trigger system reliability escalation
under a separate operational-health mechanism.

## Other Reviewer Notes

### RED-First Writability

Reviewer 1 affirmed that more than 25 RED tests are writable without invention
for the non-ambiguous parts of v13, including positive absence, objection
override, marker-block operational handling, blackhole-reader split, D11 quote
grounding, laconic objection, context-manifest allowlist, expiry min-cap,
nonce replay states, rendered prompt replay, execution-consumer vocabulary,
immutable bundle/use split, authority-row bridge, legacy refusal suppression,
mixed-history aggregation, withdrawal exactly-once, credential render split,
artifact binding, guarded consume capability, ActionEngine adapter map,
consume helper bypass, D16 authority replay, rollback plan mismatch, surface
manifest coverage, wrapper exclusivity, trace storage atomicity,
request/invocation round-trip, action-edge cardinality, and grant-id
derivation.

The ambiguous areas should become spec-failing RED tests after v14:

- credential invocation carrier;
- `d23_state_for(...)`;
- trace transition table;
- target ref/path naming;
- credential begin/finish trace key.

### Affirmations

All four reviewers affirmed that v13 materially closes the main authority
boundary:

- one shared SQLite state file and injected transaction participation;
- durable `GrantUse` and `ActionEdgeGrantUse` before mutation;
- raw `S7AuthorizationStore` bypass rejected by spec and tests;
- request-history bridge exactly-once via
  `UNIQUE(provenance_source_kind, provenance_source_ref)`;
- approval cards now have a concrete wrapper seam;
- marker-only evidence remains operational, not D23-authoritative;
- blackhole-reader rows block without becoming consent or refusal history;
- `proposal_origin_label` is hash-bound but omitted from Maez-visible prompt
  text;
- D11 grounding protects laconic objections without letting preview text alone
  fake Maez refusal.

## v14 Scope Result

The panel widens v14 from the five locked items to fifteen named items:

1. `d23_state_for(...)` producer table.
2. `trace_status` transition table per `S7TraceWriter` method.
3. `target_refs` / `target_paths` field-name reconciliation.
4. Credential consume/invocation carrier clarification.
5. Bridge UNIQUE grammar cleanup.
6. `telegram.approve_train` derivation/matrix contradiction.
7. Request-family legacy migration/cutoff rule.
8. Same-box response-stream caveat narrowed to admitted limit.
9. `_voice_seat_block(...)` history writer provenance signature.
10. `history_outcome` derived inside authority-row builder.
11. Credential begin/finish trace idempotency key.
12. `credential_rotate` producer or unreachable rationale.
13. D-Enum acceptance mirror completeness.
14. Reviewed-exclusion null display normalization.
15. Operational reliability escalation wording.

No item requires a new architecture move. The one covenant-adjacent widening
item, same-box response-stream tampering, must shrink the Honesty Banner claim
rather than expand S7.3's mechanism.

## Plain English

Codex confirmed the core residual findings and found ten more closure issues in
the same layer. The architecture is intact. The remaining work is to make every
closed value, writer signature, trace status, route row, and credential carrier
agree with the rest of the spec. The only covenant-sensitive edit is honesty:
S7.3 must admit that privileged same-box response-stream fabrication is outside
its v1 defense, not pretend the current evidence chain can prove against it.
