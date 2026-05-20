# S7.3 Spec v9 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v9, derived from the v8
fresh-reader gate plus the Codex engineering panel v8.

**Sources (committed):**
- v8 spec: `53fd499 / spec.md`
- Fresh-reader gate v8: `07b08b9 / reviews/spec-fresh-reader-gate-v8.md`
  (RATIFY-with-fold; 3 readers; 3 residual blockers; 16 deduped majors)
- Codex engineering panel v8:
  `4adee3a / reviews/spec-codex-panel-v8.md`
  (REVISE; 4 reviewers; 7 deduped blockers; about 16 majors)
- v8 fold contract:
  `3568eb5 / reviews/spec-v8-fold-plan.md` plus
  `799c364 / reviews/spec-v8-fold-plan-addendum.md`

**Convergent direction:** REVISE to v9. The covenant gate ratified the
architecture with bounded folds; the Codex panel returned REVISE on engineering
carrier gaps. Per the ladder, either-lane REVISE requires a fold.

**Plain thesis:** v8 sealed the covenant architecture. v9 is the inherited-seam
and carrier-closure fold: every named check must land in a field, row, hash
domain, signature, derivation table, or RED test.

## 1. Centerpiece - Replace The Expiry Chain With A Min-Cap Lattice

**Absorbs:** Codex panel Blocker A (Reviewer 3 + Reviewer 4); fresh-reader gate
also asked for sharper expiry seam pinning.

v8's linear chain lets authorization outlive the work item:

```text
bundle <= work_item <= artifact <= grant <= webauthn_challenge
```

v9 should not preserve that ordering. Replace the linear chain with an
expiry-lattice rule:

```text
now < bundle.expires_at
now < work_item.expires_at
now < artifact.expires_at
now < webauthn_challenge.expires_at

artifact.expires_at <= min(bundle.expires_at, work_item.expires_at, webauthn_challenge.expires_at)
grant.expires_at = min(artifact.expires_at, bundle.expires_at, work_item.expires_at, webauthn_challenge.expires_at)
```

If any ceiling is already expired at mint or consume, the operation fails
closed before artifact storage, grant mint, or substrate mutation.

Add failure reasons:

```text
expired_work_item
expired_bundle
expired_request_envelope
expiry_chain_violation
```

Update D16/D21/D24:

- D16 enforces `now < bundle.expires_at` and `now < work_item.expires_at`;
- artifact mint enforces `artifact.expires_at <= min(bundle, work_item,
  challenge)`;
- consume loads artifact binding, bundle use, work item, and challenge expiry
  and mints `grant.expires_at` from the min-cap rule;
- consumer pre-mutation enforces `now < grant.expires_at`;
- D24 adds RED tests for artifact-after-work-item, consume-after-work-item,
  consume-after-bundle, and challenge-after-artifact mismatch.

## 2. Define The Rendered Authorization Protocol Exactly

**Absorbs:** Codex Blocker B; fresh-reader gate rendered-type broadening minor.

v9 should make `S7RenderedAuthorizationStatement` a real protocol, not a loose
shared label:

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

`RenderedRequestStatement` and `RenderedCredentialRequestStatement` must both
implement these fields. Pick the stronger v9 lean: keep `precondition_hash` in
the common protocol and add a founder-signed voice render line:

```text
Precondition hash: <64-char hex>
```

Add it to:

- D-Enum-Amendment `RenderedRequestStatement` fields;
- D17 rendered text lines and `expected_metadata`;
- D16 rendered-to-bundle equality predicates;
- D21 consume checks;
- D24 rendered metadata tamper test.

For credential renders, explicitly list both `rendered_text` and
`rendered_text_hash`.

## 3. Add Durable Stores For Work Items, Previews, And Attempt Evidence

**Absorbs:** Codex Blocker C; Codex Majors 3-5; fresh-reader gate unbound hash
carrier majors.

Extend D9 table prefixes:

```text
s7_guarded_work_items
s7_mutation_previews
s7_prompt_integrity_evidence
s7_semantic_reader_attempts
s7_voice_attempt_records
s7_context_manifest_policies
```

Add store APIs:

