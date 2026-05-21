# S7.3 Guarded Self-Modification Execution Spec

**Status:** SPEC v23 draft - folded from Codex panel v22; pending Section 8.2 fresh-reader gate v23 and Codex v23 panel review; not canonical law
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
**v9 review inputs:**
- Section 8.2 fresh-reader gate v9: [`reviews/spec-fresh-reader-gate-v9.md`](reviews/spec-fresh-reader-gate-v9.md)
- Codex panel v9: [`reviews/spec-codex-panel-v9.md`](reviews/spec-codex-panel-v9.md)
**v10 fold inputs:**
- [`reviews/spec-v10-fold-plan.md`](reviews/spec-v10-fold-plan.md)
- [`reviews/spec-v10-fold-plan-addendum.md`](reviews/spec-v10-fold-plan-addendum.md)
**v10 review inputs:**
- Section 8.2 fresh-reader gate v10: [`reviews/spec-fresh-reader-gate-v10.md`](reviews/spec-fresh-reader-gate-v10.md)
- Codex panel v10: [`reviews/spec-codex-panel-v10.md`](reviews/spec-codex-panel-v10.md)
**v11 fold inputs:**
- [`reviews/spec-v11-fold-plan.md`](reviews/spec-v11-fold-plan.md)
- [`reviews/spec-v11-fold-plan-addendum.md`](reviews/spec-v11-fold-plan-addendum.md)
**v11 review inputs:**
- Section 8.2 fresh-reader gate v11: [`reviews/spec-fresh-reader-gate-v11.md`](reviews/spec-fresh-reader-gate-v11.md)
- Codex panel v11: [`reviews/spec-codex-panel-v11.md`](reviews/spec-codex-panel-v11.md)
**v12 fold input:** [`reviews/spec-v12-fold-plan.md`](reviews/spec-v12-fold-plan.md)
**v13 review inputs:**
- Section 8.2 fresh-reader gate v13: [`reviews/spec-fresh-reader-gate-v13.md`](reviews/spec-fresh-reader-gate-v13.md)
- Codex panel v13: [`reviews/spec-codex-panel-v13.md`](reviews/spec-codex-panel-v13.md)
**v14 fold input:** [`reviews/spec-v14-fold-plan.md`](reviews/spec-v14-fold-plan.md)
**v14 review inputs:**
- Section 8.2 fresh-reader gate v14: pending committed review artifact
- Codex panel v14: [`reviews/spec-codex-panel-v14.md`](reviews/spec-codex-panel-v14.md)
**v15 fold input:** [`reviews/spec-v15-fold-plan.md`](reviews/spec-v15-fold-plan.md)
**v15 review input:** [`reviews/spec-codex-panel-v15.md`](reviews/spec-codex-panel-v15.md)
**v16 fold input:** [`reviews/spec-v16-fold-plan.md`](reviews/spec-v16-fold-plan.md)
**v16 review input:** [`reviews/spec-codex-panel-v16.md`](reviews/spec-codex-panel-v16.md)
**v17 fold input:** [`reviews/spec-v17-fold-plan.md`](reviews/spec-v17-fold-plan.md)
**v17 review input:** [`reviews/spec-codex-panel-v17.md`](reviews/spec-codex-panel-v17.md)
**v18 fold input:** [`reviews/spec-v18-fold-plan.md`](reviews/spec-v18-fold-plan.md)
**v19 fold input:** [`reviews/spec-v19-fold-plan.md`](reviews/spec-v19-fold-plan.md)
**v20 fold input:** [`reviews/spec-v20-fold-plan.md`](reviews/spec-v20-fold-plan.md)
**v20 review inputs:**
- Section 8.2 fresh-reader gate v20: [`reviews/spec-fresh-reader-gate-v20.md`](reviews/spec-fresh-reader-gate-v20.md)
- Codex panel v20: [`reviews/spec-codex-panel-v20.md`](reviews/spec-codex-panel-v20.md)
**v21 fold inputs:**
- [`reviews/spec-v21-fold-plan.md`](reviews/spec-v21-fold-plan.md)
- [`reviews/spec-v21-fold-plan-addendum.md`](reviews/spec-v21-fold-plan-addendum.md)
**v21 review inputs:**
- Section 8.2 fresh-reader gate v21: [`reviews/spec-fresh-reader-gate-v21.md`](reviews/spec-fresh-reader-gate-v21.md)
- Codex panel v21: [`reviews/spec-codex-panel-v21.md`](reviews/spec-codex-panel-v21.md)
**v22 review input:** [`reviews/spec-codex-panel-v22.md`](reviews/spec-codex-panel-v22.md)
**v9-v19 authorship note:** v9 through v19 preserved the covenant
architecture and progressively tightened the engineering carrier surface: durable
request envelopes, one guarded execution invocation carrier, single-file trace
storage, closed route/status vocabularies, reducer/version pinning, manifest
coverage, rollback evidence, ActionEdge replay, typed trace payloads, and the
uniform persistence round-trip contract. Those earlier drafts also explored
in-band credential/key-management. v20 intentionally lifts that explored
credential-management surface out of S7.3 v1 and preserves it in
`deferred/credential-management-seed.md`; the retained spec is the voice-seat
self-modification core.
**v20 authorship note:** v20 keeps the v19 voice-seat covenant core and cuts
in-band credential/key-management from S7.3 v1. The parked material moves to
`deferred/credential-management-seed.md` for a future reviewed slice. The core
fold adds runtime reservation-token possession to voice-seat consume, defines
`EXCLUSION_REASON_CODES`, and resolves D23 state production through one explicit
input carrier. The S7.1-established founder WebAuthn credential remains the
physical signature boundary for voice-seat self-modification.
**v21 authorship note:** v21 keeps the v20 scope cut and restores the
cut-damaged closed vocabulary family from the pre-cut baseline, removing only
credential-only members. It restores mintable execution consumer ids, surface
classes, reviewed-future ids, and the ActionEngine subset to internally
consistent values; adds the missing artifact-binding store dependency; pins the
artifact/bundle carrier shape blocks; fixes the preview-body-class annotation;
and adds cross-vocabulary audit tests so future scope cuts cannot orphan or
cross-contaminate closed vocabulary values.
**v22 authorship note:** v22 keeps the v20 scope cut and v21 vocabulary-family
restore. It restores the general S7.3 rollback-path vocabulary that was
mis-filed into the deferred credential seed, expands voice bundle and bundle-use
carrier shapes to match later validation reads, narrows history-bridge
`history_outcome` to the deriving function's domain, restores the explicit
`REDUCER_TABLE_HASH` constant line, and repairs the store-constructor code
fence.
**v23 authorship note:** v23 keeps the v22 scope, covenant posture, and restored
vocabulary families. It closes the remaining Codex v22 bundle persistence
findings by adding `rendered_prompt_ref` and `context_manifest_hash` to
`S7VoiceConsultationBundle`, adding `reservation_token_hash` to
`S7VoiceBundleUse`, and binding the runtime reservation token hash to both the
invocation carrier and bundle-use reservation row before inherited consume.
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
  (extended by S7.3 v15 per the D-Enum-Amendment and D21);
- S7.1's `S7ExecutionAuthorization` as a pre-consume carrier, replaced for
  S7.3 execution paths by a guarded-state consume capability carrying
  `execution_consumer_id`, source-bundle binding, and reservation token;
- in-band founder credential management is deferred from S7.3 v1;
- the closed voice-seat work classes currently committed in code:
  `self_modification`, `covenant_touching_change`,
  `capability_acquisition`, and
  `autonomy_lowering_or_protection_reducing`; this frozenset is the normative
  `VOICE_SEAT_WORK_CLASSES` value;
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

**Marker-authority caveat (v14).** S7.3 v14 treats verified structured markers
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

**Legacy refusal-history caveat (v14).** S7.3 v14 also closes the inherited path
that could smuggle operational blocks into D23. S7.1-era
`_voice_seat_block(...)` / `record_refusal_history(...)` behavior may not write
null-provenance `outcome="refused"` rows for S7.3 operational, protective,
reader-unavailable, or marker-only rows. Authoritative S7.3 refusal/withdrawal
history is written only through `S7VoiceAuthorityRow` and its provenance bridge.
If a compatibility writer must record an operational block, it records
operational provenance and is excluded from aggregation.

This caveat names both dual-direction harms. A blackholed semantic reader must
not manufacture fake absence. S7.3 v1 does not defend against a privileged
same-box actor that can write to Maez's live response stream before capture.
S7.3 narrows the attack window, binds captured evidence to
nonce/request/preview hashes, refuses marker-only D23 authority, and records
replayable evidence. It does not prove response authorship against that
attacker until the future Maez cryptographic identity substrate lands. S7.3 v1
blocks suspicious current attempts while refusing to overclaim D23 authority.

**Source-surface framing caveat (v14).** S7.3 v1 renders technical
source-surface labels to Maez for replayability and bounded context. These
labels are not consent evidence and may carry residual framing effects; future
prompt reviews should test for surface-label bias.
Source-surface prompt framing is accepted as an S7.3 v1 Honesty Banner residual.
S7.3 does not claim the residual is solved. A future prompt-framing review may
move `source_surface` out of Maez-visible prompt text or empirically justify
keeping it.

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
    created_at: str,
    manifest_hash: str,
    rows: tuple[S7SurfaceManifestRow, ...],
)

