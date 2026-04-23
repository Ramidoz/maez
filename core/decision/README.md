# core/decision

The conductor. Every proposed action from every surface passes
through this subpackage.

| Module | Role |
|---|---|
| [`decision_pipeline.py`](decision_pipeline.py) | Single entry point (`DecisionPipeline.handle_action`) that runs: covenant gate → action classifier → injection scan → audit LLM → routing (execute inline / create card / open dialog / deny). |
| [`pending_cards.py`](pending_cards.py) | SQLite-backed store for approval cards. State machine: `CREATED → APPROVED → RUNNING → DONE/FAILED` (or `DENIED / EXPIRED / DEFERRED`). Fingerprint-locked against concurrent resolutions. |
| [`approval_sessions.py`](approval_sessions.py) | Pre-approval of a *class* of commands for a window (e.g. "shell reads under ~/maez until 2026-04-23"). Lets the owner blanket-trust a task session without card-per-command churn. |
| [`proposal_lookup.py`](proposal_lookup.py) | Resolves a proposal ID (from evolution subsystem or dream state) back to the underlying card / proposal row for surfacing in chat. |

## Pipeline flow

```
handle_action(action, params, reasoning, user_id, chat_id, ...)
  ├─ covenant gate         (deterministic refuse for hard-protected surface)
  ├─ classify_action       (core.actions.action_classifier)
  ├─ scan for injection    (core.safety.injection_patterns)
  ├─ audit_action          (core.cognition.audit — two-pass LLM)
  ├─ switch on verdict:
  │    APPROVE         → execute inline (Lane 0)
  │    APPROVE_WITH_CARD → create card, return pending_approval
  │    ESCALATE        → open self-mod dialog (Lane 3)
  │    DENY            → refuse with reasoning
  └─ write audit row + card row
```

## Invariants

- **Single entry point.** No chat surface calls `action_engine` or
  `tool_loop` directly. Every action flows through
  `handle_action` / `handle_reply`.
- **State-machine guards.** `pending_cards` refuses transitions that
  don't match `allow_from={...}` — prevents double-approval and
  race-terminal-transition bugs. After the 02-B1 fix, the pipeline
  catches `CardStoreError` around `mark_running` / `mark_done` /
  `mark_failed` and fails gracefully rather than propagating.
- **Audit row is append-mostly.** Only `record_outcome` can update
  an existing row; everything else inserts.

## Legacy import paths

Pre-Phase-3 paths (`core.decision_pipeline`, `core.pending_cards`,
`core.approval_sessions`, `core.proposal_lookup`) are shims.
