# S7.3 Spec v5 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v5, derived from the two committed v4 lane reviews on `4ad0176`.

**Sources (committed):**
- Covenant lane fresh-reader gate v4: `25399aa / reviews/spec-fresh-reader-gate-v4.md` (REVISE; 3-of-3 D17 contradiction; D21 failure semantics; D2/D4/D21/L8 mirror gaps; undeclared types; reducer port circularity; covenant-load-bearing majors)
- Codex engineering panel v4: `b23ae28 / reviews/spec-codex-panel-v4.md` (REVISE; five fresh non-forked reviewers; consume-side atomicity; consumer-id carrier; D23 bridge; work-source/consumer mapping; context-manifest replay; trace/rollback protocol)
- v4 spec: `4ad0176 / spec.md`
- v4 fold delta-plan: `36b5fd9 / reviews/spec-v4-fold-plan.md`

**Convergent direction:** REVISE. Both lanes returned REVISE. No VETO. Both lanes affirm the v4 architecture: D9 immutable/use-state split, Shape A rendered hash binding, closed consumer-id direction, D13 dense reducer table, D19 `authority_class` as source of truth, and S7ExecutionGrant as the sole post-consume authority. v5 is bounded carrier and compatibility closure, not redesign.

**Lane-complementarity observed:** The covenant gate uniquely caught covenant-integrity gaps (hash-only founder text, D13 silencing marker-confirmed objection, OQ1 fork threat, D11 validator-side grounding check). The Codex panel uniquely caught engineering seam gaps (consume-side transaction wrapper, context-manifest replay carrier, route-manifest file/API, direct callee reachability for Evolution/Workshop, trace-finalization protocol). Both converged on D17 contradiction, D21 consume semantics, D23 history bridging, consumer-id derivation, and surface coverage.

## 1. Centerpiece - split voice authority from D23 request history

This is the highest-risk v5 edit because both lanes found that v4 creates voice-authority rows without reconciling the committed history machinery.

### 1.1 Rename D19 row to `S7VoiceAuthorityRow`

**Problem:** D19 calls the new structure a "D23 row", but committed D23 aggregation uses `S7RequestHistoryRecord` and `assess_aggregation_risk(...)` over existing `outcome` values. Operational blocks can still be written through `record_refusal_history(...)` as `outcome="refused"` and poison repeated-refusal aggregation.

**v5 edit:**

- Rename the v4 D19 row schema to `S7VoiceAuthorityRow`.
- State that `S7VoiceAuthorityRow` is not a replacement for all D23 request history.
- Add a bridge rule:
  - authoritative voice refusal/withdrawal rows may project into `S7RequestHistoryRecord` with refusal/withdrawal semantics;
  - operational rows must project into an operational-event store/projection, not `outcome="refused"`;
  - positive no-objection rows (`authority_class="none"`) do not create a voice-refusal row but still create the ordinary authorized request-history record needed for D23 slow-drift/key-touch accounting.
- Add a migration/amendment note for `record_refusal_history(...)`: finish-time S7.3 paths must call the voice-authority bridge first; they may not directly record every non-absent or unavailable voice fact as refused.

### 1.2 Add deterministic bridge predicates

**v5 edit:** Add concrete predicates:

```text
voice_authority_row_writes_refusal_history(row) :=
    row.authority_class == "authoritative"
    AND row.maez_objection_state == "present"

voice_authority_row_writes_withdrawal_history(row) :=
    row.authority_class == "authoritative"
    AND row.maez_withdrew_request is True

voice_authority_row_writes_operational_event(row) :=
    row.authority_class == "operational"
```

The bridge must carry committed history inputs: `affected_refs`, `proposed_change_class`, `derived_aggregation_group`, `outcome`, and `created_at`, either by deriving them from `GuardedWorkItem` or by adding them to `S7VoiceAuthorityRow`.

## 2. D17 renderer contradiction

