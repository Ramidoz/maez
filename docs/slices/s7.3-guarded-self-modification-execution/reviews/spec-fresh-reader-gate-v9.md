# Fresh-Reader Gate v9 - S7.3 Spec v9

**Subject:** `spec.md` at `5e6491e62ec8b2b152da0c27de8e2786a4436cf3`
(blob `18ded69c3b2a72813657a82005b6bd25df7102db`, SHA256
`e603159eaa0f14b28ca93c2b8885725d9516287f3cec179b6593d498b8ce5d7f`),
checked against the v9 fold contract:
`reviews/spec-v9-fold-plan.md` and
`reviews/spec-v9-fold-plan-addendum.md`.

**Ran:** 2026-05-20 by the Claude covenant lane. Three blank-context
subagents were dispatched in parallel, walled off from `reviews/`, and locked
to the committed v9 spec: cold covenant reader, cold spec-implementor, and
cold residual-hunter. Each reader checked the 28 v9 pins (the 16 fold-plan
sections plus addendum A1-A12) and applied dual-direction discipline across the
new closed vocabularies and carriers.

**Verdict: REVISE.** The spec-implementor and residual-hunter returned
RATIFY-with-fold. The covenant reader returned REVISE on one narrow
writer-side refusal-history cluster. Per the ladder, the strictest covenant
lane verdict drives the direction.

This is the cleanest S7.3 gate so far: zero blockers across all three readers.
v9 is not blocked architecturally. The remaining fold is local carrier and
manifest closure, not redesign.

## Reader Results

| Reader | Verdict | Blockers | Majors | Minors | Nits |
|---|---:|---:|---:|---:|---:|
| Cold spec-implementor | RATIFY-with-fold | 0 | 0 | 2 | 2 |
| Cold covenant reader | REVISE | 0 | 3 clustered | 3 | 3 |
| Cold residual-hunter | RATIFY-with-fold | 0 | 3 | 8 | 4 |
| Consolidated | REVISE | 0 | 6 distinct / 4 clusters | about 13 | about 9 |

## What v9 Closed Cleanly

- v8 unresolved WebAuthn challenge expiry source is now
  `S7AuthorizationArtifactBinding.challenge_expires_at`.
- Addendum D24 tests landed as exact assertions, not paraphrases:
  `proposal_origin_label` byte-identical prompt plus distinct hash;
  `append_to_file` through any shell-shaped adapter fails L8; all three valid
  Maez-emitted markers reach the reducer and produce exact D13 outputs.
- A1-A12 addendum items landed: inherited consume translation,
  `is_s7_rendered_authorization_statement(...)`, Stage-1 bundle draft rename,
  semantic-reader manifest/result dataclasses, separate bundle-use store,
  preview-body-class canonicalization, prompt-integrity scans, constructor
  consulted-state invariant, operational forensic authority-row option, and
  reducer version/hash bindings.
- Min-cap expiry lattice is mechanically pinned at D9 mint, D16 pre-mint, D21
  consume, D24 tests, and Expiry Lifecycle.
- Rollback plan replay is a mint-eligibility predicate: D16 loads
  `RollbackPlanEvidence`, recomputes the plan hash, validates path class,
  target refs, and `blocks_execution_if_missing=True`.
- `S7VoiceAuthorityRow.authority_class` is honored bidirectionally: only
  grounded authoritative rows bridge; operational rows are trace-only.
- Captured-response blackhole rows are mechanically distinguishable from
  no-response unavailable rows through persisted `captured_response_nonempty`.
- `S7SurfaceManifest` is the single derivation source for surface class and
  execution consumer id across D2/D4/D21/D22.
- Atomicity is implementable end to end: single SQLite file, table-prefix
  namespace, `BEGIN IMMEDIATE`, injected connection, callback hook, and
  permissions.

## Cluster Alpha - Writer Guard For `record_refusal_history(...)`

**Source:** covenant reader M-1/M-2/M-3 plus residual-hunter m5.

This is the covenant-load-bearing cluster that drives REVISE.

### Alpha 1 - Closed-enum mismatch on `request_family`

`S7RequestHistoryRecord.request_family` admits:

```text
"s7_3_voice" | "s7_credential_management" | None
```

`record_refusal_history(...)` admits:

```text
"s7_3_voice" | "legacy_s7" | None
```

The record schema admits `s7_credential_management`; the writer signature does
not. The writer signature admits `legacy_s7`; the record schema does not. Both
carriers therefore have unreachable declared values.

**Fold requirement:** Align both to:

```text
"s7_3_voice" | "s7_credential_management" | None
```

Remove `legacy_s7`; the `None` arm already means inherited legacy.

### Alpha 2 - `request_family=None` is permissive by default

