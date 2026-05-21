# S7.3 Spec v21 Fold Delta-Plan - Restore Cut-Damaged Vocabularies

**Subject:** edits to `spec.md` for v21. v21 is a micro-mechanical restore fold
after the v20 scope cut. It does not reopen covenant architecture and it does
not bring credential/key-management back into S7.3 v1.

**Sources:**

- v20 spec: `ee580b7 / spec.md`
- Codex panel v20: `6f07d5b / reviews/spec-codex-panel-v20.md`
- Claude fresh-reader gate v20:
  `ec11071 / reviews/spec-fresh-reader-gate-v20.md`
- pre-cut baseline for vocabulary restore:
  `0c3215e / spec.md` (v19 spec immediately before the v20 lift+cut)

**Decision:** v20's big cut stands. In-band credential/key-management remains
deferred to `deferred/credential-management-seed.md`. v21 repairs only the
engineering regressions caused by non-surgical rewriting during the cut.

**Cardinal rule:** restore cut-damaged vocabulary blocks from the pre-cut
baseline and remove only credential-only members. Do not re-author these lists
from memory. Hand-retyping the lists is what caused v20's regressions.

## Must-Cover Checklist

| # | Item | Class | Source | v21 section |
|---|---|---|---|---|
| 1 | Restore `S7_EXECUTION_CONSUMER_IDS` core ids to matrix spellings | Blocker | Fresh-reader B1 | Section 1 |
| 2 | Restore `SURFACE_CLASSES` to the pre-cut credential-free values | Blocker | Fresh-reader B2 | Section 2 |
| 3 | Restore or repair `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS` | Major | Fresh-reader M1 | Section 3 |
| 4 | Add `artifact_binding_store` to `S7GuardedStateStore(...)` | Major | Codex M1 / Fresh-reader M2 | Section 4 |
| 5 | Pin binding/bundle-family carrier shape blocks | Minor | Fresh-reader m1 | Section 5 |
| 6 | Fix `PREVIEW_BODY_CLASSES` annotation | Minor | Fresh-reader m2 | Section 6 |
| 7 | Add reverse-direction vocabulary coverage to D24 + checklist | Nit | Fresh-reader n1 | Section 7 |
| 8 | Both-lane gate note | Process | Fold discipline | Section 8 |
| 9 | v21 acceptance checklist | Process | Fold discipline | Section 9 |

## 1. Restore `S7_EXECUTION_CONSUMER_IDS` Core Ids

### Problem

The v20 cut rewrote the four primary core ids into `guarded_*` forms that the
derivation table and adapter matrix never emit. This makes the mint gate
unsatisfiable for the main routes:

```text
execution_consumer_id must be in S7_EXECUTION_CONSUMER_IDS
AND
execution_consumer_id_for(source_surface, source_method) must match it
```

### v21 edit

Restore the four pre-cut spellings from `0c3215e`, while keeping credential-only
ids out:

```text
dream_apply_proposal
dream_apply_section_edit_proposal
evolution_apply_candidate
workshop_apply_diff
```

Replace these v20-only orphan spellings:

```text
guarded_dream_apply
guarded_section_edit_apply
guarded_candidate_apply
guarded_workshop_apply
```

Do not alter the already-matching non-credential ids unless a direct pre-cut
restore requires it.

### D24 tests

Add a route-manifest membership test:

```text
for every live_guarded manifest row:
    execution_consumer_id_for(row.source_surface, row.source_method)
        in S7_EXECUTION_CONSUMER_IDS
```

The test must explicitly cover `/apply_dream`, `/apply_edit`, evolution apply,
and workshop apply diff.

## 2. Restore `SURFACE_CLASSES`

### Problem

The v20 cut replaced the `SURFACE_CLASSES` closed vocabulary with the
`work_source_kind` family. The adapter matrix's `surface_class` column uses the
pre-cut `*_application` / `*_execution` family, so all matrix surface-class
values became orphaned.

### v21 edit

Restore `SURFACE_CLASSES` from `0c3215e`, dropping only
`credential_management_execution`:

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

Do not use the `work_source_kind` values (`dream_apply`, `section_edit_apply`,
etc.) as surface classes.

