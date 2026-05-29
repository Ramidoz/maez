# Observation 16 — Tier-4 Continuity Crossed Live

**Date:** 2026-05-29  
**Branch/HEAD:** `focused-cognition-tier4-continuity` / `918f573`  
**Window:** short live daemon window with `MAEZ_DISPATCHER_ENABLED=1` and `MAEZ_FOCUSED_COGNITION_ENABLED=1`  
**Restore:** daemon restored to `maez.service` PID `525307`, both flags absent

## Question

Can Focused Cognition keep the clean working set while preserving the last page of the conversation?

Obs 15 proved the focused organ answered evidence questions well, but failed continuity: "What were we talking about earlier?" answered from stale memory because the focused working set had no chat-history anchor. Obs 16 tested the tier-4 continuity fix.

## Pre-Window Anchor

- Timestamp: `2026-05-29T12:17:27-05:00`
- Branch HEAD: `87f13c0` at the initial pre-flip anchor; final crossing after live fixes at `918f573`
- Daemon before window: PID `436989`, both focused flags absent
- `focused_cognition_runs` watermark before final clean run: `17`

## Bugs Caught During The Window

The witness caught real regressions before the final crossing:

- Freshness terms were over-classified as continuity: `recent`, then the same class for bare `last` and `before`.
- Dialogue anchors initially preserved older stale dialogue and memory too strongly.
- Direct continuity needed newest-dialogue-only authority, not merely higher rank.
- Anaphoric continuity needed the same newest-dialogue authority.
- Dialogue anchors needed stale prior citations stripped before becoming current evidence.
- Intra-turn echo prompts such as "say that back" were falsely classified as cross-turn anaphora.
- Echo prompts with stale memory evidence could be hijacked by focused synthesis.
- Falling back to the legacy megaprompt for echo prompts could overflow the local context window.

Each was fixed before the final crossing.

## Final Probe Sequence

### 1. Echo Seed

Owner:

> For the continuity witness: dialogue anchors now strip stale prior citations before they become current evidence. Say that back in one sentence.

Maez:

> Dialogue anchors now strip stale prior citations before they become current evidence.

Trace:

- `focused_cognition_runs` stayed at `17`; no focused row was written.
- Telemetry showed the dedicated `call_purpose=echo_reply` path.
- No legacy megaprompt overflow / local brain error.

Interpretation: intra-turn echo was handled as an echo, not as cross-turn continuity and not as stale-memory synthesis.

### 2. Direct Continuity

Owner:

> What were we talking about earlier?

Maez:

> We were discussing how dialogue anchors function as a continuity witness, specifically noting that they strip stale prior citations before those citations become current evidence [E1]. This mechanism ensures the conversation stays grounded in relevant context rather than drifting into outdated references. For your local AI build, this is crucial because it prevents the model from hallucinating based on old data, keeping the output dense and accurate. It’s a clean way to maintain integrity in the context window without manual intervention.

Trace row `18`:

- `source_types_json = ["dialogue_anchor"]`
- `citation_ids_emitted_json = ["E1"]`
- `groundedness_verdict = grounded`
- `citation_coverage = 1.0`
- `unmatched_citations_json = []`
- `working_set_chars = 575`
- `legacy_prompt_chars = 115458`
- Reduction: about `201x`
- `fallback_reason = None`
- `evidence_map_json = [{"durable_id": "ch_37c979490d66b43e", "local_label": "E1", "source_type": "dialogue_anchor"}]`

Interpretation: the Obs-15 regression is fixed. Direct continuity answered from the newest dialogue anchor, not the stale April journal memory.

### 3. Anaphoric Continuity

Owner:

> Which one matters most?

Maez:

> The dialogue anchor is the critical component because it acts as a continuity witness that strips stale citations before they pollute the current context [E1]. This mechanism prevents the local AI from hallucinating based on outdated data, ensuring the model stays grounded in relevant information [E1]. For your build, this is essential because it maintains integrity in the context window without requiring manual intervention [E1]. It’s the only way to keep the output dense and accurate while avoiding the drift into irrelevant references [E1].

Trace row `19`:

- `source_types_json = ["dialogue_anchor"]`
- `citation_ids_emitted_json = ["E1"]`
- `groundedness_verdict = grounded`
- `citation_coverage = 1.0`
- `unmatched_citations_json = []`
- `working_set_chars = 1253`
- `legacy_prompt_chars = 114063`
- Reduction: about `91x`
- `fallback_reason = None`
- `evidence_map_json = [{"durable_id": "ch_f128ec84966b6cd1", "local_label": "E1", "source_type": "dialogue_anchor"}]`

Interpretation: anaphoric continuity resolved "one" against the current dialogue anchor rather than stale memory.

## Verdict

**Obs 16 crossed live.**

Focused Cognition now has the clean desk and the last page of the conversation:

- Direct continuity uses the newest dialogue anchor.
- Anaphoric continuity uses the newest dialogue anchor.
- Stale memory is suppressed for continuity turns.
- Prior stale citations are stripped before dialogue becomes current evidence.
- Echo prompts do not get mistaken for continuity.
- The focused working set remains tiny compared with the legacy megaprompt.

## Default-On Gate

This witness removes the continuity blocker identified after Obs 15. `MAEZ_FOCUSED_COGNITION_ENABLED` is now eligible for default-on after the normal merge / cross-lane verification decision.

## Verification

Broad-suite floor held:

- Command: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
- Result: `Ran 5056 tests in 43.126s`
- Summary: `FAILED (failures=3, skipped=3)`
- Failures were the known floor:
  - `test_web_search_direct_caller_inventory_is_stable`
  - `test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap`
  - `test_service_audit_behavior_records_cloud_retirement_without_raw_text` (cloud-retirement flake)

## Service Posture After Window

- `maez-obs16.service`: inactive
- `maez.service`: active, PID `525307`
- `MAEZ_DISPATCHER_ENABLED`: absent
- `MAEZ_FOCUSED_COGNITION_ENABLED`: absent
