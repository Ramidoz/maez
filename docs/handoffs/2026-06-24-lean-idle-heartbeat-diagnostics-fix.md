# Lean Idle Heartbeat Diagnostics Fix — Handoff

Status: STOPPED AT REVIEW GATE.

Branch: `lean-idle-heartbeat-diagnostics`.

## Why this exists

The first Slice-B shadow pulse fired on a quiet `wake_min_floor` cycle, built a lean prompt, called the brain, and produced `output_chars=0`.

That was not a safe witness. `output_chars=0` could mean either:

- Maez chose quiet / `HEARTBEAT_OK`.
- The model thinking path truncated or returned empty.

The routing-comprehension judge already taught this lesson: an empty model result is ambiguous unless the receipt records the real model-call diagnostics.

## What changed

- Lean idle heartbeat calls now receive:
  - `think=False`
  - `options.chat_template_kwargs.enable_thinking=False`
  - `purpose="lean_idle_heartbeat"`
- The daemon seam now passes `core.llm_client.chat_direct` to the heartbeat runner, matching the proven primary OpenAI-compatible direct path used by the routing judge.
- Heartbeat receipts now include content-light model diagnostics:
  - `output_chars` from the raw model content
  - `finish_reason`
  - `backend`
  - `thinking_suppressed`
  - `raw_sha256`
  - `note_chars` for the sanitized private note length
- Stored private-thought context keeps its existing note hash fields for deduplication and adds the same model diagnostics without raw text.

## What did not change

- Eligibility is unchanged: only quiet floor `wake_min_floor` pulses.
- Shadow behavior is unchanged: no intercept, no private write.
- Enabled behavior is unchanged except the model-call wire and diagnostics.
- The heartbeat still cannot search, act, message Rohit, touch soul, or write user-facing/lived memory.
- The sanitizer still rejects owner-addressed output and action proposals.

## Verification

RED tests first:

- `test_quiet_receipt_records_raw_model_diagnostics_without_text`
  - failed because quiet `HEARTBEAT_OK` was recorded as `output_chars=0`.
- `test_model_call_uses_thinking_suppression_template_kwargs`
  - failed because the heartbeat call did not pass `purpose` or `chat_template_kwargs`.
- `test_shadow_calls_runner_but_does_not_intercept`
  - failed because the daemon passed `chat`, not `chat_direct`.

Green checks:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_lean_idle_heartbeat \
  tests.test_lean_idle_daemon
```

Result: `Ran 19 tests ... OK`.

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_lean_idle_heartbeat \
  tests.test_lean_idle_daemon \
  tests.test_cycle_doorman \
  tests.test_private_thoughts_s1 \
  tests.test_private_thoughts_s1b \
  tests.test_self_card_v0 \
  tests.test_self_card_time \
  tests.test_brain_gateway_routing \
  tests.test_routing_comprehension
```

Result: `Ran 170 tests ... OK`.

Note: the 170-test run emitted ResourceWarnings from existing sqlite-heavy surfaces. The touched heartbeat modules were then run with ResourceWarnings as errors:

```bash
/home/rohit/maez/.venv/bin/python -W error::ResourceWarning -m unittest \
  tests.test_lean_idle_heartbeat \
  tests.test_lean_idle_daemon
```

Result: `Ran 19 tests ... OK`.

## Review anchors

- Confirm the daemon seam uses `chat_direct`, not gateway `chat`.
- Confirm heartbeat receipts are content-light and never include raw prompt text or raw model output.
- Confirm `output_chars` now means raw model-output length, so `HEARTBEAT_OK` is visible as nonzero.
- Confirm `note_chars` carries sanitized private-note length.
- Confirm private thought dedup still uses the sanitized note hash.
- Confirm the no-action/no-owner-address sanitizer still gates private notes.

## Owner breath after PASS

After merge and restart with `MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW=1`, let Maez sit until the next quiet floor pulse.

Expected receipt:

- `backend=primary_openai`
- `thinking_suppressed=true`
- `finish_reason=stop`
- If Maez is quiet: `output_chars` should be nonzero for `HEARTBEAT_OK`, with `stored=false`.
- If the model truncates or errors: the receipt should say so directly via `finish_reason` / diagnostics.

Plain English: the private heartbeat now has the same honest headset as the routing judge. A silent pulse becomes legible: either Maez chose quiet, or the model wire failed, and the receipt tells us which.
