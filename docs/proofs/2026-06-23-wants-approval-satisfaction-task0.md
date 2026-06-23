# Wants Approval Satisfaction Fix — Task 0 Proof

## Verdict

GO. The real owner approval path has one clean seam: `DecisionPipeline._on_approve(...)` receives the approved card for both cockpit and Telegram-style approvals. `want_terminal_proposal` cards carry the exact `want_id` and proposal marker needed to record a want lifecycle `satisfied` event. No existing production approval caller records that event today.

## Approval Path

- Web cockpit approval starts at `skills/web_interface.py:1820` and proxies to daemon `/internal/approve_card/<request_id>`.
- Daemon cockpit approval is `daemon/maez_daemon.py:11221`; it loads the real card and calls `pipe._on_approve(card, _CockpitCls(), card.user_id or "owner")` at `daemon/maez_daemon.py:11270`.
- `TelegramVoice._get_pipeline()` constructs the shared `DecisionPipeline` at `skills/telegram_voice.py:976`.
- `DecisionPipeline._on_approve(...)` is the shared approval execution seam at `core/decision/decision_pipeline.py:1683`.

## Terminal Proposal Shape

- `TERMINAL_PROPOSAL_ACTION = "want_terminal_proposal"` at `core/evolution/want_pursuit_bridge.py:15`.
- `maybe_propose_terminal(...)` creates cards with:
  - `action=TERMINAL_PROPOSAL_ACTION`.
  - `params["want_id"]`.
  - `params["proposed"] == "satisfied"`.
  - `params["conclusion"]`.
  - `params["wondering_id"]`.
- `_wants_with_open_proposal(...)` already excludes wants with open/deferred terminal proposal cards by reading `card.params["want_id"]` from `cards_store.list_open_by_action(TERMINAL_PROPOSAL_ACTION)`.

## Want Satisfaction Contract

- `EVENT_SATISFIED = "satisfied"` at `core/evolution/wants.py:71`.
- `SATISFACTION_BASES` includes `owner_confirmed` at `core/evolution/wants.py:136`.
- `RESERVED_SELF_OBSERVED_SATISFACTION_BASIS = "self_observed_resolution"` at `core/evolution/wants.py:142`.
- `_validate_satisfied_evidence(...)` rejects `self_observed_resolution`, requires an accepted basis, and requires `external_object_ref` for `owner_confirmed`.
- `record_event(...)` appends the lifecycle event at `core/evolution/wants.py:614`.
- `current_state(...)` and `active_wants(...)` are available readers at `core/evolution/wants.py:759` and `core/evolution/wants.py:799`.

## Existing Caller Check

Production grep found no existing approval-path caller that records `event_type="satisfied"` or `EVENT_SATISFIED` outside `core/evolution/wants.py`; current satisfied writes are tests/fixtures. The bug is therefore a missing bridge from approved terminal proposal card to the already-existing want lifecycle event.

## Audit Outcome

`AuditLog.record_outcome(...)` accepts free-form `outcome` strings. Its docstring names known values but explicitly says unknown values are grouped as "other". The fix can therefore record an honest outcome such as `want_satisfied_owner_confirmed` instead of pretending the action engine ran.

## Build Constraints

- Add the satisfaction hook only for `want_terminal_proposal`.
- Generic card approval must not satisfy wants.
- Deny/ignore must not satisfy wants.
- The hook must use `basis="owner_confirmed"` and must never use `self_observed_resolution`.
- `owner_confirmed` here means a direct owner answer to this specific terminal proposal, not an owner-reaction or engagement reward signal.
