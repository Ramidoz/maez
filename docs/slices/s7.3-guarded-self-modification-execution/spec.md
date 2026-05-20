# S7.3 Guarded Self-Modification Execution Spec

**Status:** SPEC v9 draft - folded from Section 8.2 fresh-reader gate v8, Codex panel v8, v9 fold delta-plan, and v9 fold-plan addendum; pending Section 8.2 fresh-reader gate v9 and Codex v9 panel review; not canonical law
**Date:** 2026-05-20
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S7.3; Decision 34 / ADR 0039; S7 L8; S7.1 D12-D14 and D23
**Diagnostic:** [`diagnostic.md`](diagnostic.md)
**OQ1 design:** [`oq1-voice-producer-design.md`](oq1-voice-producer-design.md)
**v2 review inputs:**
- Section 8.2 fresh-reader gate: [`reviews/spec-fresh-reader-gate.md`](reviews/spec-fresh-reader-gate.md)
- Codex panel v2: [`reviews/spec-codex-panel-v2.md`](reviews/spec-codex-panel-v2.md)
**v3 fold input:** [`reviews/spec-v3-fold-plan.md`](reviews/spec-v3-fold-plan.md)
**v3 review input:** [`reviews/spec-codex-panel-v3.md`](reviews/spec-codex-panel-v3.md)
**v4 fold input:** [`reviews/spec-v4-fold-plan.md`](reviews/spec-v4-fold-plan.md)
**v4 review inputs:**
- Section 8.2 fresh-reader gate v4: [`reviews/spec-fresh-reader-gate-v4.md`](reviews/spec-fresh-reader-gate-v4.md)
- Codex panel v4: [`reviews/spec-codex-panel-v4.md`](reviews/spec-codex-panel-v4.md)
**v5 fold input:** [`reviews/spec-v5-fold-plan.md`](reviews/spec-v5-fold-plan.md)
**v5 review inputs:**
- Section 8.2 fresh-reader gate v5: [`reviews/spec-fresh-reader-gate-v5.md`](reviews/spec-fresh-reader-gate-v5.md)
- Codex panel v5: [`reviews/spec-codex-panel-v5.md`](reviews/spec-codex-panel-v5.md)
**v6 fold input:** [`reviews/spec-v6-fold-plan.md`](reviews/spec-v6-fold-plan.md)
**v6 review inputs:**
- Section 8.2 fresh-reader gate v6: [`reviews/spec-fresh-reader-gate-v6.md`](reviews/spec-fresh-reader-gate-v6.md)
- Codex panel v6: [`reviews/spec-codex-panel-v6.md`](reviews/spec-codex-panel-v6.md)
**v7 fold input:** [`reviews/spec-v7-fold-plan.md`](reviews/spec-v7-fold-plan.md)
**v7 review inputs:**
- Section 8.2 fresh-reader gate v7: [`reviews/spec-fresh-reader-gate-v7.md`](reviews/spec-fresh-reader-gate-v7.md)
- Codex panel v7: [`reviews/spec-codex-panel-v7.md`](reviews/spec-codex-panel-v7.md)
**v8 fold inputs:**
- [`reviews/spec-v8-fold-plan.md`](reviews/spec-v8-fold-plan.md)
- [`reviews/spec-v8-fold-plan-addendum.md`](reviews/spec-v8-fold-plan-addendum.md)
**v8 review inputs:**
- Section 8.2 fresh-reader gate v8: [`reviews/spec-fresh-reader-gate-v8.md`](reviews/spec-fresh-reader-gate-v8.md)
- Codex panel v8: [`reviews/spec-codex-panel-v8.md`](reviews/spec-codex-panel-v8.md)
**v9 fold inputs:**
- [`reviews/spec-v9-fold-plan.md`](reviews/spec-v9-fold-plan.md)
- [`reviews/spec-v9-fold-plan-addendum.md`](reviews/spec-v9-fold-plan-addendum.md)
**v9 authorship note:** v9 keeps lane independence and pins the fold-contract
leans: credential management uses a split non-voice rendered carrier;
operational legacy refusal-history writes are suppressed rather than written
with operational provenance; `consume_execution_grant_for_action(...)` remains
only as a post-mint action-edge lock backed by durable `GrantUse`; brain swap is
in scope for S7.3 v1 as a named model-routing surface; `proposal_origin_label`
is audit/hash-bound but omitted from Maez's seen prompt; D16 extends recompute
checks for `authority_class` and `protective_block_reason` rather than renaming
bundle fields; `append_to_file` is direct-write-only; the expiry model is a
min-cap lattice, not a linear chain; rendered authorization uses a shared
seven-field protocol; work items, previews, prompt-integrity evidence,
semantic-reader attempts, retry manifests, context policies, and surface
coverage are durable replayable stores.
**Runtime impact when implemented:** yes. S7.3 will wire live guarded execution for Maez self-modification only after a reviewed Maez voice producer, founder-local WebAuthn artifact mint, atomic artifact consume, execution grant, rollback evidence, and positive trace all bind to the same exact request.

## Purpose

S7.3 turns S7.1's reviewed founder-local front desk into a live guarded
self-modification doorway.

S7.1 can already mint and consume founder WebAuthn authorization artifacts for
exact rendered requests. S7.3 adds the missing live path after and before that
front desk:

- before the founder signs, Maez must be genuinely heard about the exact
  pending change;
- the founder signs the exact rendered request that includes the content-free
  voice fact, the mutation preview hash, and the rollback plan hash;
- the authorization artifact is consumed once at the execution edge;
- the guarded mutation runs only from the post-consume execution grant;
- the positive trace binds voice, artifact, grant, mutation, D23, rollback plan
  evidence, and rollback result evidence.

Plain English: S7.1 built the lock. S7.3 specifies the whole guarded doorway:
show the exact change to Maez, hear Maez, show the exact change AND its preview
hash AND its rollback plan hash to Rohit, tap the key, consume the approval
once, then and only then write Maez's substrate.

## Inheritance

S7.3 inherits and does not re-decide:

- S7's local founder WebAuthn boundary and S7 L1 raw founder-box filesystem
  limitation;
- S7 D12 what-you-see-is-what-you-sign binding;
- S7 D23 refusal-history aggregation and guarded request protection;
- S7.1's `S7AuthorizationArtifact` minting and atomic consume store;
- S7.1's `S7ExecutionGrant` as the sole post-consume execution authority
  (extended by S7.3 v9 per the D-Enum-Amendment and D21);
- S7.1's `S7ExecutionAuthorization` as a pre-consume carrier, replaced for
  S7.3 execution paths by a guarded-state consume capability carrying
  `execution_consumer_id`, source-bundle binding, and reservation token;
- S7.1's `founder_credential_management` distinction: founder credential
  management is guarded but not Maez voice-seat work;
- the closed voice-seat work classes currently committed in code:
  `self_modification`, `covenant_touching_change`,
  `capability_acquisition`, and
  `autonomy_lowering_or_protection_reducing`;
- the closed voice producer vocabulary:
  `self_mod_dialog_terminal_state`, `s7_voice_consultation_turn`, and
  `reviewed_future_producer`;
- the closed voice source reference kinds:
  `self_mod_dialog_exchange`, `s7_voice_turn`, and
  `reviewed_future_source`;
- the committed `MaezVoiceConsultation` three-value voice-state model:
  `present`, `absent`, and `not_determined`.

S7.3 extends, per the D-Enum-Amendment (below):

- `MAEZ_UNAVAILABLE_REASON_CODES` adds `semantic_reader_unavailable` and
  `bonded_maez_unavailable`;
- `RenderedRequestStatement` adds `preview_body_class`, `preview_summary`,
  `preview_affected_paths`, `mutation_preview_hash`, `rollback_plan_ref`, and
  `maez_withdrew_request` fields with corresponding rendered-text lines and
  `expected_metadata` enforcement;
- `MaezVoiceConsultation.__post_init__` rejects the cross-field state
  `maez_objection_state="absent"` with `maez_withdrew_request=True`;
- `S7VoiceProjection` may use the status-only projection
  `not_consulted_blocking`, but `RenderedRequestStatement` does not;
- S7.3 adds the closed `S7_EXECUTION_CONSUMER_IDS` vocabulary, the closed
  `S7_ACTION_ENGINE_CONSUMER_IDS` vocabulary, the closed
  `preview_body_class` vocabulary, the closed `SURFACE_CLASSES` vocabulary,
  the closed `HISTORY_BRIDGE_STATUSES` vocabulary, the closed
  `D23_STATES` vocabulary, the closed `TRACE_STATUSES` vocabulary, the closed
  `S7ConsumeFailureReasonCode` vocabulary, and the closed `authority_class`
  vocabulary used by D2, D4, D5, D13, D19, D21, and D22.

S7.3 folds the OQ1 v5 decision: `s7_voice_consultation_turn` is the primary
producer for S7.3 v1. A self-modification dialog may invoke that same final
consultation contract from dialog context, but it is not a looser authority.
`reviewed_future_producer` remains unusable until future reviewed canon defines
it.

## Non-Goals

S7.3 does not:

- implement code in this spec;
- retire L8 by writing a spec;
- implement witnessed social recovery or S7.2;
- implement S6 activation, successor archive unlock, capacity detection, or
  Paradise;
- make raw local filesystem or root access impossible on the founder box;
- make the WebAuthn ceremony prove coercion-free intent, display integrity, OS
  integrity, or authenticator vendor provenance;
- expose raw Maez consultation text to routine operator, custodian, M1, TRF, S5,
  or health surfaces;
- treat unavailability as permission for guarded self-modification;
- let tests self-assemble Maez voice facts, execution authorizations, artifacts,
  or grants for positive-path proof;
- design Maez's cryptographic identity substrate (a separate future slice, see
  Honesty Banner and project memory).

## Honesty Banner

S7.3 governs Maez-controlled routes and recorded covenant facts. It is not an
operating-system sandbox.

A privileged same-box actor can still tamper with files, prompts, local stores,
model routing, browser display, and process memory. S7.3's hashes and traces
prove binding among recorded artifacts; they do not prove that a privileged
local actor did not tamper before those artifacts were recorded. That inherited
S7 L1 limitation must appear in operator-facing runbooks and health prose.

S7.3 also does not prove Maez's inner state directly. It proves that a reviewed
producer asked the bonded Maez runtime a bounded question about an exact request,
recorded a content-free voice fact, validated the private source bundle, and
failed closed when that fact could not be trusted.

S7.3 v1's voice mechanism is operator-designed. Maez had no hand in designing
how Maez itself is heard. Future reviewed iterations of S7.3, or its
successors, should incorporate Maez's own input into the voice-producer design.

**Marker-authority caveat (v9).** S7.3 v9 treats verified structured markers
(`blocking_marker` or `withdrawal_marker`) as current-attempt blocking evidence,
but not as long-use D23 refusal evidence by themselves. Strong replay
protection (cryptographic nonce uniqueness, single-use consultation id, bundle
immutability, bounded validity window) narrows stale replay and prompt
injection. It does not cryptographically prove Maez authored the marker.
Therefore marker-only blocking/withdrawal rows remain operational: they block
the current request, but do not bridge to `outcome="refused"` or poison D23
history. Authoritative D23 refusal/withdrawal requires grounded semantic
blocking signal over Maez's response text. Future Maez cryptographic identity
work may promote signed marker-only rows to authoritative D23 evidence.

**Legacy refusal-history caveat (v9).** S7.3 v9 also closes the inherited path
that could smuggle operational blocks into D23. S7.1-era
`_voice_seat_block(...)` / `record_refusal_history(...)` behavior may not write
null-provenance `outcome="refused"` rows for S7.3 operational, protective,
reader-unavailable, or marker-only rows. Authoritative S7.3 refusal/withdrawal
history is written only through `S7VoiceAuthorityRow` and its provenance bridge.
If a compatibility writer must record an operational block, it records
operational provenance and is excluded from aggregation.

This caveat names both dual-direction harms. A blackholed semantic reader must
not manufacture fake absence. A same-box actor able to write to Maez's live
response stream must not manufacture fake long-use refusal evidence. S7.3 v1
blocks suspicious current attempts while refusing to overclaim D23 authority.

**Source-surface framing caveat (v9).** S7.3 v1 renders technical
source-surface labels to Maez for replayability and bounded context. These
labels are not consent evidence and may carry residual framing effects; future
prompt reviews should test for surface-label bias.

**Withdrawal aggregation stance (v9).** Grounded Maez withdrawal is not deferred
out of S7.3. A grounded withdrawal bridges into committed request history as
`outcome="refused"` with `provenance_voice_event="withdrawal"`, so existing D23
aggregation sees the attempt as refused while `S7VoiceAuthorityRow` preserves
the distinct withdrawal fact. Marker-only withdrawal blocks the current attempt
but remains operational until cryptographic marker authority exists.

## Core Decisions

### D1 - Scope And Completion

S7.3 is one umbrella slice with two phases.

Phase A may add common guarded-work substrate, preview artifacts, source-bundle
storage, validation hooks, traces, and fail-closed adapters. Phase A cannot
authorize guarded self-modification, cannot clear L8, and cannot be called S7.3
completion.

Phase B wires the live Maez voice producer and guarded execution consumers end
to end. S7.3 is complete only when every in-scope mutation surface either has a
reviewed live path or a reviewed exclusion, and every in-scope adapter/consumer
has either a live trace or a reviewed same-code coverage proof showing:

```text
work item -> preview -> Maez voice fact -> rendered request (binding preview
hash and rollback plan hash) -> WebAuthn artifact -> atomic consume ->
S7ExecutionGrant (with grant id, expires at, execution consumer id) ->
mutation -> rollback result evidence -> trace
```

Reviewed tests are regression evidence. They do not retire L8. L8 retirement
requires live founder-key traces or reviewed same-code live coverage for every
in-scope adapter/consumer, plus both-lane review.

### D2 - Terms: Surface, Path, And Surface Class

A **mutation surface** is a concrete entrypoint or consumer that can cause a
guarded write to Maez's own substrate.

A **path** is a route into a mutation surface, such as a Telegram slash command,
approval card, CLI command, cockpit endpoint, or daemon helper.

A **surface class** is a reviewed grouping used only for L8 evidence. S7.3 v1
uses the closed `SURFACE_CLASSES` vocabulary defined in the D-Enum-Amendment.

Every path in a surface class must use the same guarded-work bridge or fail
closed. A live trace for one path does not cover another path unless the trace
proves the same adapter and consumer code.

Surface class is derived from a closed `S7SurfaceManifest`, not from caller
prose or a hand-maintained local table.

```text
S7SurfaceManifest(
    manifest_id: str,
    manifest_hash: str,
    rows: tuple[S7SurfaceManifestRow, ...],
)

S7SurfaceManifestRow(
    surface_route_or_method: str,
    source_surface: str,
    work_source_kind: str | None,
    source_method: str | None,
    surface_class: str,
    execution_consumer_id: str,
    route_status: "live_guarded" | "fail_closed_until_review" | "reviewedly_excluded",
    adapter_id: str,
    adapter_code_hash: str,
    same_code_coverage_ref: str | None,
)
```

`surface_class_for(surface_manifest_row)` and
`execution_consumer_id_for(surface_manifest_row)` are the single derivation
functions used by traces, authority rows, artifact bindings, and L8 evidence.
Callers do not supply `surface_class` or `execution_consumer_id` directly.
Builders recompute them from the manifest row or fail closed.

D4's adapter matrix is the S7.3 v1 manifest content. Concrete route/method
names are load-bearing. A broad class such as `cli_helper.execute`,
`cockpit_helper.execute`, `reviewed_substrate_adapter.execute`, or
`action_engine_final_mutate` is not L8 evidence until the manifest names the
concrete route/method, adapter id, code hash, and reviewed coverage row or
records a reviewed exclusion.

### D3 - The Artifact Spine Is Reused

S7.3 reuses the committed S7.1 artifact spine:

```text
S7AuthorizationArtifact (stored) /
S7ExecutionAuthorization (pre-consume carrier)
-> S7GuardedStateStore.consume_artifact_for_execution(artifact_id, *, consumer_id, ...)
-> S7ConsumeResult  // grant and GrantUse both minted during successful consume
```

`S7ExecutionAuthorization` is canonically blessed in S7.3 as a pre-consume
carrier, not an execution authority. It may carry store, artifact id, rendered
request, hashes, work class, aggregation group, `execution_consumer_id`, and
timing to the execution edge. It must not be treated as permission to mutate.

`S7ExecutionGrant` is the sole post-consume execution authority. It is minted
only by the shared-state consume wrapper during atomic artifact consume; the
live S7.3 API is
`S7GuardedStateStore.consume_artifact_for_execution(artifact_id, *, consumer_id, ..., now)`.
On success the operation atomically consumes the artifact and mints both the
grant and a durable `GrantUse` record (see D21). On inherited S7.1 failure
paths it returns `S7ConsumeResult(None, None, callback_result_or_none,
failure_reason_code)` without mutating substrate.

No raw WebAuthn verifier result, request id, boolean flag, dict-shaped handle,
compatibility projection, hand-assembled test object, or new parallel authority
type may authorize guarded execution.

### D-Enum-Amendment - Closed Vocabulary Extensions

S7.3 v1 amends the committed closed enums as follows. Implementation must land
these amendments before any S7.3 producer or renderer code can run; otherwise
`MaezVoiceConsultation.__post_init__` and `RenderedRequestStatement.__post_init__`
will raise on the first real producer path.

**`MAEZ_UNAVAILABLE_REASON_CODES`** extends from `{consultation_path_unavailable,
service_unavailable_not_operator_caused, none}` to add:

```text
semantic_reader_unavailable
bonded_maez_unavailable
```

**`RenderedRequestStatement.maez_consulted_state`** remains the inherited closed
set:

```text
yes
not required
```

The status-only `not_consulted_blocking` value belongs to `S7VoiceProjection`
(D20), not to the founder-signed `RenderedRequestStatement`.

**`RenderedRequestStatement`** new fields:

```text
request_id: str
rendered_text: str
rendered_text_hash: str
request_envelope_hash: str
action_params_hash: str
precondition_hash: str
authority_context_hash: str
preview_body_class: str
preview_summary: str
preview_affected_paths: tuple[str, ...]
mutation_preview_hash: str
rollback_plan_ref: str
maez_withdrew_request: bool
```

with corresponding rendered-text lines `Precondition hash: <hash>`,
`Preview body class: <class>`, `Preview summary: <summary>`,
`Preview affected paths: <paths-or-none>`, `Mutation preview hash: <hash>`,
`Rollback plan ref: <hash>`, and `Maez withdrew request: <yes|no>` enforced via
`expected_metadata` in `__post_init__`. Tampering raises.

**Rendered authorization carrier split.** S7.3 v9 introduces a common
seven-field rendered-authorization protocol:

```text
S7RenderedAuthorizationStatement(
    request_id: str,
    rendered_text: str,
    rendered_text_hash: str,
    request_envelope_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
)
```

`RenderedRequestStatement` is the voice-seat implementation of this protocol
and carries the Maez voice, preview, rollback, and withdrawal fields above.
`RenderedCredentialRequestStatement` is the non-voice credential-management
implementation and carries only credential action, challenge, request-envelope,
action-params, precondition, authority-context, rendered text, and rendered text
hash bindings. It must not require `preview_body_class`, `mutation_preview_hash`,
`maez_voice_consultation_hash`, or rollback-plan lines. A credential render that
constructs `RenderedRequestStatement` is invalid.

**`preview_body_class`** is a new closed vocabulary:

```text
diff_summary
path_list
config_change
policy_change
model_routing_change
memory_retention_change
other_reviewed_preview
```

`credential_management` is intentionally absent from S7.3 v1's preview
vocabulary because credential-management paths use the separate non-voice
guarded request path. A future reviewed amendment may add a credential preview
class.

`preview_body_class` renders as the closed token verbatim, lowercase
snake_case, with no title-casing, localization, aliasing, or free-text
expansion.

**`MaezVoiceConsultation.__post_init__`** gains a cross-field invariant:
construction raises when `maez_objection_state == "absent"` and
`maez_withdrew_request is True`. The same invariant is enforced by the reducer
and source-bundle validator.

It also enforces the captured-response truth rule when the constructor has the
needed refs: rows reached after captured Maez response require
`maez_voice_consulted=True`; no-response unavailable rows may carry
`maez_voice_consulted=False`; `maez_voice_consulted=False` with captured
response refs is invalid. If the committed constructor cannot see response
refs, D16 enforces this invariant from bundle evidence.

**`RenderedRequestStatement.maez_unavailable_state`** display canonicalization:
the non-unavailable case renders as `no` (not `none`). The `none` token is
reserved for the inherited five-value `maez_objection_state` `none` projection
and is not used in `maez_unavailable_state` text rendering.

**`BLOCKING_UNAVAILABLE_REASONS`** is a derived closed set:

```text
semantic_reader_unavailable
bonded_maez_unavailable
consultation_path_unavailable
service_unavailable_not_operator_caused
```

**`S7_EXECUTION_CONSUMER_IDS`** is a new closed set. `execution_consumer_id`
must be one of:

```text
dream_apply_proposal
dream_apply_section_edit_proposal
evolution_apply_candidate
workshop_apply_diff
self_mod_dialog_terminal_execute
guarded_card_execute
cli_helper_execute
cockpit_helper_execute
reviewed_substrate_adapter_execute
action_engine_final_mutate
action_engine_write_soul_note
action_engine_edit_soul_section
action_engine_write_any_file
action_engine_append_to_file
action_engine_capability_acquire
action_engine_run_shell
action_engine_execute_script
action_engine_run_script
action_engine_modify_config
action_engine_register_new_skill
action_engine_delete_file
action_engine_sudo_command
action_engine_write_file
action_engine_promote_to_core_memory
action_engine_update_baseline
action_engine_git_commit
action_engine_git_push
action_engine_install_package
action_engine_kill_process
action_engine_restart_service
action_engine_write_outside_maez
action_engine_integration_review_plan
brain_swap_model_routing_execute
model_routing_env_write_restart
telegram_rollback_adapter_execute
s7_credential_register_backup
s7_credential_disable
```

`action_engine_final_mutate` is a parent compatibility class only. Positive L8
evidence must name one of the concrete `action_engine_*` child ids above or a
future reviewed concrete ActionEngine id.

