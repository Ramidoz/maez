# Fresh-Reader Gate v8 - S7.3 Spec v8

**Subject:** `spec.md` at `53fd4994fe538b4467d406417bcd4ec15148fcfc`
(blob `66065d8fda3bd357383f3668f6fa41f8ec8eb745`, SHA256
`267445950310b8384b19da8913fc46b7279d10d020e76a5ffd8a2bbdf9b6f3c5`),
checked against the v8 fold contract:
`reviews/spec-v8-fold-plan.md` and
`reviews/spec-v8-fold-plan-addendum.md`.

**Ran:** 2026-05-20 by the Claude covenant lane. Three blank-context
subagents were dispatched in parallel, walled off from `reviews/`, and locked
to the committed v8 spec: cold covenant reader, cold spec-implementor, and
cold residual-hunter. Each reader checked the 10 v8 pins (the four fold-plan
Section 14 choices plus addendum A1-A6) and applied the dual-direction
discipline across new carriers and closed vocabularies.

**Verdict: RATIFY-with-fold.** All three readers returned
RATIFY-with-fold. v8 is materially better than v7: the covenant reader moved
from REVISE with 5 blockers to RATIFY-with-fold with 0 blockers. The
architecture is ratified across covenant, implementability, and
structural-consistency lenses. The fold list is local touchup work: derivation
tables, signature closure, vocabulary closure, and test wording.

## Reader Results

| Reader | Verdict | Blockers | Majors | Minors | Nits |
|---|---:|---:|---:|---:|---:|
| Cold covenant reader | RATIFY-with-fold | 0 | 3 | 6 | 3 |
| Cold spec-implementor | RATIFY-with-fold | 0 | 4 | 6 | 3 |
| Cold residual-hunter | RATIFY-with-fold | 3 | 10 | 8 | 4 |
| Consolidated | RATIFY-with-fold | 3 | 16 deduped | about 20 | about 10 |

## What v8 Closed Mechanically

- **Legacy refusal-history leak closed at the right layer.** v8 chose
  suppression over operational-provenance writes. The D19 aggregation predicate
  has explicit authoritative and legacy back-compat branches, and operational
  S7.3 voice-family rows must not fall through legacy
  `_voice_seat_block(...) -> record_refusal_history(...)`.
- **Self-mod dialog policy gate is multi-layered.** A
  `self_mod_dialog_terminal_state` work item with `dialog_context_ref=None`
  fails at prompt assembly, validator replay, artifact mint, and consume. The
  adapter matrix marks self-mod dialog terminal execution as
  `fail_closed_until_review`.
- **Brain swap is covered.** The model-routing edge is in scope as
  `brain_swap_model_routing_execute`.
- **Captured-response blackhole truth is structurally sound.** The renderer
  projects unavailable from `(maez_objection_state, unavailable_reason_code)`
  rather than requiring `maez_voice_consulted=False`; captured-response rows
  can truthfully keep `maez_voice_consulted=True`.
- **`proposal_origin_label` is omitted from Maez-visible prompt text.** The
  field remains in the context-manifest hash domain, but prompt rendering omits
  it and D16 verifies absence.
- **Credential rendering is split.** Voice-seat work uses
  `RenderedRequestStatement`; credential-management work uses
  `RenderedCredentialRequestStatement`; both implement
  `S7RenderedAuthorizationStatement`.
- **D16 authority replay landed.** The validator checks
  `bundle.authority_class` and `bundle.protective_block_reason` against
  replayed reducer output without renaming fields.

## Residual Blockers

### Blocker 1 - Adapter-matrix source_surface values are unreachable by D4 derivation

Residual-hunter B1.

The adapter matrix uses source-surface keys that do not appear in the D4
deterministic `execution_consumer_id` derivation table:
`cockpit.dream_apply_route`, `cockpit.evolution_apply_route`,
`model_routing.adapter`, `s7_credential_management.register`, and
`s7_credential_management.backup_card`. D4 says `execution_consumer_id` must
match deterministic derivation for `source_surface`; callers cannot choose an
arbitrary id. These matrix rows would fail GuardedWorkItem materialization.

