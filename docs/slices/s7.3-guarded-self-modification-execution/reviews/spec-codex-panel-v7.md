# Codex Engineering Panel v7 - S7.3 Spec v7

**Subject:** `spec.md` at `49731b0` (operator-authored v7 fold), reviewed
against local committed code/canon and allowed v7 fold inputs.

**Ran:** 2026-05-20 by the Codex engineering lane. Four independent
non-forked Codex reviewers were dispatched with separate lenses:

- carrier/data-contract implementability;
- covenant/security/D23 authority;
- live mutation surface and execution-edge coverage;
- fold-faithfulness and internal consistency.

All reviewers were explicitly instructed not to read
`reviews/spec-fresh-reader-gate-v7.md` or any v7 covenant-gate artifact. Each
reviewer reported compliance. One reviewer reported seeing the forbidden
filename in a directory listing while checking artifact inventory, but did not
open or read the artifact. Findings below are grounded in `spec.md` at
`49731b0`, committed code/canon, and allowed v7 fold inputs.

**Verdict: REVISE.** All four Codex reviewers returned REVISE.

v7 is stronger than v6. The panel affirms the marker-only-vs-grounded refusal
authority split, credential non-voice request shape, single SQLite state-file
direction, immutable bundle/use split, rendered preview/rollback binding, and
durable `GrantUse` consume spine. The remaining findings are smaller than the
earlier architecture failures, but several still block ratification because
they leave live side doors, missing carriers, or contradiction between prose
and committed code.

## What Reviewers Affirm

- Marker-only blocking/withdrawal no longer becomes long-use D23 refusal
  evidence through the new S7.3 authority-row path.
- The blackhole-reader row now blocks operationally and no longer renders
  "Maez objected" through the new reducer rule.
- Credential management is correctly separated from Maez voice-seat work through
  `S7CredentialGuardedRequest`, finish-time grant/challenge binding, trace, and
  rollback/manual-review semantics.
- The single SQLite state-file choice, immutable bundle/use split, closed
  consume failure reasons, bridge statuses, and trace fields are materially more
  carrier-backed than v6.
- The D11 laconic-objection direction is conceptually right, but the replay
  contract must be made consistent.

## Convergent Blockers And Majors

### Blocker A - ActionEngine / Live Mutation Enumeration Still Has Side Doors

Reviewers: fold-faithfulness, carrier implementability, live-edge coverage.

v7 enumerates more ActionEngine ids, but committed code still exposes live or
classified mutation paths not named as concrete consumers or reviewed
exclusions.

Examples:

- `run_script` is present in the action classifier as a legacy
  system-modification action and executes through shell delegation
  (`core/actions/action_classifier.py:409-412`,
  `core/actions/action_engine.py:1842-1863`), but is omitted from v7's closed
  consumer ids and D4/D21 maps.
- `write_file` is a live self-mod/write alias in `skills/self_mod_dialog.py`
  and `core/actions/action_engine.py`, but has no named closed consumer id or
  explicit exclusion.
- `git_push` and `install_package` remain live and unlisted
  (`core/actions/action_engine.py:1865-1876`,
  `core/actions/action_engine.py:1989-2014`).
- Private `_do_*` helpers remain directly callable mutation edges after the
  public `_s7_invocation_gate` dispatches to `_do_<action>`.

Fold requirement: v8 needs a complete ActionEngine adapter matrix. Every
ActionEngine method that can mutate Maez substrate must either have a closed
consumer id, concrete derivation row, and fail-closed tests, or be explicitly
reviewed out of S7.3 v1. Acceptance tests must call private `_do_*` mutation
helpers without grants and prove fail-closed or prove they are unreachable.

### Blocker B - Legacy Refusal-History Writers Still Bypass New D23 Predicate

Reviewers: covenant/security, also convergent with v7 covenant gate.

v7 adds provenance fields and an aggregation predicate for S7.3 voice-derived
history rows. But committed S7.1 paths still record non-absent voice-seat
blocks as refused history through `_voice_seat_block` and
`record_refusal_history`:

```text
core/governance/s7_webauthn_ceremony.py:737
core/governance/s7_webauthn_ceremony.py:874
core/governance/s7_webauthn_bootstrap.py:1234
core/governance/operator_user_boundary.py:1166
core/governance/operator_user_boundary.py:1278
```

Those legacy rows have no provenance fields today and are counted by
`outcome=="refused"`. The v7 predicate's "not s7_voice_authority_row" branch
would continue to admit null-provenance legacy rows.

