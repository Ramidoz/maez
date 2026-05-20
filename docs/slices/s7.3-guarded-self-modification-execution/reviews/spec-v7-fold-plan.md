# S7.3 Spec v7 Fold Delta-Plan

**Subject:** targeted edits to `spec.md` for v7, derived from both v6 review lanes.

**Sources (committed):**
- v6 spec: `df84d8f / spec.md`
- v6 fresh-reader gate: `8f88c1a / reviews/spec-fresh-reader-gate-v6.md` (REVISE; 1 covenant-load-bearing blocker plus bounded carrier residuals)
- Codex engineering panel v6: `26323db / reviews/spec-codex-panel-v6.md` (REVISE; 4/4 reviewers REVISE)
- v6 fold input: `64144d0 / reviews/spec-v6-fold-plan.md`

**Convergent direction:** REVISE. v6 is the closest S7.3 spec yet: two of
three covenant readers returned RATIFY-with-fold, all Codex reviewers affirmed
the core architecture, and every v5 carrier-vs-prose gap materially landed.
But both lanes found bounded blockers that prevent canonicalization.

**v7 shape:** small carrier/fold repair, not redesign. The architecture remains:
Maez is consulted through a reviewed producer, Rohit signs readable preview plus
hashes, the artifact consumes once into a grant, mutations verify the grant, and
traces/rollback evidence bind the path. v7 closes the last predicate, carrier,
and live-edge holes.

## 1. Centerpiece - No Fake D23 Refusal Evidence

The covenant gate's load-bearing blocker is that v6 lets marker-only verified
blocking/withdrawal become authoritative D23 evidence even though the Honesty
Banner admits a same-box privileged actor can fabricate nonce-bearing markers in
the active window.

**v7 edit:**

- D13: marker-verified blocking/withdrawal rows block the current attempt, but
  are `authority_class="operational"` unless
  `has_grounded_semantic_blocking_signal=True`.
- D19: `S7VoiceAuthorityRow` eligibility for refusal/withdrawal history requires
  `has_grounded_semantic_blocking_signal=True`.
- Remove D19 predicate arms that admit authority solely from
  `marker_was_blocking_marker_verified` or
  `marker_was_withdrawal_marker_verified`.
- Honesty Banner: explicitly name both harms:
  - fake absence by disabling/blackholing reader;
  - fake refusal evidence by marker-only same-box injection.
- Future cryptographic identity substrate slice may promote signed marker-only
  rows to authoritative D23 evidence; S7.3 v1 does not.

Current-attempt behavior remains fail-closed: a verified marker-only objection
or withdrawal still blocks the attempted mutation. It just does not poison
long-use refusal history.

## 2. Blackhole Reader Row Must Not Render As Maez Objected

Codex found that v6 routes `explicit_no_objection + reader_unavailable` to
`maez_objection_state="present"` while saying it is operational-only. That can
render as "Maez objection present: yes" and can leak into legacy refused-history
paths.

**v7 edit:**

- Split the D13 row by `captured_response_nonempty`:
  - `True`: `maez_objection_state="not_determined"`,
    `unavailable_reason_code="semantic_reader_unavailable"`,
    `authority_class="operational"`,
    `protective_block_reason="reader_unavailable_after_captured_response"`.
  - `False`: same output, with
    `protective_block_reason="reader_unavailable_no_captured_response"` or
    `None` (operator choice; lane lean: `None`).
- D18: remove the "present" exception. The row blocks via unavailability, not
  by pretending Maez objected.
- D17: no rendered line may say `Maez objection present: yes` for this row.
- D19: operational blackhole rows write no refused history.
- D24: add tests for captured-response true and false branches.

This keeps the v5/OQ1 safety property: a disabled reader cannot convert a
captured response into consent.

## 3. Credential Management: Pick One Non-Voice Path And Thread It Everywhere

v6 pins credential-management as guarded but not Maez voice-seat and not
`GuardedWorkItem`, but other sections still require work items, bundle
reservation, trace/rollback, and L8 behavior as if credential paths were voice
paths.

**v7 edit (lane lean: separate non-voice credential path):**

- D4: explicitly carve credential-management out of "every S7.3 mutation path
  materializes `GuardedWorkItem`"; instead define
  `S7CredentialGuardedRequest`.
- D9/D21: add
  `put_credential_artifact_with_binding(...)` or an overload of
  `put_artifact_with_bundle_reservation(...)` that does not take
  `source_ref_hash` and does not reserve `S7VoiceBundleUse`.
- D21: credential consumers verify closed `execution_consumer_id`, artifact
  binding, challenge binding, grant, `GrantUse`, and expiry, but skip voice
  bundle checks.