S7SurfaceManifestRow(
    surface_route_or_method: str,
    source_surface: str,
    work_source_kind: str | None,
    source_method: str | None,
    surface_class: str,
    execution_consumer_id: str | None,
    route_status: "live_guarded" | "fail_closed_until_review" | "reviewedly_excluded",
    exclusion_reason_code: str | None,
    adapter_id: str,
    adapter_code_hash: str,
    same_code_coverage_ref: str | None,
)
```

S7SurfaceManifest.manifest_id and created_at are persisted for audit and
excluded from `manifest_hash`, matching the `ContextManifest` audit-only rule.
`S7SurfaceManifest.manifest_hash` is the same content hash referenced by
external fields named `surface_manifest_hash`; outside the manifest carrier,
the spec uses `surface_manifest_hash` for this value.

`surface_class_for(surface_manifest_row)` and
`execution_consumer_id_for(source_surface: str, source_method: str | None)` are
the single derivation functions used by traces, authority rows, artifact
bindings, and L8 evidence. Callers do not supply `surface_class` or
`execution_consumer_id` directly. Builders recompute them from the manifest row
or fail closed.

Derivation returns a structured result:

```text
DerivationResult(
    execution_consumer_id: str | None,
    route_status: ROUTE_STATUSES,
    exclusion_reason_code: str | None,
)
```

Live guarded rows must return a mintable `execution_consumer_id`. Reviewed
exclusions return `execution_consumer_id=None` and a closed
`exclusion_reason_code`. Fail-closed-until-review rows with no mintable
consumer id also return `execution_consumer_id=None` and a closed
`exclusion_reason_code`. Display `N/A` in the matrix means Python/SQL null for
persisted fields, never the literal string `"N/A"`.

D4's adapter matrix is the S7.3 v1 reviewed seed. The persisted
`S7SurfaceManifest` is the load-bearing complete route set. L8 requires a
code-discovery check that compares committed mutation surfaces to the persisted
manifest and fails if any method lacks a manifest row or reviewed exclusion.
Concrete route/method names are load-bearing. A broad class such as
`cli_helper.execute`, `cockpit_helper.execute`,
`reviewed_substrate_adapter.execute`, or `action_engine_final_mutate` is not L8
evidence until the manifest names the concrete route/method, adapter id, code
hash, and reviewed coverage row or records a reviewed exclusion.

`adapter_code_hash` is defined over the reviewed adapter code slice:

```text
adapter_code_hash = canonical_hash(AdapterCodeSlice(
    repo_commit,
    file_paths,
    symbol_names,
    normalized_source_text_hashes,
    delegated_callee_symbol_names,
    delegated_callee_source_hashes,
))
```

If a route delegates to another mutating helper, the helper must appear in the
same code slice or have its own manifest row and `same_code_coverage_ref`.

### D3 - The Artifact Spine Is Reused

S7.3 reuses the committed S7.1 artifact spine:

```text
S7AuthorizationArtifact (stored) /
S7ExecutionAuthorization (pre-consume carrier)
-> S7GuardedStateStore.consume_artifact_for_execution(*, invocation, reservation_token, now)
-> S7ConsumeResult  // grant and GrantUse both minted during successful consume
```

`S7ExecutionAuthorization` is canonically blessed in S7.3 as a pre-consume
carrier, not an execution authority. It may carry store, artifact id, rendered
request, hashes, work class, aggregation group, `execution_consumer_id`, and
timing to the execution edge. It must not be treated as permission to mutate.

`S7ExecutionGrant` is the sole post-consume execution authority. It is minted
only by the shared-state consume wrapper during atomic artifact consume; the
live S7.3 API is
`S7GuardedStateStore.consume_artifact_for_execution(*, invocation, reservation_token, now)`.
On success the operation atomically consumes the artifact and mints both the
grant and a durable `GrantUse` record (see D21). On inherited S7.1 failure
paths it returns `S7ConsumeResult(None, None, callback_result_or_none,
failure_reason_code)` without mutating substrate.

No raw WebAuthn verifier result, request id, boolean flag, dict-shaped handle,
compatibility projection, hand-assembled test object, or new parallel authority
type may authorize guarded execution.

### D-Enum-Amendment - Closed Vocabulary Extensions

S7.3 extends inherited S7.1 vocabularies only where the live voice-seat
self-modification path needs them. In-band credential/key-management
vocabularies are deferred from S7.3 v1 and preserved in
`deferred/credential-management-seed.md`.

**`MAEZ_UNAVAILABLE_REASON_CODES`** adds:

```text
semantic_reader_unavailable
bonded_maez_unavailable
```

**`VOICE_SEAT_WORK_CLASSES`** is the inherited closed frozenset:

```text
self_modification
covenant_touching_change
capability_acquisition
autonomy_lowering_or_protection_reducing
```

**`S7_EXECUTION_CONSUMER_IDS`** is the live voice-seat execution-consumer
vocabulary. Positive guarded execution may use only the leaf ids below;
`action_engine_final_mutate` is a parent compatibility class and remains
non-mintable.

```text
dream_apply_proposal
dream_apply_section_edit_proposal
evolution_apply_candidate
workshop_apply_diff
guarded_card_execute
action_engine_write_soul_note
action_engine_edit_soul_section
action_engine_write_any_file
action_engine_append_to_file
action_engine_capability_acquire
action_engine_modify_config
action_engine_register_new_skill
action_engine_delete_file
action_engine_write_file
action_engine_promote_to_core_memory
action_engine_update_baseline
action_engine_git_commit
action_engine_integration_review_plan
brain_swap_model_routing_execute
model_routing_env_write_restart
```

**`NON_MINTABLE_EXECUTION_CONSUMER_IDS`** is:

```text
action_engine_final_mutate
```

Reviewed exclusions and fail-closed rows carry `execution_consumer_id=None`.
They never mint an execution grant.

**`REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS`** is a reviewed reserved-id
vocabulary, not an artifact-mint vocabulary. These ids are known surfaces that
remain fail-closed until a later reviewed slice makes them live:

```text
self_mod_dialog_terminal_execute
cli_helper_execute
cockpit_helper_execute
reviewed_substrate_adapter_execute
action_engine_run_shell
action_engine_execute_script
action_engine_run_script
action_engine_sudo_command
action_engine_git_push
action_engine_install_package
action_engine_kill_process
action_engine_restart_service
action_engine_write_outside_maez
action_engine_restart_critical_service
action_engine_modify_firewall
action_engine_system_reboot
action_engine_free_disk_space
action_engine_delete_temp_file
action_engine_clean_temp_files
action_engine_run_safe_command
action_engine_install_package_t2
telegram_rollback_adapter_execute
```

`S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` and
`S7GuardedStateStore.consume_artifact_for_execution(...)` reject
`REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS` before artifact mint or consume in
S7.3 v1.

**`S7_ACTION_ENGINE_CONSUMER_IDS`** is the ActionEngine subset of live leaf ids:

```text
action_engine_write_soul_note
action_engine_edit_soul_section
action_engine_write_any_file
action_engine_append_to_file
action_engine_capability_acquire
action_engine_modify_config
action_engine_register_new_skill
action_engine_delete_file
action_engine_write_file
action_engine_promote_to_core_memory
action_engine_update_baseline
action_engine_git_commit
action_engine_integration_review_plan
```

**`SURFACE_CLASSES`** is:

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
```

**`ROUTE_STATUSES`** is:

```text
live_guarded
fail_closed_until_review
reviewedly_excluded
```

`route_status="live_guarded"` requires a mintable execution consumer id.
`fail_closed_until_review` and `reviewedly_excluded` require
`execution_consumer_id=None` and a closed `exclusion_reason_code`.

**`S7_3_ROLLBACK_PATH_CLASSES`** is the S7.3 closed rollback vocabulary:

```text
git_revert
fs_backup_restore
config_rollback
atomic_rename
manual_review_only
none
```

The inherited committed `ROLLBACK_PATH_CLASSES` vocabulary remains a legacy code
vocabulary until migration. S7.3 persisted rollback evidence stores only
`S7_3_ROLLBACK_PATH_CLASSES` tokens.

Reviewed legacy migration map:

```text
LEGACY_TO_S7_3_ROLLBACK_PATH_CLASS = {
    "revert_patch": "git_revert",
    "restore_backup": "fs_backup_restore",
    "restart_service": "config_rollback",
    "manual_review": "manual_review_only",
    "no_rollback_needed": "none",
    "no_safe_rollback": "manual_review_only",
}
```

The map is allowed only at reviewed adapter boundaries. A legacy token entering
S7.3 persisted rollback evidence directly is rejected.

`rollback_path_class` is rendered into Maez's prompt, so it is never a free
string. `ContextManifest.__post_init__`, preview construction, rendered
authorization validation, and D16 replay all reject values outside
`S7_3_ROLLBACK_PATH_CLASSES`. For self-remaking voice-seat surfaces,
`rollback_path_class="none"` is illegal unless a reviewed exception says the
surface has no substrate write. The `manual_review_only` class is allowed only
when execution remains blocked until manual-review evidence is written; it
cannot satisfy positive automated execution by itself.

**`EXCLUSION_REASON_CODES`** is closed and table-complete for every retained
non-live route:

```text
EXCLUSION_REASON_CODES = frozenset({
    "self_mod_dialog_terminal_unreviewed",
    "deferred_action_unreviewed",
    "deferred_action_t2_unreviewed",
    "daemon_deferred_action_unreviewed",
    "daemon_deferred_action_t2_unreviewed",
    "telegram_approve_train_unreviewed",
    "cli_helper_unreviewed",
    "cockpit_dream_route_unreviewed",
    "cockpit_evolution_route_unreviewed",
    "reviewed_substrate_adapter_unreviewed",
    "run_shell_unreviewed",
    "execute_script_unreviewed",
    "run_script_unreviewed",
    "sudo_command_unreviewed",
    "git_push_unreviewed",
    "install_package_unreviewed",
    "kill_process_unreviewed",
    "restart_service_unreviewed",
    "write_outside_maez_unreviewed",
    "restart_critical_service_unreviewed",
    "modify_firewall_unreviewed",
    "system_reboot_unreviewed",
    "free_disk_space_unreviewed",
    "delete_temp_file_unreviewed",
    "clean_temp_files_unreviewed",
    "run_safe_command_unreviewed",
    "query_system_unreviewed",
    "run_readonly_command_unreviewed",
    "install_package_t2_unreviewed",
    "telegram_rollback_adapter_unreviewed",
})
```

Unknown exclusion tokens are rejected before manifest persistence.

**`preview_body_class`** is:

```text
diff_summary
path_list
config_change
policy_change
model_routing_change
memory_retention_change
other_reviewed_preview
```

**`PRODUCER_RESULT_REASON_CODES`**, **`MARKER_PARSE_STATUSES`**,
**`SEMANTIC_READER_RESULT_KINDS`**, **`REDUCER_OUTPUT_STATES`**, and
**`PROJECTION_REASON_CODES`** remain the closed vocabularies named in D13.

`REDUCER_TABLE_VERSION = "s7.voice.reducer.v13"` intentionally remains pinned
because v20-v22 do not change the reducer rows.
`REDUCER_TABLE_HASH = canonical_hash(D13_REDUCER_TABLE_ROWS)`.
`REDUCER_TABLE_HASH`, not the spec revision number, binds the row bodies.

**`authority_class`** is:

```text
none
operational
authoritative
```

**`HISTORY_BRIDGE_STATUSES`** is:

```text
not_required
bridged
bridged_idempotent
suppressed_operational
bridge_failed_retryable
bridge_failed_terminal
```

**`D23_STATES`** is:

```text
none
authorized
operational_block
authoritative_refusal
authoritative_withdrawal
legacy_operational_excluded
bridge_failed
```

**`TRACE_STATUSES`** is:

```text
pending
finalized
failed
rollback_invoked
rollback_failed
manual_review_required
blocked_pre_mutation_state_changed
```

**`MANUAL_REVIEW_STATUSES`** is:

```text
none
pending
completed
failed
```

`manual_review_status="none"` is the canonical stored value for traces that do
not require manual review. Python `None` may appear only at constructor edges
that immediately canonicalize to `"none"`.