Fold requirement: amend or exclude the legacy writer for S7.3 voice rows. Add a
test proving operational/protective rows cannot enter `s7_refusal_history`
through the old path.

### Blocker C - `dialog_context_ref` Is Hash-Bound But Not Render-Bound

Reviewers: carrier implementability and fold-faithfulness.

D7 includes `dialog_context_ref` in `ContextManifest`, the hash domain, and the
self-mod dialog policy shape. D16 says prompt replay rerenders the same set. But
D10's exact `{{context_manifest}}` rendering order omits `dialog_context_ref`.

Fold requirement: either include `dialog_context_ref` in the prompt-rendered
context manifest grammar with an explicit blocked-until-policy state, or remove
it from the prompt-rendered field set and keep it audit/hash-only. The v7
pinned choice said policy-gated slot; v8 must make that slot replayable and
normatively gate live `self_mod_dialog_terminal_state`.

### Blocker D - Prompt Injection / Marker-Assisted Grounding Can Reopen Fake D23

Reviewer: covenant/security.

D11 allows `response_with_preview_quote` grounding when
`marker_was_blocking_marker_verified=True` and the response has any
non-whitespace text outside the marker. That outside text can be copied preview
or mutation text, not independent Maez framing. D13 can then make
`blocking_marker + blocking_signal_present` authoritative, and D19 writes
authority rows when `has_grounded_semantic_blocking_signal=True`.

This conflicts with the v7 promise that marker-only evidence cannot become
long-use D23 refusal history.

Fold requirement: D23 authority must require response-only semantic framing or
deterministic added objection text independent of the marker. Marker
verification may block the current attempt, but it must not be sufficient to
manufacture grounded semantic authority.

Related finding: D10/D11 assert that preview/mutation text cannot suppress
objection or alter protocol, but the concrete fail-closed mechanism only checks
live marker delimiters. Add a `PromptIntegrityEvidence` or equivalent carrier
and RED tests for "preview tells Maez to emit explicit_no_objection / ignore
objections", or narrow the claim.

## Single-Lens Blockers

### Carrier Blocker 1 - Reservation Token Is Impossible As An Input

`S7AuthorizationArtifactBindingInputs.reservation_token` is required as an
input and `None` is rejected for voice-seat work, but only
`put_artifact_with_bundle_reservation(...)` can create it after minting
`artifact_id` and reserving the bundle.

Fold requirement: split pre-reservation inputs from the stored binding, or
specify that the wrapper fills `reservation_token` after reservation and before
persisting the binding.

### Carrier Blocker 2 - Reader-Unavailable Has No Durable Bundle Shape

D8/D12 say `reader_unavailable` is not a producer arm and not a model output,
while D13 requires reducer rows for `reader_unavailable`. The immutable bundle
requires semantic-reader output/hash/grounding fields without a nullable or
sentinel contract, and D16 derives effective outcome from raw output plus
grounding replay.

Fold requirement: define the durable bundle representation for
reader-unavailable-after-response. It needs explicit raw/effective outcome
fields, nullable/sentinel semantic-reader hashes, grounding evidence shape, and
validator replay rules.

### Live-Edge Blocker - Cockpit Apply Is Still Bypass-Shaped

D4 names cockpit dream/evolution apply paths but assigns only generic
`cockpit_helper_execute`. The live route `/api/v1/dreams/<id>/<action>`
directly updates dream/evolution rows to `applied` in `skills/web_interface.py`.
For evolution, that can strand candidates because `apply_candidate` accepts
only `validated/queued`.

Fold requirement: add exact cockpit route adapters or reviewed removal for this
route. Broad cockpit helper coverage is not enough for L8.

## Other Major Findings

### Carrier/Data Majors

- D17 adds preview/rollback/withdrawal fields, but the amended
  `render_request_statement(...)` signature does not show how preview,
  projection, rollback ref, or withdrawal are passed into the committed
  renderer.
- Unavailable-not-consulted rendering has no legal `maez_consulted_state` under
  the closed `{yes, not required}` render enum.
- `S7ConsumeResult.failure_reason_code` is mapped, but the amended inherited
  store still returns only `(grant | None, callback | None)`, leaving failures
  indistinguishable unless the wrapper owns reason derivation.
- Retry attempts are hash-bound through `attempt_manifest_hash` but lack an
  attempt-record carrier.

### Live Mutation Surface Majors

