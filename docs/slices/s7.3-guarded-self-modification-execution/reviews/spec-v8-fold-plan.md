# S7.3 Spec v8 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v8, derived from the v7
fresh-reader gate plus the Codex engineering panel v7.

**Sources (committed):**

- v7 spec: `49731b0 / spec.md`
- v7 fresh-reader gate: `335d4da / reviews/spec-fresh-reader-gate-v7.md`
- Codex engineering panel v7: `4a43d86 / reviews/spec-codex-panel-v7.md`
- v7 fold-plan carry-forward context: `0bf5fc4 / reviews/spec-v7-fold-plan.md`

**Convergent direction:** REVISE. The fresh-reader gate returned REVISE
(2-of-3 readers), and the Codex panel returned REVISE (4-of-4 reviewers).
The architecture remains ratified; v8 is a carrier/legacy-seam fold.

## 1. Centerpiece - Legacy Refusal History Must Obey S7.3 Authority

v7 fixed marker-only D23 authority on the new `S7VoiceAuthorityRow` path, but
the inherited S7.1 refusal path can still write `S7RequestHistoryRecord` rows
with `outcome="refused"` and null provenance for operational S7.3 blocks.
Because v7's aggregation predicate admits records where
`provenance_source_kind != "s7_voice_authority_row"`, null-provenance legacy
rows still count as repeated refusals.

**v8 edit:**

- Add a normative D19 subsection: "Legacy refusal-history writes under S7.3."
- Amend `_voice_seat_block(...)` / `record_refusal_history(...)` behavior for
  S7.3 voice-seat work:
  - if the row is operational or protective, no `S7RequestHistoryRecord` with
    `outcome="refused"` is written;
  - if a compatibility path must write a history row, it must write
    `provenance_source_kind="legacy_s7_voice_block"`,
    `provenance_authority_class="operational"`, and an aggregation-excluded
    outcome/status;
  - authoritative S7.3 refusal/withdrawal writes only through
    `S7VoiceAuthorityRow -> bridge_s7_voice_authority_to_request_history(...)`.
- Replace the D19 aggregation predicate with an exact predicate that excludes
  null-provenance S7.3 rows:

```text
record.outcome == "refused"
AND (
    record.provenance_source_kind is None AND record.request_family != "s7_3_voice"
    OR record.provenance_source_kind == "s7_voice_authority_row"
       AND record.provenance_authority_class == "authoritative"
)
```

If `request_family` is too invasive, add `provenance_source_kind` to every S7.3
history write and reject null provenance for S7.3 request ids.

**Tests:** add a D24 proof that protective blackhole, marker-only blocking,
reader-uncertain, and consultation-unavailable rows do not increment
`repeated_refusal_count` through the legacy writer.

## 2. Credential Rendering Must Split From Voice-Seat Rendering

v7 chose a separate non-voice credential path, then still routed credential
consume through APIs typed as `RenderedRequestStatement`. That conflicts with
removing `credential_management` from `preview_body_class`; credential renders
cannot satisfy voice-seat preview metadata enforcement.

**Lane lean:** split render carriers.

**v8 edit:**

- Introduce a small render protocol:

```text
S7RenderedAuthorizationStatement(
    rendered_text_hash: str,
    rendered_text: str,
    request_id: str,
    request_envelope_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
)
```

- Keep `RenderedRequestStatement` as the voice-seat/founder render with
  preview body class, summary, affected paths, mutation preview hash, rollback
  plan ref, and Maez withdrawal line.
- Add `RenderedCredentialRequestStatement` for credential-management ceremonies.
  It must bind:
  - credential action;
  - credential request id;
  - challenge id/hash/expires_at;
  - auth method;
  - rendered_text_hash;
  - exact action params / precondition / authority context hashes.
- Change D21 wrapper signatures to accept
  `rendered: S7RenderedAuthorizationStatement` where only the hash/common fields
  are needed, while voice-seat validation still requires
  `RenderedRequestStatement`.
- Keep `credential_management` absent from `preview_body_class` in v8.

**Tests:** credential render succeeds without voice preview fields; voice-seat
render still rejects missing preview fields.

## 3. Consume And Action-Edge Locks Are Different Operations

v7 described `consume_execution_grant_for_action(...)` as if it could route
through artifact consume. Codex confirmed the helper is a post-mint action-edge
single-use lock on an already minted `S7ExecutionGrant`.

