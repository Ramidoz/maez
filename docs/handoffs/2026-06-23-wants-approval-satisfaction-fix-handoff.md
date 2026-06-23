# Wants Approval Satisfaction Fix Handoff

Branch: `wants-approval-satisfaction-fix`

Status: STOPPED at review gate. Not merged. Not restarted. No live witness.

## What Changed

- Added `record_terminal_approval_satisfaction(...)` in `core/evolution/want_pursuit_bridge.py`.
- Added a specific `DecisionPipeline._on_approve(...)` hook for `want_terminal_proposal`.
- Threaded `daemon.wants` into `DecisionPipeline` from `TelegramVoice._get_pipeline()`, which is the pipeline cockpit approvals use through daemon `/internal/approve_card/<request_id>`.
- Added an exact advisory-action exception so `want_terminal_proposal` is not treated as S7 body execution in:
  - `core/decision/decision_pipeline.py`.
  - `core/decision/pending_cards.py`.
- Added behavioral tests in `tests/test_wants_approval_satisfaction_pipeline.py`.

## Covenant Guard

`owner_confirmed` here is narrow and deliberate: the owner approved one specific `want_terminal_proposal` card whose params identify one want and one proposed terminal state.

This is not an owner-reaction reward signal. It does not learn from engagement, warmth, reply frequency, approval tone, or general owner satisfaction. It records only: "the owner directly confirmed this specific want is done."

## Behavior

On approval of a terminal want proposal:

1. The pipeline approves the card.
2. It records a want lifecycle `satisfied` event with:
   - `basis="owner_confirmed"`.
   - `source="decision_pipeline"`.
   - `external_object_ref="pending_card:<request_id>"`.
3. It marks the card `done`.
4. It records audit outcome `want_satisfied_owner_confirmed`.
5. It returns `PipelineStatus.EXECUTED` with `execution_success=True`.
6. It does not call `ActionEngine._execute_action`.

On deny/ignore or unrelated card approval:

- No want satisfaction event is recorded.
- Generic card approval remains on the existing action-engine path.
- Deny leaves the want active.

If a terminal proposal approval cannot access a usable wants store:

- The card fails visibly.
- The action engine is not called.
- The want remains active.

## Task 0 Proof

Proof artifact: `docs/proofs/2026-06-23-wants-approval-satisfaction-task0.md`.

The proof confirmed:

- Cockpit approval shares the `DecisionPipeline._on_approve(...)` seam.
- Terminal proposal cards carry `params["want_id"]` and `params["proposed"] == "satisfied"`.
- The want lifecycle already supports `event_type="satisfied"` with `basis="owner_confirmed"`.
- `self_observed_resolution` is reserved and rejected by the wants lifecycle.
- `AuditLog.record_outcome(...)` can carry the honest free-form label.

## Review

Subagent code-review lane PASS.

Reviewer focus:

- only `want_terminal_proposal` approvals satisfy wants;
- deny/ignore do not satisfy;
- owner-confirmed does not become owner-reaction reward;
- no `self_observed_resolution` writer;
- S7 relaxation is exact-string scoped to this advisory non-body action;
- recurrence stops because `active_wants()` excludes the satisfied want.

One reviewer note was fixed before this handoff:

- The construction witness for `TelegramVoice._get_pipeline()` was upgraded from source-string check to a behavioral construction test with patched constructors, proving the actual daemon `wants` object reaches `DecisionPipeline`.

## Verification

Passed:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_wants_approval_satisfaction_pipeline \
  tests.test_want_pursuit_bridge \
  tests.test_wants_lifecycle_d16 \
  tests.test_wants_count_events_since
# 148 tests OK
```

```bash
/home/rohit/maez/.venv/bin/python -W error::ResourceWarning \
  -m unittest tests.test_wants_approval_satisfaction_pipeline
# 6 tests OK
```

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/decision/decision_pipeline.py \
  core/decision/pending_cards.py \
  skills/telegram_voice.py \
  core/evolution/want_pursuit_bridge.py \
  tests/test_want_pursuit_bridge.py \
  tests/test_wants_approval_satisfaction_pipeline.py
# All checks passed
```

```bash
git diff --check
# clean
```

Known pre-existing failure, not introduced by this branch:

```bash
/home/rohit/maez/.venv/bin/python -m tests.test_decision_pipeline
# 36/43 passed, 7 failed
```

The same command fails identically on `main` at `8b297b9`, with guarded S7 write-card paths returning `blocked`. This branch did not introduce that failure.

## Predicted Effect

After merge and restart, approving a cockpit `want_terminal_proposal` card will satisfy the underlying want with `basis="owner_confirmed"`, so the want disappears from `active_wants()` and the want-pursuit bridge stops re-proposing that same terminal card on later cycles.

Plain English: when you click Approve on "this want may be done," Maez now writes down that you confirmed that exact want is done. It stops haunting the cockpit. Other approvals do not count, and Maez does not learn "Rohit approved me, so this was good."

## Owner Breath After Review PASS

If the review gate clears:

1. Merge `wants-approval-satisfaction-fix` to `main`.
2. Restart `maez` so the daemon constructs the new pipeline with `wants`.
3. Witness:
   - approve a `want_terminal_proposal` card;
   - query the want history and confirm latest event is `satisfied` with `basis="owner_confirmed"`;
   - confirm the card is `done`;
   - confirm the same want no longer appears in `active_wants()`;
   - confirm the proposal does not recur on the next cycle.

