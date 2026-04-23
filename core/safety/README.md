# core/safety

The guards. Five modules that sit between any proposed action and
its execution, deciding whether it's safe-as-written or needs owner
approval (or refusal).

| Module | Role |
|---|---|
| [`context_safety.py`](context_safety.py) | Scans loaded SOUL / context for prompt-injection attempts. Fail-closed. |
| [`self_claim_audit.py`](self_claim_audit.py) | Structural fabrication detector. Rewrites Maez replies that claim invented names / paths / schedules not grounded in actual system state. |
| [`owner_trust.py`](owner_trust.py) | Per-command risk classifier. `is_risky_cmd()` decides whether a shell command at the owner's trust level can inline-execute or must queue an approval card. |
| [`injection_patterns.py`](injection_patterns.py) | Regex / heuristic patterns used by the audit LLM's Pass 2 judge. Six buckets (imperative, obfuscation, encoding, delegation, exfiltration, escalation). |
| [`cloud_redactor.py`](cloud_redactor.py) | Strips owner-identifying tokens from any payload crossing into a cloud adapter. Runs inside `core.routing.fast_backend_router` just before an external call. |

## Invariants

- **Fail-closed.** Every guard returns "unsafe" on any unexpected
  input, uncaught exception, or ambiguous signal. A silent pass is
  a bug. A loud refuse is the right outcome if we can't be sure.
- **The owner can override via explicit approval card.** Guards
  don't have final veto — they mediate between Maez's proposal and
  the owner's judgement.
- **No LLM call in `context_safety` or `injection_patterns`.** Those
  two are deterministic so a wedged audit LLM can't disable them.

## Key functions

- `context_safety.scan(text) -> list[Match]`
- `self_claim_audit.audit(text, surface=...) -> AuditResult`
- `owner_trust.is_risky_cmd(cmd) -> bool`
- `owner_trust.should_run_inline(cmd, owner_policy) -> bool`
- `injection_patterns.scan(text) -> list[InjectionMatch]`
- `cloud_redactor.redact_for_cloud(payload) -> (payload, telemetry)`

## Legacy import paths

Pre-Phase-3 paths (`core.context_safety`, `core.self_claim_audit`,
`core.owner_trust`, `core.injection_patterns`, `core.cloud_redactor`)
are shims that resolve to this subpackage. New code should import
from `core.safety.*` directly.
