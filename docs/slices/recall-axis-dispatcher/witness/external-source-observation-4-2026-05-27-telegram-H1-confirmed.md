# Telegram Observation 4 — H1 CONFIRMED — Diagnostic seam never fired

**Slice:** Recall-Axis Dispatcher external-source consumption, post diagnostic-seam (04ce41b)
**Predecessor witnesses:**
- `external-source-observation-2-2026-05-27-telegram.md` (Finding 10 surfaced — 6f810e6)
- `finding10-telegram-prompt-construction-investigation-2026-05-27.md` (Hypothesis B static trace — e4ee0d2)
- `external-source-observation-3-2026-05-27-telegram-failed.md` (Option B failed — c2668a6)
**Window opened:** 2026-05-27T20:47:21-05:00 (PID 3413542, flag=1)
**Window closed:** 2026-05-27T20:52:26-05:00 (restored, PID 3415958, flag absent)
**Git HEAD at flip:** `04ce41b` (`test(dispatcher): log telegram jarvis block shape`)

## Verdict

**H1 confirmed with exact mechanism.** Zero `telegram_jarvis_block_state` log lines across 3 dispatcher turns. The diagnostic seam never fired because the code it instrumented is no longer in the inbound Telegram message path.

**Root cause is not stale .pyc or systemd binding.** The code DID load (source mtime 20:41:14, daemon restart 20:47:21). The code is correct in isolation (unit tests at 4975 floor pass; helper called directly classifies correctly). The code is just in the wrong file — `skills/telegram_voice.py`, which is the LEGACY Telegram class kept alive only for outbound `send_message` / `_send_card_message` calls. **Inbound Telegram messages route through `skills/surface/maez_adapter.py` since 2026-04-20**, per the comment at `daemon/maez_daemon.py:6094-6098`:

```python
# Vendored surface adapter in `skills/surface/` owns inbound
# Telegram polling as of 2026-04-20. Legacy TelegramVoice
# above keeps its loop alive only for outbound
# `send_message()` / `_send_card_message()` calls from other
# daemon subsystems.
```

## Observation 4 Telemetry

| Signal | Count |
|---|---:|
| `dispatcher_path_entry surface=adapter` | 3 |
| `dispatcher_path_exit surface=adapter` | 3 |
| `telegram_jarvis_block_state` (new diagnostic seam) | **0** |
| `actions.log` bytes added | 0 |
| SEGV / fatal Python error | 0 |

