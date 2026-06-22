# Witness — Continuity-Synthesis Root Cause (2026-05-30)

**Posture:** live, in-process + flag-on Telegram witness (PID 111664, flags launch-env only,
`config/.env` untouched). Temporary privacy-clean instrumentation (`continuity_witness`
log: kind / ch_len / anchor count / ws built|None / per-entry speaker-prefix+parse-bool —
**no message bodies**) reverted after the witness; daemon restored flag-off under the unit.

## Question
The living-recall merge (`1ef70a5`) left continuity-synthesis as the named default-on blocker:
a continuity ask cited stale memory instead of the recent thread. Pin the exact cause
*before* designing a fix (Rohit: "re-witness first / witness before claim").

## What the 05-29 logs suggested (and why it was incomplete)
`logs/maez.log` (2026-05-29) showed `focused_cognition_skip reason=continuity_no_dialogue_anchor`
on every continuity probe → `assemble_working_set` returned `None` (focused_cognition.py:408,
`needs_dialogue and not anchors`) → daemon fell to the **legacy megaprompt** (maez_daemon.py:3945)
→ stale citation. Hypothesis: empty anchors. **But** the same strict anchor path
(`_clean_exchange → _split_exchange → dialogue_anchor_items`) run on *today's* live history
yields 3 good anchors — it did **not** reproduce. So empty-anchor was not the whole story.

## Live root cause (CONFIRMED, witness-grade)
The **continuity intent classifier** `dialogue_continuity_state` uses brittle hardcoded
substring patterns. Natural phrasings miss:

| Probe | `kind` | working set used | reply |
|---|---|---|---|
| "What were we **just** talking about?" (×3) | `none` | `memory_context`/`memory_evidence` (NO anchor) | stale / "I don't know" |
| "What were we talking about **earlier**?" (×2) | `direct` | **`dialogue_anchor`** (sole `[E1]`) | correct recap of prior turn |

`"just"` breaks the literal substring `"what were we talking about"`; `"what were we just
discussing?"` matches nothing; yet `"what did we just discuss"` *is* a pattern (inconsistent).
When `kind=none`, `needs_dialogue=False` → `assemble_working_set` never builds the anchor as
authoritative → focused cognition synthesizes over whatever memory evidence is present (the
stale "I'm not sure" rows + hardware health check). The brain answered honestly ("I don't
know") — it simply never received the dialogue anchor.

**The anchor path is mechanically sound.** Every `kind=direct` turn produced
`focused_cognition_prompt_shape … evidence_item_count=1, source_types="dialogue_anchor"` — the
anchor became the sole `[E1]` and synthesis used it. Clean confirmation (08:24): substantive
turn (infra-ground-truth) → then DIRECT probe → Maez correctly recapped *"we were trying to pin
down the infrastructure ground-truth … fabrication-class incident."*

## Findings
1. **PRIMARY (the fix):** `dialogue_continuity_state` brittleness — literal substring patterns
   miss natural continuity phrasings (`just`, `discussing`, word-order/filler variants) →
   `kind=none` → no anchor authority → stale synthesis. Live-reproducible.
2. **DIRECT path verified working:** classifier fires → anchor sole `[E1]` → faithful recap.
3. **SECONDARY (quality, edge):** `anchors[:1]` selects the single most-recent exchange even if
   that turn was itself a meta/continuity non-answer → cascades a prior non-answer. Observed when
   two failed continuity probes preceded a DIRECT one. Not the headline.
4. **TERTIARY (05-29 mode):** when classifier *does* fire DIRECT but no prior exchange is stored
   yet (fresh window), anchors are empty → `skip → legacy → stale`. Not reproduced today
   (history populated); a robustness gap (silent megaprompt fallback) worth closing.

## Fix scope (for the spec)
- **Primary:** robustify continuity intent detection so natural phrasings classify correctly.
  RED tests = the live-failing phrasings ("what were we just talking about", "what were we just
  discussing", filler/word-order variants).
- **Consider (secondary/tertiary):** substantive-anchor selection (skip meta turns); and on
  DIRECT-but-empty-anchor, prefer the adapter's resolved anchor over silent megaprompt fallback.
- Approach (deterministic-robust vs LLM-assisted vs hybrid) is an open design decision — see
  `[[feedback_brain_is_one_part_tool_calling_substrate_side]]` (intent classification is
  substrate-side and may learn from outcomes; must not bind to brain function-call grammar).

## Files
- `core/routing/focused_cognition.py` — `dialogue_continuity_state` (147–274), patterns
  (`_DIRECT_CONTINUITY_PATTERNS` 161, `_ANAPHORIC_*`), `assemble_working_set` (382), anchor
  selection `anchors[:1]` (406), `dialogue_anchor_items` (282).
- `core/brain/brain_loop.py` — `_continuity_needs_dialogue_anchor` (277), free-text anchor
  injection (383) [the loose extractor that diverges from the strict one].
- `daemon/maez_daemon.py` — synthesis call + skip→legacy (3939–3953).