v9's writer mechanically rejects only the named S7.3 voice-family arm with
non-authoritative provenance. The `request_family=None` arm accepts
null-provenance refused rows by default, and the aggregation predicate counts
those rows.

That means the suppression policy still depends on every S7.3-era caller
remembering to pass `request_family="s7_3_voice"`. If a future call site knows
about an S7.3 voice-family path but forgets the kwarg, the writer silently
treats the row as inherited legacy and D23 aggregation counts it. This leaks
the same fake long-use refusal-evidence threat named in the Honesty Banner.

**Fold requirement:** Make `request_family` derived from the record or
envelope, not caller-supplied. Preferred shape: writer derives voice-family
status from `record.derived_work_class in VOICE_SEAT_WORK_CLASSES`; if true,
the strict provenance pair is required regardless of caller kwarg. Legacy
null-provenance rows are accepted only when the record is proven outside S7.3
voice-family work.

### Alpha 3 - Orphan closed-vocabulary tokens

These tokens are declared but lack a complete writer/predicate/test chain:

- `provenance_source_kind="legacy_s7_voice_block"` appears once, but the
  aggregation predicate does not handle it and no test writes or reads it.
- `request_family="s7_credential_management"` appears on the record schema but
  not the writer guard.
- `request_family="legacy_s7"` appears on the writer guard but not the record
  schema.

Closed sets are load-bearing only when each reachable value has a writer, a
predicate, and a D24 test.

**Fold requirement:** Delete orphan tokens or name their writer, predicate, and
D24 test.

## Cluster Beta - Surface Manifest Completeness

**Source:** residual-hunter M1/M2.

### Beta 1 - `action_engine.capability.acquire` missing from printed matrix

`capability.acquire` is named as guarded in five places:

- `S7_EXECUTION_CONSUMER_IDS`
- `S7_ACTION_ENGINE_CONSUMER_IDS`
- D4 prose
- D4 deterministic derivation
- D21 consumers

But the printed adapter matrix has no row for it. Committed
`core/actions/action_engine.py` includes `_do_capability_acquire`, a real
substrate-mutating method.

**Fold requirement:** Add a matrix row for `action_engine.capability.acquire`
or mark it reviewedly excluded everywhere.

### Beta 2 - "Matrix is complete" contradicts code-discovery acceptance

D4 says the `S7SurfaceManifest` contains the complete D2/D4/D21/D22/D25 route
set. The acceptance checklist says code discovery over
`core/actions/action_engine.py` is load-bearing and every method must have a
manifest row or reviewed exclusion.

Both can be true only if the printed matrix is faithful to code discovery.
Beta 1 proves it is not. The residual reader also found committed methods such
as `_do_modify_firewall`, `_do_system_reboot`, and
`_do_restart_critical_service` with no matrix row or reviewed exclusion.

**Fold requirement:** Either add every missing row/exclusion now, or soften the
printed matrix claim: the persisted/generated `S7SurfaceManifest` plus
code-discovery acceptance is normative, while the printed matrix is a reviewed
seed that must be mechanically compared against code before L8.

## Cluster Gamma - Orphan Failure And Provenance Codes

**Source:** residual-hunter M3/m1 plus covenant M-3.

### Gamma 1 - `expired_request_envelope` has no carrier

`expired_request_envelope` appears in the closed failure-code set and D21
mapping, but no `WorkRequestEnvelope.expires_at` field exists and v9 does not
amend the envelope. The Expiry Lifecycle names bundle, work item, artifact, and
WebAuthn challenge, but not request envelope.

**Fold requirement:** Either drop `expired_request_envelope` or add a real
`request_envelope.expires_at` carrier and D16/D21/D24 semantics. If the intent
was `S7CredentialGuardedRequest.expires_at`, rename the failure code to match
that carrier.

### Gamma 2 - `invalid_authority_class_replay` lacks a D16 source status

The failure code exists, but D16 currently returns generic
`invalid_reducer_replay` for authority-class mismatch. The D21-to-D16
translation is implicit.

**Fold requirement:** Add a D16 status for authority-class replay mismatch, or
map `invalid_reducer_replay` deterministically to the D21 failure code in the
wrapper.

### Gamma 3 - `legacy_s7_voice_block` is orphaned

`legacy_s7_voice_block` appears as a provenance-source kind but has no
producer, aggregation predicate branch, or D24 test.

**Fold requirement:** Delete it or define its complete semantics.

## Cluster Delta - Amended Signatures Must Be Explicit

**Source:** residual-hunter m2/m4/m5 plus spec-implementor M2.

The implementation-facing path is now close, but several amended signatures are
still prose-shaped:

- `consume_verified(...)` amended signature is implicit.
- `record_refusal_history(...)` and `_voice_seat_block(...)` amendments are
  prose-only, overlapping Cluster Alpha.