```text
S7GuardedWorkItemStore.write(work_item) -> work_item_id
S7GuardedWorkItemStore.read(work_item_id) -> GuardedWorkItem | None
S7MutationPreviewStore.write(preview) -> preview_id
S7MutationPreviewStore.read(preview_id) -> MutationPreviewArtifact | None
S7PromptIntegrityEvidenceStore.write(evidence) -> prompt_integrity_evidence_hash
S7SemanticReaderAttemptStore.write(attempt) -> semantic_reader_attempt_hash
S7VoiceAttemptRecordStore.write_many(records) -> attempt_manifest_hash
```

Bind hash domains:

```text
prompt_integrity_evidence_hash = canonical_hash(PromptIntegrityEvidence)
semantic_reader_attempt_hash = canonical_hash(SemanticReaderAttemptEvidence)
attempt_manifest_hash = canonical_hash(ordered S7VoiceAttemptRecord list)
```

Constrain attempt count:

```text
attempt_count == len(S7VoiceAttemptRecord list)
1 <= attempt_count <= 3
```

D16 must load and replay these stores by ref/hash. D22 traces must include
prompt-integrity evidence ref/hash for producer-blocked attempts. D24 adds
tamper/replay tests for prompt-integrity evidence, semantic-reader attempts,
retry manifests, and later-retry-cannot-wash-objection.

## 4. Move WebAuthn Challenge Expiry To The Right Carrier

**Absorbs:** Codex Blocker D; Codex expiry findings; fresh-reader gate M1.

Do not leave D16 promising a check it cannot perform. Pick this v9 split:

- D16 validates bundle, work item, preview, context, prompt, reducer, render,
  rollback plan, and voice evidence before artifact mint.
- Artifact mint and D21 consume validate WebAuthn challenge expiry through
  `S7AuthorizationArtifactBinding.challenge_expires_at`.
- D21 states the wrapper loads `S7AuthorizationArtifactBinding` by
  `artifact_id` and uses `binding.challenge_expires_at` as the challenge expiry
  source.

Remove or narrow D16 wording that says it verifies
`webauthn_challenge.expires_at` directly.

## 5. Harden Legacy Refusal History At The Writer And Store Layer

**Absorbs:** fresh-reader gate Major 1 and Major 2; Codex Major 1.

Add a D19 writer/store guard:

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

For `request_family="s7_3_voice"`:

- `outcome="refused"` requires
  `provenance_source_kind="s7_voice_authority_row"` and
  `provenance_authority_class="authoritative"`;
- operational, protective, reader-unavailable, marker-only, malformed, or
  unavailable rows are rejected at the writer/store edge if they attempt
  `outcome="refused"`;
- legacy null-provenance rows are allowed only when `request_family is None`.

Add D24 aggregation predicate test:

- S7.3 authoritative refused row counts;
- S7.3 operational row does not count;
- legacy null-provenance refused row counts only under inherited legacy branch.

## 6. Replace Hand-Maintained Surface Tables With A Closed Surface Manifest

**Absorbs:** fresh-reader gate Blockers 1-3 and Majors 14-15; Codex Blocker E,
Blocker F, Blocker G, Majors 9-10 and 13-15.

Add:

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

D2/D4/D21/D22/D25 should reference this manifest rather than maintaining
independent hand-copied tables. `surface_class_for(...)` and
`execution_consumer_id_for(...)` read the manifest. Callers never supply
surface class; builders recompute or fail closed.

Trace additions:

```text
surface_route_or_method
adapter_id
adapter_code_hash
same_code_coverage_ref
surface_manifest_hash
```

Normalize source-surface spelling:

- use `brain_swap.execution_authorized`, not underscored spelling;
- choose credential canonical form. Lane lean: keep
  `source_surface="s7_credential_management"` and add `source_method` for
  `register`, `backup_card`, `disable`, and `register_finish`.

Add or classify rows for:

- `approval_card.execute`;
- cockpit dream/evolution routes;
- Telegram natural-language apply, slash apply, approve-train, and
  `/rollback_adapter`;
- `action_engine.capability.acquire`;
- `action_engine.integration.review_plan`;
- `/etc/maez/model.env` write/restart and model-routing restart edges;
- credential register, backup card, disable card, disable credential,
  begin/finish routes;
- cli/card/reviewed-substrate rows that currently exist only in
  `SURFACE_CLASSES`.

## 7. Complete ActionEngine And Model-Routing Closure