Dispatcher path fires (it's in `core/brain/brain_loop.py`, called from `skills.surface.maez_adapter`). Diagnostic seam doesn't fire (it's in `skills/telegram_voice.py`, no longer on the inbound path).

## The Actual Inbound Telegram Path

Traced via grep + Read of source files:

1. **Inbound message:** `skills/surface/telegram_adapter.py` (via `_should_process_message` → `platform_base._process_message_background`)
2. **Adapter routing:** `skills/surface/maez_adapter.py` (`MaezMessageHandler`)
3. **Brain loop call:** `maez_adapter.py:398-412` calls:
   ```python
   _result = await loop.run_in_executor(
       get_shared_executor(),
       lambda: _brain_loop.run_brain_loop(
           text,
           action_engine=action_engine,
           get_pipeline=get_pipeline,
           user_id="rohit",
           chat_id=chat_id,
           surface="adapter",
           send_intermediate=_send_intermediate,
           chat_history=chat_history,
           turn=turn,
           return_structured=True,
       ),
   )
   ```
   The dispatcher fires INSIDE `run_brain_loop` — this is where the `dispatcher_path_entry surface=adapter` telemetry comes from.
4. **Dispatcher transcript captured:** `maez_adapter.py:413-417`:
   ```python
   if hasattr(_result, "transcript"):
       jarvis_transcript = _result.transcript or ""
       jarvis_tool_calls = list(getattr(_result, "tool_calls", []) or [])
   ```
   `jarvis_transcript` IS the dispatcher's `RenderedTurn.prompt_block` (with `[memory evidence]` / `[fresh evidence]` markers).
5. **Final reply construction:** `maez_adapter.py:431-438` calls:
   ```python
   reply = await loop.run_in_executor(
       get_shared_executor(),
       lambda: self.daemon.handle_message(
           text,
           SURFACE_NAME,
           transcript=jarvis_transcript or "",
           chat_history=chat_history,
           tool_calls=jarvis_tool_calls or None,
   ```
6. **Owner-facing prompt assembled:** `daemon/maez_daemon.py:3407-3416`:
   ```python
   if transcript and transcript.strip():
       try:
           from core.brain_loop import _JARVIS_INSTRUCTION_BLOCK

           messages.append(
               {
                   "role": "system",
                   "content": (f"{transcript}\n\n{_JARVIS_INSTRUCTION_BLOCK}"),
               }
           )
   ```

**Step 6 is where Finding 10's actual fix needs to land.** The dispatcher's transcript reaches `daemon.handle_message`, which appends it to messages as `transcript + _JARVIS_INSTRUCTION_BLOCK`. The `_JARVIS_INSTRUCTION_BLOCK` is imported from `core.brain_loop` and contains the JARVIS-shaped vocabulary (✓/✗/⏳ tool semantics). That's what tells the model to treat `[memory evidence]` content as historical memory recall, not as this-turn substrate evidence.

## What Was Witnessed in Isolation vs. Live

| Layer | Unit test verdict | Live verdict |
|---|---|---|
| `core/dispatcher/*` (Layer 0, 1, 2, merge, ExternalFanout) | clean | **live: clean** (3 dispatcher turns per observation) |
| `core/brain/brain_loop.py` (dispatcher pipeline orchestration) | clean | **live: clean** (telemetry fires correctly) |
| `core/dispatcher/inventory.py` (Option A reserve fix at fd21828) | unit-clean | **live: clean** (Finding 8 fix held in observation 4) |
| `skills/telegram_voice.py` Pipeline A gate (Finding 9, 7cf9729) | unit-clean | **UNKNOWN — may also be in legacy code** |
| `skills/telegram_voice.py` dispatcher HARD INSTRUCTION (Option B, 7f078eb) | unit-clean | **DEAD CODE — not in inbound path** |
| `skills/telegram_voice.py` diagnostic seam (04ce41b) | unit-clean | **DEAD CODE — confirmed by zero log lines** |
| `daemon/maez_daemon.py` handle_message + `_JARVIS_INSTRUCTION_BLOCK` from `core.brain_loop` | (not yet tested) | **THIS IS WHERE FINDING 10 FIX MUST LAND** |

## Implications for Prior Findings

Three earlier "fixes" need re-verification at the live integration layer:

1. **Finding 9 / Option A gate** (commit 7cf9729) — the `_telegram_pipeline_a_web_search_enabled()` gate at `skills/telegram_voice.py:3367` may also be in legacy code that no longer fires. The "no `Web search triggered` in delta" verdict from observation 2 onward may have held for an unrelated reason (the legacy path simply isn't running anymore). Need to grep `skills/surface/` for any equivalent `needs_web_search` trigger before declaring Pipeline A truly gated.

2. **Finding 10 Option B** (commit 7f078eb) — confirmed dead-code by this witness. The dispatcher HARD INSTRUCTION at `skills/telegram_voice.py:3489+` never runs for inbound Telegram messages. The fix needs to be re-applied at `daemon/maez_daemon.py:3407-3416` or at `core/brain_loop.py:_JARVIS_INSTRUCTION_BLOCK`.

3. **Diagnostic seam** (commit 04ce41b) — confirmed dead-code by zero observation 4 fires. A re-located diagnostic at `daemon/maez_daemon.py:3407` (recording the shape of `transcript` and which instruction block gets appended) would actually fire on every inbound turn.

## Discipline Failure Shape

This is the third application of the canon-governs-canon witness discipline within the slice arc, and the most severe:

- **Finding 8:** unit tests passed at inventory.py level; brain_loop.py bypassed the registry. Fixed at 6520f67 by routing through registry.
- **Observation 2 → Finding 10:** Option B's static code trace was correct for `skills/telegram_voice.py`; live observation showed owner-facing reply unchanged.
- **Observation 4 (this one):** Diagnostic seam confirmed Option B's code never ran. The "static trace" diagnostic in Finding 10's diagnostic witness (e4ee0d2) was tracing a code path that hasn't received inbound messages since 2026-04-20.

The pattern: **static code traces are valid for the file they trace, but say nothing about whether that file is on the active integration path.** The unit-test-vs-integration discipline at `feedback-unit-test-is-not-integration-witness` (committed earlier this session) applies recursively to static traces too. Reading the code is necessary but not sufficient; the integration witness has to confirm the code is reached.

This will need a third memory canon update: **static-code-trace-is-not-integration-witness either**. Reading a file's logic doesn't prove the file is in the runtime path.

## Required Next Action

**Re-locate the Finding 10 fix to the actual prompt-construction site.**

**Where:** `daemon/maez_daemon.py:3407-3416` (specifically the `messages.append({"role": "system", ...})` that combines `transcript` + `_JARVIS_INSTRUCTION_BLOCK`) AND/OR `core/brain_loop.py:_JARVIS_INSTRUCTION_BLOCK` (the source of the JARVIS-shaped wrapper).

**Shape:** the same Option B logic — detect whether `transcript` is dispatcher-shaped (contains `[memory evidence]` / `[fresh evidence]` / `[memory context]` / `[no fresh evidence available:` / `[dispatcher refusal:`) and use a dispatcher-specific instruction block; fall through to `_JARVIS_INSTRUCTION_BLOCK` for non-dispatcher transcripts.

**Two reasonable placements:**

- **A. At daemon.handle_message** (line 3407-3416): the dispatch helper lives here, the choice between dispatcher-instruction and JARVIS-instruction is made at the prompt-assembly site. Smaller change, single insertion point.
- **B. At core.brain_loop**: rename `_JARVIS_INSTRUCTION_BLOCK` to a function `_instruction_block_for(transcript)` that returns dispatcher-shaped or JARVIS-shaped based on the transcript. Centralized — anyone importing this gets the right block.

Recommend B: the discipline of "the instruction block should match the transcript shape" is a property of the transcript, not of any particular caller. Centralizing it in `core.brain_loop` means any future surface that calls `run_brain_loop` and reuses `_JARVIS_INSTRUCTION_BLOCK` automatically gets correct behavior without re-implementing the dispatch.

**Re-locate the diagnostic seam to the same site.** Log `transcript_state=<dispatcher|jarvis|empty>` and `transcript_prefix=<first 100 chars>` at the prompt-assembly site in `daemon.handle_message`. Then the next observation will definitively prove whether the relocated fix reaches the model.

**Verify Finding 9 / Option A gate.** Search `skills/surface/` for any `needs_web_search` or equivalent parallel-pipeline trigger that might still be firing for inbound messages. If found, gate it identically.

## Surface Verdicts

| Surface | Verdict |
|---|---|
| Dispatcher pipeline (Layer 0/1/2/merge/ExternalFanout) | **CLOSED** — still honest at the dispatcher layer |
| Finding 8 reserve-classification live | **CLOSED** — Layer 0 emission via integrated InventoryRegistry holds |
| Finding 9 Pipeline A gate | **UNVERIFIED — may have been dead-code all along** |
| Option B dispatcher HARD INSTRUCTION at telegram_voice.py:3489+ | **DEAD CODE — never executes for inbound Telegram** |
| Diagnostic seam at telegram_voice.py:3655 | **DEAD CODE — confirmed by zero observation 4 fires** |
| Finding 10 closure | **STILL OPEN at the correct location: daemon.handle_message + core.brain_loop._JARVIS_INSTRUCTION_BLOCK** |
| SEGV trap | **HOLDING** |

## Witness Caveats

The dispatcher pipeline DOES work correctly on the live path. The transcript IS being passed through to `daemon.handle_message`. The only failure is that the JARVIS-shaped instruction block at `core.brain_loop._JARVIS_INSTRUCTION_BLOCK` wraps the dispatcher transcript with rules that tell the model not to use it. So when the fix re-lands at the correct location, Finding 10 should actually close.

But: per the discipline this slice arc has been making visible, **no claim of closure is valid until live observation confirms it**. The next move is the fix at the correct location, then observation 5.