- The concrete wrapper services
  `execute_guarded_dream_apply(...)`,
  `execute_guarded_evolution_apply(...)`,
  `execute_guarded_workshop_apply(...)`,
  `execute_guarded_action_engine_mutation(...)`, and
  `execute_guarded_credential_mutation(...)` are ellipsis-only.
- Failure-code partition needs one explicit clause: wrapper-side checks assign
  reason codes for binding lookup, expiry lattice, consumer id,
  prompt-integrity replay, authority-class replay, reservation token, missing
  artifact/credential binding, missing GrantUse, and rendered protocol
  mismatch; inherited residual returns are used only after wrapper-side checks
  pass.

**Fold requirement:** State the amended signatures and reason-code ownership
explicitly in D21/D19.

## Single-Lane Secondary Findings

### Spec-implementor minors

- `S7VoiceConsultationBundleDraft` field shape is undefined. Add an explicit
  subset rule: draft equals the immutable bundle carrier minus the write-time
  authority booleans, effective reader outcome, reducer output, reducer hash,
  source hash, and final persisted fields.
- Inherited 2-tuple failure-branch discrimination is underdetermined without
  the wrapper-side versus inherited-residual partition described in Cluster
  Delta.
- `RenderedRequestStatement` gains `precondition_hash` for the first time on
  the inherited carrier; the acceptance checklist should call this out.

### Covenant minors

- Source-surface framing caveat is prose-only. Unlike
  `proposal_origin_label`, S7.3 v9 does not mechanically omit it. If this is
  intentionally deferred, name the future prompt-review slice or add a D24
  prompt-bias test.
- `ROLLBACK_PATH_CLASSES` admits `manual_review_only` and `none`, but D16/D24
  do not state which S7.3 v1 self-remaking surfaces may legitimately carry
  `none`. Presumed lane lean: self-remaking surfaces may not use `none`.
- Wrapper exclusivity needs a named D24 test beyond "method fails closed
  without consumed grant."

### Residual-hunter minors and nits

- `S7CredentialGuardedTrace` needs an enumerated field shape, like the voice
  and execution traces.
- `bundle.semantic_reader_attempt_hash` is terminal/singular while
  `S7VoiceAttemptRecord.semantic_reader_attempt_hash` is per-attempt; v9 should
  name the distinction.
- v9 should acknowledge the deliberate helper split/reversal:
  v8 requested splitting `voice_consultation_satisfies_request(...)`; v9 keeps
  it strict and adds a renderer-only helper.
- `S7VoiceAuthorityRow.authority_class` admits `none`, but row existence
  implies non-none. Add a `__post_init__` invariant or remove `none` from the
  row field's allowed values.
- `PROJECTION_REASON_CODES` and `PRODUCER_RESULT_REASON_CODES` should appear in
  the acceptance checklist's closed-enum list.
- `PROTECTIVE_BLOCK_REASONS` is documented but not declared as a closed
  vocabulary.
- `S7VoiceAuthorityRow` binds `surface_class` but not
  `surface_manifest_hash`; traces bind both.
- D24 needs an explicit concurrency test for
  `put_artifact_with_bundle_reservation(...)`.

## Significance

This is the cleanest gate in the S7.3 ladder:

```text
v7 covenant gate: 5 blockers, 4 majors, REVISE
v8 covenant gate: 0 blockers, 3 majors, RATIFY-with-fold
v9 covenant gate: 0 blockers, 3 clustered majors, REVISE
```

For the first time, all three lanes reported zero blockers. The engineering
lenses both ratified with fold; the covenant lane caught one narrow structural
carrier cluster in v9 Section 5's writer-side refusal-history guard.

v10 should be a narrow fold, not a redesign:

1. Close writer guard mechanically by deriving request family and removing
   orphan tokens.
2. Fix surface-manifest completeness by adding missing matrix rows/exclusions
   or making code-discovery the normative completeness check.
3. Drop or anchor orphan failure/provenance codes.
4. Write explicit amended signatures for the inherited seams and wrapper
   services.
5. Absorb secondary cleanup items above.

## Plain English

Three fresh readers looked at v9. Two said it is ready enough to begin
RED-first coding. One said the spec still leaves a narrow but important side
door in the refusal-history writer: the writer rejects bad S7.3 voice-family
rows only if the caller labels them correctly. If a caller forgets that label,
the row looks like legacy history and still aggregates.

That is the right kind of late finding: small, local, and load-bearing. v10
does not need a new architecture. It needs the writer to derive the family
itself, a few missing manifest rows, orphan token cleanup, and explicit
signatures. The S7.3 shape is now stable enough that the remaining work is
mostly making the last doors close by construction.

*Read-only; semantic consolidation written by Codex on 2026-05-20 from
Claude covenant-lane in-chat v9 reader reports. ASCII normalization was applied
for repository style; this file is not a byte transcript of hidden subagent
outputs.*
