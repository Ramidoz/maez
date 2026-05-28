# External-Source Observation Window 3 — Telegram — 2026-05-27 — FAILED

**Slice:** Recall-Axis Dispatcher external-source consumption, post Option B Finding 10 fix
**Git HEAD at flip:** `7f078eb` (`fix(dispatcher): branch telegram prompt instructions by transcript shape`)
**Predecessor witness:** `docs/slices/recall-axis-dispatcher/witness/external-source-observation-2-2026-05-27-telegram.md` (commit 6f810e6) + `finding10-telegram-prompt-construction-investigation-2026-05-27.md` (commit e4ee0d2)
**Service:** `systemctl --user maez.service`, Telegram adapter surface
**Window opened:** 2026-05-27T18:34:53-05:00
**Window closed:** 2026-05-27T20:29:36-05:00 (owner closed after witnessing failure)
**Note:** maez.log rotated during observation; dispatcher delta extracted from `maez.log.1` (offset 51644886 onward).

## Verdict

**FAILED at the owner-facing layer.** Option B was correct in isolation (unit tests pass; dispatch helper routes by marker shape; dispatcher HARD INSTRUCTION rules explicitly forbid the Finding-10 fabrications) but the live observation shows the same fabrication shape recurring on Telegram replies — including phrases ("Telegram interceptor", "Reddit signal fetcher", "chat interface", "pre-fetch results", "signals are not persisting to memory") that Rule 5 of the new dispatcher HARD INSTRUCTION explicitly bans.

**Same failure-mode shape as Finding 8:** unit tests passed, live integration didn't change. The discipline named in `feedback-unit-test-is-not-integration-witness` applies recursively — Option B's tests verified the prompt branching at the helper level, but no direct witness was captured of what `jarvis_block` actually contained at the call site `telegram_voice.py:3638`, or whether the new prompt actually reached the model.

## Dispatcher Telemetry (from maez.log.1 delta)

Five dispatcher turns over the observation window. Telemetry confirms the dispatcher pipeline ran correctly for every turn — substrate rows returned, LIVE_REDDIT fetched, B3 truncation fired when applicable:

| Turn timestamp | Layer 0 | Layer 1 | External | turn_seal_state |
|---|---|---|---|---|
| 19:46:37 | PARALLEL + HYBRID; substrate=1, external=1 | REDDIT_SOURCE rows=1 | **LIVE_REDDIT rows block_count=1 elapsed_ms=694.945** | clean |
| 19:48:02 | SUBSTRATE_ONLY; substrate=1 | REDDIT_SOURCE rows=1 | branch_count=0 | clean |
| 20:00:07 | SUBSTRATE_ONLY; substrate=1 | TELEGRAM_SEMANTIC rows=1 (truncated 76949→1200) | branch_count=0 | clean |
| 20:01:59 | SUBSTRATE_ONLY; substrate=1 | REDDIT_SOURCE rows=1 | branch_count=0 | clean |
| 20:02:50 | SUBSTRATE_ONLY; substrate=1 | TELEGRAM_SEMANTIC rows=1 (truncated 75298→1200) | branch_count=0 | clean |

All five turns should have produced a `RenderedTurn.prompt_block` containing at least one of `[memory evidence]`, `[memory context]`, or `[fresh evidence]` markers — every one of which is in `DISPATCHER_TRANSCRIPT_MARKERS` and SHOULD route through `_telegram_dispatcher_hard_instruction()`.

`actions.log` delta: 0 bytes (Finding 9 fix still holds — Pipeline A web_search is gated).

## Owner-Facing Reply Behavior (from owner screenshot)

The owner-visible Telegram replies STILL contained:
- "Telegram interceptor"
- "Reddit signal fetcher"
- "chat interface"
- "pre-fetch results"
- "signals are not persisting to memory"

These are the same fabrication shape as Finding 10 (and overlap with the specific phrases Rule 5 of the new dispatcher HARD INSTRUCTION explicitly forbids):

```
"5. Forbidden fallback phrases for dispatcher turns:
   · 'I cannot perform that search'
   · 'I have no live web search tool'
   · 'the Reddit pipeline is broken'
   · 'the X pipeline is broken'
   · 'I am blind to Reddit'
   · 'trigger a Telegram interceptor'
   ..."
```

Maez also still told the owner to send a separate command to trigger a search — which is the same parallel-pipeline mental model the dispatcher slice was supposed to eliminate.

## Code Verification (in isolation)

The new Option B code IS present on disk and IS correct when called directly:

```text
$ grep -c "_telegram_dispatcher_hard_instruction\|DISPATCHER_TRANSCRIPT_MARKERS" skills/telegram_voice.py
4

$ .venv/bin/python -c "from skills import telegram_voice as tv; ..."
markers: ('[memory evidence]', '[memory context]', '[fresh evidence]', '[no fresh evidence available:', '[dispatcher refusal:')
dispatcher_shape('[memory evidence] foo'): True
dispatcher_shape('✓ tool ran'): False
which branch for dispatcher input: HARD INSTRUCTION — read this before writing a single word of
which branch for jarvis input: HARD INSTRUCTION — read this before writing a single word of
```

(Both branches start with the same "HARD INSTRUCTION" line, so the first 60 chars look identical — but the bodies are different, which the test suite verifies.)

The call site at `telegram_voice.py:3638-3643` correctly routes through `_telegram_hard_instruction_for_jarvis_block(jarvis_block)`. The dispatcher branch IS reachable from the production code path.

## Three Possible Causes (need diagnostic instrumentation to distinguish)

