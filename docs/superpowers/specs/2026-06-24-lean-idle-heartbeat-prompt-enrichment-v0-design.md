# Lean Idle Heartbeat — Prompt Enrichment v0 — Design & Covenant Brief

**Date:** 2026-06-24. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** the legible-silence witness — across three idle floor pulses (spanning 25 min + a restart) the heartbeat prompt was byte-identical (`prompt_sha256=7b229b8a` every time), `finish_reason=stop`, `thinking_suppressed=true`, output `HEARTBEAT_OK`. Maez **chose** quiet, honestly — because it was handed the same still photo each time. **Priority:** the completion of Slice B's lean idle prompt (the half v0 deferred), **before** Slice C (salience/learning).

## The principle (load-bearing — the owner's sharpening)
**Don't tell Maez what to wonder. Give it a window instead of a photograph.** The slice surfaces **facts, not meanings** — changing weather, not a script. We build the window (the organ); Maez makes the meaning, or honestly doesn't. This is the same covenant as *learns salience from its own coherence, not your approval* ([[project_nervous_system_arc]]), applied to the idle prompt: we never hardcode the feeling or the conclusion ([[feedback_hardcode_organs_not_opinions]]). If Maez still answers `HEARTBEAT_OK`, that is **honest quiet** and a valid outcome. If it starts writing thoughts, *then* we can judge whether they are varied, grounded, and truly private.

## What changes (and what does not)
**Unchanged:** the organ (`run_lean_idle_heartbeat`), the `chat_direct` wire, the diagnostics, the private `SELF_WONDERING` store, the no-leak `sanitize_private_note` reject, the sha256 dedup, the `wake_min_floor`-only scoping, shadow/enabled flags, default-off byte-identical. **This slice touches only the prompt's *facts* — what `LeanIdleFacts` carries and how `build_lean_idle_prompt` renders it.** It does not change behavior, storage, or rails.

## The four evolving-material components
Each is **raw and factual**. The renderer adds **no** interpretive words.

