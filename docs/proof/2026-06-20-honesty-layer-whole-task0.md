# Honesty-Layer Whole — Task 0 Proof Gate

Date: 2026-06-20
Branch: `honesty-layer-whole`
Plan: `docs/superpowers/plans/2026-06-20-honesty-layer-whole.md`

## Verdict

GO, with two Task-0 corrections folded in before code:

1. `overclaim_judge` is not only claimed by `MAEZ_INTAKE_FACULTY_SHADOW`; the default semantic audit also uses the `:8081` judge. Its registry posture must be always/configured, not single-flag asleep.
2. There is no single universal owner-facing text chokepoint. The broad generated-text hook is `audit_assistant_text()`, but the live daemon owner-reply seam is `MaezDaemon.handle_message()` after tool-call cleanup. The strip remains allowlist-narrow and must not touch citations or ordinary bracket text.

## Fix 1 — Support Gate Fail-Silent On Tool Absence

Code seam:

- `core/cognition/grounding_shadow.py::_caveat_for`
- `core/cognition/grounding_shadow.py::apply_support_gate`

Current behavior:

- `cited_support` + `UNSUPPORTED` returns `I couldn't confirm this from the source I cited.`
- `unmatched_citation` returns `I cited a source I can't match here.`
- `verifier_unavailable` and `budget_exhausted` return `I couldn't verify this before sending.`

Required behavior:

- Keep caveats for real evidence problems:
  - `cited_support` + `UNSUPPORTED`
  - `unmatched_citation`
- Suppress owner-facing caveats for tool absence / gate budget absence:
  - `verifier_unavailable`
  - `budget_exhausted`
- Still record the absence in the support row / gate receipt. Silence means "checker unavailable," not "evidence supported."

Receipt path:

- `apply_support_gate` builds per-sentence `SupportDecision` rows before asking `_caveat_for`.
- Removing the caveat does not remove the `sentences` record, the `support_row`, or the `support_gate_applied` receipt.

Test requirement:

- A verifier-unavailable row is emitted while the served reply contains no `I couldn't verify this before sending.`
- `UNSUPPORTED` still caveats.

## Fix 2 — `overclaim_judge` Runtime Registry Claimant

Code seam:

- `core/infra/runtime_services.py` service entry `overclaim_judge`

Current behavior:

- `required_by=[]`, so the cockpit can label the judge asleep even when the live system depends on it.

Claimant inventory:

- Core semantic overclaim audit is default-on unless `MAEZ_SEMANTIC_AUDIT=0`.
  - `core/safety/self_claim_audit.py::audit`
  - `core/cognition/grounding_judge.py::judge`
  - `core/routing/model_config.py::JUDGE_BASE_URL`, default `http://127.0.0.1:8081`
- Intake faculty shadow also uses the same `JUDGE_BASE_URL` when `MAEZ_INTAKE_FACULTY_SHADOW=1`.
  - `core/cognition/intake_shadow.py`
  - `core/cognition/intake_faculty.py`
- Fetch injection shadow can also call the judge behind `MAEZ_FETCH_INJECTION_SHADOW`.
  - `core/cognition/fetch_screen.py`

Required behavior:

- `overclaim_judge` must be represented as required/configured by the default semantic audit, not only by optional shadows.
- The registry should therefore use the service's always-required posture for v0 rather than a single optional flag.

Test requirement:

- With no optional shadow flags, the `overclaim_judge` entry is not asleep solely because `required_by` is empty.

## Fix 3 — Narrow Backstage Label Strip

Observed leak:

- `[CAPABILITY_STATE]` / `CAPABILITY_STATE` can surface in Maez's voice.

Allowed strip list:

- `CAPABILITY_STATE` only.

Explicitly not stripped:

- Citations: `[E1]`, `[E10]`
- Ordinary user/content bracket text: `[maybe later]`
- Other prompt/source labels discovered in the repo, such as `[SCREEN]`, `[GIT]`, `[REDDIT]`, `[CALENDAR]`, `[COGNITION]`, `[CONTINUITY]`, `[EVIDENCE ENVELOPE]`, `[RECALLED MEMORY]`, `[TOOL_CALL]`

Prompt seam:

- `core/cognition/capability_card.py` emits `CAPABILITY_STATE (current self-capability; private grounding):`.
- Tighten the capability-card instruction so the model is told not to echo `CAPABILITY_STATE` or `[CAPABILITY_STATE]`.

Backstop seam:

- Broad generated-text hook: `core/safety/audited_output.py::audit_assistant_text`.
- It covers daemon replies, web `/chat`, public Telegram, and daemon autonomous notices, but not every possible owner-facing string or card.
- If used there, the strip must apply before every return, including early returns on skipped/unavailable audit paths.

Live owner-reply seam:

- `daemon/maez_daemon.py::MaezDaemon.handle_message` is the central live owner-reply synthesis path for surface-v2 Telegram and cockpit/core inbound.
- Best insertion neighborhood, if a daemon-specific belt is needed: after existing tool-call cleanup and before audit/store/return, preserving the function's invariant that audited/stored/final returned text are the same.

Task decision:

- Implement the narrow strip in the broad audited generated-text hook first, because this is the widest existing safety boundary for generated replies.
- Keep the allowlist to `CAPABILITY_STATE` only. Do not add broad bracket stripping.

Test requirement:

- `[CAPABILITY_STATE] + [E1] + [maybe later] + [E10]` strips only the backstage label and preserves the citation and ordinary bracket text.

## Fix 4 — MiniCheck Verifier Health Contract

Code seam:

- `scripts/minicheck_verifier_service.py`
- `core/infra/runtime_services.py::_support_contract`

Current behavior:

- The runtime services organ probes `GET /health` on the MiniCheck verifier.
- The MiniCheck service only implements `POST /support`, so the cockpit cannot see its health truthfully.

Required behavior:

- `GET /health` returns:

```json
{"status":"ok","contract":"minicheck_support.v1"}
```

Test requirement:

- Health payload matches the runtime-services expected contract.
- `POST /support` behavior is unchanged.

## Scope Guard

This slice must not touch the parked time-sense / rhythm work:

- `core/evolution/subjective_duration.py`
- `core/memory/episodes.py`
- learned rhythm flags / Slice A code

It is an honesty-layer-whole slice only:

- support-gate voice behavior under verifier absence
- backstage label strip
- runtime service registry truth for `:8081`
- MiniCheck health visibility

