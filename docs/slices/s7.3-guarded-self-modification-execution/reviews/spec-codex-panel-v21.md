# S7.3 Spec v21 Codex Engineering Panel

**Artifact reviewed:** `spec.md` at commit `3038e65bbe2f4d5452090ab4d4b376144a9c2141`

**Scope:** v21 fold from:

- `reviews/spec-v21-fold-plan.md` at `aa55fcb69c4b9cd35fdadae568ec808b4bfa2157`
- `reviews/spec-v21-fold-plan-addendum.md` at `a0b6214b24b04ff30b8c259e2361c6fb10fac0b1`

**Verdict:** RATIFY-with-fold

**Counts:** 0 Blockers / 1 Major / 0 Minors / 0 Nits

## Bottom Line

v21 fixes the cut-induced vocabulary regression. The whole-family restore is
correct: the execution-consumer, non-mintable, future-reviewed, action-engine,
and surface-class vocabularies are back in the right families, with the
credential/key-management surface still cut out. The central v20 break, where
the four primary self-modification routes were mislabeled and would fail closed,
is fixed.

v21 also closes the Codex v20 major: `S7GuardedStateStore(...)` now owns
`artifact_binding_store`, and the execution-invocation bundle loader/unpack seam
receives that dependency.

One engineering major remains. The six carrier shape blocks exist, but
`S7VoiceConsultationBundle` and `S7VoiceBundleUse` are still narrower than the
later validation text that reads from them. This is not a covenant reopen and not
a scope-cut problem. It is a carrier-shape completeness fold: expand the shape
blocks so every field read by bundle validation and bundle-use lookup is named
on the corresponding carrier.

## Reviewer Results

| Reviewer | Lens | Verdict | Counts |
|---|---|---:|---:|
| 1 | Closed vocabulary restore / pre-cut diff | RATIFY | 0 / 0 / 0 / 0 |
| 2 | Persistence store dependency / carrier shape | RATIFY-with-fold | 0 / 1 / 0 / 0 |
| 3 | Route matrix / fail-closed route sanity | RATIFY | 0 / 0 / 0 / 0 |
| 4 | D24 checklist / cut-integrity audit | RATIFY-with-fold | 0 / 1 / 0 / 0 |

The single major is shared by reviewers 2 and 4.

## Major Finding

### M1 - Bundle Carrier Shape Blocks Are Narrower Than Later Reads

**Severity:** Major

**Finding:** v21 adds the six requested carrier shape blocks, but the
`S7VoiceConsultationBundle` and `S7VoiceBundleUse` blocks do not yet expose every
load-bearing field later validation reads.

At `spec.md:1610`, `S7VoiceConsultationBundle` lists only:

```text
request_id
consultation_id
source_ref_hash
attempt_manifest_hash
reducer_version
reducer_hash
maez_voice_consultation_hash
expires_at
```

At `spec.md:1621`, `S7VoiceBundleUse` lists only:

```text
request_id
artifact_id
source_ref_hash
consultation_id
bundle_use_hash
used_at
```

Later, the validator reads fields not named in those shape blocks:

- `bundle.context_manifest_ref`
- `bundle.rendered_prompt_hash`
- `bundle.expected_consultation_nonce_hash`
- `bundle.prompt_integrity_evidence_hash`
- `semantic_reader_attempt_hash`
- `bundle.authority_class`
- `bundle.protective_block_reason`
- `bundle.mutation_preview_hash`
- `bundle.rollback_plan_ref`
- `bundle.precondition_hash`

The validator also requires the matching `S7VoiceBundleUse` row to be
`unreserved and unconsumed`, but the carrier block exposes no reservation or
consumption fields that can carry or verify that state.

This contradicts the v21 D24 rule at `spec.md:3624`: every field read by
artifact-binding replay, bundle validation, bundle-use lookup, or execution
bundle loading must appear in the six carrier shape blocks.

**Why this matters:** an implementer following the carrier block literally cannot
write the D24 completeness test without inventing fields, and cannot implement
bundle validation without reaching outside the declared carrier shape.

