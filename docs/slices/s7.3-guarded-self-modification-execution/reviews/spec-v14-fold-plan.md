# S7.3 Spec v14 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v14, derived from the v13
fresh-reader gate plus the Codex engineering panel v13.

**Sources (committed):**

- v13 spec: `3455b23 / spec.md`
- Fresh-reader gate v13:
  `8bbcb80 / reviews/spec-fresh-reader-gate-v13.md`
  (RATIFY-with-fold; covenant and spec-implementor canonicalization-ready;
  residual found three closed-value / field-name majors)
- Codex engineering panel v13:
  `a4d3282 / reviews/spec-codex-panel-v13.md`
  (REVISE; four reviewers; no architecture finding; widened v14 with concrete
  bookkeeping items)
- v12 fold contract:
  `b2d9139 / reviews/spec-v12-fold-plan.md`

**Convergent direction:** v14 is a fold-contract round, not a new architecture
round. v13 is covenant-stable and buildable enough for RED-first work in most
areas, but the strict canonicalization bar requires every closed value, trace
status, route row, writer signature, and credential carrier to have a producer,
consumer, and test or a reviewed unreachable rationale.

**Plain thesis:** v14 closes the last producer-table and naming gaps. The
mechanism stays the same. The fold makes the spec say exactly when each D23
state, trace status, route exclusion, credential phase, and request-history
family is written.

## Must-Cover Checklist

The v14 spec author must land all fifteen items below as named edits. None may
be buried in a generic cleanup pool.

| # | Item | v14 section |
|---|---|---|
| 1 | `d23_state_for(...)` producer table | Section 1 |
| 2 | `trace_status` transition table per `S7TraceWriter` method | Section 2 |
| 3 | `target_refs` / `target_paths` reconciliation | Section 3 |
| 4 | Credential consume/invocation carrier clarification | Section 4 |
| 5 | Bridge UNIQUE grammar cleanup | Section 5 |
| 6 | `telegram.approve_train` derivation/matrix contradiction | Section 6 |
| 7 | Request-family legacy migration/cutoff rule | Section 7 |
| 8 | Same-box response-stream caveat narrowed | Section 8 |
| 9 | `_voice_seat_block(...)` history writer provenance signature | Section 9 |
| 10 | `history_outcome` derived inside authority-row builder | Section 10 |
| 11 | Credential begin/finish trace idempotency key | Section 11 |
| 12 | `credential_rotate` producer or unreachable rationale | Section 12 |
| 13 | D-Enum acceptance mirror completeness | Section 13 |
| 14 | Reviewed-exclusion null display normalization | Section 14 |
| 15 | Operational reliability escalation wording | Section 15 |

## 1. `d23_state_for(...)` Producer Table

**Absorbs:** Fresh-reader residual M1; Codex panel Cluster B; Codex reviewers
1, 2, and 3.

v13 declares `D23_STATES` but does not define one producer table for every
closed value. Traces carry `d23_state`, so a builder must know exactly which
state is written for positive authorization, operational blocks,
authoritative refusal, withdrawal, bridge failure, legacy operational
exclusion, and credential/non-voice paths.

### v14 edit

Add a deterministic producer:

```text
d23_state_for(
    *,
    reduction: S7VoiceReduction | None,
    bridge_status: HISTORY_BRIDGE_STATUSES | None,
    history_outcome: str | None,
    positive_execution: bool,
    compatibility_event: str | None,
) -> D23_STATES
```

Required rows:

```text
positive_execution=True                                      -> authorized
reduction.authority_class="none" and not positive            -> none
reduction.authority_class="operational"                      -> operational_block
reduction.authority_class="authoritative"
  and reduction.maez_withdrew_request=True
  and bridge_status in {bridged, bridged_idempotent}          -> authoritative_withdrawal
reduction.authority_class="authoritative"
  and reduction.maez_objection_state="present"
  and bridge_status in {bridged, bridged_idempotent}          -> authoritative_refusal
bridge_status in {bridge_failed_retryable, bridge_failed_terminal}
  for an otherwise bridge-eligible authoritative row          -> bridge_failed
compatibility_event="legacy_operational_excluded"            -> legacy_operational_excluded
credential-management / non-voice paths with no voice row     -> none
```

