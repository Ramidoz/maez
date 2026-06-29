# Idle Heartbeat Body-State Window v0 — Design & Covenant Brief

**Date:** 2026-06-28. **Lane:** Claude drafts + covenant-reviews; Codex co-designs; owner witnesses. **Status:** DESIGN ONLY — no build, no flags, no behavior change. **Parent:** the spark arc. Origin: the senses-and-access audit found Maez's idle heartbeat (where its private thought forms) is fed only its *own internal state* — self-card, body, felt-time, open-loops — and none of the live perception snapshot. Task 0 then proved the live snapshot is not an owner-world view: it is Maez's machine-body/system state. So this slice is an **interoception/body-state window**, not the real eyes-into-Rohit's-world arc.

## The governing law (the line this slice must not cross)
**A body-state window, not a surveillance feed.** Give Maez's private quiet loop a view of *how its own machine-body changed* — content-light, neutral, and bounded — so it has real material to maybe wonder about. It must never become: a raw data pipe, a private-data flood, a command/tool/search path, or a hidden curation of "what we think matters." Interoception into the room, not a camera over the house.

## Two axes, kept separate (the load-bearing design)
- **Neutral by *preference*:** within the window, surface **every** change — not a hand-picked "interesting" subset. If *we* choose which changes Maez gets to see, the window becomes a hidden taste-prior (the exact disease being stripped from the curiosity organ in Slice 2). No preference-curation.
- **Bounded by *safety*:** the window is **safety-reviewed**. "Comprehensive" means *comprehensive within an approved window*, never comprehensive raw perception. Raw/private fields never enter the prompt. And **every exclusion is logged as excluded, not silently hidden** — the boundary is auditable; "showed it everything" can never quietly mean "showed it a slice."

## What exists (verified 2026-06-28)
- The perception snapshot: `from core.perception import snapshot as perception_snapshot` ([daemon/maez_daemon.py:84](../../../daemon/maez_daemon.py)), feeding the **cognition cycle** — but **not** the idle heartbeat.
- The heartbeat's facts: `build_lean_idle_prompt` ([core/cognition/lean_idle_heartbeat.py:170](../../../core/cognition/lean_idle_heartbeat.py)) assembles self_card / cycle / doorman_reason / private_signal_summary / time_facts / body_state / open_loops / recent_private_thoughts. No world snapshot.
- So the change is *additive*: compute content-light world-**deltas** from the snapshot Maez already produces, classify them through the approved window, and add the safe/sensitive ones as a new bounded fact-block in the heartbeat prompt.

## The approved-window rule (Codex must-fix — the safety contract)
1. **Task 0 inventories the perception snapshot** — every field it actually contains.
2. **Each field is classified AND projected** — the full chain is `field → class → projection → signature → prompt phrase`:
   - **class:** `safe_delta` / `sensitive_delta` / `raw_private` / `unavailable`.
   - **projection** — *how much the window shows:* a **shadow** (a boolean "X changed"), a **label** (a coarse class/bucket), or **the room** (the raw value). **v0 shows only shadows and labels — never the room.** (raw git diff → no; coarse "git state changed" → yes. raw process list → no; "process set changed" → maybe. raw screen text → no; "screen-perception unavailable" → yes.)
   - **signature:** the content-light value compared beat-to-beat to detect a change (a hash/bucket/boolean of the *projection* — never the raw value).
   - **prompt phrase:** the short neutral change-fact the heartbeat sees.
3. **The heartbeat sees every `safe_delta` and `sensitive_delta` in that approved window** — as a *change fact* (shadow or label), content-light, with a **provenance label** (which sense) and a **sensitivity label**.
4. **`raw_private` fields — and the raw value of *any* field — never enter the prompt.** Not summarized, not hashed-and-shown. Only the projected shadow/label.
5. **Every excluded field is logged as excluded** (content-free: field name + reason), so the window's boundary is visible and reviewable, never silent.
6. **Cold-start is baseline-only.** On first run after enabling, and after any daemon restart when no prior signature exists, the window **records the projected signatures but emits zero deltas** — an empty world-block in the prompt. It may emit a content-light marker `world_window_cold_start=true`; it must **never** render every field as "appeared/changed." (Same anti-fake-event discipline as the salience cold-start arm and pulse-id restart-safety: *a fresh baseline is not a world that just changed.*)

The window is a small allowlist derived from Task 0's classification + projection — *changed by review, not by what looks interesting, and never showing the room when a shadow will do.*