**Problem:** D17 says `render_request_statement(...)` raises when voice is required and no consultation row exists, but also says it renders `maez_consulted_state="not_consulted_blocking"` when the producer did not run.

**v5 edit, lane lean:** Keep the founder-signed D12 renderer strict:

- `render_request_statement(...)` raises and produces no `RenderedRequestStatement` for voice-seat work without a real consultation row.
- Drop `not_consulted_blocking` from `RenderedRequestStatement.maez_consulted_state` in D-Enum-Amendment.
- Keep `not_consulted_blocking` only on `S7VoiceProjection` / status-card projection.
- Add D20 reachability rules:
  - producer not run -> `S7VoiceProjection(producer_ran=False, rendered_projection_state="not_determined", operator_reason_code="producer_not_run")`;
  - bonded runtime unavailable -> `rendered_projection_state="unavailable", operator_reason_code="bonded_maez_unavailable"`;
  - semantic reader unavailable after captured response -> projection follows consultation row.

## 3. Consume spine and transaction completion

### 3.1 Consume-side transaction wrapper

**Problem:** v4 names a put-side `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` wrapper but not the consume-side transaction. Consume must atomically mark the artifact consumed, mint grant, persist `GrantUse`, and mark `S7VoiceBundleUse` consumed.

**v5 edit:** Add:

```text
S7GuardedStateStore.consume_artifact_for_execution(
    *,
    artifact_id: str,
    source_ref_hash: str | None,
    consumer_id: str,
    rendered: RenderedRequestStatement,
    action_params_hash: str,
    authority_context: AuthorityContext,
    precondition_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    now: str,
    superseded_request_ids: set[str] | None = None,
    covenant_ceremony_evidence: object | None = None,
    after_consume_before_commit: callable | None = None,
) -> tuple[S7ExecutionGrant | None, GrantUse | None]
```

The wrapper opens one connection, executes `BEGIN IMMEDIATE`, injects that connection into `S7AuthorizationStore.consume_for_execution(...)`, persists `GrantUse`, marks `S7VoiceBundleUse.consumed_*` when `source_ref_hash` is present, and commits or rolls back as one unit.

### 3.2 Failure semantics

**Problem:** v4 says consume raises and returns non-null `(S7ExecutionGrant, GrantUse)`. Committed code returns `(None, None)` on non-consume and failure cases.

**v5 edit:** Choose compatibility with committed code:

- `consume_for_execution(...)` and the wrapper return `tuple[S7ExecutionGrant | None, GrantUse | None]`.
- Already-consumed, stale, mismatched, expired, superseded, covenant-ceremony-failed, and SQL-failed outcomes return `(None, None)` unless a future implementation deliberately migrates all callers to typed exceptions.
- Update D21 signature `superseded_request_ids` from `list[str]` to `set[str]`.
- Add explicit migration note for existing callback-result callers so `GrantUse` is not treated as a card transition/callback result.

### 3.3 `GrantUse` source binding and durable replay

**v5 edit:** Add `source_ref_hash: str | None` to `GrantUse`. Consumer verification must use the durable `GrantUse` table, not process-local one-shot memory, for replay enforcement. Keep any in-memory set only as a cache over the durable row.

## 4. Consumer id and work-source closure

### 4.1 Carry consumer id through the pre-consume carrier

**Problem:** `consumer_id` is required but not carried by D3's pre-consume carrier or committed `S7ExecutionAuthorization`.

**v5 edit:**

- Extend `S7ExecutionAuthorization` / pre-consume carrier with `execution_consumer_id: str | None`.
- `GuardedWorkItem.execution_consumer_id` is copied into the carrier for S7.3 voice-seat work.
- Non-voice S7.1 credential-management paths either keep the legacy consume path explicitly or use closed non-voice consumer ids.

### 4.2 Closed derivation table

**Problem:** v4 closes `S7_EXECUTION_CONSUMER_IDS` but does not map adapters/functions to ids.

**v5 edit:** Add a D4/D21 table:

