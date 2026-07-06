# core/safety

The guards. These modules sit between text, proposed action, cloud
egress, and memory writes, deciding whether something is safe-as-written,
needs owner approval, or must be refused/degraded.

| Module | Role |
|---|---|
| [`action_receipts.py`](action_receipts.py) | Receipt helpers for action outcomes. |
| [`audit_flag_buffer.py`](audit_flag_buffer.py) | Buffered flag/audit telemetry helpers. |
| [`audit_signal_manifest.py`](audit_signal_manifest.py) | Closed manifest of audit signal names. |
| [`audited_output.py`](audited_output.py) | Audit-before-store invariant helpers for model output. |
| [`canaries.py`](canaries.py) | Canary/marker utilities for prompt and recall safety tests. |
| [`clinical_boundary.py`](clinical_boundary.py) | Clinical/crisis boundary guard and private-thought crisis signal writer. |
| [`cloud_redactor.py`](cloud_redactor.py) | Strips owner-identifying tokens from payload previews and egress-gate minimization paths. The old fast-backend router cloud path is retired; new cloud consults route through the provenance-aware egress gate. |
| [`context_safety.py`](context_safety.py) | Scans loaded SOUL / context for prompt-injection attempts. Fail-closed. |
| [`injection_patterns.py`](injection_patterns.py) | Regex / heuristic patterns used by the audit LLM's Pass 2 judge. Six buckets (imperative, obfuscation, encoding, delegation, exfiltration, escalation). |
| [`output_command_guard.py`](output_command_guard.py) | Detects command-shaped text in generated output. |
| [`owner_trust.py`](owner_trust.py) | Per-command risk classifier. `is_risky_cmd()` decides whether a shell command at the owner's trust level can inline-execute or must queue an approval card. |
| [`premise_audit.py`](premise_audit.py) | Premise/grounding audit helpers. |
| [`self_claim_audit.py`](self_claim_audit.py) | Structural fabrication detector. Rewrites Maez replies that claim invented names / paths / schedules not grounded in actual system state. |
| [`temporal_fragment_guard.py`](temporal_fragment_guard.py) | Detects temporal-fragment misuse in responses. |

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
- `clinical_boundary.guard_owner_text(text, ...) -> ClinicalBoundaryResult`
- `audited_output.*` audit-before-store helpers

## Legacy import paths

Pre-Phase-3 paths (`core.context_safety`, `core.self_claim_audit`,
`core.owner_trust`, `core.injection_patterns`, `core.cloud_redactor`)
are shims that resolve to this subpackage. New code should import
from `core.safety.*` directly.