### D24 tests

Add a surface-class membership test:

```text
for every retained manifest row:
    row.surface_class in SURFACE_CLASSES
```

Add the reverse direction:

```text
for every value in SURFACE_CLASSES:
    at least one retained manifest row or reviewed coverage rule produces it
```

## 3. Restore Or Repair `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS`

### Problem

v20 left an enforcement rule that references
`REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS`, but cut away the set definition.
The rule is therefore unenforceable as written.

### v21 edit

Preferred edit: restore the pre-cut reserved-id definition from `0c3215e`,
minus any credential-only members. The restored set is not mintable:

```text
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS = {
    "self_mod_dialog_terminal_execute",
    "cli_helper_execute",
    "cockpit_helper_execute",
    "reviewed_substrate_adapter_execute",
    "action_engine_run_shell",
    "action_engine_execute_script",
    "action_engine_run_script",
    "action_engine_sudo_command",
    "action_engine_git_push",
    "action_engine_install_package",
    "action_engine_kill_process",
    "action_engine_restart_service",
    "action_engine_write_outside_maez",
    "action_engine_restart_critical_service",
    "action_engine_modify_firewall",
    "action_engine_system_reboot",
    "action_engine_free_disk_space",
    "action_engine_delete_temp_file",
    "action_engine_clean_temp_files",
    "action_engine_run_safe_command",
    "action_engine_install_package_t2",
    "telegram_rollback_adapter_execute",
}
```

If the v21 author instead removes the named reserved set, every reference to it
must be replaced with an equivalent explicit rule. Do not leave a dangling
symbol.

### D24 tests

Add:

```text
put_artifact_with_bundle_reservation(...) rejects REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS
consume_artifact_for_execution(...) rejects REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS
```

and a no-overlap assertion:

```text
S7_EXECUTION_CONSUMER_IDS
  INTERSECT NON_MINTABLE_EXECUTION_CONSUMER_IDS
  INTERSECT REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS
is empty pairwise
```

## 4. Add `artifact_binding_store` To `S7GuardedStateStore(...)`

### Problem

The retained execution bundle loader, unpack helper, and consume path all need
`S7AuthorizationArtifactBindingStore`, but the transaction-owning
`S7GuardedStateStore(...)` constructor does not own or expose it.

### v21 edit

Add this dependency to `S7GuardedStateStore(...)`:

```text
artifact_binding_store: S7AuthorizationArtifactBindingStore,
```

Keep the existing loader/helper signatures that already name
`artifact_binding_store`; this fold makes the constructor match the retained
load path.

### D24 tests

Add a retained store-dependency completeness test:

```text
for every store dependency named by load_guarded_execution_invocation_bundle(...)
or unpack_guarded_execution_invocation(...):
    S7GuardedStateStore(...) owns or explicitly receives that dependency
```

The test must specifically assert that `artifact_binding_store` is present.

## 5. Pin Binding/Bundle-Family Carrier Shape Blocks

### Problem

Six load-bearing carriers are referenced by field but lack consolidated shape
blocks:

- `S7AuthorizationArtifactBinding`
- `S7AuthorizationArtifactInputs`
- `S7AuthorizationArtifactBindingInputs`
- `S7VoiceConsultationBundleDraft`
- `S7VoiceBundleUse`
- `S7VoiceConsultationBundle`

A builder can infer them from scattered prose, but the canonicalization bar
should not require reconstructing covenant carriers from fragments.

### v21 edit

Add one consolidated "Artifact/Bundle Carrier Shapes" subsection near D9 or D21.
The section may state that fields are inherited from S7.1 where appropriate, but
must list every S7.3 load-bearing field referenced by this spec.

Minimum fields to include:

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
    reducer_version: str,
    reducer_hash: str,
    maez_voice_consultation_hash: str,
    expires_at: str,
)

