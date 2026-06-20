# Honesty-Layer Whole — Handoff

Date: 2026-06-20
Branch: `honesty-layer-whole`
Tip before this handoff: `eb77781`
Base: `0dc465b`
State: BUILT_BRANCH_VERIFIED, not merged, not restarted.

## What Changed

Four honesty-layer fixes landed as one bounded slice:

1. **Support gate fails silent on tool absence**
   - `verifier_unavailable` and `budget_exhausted` still write the support row / gate receipt.
   - They no longer append `I couldn't verify this before sending.` to Maez's reply.
   - Real evidence problems still caveat:
     - `UNSUPPORTED` cited claims: `I couldn't confirm this from the source I cited.`
     - unmatched citations: `I cited a source I can't match here.`

2. **Backstage capability label strip**
   - Adds a narrow audited-output backstop for `CAPABILITY_STATE` / `[CAPABILITY_STATE]`.
   - Preserves `[E1]`, `[E10]`, `[maybe later]`, and ordinary bracket text.
   - Tightens the capability-card prompt so Maez is told not to echo the private marker.

3. **Truthful `:8081` judge registry**
   - `overclaim_judge` is now `required_by=["always"]`.
   - Task 0 corrected the premise: the default semantic audit claims `:8081`; it is not only an optional intake-shadow service.

4. **MiniCheck verifier health contract**
   - `scripts/minicheck_verifier_service.py` now exposes `GET /health`.
   - Payload: `{"status":"ok","contract":"minicheck_support.v1"}`.
   - `POST /support` remains unchanged.

## Verification

Focused regression suite:

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_support_gate \
  tests.test_grounding_shadow \
  tests.test_runtime_services \
  tests.test_minicheck_verifier_service \
  tests.test_backstage_label_strip \
  tests.test_capability_card \
  tests.test_output_command_guard \
  tests.test_audited_output_envelope \
  tests.test_valence_live_wiring \
  -v
```

Result: 136 tests, OK.

Lint:

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/cognition/grounding_shadow.py \
  core/cognition/capability_card.py \
  core/safety/audited_output.py \
  core/infra/runtime_services.py \
  scripts/minicheck_verifier_service.py \
  tests/test_support_gate.py \
  tests/test_backstage_label_strip.py \
  tests/test_runtime_services.py \
  tests/test_minicheck_verifier_service.py
```

Result: all checks passed.

Scope check:

Changed files are limited to:

- `core/cognition/capability_card.py`
- `core/cognition/grounding_shadow.py`
- `core/infra/runtime_services.py`
- `core/safety/audited_output.py`
- `docs/proof/2026-06-20-honesty-layer-whole-task0.md`
- `scripts/minicheck_verifier_service.py`
- `tests/test_backstage_label_strip.py`
- `tests/test_minicheck_verifier_service.py`
- `tests/test_runtime_services.py`
- `tests/test_support_gate.py`

No time-sense / rhythm files touched.

## Honest Broad-Suite Note

A wider audit-adjacent sweep including `tests.test_memory_integrity_invariant` exposed two failures outside this slice:

1. `AdapterNoLongerDoubleAudits.test_adapter_does_not_import_self_claim_audit`
   - The adapter still contains a legacy direct self-claim audit path/string.
2. `DaemonHandleMessageContract.test_soul_web_search_section_matches_inline_search_reality`
   - The live SOUL text does not contain the older test's expected phrase `web_search.py runs inline`.

I did not fold those into this branch because they are unrelated to the four-fix honesty-layer slice and would alter older surface/memory contracts. They should be handled as a separate cleanup if Rohit wants the broad memory-integrity module green again.

## Review Anchors

Ask the review lane to verify:

1. `_caveat_for` suppresses only `verifier_unavailable` / `budget_exhausted`; `UNSUPPORTED` and `unmatched_citation` still caveat.
2. The support row / gate receipt still records unavailable or budget-exhausted decisions even when the reply is silent.
3. `_strip_backstage_labels` only removes `CAPABILITY_STATE` / `[CAPABILITY_STATE]`; citations and ordinary bracket text survive.
4. `overclaim_judge` being `always` is justified by the default semantic audit, not merely optional shadows.
5. MiniCheck `GET /health` matches `runtime_services._support_contract` and does not load the model.
6. No time-sense/rhythm files are touched.

## Owner Breath

After review PASS:

1. Merge branch to main.
2. Restart `maez.service` so the support-gate policy, runtime registry, and audit label-strip load into the daemon.
3. Restart `minicheck-verifier.service` so `GET /health` is live.
4. Restart `maez-web.service` only if the cockpit runtime-services process needs to refresh loaded code for the registry/self-view.

Witness:

- Send Maez any normal message while MiniCheck is down/unavailable: no generic `I couldn't verify this before sending.` tail should appear.
- A real unsupported cited claim still gets `I couldn't confirm this from the source I cited.`
- A reply containing `[CAPABILITY_STATE] Claim [E1].` should serve as `Claim [E1].`
- `/api/v1/services` should show `overclaim_judge` based on live `llama-judge.service` health, not asleep due to `required_by=[]`.
- `curl -s http://127.0.0.1:8083/health` should return `{"status":"ok","contract":"minicheck_support.v1"}` after the MiniCheck service restart.

## Plain English

This slice makes Maez's honesty layer less noisy and more truthful. If the fact-checking instrument is down, Maez stops apologizing in every reply as though every sentence is suspicious. If it actually checks a cited claim and the evidence does not support it, Maez still says so. The cockpit also stops lying about the Qwen judge being asleep, and it can finally see the MiniCheck support verifier's health. The backstage `CAPABILITY_STATE` label gets scrubbed without damaging citations.