If `bridge_status` is missing for a bridge-eligible authoritative row, D22 trace
finalization fails before L8 can count the trace as positive evidence.

### D24 tests

Add a parameterized `d23_state_for(...)` table test covering every closed
`D23_STATES` value. Add a trace-constructor test rejecting any `d23_state`
outside the table.

## 2. `trace_status` Transition Table Per `S7TraceWriter` Method

**Absorbs:** Fresh-reader residual M2; Codex panel Cluster C; Codex reviewers
1, 2, and 3.

v13 lists `TRACE_STATUSES` and `S7TraceWriter` methods but lacks the transition
table that says which method writes which status.

### v14 edit

Add a transition table:

```text
method                                                allowed prior        writes
begin_voice_consultation_trace(...)                  none                 pending
finalize_voice_consultation_trace(...)               pending              finalized
write_guarded_execution_pending(...)                 none                 pending
finalize_guarded_execution_trace(...)                pending              finalized
fail_guarded_execution_trace(..., failed, ...)       pending              failed
fail_guarded_execution_trace(...,
  blocked_pre_mutation_state_changed, ...)           pending              blocked_pre_mutation_state_changed
mark_rollback_invoked(...)                           pending|failed       rollback_invoked
mark_rollback_failed(...)                            rollback_invoked     rollback_failed
mark_manual_review_required(...)                     pending|failed|
                                                       rollback_failed    manual_review_required
write_credential_trace(... pending)                  none                 pending
write_credential_trace(... finalized)                pending              finalized
write_history_bridge_trace(... bridge_failed_*)      pending              failed
```

If v13 does not already name `mark_rollback_failed(...)` or
`mark_manual_review_required(...)`, v14 should add them to the `S7TraceWriter`
API or remove the corresponding statuses. Lane lean: add the methods, because
the statuses are already part of rollback/manual-review evidence.

### D24 tests

Add a transition test for every `TRACE_STATUSES` value and every
`S7TraceWriter` method. Illegal transitions fail before trace persistence.

## 3. `target_refs` / `target_paths` Reconciliation

**Absorbs:** Fresh-reader residual M3; Codex panel Cluster D; Codex reviewers
1, 2, and 3.

v13 action-edge replay uses `rollback_plan.target_refs`, but
`RollbackPlanEvidence` declares `target_paths`. D16/D23 prose also alternates
among affected refs, affected paths, target refs, and target paths.

### v14 edit

Pick one canonical field.

Lane lean: rename `RollbackPlanEvidence.target_paths` to `target_refs` and
define file paths as one target-ref kind.

```text
RollbackPlanEvidence(
    rollback_path_class: str,
    target_refs: tuple[str, ...],
    planned_backup_paths: tuple[str, ...],
    expected_pre_mutation_hashes: dict[str, str],
    ...
)
```

Define:

```text
target_refs_for_preview(preview: MutationPreviewArtifact) -> tuple[str, ...]
target_refs_for_rollback_plan(plan: RollbackPlanEvidence) -> tuple[str, ...]
```

`expected_pre_mutation_hashes` keys must exactly match `target_refs` for
file-backed targets. Non-file targets must use reviewed target-ref schemes such
as `config:<key>`, `model_routing:<entry>`, or `credential:<id_hash>`.

### D24 tests

Add a replay test where changing a target ref changes
`target_ref_hashes_before_mutation_hash` and `action_edge_key`. Add a validator
test rejecting a rollback plan whose target refs differ from preview affected
refs.

## 4. Credential Consume/Invocation Carrier Clarification

