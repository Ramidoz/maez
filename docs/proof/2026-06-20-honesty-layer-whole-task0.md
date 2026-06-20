# Honesty-Layer Whole — Task 0 Proof Gate

Date: 2026-06-20
Branch: `honesty-layer-whole`
Plan: `docs/superpowers/plans/2026-06-20-honesty-layer-whole.md`

## Verdict

GO, with two proof-gate corrections folded in before behavior code:

1. `overclaim_judge` is not only claimed by `MAEZ_INTAKE_FACULTY_SHADOW`; the default semantic audit also uses the `:8081` judge. Its registry posture must be always/configured, not optional-only asleep.
2. There is no single universal owner-facing text chokepoint. The broad generated-text hook is `audit_assistant_text()`, but it is not every mouth. For this slice, the strip is deliberately narrow and only removes the private capability-state marker at the audited generated-text boundary.

## Fix 1 — Support Gate Fail-Silent On Tool Absence

Code seam:

- `core/cognition/grounding_shadow.py::_caveat_for`
- `core/cognition/grounding_shadow.py::apply_support_gate`

Current modes:

- Keep owner-facing caveat: `mode="cited_support"` with `verdict=UNSUPPORTED`.
- Keep owner-facing caveat: `mode="unmatched_citation"`.
- Suppress owner-facing caveat: `mode="verifier_unavailable"`.
- Suppress owner-facing caveat: `mode="budget_exhausted"`.

Receipt path:

- `apply_support_gate` builds sentence records before asking `_caveat_for`.
- Removing the caveat does not remove the `sentences` record, the `support_row`, or the `support_gate_applied` receipt.
- Timeout is not a distinct owner-facing mode today; support-verifier transport failures and timeouts fold into `UNAVAILABLE`, then `verifier_unavailable`.

Test requirement:

- A verifier-unavailable or budget-exhausted row is emitted while the served reply contains no `I couldn't verify this before sending.`
- `UNSUPPORTED` still caveats.

## Fix 2 — `overclaim_judge` Runtime Registry Claimant

Code seam:

- `core/infra/runtime_services.py` service entry `overclaim_judge`

Current behavior:

- `required_by=[]`, so the cockpit can label the judge asleep even when the live system depends on it.

Claimant inventory:

- Core semantic overclaim audit is default-on unless explicitly disabled.
  - `core/safety/self_claim_audit.py`
  - `core/cognition/grounding_judge.py`
  - `core/routing/model_config.py::JUDGE_BASE_URL`, default `http://127.0.0.1:8081`
- Intake faculty shadow can also use the same judge when `MAEZ_INTAKE_FACULTY_SHADOW=1`.
- Fetch injection shadow can also use the judge when `MAEZ_FETCH_INJECTION_SHADOW=1`.

Required behavior:

- `overclaim_judge` must be represented as required/configured by the default semantic audit.
- For this v0 registry fix, use `required_by=["always"]`.

Test requirement:

- With optional shadow flags off, `overclaim_judge` is still configured and does not become asleep solely because `required_by` is empty.

## Fix 3 — Narrow Backstage Label Strip

Observed leak:

- `[CAPABILITY_STATE]` / `CAPABILITY_STATE` can surface in Maez's voice.

Allowed strip list:

- `CAPABILITY_STATE` only.

Explicitly not stripped:

- Citations: `[E1]`, `[E10]`
- Ordinary user/content bracket text: `[maybe later]`
- Other prompt/source labels discovered in the repo, such as `[SCREEN]`, `[GIT]`, `[REDDIT]`, `[CALENDAR]`, `[COGNITION]`, `[CONTINUITY]`, `[EVIDENCE ENVELOPE]`, `[RECALLED MEMORY]`, `[TOOL_CALL]`
- The legacy `YOUR LIVE BODY` prose header. It is not the leaked private marker in this slice and is not stripped.

Prompt seam:

- `core/cognition/capability_card.py` emits `CAPABILITY_STATE (current self-capability; private grounding):`.
- Tighten the capability-card instruction so the model is told not to echo `CAPABILITY_STATE` or `[CAPABILITY_STATE]`.

Backstop seam:

- Broad generated-text hook: `core/safety/audited_output.py::audit_assistant_text`.
- It covers daemon replies, web `/chat`, public Telegram, and daemon autonomous notices, but not every possible owner-facing string or card.
- The strip must apply before every return from that helper, including early returns on skipped/unavailable audit paths.

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