S7VoiceBundleUse(
    request_id: str,
    artifact_id: str,
    source_ref_hash: str,
    consultation_id: str,
    bundle_use_hash: str,
    used_at: str,
)
```

If the v21 author finds an inherited field already required by S7.1 that is
load-bearing for S7.3 replay, add it explicitly rather than relying on "and
others".

### D24 tests

Add a carrier-shape completeness test:

```text
every field read by artifact binding replay, bundle validation, bundle-use
lookup, or execution bundle loading appears in one of the six carrier shape
blocks
```

## 6. Fix `PREVIEW_BODY_CLASSES` Annotation

### Problem

D17 annotates `preview_body_class: PREVIEW_BODY_CLASSES`, but the defined
vocabulary is lowercase `preview_body_class`. Uppercase appears exactly once and
has no definition.

### v21 edit

Use the defined name consistently. Preferred minimal edit:

```text
preview_body_class: preview_body_class,
```

Alternative acceptable edit: rename the vocabulary to `PREVIEW_BODY_CLASSES`
everywhere it is defined and referenced. Do not leave both names live.

### D24 tests

Add a closed-vocabulary name test:

```text
every type annotation that names a closed vocabulary names an actually defined
closed vocabulary
```

## 7. Add Reverse-Direction Vocabulary Coverage

### Problem

v20's checklist caught several producer tables but omitted reverse coverage for
`S7_EXECUTION_CONSUMER_IDS` and `SURFACE_CLASSES`. That omission is how orphaned
values survived author verification and two reader lanes.

### v21 edit

Add to D24 and Implementation Acceptance Checklist item 7:

```text
Every retained S7_EXECUTION_CONSUMER_IDS value is emitted by at least one
live_guarded manifest row, derivation row, or reviewed non-mintable rationale.

Every retained SURFACE_CLASSES value is emitted by at least one retained
manifest row or reviewed coverage rule.
```

Also require the forward direction:

```text
Every live_guarded manifest row's execution_consumer_id is in
S7_EXECUTION_CONSUMER_IDS, and every manifest row's surface_class is in
SURFACE_CLASSES.
```

### D24 tests

These become explicit RED tests. They are the guard that prevents a future
scope cut from silently rewriting closed vocabularies into orphan token
families.

## 8. Both-Lane Gate Note

v21 gets both lanes again:

- Claude Section 8.2 fresh-reader gate: confirm covenant remains clean and the
  pre-cut-diff step proves no retained vocabulary was accidentally rewritten.
- Codex engineering panel: confirm v20's only Codex major is closed, the two
  fresh-reader blockers are closed, and the restored vocabulary sets are
  implementable without aliases.

The Claude v20 gate explicitly established the improved scope-cut technique:
future scope-cut gates must diff retained closed vocabularies against the
pre-cut parent. v21 review should use that step.

## 9. v21 Acceptance Checklist

The v21 author runs these before committing:

```text
dream_apply_proposal
dream_apply_section_edit_proposal
evolution_apply_candidate
workshop_apply_diff
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
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS
artifact_binding_store: S7AuthorizationArtifactBindingStore
S7AuthorizationArtifactBinding(
S7AuthorizationArtifactInputs(
S7AuthorizationArtifactBindingInputs(
S7VoiceConsultationBundleDraft(
S7VoiceBundleUse(
S7VoiceConsultationBundle(
preview_body_class: preview_body_class
Every retained S7_EXECUTION_CONSUMER_IDS value is emitted
Every retained SURFACE_CLASSES value is emitted
```

And these must remain absent from live `spec.md`:

```text
S7CredentialGuardedRequest
S7GuardedCredentialInvocation
RenderedCredentialRequestStatement
S7CredentialRegistrationGrantBinding
execute_guarded_credential_mutation
CREDENTIAL_ACTIONS
CHALLENGE_PHASES
registration_ceremony_challenge
credential_management_execution
```

The deferred seed doc may still contain the parked credential symbols.

## Plain English

v20 cut the right feature but damaged a few labels while doing it. v21 is not a
new design round. It restores the labels from the version just before the cut,
removing only the credential-only entries. That makes the four core routes
mintable again, makes every surface class match the matrix, restores the
reserved-future set that a rule still references, wires the one missing
artifact-binding store dependency, and adds a test so this exact kind of
scope-cut regression cannot slip through again.

The covenant is still clean. The key-management feature stays parked. v21 is a
restore-from-parent fold, not an architecture fold.