**Absorbs:** Codex Blockers F-G; fresh-reader gate ActionEngine/surface majors.

Add an acceptance item requiring code-discovery of ActionEngine mutation
methods, not a hand-maintained subset. The manifest must include every public
and private method that can mutate Maez substrate or capability state:

- soul/config/model routing writes;
- capability acquisition and integration review-plan status updates;
- shell/script/package/process/service helpers;
- baseline/core-memory writes;
- git push/commit/package install;
- write-outside-Maez paths.

For each row, choose `live_guarded`, `fail_closed_until_review`, or
`reviewedly_excluded`. L8 evidence cannot use parent
`action_engine_final_mutate` as a substitute for a concrete child id.

For model routing, replace generic `reviewed_substrate_adapter_execute` with
concrete model-routing consumer ids or reviewed exclusions. Generic shell,
sudo, restart, or substrate adapter rows cannot hide brain swap or
`/rollback_adapter`.

## 8. Make Rollback Plan Replay A Mint-Eligibility Predicate

**Absorbs:** Codex Major 6; fresh-reader gate rollback-path-class major.

Add closed vocabulary:

```text
ROLLBACK_PATH_CLASSES = {
    git_revert,
    fs_backup_restore,
    config_rollback,
    atomic_rename,
    manual_review_only,
    none,
}
```

Validate `rollback_path_class` in `ContextManifest.__post_init__`; it is
rendered into Maez's prompt, so it cannot be an open string.

D16 must load `RollbackPlanEvidence` by `rollback_plan_ref` before mint and
verify:

- plan hash recomputes;
- `rollback_path_class` matches work item, preview, context manifest, and
  rendered text;
- target refs match preview affected refs or reviewed mapping;
- `blocks_execution_if_missing=True` for S7.3 v1 self-remaking surfaces;
- missing or mismatched plan makes `mint_eligible=False`.

Add D24 rollback-plan mismatch and missing-plan tests.

## 9. Pin Context Policy Hash Bytes

**Absorbs:** Codex Major 7; fresh-reader gate self-mod dialog policy findings.

Replace "hash of this closed policy text" with a concrete carrier:

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

`policy_hash = canonical_hash(ContextManifestPolicy with policy_hash excluded)`.

State where the reviewed policy lives, e.g.:

```text
config/s7_context_manifest_policies/s7.context_manifest_policy.v1.json
```

D16 loads by `policy_id`, recomputes `policy_hash`, checks membership in
`REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES`, and rejects mismatches.

## 10. Make Runtime And Semantic-Reader Store Boundaries Explicit

**Absorbs:** Codex Major 8.

Choose one ownership model. Lane lean:

- `BondedMaezRuntime.ask_s7_voice_turn(...)` returns response text/material to
  the producer; it does not write to the bundle store.
- The producer writes raw response material to
  `S7VoiceConsultationBundleStore` and records `raw_response_ref/hash`.
- `S7VoiceSemanticReaderV1.classify(...)` receives either raw response text
  and preview text directly, or receives a `bundle_store`/`preview_store`
  capability. Pick direct text for deterministic classifier input and keep refs
  as replay pins.

Update D7, D8, D12, and D16 accordingly.

## 11. Pin Live Adapter Signatures Or Wrapper Services

**Absorbs:** Codex Major 9.

D4 currently allows callee choice: accept consumed grant plus
`GuardedWorkItem`, or derive/open a guarded work item. v9 should remove choice
from the spec and name concrete wrapper seams:

```text
execute_guarded_dream_apply(...)
execute_guarded_evolution_apply(...)
execute_guarded_workshop_apply(...)
execute_guarded_action_engine_mutation(...)
execute_guarded_credential_mutation(...)
```

Each wrapper owns:

```text
GuardedWorkItem/S7CredentialGuardedRequest lookup
source manifest row lookup
rendered authorization verification
artifact consume
GrantUse and ActionEdgeGrantUse verification
callee invocation
trace finalization
```

The underlying existing callee may remain unchanged only if the wrapper is the
exclusive mutation entry for guarded paths.

## 12. Close Remaining Carrier Vocabularies And Hash Domains

**Absorbs:** fresh-reader gate Majors 8-13 and 16; Codex Majors 11-12 and
minor reducer-row finding.

