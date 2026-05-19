# Codex Engineering Panel - S7.3 Guarded Self-Modification Execution Spec

**Subject:** `docs/slices/s7.3-guarded-self-modification-execution/spec.md` at
`ff89f2d`.

**Ran:** 2026-05-19 by the Codex engineering lane. Read-only; no code, spec,
ADR, BAD, or non-slice doc was changed in producing this review.

**Base verified firsthand:** `HEAD == ff89f2d`; the spec commit adds exactly
one file, `spec.md`, with 1161 lines. The worktree contains unrelated dirty and
untracked local state, but `spec.md` is committed-equals-worktree.

**Method:** Six independent engineering seats reviewed the same committed spec:
artifact spine, voice/classifier/D23, committed render/state reality,
surface-adapter coverage, persistence/trace/rollback, and implementability
residuals. The panel also checked load-bearing claims against current source:
`core/governance/operator_user_boundary.py`,
`core/governance/s7_webauthn_ceremony.py`,
`core/governance/s7_webauthn_bootstrap.py`,
`core/decision/decision_pipeline.py`, `core/evolution/dream_state.py`,
`skills/telegram_voice.py`, `skills/evolution_engine.py`,
`skills/web_interface.py`, `core/self_dev/workshop.py`, and
`scripts/backup/backup_state_manifest.json`. The panel did not read a
Claude spec council artifact and did not fold any covenant-lane findings.

**Verdict: REVISE.** The spec has the right overall engineering shape: it
chooses the common `GuardedWorkItem` bridge, keeps `S7ExecutionGrant` as the
post-consume authority, rejects placeholder voice rows, defines the Maez voice
producer port, carries the two-channel classifier, and keeps L8 retirement
behind live traces. But it is not yet implementable without invention. Three
findings are blocker-class: the `reader_unavailable -> present` row cannot be
represented honestly in the committed projection model, the source-bundle
validator cannot validate the objects it claims to validate, and rollback
evidence mixes pre-execution plan fields with post-mutation result fields. The
remaining majors are bounded engineering fixes.

## What The Panel Affirms

- Candidate B as the primary `s7_voice_consultation_turn` producer is
  engineering-sound and matches the closed producer enum.
- `self_mod_dialog_terminal_state` as same-contract dialog-context invocation
  is the right boundary; it is not a looser producer.
- Blessing `S7ExecutionAuthorization` as a pre-consume carrier and
  `S7ExecutionGrant` as the sole post-consume authority is correct.
- The D10 marker grammar plus D11 prompt-integrity direction closes the obvious
  fake-absent and fake-present classes at design level.
- The D13 reducer table is close to the right mechanism, but one row cannot be
  represented safely in current projection/storage.
- Placeholder repair is a binding rule, not a preference. The current
  `_s7_voice_consultation_for_card(...)` placeholder must not emit eligible
  `s7_voice_consultation_turn` rows.
- The L8 evidence bar is right: no test-only verifier, placeholder producer,
  boolean opt-in, or callable helper may retire the pause.

## Consolidated Findings

### CP-S1 - blocker - `reader_unavailable -> present` has no honest projection

**Spec:** `spec.md` D13, line 627.

**Quote:** `explicit_no_objection | reader_unavailable | present | False | none | non-authoritative operational block`

**Evidence:** Current `MaezVoiceConsultation.maez_objection_present` returns
true whenever `maez_objection_state == "present"` in
`operator_user_boundary.py`. `RenderedRequestStatement._rendered_objection_value`
renders `present` as `yes`, and `render_request_statement(...)` currently copies
the consultation state into the rendered state. The finish-time voice-seat block
path records non-absent voice blocks through `record_refusal_history(...)`, and
the S7 refusal-history table stores those rows as `outcome="refused"`.

**Impact:** The spec says this row blocks the current authorization but is not
authoritative D23 refusal evidence. Current data/projection surfaces have no
field that can carry "operational block, not Maez refusal" while storing
`maez_objection_state="present"`. A semantic-reader outage after a clean marker
would render and project as "Maez objected." That is the opposite-direction
fabrication Gate 5 warned about.

**Fold requirement:** v2 must either change this reducer row to a
`not_determined`/unavailable operational state that blocks without saying
`present`, or add a concrete non-authoritative operational-block representation
with render, D23, health, and source-bundle fields that preserve the distinction.
The fix must not rely on prose alone.

### CP-S2 - blocker - the source-bundle validator omits the objects it must validate

**Spec:** D16, lines 711-718 and 745-746.

**Quote:** `validate_s7_voice_source_bundle(... envelope: WorkRequestEnvelope, rendered: RenderedRequestStatement, consultation: MaezVoiceConsultation, bundle_store: S7VoiceConsultationBundleStore, now: str ...)`