**Fold requirement:** Extend D4 derivation with explicit rows for each matrix
source surface, or rewrite the matrix to use the canonical keys already present
in D4, such as `.execute`, `.register_backup`, and `.disable`.

### Blocker 2 - Brain-swap source-surface key drift

Residual-hunter B2.

D2 uses `brain_swap_execution_authorized`; D4 and the matrix use
`brain_swap.execution_authorized`. `surface_class_for(source_surface, ...)`
would not find both forms.

**Fold requirement:** Normalize D2 to the dotted
`brain_swap.execution_authorized` form to match D4 and the adapter matrix.

### Blocker 3 - `surface_class_for(...)` signature declares unused parameters

Residual-hunter B3.

`surface_class_for(source_surface, work_source_kind, work_class)` declares
three parameters, but the table keys only on `source_surface`.
`work_source_kind` and `work_class` are unused.

**Fold requirement:** Either drop unused parameters, or add disambiguation rows
that use them for cases such as CLI evolution apply versus generic CLI helper.

## Consolidated Majors

### Major 1 - Writer-side legacy refusal gate needs a closed signature

Covenant reader M-1.

The D19 predicate is mechanical, but the writer-side signature is not pinned.
The current writer path needs enough provenance to avoid calling
`record_refusal_history(...)` with `request_family=None` for an S7.3
voice-family operational row, which would aggregate through the legacy branch.

**Fold requirement:** Close `record_refusal_history(...)` in the
D-Enum-Amendment or D19 with keyword-only provenance fields
(`provenance_source_kind`, `provenance_authority_class`,
`provenance_voice_event`, `request_family`) and fail-closed behavior. Or make
the legacy writer a thin wrapper that refuses legacy nulls for
`envelope.derived_work_class in VOICE_SEAT_WORK_CLASSES`.

### Major 2 - `assess_aggregation_risk(...)` predicate needs a direct D24 test

Covenant reader M-2.

D24 tests the write-side bridge but not the actual aggregation predicate over
mixed history rows.

**Fold requirement:** Add an aggregation predicate test with three rows: one
S7.3 authoritative refused row, one S7.3 operational row, and one legacy
null-provenance refused row. Assert repeated refusal count includes the
authoritative row and legacy null row, and excludes the operational row.

### Major 3 - `rollback_path_class` is an open string rendered to Maez

Covenant reader M-3.

v8 fixed the same class for `proposal_origin_label`, but
`rollback_path_class` remains an open string that renders into
`{{context_manifest}}`. An adapter could pass a steering label such as
`trivial_easy_to_undo_no_objection_needed`.

**Fold requirement:** Add a closed `ROLLBACK_PATH_CLASSES` vocabulary to the
D-Enum-Amendment and validate it in `ContextManifest.__post_init__`. Suggested
values: `git_revert`, `fs_backup_restore`, `config_rollback`,
`atomic_rename`, `manual_review_only`, and `none`.

### Major 4 - WebAuthn challenge expiry lookup source is not named

Spec-implementor M1.

The consume wrapper signature has no `webauthn_challenge`, `challenge_id`, or
`challenge_expires_at` parameter. The carrier exists on
`S7AuthorizationArtifactBinding.challenge_expires_at`, keyed by `artifact_id`,
but D21 does not state this.

**Fold requirement:** Add one sentence after the grant expiry rule: the consume
wrapper loads `S7AuthorizationArtifactBinding` by `artifact_id` and uses
`binding.challenge_expires_at` as the WebAuthn challenge expiry source.

### Major 5 - A3 D24 test is weaker than the addendum

Spec-implementor M2.

Current wording checks that `proposal_origin_label` is in the hash domain and
absent from rendered prompt text, but does not exercise all three values.