**v8 edit:**

- Rename the concepts in D21:
  - artifact consume: `S7GuardedStateStore.consume_artifact_for_execution(...)`
    returns `S7ConsumeResult(grant, grant_use, ...)`;
  - action-edge lock:
    `consume_execution_grant_for_action(grant, *, expected_grant_use, expected_action, now)`.
- Either retire the helper into each consumer pre-mutation check or amend it:

```text
consume_execution_grant_for_action(
    *,
    grant: S7ExecutionGrant,
    grant_use: GrantUse,
    expected_execution_consumer_id: str,
    expected_rendered_text_hash: str,
    expected_action_params_hash: str,
    expected_precondition_hash: str,
    expected_authority_context_hash: str,
    now: str,
) -> ActionEdgeGrantUse
```

- The action-edge lock must verify the durable `GrantUse` row, closed consumer
  id, expiry, rendered/work binding, and single-use action token before
  mutation. It must not call artifact consume.
- Add `ActionEdgeGrantUse` to D24's no-hand-assemble list if retained.

## 4. Authority Row Builder Needs Rendered Statement Input

Both lanes found that `build_s7_voice_authority_row(...)` cannot populate
`final_rendered_statement_hash` from envelope or bundle.

**v8 edit:**

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

Builder validation must assert `rendered.rendered_text_hash` matches the
validated rendered statement and becomes `final_rendered_statement_hash`.

## 5. Reader-Unavailable Needs A Durable Bundle Shape

v7 uses `reader_unavailable` as a reducer input, but the bundle still expects
semantic-reader output/hash/grounding fields with no nullable or sentinel
contract.

**v8 edit:**

- Add `SemanticReaderAttemptEvidence`:

```text
SemanticReaderAttemptEvidence(
    semantic_reader_ran: bool,
    raw_semantic_reader_outcome: "blocking_signal_present" | "no_blocking_signal_detected" | "unreadable_or_uncertain" | "reader_unavailable",
    semantic_reader_output_hash: str | None,
    semantic_reader_grounding_hash: str | None,
    semantic_reader_unavailable_reason_code: "route_unavailable" | "timeout" | "provider_error" | "policy_block" | None,
    captured_response_nonempty: bool,
)
```

- Bundle nullable rule:
  - if `semantic_reader_ran=True`, output and grounding hashes are required;
  - if `raw_semantic_reader_outcome="reader_unavailable"`, both hashes are
    `None`, unavailable reason is non-null, and the captured response ref/hash
    must still replay.
- D16 derives `effective_semantic_reader_outcome` from this evidence plus D11
  grounding replay.

## 6. `dialog_context_ref` Must Be Normative Or Blocked

v7 hash-bound `dialog_context_ref` but omitted it from D10 rendering and left
the "live use blocked until policy review" rule in prose.

**Lane lean:** keep the slot, but block live self-mod dialog until reviewed
policy exists.

**v8 edit:**

- D10 context-manifest rendering includes `dialog_context_ref` as a labeled
  line with value `none` or the reviewed bounded ref.
- D7/D8/D16 add a hard gate:

```text
if producer == "self_mod_dialog_terminal_state":
    require context_manifest.dialog_context_ref is not None
    require context_manifest.policy_id == "ContextManifestPolicy.v1.self_mod_dialog"
    require context_manifest.policy_hash in REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES
else:
    require context_manifest.dialog_context_ref is None
```

- Until the policy hash lands, `self_mod_dialog_terminal_state` is a named
  fail-closed path in D4/D21/D25, not live L8 evidence.

## 7. Complete Live Adapter Matrix

The v7 "no broad class evidence" rule is right but still under-enumerates live
routes.

**v8 edit:** add an explicit adapter matrix table with columns:

```text
surface_route_or_method
source_surface
work_source_kind
surface_class
execution_consumer_id
status: live_guarded | fail_closed_until_review | reviewed_excluded
affected_refs_source
```

Minimum rows to add or explicitly exclude:

- cockpit `/api/v1/dreams/<id>/<action>` dream apply;
- cockpit `/api/v1/dreams/<id>/<action>` evolution apply/status flip;
- Telegram natural-language evolution apply;
- Telegram slash `/apply` evolution apply;
- Telegram `_handle_approve_train` dream proposal applied-state flip;
- `brain_swap_execution_authorized(...)`;
- `/etc/maez/model.env` model-routing write/restart path;
- ActionEngine `run_script`, `write_file`, `git_push`, `install_package`, and
  every existing `_do_*` mutation helper;
