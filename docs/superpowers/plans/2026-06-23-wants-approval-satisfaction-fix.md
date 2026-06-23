# Wants Approval Satisfaction Fix Plan

## Goal

Close the small but visible loop where approving a `want_terminal_proposal` card closes the card but never records the underlying want as satisfied, so Maez proposes the same "this want may be done" card again on later cycles.

This is plumbing only. `owner_confirmed` means the owner directly approved this specific terminal proposal; it is not an owner-reaction reward signal and must not become a general "approval means good" learner.

## Current Grounding

- `core/evolution/want_pursuit_bridge.py` creates cards with action `want_terminal_proposal`, `params["want_id"]`, `params["proposed"] == "satisfied"`, `source_for(want_id)`, and `want_id_from_source(...)`.
- `core/evolution/wants.py` already supports `event_type="satisfied"` with `basis="owner_confirmed"`, and rejects the reserved `self_observed_resolution` basis. For `owner_confirmed`, it requires an `external_object_ref`.
- Cockpit approval flows through `skills/web_interface.py` -> daemon `/internal/approve_card/<request_id>` -> `TelegramVoice._get_pipeline()` -> `DecisionPipeline._on_approve(...)`.
- `DecisionPipeline._on_approve(...)` currently approves the card, runs will-I, then executes the card action through `ActionEngine`. `want_terminal_proposal` is not an action engine command, so it has no satisfaction path.
- `AuditLog.record_outcome(...)` accepts free-form outcome labels. Known labels are grouped specially; unknown labels show as "other", so this fix can use an honest label instead of pretending an action ran.

## Scope

In:
- Specific approval hook for `want_terminal_proposal` only.
- Record the target want as satisfied with `basis="owner_confirmed"`.
- Mark the proposal card done after the satisfaction event records.
- Thread the daemon `wants` store into the existing decision pipeline.
- Tests for approve, deny, wrong-action, wrong-basis regression, and no recurrence.

Out:
- Any generic "approved card satisfies wants" behavior.
- Any model-inferred satisfaction.
- Any owner-reaction/engagement reward.
- Any changes to the nervous-system/time/self-card slices.
- Any restart/merge/live breath.

## Task 0 — Trace And STOP Gate

1. Re-read the live approval path:
   - `skills/web_interface.py` `/api/v1/cards/<id>/approve`.
   - daemon `/internal/approve_card/<request_id>`.
   - `skills/telegram_voice.py::_get_pipeline`.
   - `core/decision/decision_pipeline.py::_on_approve`.
2. Re-read the want lifecycle contract:
   - `core/evolution/wants.py` satisfied evidence validation.
   - `active_wants()`.
   - `history(...)`.
3. Re-read the terminal proposal contract:
   - `TERMINAL_PROPOSAL_ACTION`.
   - proposal card params.
   - open-proposal exclusion.
4. Confirm there is no existing `record_event(... event_type="satisfied" ...)` caller in the approval path.
5. Confirm the audit outcome can be an honest free-form label.
6. Write `docs/proofs/2026-06-23-wants-approval-satisfaction-task0.md` with the exact seam and any STOP findings.

STOP if:
- The cockpit/Telegram approval path does not share `DecisionPipeline._on_approve`.
- `want_id` is not reliably present on terminal proposal cards.
- The pipeline cannot receive the daemon `wants` store without broad construction churn.
- The satisfied evidence contract requires data unavailable from the approved card.

## Task 1 — Bridge Helper, TDD First

Test file: `tests/test_want_pursuit_bridge.py`.

Add RED tests for a pure helper, likely `record_terminal_approval_satisfaction(...)`:

1. Given an active want and an approved-style `want_terminal_proposal` card with `params["want_id"]` and `params["proposed"] == "satisfied"`, the helper records one `satisfied` event.
2. The recorded evidence has:
   - `basis == "owner_confirmed"`.
   - `source` naming the decision-pipeline approval path.
   - a non-empty `summary`.
   - `external_object_ref == "pending_card:<request_id>"`.
   - no `self_observed_resolution`.
3. `active_wants()` no longer returns the want.
4. Wrong action returns `None` and writes nothing.
5. Terminal card without `proposed == "satisfied"` returns `None` and writes nothing.
6. Already-satisfied or missing want returns `None` and writes nothing.

