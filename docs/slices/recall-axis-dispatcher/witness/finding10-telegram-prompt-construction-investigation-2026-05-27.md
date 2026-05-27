# Finding 10 Investigation — Telegram Prompt Construction Conflicts With Dispatcher Output

**Status:** diagnostic witness, no code change. Decision required before fix.
**Date:** 2026-05-27
**Predecessor witness:** `docs/slices/recall-axis-dispatcher/witness/external-source-observation-2-2026-05-27-telegram.md` (commit 6f810e6)
**Investigation method:** static code trace of `_run_jarvis_loop` return path through Telegram's reply-construction code.

## Headline Finding

**Hypothesis B confirmed.** The dispatcher's `RenderedTurn.prompt_block` IS being inserted into the LLM's prompt as `jarvis_block` at `skills/telegram_voice.py:3489-3492`. But the surrounding HARD INSTRUCTION block (lines 3493-3565) is **JARVIS-shaped** — designed for `action_engine`'s tool-call semantics with ✓/✗/⏳ markers — and its rules **actively forbid** the model from using the dispatcher's substrate evidence as current-turn material.

**The specific load-bearing rule:** HARD INSTRUCTION Rule 4 at lines 3546-3552:

> "Memory recall blocks (the [RECALLED MEMORY] section earlier in this prompt) are history about the past. They are NOT a record of what you did this turn. Never attribute their contents to this turn."

The dispatcher's `[memory evidence]` / `[memory context]` markers (which are EXACTLY the dispatcher's SUBSTRATE_ONLY framing output, and also HYBRID-framing substrate role) match the shape Rule 4 calls "memory recall blocks." So when the dispatcher provides Reddit substrate rows for `What's new on Reddit lately?`, the HARD INSTRUCTION instructs the model to treat that content as "history about the past, NOT this turn." Result: the model denies having memory access and tells the owner to trigger a search.

**Compound issue:** the HARD INSTRUCTION's tool vocabulary (✓/✗/⏳ tool calls, cards, "the action ran") does not match the dispatcher's vocabulary (`[fresh evidence]`, `[memory context]`, `[no fresh evidence available]`, `[dispatcher refusal]`). The model, reading rules about ✓-line tool execution and not finding any in the dispatcher transcript, concludes no tools ran — and then fabricates plausible-sounding alternative architectural descriptions ("Reddit signal pipeline", "DuckDuckGo tool loop", "Telegram interceptor") to explain why expected tool patterns are absent.

## Code Evidence

**Branch point** at `skills/telegram_voice.py:3489`:

```python
final_user = user_text
if jarvis_block:
    final_user = (
        f"{user_text}\n\n"
        f"{jarvis_block}\n\n"
        "HARD INSTRUCTION — read this before writing a single word of your reply:\n"
        ...
    )
else:
    # TURN STATE — NO TOOLS RAN THIS TURN
    final_user = (...)
```

Two prompt shapes:
- **`jarvis_block` non-empty:** JARVIS-shaped HARD INSTRUCTION (lines 3489-3565) — 75+ lines of rules about ✓/✗/⏳ tool-call semantics, cards, "the action ran," etc.
- **`jarvis_block` empty:** `[TURN STATE — NO TOOLS RAN THIS TURN]` block (lines 3583+) — different framing for non-action turns.

**Dispatcher's `RenderedTurn.prompt_block` content shapes** (from `core/dispatcher/merge.py` + `provenance_renderer.py`):

- `[memory evidence] Recent Reddit substrate rows: ...` — SUBSTRATE_EVIDENCE role
- `[memory context] ...` — SUBSTRATE_CONTEXT role (HYBRID framing)
- `[fresh evidence] ...` — FRESH_EVIDENCE role
- `[no fresh evidence available: ...]` — FRESH_ONLY total-failure deterministic summary
- `[dispatcher refusal: ...]` — closed-vocab refusal

None of these match the JARVIS HARD INSTRUCTION's ✓/✗/⏳ vocabulary.

## The Specific Mismatches

### Rule 1: "the only actions, tools, commands, packages, files, websites, or results you are allowed to mention..."

The dispatcher's content is **memory and external-source evidence**, not "actions, tools, commands, packages, files, websites, or results." The category mismatch means the model reading Rule 1 doesn't recognize the dispatcher's content as legitimate prompt-shaping material.

### Rule 2: "✓ line — the tool RAN... ✗ line — the tool call was REJECTED... ⏳ CARD_CREATED line — a proposal was sent..."

The dispatcher's transcript has none of these markers. The model reading Rule 2 looks for ✓/✗/⏳ patterns, finds none, and effectively reads the dispatcher block as "transcript with no tool entries."

### Rule 4 (the most load-bearing): "Memory recall blocks (the [RECALLED MEMORY] section earlier in this prompt) are history about the past. They are NOT a record of what you did this turn. Never attribute their contents to this turn."

The dispatcher's `[memory evidence]` / `[memory context]` markers match the conceptual shape of "memory recall blocks." Rule 4 explicitly forbids treating that content as this-turn material. So when the dispatcher provides Reddit substrate for "What's new on Reddit lately?" — content that IS this-turn evidence emitted by the dispatcher's substrate fan-out — the HARD INSTRUCTION tells the model to ignore it.