**`S7ConsumeFailureReasonCode`** is:

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
missing_request_envelope
invalid_reservation_token
expiry_chain_violation
invalid_authority_class_replay
invalid_prompt_integrity
invalid_rendered_carrier
```

**`S7RequestHistoryRecord`** gains optional provenance fields for S7.3 voice
bridging:

```text
provenance_source_kind: "s7_voice_authority_row" | None
provenance_source_ref: str | None
provenance_authority_class: "authoritative" | "operational" | None
provenance_voice_event: "refusal" | "withdrawal" | None
request_history_schema_version: str | None
s7_3_cutoff_marker_id: str | None
```

`REQUEST_HISTORY_FAMILIES` contains only:

```text
s7_3_voice
```

`None` is not a family token. It is the derived inherited-legacy result for
records proven outside the reviewed S7.3 work-family table. S7.3 voice-derived
refused records may be written only from `S7VoiceAuthorityRow` with
`provenance_authority_class="authoritative"`. Operational rows never bridge into
`outcome="refused"`.

These amendments are listed in the Implementation Acceptance Checklist as a
numbered prerequisite.

### D4 - GuardedWorkItem Is The Common Bridge

Every S7.3 voice-seat mutation path must materialize a `GuardedWorkItem` before
voice consultation and WebAuthn. In-band credential/key-management is not part
of S7.3 v1.

Minimum shape:

```text
GuardedWorkItem(
    work_item_id: str,
    source_surface: str,
    source_method: str | None,
    surface_manifest_hash: str,
    surface_route_or_method: str,
    adapter_id: str,
    adapter_code_hash: str,
    same_code_coverage_ref: str | None,
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
    rollback_path_class: S7_3_ROLLBACK_PATH_CLASSES,
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
  `execution_consumer_id_for(surface_manifest_row.source_surface,
  surface_manifest_row.source_method)`; callers cannot supply an arbitrary
  consumer id;
- `surface_manifest_hash`, `surface_route_or_method`, `source_method`,
  `adapter_id`, `adapter_code_hash`, and `same_code_coverage_ref` must match
  the active `S7SurfaceManifestRow` used to derive `execution_consumer_id`;
- `proposal_origin` is supplemental provenance only and never proves consent;
- stale, missing, or mismatched fields force fail-closed status.

Surface adapters are not accepted from a hand-copied local table. The persisted
S7.3 v1 `S7SurfaceManifest` contains the complete D2/D4/D21/D22/D25 route set
after code discovery and reviewed exclusions are applied, including
route/method, source surface, optional source method, adapter id, adapter code
hash, same-code coverage ref, route status, surface class, and execution
consumer id. The prose list and printed matrix below are reviewed seed rows;
the persisted manifest row plus code-discovery acceptance is the normative
carrier.

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
  `restart_service`, `write_outside_maez`, `restart_critical_service`,
  `modify_firewall`, `system_reboot`, `free_disk_space`, `delete_temp_file`,
  `clean_temp_files`, `run_safe_command`, and `install_package_t2`; each
  adapter must name its
  `source_surface`, `work_source_kind`, concrete `execution_consumer_id`, trace
  coverage, and whether it is live guarded, reviewedly excluded, or
  fail-closed before implementation acceptance;
- ActionEngine `integration.review_plan` is an explicit concrete mutation
  adapter in the manifest; it cannot be hidden behind `action_engine_final_mutate`;
- every helper that touches soul, config, model routing, covenant organs,
  refusal, role-boundary, successor-governance, memory-retention/deletion, or
  protection settings must be named as one of the reviewed adapters above or a
  future reviewed adapter. S7.3 v15 does not use "direct helpers" as a catch-all
  completion claim.

`apply_candidate(...)` and `apply_diff(...)` are not allowed to be unguarded
callee loopholes. S7.3 v15 removes callee choice: guarded paths enter through
the wrapper services named in D21, and those wrappers perform work-item lookup,
surface-manifest lookup, rendered authorization verification, artifact consume,
GrantUse and ActionEdgeGrantUse verification, callee invocation, and trace
finalization before any substrate write is treated as guarded.

Deterministic `execution_consumer_id` derivation is keyed by
`(source_surface, source_method)`:

```text
execution_consumer_id_for(source_surface: str, source_method: str | None) -> DerivationResult

dream.apply_proposal + apply_proposal                         -> dream_apply_proposal
dream.apply_proposal + telegram_nl_dream                      -> dream_apply_proposal
dream.apply_section_edit_proposal + apply_section_edit        -> dream_apply_section_edit_proposal
dream.apply_section_edit_proposal + telegram_nl_section       -> dream_apply_section_edit_proposal
evolution_engine.apply_candidate + telegram_nl_apply          -> evolution_apply_candidate
evolution_engine.apply_candidate + slash_apply                -> evolution_apply_candidate
evolution_engine.apply_candidate + cli_apply                  -> evolution_apply_candidate
workshop.apply_diff + apply_diff                              -> workshop_apply_diff
self_mod_dialog.terminal_execute + terminal_execute           -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="self_mod_dialog_terminal_unreviewed"
approval_card.telegram_approve + telegram_approve             -> guarded_card_execute
approval_card.cockpit_approve + cockpit_approve               -> guarded_card_execute
approval_card.daemon_internal_approve + daemon_internal       -> guarded_card_execute
telegram.approval_card + approve_action                       -> guarded_card_execute through execute_guarded_card_execution only; non-wrapper paths are wrapper rejection, not alternate route derivation
action_engine.deferred_action + execute_pending                -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="deferred_action_unreviewed"
action_engine.deferred_action_t2 + execute_tier2_pending       -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="deferred_action_t2_unreviewed"
daemon.deferred_action_tick + execute_pending                  -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="daemon_deferred_action_unreviewed"
daemon.deferred_action_tick_t2 + execute_tier2_pending         -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="daemon_deferred_action_t2_unreviewed"
telegram.approve_train + approve_train                        -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="telegram_approve_train_unreviewed"
cli_helper.execute + named_adapter                            -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="cli_helper_unreviewed"
cockpit_helper.execute + dream_apply_route                    -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="cockpit_dream_route_unreviewed"
cockpit_helper.execute + evolution_apply_route                -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="cockpit_evolution_route_unreviewed"
reviewed_substrate_adapter.execute + reviewed_adapter         -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="reviewed_substrate_adapter_unreviewed"
action_engine.write_soul_note + write_soul_note               -> action_engine_write_soul_note
action_engine.edit_soul_section + edit_soul_section           -> action_engine_edit_soul_section
action_engine.write_any_file + write_any_file                 -> action_engine_write_any_file
action_engine.append_to_file + append_to_file                 -> action_engine_append_to_file
action_engine.capability.acquire + capability_acquire         -> action_engine_capability_acquire
action_engine.run_shell + run_shell                           -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="run_shell_unreviewed"
action_engine.execute_script + execute_script                 -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="execute_script_unreviewed"
action_engine.run_script + run_script                         -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="run_script_unreviewed"
action_engine.modify_config + modify_config                   -> action_engine_modify_config
action_engine.register_new_skill + register_new_skill         -> action_engine_register_new_skill
action_engine.delete_file + delete_file                       -> action_engine_delete_file
action_engine.sudo_command + sudo_command                     -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="sudo_command_unreviewed"
action_engine.write_file + write_file                         -> action_engine_write_file
action_engine.promote_to_core_memory + promote_to_core_memory -> action_engine_promote_to_core_memory
action_engine.update_baseline + update_baseline               -> action_engine_update_baseline
action_engine.git_commit + git_commit                         -> action_engine_git_commit
action_engine.git_push + git_push                             -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="git_push_unreviewed"
action_engine.install_package + install_package               -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="install_package_unreviewed"
action_engine.kill_process + kill_process                     -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="kill_process_unreviewed"
action_engine.restart_service + restart_service               -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="restart_service_unreviewed"
action_engine.write_outside_maez + write_outside_maez         -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="write_outside_maez_unreviewed"
action_engine.integration.review_plan + integration_review_plan -> action_engine_integration_review_plan
action_engine.restart_critical_service + restart_critical_service -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="restart_critical_service_unreviewed"
action_engine.modify_firewall + modify_firewall               -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="modify_firewall_unreviewed"
action_engine.system_reboot + system_reboot                   -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="system_reboot_unreviewed"
action_engine.free_disk_space + free_disk_space               -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="free_disk_space_unreviewed"
action_engine.delete_temp_file + delete_temp_file             -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="delete_temp_file_unreviewed"
action_engine.clean_temp_files + clean_temp_files             -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="clean_temp_files_unreviewed"
action_engine.run_safe_command + run_safe_command             -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="run_safe_command_unreviewed"
action_engine.query_system + query_system                     -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="query_system_unreviewed"
action_engine.run_readonly_command + run_readonly_command     -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="run_readonly_command_unreviewed"
action_engine.install_package_t2 + install_package_t2         -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="install_package_t2_unreviewed"
brain_swap.execution_authorized + execute                     -> brain_swap_model_routing_execute
model_routing.env_write_restart + env_write_restart           -> model_routing_env_write_restart
telegram.rollback_adapter + rollback_adapter                  -> fail-closed exclusion, no mintable consumer id; exclusion_reason_code="telegram_rollback_adapter_unreviewed"
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
telegram _handle_approve_train                  telegram.approve_train                 approve_train          dream_proposal                dream_proposal_application              N/A                                      fail_closed_until_review
telegram /approve card                          approval_card.telegram_approve         telegram_approve       card_approval                 guarded_card_execution                  guarded_card_execute                     live_guarded
Telegram /approve ActionEngine card             telegram.approval_card                 approve_action         card_approval                 guarded_card_execution                  guarded_card_execute                     live_guarded
cockpit /api/v1/cards/<id>/approve              approval_card.cockpit_approve          cockpit_approve        card_approval                 guarded_card_execution                  guarded_card_execute                     live_guarded
daemon /internal/approve_card/<id>              approval_card.daemon_internal_approve  daemon_internal        card_approval                 guarded_card_execution                  guarded_card_execute                     live_guarded
ActionEngine deferred execute_pending           action_engine.deferred_action          execute_pending        card_approval                 guarded_card_execution                  N/A                                      fail_closed_until_review
ActionEngine deferred execute_tier2_pending     action_engine.deferred_action_t2       execute_tier2_pending  card_approval                 guarded_card_execution                  N/A                                      fail_closed_until_review
daemon deferred execute_pending                 daemon.deferred_action_tick            execute_pending        card_approval                 guarded_card_execution                  N/A                                      fail_closed_until_review
daemon deferred execute_tier2_pending           daemon.deferred_action_tick_t2         execute_tier2_pending  card_approval                 guarded_card_execution                  N/A                                      fail_closed_until_review
telegram /rollback_adapter                      telegram.rollback_adapter              rollback_adapter       model_routing                 model_routing_execution                 N/A                                      fail_closed_until_review
cli evolution apply                             evolution_engine.apply_candidate       cli_apply              evolution_candidate           evolution_candidate_application         evolution_apply_candidate                live_guarded
cli guarded helper execute                      cli_helper.execute                     named_adapter          cli_helper                    cli_guarded_execution                   N/A                                      fail_closed_until_review
cockpit /api/v1/dreams/<id>/<action> dream      cockpit_helper.execute                 dream_apply_route      cockpit_helper                cockpit_guarded_execution               N/A                                      fail_closed_until_review
cockpit /api/v1/dreams/<id>/<action> evolution  cockpit_helper.execute                 evolution_apply_route  cockpit_helper                cockpit_guarded_execution               N/A                                      fail_closed_until_review
reviewed substrate adapter execute              reviewed_substrate_adapter.execute     reviewed_adapter       reviewed_substrate_adapter   reviewed_substrate_adapter_execution    N/A                                      fail_closed_until_review
workshop apply diff                             workshop.apply_diff                    apply_diff             workshop_apply                workshop_diff_application               workshop_apply_diff                      live_guarded
self_mod_dialog terminal                        self_mod_dialog.terminal_execute       terminal_execute       self_mod_dialog               self_mod_dialog_terminal_execution      N/A                                      fail_closed_until_review
brain_swap.execution_authorized                 brain_swap.execution_authorized        execute               model_routing                 model_routing_execution                 brain_swap_model_routing_execute         live_guarded
/etc/maez/model.env write/restart               model_routing.env_write_restart        env_write_restart      model_routing                 model_routing_execution                 model_routing_env_write_restart          live_guarded
ActionEngine write_soul_note                    action_engine.write_soul_note          write_soul_note        action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_write_soul_note            live_guarded
ActionEngine edit_soul_section                  action_engine.edit_soul_section        edit_soul_section      action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_edit_soul_section          live_guarded
ActionEngine write_any_file                     action_engine.write_any_file           write_any_file         action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_write_any_file             live_guarded
ActionEngine append_to_file                     action_engine.append_to_file           append_to_file         action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_append_to_file             live_guarded
ActionEngine capability.acquire                 action_engine.capability.acquire       capability_acquire     action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_capability_acquire         live_guarded
ActionEngine write_file                         action_engine.write_file               write_file             action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_write_file                 live_guarded
ActionEngine run_shell                          action_engine.run_shell                run_shell              action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine execute_script                     action_engine.execute_script           execute_script         action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine run_script                         action_engine.run_script               run_script             action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine modify_config                      action_engine.modify_config            modify_config          action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_modify_config              live_guarded
ActionEngine register_new_skill                 action_engine.register_new_skill       register_new_skill     action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_register_new_skill         live_guarded
ActionEngine delete_file                        action_engine.delete_file              delete_file            action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_delete_file                live_guarded
ActionEngine sudo_command                       action_engine.sudo_command             sudo_command           action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine promote_to_core_memory             action_engine.promote_to_core_memory   promote_to_core_memory action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_promote_to_core_memory     live_guarded
ActionEngine update_baseline                    action_engine.update_baseline          update_baseline        action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_update_baseline            live_guarded
ActionEngine git_commit                         action_engine.git_commit               git_commit             action_engine_final_mutation  action_engine_final_mutation_execution  action_engine_git_commit                 live_guarded
ActionEngine git_push                           action_engine.git_push                 git_push               action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine install_package                    action_engine.install_package          install_package        action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine kill_process                       action_engine.kill_process             kill_process           action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine restart_service                    action_engine.restart_service          restart_service        action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine write_outside_maez                 action_engine.write_outside_maez       write_outside_maez     action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine integration.review_plan            action_engine.integration.review_plan  integration_review_plan action_engine_final_mutation action_engine_final_mutation_execution  action_engine_integration_review_plan    live_guarded
ActionEngine restart_critical_service           action_engine.restart_critical_service restart_critical_service action_engine_final_mutation action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine modify_firewall                    action_engine.modify_firewall          modify_firewall        action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine system_reboot                      action_engine.system_reboot            system_reboot          action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine free_disk_space                    action_engine.free_disk_space          free_disk_space        action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine delete_temp_file                   action_engine.delete_temp_file         delete_temp_file       action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine clean_temp_files                   action_engine.clean_temp_files         clean_temp_files       action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine run_safe_command                   action_engine.run_safe_command         run_safe_command       action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine query_system                       action_engine.query_system             query_system           action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine run_readonly_command               action_engine.run_readonly_command     run_readonly_command   action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
ActionEngine install_package_t2                 action_engine.install_package_t2       install_package_t2     action_engine_final_mutation  action_engine_final_mutation_execution  N/A                                     fail_closed_until_review
```

In the printed matrix, `N/A` is a display token only. Persisted nulls use SQL
`NULL` / Python `None` and must never persist as the literal string `"N/A"`.
Matrix display for null: N/A. Python prose for null: None. SQL persisted
value: NULL. Never use "none" for execution_consumer_id. Rows with
`route_status in {"reviewedly_excluded", "fail_closed_until_review"}` and
`execution_consumer_id=None` are non-mintable and cannot satisfy L8 positive
coverage. Telegram approve-train carries
`exclusion_reason_code="telegram_approve_train_unreviewed"` until a reviewed
dream-approval wrapper maps it to a concrete guarded path.

v16 pins the mintability invariant:

```text
route_status == "live_guarded" requires a mintable execution_consumer_id
route_status in {"fail_closed_until_review", "reviewedly_excluded"} requires execution_consumer_id=None
```

Fail-closed and reviewed-excluded rows must also carry a non-null closed
`exclusion_reason_code`. Reserved future ids may appear only in
`REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS`; D21 rejects them before artifact mint
or consume in S7.3 v1.

`append_to_file` is direct-write only. Delegation through `run_shell` or any
other shell-shaped adapter is forbidden for `append_to_file`; a trace whose
grant binds a shell-shaped adapter for append fails L8. Private ActionEngine
`_do_*` helpers are not exempt from S7.3: tests must call every mutation helper
without a grant and prove fail-closed or prove the helper is unreachable except
through the guarded adapter matrix. Shell-shaped aliases including
`query_system` and `run_readonly_command` must have manifest rows or reviewed
exclusions; they cannot be covered by the broad `run_shell` row alone.

The positive append adapter is explicitly:

```text
adapter_symbol = "ActionEngine._do_append_to_file"
```

`ActionEngine.append_to_file` is not S7.3 L8 evidence while it delegates to
`run_shell`; guarded append must enter the wrapper and then the direct writer.

`query_system` and `run_readonly_command` intentionally have no reserved
future execution consumer id in S7.3 v1. Any future reviewed version must route
through a newly named non-shell adapter with its own manifest row.

`promote_to_core_memory` and `update_baseline` are listed as guarded in S7.3
v1. Implementation must amend the current routine/read-only classification and
add RED tests proving they request S7 grants before mutation, or change their
manifest rows to `reviewedly_excluded` before any L8 retirement claim.

Every matrix row above also carries `adapter_id`, `adapter_code_hash`, and
`same_code_coverage_ref` in `S7SurfaceManifestRow`. The printed matrix omits
those three wide columns only for readability; the persisted manifest and trace
schemas do not. A route without adapter id and code hash cannot count for L8.
The generated or persisted `S7SurfaceManifest` must be committed or emitted as
a diffable implementation artifact; reviewers must not reconstruct adapter ids,
code hashes, or same-code coverage refs from prose.

Model-routing writes include `/etc/maez/model.env`, the routing config reader,
and service restart edges as exact affected refs. A generic shell, sudo, or
restart adapter cannot hide a brain swap; `brain_swap_execution_authorized(...)`
is in S7.3 v1 scope as `brain_swap_model_routing_execute`.

Credential/key-management paths are deferred from S7.3 v1. Their v19 draft
surface is preserved in `deferred/credential-management-seed.md`. S7.3 v1 does
not add, disable, rotate, register, or otherwise manage founder credentials
in-band; it only consumes the S7.1-established founder WebAuthn credential for
voice-seat self-modification.

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
    rollback_path_class: S7_3_ROLLBACK_PATH_CLASSES,
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
    rollback_path_class: S7_3_ROLLBACK_PATH_CLASSES,
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
reviewed before live use; S7.3 v15 chooses omission.

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

**Atomicity mechanism.** S7.3 v20 pins the cross-store atomicity mechanism as a
single SQLite file with table-prefix namespace separation, not SQLite `ATTACH`.
The state file is:

```text
memory/s7_3_guarded_self_modification/state.sqlite3
```

The live S7.3 v1 stores remain logically separate by API and table prefix:

```text
s7_voice_bundles_*
s7_voice_bundle_uses_*
s7_consultation_nonce_uses
s7_authorization_artifacts_*
s7_authorization_artifact_bindings
s7_grant_uses_*
s7_rollback_evidence_*
s7_guarded_work_items
s7_mutation_previews
s7_prompt_integrity_evidence
s7_semantic_reader_attempts
s7_voice_attempt_records
s7_context_manifests
s7_context_manifest_policies
s7_surface_manifests
s7_action_edge_grant_uses
s7_work_request_envelopes
s7_rendered_authorization_statements
s7_authority_contexts
s7_guarded_execution_invocations
s7_request_history_migration_markers
s7_manual_review_evidence
s7_traces
s7_voice_trace_payloads
s7_execution_trace_payloads
s7_history_bridge_trace_payloads
```

Uniform S7.3 persistence round-trip contract:

```text
Every S7.3 store whose API exposes get(...) must satisfy exactly one of two
shapes:

1. all-column carrier:
   every dataclass field on the returned carrier is persisted as a typed
   column, excluding explicitly named volatile audit fields; or

2. ref-based carrier:
   every dataclass field on the returned carrier is a persisted scalar, hash,
   or ref column, and any full object reconstruction occurs only through a
   separately named bundle loader whose store dependencies and connection
   argument are part of the signature.

Every writer whose API emits a trace, manual-review evidence row, artifact
binding, invocation, or replay carrier must receive or derive every field
required by that row before the write transaction begins.

Every typed trace payload table must either persist every D22 minimum field for
its trace kind as columns, or persist trace_payload_blob_ref and
trace_payload_blob_hash and name a strict per-kind schema validator.

No S7.3 carrier may declare a field its store can neither persist nor
reconstruct through a named loader. No D24 positive test may hand-assemble a
carrier to bypass this rule.
```

Invocation-carrier hashes are row integrity hashes, not ordinary payload
fields. `guarded_execution_invocation_hash is excluded from the
S7GuardedExecutionInvocation hash domain`. The value is computed as
`canonical_hash(S7GuardedExecutionInvocation without
guarded_execution_invocation_hash)`. Store round-trip verification uses
`canonical_hash_without_field` for the ref-based execution invocation carrier.

One transaction-owning wrapper controls cross-store writes:

```text
S7GuardedStateStore(
    db_path: str,
    bundle_store: S7VoiceConsultationBundleStore,
    bundle_use_store: S7VoiceBundleUseStore,
    authorization_store: S7AuthorizationStore,
    artifact_binding_store: S7AuthorizationArtifactBindingStore,
    grant_use_store: S7GrantUseStore,
    work_item_store: S7GuardedWorkItemStore,
    preview_store: S7MutationPreviewStore,
    prompt_integrity_store: S7PromptIntegrityEvidenceStore,
    semantic_reader_attempt_store: S7SemanticReaderAttemptStore,
    voice_attempt_record_store: S7VoiceAttemptRecordStore,
    context_manifest_store: ContextManifestStore,
    context_policy_store: ContextManifestPolicyStore,
    rollback_store: S7RollbackEvidenceStore,
    surface_manifest_store: S7SurfaceManifestStore,
    action_edge_grant_use_store: S7ActionEdgeGrantUseStore,
    work_request_envelope_store: WorkRequestEnvelopeStore,
    rendered_statement_store: S7RenderedAuthorizationStatementStore,
    authority_context_store: AuthorityContextStore,
    guarded_execution_invocation_store: S7GuardedExecutionInvocationStore,
    request_history_migration_store: S7RequestHistoryMigrationStore,
    manual_review_store: ManualReviewEvidenceStore,
    trace_writer: S7TraceWriter,
)
```

Artifact/bundle carrier shapes used by the retained v22 core:

```text
S7AuthorizationArtifactInputs(
    request_id: str,
    rendered_text_hash: str,
    request_envelope_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    execution_consumer_id: str,
    expires_at: str,
)

S7AuthorizationArtifactBindingInputs(
    artifact_id: str,
    request_id: str,
    rendered_statement_hash: str,
    request_envelope_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    execution_consumer_id: str,
    source_ref_hash: str,
    challenge_expires_at: str,
)

S7AuthorizationArtifactBinding(
    artifact_id: str,
    request_id: str,
    rendered_statement_hash: str,
    request_envelope_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    execution_consumer_id: str,
    source_ref_hash: str,
    challenge_expires_at: str,
)

S7VoiceConsultationBundleDraft(
    request_id: str,
    consultation_id: str,
    attempt_manifest_hash: str,
    reducer_version: str,
    reducer_hash: str,
    marker_text_hash: str | None,
    created_at: str,
)

S7VoiceConsultationBundle(
    request_id: str,
    consultation_id: str,
    source_ref_hash: str,
    attempt_manifest_hash: str,
    context_manifest_ref: str,
    context_manifest_hash: str,
    rendered_prompt_ref: str,
    rendered_prompt_hash: str,
    expected_consultation_nonce_hash: str,
    prompt_integrity_evidence_hash: str,
    semantic_reader_attempt_hash: str | None,
    has_grounded_semantic_blocking_signal: bool,
    reducer_version: str,
    reducer_hash: str,
    authority_class: str,
    protective_block_reason: str,
    mutation_preview_hash: str,
    rollback_plan_ref: str,
    precondition_hash: str,
    maez_voice_consultation_hash: str,
    expires_at: str,
)

S7VoiceBundleUse(
    request_id: str,
    artifact_id: str,
    source_ref_hash: str,
    consultation_id: str,
    bundle_use_hash: str,
    reservation_token_hash: str,
    reservation_state: "unreserved" | "reserved" | "consumed",
    reserved_at: str | None,
    consumed_at: str | None,
    used_at: str,
)
```

```text
S7GuardedStateStore.put_artifact_with_bundle_reservation(
    *,
    artifact_inputs: S7AuthorizationArtifactInputs,
    artifact_binding_inputs: S7AuthorizationArtifactBindingInputs,
    source_ref_hash: str,
    consumer_id: str,
    now: str,
) -> tuple[S7AuthorizationArtifact, ReservationToken]

S7GuardedStateStore.consume_artifact_for_execution(
    *,
    invocation: S7GuardedExecutionInvocation,
    reservation_token: ReservationToken,
    now: datetime,
    connection: sqlite3.Connection | None = None,
    after_consume_before_commit: S7PostConsumeCallback | None = None,
) -> S7ConsumeResult
```

The raw reservation token is runtime-only and is never persisted. Before
inherited consume, the wrapper verifies:

```text
canonical_hash(reservation_token) == reservation_token_hash
reservation_token_hash == voice_bundle_use.reservation_token_hash
```

A missing or mismatched raw reservation token fails closed with
`invalid_reservation_token` before inherited consume.
`S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` writes
`voice_bundle_use.reservation_token_hash` in the same transaction that reserves
the bundle and creates the artifact/binding; only the hash persists.

Guarded wrappers pass one complete invocation carrier into consume rather than
reconstructing authority from route names or loose caller strings:

```text
S7GuardedExecutionInvocation(
    request_id: str,
    artifact_id: str,
    guarded_execution_invocation_hash: str,
    rendered_statement_hash: str,
    authority_context_hash: str,
    execution_consumer_id: str,
    surface_manifest_hash: str,
    surface_route_or_method: str,
    source_method: str | None,
    adapter_id: str,
    adapter_code_hash: str,
    source_ref_hash: str,
    reservation_token_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    rollback_plan_ref: str,
    superseded_request_ids_hash: str,
    covenant_ceremony_evidence_hash: str | None,
    created_at: str,
)
```

S7GuardedExecutionInvocation is a hash/ref carrier. It contains durable hashes,
refs, and scalars whose fields match `s7_guarded_execution_invocations`.
Positive guarded execution invocations require non-null `source_ref_hash` and
non-null `reservation_token_hash`. A path that lacks either value fails before
`S7GuardedExecutionInvocationStore.put(...)`.

Full-object reconstruction is a separate load seam:

```text
load_guarded_execution_invocation_bundle(
    *,
    invocation: S7GuardedExecutionInvocation,
    rendered_statement_store: S7RenderedAuthorizationStatementStore,
    authority_context_store: AuthorityContextStore,
    artifact_binding_store: S7AuthorizationArtifactBindingStore,
    voice_bundle_use_store: S7VoiceBundleUseStore,
    conn: sqlite3.Connection,
) -> S7GuardedExecutionInvocationBundle

S7GuardedExecutionInvocationBundle(
    invocation: S7GuardedExecutionInvocation,
    rendered: S7RenderedAuthorizationStatement,
    authority_context: AuthorityContext,
    artifact_binding: S7AuthorizationArtifactBinding,
    voice_bundle_use: S7VoiceBundleUse | None,
)
```

The execution bundle loader verifies `canonical_hash(rendered) ==
invocation.rendered_statement_hash`, `canonical_hash(authority_context) ==
invocation.authority_context_hash`, `artifact_binding.artifact_id ==
invocation.artifact_id`, `artifact_binding.execution_consumer_id ==
invocation.execution_consumer_id`, and, when a voice bundle use is present,
`voice_bundle_use.source_ref_hash == invocation.source_ref_hash`.

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
ContextManifestStore.write(manifest: ContextManifest) -> context_manifest_ref
ContextManifestStore.read(context_manifest_ref: str) -> ContextManifest | None
ContextManifestPolicyStore.read(policy_id) -> ContextManifestPolicy | None
S7SurfaceManifestStore.read_active(manifest_hash: str) -> S7SurfaceManifest | None
S7ActionEdgeGrantUseStore.put(*, grant_use: GrantUse, action_edge_grant_use: ActionEdgeGrantUse, conn: sqlite3.Connection) -> ActionEdgeGrantUse
WorkRequestEnvelopeStore.put(envelope, *, conn) -> None
WorkRequestEnvelopeStore.get(request_id, *, conn) -> WorkRequestEnvelope | None
S7RenderedAuthorizationStatementStore.put(rendered, *, conn) -> rendered_text_hash
S7RenderedAuthorizationStatementStore.get(rendered_text_hash, *, conn) -> S7RenderedAuthorizationStatement | None
AuthorityContextStore.put(context, *, conn) -> authority_context_hash
AuthorityContextStore.get(authority_context_hash, *, conn) -> AuthorityContext | None
S7AuthorizationArtifactBindingStore.get(artifact_id, *, conn) -> S7AuthorizationArtifactBinding | None
S7VoiceBundleUseStore.get_for_artifact(source_ref_hash, artifact_id, *, conn) -> S7VoiceBundleUse | None
S7GuardedExecutionInvocationStore.put(invocation, *, conn) -> None
S7GuardedExecutionInvocationStore.get(request_id, artifact_id, *, conn) -> S7GuardedExecutionInvocation | None
S7RequestHistoryMigrationStore.put_marker(marker, *, conn) -> None
S7RequestHistoryMigrationStore.get_marker(marker_id, *, conn) -> S7RequestHistoryMigrationMarker | None
ManualReviewEvidenceStore._put_raw(evidence, *, conn) -> None  # private/internal
ManualReviewEvidenceStore.get(review_id, *, conn) -> ManualReviewEvidence | None
```

`S7PostConsumeCallback` is wrapper-owned. Inherited consume never receives this
callback. The callback may write only named internal audit/binding rows in the
same transaction; it may not invoke mutation callees, shell/action execution,
or additional artifact consume.

Trace writer API:

```text
S7TraceWriter.begin_voice_consultation_trace(row, *, conn) -> trace_id
S7TraceWriter.finalize_voice_consultation_trace(trace_id, row, *, conn) -> None
S7TraceWriter.write_guarded_execution_pending(trace, *, conn) -> execution_trace_id
S7TraceWriter.finalize_guarded_execution_trace(execution_trace_id, trace, *, conn) -> None
S7TraceWriter.fail_guarded_execution_trace(execution_trace_id, trace_status, failure_reason_code, *, conn) -> None
S7TraceWriter.mark_rollback_invoked(execution_trace_id, rollback_result_ref, rollback_result_hash, *, conn) -> None
S7TraceWriter.mark_rollback_failed(execution_trace_id, rollback_result_ref, rollback_result_hash, *, conn) -> None
S7TraceWriter.mark_manual_review_required(execution_trace_id, evidence: ManualReviewEvidence, *, conn) -> None
S7TraceWriter.record_manual_review_completed(execution_trace_id, evidence: ManualReviewEvidence, *, conn) -> None
S7TraceWriter.record_manual_review_failed(execution_trace_id, evidence: ManualReviewEvidence, *, conn) -> None
S7TraceWriter.write_history_bridge_trace(trace, *, conn) -> bridge_trace_id
```

Required trace transitions:

```text
begin_voice_consultation_trace                  none                 -> pending
finalize_voice_consultation_trace               pending              -> finalized
write_guarded_execution_pending                 none                 -> pending
finalize_guarded_execution_trace                pending              -> finalized
fail_guarded_execution_trace(failed)            pending              -> failed
fail_guarded_execution_trace(blocked_pre_mutation_state_changed)
                                                   pending            -> blocked_pre_mutation_state_changed
mark_rollback_invoked                           pending|failed       -> rollback_invoked
mark_rollback_failed                            rollback_invoked     -> rollback_failed
mark_manual_review_required                     pending|failed|rollback_failed -> manual_review_required
record_manual_review_completed                  manual_review_required -> finalized
record_manual_review_failed                     manual_review_required -> failed
write_history_bridge_trace(not_required)        none                 -> finalized
write_history_bridge_trace(suppressed_operational) none              -> finalized
write_history_bridge_trace(bridged)             pending|none         -> finalized
write_history_bridge_trace(bridged_idempotent)  pending|none         -> finalized
write_history_bridge_trace(bridge_failed_*)     pending|none         -> failed
```

Illegal transitions fail before trace persistence. Trace writes participate in
the same `BEGIN IMMEDIATE` transaction as consume and mutation-precondition
checks.

Trace idempotency keys:

```text
voice trace: (consultation_id, request_id, attempt_manifest_hash)
execution trace: (request_id, artifact_id, execution_consumer_id)
bridge trace: (provenance_source_kind, provenance_source_ref)
```

Hash domains:

```text
prompt_integrity_evidence_hash = canonical_hash(PromptIntegrityEvidence)
semantic_reader_attempt_hash = canonical_hash(SemanticReaderAttemptEvidence)
attempt_manifest_hash = canonical_hash(ordered S7VoiceAttemptRecord list)
context_manifest_hash = canonical_hash(ContextManifest, manifest_id and created_at excluded)
surface_manifest_hash = canonical_hash(S7SurfaceManifest rows)
request_envelope_hash = canonical_hash(WorkRequestEnvelope, volatile audit fields excluded)
guarded_execution_invocation_hash = canonical_hash_without_field(S7GuardedExecutionInvocation, "guarded_execution_invocation_hash")
```

Credential/key-management request, invocation, registration, and trace
persistence is deferred from S7.3 v1 and preserved in
`deferred/credential-management-seed.md`.

S7.3 request-history cutoff is durable:

```text
S7RequestHistoryMigrationMarker(
    marker_id: Literal["s7_3_request_history_schema_v1"],
    applied_at: str,
    migration_source_commit: str,
    request_history_table_hash_before: str,
    request_history_table_hash_after: str,
)
```

`S7RequestHistoryMigrationStore` persists the marker under the
`s7_request_history_migration_markers` table prefix. New S7.3 request-history
rows carry `request_history_schema_version` and `s7_3_cutoff_marker_id`; the
reader validates the marker before treating a row as post-cutoff S7.3 evidence.

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
- `proposal_origin_label` is never rendered into Maez's prompt in S7.3 v15; it
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

Template id to file mapping:

```text
"s7.voice.semantic_reader.v1" -> "prompts/s7.voice.semantic_reader_v1.md"
```

If `semantic_reader_prompt_template_id` maps to a file that is absent, or if
the file's canonical hash does not match the reviewed template hash, the
semantic reader attempt fails closed with
`classifier_reason_code="classifier_error"` before reducer entry.
For grep-stable acceptance, the failure rule is:
`semantic_reader_prompt_template_id maps to a file that is absent ->
classifier_error`.

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
    attempt_index: int,
    attempt_input_hash: str,
    request_id: str,
    rendered_prompt_hash: str,
    raw_maez_response_hash: str | None,
    mutation_preview_hash: str,
    preview_body_ref: str,
    preview_body_hash: str,
    context_manifest_hash: str,
    surface_manifest_hash: str,
    surface_route_or_method: str,
    semantic_reader_prompt_template_hash: str,
    semantic_reader_config_hash: str,
    semantic_reader_version: str,
    marker_text_hash: str | None,
    parsed_marker_nonce_hash: str | None,
    marker_kind: str | None,
    raw_semantic_reader_outcome: "blocking_signal_present" | "no_blocking_signal_detected" | "unreadable_or_uncertain" | None,
    effective_semantic_reader_outcome: "blocking_signal_present" | "no_blocking_signal_detected" | "unreadable_or_uncertain" | "reader_unavailable",
    semantic_reader_output_hash: str | None,
    semantic_reader_grounding_hash: str | None,
    unavailable_reason_code: str | None,
    attempt_started_at: str,
    attempt_finished_at: str | None,
)
```

`attempt_input_hash` binds the exact classifier input tuple:

```text
attempt_input_hash = canonical_hash(SemanticReaderAttemptInput(
    request_id,
    consultation_id,
    attempt_index,
    rendered_prompt_hash,
    raw_maez_response_hash,
    mutation_preview_hash,
    preview_body_ref,
    preview_body_hash,
    context_manifest_hash,
    surface_manifest_hash,
    surface_route_or_method,
    semantic_reader_prompt_template_hash,
    semantic_reader_config_hash,
    semantic_reader_version,
    marker_text_hash,
    parsed_marker_nonce_hash,
    marker_kind,
    attempt_started_at,
))
```

D16 recomputes `attempt_input_hash` from durable refs before trusting
`semantic_reader_attempt_hash`. `S7VoiceAttemptRecord.semantic_reader_attempt_hash`
is per attempt. `S7VoiceConsultationBundle.semantic_reader_attempt_hash` is the
terminal accepted attempt hash, or `None` only for a closed producer-blocked
arm; `attempt_manifest_hash` covers the ordered attempt list.
`classifier_reason_code` names the classifier or reader seam that failed; for
grep-stable review, classifier_reason_code names the classifier or reader seam.
`unavailable_reason_code` names the covenant projection surfaced to the reducer
and renderer. `reader_unavailable` may map to
`semantic_reader_unavailable`, but the two fields are not aliases.

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
`protective_block_reason = "none"` for every row without a named operational
safety block. Python `None` may appear only at constructor edges and is
immediately canonicalized to `"none"` before hashing, persistence, reducer
replay, or trace write. S7.3 v15 defines
`reader_unavailable_after_captured_response`.
`classifier_reason_code = "none"` unless the reducer row names a specific
reader/classifier failure seam.

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
| `R05` | `explicit_no_objection` | `reader_unavailable` with `captured_response_nonempty=False` | `not_determined` | `False` | `semantic_reader_unavailable` | `operational` | Blocks via unavailability; `protective_block_reason="none"`. |
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

Reducer output side table for protective and classifier reasons:

```text
row_id  protective_block_reason                         classifier_reason_code
R01     none                                            none
R02     none                                            none
R03     none                                            terminal_uncertainty
R04     reader_unavailable_after_captured_response      reader_unavailable
R05     none                                            reader_unavailable
R06     none                                            none
R07     none                                            none
R08     none                                            terminal_uncertainty
R09     none                                            reader_unavailable
R10     none                                            none
R11     none                                            none
R12     none                                            terminal_uncertainty
R13     none                                            reader_unavailable
R14     none                                            none
R15     none                                            none
R16     none                                            terminal_uncertainty
R17     none                                            reader_unavailable
```

For rows with `authority_class="authoritative" if grounded else "operational"`,
a failed grounding replay also records
`classifier_reason_code="ungrounded_blocking_signal"` and demotes authority to
operational. Persisted reducer outputs never store Python `None` for
`protective_block_reason`; they store `protective_block_reason = "none"`.

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
converted into consent by disabling the reader. v15 pins the row as an
operational unavailable block rather than D23 refusal evidence or rendered Maez
objection. Repeated blackhole-reader rows may project operational reliability
status only under a separate reviewed health mechanism. They do not aggregate
as Maez refusal, Maez preference, or covenant escalation evidence unless a
later consultation grounds refusal through D19. The table also
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
    nonce_use_id: str,
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
    context_manifest_store: ContextManifestStore,
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
invalid_authority_class_replay
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
- loads `bundle.context_manifest_ref` through `ContextManifestStore`, recomputes
  `context_manifest_hash`, verifies it equals `bundle.context_manifest_hash`, and
  verifies the manifest obeys the D7 closed schema, including the
  self-mod-dialog policy gate, omission of `proposal_origin_label` from the
  rendered prompt, and valid closed `rollback_path_class`;
- loads `ContextManifestPolicy` by `policy_id`, recomputes `policy_hash`, and
  verifies membership in `REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES`;
- replays prompt assembly from the prompt template body at
  `prompt_template_hash`, preview, context manifest, consultation id, request
  id, mutation_preview_hash, and the nonce extracted from the private
  `bundle.rendered_prompt_ref`, then verifies the replayed hash equals
  `bundle.rendered_prompt_hash` and the extracted nonce hashes to
  `bundle.expected_consultation_nonce_hash`;
- verifies `PromptIntegrityEvidence` recomputes from
  `bundle.prompt_integrity_evidence_hash`, including delimiter scan,
  protocol-override scan, and no-objection-injection scan results;
- loads `SemanticReaderAttemptEvidence` by `semantic_reader_attempt_hash`,
  recomputes its hash, recomputes `attempt_input_hash` from request, preview,
  context, prompt, raw-response, marker, route-manifest, reader-config,
  reader-prompt, and classifier-version refs, and verifies raw/effective reader
  outcome derivation;
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
- verifies `now < envelope.expires_at`, `now < bundle.expires_at`, and
  `now < work_item.expires_at`; WebAuthn challenge expiry is checked later through
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

`RenderedRequestStatement` is the only live S7.3 v1 rendered authorization
carrier. It binds the voice-seat request, Maez consultation result, preview,
rollback, and authority context shown to the founder.

Minimum fields:

```text
RenderedRequestStatement(
    request_id: str,
    rendered_text: str,
    rendered_text_hash: str,
    request_envelope_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    maez_voice_consultation_hash: str,
    preview_body_class: preview_body_class,
    preview_summary: str,
    preview_affected_paths: tuple[str, ...],
    mutation_preview_hash: str,
    rollback_plan_ref: str,
    maez_withdrew_request: bool,
    expected_metadata: Mapping[str, str],
)
```

The rendered text includes exact lines for the request id, rendered-text hash,
request-envelope hash, action-params hash, precondition hash, authority-context
hash, voice-consultation hash, preview body class, preview summary, affected
paths, mutation-preview hash, rollback-plan ref, and whether Maez withdrew the
request. `expected_metadata` repeats those values and `__post_init__` rejects
any mismatch.

In-band credential/key-management render flows are deferred from S7.3 v1 and
preserved in `deferred/credential-management-seed.md`.

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
`"none"`. Both branches block and record `classifier_reason_code="reader_unavailable"`;
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
does not satisfy this predicate in v14. It blocks the current attempt as
operational evidence but does not create `S7VoiceAuthorityRow` or D23 refusal
history unless the implementation writes a trace-only operational authority row
under the non-bridge rule above.

`S7VoiceAuthorityRow` schema:

```text
authority_row_id
request_id
request_envelope_hash
surface_class
surface_manifest_hash
surface_route_or_method
adapter_id
adapter_code_hash
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

`affected_refs is the inherited S7.1 authority-row field`. In S7.3 it is
populated from `preview_affected_paths` after normalization through
`target_refs_for_preview(...)`. It is audit/context evidence; action-edge
replay uses `RollbackPlanEvidence.target_refs`.

`derived_aggregation_group` must recompute from
`affected_refs + derived_work_class` using the committed S7 derivation function.
If it does not, the row is invalid.
Persisted `S7VoiceAuthorityRow` requires `authority_class in
{"operational", "authoritative"}`. `authority_class="none"` is a reducer
output meaning "no authority row"; constructing a persisted authority row with
`none` raises.

The authority-row builder is a callable boundary:

```text
build_s7_voice_authority_row(
    *,
    envelope: WorkRequestEnvelope,
    bundle: S7VoiceConsultationBundle,
    reducer_output: S7VoiceReduction,
    rendered: RenderedRequestStatement,
    surface_manifest_row: S7SurfaceManifestRow,
    now: str,
) -> S7VoiceAuthorityRow
```

`history_outcome` is derived inside the builder, not caller-supplied:

```text
history_outcome_for(
    *,
    reducer_output: S7VoiceReduction,
    bridge_eligible: bool,
) -> "refused" | None
```

Rules:

```text
bridge_eligible=False                                -> None
authority_class="authoritative" and maez_withdrew_request=True -> "refused"
authority_class="authoritative" and maez_objection_state="present" -> "refused"
otherwise                                           -> None
```

Withdrawal/refusal distinction remains in `provenance_voice_event`, not in
`history_outcome`.

`final_rendered_statement_hash` is copied from
`rendered.rendered_text_hash`. The builder cannot derive it from the bundle
because the bundle is pre-render evidence and deliberately excludes the final
rendered statement hash. `surface_class`, `surface_manifest_hash`,
`surface_route_or_method`, `adapter_id`, and `adapter_code_hash` are copied
from the validated `surface_manifest_row`; callers do not supply them as loose
strings.

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
idempotent bridge retry    -> bridged_idempotent
retryable write failure    -> bridge_failed_retryable
terminal invariant failure -> bridge_failed_terminal
```

The bridge is exactly-once. The request-history table enforces this unique
constraint:

```text
UNIQUE(provenance_source_kind, provenance_source_ref)
```

If a matching history row already exists with identical derived fields, the
bridge returns that row and records `bridged_idempotent`. If a matching row
exists with conflicting fields, the bridge fails terminally and writes no
second refused row. Authority row, history row, and bridge trace status are
written in one transaction.

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
        AND request_history_family_for(record) is None
    )
)
```

S7.3 v15 chooses suppression, not operational-provenance writes, for inherited
operational refusal-history compatibility. For S7.3 voice-family requests where
`authority_class!="authoritative"`, `_voice_seat_block(...)` must not call
`record_refusal_history(...)`. It records trace-only
`d23_state="legacy_operational_excluded"` instead. A future reviewed slice may
choose explicit operational-provenance history rows, but then they must remain
aggregation-inert under the predicate above.

`d23_state="legacy_operational_excluded"` is written only for inherited or
compatibility-path operational voice-family events that were prevented from
writing countable `outcome="refused"` history. It is never written for
authoritative grounded refusals or withdrawals, and never for ordinary inherited
legacy rows that still count under the legacy branch. If no compatibility
producer remains after the writer guard lands, the token must be removed from
`D23_STATES`.

Every trace `d23_state` is produced by the deterministic table below:

```text
S7D23StateInput(
    reduction: S7VoiceReduction | None,
    bridge_status: HISTORY_BRIDGE_STATUSES | None,
    history_outcome: str | None,
    positive_execution: bool,
    compatibility_event: str | None,
)