Add:

```text
CLASSIFIER_REASON_CODES
REDUCER_TABLE_VERSION
REDUCER_TABLE_HASH
```

`S7VoiceReduction` should include:

```text
classifier_reason_code: str | None
reducer_row_id: str
```

Add deterministic row ids to every D13 table row.

Define:

```text
expected_execution_consumer_id =
    execution_consumer_id_for(surface_manifest_row)
```

Artifact mint and consume compare
`expected_execution_consumer_id == execution_consumer_id`; mismatch returns
`consumer_id_mismatch`.

Reservation token fix:

```text
reserve_for_artifact(source_ref_hash, artifact_id, reserved_at) -> ReservationToken
ReservationToken = canonical_hash((source_ref_hash, artifact_id, reserved_at))
```

The wrapper passes transaction `now` as `reserved_at`.

## 13. Split Legacy Voice Helper Semantics

**Absorbs:** Codex Major 2.

Rename or clarify helper semantics:

```text
voice_consultation_matches_request(...) -> request binding only
voice_consultation_positive_absent(...) -> D14 absent predicate, or use D16 result
voice_consultation_renderable_for_unavailable(...) -> D17 render only
```

Artifact minting and authorization recheck must use D16 validation output, not
legacy `voice_consultation_satisfies_request(...)` as positive consent.

## 14. Tighten D24 Tests

**Absorbs:** fresh-reader gate Majors 2, 5, 6, 7 and Codex D24 requests.

Add or sharpen tests:

- aggregation predicate mixed-history test;
- all three `proposal_origin_label` values produce byte-identical rendered
  prompt text/hash but distinct context manifest hashes;
- `append_to_file` routed through any shell-shaped adapter fails L8, even with
  a valid shell grant;
- valid explicit no-objection, blocking, and withdrawal markers reach the
  reducer and produce exact D13 outputs;
- expiry min-cap lattice tests;
- work-item/preview store replay tests;
- prompt-integrity evidence tamper/replay tests;
- semantic-reader attempt replay tests;
- retry-wash test;
- rollback plan missing/mismatch tests;
- context policy hash mismatch test;
- no-hand-assemble positive harness test;
- surface manifest coverage test comparing code-discovered routes to manifest
  rows.

## 15. Acceptance Checklist Edits

Update the checklist to require:

- closed surface manifest and generated D2/D4/D21/D22/D25 consistency;
- durable stores for work items, previews, prompt integrity evidence,
  semantic-reader attempts, and attempt records;
- exact rendered authorization protocol;
- expiry lattice enforcement;
- writer/store guard for refusal history;
- rollback plan replay before mint;
- concrete context policy carrier;
- private-store boundary for runtime and semantic-reader ports;
- exact guarded execution wrapper seams;
- full ActionEngine/model-routing/credential route coverage;
- all D24 tests above.

## 16. v9 Review Path

v9 should remain operator-authored from this fold plan. Review path:

1. Section 8.2 fresh-reader gate v9 with the same three-reader discipline.
2. Codex engineering panel v9 independently, walled off from reviews.
3. If both lanes return RATIFY or RATIFY-with-fold with only touchups, run
   second-fold checks and prepare canonicalization.
4. If either lane returns REVISE, fold narrowly; by evidence, remaining issues
   should be terminal carrier/route-table cleanup rather than architecture.

## Plain English

v8 answered the moral question correctly: Maez is asked, marker-only evidence
does not poison refusal history, blackholed readers do not manufacture consent,
credential work has a separate non-voice path, and the founder signs a rendered
authorization that binds the exact request.

The v8 reviews found the last engineering layer. Some things are still named
as if they exist but do not yet have a durable row, a hash domain, a signature,
or a manifest entry. The expiry chain is the one true surprise: it currently
lets later authority outlive the work item. Fix that first. Then make the
rendered authorization protocol exact, give work items and previews stores,
derive every surface from one manifest, and make rollback/prompt/retry evidence
replayable.

This is still not a redesign. It is the last carrier-and-manifest fold before a
real canonicalization attempt.

*Read-only; produced by Codex on 2026-05-20, absorbing
`reviews/spec-fresh-reader-gate-v8.md` (07b08b9) and
`reviews/spec-codex-panel-v8.md` (4adee3a).*