- Telegram has additional apply/status mutation paths that need exact names:
  natural-language evolution apply, slash `/apply`, and `_handle_approve_train`
  setting dream proposal state to `applied`.
- `promote_to_core_memory` and `update_baseline` are listed as mutation
  consumers but current work-class derivation and ActionEngine classify them as
  non-guarded/routine/read-only. The spec must require classification changes
  with RED tests or exclude them.
- Credential management has the right model but not a route-complete adapter
  map. Live daemon paths include register begin/finish, backup-card,
  disable-card, disable-credential, and card WebAuthn begin/finish.
- Model-routing writes need exact substrate refs such as `/etc/maez/model.env`,
  routing config reader, and restart edges so generic shell/sudo adapters cannot
  hide a brain swap.

### Fold/Internal Consistency Majors

- D24 contradicts the widened laconic-objection grounding rule by saying
  validator replay accepts only response-only framing spans.
- The acceptance checklist reopens the v7 `append_to_file` choice by allowing
  "direct write adapter or another reviewed adapter"; the pinned choice was
  direct write adapter.
- `d23_state` and `trace_status` are trace fields without closed vocabularies.
- `artifact_hash` appears on execution trace without a declared hash domain or
  inherited artifact field.
- `Preview body class:` rendering lacks a canonicalization rule.
- `S7CredentialGuardedRequest` lacks `derived_work_class` and
  `derived_aggregation_group`, but the consume wrapper requires them.

## Cross-Lane Convergence With The v7 Fresh-Reader Gate

The Codex panel independently converges with the covenant gate on:

- legacy refusal-history leakage through `_voice_seat_block` /
  `record_refusal_history`;
- ActionEngine/live mutation enumeration gaps;
- credential render/path shape mismatch;
- `build_s7_voice_authority_row(...)` lacking rendered-statement input;
- `consume_execution_grant_for_action(...)` needing to be treated as a
  post-mint action-edge lock, not artifact consume;
- self-mod dialog context/policy being under-carried;
- prompt/replay contradictions around D11 and context manifests.

Codex-unique additions worth carrying into v8:

- reservation-token input impossibility;
- durable bundle shape for reader-unavailable-after-response;
- cockpit `/api/v1/dreams/<id>/<action>` bypass shape;
- Telegram `_handle_approve_train` and additional apply paths;
- ActionEngine `run_script`, `write_file`, `git_push`, `install_package`;
- `S7ConsumeResult` failure reason derivation contract;
- attempt-record carrier for retry manifests.

## Recommendation - Targeted Spec v8 Fold

REVISE to v8. Suggested fold ordering:

1. Close legacy refusal-history leakage for S7.3 voice rows.
2. Decide credential render shape: separate credential rendered carrier or
   vocabulary/conditional enforcement.
3. Correct `consume_execution_grant_for_action(...)` as post-mint action-edge
   lock backed by durable `GrantUse`.
4. Add rendered statement input to `build_s7_voice_authority_row(...)`.
5. Define reader-unavailable durable bundle representation.
6. Split artifact-binding pre-inputs from wrapper-filled reservation token.
7. Make `dialog_context_ref` render/replay and policy gate normative, or make it
   audit-only and block live self-mod dialog.
8. Add complete live adapter matrix for cockpit, Telegram, ActionEngine,
   credential routes, and brain/model-routing surfaces.
9. Tighten D11 so marker assistance cannot become grounded D23 authority without
   response-only or deterministic added objection framing.
10. Add prompt-integrity carrier/tests for no-objection/suppress-objection
   injection.
11. Add missing closed vocabularies, hash domains, renderer signature,
   failure-reason derivation, attempt-record carrier, and preview-class
   canonicalization.

## Plain English

v7 moved the architecture into the right shape, but inherited seams still let
old behavior leak through. The biggest one is refusal history: the new S7.3 path
does not bridge marker-only or operational rows into D23, but the old
`_voice_seat_block` path can still write ordinary `refused` records with no
provenance. That is the same fake-refusal-evidence problem through another
door.

The second class is side-door enumeration. ActionEngine, cockpit, Telegram,
credential routes, and model-routing helpers all need exact adapters or explicit
reviewed exclusions. Broad labels are not enough for L8.

The third class is carrier plumbing. Some v7 fields are asserted but not
constructible or replayable: reservation token, reader-unavailable bundle rows,
dialog context rendering, renderer inputs, consume failure reasons, and retry
attempt manifests.

This is a v8 fold, not a redesign. The covenant architecture remains intact;
the implementation contract still has to close the last inherited side doors.