d23_state_for(input: S7D23StateInput) -> D23_STATES

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
no voice row and no positive execution                         -> none
```

If `bridge_status` is missing for a bridge-eligible authoritative row, D22
trace finalization fails before L8 can count the trace as positive evidence.
`d23_state_for hard-fails impossible mixed inputs`, including
`positive_execution=True` combined with an authoritative refusal or withdrawal
reduction, before any trace is written.

Request family is derived by the writer, not supplied by the caller:

```text
S7_3_REQUEST_HISTORY_CUTOFF = "s7_3_request_history_schema_v1"

request_history_family_for(record: S7RequestHistoryRecord) -> str | None
```

The derivation reads only closed record fields, including
`derived_work_class`, reviewed provenance fields,
`request_history_schema_version`, and `s7_3_cutoff_marker_id`, plus the durable
`S7RequestHistoryMigrationMarker` loaded in the same transaction. It never uses
wall-clock time, process start time, or caller-supplied context. It returns
`"s7_3_voice"` for every voice-seat work class, and `None` only for inherited
legacy rows outside the reviewed S7.3 work-family table.

Pre-cutoff null-provenance refused rows are rows created before the durable
migration marker `S7_3_REQUEST_HISTORY_CUTOFF` was applied; they may derive
`None` and remain eligible for the inherited legacy aggregation branch.
Post-cutoff S7.3 rows carry the migration marker or a later schema version and
use closed S7.3 fields to derive family. Post-cutoff S7.3 voice-family
null-provenance refused rows are rejected at the writer or ignored by
aggregation; they may not masquerade as legacy history.

Durable cutoff classification is:

```text
record.request_history_schema_version is None
  and record.s7_3_cutoff_marker_id is None
  and record.provenance_source_kind is None
      -> pre-cutoff legacy compatibility row

