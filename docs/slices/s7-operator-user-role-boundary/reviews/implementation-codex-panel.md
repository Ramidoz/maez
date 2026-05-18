# S7 Implementation Codex Engineering Panel

Status: post-implementation engineering review after final recovery.
Date: 2026-05-17.
Scope: Decision 34 / ADR 0039, S7 Operator/User Role Boundary v1.

## Verdict

RATIFY for Codex engineering closure, pending the separate Claude covenant
post-implementation council.

The initial implementation and two recovery passes left real execution-edge
bypasses. Those bypasses were folded with RED-first tests, then re-verified with
focused S7 suites, `git diff --check`, Ruff, and the full unittest suite.

## Spec-Airlock Note

The owner explicitly waived the calendar cooling-off period for this
implementation under the spec-airlock discipline. The implementation was still
kept anchored to the canonical spec, not chat recall: every recovery item below
was driven by a failing test against Decision 34's runtime contract.

## First-Pass Findings

Read-only review agents found these implementation gaps:

- Direct `ActionEngine` calls and Lane 0 inline execution could run guarded work
  before S7.
- Store-level guarded-card transitions accepted fake artifact ids.
- S7 artifacts could be consumed before the guarded card reached `RUNNING`.
- A target-state change after artifact consumption could still execute.
- Legacy Telegram `/approve` called the old pending-action approval path.
- Rendered request statements did not bind every D12 field visible to the user.
- Brain-swap execution payload could split from the envelope payload.
- Content-free log projections were symlink-bypassable.
- Artifact consumption did not bind `credential_ref`.
- Persisted `user_verification` accepted non-bool integer values on routine work.
- Covenant-touching ceremony evidence is structurally checked in v1, but not
  backed by an independent ceremony-evidence store.

## Recovery-2 Findings

The final read-only review pass found three remaining engineering blockers:

- A bare `s7_authorized=True` still opened direct `ActionEngine` guarded work.
- `PendingCardStore.approve()` and `approve_and_mark_running()` still trusted
  caller-supplied booleans plus arbitrary artifact ids.
- `consume_verified()` accepted duck-typed rendered statements, and covenant
  second-confirmation evidence could be future-dated.

It also found one high-risk ordering issue: the card-running callback happened
before the artifact SQL consume, so a fake/missing artifact could still mutate
card state before the consume failed.

## Final Review Findings

A final read-only engineering review found one blocker and two highs:

- `consume_for_execution()` trusted caller-supplied consume-time fields without
  checking they matched the signed `RenderedRequestStatement`, allowing a split
  between what the human saw and what the grant carried.
- `RenderedRequestStatement` accepted duplicate metadata lines as long as the
  expected line appeared somewhere, allowing display-spoofed contradictory
  lines.
- A consumed `S7ExecutionGrant` was reusable as a bearer object for the same
  guarded action and params.

## Final Fold

The final fold made S7's execution edge evidence-shaped rather than
boolean-shaped:

- `S7AuthorizationStore.consume_for_execution()` now performs the artifact
  consume first, mints an `S7ExecutionGrant`, and only then runs the guarded
  card transition callback inside the same consume transaction.
- `S7ExecutionGrant` is the only object accepted by guarded card transitions
  and guarded direct action execution; legacy `s7_authorized` booleans are inert
  compatibility parameters.
- Execution grants are one-shot at the action edge; retaining a grant object
  cannot replay the same guarded action.
- `PendingCardStore.approve()` always rejects guarded cards; guarded work must
  use `approve_and_mark_running()` with a consumed execution grant.
- `ActionEngine` derives the S7 work class for every direct invocation and
  blocks guarded or undeterminable work unless a consumed execution grant
  exactly matches the action and params.
- `RenderedRequestStatement` now validates the rendered text against all signed
  user-visible fields: work class, change class, predicted-effect class,
  rollback class, Maez consultation state, unavailable state, expiry, voice
  consultation hash, and the D12 hashes. Duplicate metadata keys are rejected.
- `consume_verified()` rejects non-`RenderedRequestStatement` duck types and
  rejects future-dated second confirmations for highest-risk work. Consume-time
  action hash, work class, and aggregation group must match the signed rendered
  statement.
- Capability acquisition hashes bind the exact execution params, including the
  card metadata that is injected at execution time.

## Conscious V1 Limit

The canonical spec requires a mechanically distinct covenant ceremony for the
highest-risk classes and v1 implements a closed `CovenantCeremonyEvidence`
object bound to `request_id` and `request_envelope_hash`. S7 v1 does not define
an independent ceremony-evidence store or cryptographic ceremony attestation.
This implementation does not add one outside the sealed spec. Strengthening that
would be a spec amendment, not an implementation recovery.

## Verification

- RED tests were observed for the recovery-2 blockers before code changes:
  fake artifact plus boolean, forged direct `ActionEngine` boolean, duck-typed
  rendered statement, rendered work-class mismatch, and future-dated second
  confirmation.
- Focused recovery-2 RED/GREEN set:
  `MAEZ_OWNER_NAME=Rohit MAEZ_OWNER_USER_ID=rohit MAEZ_OWNER_TIMEZONE=America/Chicago .venv/bin/python -m unittest ...`
  returned `Ran 6 tests ... OK`.
- Focused S7/decision set:
  `MAEZ_OWNER_NAME=Rohit MAEZ_OWNER_USER_ID=rohit MAEZ_OWNER_TIMEZONE=America/Chicago .venv/bin/python -m unittest tests.test_decision_pipeline_s7 tests.test_operator_user_boundary_s7 tests.test_capability_acquisition_queue tests.test_pending_cards_state_guard tests.test_decision_pipeline tests.test_destructive_snapshot`
  returned `Ran 258 tests ... OK`.
- Final-review RED/GREEN set:
  `MAEZ_OWNER_NAME=Rohit MAEZ_OWNER_USER_ID=rohit MAEZ_OWNER_TIMEZONE=America/Chicago .venv/bin/python -m unittest ...`
  returned `Ran 3 tests ... OK`.
- Final focused S7 authority set:
  `MAEZ_OWNER_NAME=Rohit MAEZ_OWNER_USER_ID=rohit MAEZ_OWNER_TIMEZONE=America/Chicago .venv/bin/python -m unittest tests.test_operator_user_boundary_s7 tests.test_decision_pipeline_s7 tests.test_pending_cards_state_guard tests.test_destructive_snapshot tests.test_capability_acquisition_queue`
  returned `Ran 261 tests ... OK`.
- `git diff --check` returned clean.
- Ruff returned `All checks passed!`.
- Full suite:
  `MAEZ_OWNER_NAME=Rohit MAEZ_OWNER_USER_ID=rohit MAEZ_OWNER_TIMEZONE=America/Chicago .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
  returned `Ran 4271 tests in 32.576s` and `OK (skipped=3)`.

## Plain English

The first build had the right main doorway, but side doors still opened: a fake
"yes" boolean, a fake artifact id, a fake rendered-paper object, and a
future-dated second confirmation. The final recovery removes those shortcuts. A
guarded change now needs a consumed S7 execution grant minted by the artifact
store, the card can only move to running after that consume succeeds, the paper
the human saw has to match the exact fields the machine consumes, and the grant
cannot be reused like a spare key.