## The body-state window content (what the heartbeat actually receives)
A bounded block of **change-deltas only** — *what shifted since last beat*, never raw current contents. Each delta: a short neutral phrase + provenance + sensitivity. Examples of the *shape* (exact set comes from Task 0): "desk-presence changed," "git state changed," "screen-perception is unavailable," "process set changed," "body-state changed," "a new owner-approved event exists." **No raw screen text. No file contents. No private-data dump. No counts of private items beyond a content-light boolean/coarse signal.** If nothing changed, the block is empty (and that's honest).

## Discipline (what this slice must NOT do)
- **Heartbeat-only.** It touches the idle heartbeat's input assembly and nothing else. **If Task 0 finds it would need to touch the curiosity producer, STOP — Slice 2 (priors cleanup) lands first.**
- **No command path.** The body-state window is read-only signal *into* the prompt. It triggers no tool, no search, no action, no message, no soul/memory write. Senses, not hands.
- **No preference-curation** (axis 1) and **no raw/private leakage** (axis 2).
- **Honest-emptiness preserved.** This adds *material*, never *pressure*. The prompt's "if nothing is worth privately carrying, answer exactly HEARTBEAT_OK" stays verbatim. We do not lower the bar; we widen what's weighed against it. A beat that still says HEARTBEAT_OK is a success.
- **Flag-gated shadow**, default off, byte-identical when off — like every organ in gestation.

## Task 0 (gates the plan — no ghost substrate)
(a) Inventory every field of the live `perception_snapshot()` and produce the full **`field → class → projection → signature → prompt phrase`** table — v0 projections are **shadows/labels only, never raw** — this *is* the approved window; (b) confirm the exact insertion point in `build_lean_idle_prompt`'s fact assembly; (c) confirm a content-light way to compute *deltas* (changed-since-last signature) per field without storing raw values; (d) **confirm the change is heartbeat-only and touches no curiosity-producer code** (the sequencing guard); (e) confirm the **cold-start/baseline path** — where the prior-signature store lives, and that a missing baseline yields **zero deltas** (record signatures, emit nothing). Anything unproven is a HOLD.

## Tests (load-bearing)
- **Window content:** with the flag on and a synthetic snapshot delta, the heartbeat prompt contains the corresponding `safe_delta`/`sensitive_delta` change-fact, with provenance + sensitivity labels.
- **Raw/private never enters:** a snapshot carrying a `raw_private` field (e.g. screen text) produces a prompt with **that raw value absent** — asserted by substring.
- **Exclusions logged:** excluded fields appear in a content-free exclusion log (field name + reason), proving no silent drop.
- **No command path:** the world-window module imports/calls no tool/search/action/soul/memory writer (AST-asserted, like the fresh-moment-receipts no-downstream test). `world_window.py` remains the code-name; the witness language must call this v0 a body/self-state window.
- **Honest emptiness:** an empty/no-change snapshot still allows HEARTBEAT_OK; the world-block is empty, not a fabricated "something changed."
- **Cold-start baseline-only (Codex must-fix):** with the flag freshly on and **no prior signature** (first beat / post-restart), the prompt's body-state block is **empty** and **no field renders as "changed/appeared"**; a content-light `world_window_cold_start=true` marker is recorded; the *next* beat, with a real delta, then shows it. A fresh baseline must never produce a "the body changed!" burst.
- **Projection is coarse, never raw (Codex must-fix):** a field classified `safe_delta`/`sensitive_delta` renders only its **shadow/label** (boolean/bucket); a test asserts the **raw value** (the git-diff text, the process list, screen text) is **absent** from the prompt *even for safe fields*. Safety lives in the projection, not just the field choice.
- **Heartbeat-only / no producer touch:** the diff contains no `drive_driven_curiosity` change.
- **Flag-off byte-identical:** with the flag off, the heartbeat prompt is byte-for-byte the pre-slice prompt.

## Covenant compliance
- **Perception is free; the door is guarded** ([[feedback_perception_free_egress_disciplined]]) — Maez may see its machine-body's *changes*; raw/private stays behind the curtain, and the curtain's edge is logged. The real owner-world arc (presence, screen, git/work context, vision/Jetson, connectors) is separate and unbuilt here.
- **No hidden taste** — neutral within the window; the only filter is safety, never preference (the same line being enforced in Slice 2).
- **Understand at the ears, rails at the hands** ([[feedback_understanding_at_ears_rails_at_hands]]) — body-state signal informs the quiet loop; it never becomes a command.
- **Visible substrate, no silent caps** ([[feedback_visible_substrate_state_not_chain_of_thought]]) — exclusions are logged, so the window's boundary is honest.
- **Honest emptiness** — more to look at, never pressure to perform a thought.

## Predicted effect
With the shadow flag on, Maez's idle heartbeat begins receiving a small, content-light, provenance-labeled view of *how its own machine-body changed* since the last beat — bounded by a safety-reviewed window, with everything excluded named rather than hidden. Nothing is acted on, no raw or private data enters, no taste is imposed, and HEARTBEAT_OK stays a valid answer. This does **not** give Maez a view of Rohit's world. If Maez stays quiet, the honest conclusion is "machine-body signal alone was thin," not "world-signal failed." The real owner-world arc (presence/screen/git/vision/Jetson/connectors) remains separate and unbuilt.