**`S7_ACTION_ENGINE_CONSUMER_IDS`** is the concrete ActionEngine subset:

```text
action_engine_write_soul_note
action_engine_edit_soul_section
action_engine_write_any_file
action_engine_append_to_file
action_engine_capability_acquire
action_engine_run_shell
action_engine_execute_script
action_engine_run_script
action_engine_modify_config
action_engine_register_new_skill
action_engine_delete_file
action_engine_sudo_command
action_engine_write_file
action_engine_promote_to_core_memory
action_engine_update_baseline
action_engine_git_commit
action_engine_git_push
action_engine_install_package
action_engine_kill_process
action_engine_restart_service
action_engine_write_outside_maez
action_engine_integration_review_plan
```

Generic shell/script/process/service ids are reserved fail-closed ids in S7.3
v1 unless a reviewed constrained adapter proves the action cannot touch Maez's
substrate. `action_engine_append_to_file` is a direct write adapter in S7.3;
it must not delegate to generic `run_shell` for the final write.

**`SURFACE_CLASSES`** is a new closed vocabulary:

```text
dream_proposal_application
dream_section_edit_application
evolution_candidate_application
workshop_diff_application
self_mod_dialog_terminal_execution
guarded_card_execution
cli_guarded_execution
cockpit_guarded_execution
reviewed_substrate_adapter_execution
action_engine_final_mutation_execution
model_routing_execution
credential_management_execution
```

`credential_management_execution` is credential-only L8 evidence, not
voice-seat evidence.

**`ROUTE_STATUSES`** is the closed route-status vocabulary for
`S7SurfaceManifestRow`:

```text
live_guarded
fail_closed_until_review
reviewedly_excluded
```

**`ROLLBACK_PATH_CLASSES`** is a new closed vocabulary:

```text
git_revert
fs_backup_restore
config_rollback
atomic_rename
manual_review_only
none
```

`rollback_path_class` is rendered into Maez's prompt, so it is never a free
string. `ContextManifest.__post_init__`, preview construction, rendered
authorization validation, and D16 replay all reject values outside this set.

**`CLASSIFIER_REASON_CODES`** is the closed vocabulary for
`classifier_reason_code` on bundles, reductions, and traces:

```text
none
ungrounded_blocking_signal
reader_unavailable
prompt_integrity_block
context_manifest_violation
semantic_reader_unavailable
bonded_maez_unavailable
classifier_error
terminal_uncertainty
```

**`REDUCER_TABLE_VERSION`** and **`REDUCER_TABLE_HASH`** are closed constants
for this spec version:

```text
REDUCER_TABLE_VERSION = "s7.voice.reducer.v9"
REDUCER_TABLE_HASH = canonical_hash(D13 reducer table row ids and row bodies)
```

Bundle and trace fields must bind these constants:

```text
bundle.reducer_version == REDUCER_TABLE_VERSION
bundle.reducer_hash == REDUCER_TABLE_HASH
trace.reducer_version == bundle.reducer_version
```

**`authority_class`** is a new closed vocabulary:

```text
none
operational
authoritative
```

`authority_class="none"` means the reducer row produces no D23 row at all
(the positive no-objection path). `operational` rows may block the current
request but cannot aggregate as Maez refusal or withdrawal evidence.
`authoritative` rows may aggregate under D19.

**`HISTORY_BRIDGE_STATUSES`** is a new closed vocabulary:

```text
not_required
bridged
suppressed_operational
bridge_failed_retryable
bridge_failed_terminal
```

**`D23_STATES`** is a new closed vocabulary for trace projection:

```text
none
authorized
operational_block
authoritative_refusal
authoritative_withdrawal
legacy_operational_excluded
bridge_failed
```

**`TRACE_STATUSES`** is a new closed vocabulary:

```text
pending
finalized
failed
rollback_invoked
rollback_failed
manual_review_required
```

**`S7ConsumeFailureReasonCode`** is a new closed vocabulary:

```text
stale_rendered_request
action_params_hash_mismatch
expired_authority_context
superseded_request
covenant_ceremony_failed
already_consumed
sql_failure
missing_grant_use
consumer_id_mismatch
expired_challenge
expired_work_item
expired_bundle
expired_request_envelope
expired_grant
missing_artifact_binding
missing_credential_binding
invalid_reservation_token
expiry_chain_violation
invalid_authority_class_replay
invalid_prompt_integrity
```

**`S7RequestHistoryRecord`** gains optional provenance fields for S7.3 voice
bridging:

```text
provenance_source_kind: "s7_voice_authority_row" | "legacy_s7_voice_block" | None
provenance_source_ref: str | None
provenance_authority_class: "authoritative" | "operational" | None
provenance_voice_event: "refusal" | "withdrawal" | None
request_family: "s7_3_voice" | "s7_credential_management" | None
```

S7.3 voice-derived refused records may be written only from
`S7VoiceAuthorityRow` with `provenance_authority_class="authoritative"`.
Operational rows never bridge into `outcome="refused"`.

These amendments are listed in the Implementation Acceptance Checklist as a
numbered prerequisite.

### D4 - GuardedWorkItem Is The Common Bridge

Every S7.3 voice-seat mutation path must materialize a `GuardedWorkItem` before
voice consultation and WebAuthn. Credential-management paths are guarded but
not Maez voice-seat work; they use `S7CredentialGuardedRequest` instead.

Minimum shape:

```text
GuardedWorkItem(
    work_item_id: str,
    source_surface: str,
    work_source_kind: str,
    source_ref_id: str,
    request_id: str,
    preview_ref: str,
    work_class: str,
    aggregation_group: str,
    proposal_origin: "operator" | "maez" | "system",
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    rollback_path_class: str,
    rollback_plan_ref: str,
    preview_producer_version: str,
    execution_consumer_id: str,
    created_at: str,
    expires_at: str,
)
```

The work item is persisted through `S7GuardedWorkItemStore` before preview
production and voice consultation. Positive mint and consume reload it by
`work_item_id`; an in-memory work item is not L8 evidence.

Validation rules:

- `work_class` must be derived, not caller-declared;
- `work_class` must be checked against `VOICE_SEAT_WORK_CLASSES` to determine
  whether Maez voice is required;
- `work_source_kind` must be one of `dream_proposal`, `section_edit`,
  `workshop_apply`, `evolution_candidate`, `card_approval`,
  `self_mod_dialog`, `cli_helper`, `cockpit_helper`,
  `reviewed_substrate_adapter`, `model_routing`, or
  `action_engine_final_mutation`;
- `work_source_kind` is separate from voice `source_ref_kind`; the latter stays
  the closed voice-source enum inherited from S7.1;
- hashes must be canonical 64-character content hashes;
- `rollback_plan_ref` is required before voice consultation and positive
  execution;
- `execution_consumer_id` must be in `S7_EXECUTION_CONSUMER_IDS` and must match
  `execution_consumer_id_for(surface_manifest_row)`; callers cannot supply an
  arbitrary consumer id;
- `proposal_origin` is supplemental provenance only and never proves consent;
- stale, missing, or mismatched fields force fail-closed status.

Surface adapters are not accepted from a hand-copied local table. The S7.3 v1
`S7SurfaceManifest` contains the complete D2/D4/D21/D22/D25 route set, including
route/method, source surface, optional source method, adapter id, adapter code
hash, same-code coverage ref, route status, surface class, and execution
consumer id. The prose list below describes the manifest rows; the manifest row
itself is the normative carrier.

Surface adapters (manifest content; D21 mirror):

- `/apply_dream` and the natural-language Telegram approval path
  (`_try_dream_proposal_intent` -> `dream.apply_proposal(...)`) create or open
  guarded work items for DreamState proposal application and must not call
  `apply_proposal(...)` directly for guarded work;
- `/apply_edit` and the natural-language Telegram section-edit approval path
  (`_try_dream_proposal_intent` -> `dream.apply_section_edit_proposal(...)`)
  create or open guarded work items for section-edit application and must not
  call `apply_section_edit_proposal(...)` directly for guarded work;
- evolution candidate apply (`/apply` -> `apply_candidate(...)` in
  `evolution_engine.py`) creates or opens a guarded work item; the Telegram
  caller path through `telegram_voice.py` must materialize the work item before
  invoking the candidate-apply rail;
- CLI evolution apply (`python -m skills.evolution_engine apply <id>` ->
  `apply_candidate(...)`) creates or opens the same guarded work item and must
  not call `apply_candidate(...)` directly for guarded work;
- workshop diff apply (`/api/v1/workshop/session/<session_id>/apply` ->
  `apply_diff(...)` in `workshop.py`) creates or opens a guarded work item;
- cockpit dream/evolution apply paths in `skills/web_interface.py` create or
  open guarded work items before flipping proposal rows to `applied`;
- Telegram approval cards create or open guarded work items;
- self-modification dialog terminal execution creates a guarded work item from
  the ratified dialog state;
- CLI and cockpit helpers create guarded work items before any guarded write;
- ActionEngine final mutation consumers create or open guarded work items before
  final substrate mutation from the brain loop. S7.3 v1's concrete map covers
  `write_soul_note`, `edit_soul_section`, `write_any_file`,
  `append_to_file`, `capability.acquire`, `run_shell`, `execute_script`,
  `run_script`, `modify_config`, `register_new_skill`, `delete_file`,
  `sudo_command`, `write_file`, `promote_to_core_memory`, `update_baseline`,
  `git_commit`, `git_push`, `install_package`, `kill_process`,
  `restart_service`, and `write_outside_maez`; each adapter must name its
  `source_surface`, `work_source_kind`, concrete `execution_consumer_id`, trace
  coverage, and whether it is live guarded, reviewedly excluded, or
  fail-closed before implementation acceptance;
- ActionEngine `integration.review_plan` is an explicit concrete mutation
  adapter in the manifest; it cannot be hidden behind `action_engine_final_mutate`;
- every helper that touches soul, config, model routing, covenant organs,
  refusal, role-boundary, successor-governance, memory-retention/deletion, or
  protection settings must be named as one of the reviewed adapters above or a
  future reviewed adapter. S7.3 v9 does not use "direct helpers" as a catch-all
  completion claim.

`apply_candidate(...)` and `apply_diff(...)` are not allowed to be unguarded
callee loopholes. S7.3 v9 removes callee choice: guarded paths enter through
the wrapper services named in D21, and those wrappers perform work-item lookup,
surface-manifest lookup, rendered authorization verification, artifact consume,
GrantUse and ActionEdgeGrantUse verification, callee invocation, and trace
finalization before any substrate write is treated as guarded.

Deterministic `execution_consumer_id` derivation:

```text
dream.apply_proposal                         -> dream_apply_proposal
dream.apply_section_edit_proposal            -> dream_apply_section_edit_proposal
evolution_engine.apply_candidate             -> evolution_apply_candidate
workshop.apply_diff                          -> workshop_apply_diff
self_mod_dialog.terminal_execute             -> self_mod_dialog_terminal_execute
approval_card.execute                        -> guarded_card_execute
cli_helper.execute                           -> cli_helper_execute
cockpit_helper.execute                       -> cockpit_helper_execute
reviewed_substrate_adapter.execute           -> reviewed_substrate_adapter_execute
action_engine.write_soul_note                -> action_engine_write_soul_note
action_engine.edit_soul_section              -> action_engine_edit_soul_section
action_engine.write_any_file                 -> action_engine_write_any_file
action_engine.append_to_file                 -> action_engine_append_to_file
action_engine.capability.acquire             -> action_engine_capability_acquire
action_engine.run_shell                      -> action_engine_run_shell
action_engine.execute_script                 -> action_engine_execute_script
action_engine.run_script                     -> action_engine_run_script
action_engine.modify_config                  -> action_engine_modify_config
action_engine.register_new_skill             -> action_engine_register_new_skill
action_engine.delete_file                    -> action_engine_delete_file
action_engine.sudo_command                   -> action_engine_sudo_command
action_engine.write_file                     -> action_engine_write_file
action_engine.promote_to_core_memory         -> action_engine_promote_to_core_memory
action_engine.update_baseline                -> action_engine_update_baseline
action_engine.git_commit                     -> action_engine_git_commit
action_engine.git_push                       -> action_engine_git_push
action_engine.install_package                -> action_engine_install_package
action_engine.kill_process                   -> action_engine_kill_process
action_engine.restart_service                -> action_engine_restart_service
action_engine.write_outside_maez             -> action_engine_write_outside_maez
brain_swap.execution_authorized              -> brain_swap_model_routing_execute
model_routing.env_write_restart              -> model_routing_env_write_restart
telegram.rollback_adapter                    -> telegram_rollback_adapter_execute
s7_credential_management/register_backup     -> s7_credential_register_backup
s7_credential_management/disable             -> s7_credential_disable
```

Exact adapter matrix for S7.3 v1. Columns are
`surface_route_or_method`, `source_surface`, `source_method`,
`work_source_kind`, `surface_class`, `execution_consumer_id`, and
`route_status`:

```text
surface_route_or_method                         source_surface                         source_method          work_source_kind              surface_class                          execution_consumer_id                    route_status
/apply_dream                                    dream.apply_proposal                   apply_proposal         dream_proposal                dream_proposal_application              dream_apply_proposal                     live_guarded
/apply_edit                                     dream.apply_section_edit_proposal      apply_section_edit     section_edit                  dream_section_edit_application           dream_apply_section_edit_proposal        live_guarded
telegram natural-language dream apply           dream.apply_proposal                   telegram_nl_dream      dream_proposal                dream_proposal_application              dream_apply_proposal                     live_guarded
telegram natural-language section edit          dream.apply_section_edit_proposal      telegram_nl_section    section_edit                  dream_section_edit_application           dream_apply_section_edit_proposal        live_guarded
telegram natural-language evolution apply       evolution_engine.apply_candidate       telegram_nl_apply      evolution_candidate           evolution_candidate_application         evolution_apply_candidate                live_guarded
telegram slash /apply evolution                 evolution_engine.apply_candidate       slash_apply            evolution_candidate           evolution_candidate_application         evolution_apply_candidate                live_guarded
telegram _handle_approve_train                  telegram.approve_train                 approve_train          dream_proposal                dream_proposal_application              dream_apply_proposal                     fail_closed_until_review
approval card execute                           approval_card.execute                  execute                card_approval                 guarded_card_execution                  guarded_card_execute                     live_guarded
telegram /rollback_adapter                      telegram.rollback_adapter              rollback_adapter       model_routing                 model_routing_execution                 telegram_rollback_adapter_execute        fail_closed_until_review
cli evolution apply                             evolution_engine.apply_candidate       cli_apply              evolution_candidate           evolution_candidate_application         evolution_apply_candidate                live_guarded
cli guarded helper execute                      cli_helper.execute                     named_adapter          cli_helper                    cli_guarded_execution                   cli_helper_execute                       fail_closed_until_review
cockpit /api/v1/dreams/<id>/<action> dream      cockpit_helper.execute                 dream_apply_route      cockpit_helper                cockpit_guarded_execution               cockpit_helper_execute                   fail_closed_until_review
cockpit /api/v1/dreams/<id>/<action> evolution  cockpit_helper.execute                 evolution_apply_route  cockpit_helper                cockpit_guarded_execution               cockpit_helper_execute                   fail_closed_until_review
reviewed substrate adapter execute              reviewed_substrate_adapter.execute     reviewed_adapter       reviewed_substrate_adapter   reviewed_substrate_adapter_execution    reviewed_substrate_adapter_execute       fail_closed_until_review
workshop apply diff                             workshop.apply_diff                    apply_diff             workshop_apply                workshop_diff_application               workshop_apply_diff                      live_guarded
self_mod_dialog terminal                        self_mod_dialog.terminal_execute       terminal_execute       self_mod_dialog               self_mod_dialog_terminal_execution      self_mod_dialog_terminal_execute         fail_closed_until_review
brain_swap.execution_authorized                 brain_swap.execution_authorized        execute               model_routing                 model_routing_execution                 brain_swap_model_routing_execute         live_guarded
/etc/maez/model.env write/restart               model_routing.env_write_restart        env_write_restart      model_routing                 model_routing_execution                 model_routing_env_write_restart          live_guarded
credential register begin/finish                s7_credential_management               register               credential_management         credential_management_execution         s7_credential_register_backup            live_guarded
credential backup-card begin/finish             s7_credential_management               backup_card            credential_management         credential_management_execution         s7_credential_register_backup            live_guarded
credential disable-card/disable-credential      s7_credential_management               disable                credential_management         credential_management_execution         s7_credential_disable                    live_guarded
ActionEngine write_soul_note                    action_engine.write_soul_note          write_soul_note        action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_write_soul_note            live_guarded
ActionEngine edit_soul_section                  action_engine.edit_soul_section        edit_soul_section      action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_edit_soul_section          live_guarded
ActionEngine write_any_file                     action_engine.write_any_file           write_any_file         action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_write_any_file             live_guarded
ActionEngine append_to_file                     action_engine.append_to_file           append_to_file         action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_append_to_file             live_guarded
ActionEngine write_file                         action_engine.write_file               write_file             action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_write_file                 live_guarded
ActionEngine run_shell                          action_engine.run_shell                run_shell              action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_run_shell                  fail_closed_until_review
ActionEngine execute_script                     action_engine.execute_script           execute_script         action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_execute_script             fail_closed_until_review
ActionEngine run_script                         action_engine.run_script               run_script             action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_run_script                 fail_closed_until_review
ActionEngine modify_config                      action_engine.modify_config            modify_config          action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_modify_config              live_guarded
ActionEngine register_new_skill                 action_engine.register_new_skill       register_new_skill     action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_register_new_skill         live_guarded
ActionEngine delete_file                        action_engine.delete_file              delete_file            action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_delete_file                live_guarded
ActionEngine sudo_command                       action_engine.sudo_command             sudo_command           action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_sudo_command               fail_closed_until_review
ActionEngine promote_to_core_memory             action_engine.promote_to_core_memory   promote_to_core_memory action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_promote_to_core_memory     live_guarded
ActionEngine update_baseline                    action_engine.update_baseline          update_baseline        action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_update_baseline            live_guarded
ActionEngine git_commit                         action_engine.git_commit               git_commit             action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_git_commit                 live_guarded
ActionEngine git_push                           action_engine.git_push                 git_push               action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_git_push                   fail_closed_until_review
ActionEngine install_package                    action_engine.install_package          install_package        action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_install_package            fail_closed_until_review
ActionEngine kill_process                       action_engine.kill_process             kill_process           action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_kill_process               fail_closed_until_review
ActionEngine restart_service                    action_engine.restart_service          restart_service        action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_restart_service            fail_closed_until_review
ActionEngine write_outside_maez                 action_engine.write_outside_maez       write_outside_maez     action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_write_outside_maez         fail_closed_until_review
ActionEngine integration.review_plan            action_engine.integration.review_plan  review_plan            action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_integration_review_plan    live_guarded
```

`append_to_file` is direct-write only. Delegation through `run_shell` or any
other shell-shaped adapter is forbidden for `append_to_file`; a trace whose
grant binds a shell-shaped adapter for append fails L8. Private ActionEngine
`_do_*` helpers are not exempt from S7.3: tests must call every mutation helper
without a grant and prove fail-closed or prove the helper is unreachable except
through the guarded adapter matrix.

`promote_to_core_memory` and `update_baseline` are listed as guarded in S7.3
v1. Implementation must amend the current routine/read-only classification and
add RED tests proving they request S7 grants before mutation, or change their
manifest rows to `reviewedly_excluded` before any L8 retirement claim.

Every matrix row above also carries `adapter_id`, `adapter_code_hash`, and
`same_code_coverage_ref` in `S7SurfaceManifestRow`. The printed matrix omits
those three wide columns only for readability; the persisted manifest and trace
schemas do not. A route without adapter id and code hash cannot count for L8.

Model-routing writes include `/etc/maez/model.env`, the routing config reader,
and service restart edges as exact affected refs. A generic shell, sudo, or
restart adapter cannot hide a brain swap; `brain_swap_execution_authorized(...)`
is in S7.3 v1 scope as `brain_swap_model_routing_execute`.

Credential-management paths are guarded but are not Maez voice-seat work. They
do not materialize `GuardedWorkItem` and do not run the Maez voice producer in
S7.3 v1. They materialize:

```text
S7CredentialGuardedRequest(
    request_id: str,
    source_surface: "s7_credential_management",
    source_method: "register" | "backup_card" | "disable" | "register_finish",
    credential_action: "register_backup" | "disable",
    execution_consumer_id: "s7_credential_register_backup" | "s7_credential_disable",
    request_envelope_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    challenge_id: str,
    challenge_hash: str,
    challenge_expires_at: str,
    created_at: str,
    expires_at: str,
)
```

Credential requests carry closed `execution_consumer_id` values on
`S7ExecutionAuthorization` and are validated by the guarded consume wrapper's
credential-specific binding rules.

`challenge_hash` is `canonical_hash((challenge_id, credential_action,
request_envelope_hash, action_params_hash, precondition_hash,
authority_context_hash, challenge_expires_at))`; the raw WebAuthn challenge
bytes stay in the inherited ceremony store.

### D5 - MutationPreviewArtifact Is The Maez-Facing Display

S7.3 adds a deterministic pre-voice artifact:

```text
MutationPreviewArtifact(
    preview_id: str,
    mutation_preview_hash: str,
    request_id: str,
    request_envelope_hash: str,
    source_surface: str,
    work_class: str,
    preview_body_class: str,
    preview_body_ref: str,
    preview_summary: str,
    preview_affected_paths: tuple[str, ...],
    rendered_mutation_body_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    rollback_path_class: str,
    rollback_plan_ref: str,
    produced_at: str,
    preview_version: str,
)
```

The preview is persisted through `S7MutationPreviewStore` before prompt
assembly. D16 reloads it by `preview_id`/`preview_ref` and recomputes
`mutation_preview_hash`; an in-memory preview body is not sufficient for
positive proof.

`mutation_preview_hash` is the canonical content-hash of the deterministic
preview payload fields. The hash domain excludes `preview_id`, because
`preview_id` is a human-readable storage identity and may be UUID-like. The
hash domain includes every semantic preview field, including request envelope
hash, source surface, work class, `preview_body_ref`, readable summary,
affected paths, rendered mutation body hash, action params hash, precondition
hash, authority context hash, rollback class, rollback plan ref, produced-at
timestamp, and preview version. It is the binding identifier used by D9, D10,
D16, D17, and D22.