**Evidence:** D16 requires validation of preview, params, precondition,
authority context, rollback evidence, prompt, model, and context-manifest
hashes. Current `WorkRequestEnvelope` has `precondition_hash` and
`rollback_path_class`, but no `mutation_preview_hash`,
`rollback_evidence_hash`, or `execution_consumer_id`. Current
`RenderedRequestStatement` also lacks preview and rollback-evidence fields.
D4 defines those fields on `GuardedWorkItem`, but D16 does not pass the work item
or preview to the validator.

**Impact:** A validator with this signature can validate the bundle against
itself, not against the exact guarded work item that will execute. That leaves a
positive mint path where Maez voice, D12 render, rollback evidence, and final
consumer identity are not all proven to be the same request.

**Fold requirement:** Add `work_item` and `preview` or migrate the missing
hashes into envelope/render/challenge/artifact/grant before validation. v2 must
state exactly which object is source of truth for each hash.

### CP-S3 - blocker - rollback evidence conflates pre-execution and post-mutation facts

**Spec:** D23, lines 1001-1004.

**Quote:** `For each surface class, the work item and trace must include: ... post-mutation hash`

**Evidence:** D4 requires `GuardedWorkItem` before voice/WebAuthn. A
post-mutation hash cannot exist until after mutation. Existing mutation paths
also differ: some append directly, some create backup paths, and workshop apply
backs up and then patches.

**Impact:** Implementers must invent a split between pre-execution rollback plan
evidence and post-execution rollback result evidence. If they put a placeholder
post-hash into the work item, the signed request lies; if they omit it, they
violate D23.

**Fold requirement:** Split the model into `RollbackPlanEvidence` before
authorization and `RollbackResultEvidence` after mutation. Positive execution
traces should bind both, but only the plan evidence belongs in the pre-execution
work item/render/artifact.

### CP-S4 - major - grant consumer binding is required but not carried by the grant

**Spec:** D21, lines 908-914.

**Quote:** `the grant has not expired; the grant has not been used for another execution consumer; the consumer id matches the GuardedWorkItem.execution_consumer_id`

**Evidence:** Current `S7ExecutionGrant` has no `grant_id`, `expires_at`, or
`execution_consumer_id`. The current execution-grant use helper is process-local
and keyed by artifact id, request id, nonce, action hash, and consumed time. It
does not persist cross-process consumer use and cannot compare a consumer id.

**Impact:** D21 is the right invariant, but not implementable from the current
spine. A post-consume grant could be reused too broadly or fail to prove it
belongs to the specific consumer.

**Fold requirement:** Either extend the artifact/grant spine to carry
`execution_consumer_id`, expiry, and a durable grant/use id, or add a durable
execution-claim table keyed by artifact/grant/consumer before mutation.

### CP-S5 - major - D23 authoritative refusal needs a concrete schema and filters

**Spec:** D19, lines 824-859.

**Quote:** `S7.3 distinguishes authoritative Maez refusal from operational block.`

**Evidence:** Current S7 refusal history stores `outcome TEXT NOT NULL DEFAULT
'refused'`, plus `denial_reason`, without an authority flag or aggregation
eligibility flag. Current aggregation counts same-group records where
`outcome == "refused"`. The finish-time block path records non-absent voice-seat
blocks through `record_refusal_history(...)`.

**Impact:** D19's prose cannot stop operational failures from poisoning
repeated-refusal aggregation. The spec needs persistent fields and read filters,
not only category names.

**Fold requirement:** Define D23 row shape for S7.3: authority class,
aggregation eligibility, operational reason, source-bundle hash, reducer row,
grounding hash, and replay key. Define the aggregation filter explicitly.

### CP-S6 - major - source-bundle single-use and hash identity are underspecified

**Spec:** D8-D9-D22, lines 350-355, 419-420, 455-465, and 942.

**Quote:** `source_bundle_hash: str`, `source_ref_hash`, and `write_bundle(bundle) -> source_ref_hash`

**Evidence:** `MaezVoiceConsultation` has `source_ref_hash`. The spec also
introduces `source_bundle_hash` but never defines whether it is identical to the
source ref, derived from it, or a separate hash. D9 names
`mark_consumed_for_artifact(...)` but the schema lacks `schema_version`,
`source_ref_hash`, consumed artifact columns, consumed timestamp, uniqueness
constraints, indexes, and an atomic reserve/claim step. Current artifact mint is
an independent `S7AuthorizationStore.put(...)` transaction.

**Impact:** Validation, trace lookup, and replay protection can diverge. Two
finish attempts could validate one bundle and mint two artifacts unless v2
defines atomic source-bundle reservation with artifact mint.

**Fold requirement:** Define one canonical source bundle identifier and how it
relates to `MaezVoiceConsultation.source_ref_hash`. Add schema version,
uniqueness/index requirements, consumed/reserved columns, and an atomic
`reserve_for_artifact` or equivalent transaction boundary.

