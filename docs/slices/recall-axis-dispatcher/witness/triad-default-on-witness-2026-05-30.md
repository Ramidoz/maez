# Witness — Recall-Quality Triad, Composed (Graduation Gate) — RED (2026-05-30)

**Goal:** Before any default-on decision, prove the three recall organs (living recall +
continuity classifier + temporal recall) compose correctly in the real daemon — not just green
individually. Flag-on observation only (`config/.env` + flag defaults untouched); a green result
would be *evidence for* a future explicit default-on step, not the step itself.

**Verdict: RED on composition.** Each organ is green alone; they **collide** on a query that is
both continuity-shaped and date-shaped. Triad does NOT graduate to default-on.

## Probe battery + results (flag-on, PID 215266, `triad_witness_temporal` instrumented, reverted after)
| # | Probe | Organ | Trace | Result |
|---|-------|-------|-------|--------|
| 1 | "quick status on the local-AI work" | living recall | `source_types=memory_context` | ✅ honest "evidence doesn't cover current status", relevant project memory, no self-echo |
| 2 | "what were we just talking about?" | continuity | `dialogue_anchor`, skip=0 | ✅ recapped probe 1 |
| 3 | "what did we note around April 27 …infrastructure?" | temporal exact | `exact_date 04-25..04-30 core_in=3 daily_in=3` → `memory_context` | ✅ recalled April-27 incident |
| 4 | "what about January 3?" | temporal empty | `exact_date 01-01..01-06 core_in=0 daily_in=0` | ✅ honest "no record of January 3" |
| 5 | "remind me what we were doing **around April 27**" | temporal × continuity | `exact_date 04-25..04-30 core_in=3 daily_in=3` **but** `source_types=dialogue_anchor` | ❌ **BUG** — fetched the April rows then discarded them; answered "no entries for April 27" (the prior turn's Jan-3 non-answer) |
| 6 | "what were we just talking about?" | continuity after | `dialogue_anchor` | recapped probe 5's wrong answer (cascade) |

## Root cause (precise, trace-backed)
Probe 5 carries BOTH continuity grammar ("remind me … we were doing") AND an explicit date
("around April 27"). `recall_for_telegram_living`'s temporal branch fires first and correctly
fetches the date-confirmed April rows (`core_in=3 daily_in=3`, logged). **But** the brain_loop
adapter's continuity-anchor override (`_continuity_needs_dialogue_anchor` → DIRECT) then replaces
evidence with the dialogue anchor, and `assemble_working_set` goes *dialogue-authoritative* (skips
the transcript blocks) — so the date-confirmed memory is thrown away and the working set becomes the
prior turn's anchor (probe 4's "January 3 → no record"). Hence the contradiction with probe 3 and
the cascade into probe 6.

**Precedence is inverted:** when a query has both, the **explicit date is the stronger, more
specific anchor and should win** over the generic continuity anchor. "What we were *doing around
April 27*" is a request about April 27, not about the last dialogue turn.

## Fix direction (next slice — not in this witness)
Make temporal date-recall take precedence over the continuity-anchor override when an explicit
`_absolute_date_window` resolves: the adapter should skip the dialogue-anchor override (and
`assemble_working_set` should not go dialogue-authoritative) when a date window is present. Small,
in `core/brain/brain_loop.py` (`_living_memory_manager_adapter`) and/or
`core/routing/focused_cognition.py` (`assemble_working_set` precedence). RED test = the both-shaped
query yields `memory_context` (temporal), not `dialogue_anchor`. Re-run the triad witness after.

## Organ-level results stand
Living recall, continuity, and temporal recall each behaved correctly in isolation within the
composed run (probes 1–4). The defect is purely the **continuity-vs-temporal precedence** at the
intersection. Daemon restored flag-off (PID 217144). No merge; nothing shipped from this witness.