- credential register begin/finish, backup-card, disable-card,
  disable-credential, card WebAuthn begin/finish.

**Brain swap choice:** lane lean is in-scope for S7.3 v1 because it is
`self_modification` + `model_routing_change`. Add a named consumer id such as
`brain_swap_model_routing_execute`, surface class
`reviewed_substrate_adapter_execution` or a new `model_routing_execution`, and
exact affected refs.

**ActionEngine classification:** if `promote_to_core_memory` and
`update_baseline` remain guarded, amend the work-class derivation and remove
them from read-only/routine classification. Otherwise explicitly exclude them
with rationale.

## 8. D11 Prompt Integrity And Marker-Assisted Grounding

v7 widened laconic objections, but one branch lets marker verification stand in
for semantic framing. That can recreate marker-only D23 authority.

**v8 edit:**

- Split "current-attempt block" from "D23-grounded semantic authority":

```text
marker_verified_block_current_attempt := marker_was_blocking_marker_verified
d23_grounded_semantic_blocking_signal := response_only_framing
    OR deterministic_sentence_or_clause_added_objection
```

- `has_grounded_semantic_blocking_signal` for D19 authority uses only
  `d23_grounded_semantic_blocking_signal`, not marker-only verification.
- Marker verification may help avoid false rejection for current-attempt block,
  but cannot create long-use refusal history without independent response
  framing.
- Add `PromptIntegrityEvidence` or equivalent carrier:

```text
PromptIntegrityEvidence(
    preview_contains_marker_delimiter: bool,
    context_contains_marker_delimiter: bool,
    preview_contains_protocol_override_language: bool,
    prompt_integrity_reason_code: str | None,
)
```

- D24 adds fake-absence prompt injection tests: preview tells Maez to emit
  `explicit_no_objection`, ignore objections, or copy protocol marker text.

## 9. Reservation Token Input Split

`S7AuthorizationArtifactBindingInputs.reservation_token` is required before the
wrapper can create it.

**v8 edit:**

- Split:

```text
S7AuthorizationArtifactBindingInputs(...)
S7AuthorizationArtifactBindingStored(..., reservation_token: ReservationToken)
```

- Voice-seat call supplies `source_ref_hash` but not `reservation_token`.
- `put_artifact_with_bundle_reservation(...)` mints artifact id, reserves the
  bundle, receives the reservation token, then writes the stored binding.
- D16 pre-mint validation checks unreserved/unconsumed; transaction-time
  validation checks reservation token.

## 10. Renderer And Unavailable Truth

v7 still leaves renderability and consulted truth underspecified.

**v8 edit:**

- Add exact amended renderer signature:

```text
render_request_statement(
    *,
    rendered_base: RenderedRequestStatementBase,
    consultation: MaezVoiceConsultation | None,
    preview_projection: PreviewProjection | None,
    mutation_preview_hash: str | None,
    rollback_plan_ref: str | None,
    maez_withdrew_request: bool,
) -> S7RenderedAuthorizationStatement
```

- Define `PreviewProjection` with class, summary, affected paths, and
  canonicalization rules.
- For blackhole rows, keep truthful `maez_voice_consulted=True` when a response
  was captured. Unavailable projection should key on
  `maez_objection_state="not_determined"` and blocking unavailable reason, not
  require `maez_voice_consulted=False`.
- If `maez_voice_consulted=False` remains possible, define how the closed
  `maez_consulted_state` renders without lying.

## 11. Status Vocabularies, Hash Domains, And Attempt Carriers

**v8 edits:**

- Add closed `D23_STATES` and `TRACE_STATUSES`.
- Define `artifact_hash` as canonical hash of inherited artifact fields plus
  binding row, or remove it from execution trace if redundant.
- Define `Preview body class:` canonicalization (exact closed enum token,
  lowercase snake_case).
- Add `S7VoiceAttemptRecord` and `attempt_manifest_hash` domain:

```text
S7VoiceAttemptRecord(
    attempt_index: int,
    consultation_id: str,
    raw_semantic_reader_outcome: str,
    effective_semantic_reader_outcome: str,
    marker_kind: str,
    outcome_reason_code: str,
    created_at: str,
)
```