Then implement the helper in `core/evolution/want_pursuit_bridge.py`.

Implementation constraints:
- Read the current want statement via `wants_store.current_state(want_id)`.
- Preserve that exact statement when recording `EVENT_SATISFIED`.
- Keep evidence content-light; do not store the proposal conclusion text unless an existing validator forces it.
- Let lifecycle validation reject malformed satisfaction rather than bypassing it.

## Task 2 — DecisionPipeline Approval Hook, TDD First

Test file: a new focused file, likely `tests/test_wants_approval_satisfaction_pipeline.py`, or the existing `tests/test_decision_pipeline.py` if its helpers fit cleanly.

Add RED tests:

1. Approving a `want_terminal_proposal` card with a real `Wants` store:
   - calls the helper;
   - records `owner_confirmed`;
   - marks the card `done`;
   - returns `PipelineStatus.EXECUTED` with `execution_success=True`;
   - does not call `ActionEngine._execute_action`;
   - records an audit outcome such as `want_satisfied_owner_confirmed`.
2. A subsequent bridge selection sees no active want and therefore does not re-propose the same terminal proposal.
3. Approving any other card action does not satisfy the want and continues through the existing action engine path.
4. Denying a `want_terminal_proposal` card leaves the want active and records no satisfaction event.
5. If a terminal proposal approval has no usable wants store, it fails visibly and does not execute the unknown action. This prevents a silent false-success path.

Then implement:

1. Add `wants: Any = None` to `DecisionPipeline`.
2. In `_on_approve(...)`, after the card is owner-approved and expired-state is checked, but before will-I/action-engine execution, intercept only `TERMINAL_PROPOSAL_ACTION`.
3. Call the bridge helper with `self.wants` and the approved card.
4. If the helper records satisfaction:
   - `mark_done(...)` the card with a short owner-confirmed output;
   - `audit_log.record_outcome(..., outcome="want_satisfied_owner_confirmed", notes=...)`;
   - render resolution if a renderer exists;
   - return executed success.
5. If the helper cannot record satisfaction for a terminal proposal:
   - `mark_failed(...)` the card with a clear error;
   - `audit_log.record_outcome(..., outcome="approved_and_failed", notes=...)`;
   - do not execute the action engine.

Guardrails:
- Do not satisfy wants for any other card action.
- Do not call the helper from `_on_deny`.
- Do not introduce any owner-reaction reward path.

## Task 3 — Thread The Real Store

Test first:

1. Add a source-level or construction test proving `TelegramVoice._get_pipeline()` passes `wants=getattr(self.daemon, "wants", None)` to `DecisionPipeline`.
2. If there is an existing daemon/cockpit approval test harness, extend it to assert the pipeline receives the daemon wants store. If not, keep this as a minimal source/construction regression rather than building a large daemon harness.

Then update `skills/telegram_voice.py` so the decision pipeline used by cockpit approval has access to `daemon.wants`.

Do not touch the daemon route unless Task 0 proves it is necessary.

## Task 4 — Regression, Handoff, STOP

Run focused tests:

- `tests/test_want_pursuit_bridge.py`
- new/updated wants approval satisfaction tests
- `tests/test_decision_pipeline.py` if touched
- any Telegram pipeline construction test touched

Run broader protected tests around wants/cards:

- `tests/test_wants_lifecycle_d16.py`
- `tests/test_want_pursuit_bridge.py`
- `tests/test_decision_pipeline.py`
- `tests/test_web_owner_gating.py` only if web/cockpit approval code changed

Run:

- `ruff check` on changed source/test files.
- `git diff --check`.

Write `docs/handoffs/2026-06-23-wants-approval-satisfaction-fix-handoff.md` with:

- Task 0 seam proof.
- Exact files changed.
- Test commands and results.
- Covenant guard: `owner_confirmed` here is a direct answer to a specific terminal proposal, not owner-reaction reward.
- STOP at review gate.

Do not merge, restart, or live-witness in this branch.

## Predicted Effect

After merge and restart, when the owner approves a `want_terminal_proposal` card for a specific want, the card closes and the want records a `satisfied` event with `basis="owner_confirmed"`. The want disappears from `active_wants()`, so the want pursuit bridge no longer proposes the same terminal card on later cycles. Deny/ignore and unrelated card approvals do not satisfy wants.
