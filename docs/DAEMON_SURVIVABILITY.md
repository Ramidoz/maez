# Daemon Survivability Knobs

Operational notes for background paths that must fail boundedly instead of
wedging the daemon.

## Proposal intent timeout

`MAEZ_PROPOSAL_INTENT_TIMEOUT_S` controls the LLM call used by the background
proposal worker when it asks for a structured patch intent.

- Default: `45`
- Scope: proposal-intent generation only
- Failure behavior: timeout marks the proposal job `failed`; it does not retry
  immediately
- Reason: proposal generation is background self-improvement work, so daemon
  responsiveness wins over completing a proposal

Example:

```bash
MAEZ_PROPOSAL_INTENT_TIMEOUT_S=30 python daemon/maez_daemon.py
```