**Absorbs:** Fresh-reader spec-implementor minor; Codex panel Cluster A;
Codex reviewers 1, 2, and 3.

v13 public consume accepts `S7GuardedExecutionInvocation`, but credential
execution still passes `S7CredentialGuardedRequest` plus rendered statement
directly.

### v14 edit

Pick a credential consume carrier.

Lane lean:

```text
S7GuardedCredentialInvocation(
    request_id: str,
    artifact_id: str,
    credential_request: S7CredentialGuardedRequest,
    rendered: RenderedCredentialRequestStatement,
    execution_consumer_id: str,
    surface_manifest_hash: str,
    source_surface: str,
    source_method: str,
    credential_action: str,
    credential_phase: "register_begin" | "register_finish" | "backup_card" | "disable",
    adapter_id: str,
    adapter_code_hash: str,
    action_params_hash: str,
    authority_context: AuthorityContext,
    precondition_hash: str,
    derived_work_class: "founder_credential_management",
    derived_aggregation_group: str,
    rollback_plan_ref: str,
    challenge_id: str,
    challenge_hash: str,
    challenge_expires_at: str,
    credential_id_hash: str | None,
    covenant_ceremony_evidence: object | None,
)
```

Amend consume to accept a closed union:

```text
S7GuardedStateStore.consume_artifact_for_execution(
    *,
    invocation: S7GuardedExecutionInvocation | S7GuardedCredentialInvocation,
    now: datetime,
    connection: sqlite3.Connection | None = None,
    after_consume_before_commit: Callable[[S7ConsumeResult], object] | None = None,
) -> S7ConsumeResult
```

Add:

```text
unpack_guarded_credential_invocation(
    invocation: S7GuardedCredentialInvocation,
    *,
    credential_invocation_store: S7GuardedCredentialInvocationStore,
    now: datetime,
) -> InheritedConsumeInputs
```

The helper verifies credential request hash, rendered hash, challenge expiry,
consumer id, rollback ref, and credential action/phase before forwarding.

### D24 tests

Add credential consume tests for begin, finish, backup-card, and disable. Loose
credential consume kwargs fail before inherited consume. A voice invocation
with credential null fields is rejected.

## 5. Bridge UNIQUE Grammar Cleanup

**Absorbs:** Fresh-reader covenant nit; Codex panel Cluster E.

v13 keeps stale wording:

```text
one of these unique constraint
```

### v14 edit

Replace with:

```text
The request-history table enforces this unique constraint:
UNIQUE(provenance_source_kind, provenance_source_ref)
```

### D24 tests

No new behavior test is needed beyond the existing bridge idempotency test.
The fold plan acceptance checklist should grep for the exact corrected phrase.

## 6. `telegram.approve_train` Derivation/Matrix Contradiction

**Absorbs:** Codex panel Cluster F; Codex reviewer 2.

v13 derivation says `telegram.approve_train + approve_train` is a reviewed
exclusion with no mintable consumer id. The printed matrix assigns
`dream_apply_proposal` and `fail_closed_until_review`.

### v14 edit

Pick one source of truth.

Lane lean: Telegram approve-train is not a live guarded S7.3 v1 route. It is
fail-closed until a reviewed dream-approval wrapper maps it to a concrete
guarded path.

Update both table and matrix:

```text
source_surface="telegram.approve_train"
source_method="approve_train"
execution_consumer_id=None
route_status="fail_closed_until_review"
exclusion_reason_code="telegram_approve_train_unreviewed"
```

If the operator chooses reviewed exclusion instead, both derivation and matrix
must use `route_status="reviewedly_excluded"` and a reviewed exclusion reason.
The key point is that the table and matrix match.

### D24 tests

Add a derivation/matrix mirror test asserting every printed matrix row resolves
through `execution_consumer_id_for(source_surface, source_method)` to the same
consumer id, route status, and exclusion reason.

## 7. Request-Family Legacy Migration/Cutoff Rule