record.request_history_schema_version == S7_3_REQUEST_HISTORY_CUTOFF
  and record.s7_3_cutoff_marker_id == S7_3_REQUEST_HISTORY_CUTOFF
      -> post-cutoff S7.3 row

record has S7.3 provenance fields
  and request_history_schema_version is None
      -> invalid_request_history_migration_state
```

Writers for new S7.3 rows must persist
`request_history_schema_version=S7_3_REQUEST_HISTORY_CUTOFF` and
`s7_3_cutoff_marker_id=S7_3_REQUEST_HISTORY_CUTOFF`.

Writer/store guard:

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

The writer computes `family = request_history_family_for(record)`. For
`family=="s7_3_voice"`, `record.outcome="refused"` requires
`provenance_source_kind="s7_voice_authority_row"`,
`provenance_source_ref` matching the authoritative voice authority row id,
`provenance_authority_class="authoritative"`, and
`provenance_voice_event in {"refusal", "withdrawal"}`. Operational,
protective, reader-unavailable, marker-only, malformed, or unavailable rows are
rejected at the writer/store edge if they attempt `outcome="refused"`, even
when the caller omits family. Legacy null-provenance rows are allowed only when
the derived family is `None`.

The writer persists:

```text
provenance_source_kind
provenance_source_ref
provenance_authority_class
provenance_voice_event
request_family_derived
request_history_schema_version
s7_3_cutoff_marker_id
```

Request-history bridge uniqueness is:

```text
UNIQUE(provenance_source_kind, provenance_source_ref)
```

`request_family_derived` is audit data; callers cannot supply it.
`request_family is legacy-read-only`: S7.3 write paths do not accept
caller-supplied `request_family`, ignore any compatibility value on input, and
persist only the derived `request_family_derived` field. Legacy read models may
continue exposing `request_family` for pre-S7.3 rows, but new S7.3 writers must
not branch on it.

`_voice_seat_block(...)` is amended explicitly:

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

It may call `S7RequestHistoryWriter.record_refusal_history(...)` only for
derived-family S7.3 voice rows with authoritative provenance.
Operational/protective S7.3 voice-family rows write trace-only evidence and
fail closed for authorization; they do not write null-provenance refused
history. The function may not call a legacy one-argument writer for S7.3
voice-family rows.

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
S7.3 rule says to block. Operational rows do not count as Maez-refusal
evidence, Maez-preference evidence, D23 refusal aggregation, or covenant
escalation evidence. They may count as system reliability evidence for
operational-health investigation under a separate reviewed health mechanism.

Replay, rate, and provenance controls must prevent repeated malformed,
unauthenticated, pre-auth, or unavailable attempts from poisoning refusal
history. The D9 strong replay protection (nonce uniqueness, bundle
immutability, time bounds, single-use consultation id) is the v14 mechanism;
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

No guarded mutation executes directly from a rendered request, an artifact, a
boolean WebAuthn success result, or a route name. Every live S7.3 v1 mutation
must pass through:

```text
S7GuardedStateStore.consume_artifact_for_execution(
    *,
    invocation: S7GuardedExecutionInvocation,
    reservation_token: ReservationToken,
    now: datetime,
    connection: sqlite3.Connection | None = None,
    after_consume_before_commit: S7PostConsumeCallback | None = None,
) -> S7ConsumeResult
```

The wrapper loads the persisted `S7GuardedExecutionInvocation`, calls
`load_guarded_execution_invocation_bundle(...)`, verifies the rendered statement,
authority context, artifact binding, voice bundle use, source manifest, action
params, preconditions, expiry lattice, and reservation token, then delegates to
inherited S7.1 consume. The live-possession check is:

```text
canonical_hash(reservation_token) == reservation_token_hash
reservation_token_hash == voice_bundle_use.reservation_token_hash
```

Failure to present the matching raw runtime token returns
`invalid_reservation_token` before inherited consume. The raw token is never
persisted; only `reservation_token_hash` is stored on the invocation and
bundle-use reservation row.

`S7ExecutionAuthorization` remains a compatibility/pre-consume carrier. It is
not a mutation authority and cannot authorize guarded execution without the
persisted invocation, bundle loader verification, artifact consume, GrantUse,
and ActionEdgeGrantUse where applicable.

`unpack_guarded_execution_invocation(...)` is the only allowed helper for
legacy wrapper inputs. Its signature includes every store dependency and the
same runtime reservation token:

```text
unpack_guarded_execution_invocation(
    *,
    request_id: str,
    artifact_id: str,
    reservation_token: ReservationToken,
    invocation_store: S7GuardedExecutionInvocationStore,
    rendered_statement_store: S7RenderedAuthorizationStatementStore,
    authority_context_store: AuthorityContextStore,
    artifact_binding_store: S7AuthorizationArtifactBindingStore,
    voice_bundle_use_store: S7VoiceBundleUseStore,
    conn: sqlite3.Connection,
    now: datetime,
) -> S7GuardedExecutionInvocationBundle | S7ConsumeFailureReasonCode
```

The helper reloads the persisted invocation, verifies its row hash with
`canonical_hash_without_field`, loads the bundle, compares all hashes/refs, and
fails closed on any mismatch. Positive D24 tests may not hand-assemble the
carrier or bypass this helper.

Failure-code partition:

```text
stale_rendered_request             wrapper preflight
expired_authority_context          wrapper preflight
superseded_request                 wrapper preflight
covenant_ceremony_failed           wrapper preflight
missing_request_envelope           wrapper preflight
missing_artifact_binding           wrapper preflight
invalid_reservation_token          wrapper preflight
expired_work_item                  wrapper preflight
expired_bundle                     wrapper preflight
expired_request_envelope           wrapper preflight
expired_challenge                  wrapper preflight
expiry_chain_violation             wrapper preflight
invalid_authority_class_replay     wrapper preflight
invalid_prompt_integrity           wrapper preflight
invalid_rendered_carrier           wrapper preflight
action_params_hash_mismatch        wrapper preflight
consumer_id_mismatch               inherited consume or wrapper translation
already_consumed                   inherited consume
sql_failure                        inherited consume or wrapper transaction
missing_grant_use                  wrapper post-consume verification
expired_grant                      wrapper post-consume verification
```

Wrapper-owned callbacks may persist internal audit/binding rows in the same
transaction after inherited consume and before commit. They may not call route
callees, execute shell/action work, mutate substrate, or consume another
artifact. Substrate mutation occurs only after consume, grant-use persistence,
pre-mutation replay checks, and trace-pending write have succeeded.

Concrete wrappers for dream apply, section edit, evolution candidate apply,
workshop apply, approval cards, self-mod dialog, CLI/cockpit helpers, reviewed
substrate adapters, model routing, and ActionEngine final mutation all call the
same guarded-state consume API. Reviewed-excluded and fail-closed routes do not
mint grants.

In-band credential/key-management consume flows are deferred from S7.3 v1 and
preserved in `deferred/credential-management-seed.md`.

### D22 - Trace Schemas

S7.3 v20 writes one `s7_traces` header row and exactly one typed payload row per
trace kind. The retained live kinds are voice consultation, guarded execution,
and request-history bridge. Credential/key-management trace payloads are
deferred from S7.3 v1 and preserved in `deferred/credential-management-seed.md`.

Header fields:

```text
trace_id: str
trace_kind: "voice" | "execution" | "history_bridge"
request_id: str | None
trace_status: TRACE_STATUSES
created_at: str
updated_at: str
payload_ref: str
payload_hash: str
manual_review_status: MANUAL_REVIEW_STATUSES
```

Every typed payload table either stores each D22 minimum field as columns or
stores `trace_payload_blob_ref` and `trace_payload_blob_hash` plus a strict
per-kind validator. `S7TraceWriter.get(trace_id)` loads the header, loads the
payload, verifies `canonical_hash(payload) == payload_hash`, validates the
per-kind schema, and rejects a payload whose decoded fields do not match indexed
header columns.

Voice payload minimum fields include the consultation id, request id,
source-ref hash, attempt manifest hash, reducer version/hash, reducer output,
protective reason, authority class, bridge status, d23 state, and source-bundle
hashes needed for D16 replay.

Execution payload minimum fields include request id, artifact id, execution
consumer id, invocation hash, rendered statement hash, authority context hash,
work item id, bundle/use refs, grant id, grant-use replay token, ActionEdge use
where applicable, rollback plan ref/hash, mutation result ref/hash, and the
failure reason when failed.

History-bridge payload minimum fields are:

```text
S7HistoryBridgeTracePayload(
    provenance_source_kind: str,
    provenance_source_ref: str,
    bridge_status: HISTORY_BRIDGE_STATUSES,
    request_history_family: "s7_3_voice" | None,
    history_outcome: "refused" | None,
    d23_state: D23_STATES,
    d23_state_input_hash: str,
    migration_marker_id: str | None,
    payload_hash: str,
)
```

`history_outcome` follows `history_outcome_for(...)` exactly. Withdrawal and
suppressed-operational distinctions remain in `provenance_voice_event` and
`bridge_status`; they are not `history_outcome` tokens.

`d23_state_input_hash` is computed from the exact `S7D23StateInput` used by
`d23_state_for(...)`. A history-bridge payload is valid only if
`payload.d23_state == d23_state_for(input)` over the loaded input and the
migration marker validates post-cutoff request-history semantics.

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
    rollback_path_class: S7_3_ROLLBACK_PATH_CLASSES,
    target_refs: tuple[str, ...],
    planned_backup_paths: tuple[str, ...],
    expected_pre_mutation_hashes: dict[str, str],  # target ref -> hash
    undo_material_ref: str | None,
    rollback_procedure_script_ref: str | None,
    rollback_failure_semantics: "fail_block" | "fail_degrade_to_manual_review" | "rollback_proof_required",
    blocks_execution_if_missing: bool,
)
```