| Hypothesis | What it means | Test |
|---|---|---|
| H1. Daemon didn't load the new code | Restart at 18:34:53 should have re-imported the new file, but stale .pyc cache or systemd unit binding to an old Python interpreter could prevent it | Add telemetry that logs the value of a module-level sentinel constant added in the new code; any missing log line means the module didn't load |
| H2. Dispatcher-shape branch didn't fire | The new code is loaded but `jarvis_block` at the call site didn't actually contain the dispatcher markers — possibly the dispatcher's RenderedTurn.prompt_block was empty, post-processed, or replaced with something else by some intermediate code | Add telemetry that logs jarvis_block shape (dispatcher / jarvis / empty) + first 200 chars per turn |
| H3. New prompt fired but model ignored it | The dispatcher HARD INSTRUCTION reached the model's prompt, but the LoRA fine-tune (referenced at line 3652 commentary) or training-data fluency overrode the instruction and generated the fabrication anyway | After H1 and H2 are ruled in or out, this is the remaining hypothesis; investigating requires comparing the full final_user prompt to the model output, possibly with prompt-only A/B testing |

The previous fix (Option B) was based on diagnostic evidence that the JARVIS HARD INSTRUCTION was in the prompt and was overriding the dispatcher transcript. But that diagnostic was a STATIC code trace, not a live witness of what reached the model. Per `feedback-unit-test-is-not-integration-witness`, the static trace established necessary structure but did not prove sufficient runtime behavior change.

## Required Next Action

**Diagnostic telemetry seam.** Add narrow `logger.info` instrumentation at `telegram_voice.py:3638-3643` that records per dispatcher-enabled turn:

```python
logger.info(
    "telegram_prompt_construction surface=adapter chat_id=%s "
    "jarvis_block_state=%s jarvis_block_first_100=%r",
    chat_id,
    "dispatcher" if _telegram_jarvis_block_is_dispatcher_shaped(jarvis_block)
    else ("jarvis" if jarvis_block else "empty"),
    jarvis_block[:100] if jarvis_block else "",
)
```

This produces three observable signals per turn:
1. **jarvis_block_state** — definitively answers H1 (if no log line at all, module not loaded) and H2 (which branch fired)
2. **jarvis_block_first_100** — shows the actual prompt prefix (with markers if dispatcher-shaped)
3. **chat_id correlation** — lets us cross-reference with the dispatcher telemetry per turn

After this telemetry lands and observation 4 fires, the witness will definitively classify H1 vs H2. If both are ruled out, only H3 remains — which is a deeper investigation into LoRA priming or model-layer behavior.

**Scope of the telemetry seam:**
- Single-file change in `skills/telegram_voice.py`
- 1 logger.info call + import any needed helper
- RED test: assert the logger.info fires when jarvis_block is dispatcher-shaped; fires when jarvis-shaped; not fires (or fires with empty state) when empty
- No behavior change beyond logging

**Out of scope:**
- Any actual fix for Finding 10 — this is purely diagnostic. The fix follows the diagnosis.
- Modifying the dispatcher HARD INSTRUCTION content — Option B's content is correct in principle; the question is whether it reaches the model.
- Modifying the dispatcher pipeline — telemetry confirms the dispatcher is correct.

## Surface Verdicts

| Surface | Verdict | Witness |
|---|---|---|
| Dispatcher path on Telegram | **CLOSED (verified again)** | 5 `dispatcher_path_entry surface=adapter` events |
| Finding 8 reserve-classification live | **CLOSED** | zero `outcome=error` for ENTITY_INDEX/LIVED_EPISODES across all 5 turns |
| Finding 9 Pipeline A gate | **CLOSED** | zero `Web search triggered` in delta |
| B3 budget truncation | **CLOSED in observation** | 2 events with consistent shape |
| LIVE_REDDIT external fan-out | **CLOSED at dispatcher layer** | block_count=1 on probe 1 |
| Finding 10 closure at owner-facing layer | **STILL OPEN — Option B did not change owner-visible behavior** | screenshot shows fabrications matching Rule-5-forbidden phrases |
| H1 (code didn't load) | **UNDETERMINED** | needs telemetry |
| H2 (branch didn't fire) | **UNDETERMINED** | needs telemetry |
| H3 (model overrode prompt) | **UNDETERMINED until H1/H2 ruled out** | needs telemetry + further investigation |
| SEGV trap | **HOLDING** | preserved across all restarts; no recurrence |

## Recommendation

1. **Dispatch Codex on the diagnostic telemetry seam.** Small, witness-only, no behavior change.
2. **After telemetry lands, re-open observation 4** with the same probe corpus.
3. **Diagnose H1 vs H2 from the log delta.** If the telemetry shows jarvis_block_state=dispatcher with correct marker content but the owner-facing reply still fabricates, H3 is the live finding and the next investigation is at the model layer.
4. **Do not flip default flag.** Same as observation 2 — the dispatcher pipeline is honest, the owner-facing layer is not.

## Note on Discipline Recursion

This is the second time in the slice arc (Finding 8 was the first) that unit tests passed but live integration didn't change. The discipline in `feedback-unit-test-is-not-integration-witness` is now load-bearing for the slice arc — every "fix landed" claim needs an observation-window witness before being treated as closed.

Option B's tests cover the helper-level dispatch correctly. What they don't cover (and couldn't cover without integration test fixtures that mock the model layer) is the end-to-end path from dispatcher transcript → Telegram prompt → LLM call → owner-visible reply. The observation window IS that integration witness, and observation 3 surfaced the gap. This is the canon-governs-canon discipline working correctly — claims are checked against witness.
