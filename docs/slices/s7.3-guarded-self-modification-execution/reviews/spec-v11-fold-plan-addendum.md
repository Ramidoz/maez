# S7.3 Spec v11 Fold Delta-Plan Addendum

**Subject:** addendum to `reviews/spec-v11-fold-plan.md`, covering absorption
residuals found during covenant-lane faithfulness review of the v11 fold plan.

**Extends:** `reviews/spec-v11-fold-plan.md` at `02ec7bb`.

**Why this exists:** the v11 fold plan absorbs every material finding from the
v10 fresh-reader gate and the Codex engineering panel v10. Faithfulness review
found zero material gaps, plus three minor pins and five nit-class wayfinding
items. This addendum records those pins so v11 spec authoring does not rely on
session memory.

## A1 - `S7CredentialGuardedTrace.artifact_binding_id`

**Source:** spec-implementor minor from the v10 fresh-reader gate.

**Extends:** v11 fold plan Sections 2, 12, and 14.

`S7CredentialGuardedTrace.artifact_binding_id` is redundant if
`S7AuthorizationArtifactBinding` is keyed by `artifact_id`.

v11 should choose one shape:

- lane lean: remove `artifact_binding_id` and use `artifact_id` as the binding
  key everywhere; or
- keep `artifact_binding_id` only if v11 defines a distinct binding primary key
  and the lookup from `artifact_id -> artifact_binding_id`.

D24 should assert the chosen key shape for credential traces.

## A2 - Deprecated `consume_verified(...)` Missing Optional Context

**Source:** spec-implementor minor from the v10 fresh-reader gate.

**Extends:** v11 fold plan Sections 1 and 9.

The deprecated `consume_verified(...)` compatibility wrapper takes
`execution_authorization`, `expected_execution_consumer_id`, and `now`, but
does not carry `superseded_request_ids` or `covenant_ceremony_evidence`.

v11 should pin:

```text
For the deprecated consume_verified(...) path, superseded_request_ids=()
and covenant_ceremony_evidence=None. Any non-empty supersession or ceremony
evidence requires the new S7GuardedExecutionInvocation path.
```

This prevents the compatibility path from silently inventing ceremony context.

## A3 - Reader-Unavailable Reason-Code Distinction

**Source:** spec-implementor minor from the v10 fresh-reader gate.

**Extends:** v11 fold plan Section 15.

v10 uses `classifier_reason_code="reader_unavailable"` in the effective-outcome
view and `unavailable_reason_code="semantic_reader_unavailable"` in the reducer
view. A cold implementer could collapse the two.

Add a one-sentence distinction:

```text
classifier_reason_code names the classifier/reader seam that failed;
unavailable_reason_code names the covenant projection surfaced to the reducer
and renderer. "reader_unavailable" may map to
"semantic_reader_unavailable", but the two fields are not aliases.
```

## A4 - Source-Surface Framing Caveat Deferral

**Source:** covenant nit from the v10 fresh-reader gate.

**Extends:** v11 fold plan Section 15.

The Honesty Banner keeps `source_surface` as a real prompt-framing residual.
v11 should name the deferral path explicitly:

```text
Source-surface prompt framing is accepted as a v11 Honesty Banner residual.
It is not claimed solved by S7.3. A future prompt-framing review may move
source_surface out of Maez-visible prompt text or empirically justify keeping
it.
```

## A5 - Plain-English Close Version Scope

**Source:** residual-hunter nit from the v10 fresh-reader gate.

**Extends:** v11 fold plan Plain English / authorship note.

When authoring v11, the Plain English close should name v10's own folds, not
only inherited v9 review findings. This is wayfinding, not a semantic change.

## A6 - Manifest Audit-Only Field Consistency

**Source:** residual-hunter nit from the v10 fresh-reader gate.

**Extends:** v11 fold plan Sections 11 and 14.

If `manifest_id` is audit-only for `ContextManifest`, v11 should state whether
`S7SurfaceManifest.manifest_id` follows the same rule. Lane lean:

```text
S7SurfaceManifest.manifest_id and created_at are persisted for audit and
excluded from manifest_hash, matching ContextManifest.
```

## A7 - Spec Status Line Update

**Source:** spec-implementor nit from the v10 fresh-reader gate.

**Extends:** v11 spec authorship header.

Update the status line during v11 authoring so it does not describe v10 as the
current active fold. This is cosmetic but avoids review confusion.

## A8 - Prompt Template Missing-File Failure

**Source:** spec-implementor nit from the v10 fresh-reader gate.

**Extends:** v11 fold plan Section 15.

The semantic reader prompt template id-to-file mapping should specify the
missing-file behavior:

```text
If semantic_reader_prompt_template_id maps to a file that is absent or whose
hash does not match the reviewed template hash, the semantic reader attempt
fails closed with classifier_reason_code="classifier_error" before reducer
entry.
```

## Process

v11 spec should be authored from:

- `reviews/spec-v11-fold-plan.md`;
- this addendum.

No new architecture is introduced here. A1-A3 are minor carrier pins. A4-A8
are nit-class wayfinding and consistency pins.

*Addendum written by Codex on 2026-05-20 in response to covenant-lane
faithfulness review of `reviews/spec-v11-fold-plan.md`. ASCII normalization
applied for repository style.*