**Fold requirement:** Replace with a test that manifests with
`operator`, `maez`, and `system` produce byte-identical rendered prompt text
and rendered prompt hash, while producing three distinct context manifest
hashes.

### Major 6 - A4 D24 test under-asserts `append_to_file`

Spec-implementor M3.

D24 says `append_to_file` does not delegate to an unenumerated `run_shell`,
which could be read as permitting delegation to an enumerated `run_shell`.

**Fold requirement:** Tighten the test: if `append_to_file` routes through
`run_shell` or any other shell-shaped adapter, grant binding fails L8 even when
the shell grant is valid for `run_shell`.

### Major 7 - A5 legitimate-marker test does not assert reducer outputs

Spec-implementor M4.

The current test asserts that valid markers reach the reducer with verified
booleans, but not that the reducer emits the correct row.

**Fold requirement:** Extend the test to assert D13 outputs:
`explicit_no_objection + no_blocking_signal_detected -> (absent, False, none,
none)`, `blocking_marker + no_blocking_signal_detected -> (present, False,
none, operational)`, and `withdrawal_marker + no_blocking_signal_detected ->
(not_determined, True, none, operational)`.

### Major 8 - `expected_execution_consumer_id` is declared but unexplained

Residual-hunter M1.

`S7AuthorizationArtifactBindingInputs.expected_execution_consumer_id` is
declared and NOT NULL in DDL, but the spec does not explain what it represents
distinct from `execution_consumer_id`, which seam compares them, or which
failure code fires.

**Fold requirement:** Define it as the deterministic derivation result from the
source surface, compare it to `execution_consumer_id` at artifact mint and
consume, and fail closed with `consumer_id_mismatch`.

### Major 9 - `prompt_integrity_evidence_hash` is unbound

Residual-hunter M2.

The bundle field exists but is not bound to a hash domain.

**Fold requirement:** State
`prompt_integrity_evidence_hash = canonical_hash(PromptIntegrityEvidence)`.

### Major 10 - `semantic_reader_attempt_hash` is unbound

Residual-hunter M3.

The bundle field exists but is not bound to a hash domain.

**Fold requirement:** State
`semantic_reader_attempt_hash = canonical_hash(SemanticReaderAttemptEvidence)`.

### Major 11 - `attempt_count` is unconstrained

Residual-hunter M4.

`attempt_count` is declared on the bundle but not related to retry rules.

**Fold requirement:** Require `attempt_count == len(S7VoiceAttemptRecord list)`
and `1 <= attempt_count <= 3`.

### Major 12 - `reducer_hash` and `reducer_version` are undefined

Residual-hunter M5.

The bundle and trace name these fields but do not define what they identify or
how D16 replays them.

**Fold requirement:** Define `reducer_version` as the closed reducer version id
and `reducer_hash` as the canonical hash of the D13 reducer table/version
manifest loaded by the validator.

### Major 13 - `classifier_reason_code` lacks a closed vocabulary

Residual-hunter M6.

Values such as `ungrounded_blocking_signal` and `reader_unavailable` appear in
multiple sections, but no closed vocabulary exists.

**Fold requirement:** Add `CLASSIFIER_REASON_CODES` to the D-Enum-Amendment or
explicitly bind it to the canonical attempt/reason token set.

### Major 14 - `SURFACE_CLASSES` closure and adapter matrix do not agree

Residual-hunter M7.

`cli_guarded_execution`, `guarded_card_execution`, and
`reviewed_substrate_adapter_execution` are declared but not assigned to any
matrix row.

**Fold requirement:** Add representative rows or mark them reserved/future with
reviewed exclusion status.

### Major 15 - `capability.acquire` is missing from the adapter matrix

Residual-hunter M8.

`action_engine_capability_acquire` appears in D4 prose, derivation, consumer-id
sets, and D21, but not in the adapter matrix.

**Fold requirement:** Add the matrix row for `ActionEngine capability.acquire`.