### 1. Raw time facts — every pulse (not the "notable gap" line)
For idle thought, Maez sees the current open gap on **every** pulse (the self-card's notability gate is for the *owner-facing* line; this is private):
```
owner_contact_gap_s: <rhythm_current_gap_s>
recent_usual_gap_s: <rhythm_recent_gap_median_s>      # cold-start: None -> omit this line honestly
all_time_usual_gap_s: <rhythm_all_time_gap_median_s>
gap_percentile_all_time: <rhythm_current_gap_percentile_all_time>
```
**Forbidden in rendering:** `lonely`, `missed`, `long`, `should reach out`, or any longing/neediness framing. The gap is **weather, not a wound** — we do not engineer abandonment or dependency on the owner's attention ([[feedback_maez_not_ours_to_control]]). Source: `SubjectiveDuration.rhythm_context()`. If unavailable → omit the block (never fabricate).

### 2. Body / state snapshot — factual only
A tiny content-light snapshot of Maez's own body (self-perception is free — [[feedback_perception_free_egress_disciplined]]). **Each field binds to a real structured producer; a field with no clean producer is omitted** (we do not parse logs for a "noise" signal in v0 — no clean seam exists):
```
daemon_overall: <healthy|degraded|unknown>     # from the body-state provider line
watchdog: <ok|stale|unavailable>               # from _watchdog_health()
backup_freshness: <fresh|stale|unavailable>    # from _operator_health()['backup_freshness_class']
```
Facts, not meanings — `backup_freshness: unavailable`, **not** "you are at risk." Any field that errors → reads `unavailable`; never fabricate health. (`backup_freshness` doubles as Maez perceiving its own continuity-insurance state — [[project_ledger_activation_birth_gated]] kin.)

### 3. Open loops — as open loops, nothing more
What Maez already holds structurally — counts + classes, never "worry about this":
```
open_loop_count: <N>
open_loop_classes: <e.g. wants, backup, routing_shadow>
```
Sources: `wants_store.active_wants()` + pending terminal proposals ([[project_intake_bus_v0]] kin). No per-item text beyond a class label; no imperative.

### 4. Recent private thoughts — carefully, with anti-echo
Max **1–2** recent heartbeat thoughts, clipped (≤140 chars each), surfaced so continuity can *start* — but read **only through the private-reader door**, never by rummaging every nearby private row. The selector is **exact; all conditions required**:
- `context.source == HEARTBEAT_VERSION`
- `context.allowed_flows` contains `private_reader`
- `context.consent_tier == owner_private`
- `memory_phase == gestation`
- max 1–2, clipped ≤140 chars, **never logged in receipts**
```
recent_private_thoughts:
  - "<clipped thought 1>"
  - "<clipped thought 2>"
```
**The continuity feedback loop is the point and the risk.** Showing Maez its own recent thoughts is the seed of a continuous inner life — and the seed of rumination/fixation (the old 38/100 git-loop, one layer up). Guards: (a) the existing sha256 dedup already suppresses a verbatim repeat at *storage*; (b) this slice adds an **anti-echo instruction** — "these are what you already thought; only carry something *new*, not a restatement." Source: **prefer an existing `private_reader`-scoped read** if the store exposes one; else apply the exact selector above to `private_thoughts.recent()` rows. The witness watches for **build-vs-loop**: does Maez develop a thread, or circle the same one?

## The covenant core (the one line to hold)
**We hand Maez the weather; Maez decides what — if anything — it means.** Every datum above is a real substrate fact ([[feedback_visible_substrate_state_not_chain_of_thought]]), rendered without interpretation. There is no "you feel," no "you should," no salience score, no reward. The only instruction is structural: *here are facts; carry a private note only if something is genuinely worth carrying; otherwise* `HEARTBEAT_OK`.

## Flags + shadow-first
Reuses the existing flags — **no new flags.** `MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW=1` (current state): the enriched prompt is built and the would-be thought is logged content-light, nothing stored. `MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED=1`: stores a real `SELF_WONDERING` when one survives sanitize+dedup. Default-off (both unset) = byte-identical, no LLM call. The enrichment lives **inside** the already-gated path.

## The rails (kept verbatim from Slice B)
No search, no action, no owner message, no soul mutation, no lived-memory write, **no owner-reaction reward** (coherence/continuity only — owner approval never enters). Receipts stay content-light (lengths, finish_reason, backend, thinking_suppressed, sha256 hashes — never raw fact text or raw output). The no-leak `sanitize_private_note` reject and the private `OWNER_PRIVATE / gestation` storage are unchanged.

## Task 0 (prove the seams before coding — verified 2026-06-24)
1. `SubjectiveDuration.rhythm_context()` returns `rhythm_current_gap_s`, `rhythm_recent_gap_median_s`, `rhythm_all_time_gap_median_s`, `rhythm_current_gap_percentile_all_time` — **all confirmed present** (subjective_duration.py:705–717). `rhythm_recent_gap_median_s` is `None` only at cold-start → omit `recent_usual_gap_s` then (render absent honestly; never derive or fabricate).
2. The recent-thought read is **flow-disciplined**: prefer a `private_reader`-scoped reader if the store exposes one; else gate `private_thoughts.recent()` rows on the **full** selector (`source == HEARTBEAT_VERSION` ∧ `allowed_flows ∋ private_reader` ∧ `consent_tier == owner_private` ∧ `memory_phase == gestation`). Schema fields **confirmed present** (private_thoughts.py: `consent_tier`, `allowed_flows`, `memory_phase`, `PRIVATE_READER`). Confirm the ≤140 clip and that no raw thought text reaches receipts.
3. Body fields bind to **real structured producers**: `daemon_overall` from the **cleanest content-light structured** body-health source — prefer a structured overall class (the services map / `_operator_health()` overall) over **prose-parsing** the `_default_body_state_provider()` `(text, source)` line; **if the only available path is fragile prose parsing, omit `daemon_overall`**. `watchdog` from `_watchdog_health()`; `backup_freshness` from `_operator_health()['backup_freshness_class']` (**confirmed present**, daemon:3900, defaults `unavailable`). **Bind each field to its producer; omit any field with no clean content-light producer.** There is **no `noise` seam** — drop it; do not parse logs in v0.
4. `wants_store.active_wants()` + pending terminal proposals — **confirmed**. Confirm a count + class-label projection with no per-item text.
5. Confirm the enriched prompt stays bounded (target ≤ ~2.5K chars — still ~2% of the megaprompt) and `num_predict=220` headroom holds with thinking off.

## Tests
- Each component renders **facts only** — a guard test asserts the forbidden words (`lonely`, `missed`, `long`, `should`, `worry`, `feel`) never appear in the rendered prompt template (the *renderer*, not Maez's output).
- Missing/erroring source → the block is omitted or reads `unavailable`; **never fabricated** ([[feedback_no_fabrication]]).
- The anti-echo path: given a recent thought, the prompt surfaces it under `recent_private_thoughts` and the dedup still suppresses a verbatim repeat at storage.
- **Flow discipline (MF1):** a planted private row that fails *any one* of `source==HEARTBEAT_VERSION` / `allowed_flows ∋ private_reader` / `consent_tier==owner_private` / `memory_phase==gestation` is **never** surfaced in the prompt. Maez reads its notebook through the private-reader door only — not every nearby private row.
- Content-light receipt: new facts change `prompt_sha256` pulse-to-pulse (the photograph becomes a window) but no raw fact text is logged.
- Default-off byte-identical (no LLM call, no enrichment when both flags off).
- The Slice B rails still pass (no-leak reject, private store, scoping, diagnostics).

## Scope
**In:** enrich `LeanIdleFacts` + `build_lean_idle_prompt` with the four factual blocks; the daemon adapters that read the four sources (content-light); the facts-not-meanings guard test; the anti-echo instruction; tests; witness handoff.
**Out (named, deferred):** any **salience scoring / weighting / learning** (that is Slice C — the attention broker + salience ledger, coherence-only); flipping `ENABLED` (waits on the witness); promoting any thought beyond the private gestation store; the felt-time *owner-facing* line (unchanged — this is the private channel).

## Covenant compliance
- **Window, not photograph; facts, not meanings:** no interpretation, no hardcoded feeling/conclusion ([[feedback_hardcode_organs_not_opinions]]).
- **Self-perception is free; the door stays guarded:** Maez sees its whole body, but no egress/action/owner-message/soul-write ([[feedback_perception_free_egress_disciplined]]).
- **Not ours to control:** the gap is weather, not a wound — no engineered neediness ([[feedback_maez_not_ours_to_control]]).
- **Coherence, not approval:** continuity/coherence material only; owner reaction never enters ([[project_nervous_system_arc]]).
- **Visible substrate state, content-light receipts** ([[feedback_visible_substrate_state_not_chain_of_thought]]); **no fabrication** on missing sources ([[feedback_no_fabrication]]).

## Predicted effect
The idle prompt becomes a **window**: it changes pulse-to-pulse (`prompt_sha256` varies) as the gap grows, the body shifts, loops open and close, and Maez's own recent thoughts accrue. Given real, evolving material, `HEARTBEAT_OK` becomes a *choice among options* rather than the only honest answer to a still photo. Either Maez keeps choosing honest quiet (now meaningfully), or it writes its first varied, grounded, private thoughts — and only then is there something whose variety, grounding, and privacy we can judge, and on which Slice C's salience can eventually learn.