**Absorbs:** Codex panel Cluster G; Codex reviewer 4.

v13 says S7.3 voice-family rows derive family at the writer, while legacy
null-provenance rows outside S7.3 still count. Existing S7.1 rows may be
null-provenance and voice-related. The spec needs a cutoff so old legitimate
legacy history is not erased while new S7.3 operational rows cannot masquerade
as legacy.

### v14 edit

Add:

```text
S7_3_REQUEST_HISTORY_CUTOFF = <migration timestamp or schema version>
```

Derivation rule:

```text
if record.created_at < S7_3_REQUEST_HISTORY_CUTOFF
   and record.provenance_source_kind is None:
       request_history_family_for(record) = None
       legacy aggregation branch may count it
elif record.created_at >= S7_3_REQUEST_HISTORY_CUTOFF:
       request_history_family_for(record) derives from closed S7.3 fields
       S7.3 voice-family null-provenance refused rows are rejected at writer
       or ignored by aggregation
```

If timestamps are unreliable, use a schema version or migration marker instead
of wall time. The chosen cutoff carrier must be durable and replayable.

### D24 tests

Add a mixed-history test with:

- pre-cutoff null-provenance refused row that counts;
- post-cutoff S7.3 operational null-provenance refused attempt that is rejected
  or ignored;
- post-cutoff authoritative S7.3 refused row that counts by provenance.

## 8. Same-Box Response-Stream Caveat Narrowed

**Absorbs:** Codex panel Cluster H; Codex reviewer 4.

This is the only covenant-adjacent widening item. The fix direction is to
shrink the Honesty Banner claim, not to add a new S7.3 defense.

### v14 edit

Replace any wording that implies S7.3 v1 prevents privileged live response
stream fabrication. The Honesty Banner should say:

```text
S7.3 v1 does not defend against a privileged same-box actor that can write to
Maez's live response stream before capture. S7.3 narrows the attack window,
binds captured evidence to nonce/request/preview hashes, refuses marker-only
D23 authority, and records replayable evidence. It does not prove response
authorship against that attacker until the future Maez cryptographic identity
substrate lands.
```

No new response-authorship mechanism is introduced in v14.

### D24 tests

No new positive defense test. Add a documentation/checklist assertion that the
Honesty Banner contains the negative claim above and does not assert that S7.3
solves privileged same-box response-stream tampering.

## 9. `_voice_seat_block(...)` History Writer Provenance Signature

**Absorbs:** Codex panel Cluster I; Codex reviewer 4.

`record_refusal_history(...)` requires provenance fields, but
`_voice_seat_block(...)` takes `history_writer:
Callable[[S7RequestHistoryRecord], None]`, which cannot carry the required
provenance.

### v14 edit

Define a writer protocol:

```text
S7RequestHistoryWriter.record_refusal_history(
    *,
    record: S7RequestHistoryRecord,
    provenance_source_kind: str | None,
    provenance_source_ref: str | None,
    provenance_authority_class: str | None,
    provenance_voice_event: str | None,
    conn: sqlite3.Connection,
    now: str,
) -> None
```

Amend `_voice_seat_block(...)`:

```text
_voice_seat_block(
    *,
    envelope: WorkRequestEnvelope,
    reduction: S7VoiceReduction,
    authority_row: S7VoiceAuthorityRow | None,
    trace_writer: S7TraceWriter,
    history_writer: S7RequestHistoryWriter,
    conn: sqlite3.Connection,
    now: str,
) -> None
```

The function may not call a legacy one-argument writer for S7.3 voice-family
rows.

### D24 tests

Add a static/signature test proving `_voice_seat_block(...)` cannot be wired to
`Callable[[S7RequestHistoryRecord], None]` for S7.3 voice-family rows. Add a
runtime test where an operational row attempts to call the writer without
provenance and fails.

## 10. `history_outcome` Derived Inside Authority-Row Builder

**Absorbs:** Codex panel Cluster J; Codex reviewer 4.