**Fold shape:** expand the carrier blocks, especially
`S7VoiceConsultationBundle` and `S7VoiceBundleUse`, until every later read has a
named field. If any field is intentionally indirect, the block must name the
ref/hash field and the loader seam that reconstructs it. The D24 carrier-shape
completeness test should remain and pass against the expanded blocks.

## Affirmations

### A1 - Vocabulary Family Restore Is Correct

The addendum required the whole closed-vocabulary family to be restored from the
pre-cut baseline, minus credential/key-management members. v21 lands that
restore.

Observed target counts:

```text
S7_EXECUTION_CONSUMER_IDS = 20
NON_MINTABLE_EXECUTION_CONSUMER_IDS = 1
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS = 22
S7_ACTION_ENGINE_CONSUMER_IDS = 13
SURFACE_CLASSES = 11
```

The three execution-id families are pairwise disjoint. `action_engine_final_mutate`
is present only in `NON_MINTABLE_EXECUTION_CONSUMER_IDS`. The dangerous future
routes (`action_engine_run_shell`, `action_engine_execute_script`,
`action_engine_run_script`, `action_engine_sudo_command`) are not mintable
execution-consumer ids.

### A2 - The Four Primary Self-Modification Routes Are Restored

The live route rows again emit the pre-cut core execution-consumer ids:

```text
dream_apply_proposal
dream_apply_section_edit_proposal
evolution_apply_candidate
workshop_apply_diff
```

The v20 orphan ids are absent:

```text
guarded_dream_apply
guarded_section_edit_apply
guarded_candidate_apply
guarded_workshop_apply
cli_helper_guarded_execution
```

`cockpit_guarded_execution` is back in the surface-class family only, not in the
execution-consumer family.

### A3 - Credential/Key-Management Cut Remains Clean

The v21 spec does not reintroduce the credential/key-management symbols that the
v20 cut intentionally lifted into the deferred seed document:

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

The signature-scope council item remains off the S7.3 v1 critical path because
backup credential registration is still deferred with the key-management slice.

### A4 - Codex v20 M1 Is Closed

`S7GuardedStateStore(...)` now owns:

```text
artifact_binding_store: S7AuthorizationArtifactBindingStore
```

`load_guarded_execution_invocation_bundle(...)` and
`unpack_guarded_execution_invocation(...)` receive the artifact-binding
dependency through the state-store path. The v20 major is closed.

### A5 - Preview Body Annotation Is Fixed

The D17 annotation now uses:

```text
preview_body_class: preview_body_class
```

It no longer references the undefined uppercase `PREVIEW_BODY_CLASSES` token.

### A6 - D24 Now Has The Right Net

D24 includes the reverse coverage and disjointness checks the v20 cut needed:

- pairwise disjointness across `S7_EXECUTION_CONSUMER_IDS`,
  `NON_MINTABLE_EXECUTION_CONSUMER_IDS`, and
  `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS`;
- exact cardinality checks for the restored sets;
- forward and reverse coverage for execution-consumer ids and surface classes;
- a closed-vocabulary name test.

This is the correct durable guard against a repeat of the v20 relabeling
regression.

## Recommended v22 Fold Scope

One item:

1. Expand the artifact/bundle carrier shape blocks so every later field read by
   bundle validation, bundle-use lookup, artifact-binding replay, or execution
   bundle loading is declared on a carrier or routed through a named loader seam.

The fold should not reopen the scope cut, covenant posture, route vocabulary, or
credential/key-management deferral.

## Plain English

v21 fixed the damage caused by the big cut. The labels are back where they
belong: the routes Maez actually uses are mintable again, the dangerous shell and
script routes are not mintable, and the key-management feature stayed parked for
later.

One bookkeeping problem remains. The spec now prints the shape of six important
objects, but two of those printed shapes are too short: later paragraphs read
fields that the printed object shape never listed. So an engineer would still
have to invent those missing fields while building. The next fold is small:
make the printed object shapes match what the validator already says it reads.