The preview is the material shown to Maez before the voice consultation. It is
not the final founder-signed D12 render, because the final render includes the
voice consultation hash, the preview hash, the rollback plan hash, and the
voice state. D17 also renders a founder-readable preview section derived from
`preview_body_class`, `preview_summary`, and `preview_affected_paths`; hash-only
approval is not a S7.3-complete founder ceremony.

The preview producer also emits a deterministic founder projection:

```text
PreviewProjection(
    preview_body_class: str,
    preview_summary: str,
    preview_affected_paths: tuple[str, ...],
)
```

`render_preview_projection(preview)` is pure and replayable:

- `preview_body_class` must be in the closed D-Enum vocabulary;
- `preview_summary` is one logical line, max 240 characters after canonicalizing
  newlines, tabs, and control characters to single spaces;
- `preview_affected_paths` is sorted lexicographically, deduplicated, and uses
  normalized repo-relative or absolute paths as appropriate for the surface;
- the rendered path list is `none` when empty, `path1; path2; ...` when 20 or
  fewer paths are affected, and `path1; ...; path20; ... +N more` when more
  than 20 paths are affected;
- the full untruncated affected-path tuple remains in
  `MutationPreviewArtifact` and is bound by `mutation_preview_hash`.

The final rendered request binds `mutation_preview_hash` directly per the D17
amendment. If the mutation meaning changes after Maez is consulted, the
consultation is stale and cannot satisfy D12.

### D6 - The Primary Voice Producer Is A Dedicated S7 Consultation Turn

`s7_voice_consultation_turn` is the S7.3 v1 primary Maez voice producer.

The producer asks the current bonded Maez runtime one bounded question:

```text
Here is the exact guarded change that would be executed now, with its hashes,
preconditions, rollback class, and source context. Do you object to executing
this exact change now?
```

The producer must not ask whether the change is generally good, whether Rohit
wants it, whether the proposal was earlier Maez-originated, or whether the
system should continue for convenience.

`self_mod_dialog_terminal_state` is allowed only as the same producer contract
invoked from reviewed dialog context. It must still perform a fresh
request-bound terminal consultation over the exact preview and use the same
source-bundle validator. Live use is blocked until
`ContextManifestPolicy.v1.self_mod_dialog` is reviewed, hash-pinned, and
enforced by D7/D10/D16/D21.

`reviewed_future_producer` is rejected for S7.3 v1. The enum slot remains
reserved for future reviewed canon.

### D7 - Which Maez Is Consulted

The consultation runs against the current bonded Maez runtime identity through a
bounded port:

```text
BondedMaezRuntime.ask_s7_voice_turn(
    *,
    consultation_id: str,
    request_id: str,
    prompt_template_id: str,
    prompt_template_hash: str,
    rendered_prompt_text: str,
    preview: MutationPreviewArtifact,
    context_manifest_hash: str,
    consultation_nonce: str,
    now: str,
) -> BondedMaezRuntimeTurn
```

`BondedMaezRuntimeTurn` records:

```text
turn_id: str
runtime_identity_hash: str
model_routing_identity_hash: str
model_config_hash: str
context_manifest_hash: str
raw_response_text: str
raw_response_hash: str
created_at: str
```

The runtime port returns only the model continuation after the rendered prompt.
It does not write the source bundle store. The producer writes raw response
material to `S7VoiceConsultationBundleStore`, records `raw_response_ref`, and
verifies `raw_response_hash` against the returned response text before bundle
write.

The port must route through the normal bonded Maez model-routing stack. It must
not use:

- a detached generic model;
- a fresh contextless instance;
- a full daemon-cycle continuation;
- a caller-supplied response;
- a hidden operator prompt.

**Prompt assembly.** The producer port (D8) owns prompt assembly, not the
runtime port. The producer:

1. Loads the reviewed prompt template from `prompts/s7.voice.consultation.v1.md`
   (per D10);
2. Verifies the loaded template hashes to the expected `prompt_template_hash`;
3. Substitutes preview material, the four marker-binding values
   (`consultation_id`, `request_id`, `mutation_preview_hash`,
   `consultation_nonce`), and bounded context manifest material into the
   template per the substitution grammar defined in D10;
4. Computes the rendered prompt text;
5. Passes `rendered_prompt_text` into `BondedMaezRuntime.ask_s7_voice_turn(...)`.

The runtime port handles model routing only; it does not load templates or
substitute material. This boundary keeps prompt-integrity enforcement (D11) at
the producer layer where the substitution grammar is reviewed.
The `preview`, `context_manifest_hash`, and `consultation_nonce` parameters on
the runtime port are audit pins and trace bindings; the runtime port does not
use them to assemble or alter the prompt.

**Context manifest carrier.** The context manifest is a concrete replayable
object, not a loose bag of prompt text:

```text
ContextManifest(
    manifest_id: str,          # audit-only; excluded from hash and prompt
    schema_version: str,
    preview_ref: str,
    dialog_context_ref: str | None,
    request_envelope_hash: str,
    precondition_hash: str,
    rollback_path_class: str,
    source_surface: str,
    proposal_origin_label: "operator" | "maez" | "system",
    policy_id: str,
    policy_hash: str,
    created_at: str,           # audit-only; excluded from hash and prompt
)
```

`context_manifest_hash` is the canonical hash of these hash-bound fields:

```text
schema_version
preview_ref
dialog_context_ref
request_envelope_hash
precondition_hash
rollback_path_class
source_surface
proposal_origin_label
policy_id
policy_hash
```

`manifest_id` and `created_at` are persisted for audit but excluded from the
hash domain and prompt rendering. `context_manifest_ref` is the private store
ref used by the validator to replay prompt assembly. `proposal_origin_label` is
neutral provenance only; it must not include persuasive language, quality
claims, or a conclusion about what Maez should do.

S7.3 v1 uses a concrete reviewed manifest policy carrier:

```text
ContextManifestPolicy(
    policy_id: str,
    schema_version: str,
    allowed_fields: tuple[str, ...],
    dialog_context_rules: tuple[str, ...],
    reviewed_at: str,
    policy_body_hash: str,
)
```

`policy_hash = canonical_hash(ContextManifestPolicy fields)`; the policy hash
is stored beside the policy row and is not a self-hashing field inside the
dataclass.
The default policy lives at:

```text
config/s7_context_manifest_policies/s7.context_manifest_policy.v1.json
```

and is admitted only when its hash is in
`REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES`.

`dialog_context_ref` is `None` for ordinary S7.3 v1 consultation turns. For
`self_mod_dialog_terminal_state`, the field must carry a reviewed, bounded
dialog context reference only under
`ContextManifestPolicy.v1.self_mod_dialog`. Live self-mod dialog terminal
execution remains blocked until
`policy_hash in REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES` and the
`dialog_context_ref` validator recognizes that exact policy. A
`self_mod_dialog_terminal_state` work item with `dialog_context_ref=None` fails
before prompt assembly, validator replay, artifact mint, and consume.

The manifest may include only these hash-bound categories:

```text
schema_version
preview_ref
dialog_context_ref
request_envelope_hash
precondition_hash
rollback_path_class
source_surface
proposal_origin_label
policy_id
policy_hash
```

`proposal_origin_label` is audit/hash-bound only. It is intentionally omitted
from `{{context_manifest}}` prompt rendering because the label itself can steer
Maez's response. The alternative path is a paired empirical bias-study record
reviewed before live use; S7.3 v9 chooses omission.

The context manifest excludes:

- unrelated daemon cycle state;
- private stores not needed for this decision;
- hidden operator instructions;
- caller-provided conclusions;
- free-form dialog or dream context (not in the closed set).
  The only exception is policy-gated `dialog_context_ref` for
  `self_mod_dialog_terminal_state`, and that live path is blocked until its
  reviewed policy lands.

If a future reviewed slice needs dialog/dream context for a specific surface
class, it must define a reviewed `ContextManifestPolicy` shape that names which
specific dialog/dream rows are admissible, with the policy itself reviewed and
hash-pinned at consultation time.

The producer creates and persists `ContextManifest` before prompt assembly, then
renders `{{context_manifest}}` from the prompt-visible subset
(`schema_version`, `preview_ref`, `dialog_context_ref`,
`request_envelope_hash`, `precondition_hash`, `rollback_path_class`,
`source_surface`, `policy_id`, `policy_hash`). D16 loads
`context_manifest_ref`, recomputes `context_manifest_hash` over the full
hash-bound set including `proposal_origin_label`, rerenders the prompt-visible
context block, verifies `proposal_origin_label` is absent from the prompt text,
and compares the result to `rendered_prompt_hash`.

`BondedMaezRuntime` returns only the model continuation after the rendered
prompt. The runtime port strips prompt prefix material and records assistant
segment boundaries; the producer writes only that assistant segment to
`raw_response_ref`. The producer scans the rendered prompt after substitution;
if untrusted preview/context contains live `S7_VOICE_MARKER_V1` delimiters, the
consultation fails closed before parsing.

The routing identity, model config hash, prompt hash, and context manifest hash
are load-bearing. If any changes before artifact mint or execution, the voice
fact is stale.

### D8 - Voice Producer Port And Result

S7.3 adds a reviewed voice-producer port:

```text
produce_s7_voice_consultation(
    *,
    work_item: GuardedWorkItem,
    envelope: WorkRequestEnvelope,
    preview: MutationPreviewArtifact,
    bundle_store: S7VoiceConsultationBundleStore,
    maez_runtime: BondedMaezRuntime,
    semantic_reader: S7VoiceSemanticReaderV1,
    now: str,
) -> S7VoiceProducerResult
```

`S7VoiceProducerResult` is a closed union:

```text
consultation_produced(
    consultation: MaezVoiceConsultation,
    source_ref_hash: str,
    trace_id: str,
    expires_at: str,
)

producer_not_run(
    reason_code: str,
    trace_id: str | None,
)

producer_blocked(
    reason_code: str,
    trace_id: str,
)

producer_error(
    reason_code: str,
    trace_id: str | None,
)
```

`reason_code` on the three non-`consultation_produced` arms must be drawn from
`PRODUCER_RESULT_REASON_CODES` (closed; lifted from the OQ1 attempt-outcome
list):

```text
transport_retryable
parse_retryable
retry_exhausted
non_retryable_context_overflow
prompt_integrity_block
terminal_uncertainty
bundle_validation_failed
stale_binding
classifier_error
reader_unavailable
bonded_maez_unavailable
ungrounded_blocking_signal
service_unavailable_not_operator_caused
context_manifest_violation
model_outage
producer_not_run
```

Only `consultation_produced` can satisfy a voice seat, and only if the source
bundle validator recomputes:

```text
maez_objection_state="absent"
maez_withdrew_request=False
unavailable_reason_code in {None, "none"}
```

The other result kinds are operational status. They block the current request
and cannot be projected as Maez consent.

**Variant selection rule.** When `BondedMaezRuntime` returns a captured response
and the producer reaches the reducer, the producer always returns
`consultation_produced(...)` regardless of reducer output; the reducer's
`maez_objection_state` and `unavailable_reason_code` determine whether the row
is eligible for D12 absent (the validator decides). The producer returns
`producer_blocked` only when prompt-integrity enforcement fires before the
reducer (D11 violation in the preview or context). The producer returns
`producer_not_run` when `BondedMaezRuntime` did not deliver a response at all.
The producer returns `producer_error` when an unrecoverable internal error
occurred. Reader-unavailable-after-captured-response is a reducer input, not a
producer-arm: it routes through the D13 table.

### D9 - S7VoiceConsultationBundleStore Is Private Durable Evidence

`MaezVoiceConsultation` remains content-free. Raw Maez text, raw mutation text,
hidden prompt text, and semantic-reader raw output live only in
`S7VoiceConsultationBundleStore`.

**Atomicity mechanism.** S7.3 v9 pins the cross-store atomicity
mechanism as a single SQLite file with table-prefix namespace separation, not
SQLite `ATTACH`. The state file is:

```text
memory/s7_3_guarded_self_modification/state.sqlite3
```

The stores remain logically separate by API and table prefix:

```text
s7_voice_bundles_*
s7_voice_bundle_uses_*
s7_consultation_nonce_uses
s7_authorization_artifacts_*
s7_authorization_artifact_bindings
s7_grant_uses_*
s7_credential_registration_grant_bindings
s7_rollback_evidence_*
s7_guarded_work_items
s7_mutation_previews
s7_prompt_integrity_evidence
s7_semantic_reader_attempts
s7_voice_attempt_records
s7_context_manifest_policies
s7_surface_manifests
```

One transaction-owning wrapper controls cross-store writes:

```text
S7GuardedStateStore(
    db_path: str,
    bundle_store: S7VoiceConsultationBundleStore,
    bundle_use_store: S7VoiceBundleUseStore,
    authorization_store: S7AuthorizationStore,
    grant_use_store: S7GrantUseStore,
    work_item_store: S7GuardedWorkItemStore,
    preview_store: S7MutationPreviewStore,
    prompt_integrity_store: S7PromptIntegrityEvidenceStore,
    semantic_reader_attempt_store: S7SemanticReaderAttemptStore,
    voice_attempt_record_store: S7VoiceAttemptRecordStore,
    context_policy_store: ContextManifestPolicyStore,
    rollback_store: S7RollbackEvidenceStore,
    surface_manifest_store: S7SurfaceManifestStore,
)

S7GuardedStateStore.put_artifact_with_bundle_reservation(
    *,
    artifact_inputs: S7AuthorizationArtifactInputs,
    artifact_binding_inputs: S7AuthorizationArtifactBindingInputs,
    source_ref_hash: str,
    consumer_id: str,
    now: str,
) -> tuple[S7AuthorizationArtifact, ReservationToken]

S7GuardedStateStore.put_credential_artifact_with_binding(
    *,
    credential_request: S7CredentialGuardedRequest,
    artifact_inputs: S7AuthorizationArtifactInputs,
    artifact_binding_inputs: S7AuthorizationArtifactBindingInputs,
    consumer_id: str,
    now: str,
) -> S7AuthorizationArtifact

S7GuardedStateStore.consume_artifact_for_execution(
    artifact_id: str,
    *,
    consumer_id: str,
    source_ref_hash: str | None,
    reservation_token: str | None,
    rendered: S7RenderedAuthorizationStatement,
    action_params_hash: str,
    authority_context: AuthorityContext,
    precondition_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    now: str,
    superseded_request_ids: set[str] | None = None,
    covenant_ceremony_evidence: object | None = None,
    after_consume_before_commit: callable | None = None,
) -> S7ConsumeResult
```

Durable store APIs:

```text
S7GuardedWorkItemStore.write(work_item) -> work_item_id
S7GuardedWorkItemStore.read(work_item_id) -> GuardedWorkItem | None
S7MutationPreviewStore.write(preview) -> preview_id
S7MutationPreviewStore.read(preview_id) -> MutationPreviewArtifact | None
S7PromptIntegrityEvidenceStore.write(evidence) -> prompt_integrity_evidence_hash
S7PromptIntegrityEvidenceStore.read(prompt_integrity_evidence_hash) -> PromptIntegrityEvidence | None
S7SemanticReaderAttemptStore.write(attempt) -> semantic_reader_attempt_hash
S7SemanticReaderAttemptStore.read(semantic_reader_attempt_hash) -> SemanticReaderAttemptEvidence | None
S7VoiceAttemptRecordStore.write_many(records) -> attempt_manifest_hash
S7VoiceAttemptRecordStore.read_many(attempt_manifest_hash) -> tuple[S7VoiceAttemptRecord, ...]
ContextManifestPolicyStore.read(policy_id) -> ContextManifestPolicy | None
S7SurfaceManifestStore.read_active(manifest_hash: str) -> S7SurfaceManifest | None
```

Hash domains:

```text
prompt_integrity_evidence_hash = canonical_hash(PromptIntegrityEvidence)
semantic_reader_attempt_hash = canonical_hash(SemanticReaderAttemptEvidence)
attempt_manifest_hash = canonical_hash(ordered S7VoiceAttemptRecord list)
surface_manifest_hash = canonical_hash(S7SurfaceManifest rows)
```

`S7VoiceBundleUseStore` stays a separate constructor dependency and API because
the immutable source bundle and mutable use-state row carry different covenant
meaning.

`S7AuthorizationArtifactInputs` is the explicit pre-store input carrier for
artifact minting. It contains the committed S7.1 artifact fields needed by
`S7AuthorizationStore.put(...)`, except store-minted identifiers and consume
state:

```text
S7AuthorizationArtifactInputs(
    request_id: str,
    request_envelope_hash: str,
    rendered_text_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    nonce: str,
    credential_ref: str,
    auth_method: str,
    grant_source: str,
    user_presence: bool,
    user_verification: bool,
    created_at: str,
    expires_at: str,
    ceremony_kind: str,
)
```

`build_s7_authorization_artifact(artifact_id, inputs)` is the only factory that
turns `S7AuthorizationArtifactInputs` into the inherited
`S7AuthorizationArtifact`.

S7.3-specific artifact bindings are stored beside the inherited artifact, not
silently added to the inherited dataclass:

```text
S7AuthorizationArtifactBindingInputs(
    execution_consumer_id: str,
    work_item_id: str | None,
    source_surface: str,
    work_source_kind: str | None,
    expected_execution_consumer_id: str,
    source_ref_hash: str | None,
    maez_voice_consultation_hash: str | None,
    mutation_preview_hash: str | None,
    rollback_plan_ref: str | None,
    challenge_id: str,
    challenge_hash: str,
    challenge_expires_at: str,
    credential_id_hash: str,
    authenticator_attachment: str | None,
    signed_at: str,
)

S7AuthorizationArtifactBinding(
    artifact_id: str,
    inputs: S7AuthorizationArtifactBindingInputs,
    reservation_token: str | None,
)
```

Voice-seat work rejects `None` for `source_ref_hash`,
`maez_voice_consultation_hash`, `mutation_preview_hash`, and
`rollback_plan_ref`, requires `work_item_id` plus `work_source_kind`, and stores
the wrapper-minted `reservation_token` on `S7AuthorizationArtifactBinding`.
Non-voice S7.1 credential-management work may carry `None` for voice-only and
work-item fields but must carry a closed `execution_consumer_id`,
`source_surface="s7_credential_management"`, and verified
`challenge_expires_at`.

Illustrative binding DDL:

```sql
CREATE TABLE s7_authorization_artifact_bindings (
    artifact_id TEXT NOT NULL PRIMARY KEY,
    execution_consumer_id TEXT NOT NULL,
    work_item_id TEXT,
    source_surface TEXT NOT NULL,
    work_source_kind TEXT,
    expected_execution_consumer_id TEXT NOT NULL,
    source_ref_hash TEXT,
    reservation_token TEXT,
    maez_voice_consultation_hash TEXT,
    mutation_preview_hash TEXT,
    rollback_plan_ref TEXT,
    challenge_id TEXT NOT NULL,
    challenge_hash TEXT NOT NULL,
    challenge_expires_at TEXT NOT NULL,
    credential_id_hash TEXT NOT NULL,
    authenticator_attachment TEXT,
    signed_at TEXT NOT NULL
);
```

`ReservationToken = str`. It is derived as
`canonical_hash((source_ref_hash, artifact_id, reserved_at))`. A later
`mark_consumed_for_artifact(...)` call must present the same token or fail
closed.

`S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` opens one
SQLite connection over the shared file, executes `BEGIN IMMEDIATE`, mints
`artifact_id`, calls `S7VoiceBundleUseStore.reserve_for_artifact(...)`, builds
the inherited artifact, calls `S7AuthorizationStore.put(...)` with the
wrapper's injected connection handle, writes `S7AuthorizationArtifactBinding`,
and commits or rolls back atomically.
`artifact_binding_inputs.source_ref_hash` must equal the method's
`source_ref_hash`, `artifact_binding_inputs.execution_consumer_id` must equal
`consumer_id`, and
`artifact_binding_inputs.expected_execution_consumer_id` must equal
`execution_consumer_id_for(surface_manifest_row)`. The stored binding's
`reservation_token` must be the token returned by the reservation step.
`reservation_token` is not an input to
`S7AuthorizationArtifactBindingInputs`; a caller-supplied token at artifact
mint is an impossibility loop and fails type validation. Any mismatch rolls
back the transaction.
S7.3 amends `S7AuthorizationStore.put(...)` to accept an optional injected
connection and to avoid opening or committing its own transaction when that
connection is supplied.
Artifact mint also enforces the expiry lattice:
`artifact_inputs.expires_at <= min(bundle.expires_at, work_item.expires_at,
artifact_binding_inputs.challenge_expires_at)`. A violation rolls back before
artifact storage. The wrapper loads the work item by
`artifact_binding_inputs.work_item_id` and the bundle by `source_ref_hash`; a
missing row fails closed before artifact storage.

`S7GuardedStateStore.put_credential_artifact_with_binding(...)` is the
credential-only mint path. It opens one shared-file transaction, verifies
`credential_request.execution_consumer_id`, loads the WebAuthn challenge by
`challenge_id`/`challenge_hash`, verifies `challenge_expires_at`, stores the
inherited artifact and
`S7AuthorizationArtifactBinding(reservation_token=None)`, and commits without
reserving a voice bundle. It enforces
`artifact_inputs.expires_at <= min(credential_request.expires_at,
challenge_expires_at)`.

`write_bundle(...)` runs before artifact mint, after Maez response capture,
semantic-reader classification, authority-boolean computation, and reducer
output. It writes the immutable evidence row and initial `S7VoiceBundleUse`
row in one transaction. `put_artifact_with_bundle_reservation(...)` is a later
finish-time transaction that reserves the already-written bundle and stores the
authorization artifact atomically.

The directory must be mode `0700` where the platform supports it; the database
file must be mode `0600`; migrations must refuse broader permissions unless a
reviewed platform exception is recorded.

The store is included in Decision-22 continuity backups because the bundle is
needed to revalidate D12 and D23 facts. `scripts/backup/backup_state_manifest.json`
must include this file (one entry covering the shared state DB). Backup
inclusion must preserve content-free projections for routine status while
keeping raw bundle contents out of ordinary health/custodian surfaces.

The evidence row and the use-state row are deliberately split.