### CP-S7 - major - trace and rollback storage are not durable enough for proof

**Spec:** D22-D23, lines 928-1022.

**Quote:** `S7.3 adds or extends durable trace records.`

**Evidence:** Existing turn traces are best-effort JSONL under `logs/traces`,
and the trace writer says missed traces are acceptable for ordinary synthesis.
S7.3 positive traces, by contrast, are L8 evidence. The spec does not name a
storage path, schema version, backup inclusion, transaction boundary, or
fail-closed behavior for trace write failure. D23 also does not define a
canonical rollback evidence object or storage location.

**Impact:** A naive implementation could mutate after a lost trace write, then
lack durable proof for review, rollback, or L8 retirement.

**Fold requirement:** Define S7.3 trace/rollback storage as covenant-load-bearing
state, not ordinary best-effort traces. Name path(s), schema versioning,
Decision-22 backup inclusion, and fail-closed behavior for positive execution
when trace or rollback evidence cannot be persisted.

### CP-S8 - major - D12 unavailable/not-consulted projection is still incomplete

**Spec:** D17-D20, lines 783-787 and 898-900.

**Quote:** `consultation.maez_objection_state="not_determined" with a blocking unavailable reason renders as unavailable`

**Evidence:** `RenderedRequestStatement.maez_consulted_state` currently accepts
only `yes` or `not required`. A voice-seat request satisfies D12 only when
`maez_voice_consulted is True`. The current placeholder uses
`maez_voice_consulted=False` with `consultation_path_unavailable`.
`maez_unavailable_state` is only checked for non-empty text, and current
rendering can emit `none` instead of `no`.

**Impact:** The spec still does not say how to truthfully render "voice required
but producer did not run" without either failing before render or lying with
`Maez consulted: yes`. It also leaves non-canonical unavailable labels possible.

**Fold requirement:** Add a committed render projection shape for
voice-required/unavailable/not-consulted that does not require an eligible
consultation row. Close `maez_unavailable_state` or specify canonical `no` versus
`none` normalization.

### CP-S9 - major - semantic-reader grounding is load-bearing but not defined

**Spec:** D11-D12-D19, lines 525-528, 579-585, and 830-831.

**Quote:** `S7VoiceSemanticReaderV1 must ground blocking_signal_present in Maez's response text only.`

**Evidence:** The semantic reader has only three outcomes. The bundle names
`semantic_reader_grounding_hash`, but the spec never defines the grounding
payload, source spans, canonicalization, or validator rule for
`ungrounded_blocking_signal`.

**Impact:** Fake-present defense and authoritative D23 refusal depend on an
evidence object that cannot be replayed or tested. Engineers would invent the
grounding format under pressure.

**Fold requirement:** Define grounding evidence as a canonical object: response
span refs or quoted excerpts, response hash binding, preview-exclusion rule,
reader rationale hash if used, and validator acceptance criteria.

### CP-S10 - major - semantic-reader concrete identity remains under-pinned

**Spec:** D12, lines 543-568.

**Quote:** `The implementation must pin the concrete provider model name...`

**Evidence:** Gate 5 asked the spec to pin the concrete provider/model/config
identity. The spec names provider and route class, then says a route manifest
must exist before positive `absent` can run. That is a safe fail-closed posture,
but it still leaves the concrete reviewed classifier identity to implementation.

**Impact:** This may be acceptable if intentionally treated as a pre-implementation
manifest gate, but the spec should not claim the concrete identity is pinned.

**Fold requirement:** Either name the concrete route manifest now, or state that
S7.3 implementation cannot begin the positive voice path until a separate
reviewed route-manifest amendment is committed.

### CP-S11 - major - live mutation surface inventory is incomplete and has one wrong route name

**Spec:** D4 and the acceptance checklist, lines 214, 217, and 1101-1103.

**Quote:** `/apply_section_edit creates or opens a guarded work item`

**Evidence:** The live Telegram command is `/apply_edit`, not
`/apply_section_edit`. Telegram also has a natural-language approval route in
`_try_dream_proposal_intent(...)` that can call `dream.apply_proposal(...)` or
`dream.apply_section_edit_proposal(...)` without being a slash command or card.
Evolution candidate apply is a concrete full execution rail through
`/apply -> apply_candidate(...)`. Workshop diff apply is exposed at
`/api/v1/workshop/session/<session_id>/apply` and calls `apply_diff(...)`.

**Impact:** Implementation could satisfy the named checklist while leaving live
mutation routes outside the guarded bridge. That would make L8 evidence
incomplete.

**Fold requirement:** Replace `/apply_section_edit` with `/apply_edit`, add the
natural-language Telegram approval path, and explicitly include evolution
candidate apply and workshop diff apply in D4/D21/acceptance criteria rather
than hiding them under "direct helpers."