- D22: define credential pending trace:
  - begin consumes authorization and writes pending trace plus
    `S7CredentialRegistrationGrantBinding`;
  - finish verifies binding and finalizes trace;
  - abandoned challenge or replay writes failed/expired trace.
- D23: define rollback/manual-review semantics for credential registry writes
  and credential disable.
- D25: state credential-management L8 evidence requires credential traces and
  grant/challenge bindings, not Maez voice traces.
- D-Enum-Amendment: remove `credential_management` from `preview_body_class`
  for S7.3 v1, or mark it reserved and unusable. Lane lean: remove from v1.

## 4. Complete Live Mutation Surface Enumeration

Both lanes found that broad helper categories still hide live mutation doors.

**v7 edit:**

- D4/D21: add a concrete adapter matrix for:
  - cockpit dream/evolution apply paths in `skills/web_interface.py`;
  - CLI evolution apply path (`python -m skills.evolution_engine apply <id>`);
  - ActionEngine mutation helpers beyond the five named ids:
    `run_shell`, `execute_script`, `modify_config`, `register_new_skill`,
    `delete_file`, `sudo_command`, plus covenant-gate names:
    `_do_run_shell`, `promote_to_core_memory`, `update_baseline`,
    `_do_git_commit`, `run_script`, `_do_kill_process`,
    `_do_restart_service`, `write_outside_maez`.
- For each path, choose one:
  - reviewed adapter with closed `execution_consumer_id`; or
  - reviewed exclusion that proves it cannot touch Maez substrate; or
  - fail-closed until a future reviewed adapter.
- Resolve `append_to_file -> run_shell`: either refactor append to direct write
  or give `run_shell` its own constrained consumer id and adapter contract.
- D25: L8 evidence cannot rely on `cli_helper_execute`,
  `cockpit_helper_execute`, or `reviewed_substrate_adapter_execute` unless the
  concrete route/method is listed.

## 5. Surface-Class Carrier Closure

`surface_class` remains a prose label, but L8 evidence depends on it.

**v7 edit:**