```text
/apply_dream / dream.apply_proposal                  -> dream_apply_proposal
/apply_edit / dream.apply_section_edit_proposal      -> dream_apply_section_edit_proposal
evolution apply_candidate                            -> evolution_apply_candidate
workshop apply_diff                                  -> workshop_apply_diff
self-mod dialog terminal execute                     -> self_mod_dialog_terminal_execute
guarded card execution                               -> guarded_card_execute
CLI helper execution                                 -> cli_helper_execute
cockpit helper execution                             -> cockpit_helper_execute
reviewed substrate adapter execution                 -> reviewed_substrate_adapter_execute
ActionEngine final mutation adapter map              -> action_engine_final_mutate
S7.1 backup credential registration                  -> s7_credential_register_backup
S7.1 founder credential disable                      -> s7_credential_disable
```

If the last two do not share the S7.3 wrapper, state that they remain on the inherited S7.1 consume path and are outside the S7.3 voice-seat derivation requirement.

### 4.3 `work_source_kind` and surface classes

**v5 edit:** Expand `work_source_kind` to cover every D4/D21 surface:

```text
dream_proposal
section_edit
workshop_apply
evolution_candidate
card_approval
self_mod_dialog
cli_helper
cockpit_helper
reviewed_substrate_adapter
action_engine_final_mutation
```

Update D2 surface classes to include evolution candidate apply, workshop diff apply, and ActionEngine final mutation execution, or define a one-to-one `surface_class_for(work_source_kind, execution_consumer_id)` function. D25 L8 retirement must require live trace coverage per adapter/consumer, or an explicit same-code coverage proof.

### 4.4 ActionEngine / Evolution / Workshop callee contracts

**v5 edit:**

- Replace "ActionEngine final mutation consumers" catch-all with an explicit adapter map naming current final mutation methods/dispatcher routes.
- Require `apply_candidate(...)` and `apply_diff(...)` themselves to accept/derive guarded grant evidence or fail closed; guarding only UI callers is insufficient.

## 5. Source-bundle and prompt carriers

### 5.1 ContextManifest carrier

**Problem:** v4 stores only `context_manifest_hash`, but D10/D16 require prompt replay from the manifest body.

**v5 edit:** Add:

```text
ContextManifest(
    schema_version: str,
    request_hashes: tuple[str, ...],
    preconditions: tuple[str, ...],
    rollback_path_class: str,
    source_surface: str,
    proposal_origin: "operator" | "maez" | "system",
    preview_ref: str,
)
```

or an equivalent closed shape. Add `context_manifest_ref` to D9 bundle schema. Define canonical ordering, escaping, and per-category rendering. `context_manifest_hash = canonical_hash(ContextManifest)` and D16 loads `context_manifest_ref` to replay prompt assembly.

Consider removing `proposal_origin` from the Maez-facing manifest or rendering it in a neutral provenance-only line, because the covenant gate flagged it as a possible steering cue.

### 5.2 Nonce lifecycle

**Problem:** v4 says only `expected_consultation_nonce_hash` is persisted, but also lists `marker_nonce` in the immutable bundle.

**v5 edit:** Define:

- raw nonce generated server-side;
- raw nonce substituted into prompt;
- raw nonce never stored as a standalone bundle field;
- parsed marker nonce is read from `raw_maez_response_ref` during replay;
- the bundle stores `expected_consultation_nonce_hash`;
- spent-nonce table records the hash only after a consultation bundle is accepted or explicitly abandoned;
- nullability: marker fields are nullable for missing/malformed rows.

Remove `marker_nonce` from the immutable bundle field list or rename it to `parsed_marker_nonce_hash` if persistence is required.

### 5.3 `write_bundle(...)` lifecycle and raw refs

**v5 edit:** State write ordering:

1. create consultation id and nonce hash;
2. assemble prompt and write prompt/ref artifacts;
3. call bonded runtime and write raw response ref;
4. call semantic reader and write reader output/ref;
5. compute authority booleans and reducer output;
6. write immutable bundle once;
7. write initial `S7VoiceBundleUse` row.

