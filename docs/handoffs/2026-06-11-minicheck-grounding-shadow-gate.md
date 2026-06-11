# MiniCheck Grounding Shadow v0 — STOP AT GATE

**Branch:** `minicheck-grounding-shadow-v0`
**Status:** built, default-OFF, not merged, not witnessed
**Scope:** offline/inert code plus a default-OFF daemon hook. No service was started, no daemon was restarted, and no flag was flipped.

## What Is Built

- `core/cognition/support_verifier.py`
  - `SupportVerifier` interface.
  - `HttpSupportVerifier` for the out-of-process MiniCheck service.
  - `FakeSupportVerifier` for tests.
- `core/cognition/grounding_shadow.py`
  - sentence splitting.
  - claimable-evidence extraction.
  - per-sentence support checks under a worker-only budget.
  - content-light telemetry generation.
  - bounded queue + background worker.
  - default-OFF `shadow_observe(...)`.
- `core/safety/audited_output.py`
  - behavior-touching hook, default-OFF.
  - after `_audit(...)` returns final `AuditResult.text`, it lazily calls `shadow_observe(...)`.
  - the returned reply remains `AuditResult.text`; shadow output is never consulted.
- `scripts/minicheck_verifier_service.py`
  - loopback `POST /support` MiniCheck wrapper.
  - lazy model load on first prediction.
  - the only new file that imports `torch` / `transformers`.
- `scripts/maez-minicheck-verifier.template.service`
  - inert user-service template.
  - not installed or started by this slice.

## Guarantees Pinned By Tests

- Default-OFF: `shadow_observe(...)` returns `disabled` without building the shadow singleton.
- Reply unchanged: the audited-output call site returns the same final text with shadow off and with shadow on plus a failing fake verifier.
- Non-blocking enqueue: `shadow_observe(...)` returns promptly even when the fake verifier would sleep for 5 seconds.
- Bounded queue: full queue returns and records `shadow_enqueue_failed`; enqueue never raises.
- Worker-only budget: slow fake verifier produces `budget_exceeded` and leaves remaining sentences unshadowed.
- Content-light telemetry: no reply text or evidence text is present by default; snippets require explicit debug.
- Import boundary: importing `core.cognition.grounding_shadow` does not import `torch` or `transformers`.

## Verification

Fresh run on this branch:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_support_verifier \
  tests.test_grounding_shadow \
  tests.test_minicheck_verifier_service \
  tests.test_self_claim_audit -v
```

Result: `Ran 81 tests ... OK`.

```bash
/home/rohit/maez/.venv/bin/ruff check \
  core/cognition/ \
  scripts/minicheck_verifier_service.py \
  core/safety/audited_output.py \
  tests/test_support_verifier.py \
  tests/test_grounding_shadow.py \
  tests/test_minicheck_verifier_service.py
```

Result: `All checks passed!`

## Review Gate

Before merge, the cross-lane covenant review should focus on:

- the reply-unchanged guarantee in `audited_output.py`;
- that the hook observes `AuditResult.text` (final served text), not pre-audit text;
- that the daemon imports no model runtime;
- that telemetry is content-light by default;
- that `shadow_enqueue_failed` is real and tested;
- that v0 gates nothing and never feeds the verifier verdict back into the reply.

## Owner Witness Breath

These steps are intentionally not taken by the implementer:

1. Merge after cross-lane review.
2. Install and start `minicheck-verifier.service` from `scripts/maez-minicheck-verifier.template.service`.
3. Smoke the endpoint:
   - evidence: `The sky is blue.`
   - claim: `The sky is blue.` should return `SUPPORTED`.
   - claim: `The sky is green.` should return `UNSUPPORTED`.
   If the real MiniCheck call shape differs, adapt the service instead of forcing it.
4. Flip `MAEZ_GROUNDING_SHADOW_ENABLED=1` (optionally `MAEZ_GROUNDING_SHADOW_DEBUG=1`) and restart the daemon.
5. Read `~/.local/state/maez/grounding_shadow.jsonl` for divergence telemetry.
6. Use the shadow data to decide the later wire-in slice: in-scope sentence filtering, recency/supersession, and any gating under the two-sided verifier-pressure discipline.

## Plain English

The lab instrument is built, but it is still sitting on the bench. By default Maez does not consult it at all. When the owner opens the gate, Maez will keep speaking exactly as before while a background worker quietly asks MiniCheck whether each final sentence followed from the claimable evidence, then writes down content-light divergence notes for humans to study.