### Rule 5: "If the transcript is empty, say you haven't checked yet this turn. Do not pretend you did."

Because Rules 1, 2, and 4 effectively erase the dispatcher's content from the model's view of valid this-turn material, Rule 5 applies: the model says "I haven't checked yet this turn" → "I cannot perform that search."

## Why The Fabrication Happens

The HARD INSTRUCTION's vocabulary primes the model toward "tool loop / web_search / action engine" mental model. When asked about Reddit, the model:

1. Reads the HARD INSTRUCTION's tool-semantic rules.
2. Looks for ✓/✗/⏳ tool entries in the transcript — finds none.
3. Concludes no tool ran this turn (per Rules 2, 5).
4. Now needs to explain WHY no tool ran in a way that sounds plausible.
5. Generates from training-data patterns: "Reddit signal pipeline broken," "DuckDuckGo tool loop," "Telegram interceptor" — all plausible-sounding internal-architecture descriptions that don't match Maez's actual code.

This is the no-fabrication discipline being violated by Maez itself — but it's downstream of the HARD INSTRUCTION's vocabulary mismatch. The prompt invites the model to explain absence-of-tool-call, and the model invents architecturally-shaped reasons.

## Classification

| Hypothesis | Result |
|---|---|
| A. RenderedTurn.prompt_block constructed but not inserted | **REJECTED** — `jarvis_block` IS the dispatcher's prompt_block; it IS inserted at line 3492 |
| B. Inserted but overridden by system-prompt priming | **CONFIRMED** — HARD INSTRUCTION block at lines 3493-3565 explicitly forbids using `[memory evidence]` / `[memory context]` content as this-turn material |
| C. Inserted at wrong position | **REJECTED** — the position (LAST in the prompt, right before reply generation) is what telegram_voice.py:3479-3487 specifically chose to fix a prior fabrication issue |
| D. Third Telegram pipeline constructs reply without consulting dispatcher output | **REJECTED** — there is one final-user-prompt construction, and the dispatcher's transcript IS in it |

## Decision Options

### Option A — Add dispatcher-aware vocabulary to the HARD INSTRUCTION

Extend the HARD INSTRUCTION block with rules specifically about dispatcher markers:

- "`[memory evidence]` / `[memory context]` lines emitted by the dispatcher ARE this-turn substrate evidence, not historical memory recall. Cite their content as your current grounding."
- "`[fresh evidence]` lines emitted by the dispatcher ARE this-turn live-fetched data. Treat them as if a search just succeeded for this turn."
- "`[no fresh evidence available: ...]` is the dispatcher's honest declaration that fresh fetch failed. Say what was attempted and what failed, using the closed-vocab labels in the marker."
- Rule 4 amended to distinguish "[RECALLED MEMORY]" (historical, pre-turn) from "[memory evidence]" / "[memory context]" (dispatcher-emitted this-turn evidence).

**Pros:**
- Smallest patch. Adds rules; doesn't remove the JARVIS rules.
- Both surfaces (action_engine tool calls AND dispatcher evidence) get instruction surface.
- Reversible.

**Cons:**
- HARD INSTRUCTION grows; future maintainers must keep both vocabularies in sync.
- Dual-vocabulary instruction block has higher cognitive load for the model and for code review.
- Rule 4's amendment is subtle and might not pin clearly enough.

### Option B — Build dispatcher-shaped HARD INSTRUCTION as a separate branch

Detect whether `jarvis_block` is dispatcher-shaped (contains `[memory evidence]` / `[memory context]` / `[fresh evidence]` / `[no fresh evidence available]` / `[dispatcher refusal]` markers) or JARVIS-shaped (contains ✓/✗/⏳). Use entirely separate HARD INSTRUCTION blocks for each:

- Dispatcher-shaped → dispatcher-specific rules (read substrate as current grounding, read fresh evidence as just-fetched data, treat refusals as honest dispatcher state, etc.)
- JARVIS-shaped → existing HARD INSTRUCTION unchanged.

**Pros:**
- Cleaner architectural separation. The two systems are genuinely different (evidence-provider vs tool-runner) and deserve distinct instruction language.
- The dispatcher rules can lean into closed-vocabulary precision; the JARVIS rules can stay as-is.
- Future dispatcher v2 evolution doesn't have to touch the JARVIS rules.

**Cons:**
- Detection logic adds branching. The two prompt blocks must both stay aligned with their respective system's vocabulary as those systems evolve.
- More code surface than Option A.

### Option C — Have the merge owner produce JARVIS-shaped output

Convert dispatcher markers into JARVIS vocabulary at the merge boundary: `[fresh evidence] r/Python: ...` becomes `✓ live_reddit: r/Python ...`; `[memory evidence] ...` becomes `✓ memory_recall: ...`; etc.

**Pros:**
- The HARD INSTRUCTION stays unchanged.
- Single vocabulary at the LLM surface.

