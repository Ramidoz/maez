# Idle Heartbeat Body-State Window v0 — Build Handoff

Date: 2026-06-28
Status: STOP AT REVIEW GATE — not merged, not enabled, no live flag flip

## What Built

This slice adds a shadow-gated body/self-state window to the lean idle
heartbeat. The code-name remains `world_window.py`, but the witness
interpretation is deliberately narrower:

> This is a body/self-state sense, not an owner-world sense. If Maez stays quiet
> after this, the honest conclusion is "machine-body signal alone was thin,"
> not "world-signal failed." The owner-world arc
> (presence/screen/git/vision/Jetson/connectors) is separate and unbuilt.

The approved Task 0 table is:

`docs/proofs/2026-06-28-world-window-table.md`

It was owner-approved before implementation.

## Files

- `core/cognition/world_window.py` — pure body-state signature/delta module.
- `core/cognition/lean_idle_heartbeat.py` — renders a bounded
  `BODY-STATE WINDOW (changes since last beat)` block.
- `daemon/maez_daemon.py` — computes the window only when
  `MAEZ_WORLD_WINDOW_SHADOW=1`, then passes content-light deltas to the
  heartbeat.
- `tests/test_world_window.py`
- `tests/test_lean_idle_heartbeat.py`
- `tests/test_lean_idle_daemon.py`
- docs/spec/plan/proof wording patched to prevent overclaiming this as a full
  world/owner-life window.

No `core/evolution/` files were changed.

## Guards

- Cold start is baseline-only: first beat records projected signatures and emits
  zero deltas.
- The transient signature cache lives at
  `~/.local/state/maez/world_window_signatures.json`, not `memory/`.
- Flag off creates no cache and leaves the prompt byte-equivalent.
- Projections are shadows/labels only. Raw values, process names, PIDs, exact
  rates, exact percentages, and exact temperatures do not enter the prompt.
- Prompt rendering includes only neutral phrase + provenance + sensitivity.
  Signature hashes are for comparison/receipts only and do not render.
- Exclusion receipts are content-light: field + reason only.
- The module imports no curiosity producer, action path, soul/want/wondering,
  private thought, salience, or fresh-moment writer.
- `HEARTBEAT_OK` instruction remains unchanged.

## Verification

Focused test command:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest \
  tests.test_world_window \
  tests.test_lean_idle_heartbeat \
  tests.test_lean_idle_daemon \
  -v
```

Observed result: 67 tests, OK.

## Review Checklist

- Confirm the body-state naming/interpretation guard is present in spec, plan,
  proof, and this handoff.
- Confirm prompt block says `BODY-STATE WINDOW`, not a generic world block.
- Confirm no raw values appear in tests or prompt rendering.
- Confirm no `core/evolution/` diff.
- Confirm flag-off path does not instantiate or create the signature cache.
- Confirm `MAEZ_WORLD_WINDOW_SHADOW` is not enabled by this build.

## Post-Review Witness

If review passes and owner chooses to witness:

1. Merge/apply the build.
2. Set `MAEZ_WORLD_WINDOW_SHADOW=1`.
3. Restart daemon.
4. First eligible idle heartbeat should log `world_window` receipt with
   `cold_start=true`, `delta_count=0`; prompt has no body-state deltas.
5. Cause or wait for a real body-state band/set change.
6. Next eligible heartbeat should show a content-light body-state delta, e.g.
   `cpu load or temperature band changed` or `active process set changed`, with
   provenance/sensitivity labels and no raw values.
7. Turning the flag off should stop new cache reads/writes and return the prompt
   to the prior shape.

Witness interpretation:

- If Maez writes a thought, it was stirred by machine-body/interoceptive signal,
  not owner-world signal.
- If Maez stays quiet, the finding is that body-signal alone was thin.
