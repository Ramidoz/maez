# Lean Idle Heartbeat Prompt Enrichment v0 — Review Gate Handoff

Branch: `lean-idle-heartbeat-prompt-enrichment-v0`
Tip: `a57e077`
Base: `27f07b9`

Status: built and stopped at the review gate. Not merged. Not restarted. No flags flipped.

## Task 0 Seam Decisions

- Rhythm facts: bound to `self._time_sense_handle().rhythm_context()`.
- Rhythm keys used:
  - `rhythm_current_gap_s` -> `owner_contact_gap_s`
  - `rhythm_recent_gap_median_s` -> `recent_usual_gap_s`
  - `rhythm_all_time_gap_median_s` -> `all_time_usual_gap_s`
  - `rhythm_current_gap_percentile_all_time` -> `gap_percentile_all_time`
- Body state:
  - `daemon_overall` uses `_operator_health()["mode"]`.
  - `backup_freshness` uses `_operator_health()["backup_freshness_class"]`.
  - `watchdog` uses `_watchdog_health()["watchdog_state"]`.
  - No prose parsing from `_default_body_state_provider()`.
- Private thoughts:
  - `PrivateThoughts.recent(limit)` rows expose top-level `content`, top-level `memory_phase`, and `context` from `context_json`.
  - No dedicated private-reader-scoped row reader exists for this exact envelope, so `select_private_reader_thoughts()` is the gate.
  - Required envelope: `context.source == lean_idle_heartbeat.v0`, `context.consent_tier == owner_private`, `private_reader in context.allowed_flows`, `memory_phase == gestation`.
- Open loops:
  - Wants use the real daemon seam `self.wants.active_wants(limit=50)`.
  - Pending terminal proposals use `self._want_pursuit_card_store().list_open_by_action(TERMINAL_PROPOSAL_ACTION)`.
  - Output is count + class labels only: `wants`, `proposals`. No want/card text.

## What Changed

- `LeanIdleFacts` now carries optional `time_facts`, `body_state`, `open_loops`, and `recent_private_thoughts`.
- `build_lean_idle_prompt()` appends factual blocks only when material exists.
- `FORBIDDEN_RENDER_WORDS` guards the renderer against interpretive framing: `lonely`, `missed`, `long`, `should`, `worry`, `feel`.
- `select_private_reader_thoughts()` surfaces at most two clipped heartbeat thoughts through the full private-reader envelope.
- `MaezDaemon` now has fail-soft adapters for time, body, open-loop counts/classes, and recent private-reader thoughts.
- `_maybe_run_lean_idle_heartbeat()` threads those adapters into `LeanIdleFacts` only after the heartbeat flags and quiet-floor eligibility pass.

## Verification

Commands run:

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v
```

Result: `35 OK`.

```bash
/home/rohit/maez/.venv/bin/ruff check core/cognition/lean_idle_heartbeat.py daemon/maez_daemon.py tests/test_lean_idle_heartbeat.py tests/test_lean_idle_daemon.py
```

Result: `All checks passed!`

## Covenant Checklist For Review

- Facts, not feelings: the forbidden-word renderer guard fires on assembled prompt text with controlled neutral inputs.
- Private-reader discipline: planted rows failing any one envelope condition are invisible.
- Content-light receipts: existing receipt tests still assert no raw prompt or raw model output. New adapter outputs are count/class/factual maps only.
- Default-off byte-identical: `test_default_off_reads_no_enrichment_seams` proves the four enrichment adapters are never touched when both heartbeat flags are off.
- Task 0 placeholders resolved: no `<...FROM_TASK0>` placeholders remain in code.
- No salience: no scoring, weighting, learning, or owner-reaction reward added.
- No rail change: still quiet-floor only, still private, still no search/action/owner-message/soul-write/lived-memory-write.

## Owner Breath After Review Pass

Merge, then restart with the existing shadow posture. Watch `lean_idle_heartbeat` receipts across quiet floor pulses:

- `prompt_sha256` should vary as the gap/body/loops/recent private thoughts change.
- `fact_keys` should include `time_facts,body_state,open_loops,recent_private_thoughts`.
- If the brain returns `HEARTBEAT_OK`, verify `finish_reason=stop` and `thinking_suppressed=true`.
- If it writes a private thought, verify it stays private, lean, non-leaking, and non-fixated.

Plain English: this slice gives Maez a changing window instead of the same static photograph. It still does not tell Maez what to feel or what matters.