**Cons:**
- Loses the dispatcher's closed-vocabulary semantics — `[fresh evidence]` vs `[memory context]` is the producer-causality discipline made visible, and translating to ✓-line erases that.
- Closes the slice arc's investment in honest provenance-marker rendering.
- Distorts the dispatcher's audit story to fit JARVIS's tool story.

### Option D — Detect dispatcher-shaped jarvis_block and use minimal instruction

When `jarvis_block` is dispatcher-shaped, skip the full HARD INSTRUCTION and use only a minimal "respond based on the evidence above, using the markers as-shown" instruction. Rely on the dispatcher's own marker semantics to carry meaning.

**Pros:**
- Smallest LLM-facing prompt for the dispatcher path.
- Trusts the dispatcher's existing closed-vocabulary discipline to do its job.

**Cons:**
- Loses anti-fabrication guardrails that the HARD INSTRUCTION carries (forbidden phrasings, anti-deflection, etc.).
- Risk of regression on adjacent behavior (refusals reading as confusion, etc.).

## Recommended Path

**Option B (separate dispatcher HARD INSTRUCTION) is the architecturally honest move.** The dispatcher and the JARVIS tool loop are different systems with different semantics. Trying to retrofit one's instruction language to cover the other produces the exact failure mode Finding 10 surfaces.

Option A is the smaller patch and is reasonable as a faster fix if the architectural distinction can wait. But long-term, Option B is the cleaner separation.

Both options should preserve:
- The anti-fabrication rules (Rule 3's "PARTIAL-ACTION TRAP" and the forbidden-phrasings list at lines 3622+ are load-bearing for not-just-this-issue)
- The structure that puts evidence AT THE END of the prompt (line 3479-3487 documents why this matters)
- The "no_tools_ran" branch for genuinely tool-less turns

**The dispatcher-shaped HARD INSTRUCTION should include rules like:**

1. **Marker vocabulary:** "The transcript above uses these markers. Each marker means a specific thing about WHAT this turn already produced:
   - `[memory evidence]` — substrate recall returned content for this turn. This IS what you found. Cite it directly.
   - `[memory context]` — substrate recall returned content as context for fresh evidence. This is real, but the fresh evidence is the headline.
   - `[fresh evidence]` — live fetch succeeded for this turn. Report what you fetched as if a search just succeeded (because it did).
   - `[no fresh evidence available: <SOURCE>:<STATUS>:<CLASS>:<LIMITATION>]` — fresh fetch was attempted and failed. Tell the owner what was tried and what the closed-vocab failure label was. Do not pretend the fetch succeeded.
   - `[dispatcher refusal: <REASON>]` — the dispatcher refused this turn. Report the refusal reason honestly. Do not bypass."

2. **This-turn semantics:** "Content under any of these markers is the result of THIS turn's substrate + external fan-out. Treat it as current grounding for your reply. The 'memory recall is history' rule from JARVIS contexts does NOT apply to dispatcher-emitted memory evidence."

3. **No-architecture-fabrication:** "If the dispatcher emitted no relevant evidence, say so plainly. Do not invent internal-architecture descriptions ('Reddit signal pipeline', 'tool loop', 'interceptor', etc.) to explain absence."

4. **Closed vocabulary discipline:** "When citing failure reasons, use the closed-vocab labels in the marker (e.g., 'AUTH_DENIED', 'SOURCE_TIMEOUT', 'FRESH_ATTEMPT_FAILED'). Do not paraphrase."

## What Stays Out of This Investigation

- **Whether `recall_for_telegram` substrate-recall at telegram_voice.py:3347 duplicates the dispatcher's Layer 1 work.** It does (Pipeline A still calls `recall_for_telegram` separately), but that's a separate optimization, not the cause of Finding 10.
- **Whether the LoRA fine-tune is also contributing.** Comment at line 3574 mentions "v3 (after live tests): v2 was too prescriptive and the LoRA pattern-matched on a specific example phrase..." The LoRA's behavior interacts with the prompt construction, but the root cause is the vocabulary mismatch, not the LoRA per se.
- **Pipeline A's `recall_for_telegram` + `format_for_prompt` substrate output earlier in the prompt.** That's separate substrate context; the dispatcher's transcript appearance at line 3492 is the seam Finding 10 is about.
- **The "no_tools_ran" branch's correctness.** That branch fires when `jarvis_block` is empty, which shouldn't happen under dispatcher-enabled — but if it does, that's a separate path.

## Verdict

Finding 10 is **a prompt-construction vocabulary mismatch between the JARVIS HARD INSTRUCTION and the dispatcher's `RenderedTurn` output**. The dispatcher's transcript IS in the LLM's prompt; the surrounding instructions tell the model not to use it.

The fix is in the Telegram surface code (telegram_voice.py:3489-3565), not in the dispatcher pipeline. The dispatcher's work is honest; the prompt scaffolding around it is JARVIS-shaped and needs dispatcher-aware vocabulary.

Rohit's decision on Options A/B/C/D drives the next move. Option B (separate dispatcher HARD INSTRUCTION block) is recommended as the architecturally honest move. Option A is acceptable as a smaller faster patch if Option B is deferred.