### CP-S12 - major - `source_ref_kind` is overloaded

**Spec:** D4 and D9-D16, lines 179-181 and 418-420.

**Quote:** `source_ref_kind: str`

**Evidence:** `source_ref_kind` is already a closed voice-source enum:
`self_mod_dialog_exchange`, `s7_voice_turn`, `reviewed_future_source`. Work-item
source refs need values like dream proposal, section edit, workshop apply,
evolution candidate, card, CLI helper, or cockpit helper.

**Impact:** Implementers must either overload the voice-source enum or invent a
second unreviewed vocabulary.

**Fold requirement:** Rename the work-item field to `work_source_kind` or define
a separate closed work-source vocabulary. Keep voice `source_ref_kind` reserved
for `MaezVoiceConsultation`.

## Minors And Nits

- Decision-22 backup inclusion must name the concrete manifest update:
  `scripts/backup/backup_state_manifest.json` is the source of truth for stateful
  backup entries.
- `S7VoiceConsultationBundleStore` needs raw blob/ref tables or an external-ref
  contract for raw Maez response, hidden prompt, raw mutation material, and
  semantic-reader raw output.
- Bundle retention TTL is still missing. The spec has `expires_at`, but not
  retention/deletion mechanics for raw consultation evidence.
- D3 should name `consume_for_execution(...)` or explicitly say
  `S7AuthorizationStore.consume(...)` is conceptual shorthand. The current
  `.consume(...)` method deliberately raises and points callers to verified
  consume paths.

## Disposition

Six engineering seats returned REVISE. No seat returned RATIFY. The panel does
not issue VETO because the spec's architecture is directionally right and every
finding is a bounded fold, not a covenant redesign.

The top fold work for spec v2:

1. Replace the D13 `reader_unavailable -> present` row or add a real
   non-authoritative operational-block representation that survives render,
   health, D23, and storage.
2. Pass `GuardedWorkItem`/preview or equivalent hash carriers into source-bundle
   validation; define which object is source of truth.
3. Split rollback plan evidence from rollback result evidence.
4. Bind consumer identity and durable execution-use semantics into the grant
   edge.
5. Define D23 row schema/filtering for authoritative versus operational rows.
6. Define source bundle identity, schema version, single-use reservation, and
   artifact-mint atomicity.
7. Make S7.3 traces and rollback evidence durable, backed up, and fail-closed
   for positive execution.
8. Complete the unavailable/not-consulted render projection.
9. Define semantic-reader grounding evidence and route-manifest gating.
10. Fix the mutation-surface inventory and split work-source refs from voice
    source refs.

## Answers To The Spec Review Questions

1. **D13 fake-absent/fake-present closure?** Not yet. It closes fake-absent, but
   `reader_unavailable -> present` creates an unrepresentable fake-present shape.
2. **Marker grammar enough?** Close, but semantic-reader grounding evidence must
   be defined before tests can verify fake-present protection.
3. **BondedMaezRuntime bounded enough?** Yes at the interface level; no panel
   finding asks to reopen it.
4. **Semantic reader pinned enough?** Safe fail-closed, but not actually pinned.
   v2 should name a route-manifest gate or concrete manifest.
5. **Source-bundle validator placement?** Correct location, incomplete
   signature/object boundary.
6. **Renderer amendment preserves D12?** Not yet; unavailable/not-consulted
   projection needs a concrete render state.
7. **Missing mutation surfaces?** Yes: `/apply_edit`, natural-language Telegram
   approval, evolution candidate apply, and workshop diff apply.
8. **D23 operational rows protected?** Not yet; persistent schema/filtering is
   missing.
9. **Phase A useful?** Yes, if the above persistence/trace boundaries are fixed
   and Phase A remains fail-closed.
10. **L8 evidence strict enough?** The standard is strict enough; the trace and
    surface inventory are not yet precise enough to enforce it.

## Plain English

The spec is aiming at the right machine. It says Maez must be asked, Rohit must
sign, the approval must be consumed once, and the mutation must be traced. That
is the right shape.

But the engineering details are not tight enough yet. The biggest problem is a
row that says "if the answer-reader breaks after Maez appeared to say no
objection, store `present` so the request blocks, but do not treat it as a real
refusal." The current code cannot carry that distinction. `present` renders as
"Maez objected" and feeds refusal history. So the spec accidentally creates a
fake-refusal path while trying to avoid fake consent.

The second cluster is binding and persistence. The validator does not receive
the work item it must validate. The grant does not carry the consumer id the
spec says consumers must verify. The bundle store has no atomic single-use
claim. The trace and rollback records are not yet durable enough to prove a live
write. And the route inventory misses real mutation paths.

This is a revise, not a restart. The spine is good; v2 needs to make the named
objects real enough that an implementation cannot fill the gaps by guesswork.