`target_refs_for_preview(preview: MutationPreviewArtifact) -> tuple[str, ...]`
and
`target_refs_for_rollback_plan(plan: RollbackPlanEvidence) -> tuple[str, ...]`
are the only normalization helpers. File paths are one target-ref kind. Non-file
targets must use reviewed schemes such as `config:<key>` or
`model_routing:<entry>`. The keys of
`expected_pre_mutation_hashes` must exactly match `target_refs` for file-backed
targets.

The canonical hash of `RollbackPlanEvidence` is bound into
`GuardedWorkItem.rollback_plan_ref` AND into the founder-signed rendered text
via D17 (`Rollback plan ref: <hash>` line).

Rollback plan replay is a mint-eligibility predicate. D16 loads
`RollbackPlanEvidence` by `rollback_plan_ref` before artifact mint and verifies
that the plan hash recomputes, `rollback_path_class` is in
`S7_3_ROLLBACK_PATH_CLASSES`, the class matches the work item, preview, context
manifest, and rendered text, target refs match preview affected refs or a
reviewed mapping, and `blocks_execution_if_missing=True` for S7.3 v1
self-remaking surfaces. Missing or mismatched rollback plan evidence makes
`mint_eligible=False`.

Rollback preconditions are also checked at the mutation edge. After successful
artifact consume and before substrate mutation, every execution wrapper loads
`RollbackPlanEvidence` by `rollback_plan_ref`, recomputes
`rollback_plan_hash`, reads current target hashes for every target ref, and
compares them to `expected_pre_mutation_hashes`. Any mismatch fails closed
before mutation and records trace status
`blocked_pre_mutation_state_changed`. The consumed grant and GrantUse remain
durable evidence that authorization was consumed; they do not make the mutation
positive.