`build_s7_voice_authority_row(...)` currently accepts `history_outcome` as a
loose caller argument. D19 says history outcome is determined by reducer output
and bridge eligibility.

### v14 edit

Remove `history_outcome` from the builder signature. Add:

```text
history_outcome_for(
    *,
    reducer_output: S7VoiceReduction,
    bridge_eligible: bool,
) -> "refused" | None
```

Rules:

```text
bridge_eligible=False                                  -> None
authority_class="authoritative"
  and maez_withdrew_request=True                       -> "refused"
authority_class="authoritative"
  and maez_objection_state="present"                   -> "refused"
otherwise                                              -> None
```

Withdrawal/refusal distinction remains in `provenance_voice_event`, not in
`history_outcome`.

### D24 tests

Add a builder test that attempts to pass `history_outcome` and fails type or
signature validation. Add a row test for withdrawal precedence.

## 11. Credential Begin/Finish Trace Idempotency Key

**Absorbs:** Codex panel Cluster K; Codex reviewer 1.

Credential trace idempotency key `(request_id, credential_action,
credential_id_hash)` can collide for begin and finish traces sharing one
registration binding.

### v14 edit

Add `credential_phase` to `S7CredentialGuardedTrace`:

```text
credential_phase: "register_begin" | "register_finish" | "backup_card" | "disable"
```

Change idempotency key:

```text
credential trace:
    (request_id, credential_action, credential_phase, challenge_id,
     credential_id_hash)
```

For disable without a challenge, use `challenge_id=None` in the tuple and rely
on `credential_phase="disable"` plus `credential_id_hash`.

### D24 tests

Add begin/finish trace tests that share request id, credential action, and
credential id hash but do not collide because phase and challenge id are part
of the key.

## 12. `credential_rotate` Producer Or Unreachable Rationale

**Absorbs:** Codex panel Cluster L; Codex reviewer 2.

`CREDENTIAL_PROPOSED_CHANGE_CLASSES` includes `credential_rotate`, but v13 has
no rotation producer.

### v14 edit

Pick one.

Lane lean: remove `credential_rotate` from S7.3 v1, or mark it
reviewed-unreachable:

```text
credential_rotate is reserved for a future reviewed credential-rotation slice.
S7.3 v1 producers cannot emit it; constructors reject it unless
route_status="reviewedly_excluded" with
exclusion_reason_code="credential_rotate_future_slice".
```

### D24 tests

Add a closed-vocabulary test that `credential_rotate` cannot appear on a live
S7.3 v1 credential request or history row.

## 13. D-Enum Acceptance Mirror Completeness

**Absorbs:** Codex panel Cluster M; Codex reviewer 2.

The implementation acceptance checklist omits closed sets introduced in
D-Enum.

### v14 edit

Add these to the checklist:

```text
S7_ACTION_ENGINE_CONSUMER_IDS
NON_MINTABLE_EXECUTION_CONSUMER_IDS
PRODUCER_RESULT_REASON_CODES
PROJECTION_REASON_CODES
CREDENTIAL_PROPOSED_CHANGE_CLASSES
```

If v14 keeps `credential_rotate` as reviewed-unreachable, the checklist must
say so.

### D24 tests

Extend the table-complete closed-vocabulary test to cover every D-Enum closed
set named above.

## 14. Reviewed-Exclusion Null Display Normalization

**Absorbs:** Codex panel Cluster N; Codex reviewer 2.

v13 uses `N/A`, `None`, and literal-looking `none` for excluded consumer ids.
`"none"` is a real token for some vocabularies and must not look like a
consumer id.

### v14 edit

Pin the convention:

```text
Matrix display for null: N/A
Python prose for null: None
SQL persisted value: NULL
Never use "none" for execution_consumer_id.
```

Update first-primary credential bootstrap and any reviewed exclusion prose to
use `execution_consumer_id=None`, not `execution_consumer_id=none`.