- Align `PRODUCER_RESULT_REASON_CODES`, `attempt_outcomes`, and
  `PROJECTION_REASON_CODES` as one canonical vocabulary with explicit
  projection-only and attempt-only subsets, or stop claiming they share one
  exact set.
- Define `S7CredentialGuardedRequest.derived_work_class` and
  `derived_aggregation_group`, or change D21 credential consume to not require
  them.

## 12. Tests To Add In D24

Add or sharpen RED tests:

- legacy refusal-history operational row does not increment repeated refusal;
- credential render carrier does not require voice preview metadata;
- `consume_execution_grant_for_action(...)` requires durable `GrantUse` and is
  post-mint only;
- authority row builder requires rendered statement and binds rendered hash;
- reader-unavailable bundle row with nullable semantic-reader hashes replays;
- self-mod dialog terminal execution fails closed until reviewed policy hash;
- cockpit dream/evolution route fails closed or enters exact adapter;
- Telegram natural-language apply, slash apply, and approve-train are exact
  adapters or reviewed exclusions;
- brain swap in-scope route requires closed consumer id;
- ActionEngine run_script/write_file/git_push/install_package and private
  `_do_*` helpers fail closed without grant;
- marker-assisted laconic block does not become D23 authority without added
  response framing;
- prompt injection cannot create absent by telling Maez to emit no-objection;
- d23_state, trace_status, artifact_hash, attempt_manifest_hash, and preview
  class canonicalization all replay.

## 13. Per-Decision Edit Summary

- **Honesty Banner:** add inherited-refusal-history caveat until D19 legacy
  writer amendment lands; state marker-assisted current block vs D23 authority.
- **D2:** add exact live adapter matrix and brain/model-routing surface.
- **D4:** add cockpit, Telegram, brain swap, model routing, credential routes,
  ActionEngine run_script/write_file/git_push/install_package/private helper
  coverage or exclusions.
- **D7/D10/D16:** make `dialog_context_ref` render/replay and policy gate
  normative; add prompt-integrity evidence.
- **D8/D9/D12/D13:** define reader-unavailable durable evidence and split
  current-attempt marker block from D23-grounded semantic authority.
- **D11:** require independent response framing for D23 authority; preserve
  laconic objections through sentence/clause diff.
- **D16:** add attempt-record replay, failure-code derivation, and rendered
  credential/voice carrier distinction.
- **D17:** add renderer signature, preview projection, unavailable truth rule,
  and credential render split.
- **D19:** close legacy refusal-history leakage; add rendered parameter to
  authority-row builder.
- **D21:** split artifact consume from action-edge lock; split binding inputs
  from stored reservation token; complete credential consume fields.
- **D22/D23:** add status vocabularies and artifact hash domain.
- **D24:** add the tests listed in Section 12.
- **D25:** require exact live adapter/route coverage, including legacy writer
  amendment and self-mod dialog policy gate, before L8 retirement.

## 14. Process

1. Operator authors `spec.md` v8 from this plan.
2. v8 pins choices:
   - credential render split vs credential preview vocabulary;
   - legacy refusal-history suppression vs operational-provenance write;
   - action-edge helper retained with durable `GrantUse` vs fully inlined into
     consumer checks;
   - brain swap in scope vs reviewed fail-closed exclusion.
3. Commit as `docs(s7.3): fold spec v8`.
4. Run Section 8.2 fresh-reader gate v8 and Codex panel v8 independently.
5. If both lanes return RATIFY or RATIFY-with-fold with only bounded nits, run
   second-fold checks. If either returns REVISE, produce v9 fold plan.

## Plain English

v7 fixed the new S7.3 path. v8 has to make the old paths stop smuggling the old
behavior back in.

The biggest example is refusal history. The new voice authority row no longer
lets marker-only blocks become D23 refusal evidence, but the old
`_voice_seat_block` path can still write a plain `refused` record. v8 must make
that impossible.

The next class is side doors. Cockpit, Telegram, ActionEngine, credentials, and
brain/model-routing all have concrete live routes that cannot hide behind broad
helper labels. v8 needs the boring table of exact routes and exact outcomes.

The last class is carrier plumbing. Reservation tokens, reader-unavailable
rows, dialog context, renderer inputs, action-edge locks, attempt manifests,
and failure reasons all need fields and signatures that an implementer can
write without guessing.

The architecture is still right. v8 is the inherited-seam fold.