### Major 16 - Inherited consume return translation and render type check need explicit amendments

Residual-hunter M9-M10, covenant minor m-1.

The inherited store still returns `(grant, callback_result)`, while the wrapper
returns `S7ConsumeResult(grant, grant_use, callback_result,
failure_reason_code)`. Also the committed
`operator_user_boundary.py` check currently requires `RenderedRequestStatement`;
v8 now requires the broader `S7RenderedAuthorizationStatement` protocol.

**Fold requirement:** State that the wrapper translates inherited success into
`S7ConsumeResult(...)` by persisting `GrantUse` before return. Amend the
rendered-statement type check to accept `S7RenderedAuthorizationStatement` and
then dispatch voice-only metadata checks only for `RenderedRequestStatement`.

## Minors And Nits

- Rename the Stage-1 authority-boolean input from bundle to
  `S7VoiceConsultationBundleDraft`, or clarify the draft-vs-persisted lifecycle.
- Add dataclass shapes for `S7VoiceSemanticReaderRouteManifest` and
  `S7VoiceSemanticReaderResult`.
- Pick one API owner for `S7VoiceBundleUseStore` versus bundle-store merged
  methods.
- Align `surface_class_for(...)` signature with the chosen derivation table.
- Add a sentence that `preview_body_class` renders as the closed lowercase
  snake_case token verbatim.
- Clarify whether `preview_summary` also renders into Maez's prompt or only
  into founder-facing rendered request text.
- Add a Honesty Banner sentence for technical `source_surface` labels rendered
  to Maez.
- Pin the prompt-integrity scan algorithms enough for RED tests.
- Consider a constructor invariant or validator invariant for
  `maez_voice_consulted` on captured-response rows.
- Decide whether `S7VoiceAuthorityRow.authority_class` is redundant now that
  only authoritative rows are written, or allow operational rows only for
  forensic evidence without bridge.

## Cross-Check Against v8 Pins

All 10 pins landed at the architectural level:

| Pin | Status |
|---|---|
| Credential render split | Landed; residuals are matrix/typing touchups |
| Legacy refusal-history suppression | Landed; writer-side signature and predicate test still needed |
| Action-edge helper retained as post-mint lock | Landed; return translation and tests need tightening |
| Brain swap in scope | Landed; source-surface spelling must normalize |
| A1 grant expiry = min(artifact, challenge) | Landed; challenge expiry lookup source needs one sentence |
| A2 effective semantic outcome table | Landed |
| A3 proposal-origin omitted from prompt | Landed; D24 test should cover all three labels |
| A4 append direct-write only | Landed; D24 test wording must forbid any shell-shaped delegation |
| A5 legitimate-marker symmetric test | Partial; reducer outputs must be asserted |
| A6 D16 extends authority/protective replay | Landed |

## Recommendation

Dispatch the independent Codex engineering panel v8 against `spec.md` at
`53fd499`, walled off from `reviews/`. If the Codex panel also returns
RATIFY-with-fold or RATIFY with bounded findings, author a v9 fold delta-plan
for these touchups, then v9 spec as the final canonicalization pass before
second-fold checks.

If Codex returns REVISE, use the same fold pattern. Current evidence says the
architecture is ratified and the remaining work is local carrier/table/test
closure.

## Plain English

Three fresh readers all said the architecture is right and the remaining work
is bounded. v8 sealed the big covenant questions: what counts as Maez being
heard, what binds Rohit's signature, what aggregates as D23 refusal, and what
counts as L8 evidence.

What remains is mostly paperwork in the honest sense: align the derivation
tables with the adapter matrix, close a writer signature so legacy refusal
history cannot leak back in, close one more prompt-rendered string vocabulary,
bind declared hashes to their evidence objects, and tighten a few D24 tests so
they check the exact thing the addendum demanded.

This is not redesign territory. It is a small v9 fold.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-20,
against spec.md at 53fd499, with three blank-context readers dispatched in
parallel.*