- D-Enum-Amendment: add `SURFACE_CLASSES` closed vocabulary:
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
  credential_management_execution
  ```
  If credential paths stay separate, mark `credential_management_execution` as
  credential-only L8 evidence, not voice-seat evidence.
- D2/D4: add `surface_class_for(source_surface, work_source_kind, work_class)`
  table, mirroring the consumer-id table.
- D22: add `surface_class` to `S7VoiceConsultationTrace`.

## 6. Nonce Lifecycle: Reserved Is Not Spent

Both Codex and covenant findings converged on nonce-state ambiguity.

**v7 edit:**

- Replace `s7_spent_consultation_nonces` with `s7_consultation_nonce_uses`.
- Define:
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
- Parser accepts only the current `reserved` row for the consultation/request.
- Accepted marker atomically transitions to `accepted_spent` during bundle write.
- Reuse transitions or records `rejected_reused` and fails closed.
- D10/D16/D24: update all spent-nonce wording and tests accordingly.
- Copy `consultation_expires_at` into `bundle.expires_at` at `write_bundle(...)`.

## 7. D11 Laconic Objections Must Remain Hearable

Covenant gate found v6 can over-reject terse objections that quote the proposed
change and then say "No."

**v7 edit:**

- D11: widen `response_with_preview_quote` grounding:
  - accepted if at least one response-only framing span exists; OR
  - `marker_was_blocking_marker_verified=True` and the response has
    non-whitespace content outside the marker; OR
  - sentence/clause-level deterministic diff shows the response adds objection
    framing to preview text.
- Because marker-only rows no longer create D23 authority by themselves (Section
  1), the marker can help make laconic text readable without re-opening fake
  D23 refusal evidence.
- D24: add laconic objection test: preview contains dangerous command; Maez
  quotes command plus "No"; row blocks and becomes authoritative only when the
  semantic grounding branch is satisfied.

## 8. D19 Bridge: Exactly Once, With Closed Statuses

v6 can double-write withdrawal and leaves `history_bridge_status` open.

**v7 edit:**

- D-Enum-Amendment: add `HISTORY_BRIDGE_STATUSES`:
  ```text
  not_required
  bridged
  suppressed_operational
  bridge_failed_retryable
  bridge_failed_terminal
  ```
- D19: bridge exactly one `S7RequestHistoryRecord` per
  `S7VoiceAuthorityRow`.
- Withdrawal precedence:
  - if `maez_withdrew_request=True`, write one `outcome="refused"` row with
    `provenance_voice_event="withdrawal"`;
  - else if `maez_objection_state="present"`, write one `outcome="refused"` row
    with `provenance_voice_event="refusal"`.
- Operational rows either write no history or write `outcome="blocked"`; pick
  one. Lane lean: no request-history row for operational S7.3 voice rows; keep
  operational evidence in traces/authority row only.
- Add exact `assess_aggregation_risk` filter:
  ```text
  record.outcome == "refused"
  AND (
      record.provenance_source_kind != "s7_voice_authority_row"
      OR record.provenance_authority_class == "authoritative"
  )
  ```
- Add `build_s7_voice_authority_row(...)` signature.
- Add `mutation_preview_hash` to `S7VoiceAuthorityRow` for audit/replay.

## 9. D16 And Validator Carrier Repairs

**v7 edits:**

- Rendered-to-bundle field equality predicates:
  ```text
  rendered.mutation_preview_hash == bundle.mutation_preview_hash
  rendered.rollback_plan_ref == bundle.rollback_plan_ref
  rendered.maez_withdrew_request == reducer_output_withdrew
  rendered.preview_body_class == render_preview_projection(preview).preview_body_class
  rendered.preview_summary == render_preview_projection(preview).preview_summary
  rendered.preview_affected_paths == render_preview_projection(preview).preview_affected_paths
  ```
- Context manifest hash routing: change D16 from `manifest_id excluded` to
  `manifest_id and created_at excluded`.
- Add `preview_body_ref` to `MutationPreviewArtifact` so validator replay can
  recover `preview_body_text` deterministically.
- Move bundle-reservation validation into
  `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)`, or add
  `MintValidationContext(artifact_id, reservation_token, phase)` to
  `validate_s7_voice_source_bundle(...)`. Lane lean: pre-mint validator checks
  unreserved/unconsumed; guarded transaction checks reservation token.
- Split semantic-reader outputs:
  ```text
  raw_semantic_reader_outcome
  effective_semantic_reader_outcome
  ```
  D13 consumes the effective outcome after D11 deterministic grounding replay.

## 10. D21 Store, Grant, And Challenge Carriers

**v7 edits:**

- Replace `...` placeholders in amended inherited signatures with full kwargs.
- Add `S7ConsumeFailureReasonCode` closed vocabulary and mapping table for:
  stale rendered request, action-params mismatch, expired authority context,
  supersession, covenant ceremony failure, already consumed, SQL failure,
  missing grant use, consumer id mismatch, expired challenge, expired grant.
- Carry WebAuthn challenge expiry:
  - add `challenge_expires_at` to `S7AuthorizationArtifactBindingInputs`; or
  - require mint wrapper to load challenge by `challenge_id/challenge_hash`.
  Lane lean: add `challenge_expires_at` to binding inputs and verify it against
  the loaded challenge row.
- Persist work-item/source-surface derivation at artifact mint:
  ```text
  work_item_id
  source_surface
  work_source_kind
  expected_execution_consumer_id
  ```
  in `S7AuthorizationArtifactBinding`.
- Explicitly retire or amend `consume_execution_grant_for_action(...)` so
  ActionEngine cannot bypass durable `GrantUse`, closed consumer id, expiry, and
  rendered/work-item binding.
- Specify `S7CredentialRegistrationGrantBinding` is written by the
  `after_consume_before_commit` callback inside
  `S7GuardedStateStore.consume_artifact_for_execution(...)`, unless v7 chooses a
  separate credential consume wrapper.

## 11. Rendering And Helper Boundaries

**v7 edits:**

- Replace the global `voice_consultation_satisfies_request(...)` rendering
  relaxation with a renderer-only helper:
  ```text
  voice_consultation_renderable_for_unavailable(envelope, consultation) -> bool
  ```
  Keep `voice_consultation_satisfies_request(...)` strict for mint/recheck.
- Bonded runtime assistant boundary:
  - `BondedMaezRuntimeTurn` returns only model continuation after prompt;
  - runtime strips prompt prefix and records assistant segment boundaries;
  - parser scans rendered prompt after substitution for marker delimiters and
    fails closed if untrusted preview/context contains live marker delimiters.
- `self_mod_dialog_terminal_state` context:
  - either add `dialog_context_ref` with reviewed
    `ContextManifestPolicy.v1.self_mod_dialog`; or
  - mark self-mod dialog terminal execution blocked until that policy lands.
  Lane lean: add the slot but require reviewed policy before live use.

## 12. Trace And Vocabulary Sharpness

**v7 edits:**

- Normalize D23 trace vocabulary: choose `d23_state` everywhere or define
  mapping. Lane lean: use `d23_state` in both traces.
- Add to `S7VoiceConsultationTrace`:
  ```text
  surface_class
  marker_was_explicit_no_objection_verified
  protective_block_reason
  classifier_reason_code
  ```
- Move `BLOCKING_UNAVAILABLE_REASONS` definition to D-Enum-Amendment only; D17
  references it.
- Define `challenge_hash` domain.
- Clarify `PROJECTION_REASON_CODES.none` usage.
- Clarify D9 `marker_kind` nullable phrasing: nullable only before parser result
  object exists; immutable bundle stores final closed value.
- Define `S7ExecutionGrant` mint-token preservation for `grant_id`,
  `expires_at`, and `execution_consumer_id`.

## 13. D24 Test Bar Expansion

Extend no-hand-assembly list to include every v6/v7 covenant-load-bearing
carrier:

```text
S7AuthorizationArtifactBinding
S7VoiceConsultationBundle
SemanticReaderGroundingEvidence
S7VoiceAuthorityBooleans
S7VoiceReduction
ReservationToken
S7ConsumeResult
S7VoiceAuthorityRow
S7CredentialRegistrationGrantBinding
S7ConsultationNonceUse
RollbackPlanEvidence
RollbackResultEvidence
```

Add RED tests for:

- marker-only verified blocking/withdrawal blocks current attempt but does not
  write D23 refusal evidence;
- blackhole reader true/false captured-response branches;
- operational protective rows do not render as "Maez objected";
- withdrawal bridge exactly once with withdrawal precedence;
- nonce first-use accepted, reuse rejected;
- credential begin/finish trace lifecycle;
- ActionEngine/cockpit/CLI mutation surfaces fail closed unless enumerated;
- `consume_execution_grant_for_action(...)` cannot bypass D21;
- rendered-to-bundle equality predicates;
- raw/effective semantic-reader outcome split;
- laconic objection remains hearable.

## 14. Per-Decision Edit Summary

- **Honesty Banner:** add fake-refusal-evidence harm and marker-only D23
  limitation.
- **D-Enum-Amendment:** add `SURFACE_CLASSES`, `HISTORY_BRIDGE_STATUSES`,
  `S7ConsumeFailureReasonCode`; remove `credential_management` from
  `preview_body_class`; move `BLOCKING_UNAVAILABLE_REASONS` here.
- **D2:** add concrete surface-class mapping.
- **D4/D21/D25:** thread credential non-voice path; complete live surface
  enumeration and ActionEngine helpers.
- **D5/D16:** add `preview_body_ref`; rendered-to-bundle equality.
- **D7/D16:** fix ContextManifest hash domain; add dialog context policy stance.
- **D9/D10:** replace spent-nonce table with nonce-use lifecycle.
- **D11/D13:** widen laconic objection grounding; split blackhole rows; marker-only
  D23 authority becomes operational.
- **D17/D18:** prevent blackhole row from rendering as Maez objection; use
  renderer-only unavailable helper.
- **D19:** authoritative D23 requires grounded semantic evidence; exactly-once
  bridge; closed bridge statuses; exact aggregation filter.
- **D21:** full store signatures; failure reason mapping; challenge expiry;
  work-item/source-surface binding; retire grant helper bypass.
- **D22/D23:** credential trace/rollback lifecycle; trace vocabulary alignment.
- **D24:** expand no-hand-assembly list and add tests above.

## 15. Open Choices For v7 Author

1. **Operational row history:** no request-history row for operational S7.3
   voice blocks vs `outcome="blocked"`. Lane lean: no history row; trace-only.
2. **Credential path shape:** separate non-voice credential request vs
   credential `GuardedWorkItem`. Lane lean: separate non-voice credential path.
3. **ActionEngine `append_to_file`:** direct write adapter vs constrained
   `run_shell` consumer id. Lane lean: direct write adapter for append; reviewed
   exclusion or fail-closed for generic shell.
4. **Self-mod dialog context:** add policy-gated `dialog_context_ref` vs block
   self-mod dialog terminal execution until future policy. Lane lean: add slot
   and keep live use blocked until policy reviewed.
5. **Blackhole false branch protective reason:** `None` vs a named
   `reader_unavailable_no_captured_response`. Lane lean: `None`.

## Plain English

v6 closed the big design gaps. v7 is the last wiring fold: stop marker-only rows
from becoming long-term refusal evidence, make blackhole-reader blocks unable
to masquerade as "Maez objected," thread credential-management through its
non-voice path consistently, and enumerate the remaining real mutation doors.

The slice is not asking for a new architecture. It is asking for the last few
places where prose says "the system verifies this" to name the exact field,
row, helper, or mapping table that makes that true.

*Read-only; produced by Codex on 2026-05-20, absorbing `reviews/spec-fresh-reader-gate-v6.md` (8f88c1a) and `reviews/spec-codex-panel-v6.md` (26323db).*