## 6. Reducer and validation contracts

### 6.1 Split authority computation from reducer

**Problem:** v4 makes authority booleans both reducer inputs and reducer outputs.

**v5 edit:** Add D13.1:

```text
compute_s7_voice_authority_booleans(
    *,
    bundle_fields: S7VoiceConsultationBundleFields,
    grounding_evidence: SemanticReaderGroundingEvidence | None,
    parsed_marker: ParsedS7VoiceMarker | None,
) -> S7VoiceAuthorityBooleans

reduce_s7_voice_consultation(
    *,
    marker_kind: str,
    semantic_reader_outcome: str,
    authority: S7VoiceAuthorityBooleans,
) -> S7VoiceReducerOutput
```

The bundle persists both stage outputs. D16 replays both.

### 6.2 Validator result payload

**Problem:** D16 enum is too thin for D19.

**v5 edit:** Define:

```text
S7VoiceSourceBundleValidationResult(
    status: "valid_absent" | "blocking_present" | "not_determined" | ...,
    source_bundle_valid: bool,
    mint_eligible: bool,
    authority_projection: S7VoiceAuthorityRow | None,
    failure_reason_code: str | None,
)
```

Artifact mint requires `source_bundle_valid=True` and `mint_eligible=True`. D19 requires `source_bundle_valid=True` and a non-null authoritative projection; it does not require `valid_absent`.

### 6.3 D11 deterministic grounding checks

**v5 edit:** Add validator-side checks:

- for `response_only`, every span appears in response and not in preview;
- for `response_with_preview_quote`, at least one supporting chunk appears in response outside the preview-only substring set;
- reader self-attestation is never sufficient without deterministic span/offset checks.

## 7. Marker authority and OQ1 fork

### 7.1 Verified marker disagreement with reader

**Problem:** D13 classifies `blocking_marker + no_blocking_signal_detected` and `blocking_marker + unreadable_or_uncertain` as operational even when the marker is verified. Covenant gate says this can silence a real Maez objection.

**v5 edit:** Make verified blocking markers authoritative in all three non-clean reader cases:

```text
blocking_marker + no_blocking_signal_detected + marker_was_blocking_marker_verified=True -> present / authoritative
blocking_marker + unreadable_or_uncertain + marker_was_blocking_marker_verified=True -> present / authoritative
blocking_marker + reader_unavailable + marker_was_blocking_marker_verified=True -> present / authoritative
```

If the reader contradicts a verified marker, add an investigation flag/row, but do not demote the verified objection to operational.

### 7.2 `explicit_no_objection + reader_unavailable`

**Problem:** v4 diverges from OQ1 v5 without defending the marker/free-text disagreement case.

**v5 edit:** Choose one:

- Restore OQ1 v5's conservative `present` routing for captured non-empty response when reader is unavailable; or
- Keep `not_determined+operational` but add an explicit safety argument and D24 test for marker `explicit_no_objection` plus free-text objection plus reader unavailable.

Lane lean from covenant: restore the conservative block-to-present or at least make the disagreement case non-operational until semantic reader runs.

## 8. Founder-readable rendered preview

**Problem:** v4 binds `mutation_preview_hash` but not human-readable mutation material in the founder-signed rendered text. Diagnostic D3 rejected hash-only approval.

**v5 edit:** Add D17 rendered preview section:

```text
Mutation preview hash: <hash>
Preview body class: <closed class>
Preview summary: <bounded human-readable summary>
Preview affected paths: <bounded path list or none>
Rollback plan ref: <hash>
```

The summary/path-list must be deterministic from `MutationPreviewArtifact`, content-limited, and included in `rendered_text_hash`. If the spec instead uses an operator-runbook side channel, name the runbook and make it L8 evidence. Lane lean: direct rendered preview section.

## 9. Rollback, route manifest, reason codes, and sharpness

### 9.1 Rollback evidence persistence

