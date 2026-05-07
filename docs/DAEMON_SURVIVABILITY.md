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

Inspect recent proposal-intent failures:

```bash
sqlite3 memory/evolution_track.db \
  "SELECT id, weakness_description, last_error FROM proposal_jobs \
   WHERE state='failed' ORDER BY finished_at DESC LIMIT 10"
```

## Grounding judge circuit breaker

The grounding judge endpoint (default port 8081) is wrapped by a process-
local circuit breaker. After `MAEZ_JUDGE_BREAKER_THRESHOLD` transport
failures within `MAEZ_JUDGE_BREAKER_WINDOW_S` seconds, the breaker opens
and subsequent calls short-circuit as
`JudgeUnavailable(error_class='circuit_open')` without touching the
network. After `MAEZ_JUDGE_BREAKER_COOLDOWN_S`, the next call is admitted
as a single probe; success closes the breaker, failure reopens it.

| Env var | Default | Notes |
|---|---|---|
| `MAEZ_JUDGE_BREAKER_THRESHOLD` | `3` | Transport failures to open |
| `MAEZ_JUDGE_BREAKER_WINDOW_S`  | `300` | Window over which failures count |
| `MAEZ_JUDGE_BREAKER_COOLDOWN_S` | `30` | Time before HALF_OPEN probe allowed |

Invalid or non-positive values fall back to the defaults with a WARNING
on `core.cognition.grounding_judge`. A typo will not crash daemon import.

- Scope: dedicated judge HTTP path only (`_call_dedicated_judge`). The
  fallback `_llm_client.chat` path is intentionally not wrapped — it
  shares an endpoint with the proposal worker and gets its own breaker
  policy in a future slice.
- Failure classification: only `refused`, `timeout`, and `http_5xx`
  count toward the threshold. `bad_response` (judge alive, body
  malformed) is surfaced normally as `JudgeUnavailable` but does NOT
  trip the breaker — otherwise a single bad prompt-template deploy
  would deterministically open the circuit forever.
- State transitions log at WARNING on `core.cognition.grounding_judge`.
- Per-process state. Restart resets to CLOSED.

Inspect breaker state from a Python REPL:

```python
from core.cognition.grounding_judge import _JUDGE_BREAKER
print(_JUDGE_BREAKER)  # → CircuitBreaker(name='grounding_judge', state=..., ...)
```