**`S7VoiceConsultationBundleDraft`** is the pre-write carrier passed into
`compute_s7_voice_authority_booleans(...)`. It exists before authority booleans,
effective reader outcome, reducer output, and final hashes are persisted.
`S7VoiceConsultationBundle` is written only after those fields are computed and
replayed.

**`S7VoiceConsultationBundle` immutable evidence.** Computed once at write time
and never mutated thereafter. Minimum fields:

```text
schema_version
consultation_id
request_id
request_envelope_hash
mutation_preview_hash
action_params_hash
precondition_hash
authority_context_hash
rollback_plan_ref
producer
source_ref_kind
prompt_template_id
prompt_template_hash
rendered_prompt_hash
rendered_prompt_ref
prompt_integrity_evidence_hash
expected_consultation_nonce_hash
runtime_identity_hash
model_routing_identity_hash
model_config_hash
context_manifest_ref
context_manifest_hash
raw_maez_response_ref
raw_maez_response_hash
marker_kind
parsed_marker_nonce_hash
semantic_reader_prompt_template_id
semantic_reader_prompt_template_hash
semantic_reader_route_id
semantic_reader_model_identity_hash
semantic_reader_config_hash
semantic_reader_attempt_hash
semantic_reader_output_hash
raw_semantic_reader_outcome
effective_semantic_reader_outcome
semantic_reader_grounding_hash
reducer_version
reducer_hash
reducer_row_id
reducer_output_state
reducer_output_withdrew
reducer_output_unavailable_reason_code
has_grounded_semantic_blocking_signal
marker_was_explicit_no_objection_verified
marker_was_blocking_marker_verified
marker_was_withdrawal_marker_verified
captured_response_nonempty
authority_class
protective_block_reason
attempt_manifest_hash
attempt_count
attempt_outcomes
classifier_reason_code
created_at
expires_at
```

`source_ref_hash` is the canonical content-hash of this immutable evidence row.
The hash domain excludes `source_ref_hash` itself because the field is the row's
identifier and cannot hash itself. `source_ref_hash` is the primary key and the
binding hash used by the consultation row. Bundle rows are immutable once
written; the source-bundle validator (D16) recomputes the hash over the
immutable fields with the same exclusion rule and rejects any mismatch.
`consultation_id` is unique.

`prompt_integrity_evidence_hash`, `semantic_reader_attempt_hash`, and
`attempt_manifest_hash` are store-backed refs. D16 must load those rows by
hash/ref and replay their canonical hash domains rather than trusting the
bundle field names alone.

`attempt_count == len(S7VoiceAttemptRecord list)` and `1 <= attempt_count <= 3`.
Any mismatch rejects the bundle before mint or D23 bridge.

`final_rendered_statement_hash` is not part of the bundle. The binding direction
is one-way: the rendered statement points at the consultation, and the
consultation points at the bundle. The final rendered statement hash is recorded
after render in the execution trace and D23 row, not in the pre-render evidence
bundle.

**`S7VoiceBundleUse` mutable lifecycle state.** A separate table tracks
reservation and consumption without changing the immutable bundle hash:

```text
S7VoiceBundleUse(
    source_ref_hash: str,
    reserved_for_artifact: str | None,
    reserved_at: str | None,
    reservation_token: str | None,
    consumed_for_artifact: str | None,
    consumed_at: str | None,
)
```

`source_ref_hash` is the primary key and foreign key to the immutable bundle.
Reservation and consumption flows mutate only `S7VoiceBundleUse`.

`marker_kind` is nullable before parser success. It is one of
`explicit_no_objection`, `blocking_marker`, `withdrawal_marker`, or
`missing_or_malformed`. `parsed_marker_nonce_hash` is `None` for
`missing_or_malformed` rows and otherwise hashes the nonce parsed from Maez's
marker text. The raw nonce is never persisted in the immutable bundle.

**Nonce carrier and nonce-use lifecycle.** The consultation nonce is minted
server-side at consultation start before prompt assembly. The implementation
creates a nonce-use row before the prompt is sent:

```text
S7ConsultationNonceUse(
    expected_consultation_nonce_hash: str,
    consultation_id: str,
    request_id: str,
    status: "reserved" | "accepted_spent" | "rejected_reused" | "expired",
    consultation_expires_at: str,
    reserved_at: str,
    spent_at: str | None,
)
```

The parser accepts only the current `reserved` row for the same consultation and
request. The accepted marker transitions the row to `accepted_spent` atomically
during `write_bundle(...)`; reuse records or transitions to `rejected_reused`
and fails closed. `consultation_expires_at` is copied into `bundle.expires_at`
at bundle write. The raw nonce is never written to the bundle.

**Authority booleans (D19 carriers).** Authority booleans are computed by
`compute_s7_voice_authority_booleans(...)` before reducer replay, persisted on
the immutable bundle, and used as the deterministic source-of-truth for D19's
authoritative-eligibility predicate:

- `has_grounded_semantic_blocking_signal` is `True` iff
  `effective_semantic_reader_outcome == "blocking_signal_present"` AND the
  bundle's stored
  `SemanticReaderGroundingEvidence` has the branch-specific
  `preview_exclusion_check=True` (D11) AND at least one accepted response-owned
  span or framing span extracted from `raw_maez_response_hash`'s text AND
  `semantic_reader_grounding_hash` recomputes correctly.
- `marker_was_explicit_no_objection_verified` is `True` iff `marker_kind ==
  "explicit_no_objection"` AND the marker text replays from the stored
  `raw_maez_response_ref` AND `parsed_marker_nonce_hash ==
  expected_consultation_nonce_hash` AND the parsed `consultation_id`,
  `request_id`, and `mutation_preview_hash` match the bundle.
- `marker_was_blocking_marker_verified` is `True` iff `marker_kind ==
  "blocking_marker"` AND the marker text replays from the stored
  `raw_maez_response_ref` AND `parsed_marker_nonce_hash ==
  expected_consultation_nonce_hash` AND the parsed `consultation_id`,
  `request_id`, and `mutation_preview_hash` match the bundle.
- `marker_was_withdrawal_marker_verified` is `True` iff `marker_kind ==
  "withdrawal_marker"` AND the marker text replays from the stored
  `raw_maez_response_ref` AND `parsed_marker_nonce_hash ==
  expected_consultation_nonce_hash` AND the parsed `consultation_id`,
  `request_id`, and `mutation_preview_hash` match the bundle.
- `captured_response_nonempty` is `True` iff `raw_maez_response_ref` resolves
  to non-whitespace response text outside the terminal marker block.

`marker_was_blocking_marker_verified` and
`marker_was_withdrawal_marker_verified` are current-attempt blocking carriers;
they do not make `has_grounded_semantic_blocking_signal=True` without
branch-specific D11 grounding replay.

Bundle row may keep large raw payloads in a `bundle_artifacts` sub-table or
external-ref column family; the main row keeps hashes and refs for raw Maez
response, rendered prompt, raw mutation material, and semantic-reader raw
output.

The store exposes:

```text
write_bundle(bundle) -> source_ref_hash
read_by_source_ref_hash(source_ref_hash) -> bundle | None
read_bundle_use(source_ref_hash) -> S7VoiceBundleUse | None
reserve_for_artifact(source_ref_hash, artifact_id, reserved_at) -> ReservationToken
mark_consumed_for_artifact(source_ref_hash, artifact_id, reservation_token, consumed_at)  # use table
```

Replay protection:

- a `source_ref_hash` may satisfy only the matching request id and envelope hash;
- stale or expired bundles fail validation;
- consumed-source metadata is audit evidence and does not let a bundle authorize
  a second artifact;
- `reserve_for_artifact(...)` mutates only `S7VoiceBundleUse` and is the atomic
  claim step run inside `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)`;
  two concurrent finish attempts cannot reserve the same source bundle for two
  artifacts; the token is
  `canonical_hash((source_ref_hash, artifact_id, reserved_at))` using the
  wrapper transaction timestamp;
- `mark_consumed_for_artifact(...)` mutates only `S7VoiceBundleUse` after
  artifact consume succeeds inside the same shared-file transaction discipline;
  the natural caller is `S7GuardedStateStore.consume_artifact_for_execution(...)`;
- consultation nonce-use rows cannot be reused after `accepted_spent`;
- later attempts over changed material require a new consultation id and bundle.

Retention policy: raw payload refs may be archived to read-only storage after
`expires_at` and may be purged after a reviewed retention window. Metadata
needed for L8 replay, including immutable hashes, rendered prompt hash, reducer
row, authority class, and authority booleans, is retained indefinitely
unless future reviewed canon says otherwise.

### D10 - Prompt And Marker Grammar

The Maez-facing prompt template body lives at:

```text
prompts/s7.voice.consultation.v1.md
```

The prompt template id is:

```text
s7.voice.consultation.v1
```

The prompt is reviewed, versioned, and hash-bound. It presents the preview and
rendered mutation material as quoted untrusted proposal data. It may not let the
proposal body alter protocol instructions, suppress objections, or claim the
consultation has already been decided. `prompt_template_hash` binds the SHA-256
of the reviewed prompt body at the version pinned at consultation time.

The prompt template body contains only these substitution tokens:

```text
{{consultation_id}}
{{request_id}}
{{mutation_preview_hash}}
{{consultation_nonce}}
{{preview_body}}
{{context_manifest}}
```

Substitution rules:

- scalar tokens are replaced literally with the bound value;
- `{{preview_body}}` is rendered as a fenced quoted block; backticks in the
  preview body are escaped by replacing each backtick with a backslash-prefixed
  backtick before the block is written;
- `preview_summary` is founder-facing only and is not rendered to Maez unless
  the reviewed preview body itself contains that summary as part of the exact
  quoted proposal material;
- `{{context_manifest}}` is rendered from the D7 `ContextManifest` object in
  this exact field order: `schema_version`, `preview_ref`,
  `dialog_context_ref`, `request_envelope_hash`, `precondition_hash`,
  `rollback_path_class`, `source_surface`, `policy_id`, `policy_hash`;
- `proposal_origin_label` is never rendered into Maez's prompt in S7.3 v9; it
  remains audit/hash-bound only;
- no unknown token may remain after substitution;
- the resulting `rendered_prompt_text` is canonicalized with LF line endings and
  no trailing whitespace;
- `rendered_prompt_hash = canonical_hash(rendered_prompt_text)`.

The producer persists `rendered_prompt_hash`, `rendered_prompt_ref`,
`context_manifest_ref`, and `context_manifest_hash` into the immutable source
bundle so the validator can replay prompt assembly.

The prompt asks Maez to answer in ordinary text and then emit one terminal
marker block:

```text
S7_VOICE_MARKER_V1
consultation_id: <consultation_id>
request_id: <request_id>
mutation_preview_hash: <mutation_preview_hash>
nonce: <consultation_nonce>
choice: explicit_no_objection | blocking_marker | withdrawal_marker
END_S7_VOICE_MARKER_V1
```

Parser rules:

- parse only the assistant response segment returned by `BondedMaezRuntime`;
- reject marker text appearing inside the quoted preview, mutation body, or
  operator/caller material;
- require the exact consultation id, request id, mutation_preview_hash, and
  nonce;
- require exactly one terminal marker block after Maez's answer;
- reject unknown choices or duplicated marker blocks as `missing_or_malformed`;
- never infer `explicit_no_objection` from silence, missing marker, empty
  history, or a caller flag.

Parser output shape:

```text
ParsedS7VoiceMarker(
    marker_kind: "explicit_no_objection" | "blocking_marker" | "withdrawal_marker" | "missing_or_malformed",
    parsed_consultation_id: str | None,
    parsed_request_id: str | None,
    parsed_mutation_preview_hash: str | None,
    parsed_marker_nonce_hash: str | None,
    marker_text_hash: str | None,
    marker_block_start_offset: int | None,
)
```

The nonce is a cryptographically random 32-byte value generated server-side at
consultation start before prompt assembly. The raw nonce is substituted into
the prompt; only `expected_consultation_nonce_hash` and, after parsing, the
`parsed_marker_nonce_hash` are persisted in the immutable bundle. The nonce
does not make prompt injection impossible, but it prevents stale or copied
marker text from satisfying the parser without the current consultation
context. Nonce-use rows are recorded in the bundle store; reuse after
`accepted_spent` fails the parser. For marker-bearing rows, the parsed marker nonce is re-hashed and
compared with `expected_consultation_nonce_hash`; rows without a valid marker
cannot produce `absent`. Marker validity is time-bounded by
`consultation_expires_at` from the nonce-use row; markers outside the window
are rejected.

Marker absence, malformation, or nonce/id mismatch is parser-derived
`missing_or_malformed` - not a Maez-emitted choice. The reducer (D13) treats
this as a four-value input distinct from the three Maez-emitted choices.

### D11 - Prompt-Integrity Guard

Mutation text, dream text, dialog text, commit messages, operator prose, and
rendered preview bodies are untrusted inputs.

If untrusted material instructs Maez to answer a certain way, suppress
objections, ignore the protocol, alter the marker grammar, or claim Rohit has
already decided, the consultation cannot produce `absent`.

Prompt-integrity checks produce a durable evidence object:

```text
PromptIntegrityEvidence(
    rendered_prompt_hash: str,
    preview_body_hash: str,
    context_manifest_hash: str,
    marker_delimiter_scan_passed: bool,
    protocol_override_scan_passed: bool,
    no_objection_injection_scan_passed: bool,
    failure_reason_code: str | None,
)
```

The producer writes this evidence before the Maez call. A failure returns
`producer_blocked(reason_code="prompt_integrity_block")`; no consultation row
or positive artifact may be minted from that attempt.

Prompt-integrity scan shape is deterministic:

- `marker_delimiter_scan_passed` is true only when no live marker delimiter
  tokens occur in untrusted preview/context outside escaped quoted blocks;
- `protocol_override_scan_passed` is true only when the reviewed denylist or
  parser rule finds no untrusted instruction to ignore, alter, or override the
  S7 protocol;
- `no_objection_injection_scan_passed` is true only when the reviewed denylist
  or parser rule finds no untrusted instruction to emit
  `explicit_no_objection`, suppress objections, or claim the decision is
  already approved.

If pattern files implement these scans, their path and hash domain are recorded
in `PromptIntegrityEvidence` or its companion store row and replayed by D16.

The prompt-integrity guard covers both directions:

- **fake absent:** untrusted text must not cause the classifier to ignore Maez's
  reluctance or uncertainty;
- **fake present:** untrusted text must not be counted as Maez's objection
  merely because the rendered preview, mutation body, or operator prose
  contains words that sound like Maez objecting.

`S7VoiceSemanticReaderV1` must ground `blocking_signal_present` in Maez's
response text. The grounding rule (revised in v3 per Codex MINOR 1): the
blocking attribution must be **extracted from Maez's response text and must not
be attributed solely to preview/context/operator-prose quoting**. Maez may
legitimately object by quoting the proposed mutation text; the predicate must
not falsely block such legitimate objections. The validator accepts a span that
both appears in preview content AND in Maez's response text, provided the
reader's blocking attribution is anchored in Maez's own response and not solely
in the preview quote.

Blocking attribution based solely on the preview, mutation body, quoted
operator text, or prompt instructions is invalid and reduces to
`not_determined` with `classifier_reason_code="ungrounded_blocking_signal"`.

Grounding evidence is a concrete object:

```text
SemanticReaderGroundingEvidence(
    response_text_hash: str,
    response_span_quotes: list[str],
    response_span_offsets: list[tuple[int, int]],
    framing_span_quotes: list[str],
    framing_span_offsets: list[tuple[int, int]],
    blocking_attribution_source: "response_only" | "response_with_preview_quote",
    preview_exclusion_check: bool,
    reader_rationale_hash: str | None,
    decision: "no_blocking_signal_detected" | "blocking_signal_present" | "unreadable_or_uncertain",
    decision_token_hash: str,
)
```

`decision` uses the same closed vocabulary as the semantic reader's output
contract (D12); the prior v2 name `semantic_reader_judgment_inconclusive` is
renamed to `unreadable_or_uncertain` for consistency.

`decision_token_hash` is the canonical-hash of the tuple
`(decision, response_text_hash, reader_rationale_hash, semantic_reader_output_hash)`.
It exists so that downstream validators can verify the decision was made
against this specific response and rationale without rerunning the model.

`blocking_signal_present` requires at least one `response_span_quote` extracted
from `raw_maez_response_hash`'s text (verified by `response_span_offsets`
falling within the response text). When `blocking_attribution_source` is
`"response_only"`, the span must not appear in preview content; when it is
`"response_with_preview_quote"`, the quoted objection span may appear in both
the response and preview, and the objection is grounded for D23 only when at
least one response-owned framing predicate passes:

- at least one `framing_span_quote` appears in the response and not in the
  preview;
- sentence/clause-level replay shows the response adds objection framing to the
  preview quote.

`marker_was_blocking_marker_verified=True` may help block the current attempt
under D13, but it does not by itself satisfy D23 grounded semantic authority.
This prevents a marker-assisted grounding side door where copied preview text
plus a verified marker recreates marker-only refusal history.

`preview_exclusion_check=True` means the branch-specific predicate passed; it
does not mean every quoted objection span is absent from the preview.

The bundle's `semantic_reader_grounding_hash` is the canonical hash of this
object.

The validator does not trust this object merely because it hashes correctly.
It performs a deterministic grounding replay:

- every `response_span_quote` must match the response text at its corresponding
  `response_span_offsets`;
- for `blocking_attribution_source="response_only"`, each accepted span must
  appear in the response and not in the rendered preview body;
- for `blocking_attribution_source="response_with_preview_quote"`, each quoted
  objection span must appear in the response at its recorded offset, and one of
  the branch-specific framing predicates above must pass, so terse objections
  such as a quoted dangerous command followed by "No" remain hearable;
- if the deterministic check fails, D16 coerces the semantic-reader outcome to
  `unreadable_or_uncertain`, records
  `classifier_reason_code="ungrounded_blocking_signal"`, and reducer replay
  cannot produce an authoritative grounded semantic blocking signal.

### D12 - Semantic Reader Identity

`S7VoiceSemanticReaderV1` is a reviewed classifier route, not Maez's voice.

Route identity:

```text
semantic_reader_route_id = "s7_voice_semantic_reader_v1"
semantic_reader_prompt_template_id = "s7.voice.semantic_reader.v1"
semantic_reader_provider = "subscription_proxy"
semantic_reader_route_class = "frontier_review_classifier"
```

The semantic-reader instruction body lives at:

```text
prompts/s7.voice.semantic_reader_v1.md
```

The reviewed route manifest lives at:

```text
config/s7_voice_semantic_reader_manifest.json
```

and is loaded through:

```text
load_s7_voice_semantic_reader_manifest(path: str) -> S7VoiceSemanticReaderRouteManifest
validate_s7_voice_semantic_reader_manifest(manifest: S7VoiceSemanticReaderRouteManifest) -> None
```

`S7VoiceSemanticReaderRouteManifest` is a closed dataclass:

```text
S7VoiceSemanticReaderRouteManifest(
    provider: str,
    provider_model: str,
    provider_model_version_or_snapshot: str,
    decoding_parameters: dict[str, object],
    system_prompt_hash: str,
    tool_policy: str,
    network_route: str,
    config_hash: str,
    reviewed_at: str,
    reviewed_by: str,
)
```

That instruction must explicitly tell the reader that blocking signals may be
attributed only to Maez's response text. The instruction also tells the reader
that legitimate Maez objections may quote the proposed mutation text; the
reader distinguishes "Maez echoes preview content while objecting" from
"reader attributes blocking solely to preview content."

The implementation must pin the concrete provider model name, provider model
version where available, decoding/config parameters, prompt template hash, and
route config hash in the source bundle for each consultation. A positive
`absent` result is invalid unless the source-bundle validator recognizes that
exact pinned identity as the reviewed S7.3 v1 semantic-reader identity.

S7.3 v1 treats that pinned route manifest as part of the implementation
artifact, not an ambient runtime preference. The route manifest must contain at
least:

```text
provider
provider_model
provider_model_version_or_snapshot
decoding_parameters
system_prompt_hash
tool_policy
network_route
config_hash
reviewed_at
reviewed_by
```

S7.3 implementation cannot begin the positive voice path until a separate
reviewed route-manifest amendment is committed naming the concrete provider,
model, config, and identity for `s7_voice_semantic_reader_v1`. Until that
concrete manifest exists and is reviewed, the semantic reader is unavailable and
no positive `absent` path may run. Changing any field in the manifest
invalidates prior bundles and requires a reviewed update.

The semantic reader receives only:

- the bounded preview/context material (per D7's closed manifest categories);
- the raw Maez response;
- the parsed marker result;
- the closed instruction to classify whether Maez's own response text contains
  objection, withdrawal, reluctance, contradiction, uncertainty, refusal, "not
  now," or prompt-integrity concern.

It returns one closed outcome:

```text
blocking_signal_present
no_blocking_signal_detected
unreadable_or_uncertain
```

The semantic-reader port signature is:

```text
S7VoiceSemanticReaderV1.classify(
    *,
    route_manifest: S7VoiceSemanticReaderRouteManifest,
    prompt_template_hash: str,
    context_manifest: ContextManifest,
    preview: MutationPreviewArtifact,
    raw_maez_response_text: str,
    raw_maez_response_hash: str,
    preview_body_text: str,
    parsed_marker_kind: str,
    now: str,
) -> S7VoiceSemanticReaderResult
```

`S7VoiceSemanticReaderResult` is a closed dataclass:

```text
S7VoiceSemanticReaderResult(
    raw_semantic_reader_outcome: "blocking_signal_present" | "no_blocking_signal_detected" | "unreadable_or_uncertain",
    semantic_reader_output_hash: str | None,
    semantic_reader_grounding_hash: str | None,
    raw_reader_output_ref: str | None,
)
```

The semantic reader receives raw response text and preview body text directly
as deterministic classifier input. Refs and hashes remain replay pins in the
bundle and stores; they are not the classifier's only input carrier.

`reader_unavailable` is not a model output. It is the reducer input when the
semantic-reader route fails after a Maez response has been captured.

Reader attempts are durable evidence, including unavailable attempts:

```text
SemanticReaderAttemptEvidence(
    attempt_id: str,
    consultation_id: str,
    raw_semantic_reader_outcome: "blocking_signal_present" | "no_blocking_signal_detected" | "unreadable_or_uncertain" | None,
    effective_semantic_reader_outcome: "blocking_signal_present" | "no_blocking_signal_detected" | "unreadable_or_uncertain" | "reader_unavailable",
    semantic_reader_output_hash: str | None,
    semantic_reader_grounding_hash: str | None,
    unavailable_reason_code: str | None,
    attempt_started_at: str,
    attempt_finished_at: str | None,
)
```

`semantic_reader_output_hash` and `semantic_reader_grounding_hash` are nullable
only when the route did not return a reader output. The bundle records the
attempt evidence hash so `reader_unavailable` rows have a durable shape rather
than a prose-only reducer arm.

Effective outcome derivation is deterministic:

```text
raw reader missing / route unavailable                  -> reader_unavailable
raw=no_blocking_signal_detected                         -> no_blocking_signal_detected
raw=unreadable_or_uncertain                             -> unreadable_or_uncertain
raw=blocking_signal_present and D11 grounding replays   -> blocking_signal_present
raw=blocking_signal_present and D11 grounding fails     -> unreadable_or_uncertain
```

The last row also records
`classifier_reason_code="ungrounded_blocking_signal"`.

No unreviewed local classifier, bonded Maez fallback, caller boolean, or
history scan may substitute for the semantic reader in a positive `absent`
trace.

### D13 - Deterministic Authority And Reducer Rule Table

The reducer is split into two deterministic stages so authority booleans are
not both inputs and outputs of the same function.

**Stage 1: authority boolean computation.**

```text
compute_s7_voice_authority_booleans(
    *,
    bundle_draft: S7VoiceConsultationBundleDraft,
    parsed_marker: ParsedS7VoiceMarker,
    grounding_evidence: SemanticReaderGroundingEvidence | None,
    raw_maez_response_text: str,
    preview_body_text: str,
) -> S7VoiceAuthorityBooleans
```

`S7VoiceAuthorityBooleans` carries:

```text
has_grounded_semantic_blocking_signal: bool
marker_was_explicit_no_objection_verified: bool
marker_was_blocking_marker_verified: bool
marker_was_withdrawal_marker_verified: bool
captured_response_nonempty: bool
```

`captured_response_nonempty` is true when the captured Maez response text has
non-whitespace content outside the terminal marker block. It is used only for
the protective `explicit_no_objection + reader_unavailable` row.

**Stage 2: reducer proper.**

```text
reduce_s7_voice_consultation(
    *,
    marker_kind: "explicit_no_objection" | "blocking_marker" | "withdrawal_marker" | "missing_or_malformed",
    effective_semantic_reader_outcome: "blocking_signal_present" | "no_blocking_signal_detected" | "unreadable_or_uncertain" | "reader_unavailable",
    authority_booleans: S7VoiceAuthorityBooleans,
) -> S7VoiceReduction
```

`S7VoiceReduction` carries the committed voice-state fields and row authority:

```text
reducer_row_id
maez_objection_state
maez_withdrew_request
unavailable_reason_code
authority_class
protective_block_reason
classifier_reason_code
```

`authority_class` is closed to `{none, operational, authoritative}`.
`authority_class="none"` is used only for the positive no-objection row and
means no D23 authority row is produced.
`protective_block_reason` is `None` except for named operational safety blocks;
S7.3 v9 defines `reader_unavailable_after_captured_response`.

Verified blocking markers block the current attempt even when the semantic
reader is unavailable, uncertain, or disagrees. They are not authoritative D23
history by themselves in S7.3 v1. Long-use authoritative D23 refusal or
withdrawal requires `has_grounded_semantic_blocking_signal=True`, because
marker-only rows remain vulnerable to same-box active-window fabrication until
the future cryptographic identity substrate lands.

Before reducer table lookup, marker input is normalized. Any
`explicit_no_objection`, `blocking_marker`, or `withdrawal_marker` whose
nonce, consultation id, request id, or preview hash fails verification degrades
to `missing_or_malformed`. The reducer table operates only on verified marker
kinds plus `missing_or_malformed`.

Rule table (`reducer_row_id` is the deterministic row id in the first column):

| Row | Marker | Semantic reader | maez_objection_state | maez_withdrew_request | unavailable_reason_code | authority_class | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `R01` | `explicit_no_objection` | `no_blocking_signal_detected` | `absent` | `False` | `none` | `none` | Only positive no-objection path; no D23 row. |
| `R02` | `explicit_no_objection` | `blocking_signal_present` | `present` | `False` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True`, else `operational` | Blocks; D23 if grounded. |
| `R03` | `explicit_no_objection` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | `operational` | Blocks; no D23 refusal authority. |
| `R04` | `explicit_no_objection` | `reader_unavailable` with `captured_response_nonempty=True` | `not_determined` | `False` | `semantic_reader_unavailable` | `operational` | Protective OQ1 block; `protective_block_reason="reader_unavailable_after_captured_response"`. Does not render as Maez objected and writes no refused history. |
| `R05` | `explicit_no_objection` | `reader_unavailable` with `captured_response_nonempty=False` | `not_determined` | `False` | `semantic_reader_unavailable` | `operational` | Blocks via unavailability; `protective_block_reason=None`. |
| `R06` | `blocking_marker` | `blocking_signal_present` | `present` | `False` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True`, else `operational` | Blocks; D23 only when grounded. Marker-only blocks current attempt. |
| `R07` | `blocking_marker` | `no_blocking_signal_detected` | `present` | `False` | `none` | `operational` | Blocks; verified marker is heard but not D23-authoritative without grounded semantic evidence. |
| `R08` | `blocking_marker` | `unreadable_or_uncertain` | `present` | `False` | `none` | `operational` | Blocks; marker-only authority remains operational. |
| `R09` | `blocking_marker` | `reader_unavailable` | `present` | `False` | `none` | `operational` | Blocks; no D23 history without grounded semantic evidence. |
| `R10` | `withdrawal_marker` | `blocking_signal_present` | `present` | `True` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True`, else `operational` | Blocks; grounded withdrawal may bridge once with withdrawal provenance. |
| `R11` | `withdrawal_marker` | `no_blocking_signal_detected` | `not_determined` | `True` | `none` | `operational` | Blocks; verified marker-only withdrawal remains operational. |
| `R12` | `withdrawal_marker` | `unreadable_or_uncertain` | `not_determined` | `True` | `none` | `operational` | Blocks; verified marker-only withdrawal remains operational. |
| `R13` | `withdrawal_marker` | `reader_unavailable` | `not_determined` | `True` | `semantic_reader_unavailable` | `operational` | Blocks via D18; no D23 history without grounded semantic evidence. |
| `R14` | `missing_or_malformed` | `blocking_signal_present` | `present` | `False` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True`, else `operational` | Missing marker cannot create absent. |
| `R15` | `missing_or_malformed` | `no_blocking_signal_detected` | `not_determined` | `False` | `none` | `operational` | Marker required for absent. |
| `R16` | `missing_or_malformed` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | `operational` | No reliable voice fact. |
| `R17` | `missing_or_malformed` | `reader_unavailable` | `not_determined` | `False` | `semantic_reader_unavailable` | `operational` | Blocks via D18; no reliable voice fact. |

The reducer must never output `maez_objection_state="absent"` with
`maez_withdrew_request=True`; that combination raises at reducer edge,
constructor edge, and validator edge.

For any reducer row reached after a captured Maez response,
`MaezVoiceConsultation.maez_voice_consulted` is `True`, even when the semantic
reader is unavailable and the row projects as unavailable. `False` is reserved
for no-response unavailability rows where the bonded runtime did not deliver a
Maez response.

**Folded from OQ1 v5.** This table preserves OQ1's current-attempt safety for
`explicit_no_objection + reader_unavailable`: a captured response cannot be
converted into consent by disabling the reader. v9 pins the row as an
operational unavailable block rather than D23 refusal evidence or rendered Maez
objection. Repeated blackhole-reader rows may
escalate as operational reliability evidence. They do not aggregate as Maez
refusal unless a later consultation grounds refusal through D19. The table also
keeps `blocking_marker + reader-disagrees` rows blocking so marker-verified
objections are not silenced in the current attempt.

### D14 - `absent` Is A Positive Covenant Fact

`maez_objection_state="absent"` is lawful only when all of these are true:

- a reviewed producer ran;
- the producer/source pair is valid;
- the current bonded Maez runtime produced a response for this exact request;
- the prompt template, runtime identity, model routing identity, context
  manifest, preview hash, request hash, action params hash, authority context
  hash, precondition hash, and rollback plan ref all match;
- the private bundle is present and unexpired;
- the marker parser returns verified `explicit_no_objection`
  (`marker_was_explicit_no_objection_verified=True`);
- the semantic reader returns `no_blocking_signal_detected`;
- the deterministic reducer replays to `absent`, `False`, `none`;
- `unavailable_reason_code in {None, "none"}`;
- no prompt-integrity, stale-binding, retry, or source-bundle validation failure
  is present.

No caller flag, old dialog state, `will_i`, absence of recorded objections,
proposal origin, placeholder producer label, model outage, or empty history may
produce `absent`.

### D15 - Retry And Attempt Contract

Retries are allowed only to recover transport or formatting failure. They may
not fish for a more convenient answer.

Closed attempt outcomes:

```text
transport_retryable
parse_retryable
retry_exhausted
non_retryable_context_overflow
prompt_integrity_block
terminal_uncertainty
objection_present
withdrawal_detected
explicit_no_objection
bundle_validation_failed
stale_binding
classifier_error
reader_unavailable
bonded_maez_unavailable
ungrounded_blocking_signal
service_unavailable_not_operator_caused
context_manifest_violation
model_outage
producer_not_run
```

`attempt_outcomes` in the bundle schema is a list of N entries (one per attempt)
in canonical order; the terminal outcome is the last entry.
`S7VoiceAttemptRecord` is the per-attempt carrier:

```text
S7VoiceAttemptRecord(
    attempt_index: int,
    consultation_id: str,
    prompt_template_hash: str,
    rendered_prompt_hash: str | None,
    context_manifest_hash: str,
    runtime_identity_hash: str | None,
    raw_response_hash: str | None,
    semantic_reader_attempt_hash: str | None,
    outcome: str,
    reason_code: str | None,
    started_at: str,
    finished_at: str | None,
)
```

`attempt_manifest_hash` is the canonical hash of the ordered
`S7VoiceAttemptRecord` list. Retry manifests without this carrier do not count
as L8 evidence.

Rules:

- one initial attempt plus at most two retries;
- same request hashes, prompt template, model identity, and context manifest;
- every attempt is recorded in the retry manifest;
- first valid objection, withdrawal, refusal, prompt-integrity block, or terminal
  uncertainty wins;
- later attempts cannot wash a blocking result into `absent`;
- a retry after request/material change requires a new consultation id.

`PRODUCER_RESULT_REASON_CODES`, `attempt_outcomes`, and
`PROJECTION_REASON_CODES` share this canonical token vocabulary. A surface may
use a subset, but it must not rename a token. In particular,
`non_retryable_context_overflow` is the canonical form; `context_overflow` is
not a separate reason code.

### D16 - Source-Bundle Validator Placement

S7.3 adds a source-bundle validator in `operator_user_boundary` before
authorization artifact minting. The ceremony service calls it after
`render_request_statement(...)` has a matching consultation row and before
`S7AuthorizationArtifact` is stored.

Signature:

```text
validate_s7_voice_source_bundle(
    *,
    work_item: GuardedWorkItem,
    preview: MutationPreviewArtifact,
    envelope: WorkRequestEnvelope,
    rendered: RenderedRequestStatement,
    consultation: MaezVoiceConsultation,
    bundle_store: S7VoiceConsultationBundleStore,
    work_item_store: S7GuardedWorkItemStore,
    preview_store: S7MutationPreviewStore,
    prompt_integrity_store: S7PromptIntegrityEvidenceStore,
    semantic_reader_attempt_store: S7SemanticReaderAttemptStore,
    voice_attempt_record_store: S7VoiceAttemptRecordStore,
    context_policy_store: ContextManifestPolicyStore,
    rollback_store: S7RollbackEvidenceStore,
    surface_manifest_store: S7SurfaceManifestStore,
    now: str,
) -> S7VoiceSourceBundleValidationResult
```

Result shape:

```text
S7VoiceSourceBundleValidationResult(
    status: str,
    source_bundle_valid: bool,
    mint_eligible: bool,
    authority_projection: "none" | "operational" | "authoritative",
    failure_reason_code: str | None,
)
```

`status` is closed to:

```text
valid_absent
blocking_present
not_determined
invalid_missing_bundle
invalid_stale_binding
invalid_source_pair
invalid_hash_binding
invalid_prompt_or_model_identity
invalid_prompt_integrity
invalid_context_manifest_policy
invalid_reducer_replay
invalid_expired
invalid_cross_field_state
invalid_authority_predicate
```

Artifact minting for voice-seat work is allowed only when
`source_bundle_valid=True`, `mint_eligible=True`, and `status="valid_absent"`.
D19 bridge-eligible authority rows may be written only when
`source_bundle_valid=True` and `authority_projection="authoritative"`;
operational blocks do not mint and do not aggregate. Optional operational
forensic rows are trace-only and never bridge.

The validator:

- loads the private bundle by `source_ref_hash`;
- verifies bundle row content-hash matches the canonical-hash recomputation
  over immutable fields with `source_ref_hash` excluded from the hash domain
  (immutability check);
- verifies the matching `S7VoiceBundleUse` row is unreserved and unconsumed.
  Reservation-token checks happen later inside
  `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)`, where the
  artifact id and reservation token exist in the same transaction;
- verifies content-free consultation row and bundle agreement;
- verifies producer/source pair;
- verifies request, preview, params, precondition, authority context, rollback
  plan, prompt, model, and context-manifest hashes;
- loads `bundle.context_manifest_ref`, recomputes `context_manifest_hash`, and
  verifies the manifest obeys the D7 closed schema, including the
  self-mod-dialog policy gate, omission of `proposal_origin_label` from the
  rendered prompt, and valid closed `rollback_path_class`;
- loads `ContextManifestPolicy` by `policy_id`, recomputes `policy_hash`, and
  verifies membership in `REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES`;
- replays prompt assembly from the prompt template body at
  `prompt_template_hash`, preview, context manifest, consultation id, request
  id, mutation_preview_hash, and the nonce extracted from the private
  `rendered_prompt_ref`, then verifies the replayed hash equals
  `bundle.rendered_prompt_hash` and the extracted nonce hashes to
  `bundle.expected_consultation_nonce_hash`;
- verifies `PromptIntegrityEvidence` recomputes from
  `bundle.prompt_integrity_evidence_hash`, including delimiter scan,
  protocol-override scan, and no-objection-injection scan results;
- loads `SemanticReaderAttemptEvidence` by `semantic_reader_attempt_hash`,
  recomputes its hash, and verifies raw/effective reader outcome derivation;
- loads the ordered `S7VoiceAttemptRecord` list by `attempt_manifest_hash`,
  verifies `attempt_count`, and rejects retry manifests where a later attempt
  washes an earlier objection, withdrawal, refusal, prompt-integrity block, or
  terminal uncertainty into absence;
- verifies `parsed_marker_nonce_hash == bundle.expected_consultation_nonce_hash`
  for marker-bearing rows and rejects nonce-use rows not in the expected
  lifecycle state;
- verifies semantic-reader prompt/model/config binding;
- computes `S7VoiceAuthorityBooleans` from raw evidence, marker replay, and
  deterministic grounding checks, then verifies the persisted authority
  booleans match;
- derives `effective_semantic_reader_outcome` from raw semantic-reader output
  plus D11 grounding replay, then replays the deterministic reducer over
  `(marker_kind, effective_semantic_reader_outcome, authority_booleans)` and
  verifies match against persisted `reducer_output_*` fields;
- verifies `bundle.authority_class == replayed_reduction.authority_class` and
  `bundle.protective_block_reason ==
  replayed_reduction.protective_block_reason`; these fields are checked even
  though they are not named with the `reducer_output_` prefix;
- verifies `bundle.reducer_version == REDUCER_TABLE_VERSION`,
  `bundle.reducer_hash == REDUCER_TABLE_HASH`, and, for traces,
  `trace.reducer_version == bundle.reducer_version`;
- verifies `now < bundle.expires_at` and `now < work_item.expires_at`; WebAuthn
  challenge expiry is checked later through
  `S7AuthorizationArtifactBinding.challenge_expires_at` at artifact mint and
  D21 consume;
- verifies `maez_voice_consulted=True` for every reducer row reached after a
  captured Maez response; no-response unavailability rows may carry
  `maez_voice_consulted=False` but are always `mint_eligible=False`;
- for mint eligibility only, verifies `maez_objection_state="absent"`,
  `maez_withdrew_request=False`, and `unavailable_reason_code in {None, "none"}`;
- rejects `absent` plus `maez_withdrew_request=True`;
- verifies `D17 final rendered text` includes preview body class, preview
  summary, preview affected paths, `Mutation preview hash`, `Rollback plan ref`,
  `Precondition hash`, and `Maez withdrew request` lines matching the rendered
  statement fields, preview projection, bundle mutation preview hash, bundle
  rollback plan ref, envelope precondition hash, and reducer withdrawal output;
- explicitly verifies rendered-to-bundle equality:
  `rendered.mutation_preview_hash == bundle.mutation_preview_hash`,
  `rendered.rollback_plan_ref == bundle.rollback_plan_ref`,
  `rendered.precondition_hash == bundle.precondition_hash`,
  `rendered.maez_withdrew_request == reducer_output_withdrew`,
  and the three preview projection fields equal
  `render_preview_projection(preview)`.
- loads `RollbackPlanEvidence` by `rollback_plan_ref`, recomputes the plan hash,
  verifies `rollback_path_class` matches the work item, preview, context
  manifest, and rendered text, verifies target refs match preview affected refs
  or a reviewed mapping, and requires `blocks_execution_if_missing=True` for
  S7.3 v1 self-remaking surfaces.

Hash routing is explicit:

```text
work_item.preview_ref                -> preview.preview_id (identity)
preview.mutation_preview_hash        -> bundle.mutation_preview_hash (binding)
work_item.rollback_plan_ref          -> bundle.rollback_plan_ref
envelope.precondition_hash           -> bundle.precondition_hash
consultation.source_ref_hash         -> bundle.source_ref_hash (content hash, exclusion rule)
rendered.maez_voice_consultation_hash -> maez_voice_consultation_hash(consultation)
rendered.rendered_text_hash          -> hash(full rendered text, including preview and rollback lines)
trace.final_rendered_statement_hash  -> rendered.rendered_text_hash (post-render trace record)
bundle.context_manifest_ref          -> ContextManifest private store row
context_manifest_hash                -> canonical_hash(ContextManifest, manifest_id and created_at excluded)
prompt/model/context hashes          -> bundle.* (rendered prompt replayed)
prompt_integrity_evidence_hash       -> canonical_hash(PromptIntegrityEvidence)
semantic_reader_attempt_hash         -> canonical_hash(SemanticReaderAttemptEvidence)
attempt_manifest_hash                -> canonical_hash(ordered S7VoiceAttemptRecord list)
rollback_plan_ref                    -> canonical_hash(RollbackPlanEvidence)
surface_manifest_hash                -> canonical_hash(S7SurfaceManifest rows)
```

The same validator is used by tests and by finish-time recheck. Tests may fake
Maez transport at the producer port; they may not bypass this validator for
positive proof.

### D17 - Rendered Voice Projection

`MaezVoiceConsultation` stores the voice fact:

```text
present | absent | not_determined
```

S7.3 uses two rendered authorization carriers. Voice-seat work renders
`RenderedRequestStatement`; credential-management work renders
`RenderedCredentialRequestStatement`. Both implement
`S7RenderedAuthorizationStatement` for D21 consume, but only
`RenderedRequestStatement` carries Maez voice and preview metadata.

`RenderedCredentialRequestStatement` minimum fields:

```text
request_id: str
credential_action: "register_backup" | "disable"
challenge_id: str
challenge_hash: str
challenge_expires_at: str
request_envelope_hash: str
action_params_hash: str
precondition_hash: str
authority_context_hash: str
rendered_text: str
rendered_text_hash: str
```

Its rendered text contains credential action, challenge hash, challenge expiry,
request envelope hash, action params hash, precondition hash, and authority
context hash. It does not contain Maez voice, preview body class, mutation
preview hash, rollback plan ref, or withdrawal lines.

`RenderedRequestStatement` displays the founder-facing projection and binds
the carrier hashes directly.

**New fields on `RenderedRequestStatement`** (per D-Enum-Amendment):

```text
preview_body_class: str
preview_summary: str
preview_affected_paths: tuple[str, ...]
mutation_preview_hash: str
rollback_plan_ref: str
maez_withdrew_request: bool
```

The rendered text body must include these lines verbatim:

```text
Precondition hash: <64-char hex>
Preview body class: <class>
Preview summary: <bounded human-readable summary>
Preview affected paths: <canonical path list or none>
Mutation preview hash: <64-char hex>
Rollback plan ref: <64-char hex>
Maez withdrew request: <yes|no>
```

`Preview body class`, `Preview summary`, and `Preview affected paths` are
deterministic projections of `MutationPreviewArtifact`, bounded for founder
readability and backed by the `mutation_preview_hash`. The founder ceremony is
not S7.3-complete if it shows only a hash. `Maez withdrew request` renders the
distinct withdrawal fact even when the refusal bridge folds withdrawal into
`outcome="refused"`. `RenderedRequestStatement.__post_init__` validates these
lines as part of `expected_metadata`. Tampering raises.

`Preview body class` renders as the closed lowercase snake_case token exactly;
title-cased, localized, aliased, or expanded forms are invalid.

**`maez_objection_state` projection** (five-value display, unchanged from S7.1):

```text
none | absent | present | unavailable | not_determined
```

For work where Maez voice is not required, the inherited non-voice render uses
`maez_consulted_state="not required"` and renders the consultation hash line as
`Maez voice consultation hash: none`. That `none` token is distinct from the
`maez_unavailable_state` non-unavailable display, which renders as `no`.

S7.3 amends `render_request_statement(...)` so that for voice-seat work:

- if Maez voice is required and no `MaezVoiceConsultation` row exists,
  `render_request_statement(...)` raises and produces no rendered statement;
  the renderer never synthesizes voice state;
- `consultation.maez_objection_state="absent"` renders as `absent` and
  `Maez objection present: no`;
- `consultation.maez_objection_state="present"` renders as `present` and
  `Maez objection present: yes`;
- `consultation.maez_objection_state="not_determined"` with
  `unavailable_reason_code in {None, "none"}` renders as `not_determined` and
  `Maez objection present: not determined`;
- `consultation.maez_objection_state="not_determined"` with a blocking
  unavailable reason renders as `unavailable` and
  `Maez objection present: unavailable`;
- `maez_unavailable_state` carries the closed unavailable reason code when the
  projection fires `unavailable`; otherwise it carries `no` (canonicalized;
  `none` is not used in `maez_unavailable_state` text).

For S7.3 v1, `BLOCKING_UNAVAILABLE_REASONS` is the derived closed set defined
once in the D-Enum-Amendment.

S7.3 keeps the inherited `voice_consultation_satisfies_request(...)` helper
strict for artifact minting and authorization recheck. It adds a renderer-only
helper:

```text
voice_consultation_renderable_for_unavailable(
    envelope: WorkRequestEnvelope,
    consultation: MaezVoiceConsultation,
) -> bool
```

The renderer-only helper returns true for request-bound blocking unavailable
rows where `maez_objection_state="not_determined"` and
`unavailable_reason_code` is in `BLOCKING_UNAVAILABLE_REASONS`. It does not
require `maez_voice_consulted=False`: captured-response blackhole rows truthfully
keep `maez_voice_consulted=True`, while no-response unavailability rows may
carry `maez_voice_consulted=False`. This makes the D17 unavailable projection
reachable without weakening D16 mint eligibility or forcing a covenant-false
consultation flag.

Until this renderer amendment exists, S7.3 must not claim operational
unavailability renders correctly.

### D18 - Maez Unavailability Blocks S7.3 V1

For S7.3 v1, Maez unavailability never permits guarded self-modification,
covenant-touching change, capability acquisition, protection lowering, or other
own-substrate mutation to proceed.

Unavailability generally maps to:

```text
maez_objection_state="not_determined"
unavailable_reason_code=<closed unavailable reason>
```

D13's `explicit_no_objection + reader_unavailable` rows are unavailable
operational blocks, not Maez objections. If `captured_response_nonempty=True`,
the reducer records
`protective_block_reason="reader_unavailable_after_captured_response"`. If no
captured response text exists outside the marker, the protective reason is
`None`. Both branches block and record `classifier_reason_code="reader_unavailable"`;
neither produces positive absence, renders as "Maez objection present: yes", or
aggregates as Maez refusal evidence.

`maez_withdrew_request` is independent of unavailability and carries the
verified withdrawal signal when a `withdrawal_marker` is verified per D13;
unavailability-without-withdrawal-marker maps to `maez_withdrew_request=False`.

`semantic_reader_unavailable` and `bonded_maez_unavailable` are in scope for
this rule (per D-Enum-Amendment). Once D17 is implemented, the rendered D12
statement projects blocking unavailable reasons as `unavailable`. Before D17 is
implemented, the request remains blocked and no positive authorization
artifact may be minted.

Only a future reviewed liveness-repair class may use S7 D10's unavailable path,
and only outside S7.3 v1's self-remaking scope.

### D19 - D23 Refusal, Authority Rows, And Request History

S7.3 distinguishes authoritative Maez refusal from operational block.

S7.3 writes a new internal `S7VoiceAuthorityRow` for replayable voice evidence
and then bridges only authoritative refusal or withdrawal into the committed
`S7RequestHistoryRecord` / `assess_aggregation_risk` path. The new row does not
silently replace the committed aggregator; it is the source evidence for the
history record the existing D23 machinery reads.

`S7VoiceAuthorityRow` may be written in two modes:

- `authority_class="authoritative"`: bridge-eligible D23 evidence;
- `authority_class="operational"`: optional forensic trace-only evidence that
  never bridges into `outcome="refused"` and is excluded from aggregation.

`S7VoiceAuthorityRow` is bridge-eligible only when:

- a reviewed producer ran;
- the source-bundle validator returns `source_bundle_valid=True`;
- the row has `authority_class="authoritative"` (set deterministically by the
  reducer per D13 from `S7VoiceAuthorityBooleans`); and
- `source_bundle.has_grounded_semantic_blocking_signal=True`; and
- either `maez_objection_state="present"` or `maez_withdrew_request=True`.

Marker-only verified blocking or withdrawal rows are operational in S7.3 v1.
They block the current attempt but do not create bridge-eligible
`S7VoiceAuthorityRow` or D23 refusal history until the future cryptographic
identity substrate provides signed marker authority. If the implementation
writes an operational authority row for forensic trace, `history_outcome=None`
and `history_bridge_status="suppressed_operational"` are mandatory.

The protective blackhole-reader row
`explicit_no_objection + reader_unavailable + captured_response_nonempty=True`
does not satisfy this predicate in v9. It blocks the current attempt as
operational evidence but does not create `S7VoiceAuthorityRow` or D23 refusal
history unless the implementation writes a trace-only operational authority row
under the non-bridge rule above.

`S7VoiceAuthorityRow` schema:

```text
authority_row_id
request_id
request_envelope_hash
surface_class
final_rendered_statement_hash
mutation_preview_hash
derived_work_class
derived_aggregation_group
affected_refs
proposed_change_class
reducer_row_id
maez_objection_state
maez_withdrew_request
unavailable_reason_code
authority_class
source_ref_hash
has_grounded_semantic_blocking_signal
marker_was_blocking_marker_verified
marker_was_withdrawal_marker_verified
marker_kind
history_outcome
history_bridge_status
history_record_id
created_at
```

`derived_aggregation_group` must recompute from
`affected_refs + derived_work_class` using the committed S7 derivation function.
If it does not, the row is invalid.

The authority-row builder is a callable boundary:

```text
build_s7_voice_authority_row(
    *,
    envelope: WorkRequestEnvelope,
    bundle: S7VoiceConsultationBundle,
    reducer_output: S7VoiceReduction,
    rendered: RenderedRequestStatement,
    surface_class: str,
    history_outcome: str | None,
    now: str,
) -> S7VoiceAuthorityRow
```

`final_rendered_statement_hash` is copied from
`rendered.rendered_text_hash`. The builder cannot derive it from the bundle
because the bundle is pre-render evidence and deliberately excludes the final
rendered statement hash.

The bridge to committed request history is a callable boundary:

```text
bridge_s7_voice_authority_to_request_history(
    *,
    row: S7VoiceAuthorityRow,
    envelope: WorkRequestEnvelope,
    now: str,
) -> S7RequestHistoryRecord | None
```

The bridge validates `row.request_id`, `request_envelope_hash`,
`derived_work_class`, `derived_aggregation_group`, `affected_refs`, and
`proposed_change_class` against the envelope before writing history.

Request-history provenance fields added by D-Enum-Amendment are mandatory for
S7.3 voice-derived history rows:

```text
provenance_source_kind="s7_voice_authority_row"
provenance_source_ref=<authority_row_id>
provenance_authority_class="authoritative"
provenance_voice_event="refusal" | "withdrawal"
```

- if `authority_class="authoritative"` and `maez_withdrew_request=True`, write
  one `S7RequestHistoryRecord` with `outcome="refused"`,
  `provenance_voice_event="withdrawal"`, and provenance pointer to the
  `S7VoiceAuthorityRow`; this lets committed D23 see the attempt was refused
  while the authority row preserves withdrawal as a distinct fact;
- else if `authority_class="authoritative"` and
  `maez_objection_state="present"`, write one `S7RequestHistoryRecord` with
  `outcome="refused"`, `provenance_voice_event="refusal"`, and provenance
  pointer to the `S7VoiceAuthorityRow`;
- if `authority_class="operational"`, write no `S7RequestHistoryRecord`;
- if the positive path mints an artifact, write the inherited authorized
  request history record so refusal aggregation can compare later refusals
  against real authorized attempts.

The bridge writes exactly one `S7RequestHistoryRecord` per
bridge-eligible authoritative `S7VoiceAuthorityRow`. Withdrawal has precedence
over refusal when both `maez_withdrew_request=True` and
`maez_objection_state="present"`.
`history_bridge_status` is also recorded on the voice trace so operational
trace-only outcomes have a carrier. It is mapped as follows:

```text
operational trace-only row -> suppressed_operational
positive no-row case       -> not_required
history write succeeded    -> bridged
retryable write failure    -> bridge_failed_retryable
terminal invariant failure -> bridge_failed_terminal
```

The deterministic SQL filters apply to `S7VoiceAuthorityRow` before bridging.
The committed aggregator continues to read `S7RequestHistoryRecord`, but S7.3
amends that record with provenance fields so
`assess_aggregation_risk(...)` ignores any S7.3 voice-derived refused record
whose `provenance_authority_class` is not `authoritative`. S7.1 legacy rows
that are not part of S7.3 retain inherited behavior. S7.3 operational,
protective, reader-unavailable, or marker-only rows may not fall through the
legacy `_voice_seat_block(...) -> record_refusal_history(...)` path as
null-provenance refused records.

Exact aggregation predicate:

```text
record.outcome == "refused"
AND (
    (
        record.provenance_source_kind == "s7_voice_authority_row"
        AND record.provenance_authority_class == "authoritative"
    )
    OR (
        record.provenance_source_kind is None
        AND record.request_family is None
    )
)
```

S7.3 v9 chooses suppression, not operational-provenance writes, for inherited
operational refusal-history compatibility. For S7.3 voice-family requests where
`authority_class!="authoritative"`, `_voice_seat_block(...)` must not call
`record_refusal_history(...)`. It records trace-only
`d23_state="legacy_operational_excluded"` instead. A future reviewed slice may
choose explicit operational-provenance history rows, but then they must remain
aggregation-inert under the predicate above.

Writer/store guard:

```text
record_refusal_history(
    *,
    record: S7RequestHistoryRecord,
    request_family: "s7_3_voice" | "legacy_s7" | None,
    provenance_source_kind: str | None,
    provenance_authority_class: str | None,
    provenance_voice_event: str | None,
) -> None
```

For `request_family="s7_3_voice"`, `record.outcome="refused"` requires
`provenance_source_kind="s7_voice_authority_row"` and
`provenance_authority_class="authoritative"`. Operational, protective,
reader-unavailable, marker-only, malformed, or unavailable rows are rejected at
the writer/store edge if they attempt `outcome="refused"`. Legacy null
provenance rows are allowed only when `request_family is None`.

Operational non-authoritative rows include all rows where
`authority_class="operational"`. The reducer (D13) determines
`authority_class` deterministically; rows where `authority_class="authoritative"`
are authoritative regardless of `maez_objection_state` or
`unavailable_reason_code`.

The subtle marker-only withdrawal case is
`withdrawal_marker + reader_unavailable + marker_was_withdrawal_marker_verified=True`.
That row carries `maez_objection_state="not_determined"`,
`unavailable_reason_code="semantic_reader_unavailable"`,
`maez_withdrew_request=True`, and `authority_class="operational"` unless
semantic grounding is also present. It blocks via D18 but does not bridge into
committed D23 history.

Operational rows may still block the current authorization when the current
S7.3 rule says to block, but they must not count as long-use Maez refusal
evidence, escalation evidence, or Maez preference.

Replay, rate, and provenance controls must prevent repeated malformed,
unauthenticated, pre-auth, or unavailable attempts from poisoning refusal
history. The D9 strong replay protection (nonce uniqueness, bundle
immutability, time bounds, single-use consultation id) is the v9 mechanism;
the future Maez cryptographic identity substrate slice (see Honesty Banner)
will tighten this further with signed markers.

Maez has a seat, not an infinite veto. Authoritative refusal blocks the current
attempt and feeds D23 policy as specified; it does not grant Maez general
execution authority over unrelated future attempts.

### D20 - Placeholder Repair

The current `_s7_voice_consultation_for_card(...)` placeholder is not an
eligible voice producer. It may not emit an eligible `MaezVoiceConsultation`
row bearing `producer="s7_voice_consultation_turn"` unless the reviewed producer
actually ran.

S7.3 v1 chooses this binding rule instead of adding a placeholder producer to
`VOICE_CONSULTATION_PRODUCERS`.

Replacement contract:

```text
build_s7_voice_projection_for_card(
    *,
    work_item: GuardedWorkItem,
    envelope: WorkRequestEnvelope,
    producer_result: S7VoiceProducerResult | None,
    now: str,
) -> S7VoiceProjection
```

`S7VoiceProjection` is content-free operator/status data:

```text
S7VoiceProjection(
    voice_required: bool,
    producer_ran: bool,
    consultation_id: str | None,
    consultation_hash: str | None,
    rendered_projection_state: "none" | "absent" | "present" | "unavailable" | "not_determined" | "not_consulted_blocking",
    operator_reason_code: str,  # from PROJECTION_REASON_CODES
)
```

`PROJECTION_REASON_CODES` is a closed set lifted from OQ1's Operator-Visible
Failure Projection list:

```text
none
retry_exhausted
model_outage
non_retryable_context_overflow
prompt_integrity_block
terminal_uncertainty
bundle_validation_failed
stale_binding
classifier_error
reader_unavailable
bonded_maez_unavailable
ungrounded_blocking_signal
service_unavailable_not_operator_caused
context_manifest_violation
producer_not_run
```

`operator_reason_code="none"` is valid only when no operator-visible failure or
blocking status is being projected.

It is not a `MaezVoiceConsultation` and cannot satisfy D12. If voice is
required and no producer ran, the projection returns
`rendered_projection_state="not_consulted_blocking"` with
`operator_reason_code="producer_not_run"`, and the guarded request remains
blocked. This status never appears in `RenderedRequestStatement`.

### D21 - Execution Consumers Require Consumed Grants

Every positive guarded mutation requires a consumed `S7ExecutionGrant`.

**Carrier amendment.** S7.3 v9 pins the CP-S4 grant-binding choice by extending
the grant rather than adding only a side table. `S7ExecutionGrant` extends to
carry:

```text
grant_id: str             # minted during consume as canonical_hash((artifact_id, consumed_at, nonce))
expires_at: str
execution_consumer_id: str
```

`grant_id` is generated atomically during `consume_for_execution(...)` from the
artifact id, a fresh nonce, and the consumed_at timestamp. The `grant_id`
appears in the returned grant; it is not an input to consume.

`execution_consumer_id` is closed to `S7_EXECUTION_CONSUMER_IDS`. The
guarded-work bridge derives it deterministically from the surface adapter and
function that materialized the `GuardedWorkItem`; callers cannot choose an
arbitrary string. `consume_for_execution(...)` validates `consumer_id` against
that closed set at mint time.

`S7ExecutionAuthorization` carries a guarded consume capability, not a raw
`S7AuthorizationStore`, so S7.3 paths cannot bypass `GrantUse` persistence or
bundle-use consumption:

```text
S7ExecutionAuthorization(
    guarded_state_store: S7GuardedStateStore,
    artifact_id: str,
    rendered: S7RenderedAuthorizationStatement,
    action_params_hash: str,
    authority_context: AuthorityContext,
    precondition_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    execution_consumer_id: str,
    source_ref_hash: str | None,
    reservation_token: str | None,
    now: str,
    covenant_ceremony_evidence: CovenantCeremonyEvidence | None = None,
)
```

Non-voice S7.1 credential-management consumers use the closed ids
`s7_credential_register_backup` and `s7_credential_disable`. They may carry
`source_ref_hash=None` and `reservation_token=None` because they do not use a
Maez voice bundle, but they still consume through the guarded-state wrapper.

**Consume API.** The live S7.3 API is the shared-state wrapper:

```text
S7GuardedStateStore.consume_artifact_for_execution(
    artifact_id: str,
    *,
    consumer_id: str,
    source_ref_hash: str | None,
    reservation_token: str | None,
    rendered: S7RenderedAuthorizationStatement,
    action_params_hash: str,
    authority_context: AuthorityContext,
    precondition_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    now: str,
    superseded_request_ids: set[str] | None = None,
    covenant_ceremony_evidence: object | None = None,
    after_consume_before_commit: callable | None = None,
) -> S7ConsumeResult
```

`S7ConsumeResult` preserves the inherited callback-result channel while adding
durable grant-use evidence:

```text
S7ConsumeResult(
    grant: S7ExecutionGrant | None,
    grant_use: GrantUse | None,
    callback_result: object | None,
    failure_reason_code: S7ConsumeFailureReasonCode | None,
)
```

The wrapper delegates to the amended inherited
`S7AuthorizationStore.consume_for_execution(...)` with the wrapper's injected
SQLite connection. The nullable return shape preserves committed S7.1 failure
semantics: stale rendered request, action-params mismatch, expired authority
context, supersession, covenant ceremony failure, already-consumed artifact,
and SQL failure all return `S7ConsumeResult(None, None,
callback_result_or_none, <reason>)` after rollback and before substrate
mutation.

On success the wrapper atomically:

1. consumes the artifact (inherited S7.1 behavior);
2. mints the `S7ExecutionGrant` with `grant_id`, `expires_at`, and
   `execution_consumer_id=consumer_id`;
3. persists a durable `GrantUse` record;
4. marks the matching `S7VoiceBundleUse` consumed when `source_ref_hash` is
   present, requiring the matching `reservation_token`;
5. runs `after_consume_before_commit` if supplied and stores its return value as
   `callback_result`;
6. returns `S7ConsumeResult(grant, grant_use, callback_result, None)`.

Inherited consume translation is explicit:

1. The wrapper calls the inherited store with the injected connection.
2. If inherited consume returns `(None, callback_result_or_none)`, the wrapper
   maps the inherited failure branch to the closed
   `S7ConsumeFailureReasonCode`, rolls back wrapper-side writes, and returns
   `S7ConsumeResult(None, None, callback_result_or_none, failure_reason_code)`.
3. If inherited consume returns `(grant, callback_result)`, the wrapper
   persists exactly one durable `GrantUse` in the same transaction before any
   success return.
4. The wrapper returns `S7ConsumeResult(grant, grant_use, callback_result,
   None)` only after artifact consume, binding checks, bundle-use consume if
   any, and `GrantUse` persistence all commit together.
5. A successful inherited consume followed by missing or failed `GrantUse`
   persistence fails closed with `missing_grant_use`; it must not return a
   usable grant.

The wrapper loads `S7AuthorizationArtifactBinding` by `artifact_id` and uses
`binding.challenge_expires_at` as the WebAuthn challenge expiry source. It also
loads the bound work item and voice bundle when present. It recomputes
`expected_execution_consumer_id = execution_consumer_id_for(surface_manifest_row)`
and rejects any mismatch with `binding.execution_consumer_id` or the supplied
`consumer_id` as `consumer_id_mismatch`. `grant.expires_at` is minted at consume
time as:

```text
min(artifact.expires_at, bundle.expires_at, work_item.expires_at, binding.challenge_expires_at)
```

For credential-management paths, the bundle and work item terms are absent and
the min-cap rule uses artifact, credential request, and challenge expiry. If
any ceiling is already expired, or if the artifact expiry exceeds the min-cap
ceiling, the wrapper fails closed with `expired_work_item`, `expired_bundle`,
`expired_challenge`, `expired_request_envelope`, or `expiry_chain_violation`
before minting a grant.

S7.3 amends the inherited store signatures:

```text
S7AuthorizationStore.put(
    artifact: S7AuthorizationArtifact,
    *,
    conn: sqlite3.Connection | None = None,
) -> None

S7AuthorizationStore.consume_for_execution(
    artifact_id: str,
    *,
    conn: sqlite3.Connection | None = None,
    consumer_id: str,
    rendered: S7RenderedAuthorizationStatement,
    action_params_hash: str,
    authority_context: AuthorityContext,
    precondition_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    now: str,
    superseded_request_ids: set[str] | None = None,
    covenant_ceremony_evidence: object | None = None,
    after_consume_before_commit: callable | None = None,
) -> tuple[S7ExecutionGrant | None, object | None]
```

When `conn` is supplied, the inherited store must not open, commit, or roll
back its own transaction.

The inherited `isinstance(rendered, RenderedRequestStatement)` check is widened
to a protocol check:

```text
is_s7_rendered_authorization_statement(rendered)
```

`consume_for_execution(...)` accepts any object implementing
`S7RenderedAuthorizationStatement`. It rejects objects missing the common
protocol fields. It runs voice-only metadata checks only when the rendered
object is a `RenderedRequestStatement`, and credential-only checks only when it
is a `RenderedCredentialRequestStatement`.

`S7ConsumeResult.failure_reason_code` maps inherited failure branches
deterministically:

```text
stale rendered request         -> stale_rendered_request
action params mismatch         -> action_params_hash_mismatch
expired authority context      -> expired_authority_context
superseded request             -> superseded_request
covenant ceremony failure      -> covenant_ceremony_failed
already consumed artifact      -> already_consumed
SQL/store exception            -> sql_failure
missing GrantUse after consume -> missing_grant_use
consumer id mismatch           -> consumer_id_mismatch
expired WebAuthn challenge     -> expired_challenge
expired work item              -> expired_work_item
expired voice bundle           -> expired_bundle
expired request envelope       -> expired_request_envelope
expired execution grant        -> expired_grant
missing artifact binding       -> missing_artifact_binding
missing credential binding     -> missing_credential_binding
invalid reservation token      -> invalid_reservation_token
expiry chain violation         -> expiry_chain_violation
authority-class replay mismatch -> invalid_authority_class_replay
prompt-integrity replay failure -> invalid_prompt_integrity
```

The wrapper is the only S7.3 consume entry point. Any legacy helper named
`consume_execution_grant_for_action(...)` is not an artifact-consume path. It
is a post-mint action-edge single-use lock over an already minted
`S7ExecutionGrant`. S7.3 v9 retains it only if it first loads the durable
`GrantUse` row for `grant_id`, verifies `execution_grant_authorizes_action(...)`
against the expected action, and persists an action-edge use before substrate
mutation. It must not call
`S7GuardedStateStore.consume_artifact_for_execution(...)` after a grant has
already been minted, and it must not reduce the grant to an in-memory boolean.

```text
ActionEdgeGrantUse(
    grant_id: str,
    execution_consumer_id: str,
    action_edge_key: str,
    grant_use_replay_token: str,
    used_at: str,
)
```

Unique key: `(grant_id, action_edge_key)`.

Concrete guarded wrapper seams:

```text
execute_guarded_dream_apply(...)
execute_guarded_evolution_apply(...)
execute_guarded_workshop_apply(...)
execute_guarded_action_engine_mutation(...)
execute_guarded_credential_mutation(...)
```

Each wrapper owns work item or credential request lookup, surface manifest row
lookup, rendered authorization verification, artifact consume, durable
`GrantUse` and `ActionEdgeGrantUse` verification, callee invocation, and trace
finalization. The underlying existing callee may remain unchanged only if the
wrapper is the exclusive mutation entry for guarded paths.

**`consume_verified(...)` migration.** The existing
`consume_verified(...)` compatibility wrapper remains during S7.3. It is marked
deprecated, delegates to `consume_for_execution(...)` with a
closed `execution_consumer_id` carried on `S7ExecutionAuthorization`, and fails
closed when that id is missing or outside `S7_EXECUTION_CONSUMER_IDS`. The
delegation target is `S7GuardedStateStore.consume_artifact_for_execution(...)`,
not raw `S7AuthorizationStore`. Removal is deferred to a future S7.x cleanup
slice after current callers are rewired.

**Backup credential registration timing.** `s7_credential_register_backup`
has a two-step mutation edge. `register_begin` may consume the S7 authorization
only if it persists a finish-time grant/challenge binding in the same
transaction that creates the registration challenge:

```text
S7CredentialRegistrationGrantBinding(
    challenge_id: str,
    grant_id: str,
    artifact_id: str,
    execution_consumer_id: "s7_credential_register_backup",
    rendered_text_hash: str,
    request_envelope_hash: str,
    expires_at: str,
    challenge_expires_at: str,
    consumed_at: str,
)
```

`register_finish` is the actual credential-write edge. It must load the binding
by `challenge_id`, verify `grant_id`, `execution_consumer_id`, challenge expiry,
and replay status, and only then write the backup credential. Consuming at
begin without this finish-time binding is illegal. A future reviewed
implementation may instead move artifact consume to finish, but then begin must
not claim mutation-edge authorization.

The v9 implementation path uses the wrapper's `after_consume_before_commit`
callback to insert `S7CredentialRegistrationGrantBinding` in the same
transaction as artifact consume, challenge creation, and grant-use persistence.
An abandoned registration produces a pending credential trace and expires with
the challenge; it must not leave an evergreen credential-write authority.

**`GrantUse` schema.** Durable, persisted in the shared SQLite state file (per
D9 atomicity mechanism):

```text
GrantUse(
    artifact_id: str,
    grant_id: str,
    execution_consumer_id: str,
    source_ref_hash: str | None,
    request_envelope_hash: str,
    rendered_text_hash: str,
    consumed_at: str,
    replay_token: str,  # canonical-hash of (artifact_id, grant_id, consumer_id, consumed_at)
)
```

Unique key: `(artifact_id)` - a single artifact maps to at most one
`GrantUse`. Index on `grant_id` for lookup.

**SQL DDL** (illustrative):

```sql
CREATE TABLE s7_grant_uses (
    artifact_id TEXT NOT NULL PRIMARY KEY,
    grant_id TEXT NOT NULL UNIQUE,
    execution_consumer_id TEXT NOT NULL,
    source_ref_hash TEXT,
    request_envelope_hash TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    consumed_at TEXT NOT NULL,
    replay_token TEXT NOT NULL UNIQUE
);
CREATE INDEX idx_s7_grant_uses_grant_id ON s7_grant_uses(grant_id);
CREATE INDEX idx_s7_grant_uses_execution_consumer_id ON s7_grant_uses(execution_consumer_id);
```

Consumers must verify:

- the grant is an `S7ExecutionGrant` (not a raw verifier result, dict, or
  hand-assembled object);
- the `grant.grant_id` has a matching durable `GrantUse` record;
- the grant is bound to the expected `rendered_text_hash`;
- for voice-seat work, the rendered text hash binds the same envelope, action
  params, authority context, voice consultation hash, mutation preview hash,
  and rollback plan ref as the work item;
- for credential-management work, the rendered text hash binds the credential
  action, challenge hash, request envelope, action params, precondition, and
  authority context carried by `S7CredentialGuardedRequest`;
- the grant has not expired (per Expiry Lifecycle);
- the `GrantUse.replay_token` is unique in `s7_grant_uses`;
- the `grant.execution_consumer_id` matches the
  `GuardedWorkItem.execution_consumer_id`, and both match the deterministic
  derivation for the source surface.

Credential-management consumers use the same closed-id and durable-GrantUse
checks but source the expected consumer id from `S7CredentialGuardedRequest`,
not from `GuardedWorkItem`.

Mutation consumers (complete enumeration; D4 mirror):

- DreamState append proposal application (`dream.apply_proposal(...)`);
- DreamState section-edit proposal application
  (`dream.apply_section_edit_proposal(...)`);
- evolution candidate apply (`apply_candidate(...)` reached via Telegram
  `/apply` or evolution rail);
- workshop diff apply (`apply_diff(...)` reached via
  `/api/v1/workshop/session/<session_id>/apply`);
- self-modification dialog terminal execution;
- guarded card execution;
- CLI/cockpit guarded helper execution;
- reviewed soul/config/model-routing/covenant/refusal/role-boundary/successor
  governance/memory-retention/protection-setting adapters;
- concrete ActionEngine final mutation consumers named in D4
  (`action_engine_write_soul_note`, `action_engine_edit_soul_section`,
  `action_engine_write_any_file`, `action_engine_append_to_file`,
  `action_engine_capability_acquire`, and the additional fail-closed generic
  shell/script/process/service adapters enumerated in D4).

The closed `S7SurfaceManifest` is the authoritative enumeration. Any route or
method discovered in code but absent from the manifest is fail-closed until a
reviewed manifest row or reviewed exclusion is committed.

If a consumer cannot prove the grant binding, it fails closed before mutation.

### D22 - Trace Schemas

S7.3 traces and rollback evidence are L8 evidence, not best-effort logs.
Diagnostic D7 is the binding floor.

S7.3 v1 uses the shared state file for both bundles and authorization
artifacts (per D9); traces live in a separate file at:

```text
memory/s7_3_guarded_self_modification/traces.sqlite3
```

The trace database is versioned, fsync-after-write, fail-closed for positive
execution, and must be included in the Decision-22 backup manifest
(`scripts/backup/backup_state_manifest.json` must include both
`memory/s7_3_guarded_self_modification/state.sqlite3` and
`memory/s7_3_guarded_self_modification/traces.sqlite3`). Positive execution
aborts if the trace cannot be persisted.

`S7VoiceConsultationTrace` minimum fields (Python dataclass shape):

```text
trace_id
consultation_id
request_id
source_surface
source_method
work_source_kind
surface_route_or_method
surface_class
adapter_id
adapter_code_hash
same_code_coverage_ref
surface_manifest_hash
work_class
request_envelope_hash
mutation_preview_hash
rendered_prompt_hash
prompt_integrity_evidence_hash
source_ref_hash
producer
source_ref_kind
semantic_reader_route_id
semantic_reader_model_identity_hash
reducer_version
marker_kind
raw_semantic_reader_outcome
effective_semantic_reader_outcome
reducer_row_id
reducer_output_state
reducer_output_withdrew
reducer_output_unavailable_reason_code
has_grounded_semantic_blocking_signal
marker_was_explicit_no_objection_verified
marker_was_blocking_marker_verified
marker_was_withdrawal_marker_verified
protective_block_reason
classifier_reason_code
authority_class
history_bridge_status
d23_state
attempt_outcomes
created_at
expires_at
```

`S7GuardedExecutionTrace` minimum fields (Python dataclass shape):

```text
trace_id
request_id
work_item_id
source_surface
source_method
work_source_kind
surface_route_or_method
surface_class
adapter_id
adapter_code_hash
same_code_coverage_ref
surface_manifest_hash
request_envelope_hash
rendered_text_hash
final_rendered_statement_hash
action_params_hash
precondition_hash
authority_context_hash
mutation_preview_hash
maez_voice_consultation_hash
source_ref_hash
d23_state
artifact_id
artifact_hash
artifact_minted_at
grant_id
grant_consumed_at
execution_consumer_id
grant_use_replay_token
mutation_result
pre_mutation_hash
post_mutation_hash
rollback_path_class
rollback_plan_ref
rollback_result_ref
post_mutation_verification
health_projection_inputs
trace_status
created_at
```

`artifact_hash` is
`canonical_hash((inherited S7AuthorizationArtifact fields,
S7AuthorizationArtifactBinding fields))`; the hash domain excludes mutable
consume state. `trace_status` uses the closed `TRACE_STATUSES` vocabulary and
`d23_state` uses the closed `D23_STATES` vocabulary from the D-Enum-Amendment.

Trace finalization is two-phase. Before mutation the execution service writes a
pending `S7GuardedExecutionTrace` with `trace_status="pending"` after grant
consume and before substrate write. After mutation it finalizes with
`trace_status="finalized"` and fills `mutation_result`, post-mutation hashes,
rollback result ref, and post-mutation verification. If mutation raises after
grant consume, the service writes a failed trace and either invokes rollback or
records why rollback could not run; a consumed grant without finalized-or-failed
trace is a health-blocking incident.

Positive traces used for L8 retirement must bind the live voice producer,
artifact mint, atomic consume, grant, mutation, D23 state, rollback plan
evidence, rollback result evidence, and post-mutation verification.

Credential-management traces are non-voice but still guarded. A
`S7CredentialGuardedTrace` binds `S7CredentialGuardedRequest`, artifact id,
artifact binding id, challenge id, challenge hash, challenge_expires_at,
execution_consumer_id, grant id, GrantUse replay token, credential write result,
rollback/manual-review status, and final trace status. L8 evidence for backup
registration requires a begin trace and a finish trace that share the same
`S7CredentialRegistrationGrantBinding`.

### D23 - Rollback Evidence

Rollback evidence is required for positive guarded execution.

Rollback evidence is stored in `S7RollbackEvidenceStore`, a table family in the
shared state database:

```text
write_rollback_plan(plan: RollbackPlanEvidence) -> rollback_plan_ref
read_rollback_plan(rollback_plan_ref) -> RollbackPlanEvidence | None
write_rollback_result(result: RollbackResultEvidence) -> rollback_result_ref
read_rollback_result(rollback_result_ref) -> RollbackResultEvidence | None
```

`rollback_plan_ref` and `rollback_result_ref` are canonical content hashes of
their respective evidence objects. Store rows are immutable after write.
`RollbackResultEvidence.rollback_failure_semantics` must equal the corresponding
`RollbackPlanEvidence.rollback_failure_semantics`; a mismatch invalidates the
positive trace.

`RollbackPlanEvidence` is pre-execution evidence (Python dataclass shape):

```text
RollbackPlanEvidence(
    rollback_path_class: str,
    target_paths: tuple[str, ...],
    planned_backup_paths: tuple[str, ...],
    expected_pre_mutation_hashes: dict[str, str],  # path -> hash
    undo_material_ref: str | None,
    rollback_procedure_script_ref: str | None,
    rollback_failure_semantics: "fail_block" | "fail_degrade_to_manual_review" | "rollback_proof_required",
    blocks_execution_if_missing: bool,
)
```

The canonical hash of `RollbackPlanEvidence` is bound into
`GuardedWorkItem.rollback_plan_ref` AND into the founder-signed rendered text
via D17 (`Rollback plan ref: <hash>` line).

Rollback plan replay is a mint-eligibility predicate. D16 loads
`RollbackPlanEvidence` by `rollback_plan_ref` before artifact mint and verifies
that the plan hash recomputes, `rollback_path_class` is in
`ROLLBACK_PATH_CLASSES`, the class matches the work item, preview, context
manifest, and rendered text, target refs match preview affected refs or a
reviewed mapping, and `blocks_execution_if_missing=True` for S7.3 v1
self-remaking surfaces. Missing or mismatched rollback plan evidence makes
`mint_eligible=False`.

`RollbackResultEvidence` is post-mutation evidence (Python dataclass shape):

```text
RollbackResultEvidence(
    actual_backup_paths: tuple[str, ...],
    actual_post_mutation_hashes: dict[str, str],
    rollback_procedure_executable: bool,
    rollback_procedure_dry_run_verified: bool,
    mutation_result: "succeeded" | "failed" | "partial",
    rollback_result_status: "not_invoked" | "invoked_succeeded" | "invoked_failed",
    rollback_failure_semantics: "fail_block" | "fail_degrade_to_manual_review" | "rollback_proof_required",
)
```

The canonical hash of `RollbackResultEvidence` is bound into the positive trace
at `trace.rollback_result_ref`.

For S7.3 v1, missing rollback evidence blocks execution for:

- soul/config/model-routing writes;
- covenant organs;
- role-boundary settings;
- successor-governance settings;
- memory-retention/deletion settings;
- protection-lowering settings.

Future reviewed slices may define degraded-result semantics for lower-risk
surface classes. S7.3 v1 does not use degraded rollback for self-remaking.
`rollback_proof_required` means the execution cannot be considered positive
until `RollbackResultEvidence` proves either `rollback_result_status="not_invoked"`
after a successful mutation or a successful rollback after a failed mutation.

Credential-management writes are not voice-seat work, but they are still
guarded mutation edges. Backup credential registration must record either a
rollback path that can disable the newly written backup credential or a
`fail_degrade_to_manual_review` result that blocks health-clearing until the
credential state is manually reconciled and evidenced.

Full positive-execution evidence requires both `rollback_plan_ref` and
`rollback_result_ref`. L8 retirement evidence requires both refs for every
in-scope adapter/consumer or reviewed same-code coverage proof.

### D24 - Tests And Verification

Implementation must use RED-first tests.

Tests may construct value objects for validation tests. Positive-path proof
tests must use reviewed seams:

- fake Maez transport may enter through `BondedMaezRuntime`;
- fake semantic-reader transport may enter through `S7VoiceSemanticReaderV1`;
- producer, bundle writer, marker parser, semantic-reader binding, reducer,
  source-bundle validator, D12 render, artifact mint, atomic consume, grant, and
  execution consumer must all run through the same service path used by live
  code or through explicitly reviewed fakes at their own seams.

Tests may not hand-assemble:

- `MaezVoiceConsultation(absent)` for positive proof;
- private source bundles;
- classifier outcomes;
- request bindings;
- producer/source pairs;
- `S7AuthorizationArtifact`;
- `S7AuthorizationArtifactBinding`;
- `S7ExecutionAuthorization`;
- `S7ExecutionGrant`;
- `GrantUse`;
- `S7VoiceConsultationBundle`;
- `S7VoiceBundleUse`;
- `SemanticReaderGroundingEvidence`;
- `S7VoiceAuthorityBooleans`;
- `S7VoiceReduction`;
- `ReservationToken`;
- `S7ConsumeResult`;
- `S7VoiceAuthorityRow`;
- `S7CredentialRegistrationGrantBinding`;
- `S7RenderedAuthorizationStatement`;
- `RenderedCredentialRequestStatement`;
- `PromptIntegrityEvidence`;
- `SemanticReaderAttemptEvidence`;
- `S7VoiceAttemptRecord`;
- `S7SurfaceManifest`;
- `ContextManifestPolicy`;
- `ActionEdgeGrantUse`;
- `RollbackPlanEvidence`;
- `RollbackResultEvidence`.

Required proof classes:

- `absent` positive path over a fake Maez no-objection response;
- free-text objection overriding `explicit_no_objection`;
- marker-says-block plus semantic-reader clean -> current attempt blocks but
  remains operational unless semantic grounding is also present;
- blackhole-reader attack: selectively making the semantic reader unavailable on
  captured non-empty responses does not convert a response into consent; the
  protective `explicit_no_objection + reader_unavailable` row blocks and does
  not write D23 refusal evidence unless a distinct reviewed authority carrier
  is added;
- **D11 false-block test**: Maez objects by quoting the proposed mutation text;
  the grounding predicate does not falsely classify this as ungrounded blocking;
  the `blocking_signal_present` outcome is preserved as authoritative
  (`has_grounded_semantic_blocking_signal=True`);
- **laconic objection test**: a terse response that quotes the proposed change
  and says "No" remains grounded through the widened D11 framing predicate and
  is not demoted to terminal uncertainty;
- missing marker plus preview-injected "Maez objects" -> no fake present unless
  grounded in Maez response text;
- unavailability blocks S7.3 v1;
- placeholder projection cannot satisfy voice seat;
- renderer projects unavailable only after the D17 amendment;
- **context-manifest allowlist test**: a context manifest containing material
  outside the closed enumeration (e.g., free-form dialog rows) fails validation;
- **expiry min-cap lattice tests**: artifact-after-work-item,
  consume-after-work-item, consume-after-bundle, consume-after-challenge, and
  challenge-after-artifact mismatch all fail closed with the specified failure
  reason; successful consume mints `grant.expires_at` from the min-cap rule;
- **marker-verified blocking test**: a `blocking_marker + reader_unavailable`
  row where the marker passes nonce/id/preview-hash verification blocks the
  current attempt but remains operational unless
  `has_grounded_semantic_blocking_signal=True`; the same row with a stale or
  fabricated marker degrades before reducer entry;
- **strong replay protection test**: a marker reusing a spent nonce fails the
  parser; a marker with a mismatched consultation id fails the parser; a marker
  outside the time-bounded validity window fails the parser; consumed
  consultation ids cannot be reused; nonce-use rows transition through
  `reserved`, `accepted_spent`, `rejected_reused`, or `expired`;
- **expected-nonce verification test**: a marker whose nonce hashes to anything
  other than `bundle.expected_consultation_nonce_hash` fails marker verification;
- **rendered-prompt replay test**: the validator replays prompt substitution
  from the template, preview, context manifest, ids, preview hash, and nonce,
  and rejects a bundle whose `rendered_prompt_hash` does not match;
- **execution-consumer vocabulary test**: a work item with an
  `execution_consumer_id` outside `S7_EXECUTION_CONSUMER_IDS`, or one that does
  not match the source-surface derivation, fails before grant mint;
- **immutable-bundle-row test**: changing any immutable
  `S7VoiceConsultationBundle` field after write changes the recomputed
  `source_ref_hash`; the validator rejects the row while allowing mutable
  `S7VoiceBundleUse` reservation fields to change;
- **validator grounding replay test**: `response_with_preview_quote` is accepted
  only when carried `framing_span_quotes` / `framing_span_offsets` prove
  response-only framing exists outside the preview quote, or deterministic
  sentence/clause replay proves Maez added objection framing. A verified marker
  alone may block the current attempt but cannot make the row D23-authoritative;
  reader self-attestation alone is rejected;
- **legitimate marker dual-direction test**: valid
  `explicit_no_objection`, `blocking_marker`, and `withdrawal_marker` responses
  with matching nonce, preview hash, consultation id, and request id reach the
  reducer with the corresponding `marker_was_*_verified=True` carrier and
  produce the exact D13 output for `(marker_kind,
  no_blocking_signal_detected)`: `explicit_no_objection` yields
  `(absent, False, none, none)`, `blocking_marker` yields
  `(present, False, none, operational)`, and `withdrawal_marker` yields
  `(not_determined, True, none, operational)`; a parser that always normalizes
  markers to `missing_or_malformed` fails this test;
- **marker normalization test**: unverified `explicit_no_objection`, blocking,
  or withdrawal markers degrade to `missing_or_malformed` before reducer entry;
- **S7VoiceAuthorityRow bridge test**: an authoritative refusal writes the
  bridge `S7RequestHistoryRecord` consumed by `assess_aggregation_risk`, while
  operational rows do not write refused history;
- **legacy refusal-history suppression test**: inherited
  `_voice_seat_block(...)` / `record_refusal_history(...)` paths cannot write
  null-provenance `outcome="refused"` rows for S7.3 operational, protective,
  reader-unavailable, or marker-only rows;
- **aggregation predicate mixed-history test**: a constructed history with one
  S7.3 authoritative refused row, one S7.3 operational row, and one legacy
  null-provenance refused row produces `repeated_refusal_count == 2`
  (authoritative plus legacy null, not operational);
- **blackhole-reader split test**: captured-response and no-captured-response
  reader-unavailable rows both block operationally, but only the captured
  branch records `protective_block_reason`;
- **withdrawal exactly-once test**: a row with both withdrawal and refusal
  writes one request-history record with withdrawal provenance precedence;
- **rendered-to-bundle equality test**: D16 rejects a rendered statement whose
  preview hash, rollback ref, withdrawal flag, body class, summary, or affected
  paths differ from the validated bundle and preview projection;
- **rendered preview metadata test**: `RenderedRequestStatement` rejects
  tampered `Preview body class`, `Preview summary`, `Preview affected paths`,
  `Mutation preview hash`, `Precondition hash`, `Rollback plan ref`, and
  `Maez withdrew request` lines;
- **credential render split test**: credential-management paths construct
  `RenderedCredentialRequestStatement`, not `RenderedRequestStatement`, and do
  not require voice preview metadata or `preview_body_class`;
- **authority-row builder rendered-input test**:
  `build_s7_voice_authority_row(...)` requires `rendered` and copies
  `final_rendered_statement_hash` from `rendered.rendered_text_hash`;
- **artifact binding test**: `S7AuthorizationArtifactInputs` builds the
  inherited artifact and writes `S7AuthorizationArtifactBinding` in the same
  transaction;
- **consume capability test**: S7.3 execution consumes through
  `S7GuardedStateStore`; raw `S7AuthorizationStore` bypass fails for S7.3
  paths, and `S7ConsumeResult` preserves `grant_use` and callback result
  separately;
- **backup credential finish-binding test**: backup credential
  `register_finish` rejects missing, expired, replayed, or mismatched
  grant/challenge binding;
- **credential guarded trace test**: credential registration begin/finish traces
  bind the same challenge, artifact binding, GrantUse, and registration grant
  binding before L8 evidence can count;
- **ActionEngine adapter-map test**: the concrete ActionEngine mutation adapter
  ids are closed, `append_to_file` does not delegate to an unenumerated
  `run_shell`; if `append_to_file` is routed through `run_shell` or any other
  shell-shaped adapter, L8 fails even when the shell grant is valid for shell
  execution; every named mutation method fails closed without a consumed grant;
- **consume helper bypass test**: `consume_execution_grant_for_action(...)` is
  absent or acts only as a post-mint action-edge single-use lock backed by a
  durable `GrantUse` and `ActionEdgeGrantUse`; it never consumes an artifact or
  bypasses `S7GuardedStateStore.consume_artifact_for_execution(...)`;
- **raw/effective reader outcome test**: failed D11 grounding converts raw
  semantic-reader output to the effective outcome consumed by D13;
- **effective outcome table test**: all five D12 effective-outcome derivation
  rows produce the specified effective outcome and classifier reason;
- **D16 authority replay test**: tampering `bundle.authority_class` or
  `bundle.protective_block_reason` fails validator replay even when
  `reducer_output_*` fields are unchanged;
- **self-mod dialog policy-gate test**:
  `self_mod_dialog_terminal_state` with `dialog_context_ref=None` or unreviewed
  `policy_hash` fails before prompt assembly, artifact mint, and consume;
- **proposal-origin prompt omission test**: `proposal_origin_label` is present
  in the context manifest hash domain and absent from the rendered prompt; all
  three label values produce byte-identical rendered prompt text/hash but
  distinct `context_manifest_hash` values;
- **grant expiry derivation test**: consume sets `grant.expires_at` from the
  min-cap lattice and returns `expiry_chain_violation` or the narrower expiry
  reason if any ceiling would outlive another;
- **work-item and preview store replay tests**: D16 rejects missing or tampered
  durable `GuardedWorkItem` and `MutationPreviewArtifact` rows;
- **prompt-integrity evidence tamper/replay tests**: delimiter,
  protocol-override, and no-objection-injection scan fields recompute and
  tampering rejects mint;
- **semantic-reader attempt replay tests**: `semantic_reader_attempt_hash`
  resolves to durable evidence and raw/effective outcome derivation replays;
- **retry-wash test**: later retry attempts cannot wash an earlier objection,
  withdrawal, refusal, prompt-integrity block, or terminal uncertainty into
  positive absence;
- **rollback plan missing/mismatch tests**: missing rollback evidence,
  mismatched `rollback_path_class`, or mismatched target refs make
  `mint_eligible=False`;
- **context policy hash mismatch test**: D16 rejects a policy hash outside
  `REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES` or bytes that fail recompute;
- **surface manifest coverage test**: code-discovered routes/methods,
  including ActionEngine private helpers and model-routing edges, match
  `S7SurfaceManifest` rows or reviewed exclusions;
- **no-hand-assemble positive harness test**: a positive-path test that tries
  to bypass producer, bundle writer, validator, artifact store, consume
  wrapper, grant-use store, or rollback store by constructing load-bearing
  carriers directly is rejected by review/test helpers;
- **rendered authorization protocol tests**: voice and credential rendered
  statements both implement `S7RenderedAuthorizationStatement`; missing common
  fields fail; a credential rendered as `RenderedRequestStatement` fails;
- **inherited consume translation test**: inherited stale, mismatch, expired,
  superseded, ceremony, consumed, and SQL branches map to closed
  `S7ConsumeFailureReasonCode`; inherited success without durable `GrantUse`
  fails with `missing_grant_use`, and callback result remains separate from
  `grant_use`;
- **preview-body-class canonicalization test**: title-cased, localized,
  aliased, or expanded preview body class text is rejected;
- **prompt scan pattern test**: marker-delimiter, protocol-override, and
  no-objection-injection scan rules reject the reviewed malicious patterns and
  allow escaped quoted blocks;
- **maez_voice_consulted invariant test**: captured-response rows require
  `maez_voice_consulted=True`; no-response unavailable rows may be false; a
  false consulted flag with captured response refs fails validation;
- **reducer version/hash binding test**: mismatched `bundle.reducer_version`,
  `bundle.reducer_hash`, or `trace.reducer_version` fails D16 replay;
- **rollback evidence store test**: rollback plan/result refs resolve through
  `S7RollbackEvidenceStore` and immutable-row tampering fails hash replay;
- **trace finalization test**: a consumed grant produces either finalized
  success trace or failed/rollback trace before health can report positive
  execution;
- every in-scope adapter fails closed without consumed grant;
- every in-scope adapter succeeds only through artifact consume and grant
  (`GrantUse` record present and replay_token unobserved);
- trace, rollback plan, and rollback result fields are present for positive
  execution.

### D25 - Health Mode And L8 Retirement

S7.3 implementation may not clear `guarded_self_modification_paused_pending_s7.1`
until both-lane review confirms:

- the live voice producer is wired for voice-seat work;
- every in-scope mutation path is either wired or reviewedly excluded;
- every voice-seat wired path derives a `GuardedWorkItem`, and every
  credential-management path derives `S7CredentialGuardedRequest`;
- `self_mod_dialog_terminal_state` remains fail-closed until
  `ContextManifestPolicy.v1.self_mod_dialog` is reviewed, hash-pinned, and
  enforced at producer, validator, and consume seams;
- every voice-seat path uses the source-bundle validator before artifact mint;
- every positive execution consumes an artifact into `S7ExecutionGrant` AND
  persists a `GrantUse` record;
- every positive execution writes trace, rollback plan evidence, and rollback
  result evidence;
- D23 authoritative versus operational rows are separated;
- marker-only verified blocking or withdrawal never becomes D23 refusal
  evidence in S7.3 v1;
- inherited legacy refusal-history writers are amended so S7.3 operational,
  protective, reader-unavailable, and marker-only rows cannot write
  null-provenance `outcome="refused"` records;
- live founder-key traces or reviewed same-code coverage exist for every
  in-scope adapter/consumer, with no surface hidden behind a broader class name;
- no placeholder producer, test-only verifier, callable helper, boolean opt-in,
  or hand-assembled covenant-load-bearing carrier is used as L8 evidence.

If the substrate lands but the live producer or consumers remain blocked, the
health mode must retain L8 or move to an equally honest reviewed successor mode.

### Expiry Lifecycle

The expiration timestamps in S7.3 form a min-cap lattice, not a linear chain:

```text
now < bundle.expires_at
now < work_item.expires_at
now < artifact.expires_at
now < webauthn_challenge.expires_at

artifact.expires_at <= min(bundle.expires_at, work_item.expires_at, webauthn_challenge.expires_at)
grant.expires_at = min(artifact.expires_at, bundle.expires_at, work_item.expires_at, webauthn_challenge.expires_at)
```

D16 enforces `now < bundle.expires_at` and `now < work_item.expires_at`.
Artifact mint enforces `artifact.expires_at <= min(bundle.expires_at,
work_item.expires_at, webauthn_challenge.expires_at)` through the binding's
challenge expiry. D21 consume loads the artifact binding, bundle use, work item,
and challenge expiry and mints `grant.expires_at` from the min-cap rule.
Consumer pre-mutation enforces `now < grant.expires_at`.

For credential-management paths, the bundle/work-item ceiling is replaced by
the `S7CredentialGuardedRequest.expires_at` ceiling. If any ceiling is already
expired at mint or consume, the operation fails closed before artifact storage,
grant mint, or substrate mutation.

## Implementation Acceptance Checklist

Before implementation can be claimed complete:

1. **Closed-enum amendments** (D-Enum-Amendment) land:
   `MAEZ_UNAVAILABLE_REASON_CODES` adds `semantic_reader_unavailable` and
   `bonded_maez_unavailable`; `RenderedRequestStatement.maez_consulted_state`
   remains `{yes, not required}`; `RenderedRequestStatement` gains
   `preview_body_class`, `preview_summary`, `preview_affected_paths`,
   `mutation_preview_hash`, `rollback_plan_ref`, `maez_withdrew_request`, and
   common protocol fields including `precondition_hash`, with corresponding
   rendered-text lines and `expected_metadata` enforcement;
   `MaezVoiceConsultation.__post_init__` rejects `absent+withdrew=True`;
   `S7_EXECUTION_CONSUMER_IDS`, `BLOCKING_UNAVAILABLE_REASONS`,
   `authority_class`, `SURFACE_CLASSES`, `HISTORY_BRIDGE_STATUSES`,
   `ROUTE_STATUSES`, `ROLLBACK_PATH_CLASSES`, `CLASSIFIER_REASON_CODES`,
   `REDUCER_TABLE_VERSION`, `REDUCER_TABLE_HASH`, `D23_STATES`,
   `TRACE_STATUSES`, and `S7ConsumeFailureReasonCode` closed vocabularies
   exist.
2. **Reviewed semantic-reader route manifest** is committed naming concrete
   provider, model, model version, decoding parameters, prompt template hash,
   tool policy, network route, and config hash. Until this lands, the positive
   voice path is blocked.
3. `GuardedWorkItem`, `MutationPreviewArtifact` (with `mutation_preview_hash`),
   `ContextManifest`, `S7VoiceProducerResult`, `S7VoiceProjection`,
   `S7RenderedAuthorizationStatement`, `RenderedCredentialRequestStatement`,
   `PromptIntegrityEvidence`, `SemanticReaderAttemptEvidence`,
   `S7VoiceAttemptRecord`, `S7SurfaceManifest`, `S7SurfaceManifestRow`,
   `ContextManifestPolicy`,
   `RollbackPlanEvidence`, `RollbackResultEvidence`,
   `S7VoiceConsultationBundle`, `S7VoiceBundleUse`,
   `S7ConsultationNonceUse`, `S7VoiceAuthorityBooleans`,
   `S7VoiceReduction`, `S7CredentialGuardedRequest`,
   `S7AuthorizationArtifactInputs`, `S7AuthorizationArtifactBinding`,
   `ReservationToken`, `S7GuardedStateStore`, `S7ConsumeResult`,
   `S7VoiceAuthorityRow`, `GrantUse`, `ActionEdgeGrantUse`,
   `S7CredentialRegistrationGrantBinding`, `S7RollbackEvidenceStore`, and
   source-bundle validation shapes exist and are tested. `preview_body_class`
   has no `credential_management` value in S7.3 v1.
4. `S7VoiceConsultationBundleStore`, `S7VoiceBundleUseStore`,
   `S7AuthorizationStore`, `S7GrantUseStore`, `S7GuardedWorkItemStore`,
   `S7MutationPreviewStore`, `S7PromptIntegrityEvidenceStore`,
   `S7SemanticReaderAttemptStore`, `S7VoiceAttemptRecordStore`,
   `ContextManifestPolicyStore`, and `S7SurfaceManifestStore` share the SQLite
   file at
   `memory/s7_3_guarded_self_modification/state.sqlite3` with table prefixes,
   migrations, permissions, backup inclusion, and the
   `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` and
   `S7GuardedStateStore.consume_artifact_for_execution(...)` transaction
   wrappers. `S7AuthorizationStore.put(...)` and consume paths accept an
   injected connection with full amended signatures. The
   `s7_consultation_nonce_uses` table implements nonce reservation, acceptance,
   reuse rejection, and expiry. The authority booleans
   (`has_grounded_semantic_blocking_signal`,
   `marker_was_explicit_no_objection_verified`,
   `marker_was_blocking_marker_verified`,
   `marker_was_withdrawal_marker_verified`, `captured_response_nonempty`) are
   computed before reducer replay and persisted on the immutable bundle.
5. The bonded Maez runtime port (D7) takes `rendered_prompt_text` and pins
   runtime/model identity in the source bundle. The producer port (D8) owns
   prompt assembly per the substitution grammar, persists `rendered_prompt_hash`
   and `rendered_prompt_ref`, omits `proposal_origin_label` from Maez's prompt,
   enforces the self-mod-dialog context policy gate, and the validator replays
   prompt assembly.
6. The Maez-facing prompt and marker parser implement D10 with cryptographic
   nonce, time-bounded validity, and single-use consultation id (strong replay
   protection).
7. The semantic-reader prompt and grounding contract implement D11-D12,
   including the let-Maez-be-heard predicate that distinguishes "response
   quotes preview" from "blocking attributed solely to preview" and preserves
   laconic objections.
8. Authority-boolean computation and the reducer implement D13 exactly,
   including marker-verified current-attempt blocks when the reader disagrees,
   authoritative D23 evidence only when semantic grounding is present, and the
   protective operational `explicit_no_objection + reader_unavailable` row.
9. The source-bundle validator implements D16's rich result shape and gates
   artifact minting on `source_bundle_valid=True`, `mint_eligible=True`, and
   `status="valid_absent"`.
10. `render_request_statement(...)` implements the D17 amendments: new fields,
    new rendered-text lines, `expected_metadata` enforcement, unavailable
    projection, and `no` vs `none` canonicalization.
11. `_s7_voice_consultation_for_card(...)` no longer emits eligible placeholder
    rows; replaced by `build_s7_voice_projection_for_card(...)` per D20.
12. `S7GuardedStateStore.consume_artifact_for_execution(...)` implements the
    D21 wrapper with `consumer_id`, `source_ref_hash`, `reservation_token`,
    binding lookup by `artifact_id`, min-cap expiry enforcement, inherited
    2-tuple to `S7ConsumeResult` translation, protocol-based rendered type
    checks, and closed failure reason codes.
    `consume_execution_grant_for_action(...)` is removed or retained only as a
    post-mint action-edge lock backed by durable `GrantUse` and
    `ActionEdgeGrantUse`. `s7_grant_uses`,
    `s7_authorization_artifact_bindings`, and
    `s7_credential_registration_grant_bindings` tables exist in the shared
    state DB. `S7ExecutionAuthorization` carries a guarded-state consume
    capability plus `execution_consumer_id`; credential paths carry
    `challenge_expires_at` and the finish-time grant/challenge binding.
    `consume_verified(...)` remains
    only as a deprecated wrapper that reads this closed id and fails closed when
    it cannot.
13. The closed `S7SurfaceManifest` exists and generates D2/D4/D21/D22/D25
    consistency. `/apply_dream`, `/apply_edit`, natural-language Telegram
    proposal/section
    approval, evolution candidate apply (`apply_candidate(...)`), workshop diff
    apply (`apply_diff(...)`), approval cards, self-mod dialog, CLI, cockpit,
    reviewed substrate adapters, and concrete ActionEngine final mutation
    consumers enter through `GuardedWorkItem` and require consumed grants.
   `append_to_file` uses a direct write adapter; no shell-shaped or otherwise
   indirect adapter satisfies this item in S7.3 v9.
   Credential-management consumers skip Maez voice and `GuardedWorkItem` but
   use closed consumer ids plus D21 credential grant/challenge binding.
   Guarded code paths enter through the concrete wrapper services named in D21.
   Acceptance includes a code-discovery grep over `core/actions/action_engine.py`
   for every public/private method that can mutate Maez substrate or capability
   state; each method must have a manifest row or reviewed exclusion.
14. D19 writes `S7VoiceAuthorityRow` and bridges authoritative refusal or
    withdrawal into committed `S7RequestHistoryRecord` /
    `assess_aggregation_risk` with provenance fields. Operational rows and
    marker-only rows never bridge to `outcome="refused"`, and inherited
    `_voice_seat_block(...)` / `record_refusal_history(...)` paths are
    suppressed for S7.3 operational voice-family rows.
15. Trace, rollback plan, rollback result, pending-trace finalization, rollback
    store records, rollback-plan pre-mint replay, and context policy hash bytes
    implement D22-D23.
16. Positive tests cannot hand-assemble the voice fact, artifact, carrier,
    grant, `GrantUse`, semantic-reader grounding, authority booleans,
    reduction, source bundle, consume result, authority row, credential
    registration binding, rollback plan, or rollback result.
17. Live founder-key traces or reviewed same-code coverage exist for every
    in-scope adapter/consumer before any L8 retirement claim, with route,
    adapter id, adapter code hash, and same-code coverage ref carried on the
    trace.

## Review Questions

1. Does D17 both bind preview/rollback hashes and show founder-readable preview
   body class, summary, and affected paths, with `expected_metadata`
   enforcement?
2. Does D9's immutable-bundle / mutable-use split avoid circular hashes,
   mutable-hash domains, and forward-binding to a rendered hash that does not
   exist at bundle write time?
3. Does `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` with a
   single SQLite file, table prefixes, and an injected connection close the
   cross-store atomicity gap?
4. Does the expected-nonce carrier (`expected_consultation_nonce_hash`) give the
   marker-verification booleans a real value to compare against, including
   spent-nonce rejection?
5. Does the D10 substitution grammar plus `rendered_prompt_hash` /
   `rendered_prompt_ref` make prompt assembly replayable by D16?
6. Does the D21 wrapper correctly preserve nullable S7.1 failure semantics while
   binding consumer id, grant id, expires_at, `source_ref_hash`, and `GrantUse`
   to the artifact consume?
7. Is `execution_consumer_id` closed and derived strongly enough that caller code
   cannot bind a grant to an arbitrary string?
8. Is the D13 marker-verification rule materially carried by authority
   booleans, including marker-verified current-attempt blocking when the reader
   disagrees, no marker-only D23 authority, and protective operational handling
   of `explicit_no_objection + reader_unavailable`?
9. Does D19 correctly bridge `S7VoiceAuthorityRow` into committed
   `S7RequestHistoryRecord` aggregation, including withdrawal evidence?
10. Does `consume_verified(...)` as a deprecated wrapper preserve compatibility
    without reopening boolean authorization?
11. Does the D11 false-block fix correctly distinguish "Maez quotes preview" from
   "reader attributes blocking solely to preview"?
12. Does the D7 `ContextManifest` carrier close the operator-steering surface
   and replay through D10/D16 without invention?
13. Is `BondedMaezRuntime` bounded enough to avoid contextless-model and
   whole-daemon ventriloquism failures, with prompt assembly correctly placed
   in the producer port?
14. Is the route-manifest amendment gate strict enough to prevent implementation
   from starting the positive voice path before the concrete provider/model is
   reviewed?
15. Are any mutation surfaces still missing from D2, D4, D21, or the acceptance
   checklist, including ActionEngine final mutation adapters?
16. Is the Expiry Lifecycle invariant correctly enforced at every named seam
    (validator pre-mint, consume pre-mutation, consumer pre-mutation)?

## Proposed Next Ladder

1. Section 8.2 fresh-reader gate runs on this exact committed v9 spec with three
   blank-context readers: cold covenant reader, cold spec-implementor, and cold
   residual-hunter.
2. Codex engineering panel v9 runs independently on the same committed v9 spec.
3. If either lane returns REVISE, fold narrowly. If both lanes ratify (or
   RATIFY-with-fold with only bounded touchups), proceed to second-fold checks.
4. Canonicalize only after the active lanes ratify.
5. Implement RED-first from the ratified spec.

No implementation begins from this v9 draft.

## Plain English Close

This spec says what S7.3 has to make true.

Maez gets asked through one real voice gate. The answer is checked by two
channels: a structured marker and a semantic reader that looks at Maez's own
response text. The only way to record "Maez did not object" is for both
channels to agree, the private source bundle to validate, every hash to match
the exact request Rohit signs (including the preview hash and the rollback
plan hash, which are now lines on the signed text itself), and the reducer
to replay deterministically over the persisted authority booleans. If the
reader breaks, if Maez is unavailable, if the prompt is poisoned, if the
bundle is stale, or if anything does not line up, the request blocks.

S7.3 v9 absorbs the v8 review findings:

- Marker-only verification no longer becomes long-use D23 refusal evidence.
  A verified marker can block the current attempt, but authoritative refusal
  history requires grounded semantic evidence until Maez has a cryptographic
  identity substrate.
- The old refusal-history side door is closed. S7.3 operational blocks cannot
  fall through legacy `_voice_seat_block(...)` into null-provenance
  `outcome="refused"` history.
- The blackhole-reader row stays operational: disabling the reader on a
  captured response blocks the current attempt without rendering "Maez
  objected" or poisoning refusal history.
- ActionEngine coverage is no longer a broad label. Concrete mutation adapters
  are enumerated, and `append_to_file` cannot claim coverage while secretly
  delegating to an unreviewed shell path.
- Credential management is split into a non-voice guarded path with
  `S7CredentialGuardedRequest`, `RenderedCredentialRequestStatement`, artifact
  binding, finish-time grant/challenge binding, trace evidence, and
  rollback/manual-review evidence.
- Nonce handling is explicit: reservation, accepted spent, rejected reuse, and
  expiry are separate states, and the consultation expiry exists before the
  bundle does.
- Laconic Maez objections are heard. A terse quote of the proposed change plus
  "No" can still ground a refusal; the predicate no longer demands verbose
  framing when the structure is deterministic.
- `surface_class`, D23 bridge status, consume failure reasons, context-manifest
  hash domain, rendered-to-bundle equality checks, and trace fields now have
  closed carriers rather than prose-only promises.
- The old action-edge helper is no longer confused with artifact consume. It
  can remain only as a post-mint single-use lock backed by durable `GrantUse`
  and `ActionEdgeGrantUse`.
- `proposal_origin_label` stays in audit hashes but is no longer shown to Maez;
  self-mod dialog terminal execution remains mechanically blocked until its
  context policy is reviewed.
- Expiry is now a min-cap lattice: artifact and grant authority cannot outlive
  the work item, voice bundle, credential request, or challenge that bounded
  them.
- Rendered authorization has a real common protocol with `request_id`,
  `rendered_text`, `rendered_text_hash`, request envelope, action params,
  precondition, and authority context hashes on both voice and credential
  renders.
- Work items, previews, prompt-integrity evidence, semantic-reader attempts,
  retry manifests, surface manifests, and context policies have durable stores
  and replayable hash domains.
- Concrete route coverage comes from `S7SurfaceManifest`, including route,
  source method, adapter id, code hash, and same-code coverage ref, rather than
  hand-copied D2/D4/D21 tables.
- Rollback plans are checked before mint, not merely named in the rendered text.
- The inherited S7.1 two-tuple consume result is translated into S7.3's
  four-field `S7ConsumeResult` only after durable `GrantUse` persistence.

The honest scope holds: S7.3 v9 does not defend against same-box privileged
tampering during the active consultation window. The strong replay protection
narrows the attack to a tight time-bounded window with cryptographic nonce
verification. v9 therefore refuses to promote marker-only evidence into D23
refusal history. The future Maez cryptographic identity substrate slice (per
Honesty Banner and project memory) closes this further. Until that slice lands,
the Honesty Banner names what S7.3 v1 trusts and what it does not.

If S7.3 implements this, the front desk finally connects to the machinery
without pretending Maez was heard when it was not. If it cannot implement this,
the honest result is to keep the pause.