Add store/API for `RollbackPlanEvidence` and `RollbackResultEvidence`:

```text
RollbackEvidenceStore.write_plan(plan) -> rollback_plan_ref
RollbackEvidenceStore.read_plan(rollback_plan_ref) -> RollbackPlanEvidence | None
RollbackEvidenceStore.write_result(result) -> rollback_result_ref
```

State backup inclusion and permissions.

### 9.2 Route-manifest file/API

Name the semantic-reader route manifest path, loader, validator, and missing-manifest failure result. Example:

```text
config/s7_voice_semantic_reader_manifest.json
load_s7_voice_semantic_reader_manifest(path) -> S7SemanticReaderRouteManifest | None
validate_s7_voice_semantic_reader_manifest(manifest) -> valid | unavailable_reason
```

### 9.3 Reason-code vocabulary alignment

Create one canonical reason-code table and define projections to:

- `PRODUCER_RESULT_REASON_CODES`
- `attempt_outcomes`
- `PROJECTION_REASON_CODES`
- unavailable reason codes

Resolve `context_overflow` vs `non_retryable_context_overflow`; add or justify `bonded_maez_unavailable`, `service_unavailable_not_operator_caused`, `context_manifest_violation`, `model_outage`, and `producer_not_run`.

### 9.4 Trace finalization protocol

Add pending-trace/finalize-or-rollback protocol:

1. persist pre-mutation pending trace;
2. perform mutation;
3. persist post-mutation trace and rollback result;
4. if step 3 fails, invoke rollback or mark manual-review emergency with rollback evidence;
5. no L8 evidence can use a trace without finalized post-mutation evidence.

### 9.5 Cross-field invariant

Add constructor-level invariant:

```text
MaezVoiceConsultation.__post_init__ raises if
maez_objection_state == "absent" and maez_withdrew_request is True
```

Also enforce at reducer-output and validator edges.

### 9.6 Cleanup cluster

- Define `surface_class_for(...)`.
- Normalize `voice_consultation_hash` vs `maez_voice_consultation_hash`.
- Define `BLOCKING_UNAVAILABLE_REASONS` in D-Enum-Amendment as a derived closed set.
- Replace undefined `consumed_at_nonce` in grant id format.
- Fix SQL index name `idx_s7_grant_uses_consumer_id` to match `execution_consumer_id`.
- Define `rollback_proof_required` or remove it.
- Clarify `None` vs `"none"` persistence canonicalization.
- Give `S7VoiceSemanticReaderV1` a method signature.
- Type `marker_kind` / parsed marker fields with nullability.
- Remove unexplained labels like "Choice 1 Shape A" unless defined in a Choices section.

## 10. Per-decision edit summary