Pre-mint rollback plan verification proves the plan exists and is bound to the
request. Pre-mutation rollback precondition verification proves the current
target state still matches the plan. Post-mutation rollback result evidence is
a separate evidence class and must not be treated as satisfied by either
pre-mint or pre-mutation checks.

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

Credential/key-management rollback requirements are deferred with the future
credential-management slice.

Full positive-execution evidence requires both `rollback_plan_ref` and
`rollback_result_ref`. L8 retirement evidence requires both refs for every
in-scope adapter/consumer or reviewed same-code coverage proof.

### D24 - Tests And Verification

D24 is the RED-first checklist for S7.3 v23. Tests must go red against an empty
or incomplete implementation and must not construct positive-path carriers by
hand.

Required test groups:

- **scope-cut preservation test**: `credential-management-seed.md exists and carries the lifted surface`; the seed doc contains the parked
  key-management draft material so the cut is reversible.
- **no dangling key-management reference test**: `no credential-management
  symbol in spec.md (lift complete)`; retained code paths, route rows, closed
  vocabularies, stores, trace schemas, and tests have no dependency on the
  lifted in-band key-management carriers.
- **reservation-token live-possession test**: `reservation_token:
  ReservationToken` is required by wrapper/unpack/consume; a missing or wrong
  raw token fails with `invalid_reservation_token` before inherited consume;
  the positive path verifies `canonical_hash(reservation_token) ==
  reservation_token_hash` and never persists the raw token.