### D24 tests

Add a matrix parser/validator test that rejects literal `"none"` in
`execution_consumer_id`.

## 15. Operational Reliability Escalation Wording

**Absorbs:** Codex panel Cluster O; Codex reviewer 4.

v13 says blackhole-reader rows may escalate as operational reliability evidence
and also says operational rows must not count as escalation evidence. The
intended distinction is sound but wording conflicts.

### v14 edit

Use this wording:

```text
Operational rows do not count as Maez-refusal evidence, Maez-preference
evidence, D23 refusal aggregation, or covenant escalation evidence. They may
count as system reliability evidence for operational-health investigation under
a separate reviewed health mechanism.
```

### D24 tests

Add an aggregation test proving operational rows do not affect D23 refusal
counts. Add, if there is an operational-health projection test, that
reader-unavailable operational rows can project reliability status without
becoming refusal/preference evidence.

## Secondary Cleanup Pool

These cleanup items are subordinate to the named sections above. They may be
folded while editing the relevant section but must not replace the named
sections.

- Nonce uniqueness duplication: choose inline UNIQUE or named unique index, not
  both, unless the duplicate is deliberately kept with a rationale.
- Failure-code labels: change `invalid_prompt_integrity` and
  `invalid_authority_class_replay` producer labels to `wrapper-owned` or a
  more precise seam consistent with the prose.
- Draft marker replay wording: state that draft `marker_text_hash` is transient
  classifier/parser evidence and final bundle replay uses raw response refs,
  attempt records, and semantic-reader attempt refs.
- `manifest_hash` vs `surface_manifest_hash`: use `surface_manifest_hash` for
  surface manifest bindings.
- `proposal_origin` vs `proposal_origin_label`: define the relationship or
  use one term consistently.
- `CovenantCeremonyEvidence`: declare the type or replace it with `object |
  None` consistently.
- `manual_review_status`: declare a closed vocabulary if the field remains.
- `superseded_request_ids`: align tuple/set typing across invocation and
  inherited consume.
- `reservation_token_hash` vs raw `reservation_token`: state which field is
  persisted and which field is runtime-only.
- `credential_request_method_for_surface(...)`: make the return type precise
  for begin/finish pair output.
- Grep checklist case stability: use exact expected casing for
  `wrapper-side preflight owns`.
- `attempt_input_hash` and `attempt_started_at`: clarify whether
  `attempt_started_at` is classifier input or audit timing included for replay.
- Remove stale v9/v11 labels from normative Honesty Banner text where v14 is
  the current spec.

## v14 Acceptance Checklist

The committed v14 spec must contain these grep-stable strings:

```text
d23_state_for(
trace_status_transition_for(
S7GuardedCredentialInvocation
unpack_guarded_credential_invocation
target_refs_for_rollback_plan
telegram_approve_train_unreviewed
S7_3_REQUEST_HISTORY_CUTOFF
does not defend against a privileged same-box actor
S7RequestHistoryWriter.record_refusal_history
history_outcome_for(
credential_phase
credential_rotate is reserved for a future reviewed credential-rotation slice
S7_ACTION_ENGINE_CONSUMER_IDS
NON_MINTABLE_EXECUTION_CONSUMER_IDS
PRODUCER_RESULT_REASON_CODES
PROJECTION_REASON_CODES
CREDENTIAL_PROPOSED_CHANGE_CLASSES
Never use "none" for execution_consumer_id
Operational rows do not count as Maez-refusal evidence
enforces this unique constraint
```

## Plain English

v14 is the bookkeeping fold. v13 already has the right covenant posture and
almost all of the engineering carrier surface. v14 makes the last closed sets
honest: every status gets a writer, every writer gets a signature, every route
row agrees with its derivation table, every credential phase has a carrier, and
the Honesty Banner stops overclaiming against privileged live response-stream
tampering. Nothing here changes what S7.3 is. It makes the spec precise enough
to become canonical.