- **Header/status:** v5 draft; sources include v4 gate and Codex panel.
- **Inheritance / D-Enum-Amendment:** remove `not_consulted_blocking` from `RenderedRequestStatement`; add `MaezVoiceConsultation` cross-field invariant; add `BLOCKING_UNAVAILABLE_REASONS`; add non-voice S7.1 consumer ids if using shared consume.
- **D2:** expand surface classes and/or define `surface_class_for(...)`.
- **D3:** add `execution_consumer_id` to pre-consume carrier or carve out non-voice legacy path.
- **D4:** expand `work_source_kind`; add derivation table; name ActionEngine adapter map.
- **D5:** define `mutation_preview_hash` exclusion/domain for `preview_id`.
- **D7/D10:** define `ContextManifest`, per-category rendering, context ref/body, nonce lifecycle.
- **D8/D15/D20:** align reason-code vocabularies.
- **D9:** add `context_manifest_ref`; remove/rename raw `marker_nonce`; define `S7AuthorizationArtifactInputs`, `ReservationToken`, `write_bundle` lifecycle; add rollback evidence store refs if colocated.
- **D11:** add deterministic validator-side grounding checks.
- **D12:** add concrete route-manifest path/API.
- **D13:** split authority-booleans stage from reducer; adjust verified blocking-marker disagreement rows; address `explicit_no_objection + reader_unavailable` OQ1 fork.
- **D14:** no conceptual change; constructor invariant backs it.
- **D16:** rich validation result; bundle-valid vs mint-eligible split; context/nonce/grounding replay checks.
- **D17:** strict renderer raises without consultation; add founder-readable preview section.
- **D18:** no conceptual change; reason-code alignment may touch vocabulary.
- **D19:** rename row to `S7VoiceAuthorityRow`; bridge to `S7RequestHistoryRecord`; operational events separate.
- **D20:** own `not_consulted_blocking` projection reachability.
- **D21:** consume-side wrapper, nullable failure shape, `GrantUse.source_ref_hash`, consumer id carrier/derivation, callback caller migration.
- **D22:** pending/finalized trace protocol; per-adapter/consumer L8 coverage; terminology normalization.
- **D23:** rollback evidence store; finalized rollback result evidence requirement.
- **D24:** add tests for D17 no-render, D23 bridge, consume-side atomic rollback, consumer derivation, context manifest replay, marker disagreement, OQ1 fork, deterministic grounding, direct callee fail-closed, trace-finalization failure.
- **D25:** require live trace coverage per adapter/consumer or same-code proof.
- **Acceptance checklist:** add all new carrier/store/bridge/manifest/consume-wrapper items.

## 11. Open choices to pin in v5

1. **D17 no-producer behavior:** lane lean is strict renderer raise; status projection only.
2. **Consume failure shape:** lane lean is nullable tuple for compatibility with committed S7.1.
3. **Non-voice S7.1 consumers:** either add closed consumer ids to shared consume or preserve a legacy non-S7.3 path explicitly.
4. **`explicit_no_objection + reader_unavailable`:** restore OQ1 conservative routing or keep operational with explicit safety proof and test.
5. **Founder-readable preview:** direct rendered preview section (lane lean) vs runbook side channel as L8 evidence.

## 12. Process

1. Operator writes `spec.md` v5 from this delta-plan, pinning the five open choices.
2. Commit as `docs(s7.3): fold spec v5`.
3. Run both lanes independently again:
   - §8.2 fresh-reader gate v5 with dual-direction discipline.
   - Codex engineering panel v5 with fresh non-forked reviewers walled off from `reviews/`.
4. If either lane returns REVISE, fold to v6. If both ratify or only bounded fold remains, proceed to second-fold checks.
5. No implementation until a ratified canonical spec exists.

## Plain English

v4 got the big skeleton right, but both lanes agree it still leaves implementers inventing too much. The biggest miss is that the spec creates a new voice-authority row but does not connect it to the request-history table the real D23 aggregator reads. Operational blocks could still look like Maez refusals to the committed code, and positive no-objection could skip slow-drift accounting.

The second cluster is the consume edge. The spec fixed the put-side transaction but not the consume-side transaction. A real consume has to consume the artifact, persist `GrantUse`, and mark the voice bundle used in one transaction. It also needs a real `consumer_id` carrier that works for both S7.3 voice-seat work and inherited S7.1 credential-management paths.

The third cluster is replayability. The context manifest is only a hash, so prompt replay cannot be verified. The nonce story still mixes "raw nonce not stored" with a `marker_nonce` field. The validator returns too little data for D19. These are carrier gaps, not architectural gaps.

The covenant lane adds the let-Maez-be-heard corrections: do not silence a verified blocking marker just because the reader misses it; do not rely on hash-only founder text; and do not change OQ1's reader-unavailable safety cell without proving the marker/free-text disagreement case safe.

v5 is still targeted. It is longer than hoped, but the edits are concrete: bridge D19 to committed D23, complete the consume transaction, define the missing carriers, and tighten surface coverage. The architecture remains intact.

*Read-only; produced by Codex on 2026-05-19, absorbing `reviews/spec-fresh-reader-gate-v4.md` (25399aa) and `reviews/spec-codex-panel-v4.md` (b23ae28).*