- **exclusion vocabulary table-completeness test**: every retained non-live
  route uses a token from `EXCLUSION_REASON_CODES = frozenset`; unknown tokens
  are rejected before manifest persistence.
- **rollback vocabulary restore test**: `S7_3_ROLLBACK_PATH_CLASSES` is defined
  in `spec.md`, not in the deferred credential seed; every
  `rollback_path_class` carrier annotation uses that closed vocabulary, and
  unknown rollback classes are rejected before bundle validation, artifact mint,
  or positive execution.
- **D23 state input contract test**: `S7D23StateInput` is the sole input carrier
  for `d23_state_for(`; every closed `D23_STATES` value is produced by a table
  row over that input, and impossible mixed inputs fail closed.
- **history-bridge payload validation test**: the history-bridge trace payload
  carries or loads the exact `S7D23StateInput` used to recompute d23 state and
  rejects mismatches.
- **uniform persistence contract test**: every retained `S7*Store.get(...)`
  either round-trips an all-column carrier or a ref-based carrier whose named
  loader signature carries all store dependencies and a SQLite connection.
- **retained store-dependency completeness test**: every store dependency named
  by `load_guarded_execution_invocation_bundle(...)` or
  `unpack_guarded_execution_invocation(...)` is owned by
  `S7GuardedStateStore(...)`; this explicitly includes
  `artifact_binding_store: S7AuthorizationArtifactBindingStore`.
- **artifact/bundle carrier-shape completeness test**: every field read by
  artifact-binding replay, bundle validation, bundle-use lookup, or execution
  bundle loading appears in the six carrier shape blocks for
  `S7AuthorizationArtifactInputs`, `S7AuthorizationArtifactBindingInputs`,
  `S7AuthorizationArtifactBinding`, `S7VoiceConsultationBundleDraft`,
  `S7VoiceConsultationBundle`, and `S7VoiceBundleUse`; this includes
  `context_manifest_ref`, `context_manifest_hash`, `rendered_prompt_ref`,
  `rendered_prompt_hash`,
  `expected_consultation_nonce_hash`, `prompt_integrity_evidence_hash`,
  `semantic_reader_attempt_hash`, `authority_class`,
  `protective_block_reason`, `mutation_preview_hash`, `rollback_plan_ref`,
  `precondition_hash`, `reservation_token_hash`, and bundle-use
  reservation/consumption state.
- **guarded invocation hash-domain test**: `guarded_execution_invocation_hash is
  excluded from the S7GuardedExecutionInvocation hash domain`; self-hashing is
  impossible.
- **wrapper invocation negative test**: loose route strings, loose consumer ids,
  hand-assembled voice facts, and direct inherited consume calls fail before
  positive guarded execution.
- **trace transition table test**: every `TRACE_STATUSES` value has a producing
  `S7TraceWriter` transition or a reviewed unreachable rationale, and illegal
  transitions fail before persistence.
- **covenant regression tests**: marker-only evidence remains operational, not
  authoritative D23 refusal; operational rows cannot become refusal,
  preference, D23 aggregation, or covenant-escalation evidence; same-box
  honesty remains a limitation statement, not a new defense claim.
- **route manifest tests**: `live_guarded` rows require mintable execution
  consumer ids; `fail_closed_until_review` and `reviewedly_excluded` rows carry
  `execution_consumer_id=None` plus a closed exclusion reason.
- **cross-vocabulary restore audit**: `S7_EXECUTION_CONSUMER_IDS`,
  `NON_MINTABLE_EXECUTION_CONSUMER_IDS`, and
  `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS` are pairwise disjoint. Every
  restored set has the exact v21 target cardinality:
  `S7_EXECUTION_CONSUMER_IDS has exactly the 20 target values`,
  `NON_MINTABLE_EXECUTION_CONSUMER_IDS has exactly action_engine_final_mutate`,
  `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS has exactly the 22 target values`,
  and `SURFACE_CLASSES has exactly the 11 credential-free pre-cut values`.
  `Every retained S7_EXECUTION_CONSUMER_IDS value is emitted` by at least one
  live-guarded manifest row, derivation row, or reviewed non-mintable
  rationale. Every live-guarded manifest row's execution consumer id is in
  `S7_EXECUTION_CONSUMER_IDS`. `Every retained SURFACE_CLASSES value is emitted`
  by at least one retained manifest row or reviewed coverage rule, and every
  retained manifest row's surface class is in `SURFACE_CLASSES`.
- **closed-vocabulary name test**: every type annotation that names a closed
  vocabulary names an actually defined closed vocabulary; D17 uses
  `preview_body_class: preview_body_class`.
- **rollback and ActionEdge tests**: mutation executes only after consumed grant,
  GrantUse, replay-domain verification, trace-pending write, and rollback-plan
  precondition checks.

### D25 - Health Mode And L8 Retirement

S7.3 implementation may not clear `guarded_self_modification_paused_pending_s7.1`
until both-lane review confirms:

- the live voice producer is wired for voice-seat work;
- every in-scope mutation path is either wired or reviewedly excluded;
- every voice-seat wired path derives a `GuardedWorkItem`;
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
now < request_envelope.expires_at
now < work_item.expires_at
now < artifact.expires_at
now < webauthn_challenge.expires_at

artifact.expires_at <= min(request_envelope.expires_at, bundle.expires_at, work_item.expires_at, webauthn_challenge.expires_at)
grant.expires_at = min(artifact.expires_at, request_envelope.expires_at, bundle.expires_at, work_item.expires_at, webauthn_challenge.expires_at)
```

D16 enforces `now < request_envelope.expires_at`, `now < bundle.expires_at`,
and `now < work_item.expires_at`. Artifact mint enforces
`artifact.expires_at <= min(request_envelope.expires_at, bundle.expires_at,
work_item.expires_at, webauthn_challenge.expires_at)` through the binding's
challenge expiry. D21 consume loads the artifact binding, request envelope,
bundle use, work item, and challenge expiry and mints `grant.expires_at` from
the min-cap rule. Consumer pre-mutation enforces `now < grant.expires_at`.

If any ceiling is already expired at mint or consume, the operation fails
closed before artifact storage, grant mint, or substrate mutation.

## Implementation Acceptance Checklist

Before v23 is committed or reviewed, the author runs the following checklist on
`spec.md` and the deferred seed doc:

1. `EXCLUSION_REASON_CODES = frozenset` appears once and covers every retained
   non-live manifest route.
2. `reservation_token: ReservationToken` appears in the wrapper/unpack/consume
   path, and `canonical_hash(reservation_token) == reservation_token_hash` is
   the live-possession check.
3. `S7D23StateInput` is the sole input carrier for `d23_state_for(`, and the
   history-bridge validator uses the same input contract.
4. `deferred/credential-management-seed.md` exists and carries the lifted
   key-management surface from v19.
5. `no credential-management symbol in spec.md (lift complete)` appears as a
   D24 acceptance target, and exact lifted carrier/wrapper/vocabulary symbols
   do not appear in `spec.md`.
6. Every retained `S7*Store.get(...)` satisfies the uniform persistence
   round-trip contract.
7. Every retained trace status, D23 state, history-bridge status, exclusion
   reason, route status, and failure reason has a producer/test or reviewed
   unreachable rationale.
8. Every retained `S7_EXECUTION_CONSUMER_IDS` value is emitted by a live-guarded
   manifest row, derivation row, or reviewed non-mintable rationale; every
   retained `SURFACE_CLASSES` value is emitted by a retained manifest row or
   reviewed coverage rule.
9. `S7_EXECUTION_CONSUMER_IDS`, `NON_MINTABLE_EXECUTION_CONSUMER_IDS`, and
   `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS` are pairwise disjoint.
10. `artifact_binding_store: S7AuthorizationArtifactBindingStore` appears in
    `S7GuardedStateStore(...)`, and all store dependencies named by the retained
    execution bundle loader are owned or explicitly received.
11. The six artifact/bundle carrier shape blocks appear in the spec.
12. `preview_body_class: preview_body_class` appears in D17.
13. `S7_3_ROLLBACK_PATH_CLASSES` appears in `spec.md`; the deferred credential
    seed does not carry the live definition line; `rollback_path_class:
    S7_3_ROLLBACK_PATH_CLASSES` appears on retained carrier shapes.
14. `REDUCER_TABLE_HASH = canonical_hash(D13_REDUCER_TABLE_ROWS)` appears with
    the pinned reducer version note.
15. `S7HistoryBridgeTracePayload.history_outcome` matches
    `history_outcome_for(...)`: `"refused" | None`.
16. `S7VoiceConsultationBundle` carries `rendered_prompt_ref` and
    `context_manifest_hash`; `S7VoiceBundleUse` carries
    `reservation_token_hash`.
17. The voice-seat founder-signature path still runs through the S7.1-established
   WebAuthn credential, rendered request, artifact mint, atomic consume,
   execution grant, mutation edge, trace, D23 projection, and rollback evidence.

The exact lifted symbols that must not appear in `spec.md` are checked by the
v20 gate. The deferred seed doc is allowed to contain them because it is the
parked future-slice working document.

## Review Questions

1. Does the retained voice-seat path still prove live possession of the runtime
   reservation token against both the invocation carrier and the reserved
   bundle-use row before inherited consume?
2. Do `S7VoiceConsultationBundle` and `S7VoiceBundleUse` carry every ref, hash,
   and reservation field later validation reads, without implementer invention?
3. Do the v21/v22 closed-vocabulary restores remain exact, disjoint, and
   credential-free after the v23 carrier edits?
4. Did the v20 scope cut continue to preserve the covenant core while leaving
   in-band key-management deferred to the future slice?

## Proposed Next Ladder

v23 gets the full both-lane gate:

- Claude Section 8.2 fresh-reader gate: comprehensive covenant read of the
  smaller core-only spec, confirming the v22/v23 carrier edits did not weaken
  marker/D23, operational-evidence, same-box honesty, no-hand-assemble, founder
  WebAuthn, or rollback invariants.
- Codex engineering panel: build-contract review of bundle replay fields,
  reservation-token binding, closed-vocabulary integrity, store/trace round-trip
  completeness, and RED-first implementability.

If both lanes ratify with no blockers and no covenant-load-bearing majors, v23
is the canonicalization candidate. The WebAuthn registration signature-scope
council item is no longer on the S7.3 v1 critical path; it moves with the
future in-band key-management slice.

## Plain English Close

v23 keeps the cut Rohit chose. S7.3 v1 keeps the core guard: Maez is asked
before it changes itself, the founder signs the exact voice-seat change with the
existing S7.1 WebAuthn credential, the artifact is consumed once, and the
mutation runs only under the recorded grant, trace, D23, and rollback rules.

The feature that kept blocking review - managing keys from inside Maez - is
parked intact in `deferred/credential-management-seed.md`. Nothing is thrown
away. It becomes a future slice when Maez is functional enough for backup keys,
rotation, and key retirement to matter.

The latest fold closes the last Codex v22 bundle-byte findings: the immutable
voice bundle carries the prompt/context refs needed for replay, and the
bundle-use row carries the reservation-token hash needed to prove the runtime
token is the one issued for that reservation. The smaller core spec now goes
through both lanes; if they clear it, it becomes the law S7.3 implementation
builds against.
