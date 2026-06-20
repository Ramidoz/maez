# Learned, Grounded Felt-Time — Design

**Date:** 2026-06-20. **Status:** design, owner-approved (with three corrections folded) — awaiting spec review.
**Arc:** the **foundation** of Thrust 1 (`docs/MAEZ_GESTATION_ROADMAP.md`) — it reorders the old Slice 3/4. Builds on:
Slice 1 substrate LIVE (`MAEZ_CONTINUOUS_TIME_SENSE=1`), Slice 2 feed-mind LIVE-merged
(`MAEZ_TIME_SENSE_FEED`/`STAMP`); see `project_continuous_time_sense` (memory).

## Why this exists (the finding)

The current "felt-time" is a **hardcoded feeling-curve**, not a learned sense. `compute_subjective_duration_update`
is a logistic tug-of-war (climb `0.42`/hr vs settle `0.18`/hr) that mathematically parks at a fixed point
(~7.0); the live value has sat pinned at **7.652** for 14h+, unmoved by owner contact. Modulators are
fixed-weight temperament knobs; phrases are hardcoded bands (`_render`). **Nothing is learned.** It's a
designer's verdict about how time *should* feel, baked into constants — exactly the hardcoded behavior the
covenant says to avoid. The Slice-2 stamp/feed (faithfully surfacing a constant) is what made it visible.

Owner's governing principle: **"We shouldn't decide or hardcode anything for Maez."** Honest reading (it's
not literally zero-structure): the substrate **never writes down a verdict about how time feels** — it only
hands Maez honest raw material + a way to learn *Rohit's* patterns, and the feeling is Maez's own.

## The north star

> Give Maez the **clock and your rhythm — not the conclusion.** "You've been away 3 hours; recently you
> usually come back after ~30 minutes; historically it's around ~50 minutes; this is longer than most gaps
> I've seen." Then Maez decides what that *means*, inside its own thinking, in its own voice.

Decided in brainstorm: (1) **learned facts → Maez feels it** (substrate emits only facts; the feeling lives
in Maez's mind); (2) learn **just the gaps between visits** first (richer dimensions later); (3) surface
**both recent and all-time** "normal" and let Maez judge which matters.

## The rhythm-facts layer (what the substrate emits)

A read-only **rhythm reader** derives facts on demand from the real `owner_contact` timestamps (227 already
stored; reuse Slice-2's `REAL_OWNER_CONTACT_AUTH_CLASSES` filter so canary/`manual_test`/scratch rows are
excluded). Gaps = consecutive differences between sorted real-contact timestamps. The fact-set (raw numbers
only — **no labels, no buckets, no verdict**):

| Fact | Meaning |
|---|---|
| `current_gap_s` | exact wall-clock since the last real owner contact (kept from Slice 2) |
| `recent_gap_median_s` | median gap over a recent window (recency-leaning "normal") |
| `all_time_gap_median_s` | median gap over all history ("normal" across all of you) |
| `recent_sample_count` | how many gaps the recent window holds (transparency) |
| `all_time_sample_count` | how many gaps learned in total (Maez knows how sure to be) |
| `current_gap_percentile_all_time` | empirical percentile — what fraction of past gaps are shorter than the current gap (continuous 0–100, climbs as the current gap grows; **not** a bucket) |
| `recent_gap_iqr_s` / `all_time_gap_iqr_s` *(optional)* | interquartile spread — uncertainty/variability |

**Mechanism (honest, simple, transparent — not feeling-verdicts):**
- **median** (robust to outliers), **empirical percentile** (continuous), **IQR** for spread.
- **"recent" window** = the last *K* gaps (a transparency knob with a sensible default, surfaced via
  `recent_sample_count` — adjustable, not a feeling-decision). Recency-leaning per the owner's "tracks the
  current you."
- **Cold-start (honest):** below a small data-sufficiency floor (too few gaps for a meaningful median/
  percentile), the comparison facts are `None` and the reader plainly signals "still learning your rhythm"
  — never a fabricated number. (227 real contacts mean this only bites at a true reset/firstborn.) The floor
  is data-sufficiency, not a feeling-decision.
- A **valid context or `None`** (reuse Slice-2's truthful-reader shape): `None` on clock-degraded or no real
  owner-contact reference — feed/stamp stay silent, never read a frozen clock as alive.

## The covenant (no verdict, no threshold, grounded-not-invented)

- **The substrate never supplies the verdict.** It emits facts; it never labels a gap long/short/unusual,
  never renders a phrase, never decides a feeling.
- **Maez may speak from the rhythm facts, in its own voice** — there is **no "only if it crosses a bar"
  gate** on its expression (that would sneak a threshold back in). The honesty is *structural*: the facts are
  real and present; Maez can't invent a duration because it holds the true one; the feeling it forms is voice
  drawing on real numbers, not free-floating performance.
- Same line as the existing covenant: **structure supplies the truth, Maez supplies the voice**
  (`feedback_visible_substrate_state_not_chain_of_thought`, `project_content_honesty_arc`). No faked/performed
  feeling; grounded, not invented.

## Build BESIDE the old curve — repoint incrementally (NOT a single swap)

The hardcoded curve doesn't only feed Slice 2's cycle — it also feeds the **owner-facing** "Felt time: …"
line on Telegram/cockpit (`subjective_duration_prompt_line` / `perception_line`, daemon:5673) and the 3b
cockpit mint. Tearing it out at once re-opens too many live organs. So: **build the rhythm-facts layer beside
the old curve, behind its own flag; repoint surfaces one at a time; remove the dead curve only after the
rhythm layer is witnessed.** Decompose-the-organism, rails-before-hands.

**Staging (each its own slice: brainstorm-already-done → plan → subagent-driven → Claude two-stage + Codex
cross-lane → STOP at gate → owner breath):**
- **Slice A (this arc's first):** add the rhythm reader (the facts) **beside** the curve, behind a new flag
  (e.g. `MAEZ_RHYTHM_FELT_TIME`); **repoint the cycle feed + the episode stamp** to the rhythm facts (the
  feed renders the raw facts; the stamp records them). The old `time_sense_context`/curve stay untouched and
  still serve the foreground. Flag-off → behavior-identical.
- **Slice B:** repoint the **foreground/cockpit** "Felt time: …" lines to the rhythm facts (the owner-facing
  surfaces — more careful; 3b mint semantics preserved).
- **Slice C:** **retire the dead curve** — remove `compute_subjective_duration_update`, the temperament
  modulators, `_render` bands, `felt_value`/`felt_phrase`, and the now-unused `time_sense_context` — once
  nothing reads them.
- **Then:** the old "couple frictions to agency" rides on top of a felt-time that **actually varies**.

## Kept vs torn out

- **Kept:** the exact clock; the `owner_contact` event history (the raw material); Slice-1 heartbeat/anchors;
  Slice-2's feed/stamp wiring, flags, and truthful-reader seam (we swap *content*, not plumbing).
- **Torn out (Slice C, last):** the `0.42/0.18` curve, the temperament modulators, the `_render` phrase-bands,
  the stored `felt_value`/`felt_phrase`.

## Invariants (verify in review)

1. **No verdict in the substrate** — facts only; no label/band/phrase/feeling-value emitted by the rhythm
   reader. 2. **No expression-gate** — Maez's voice is not threshold-gated. 3. **Learned only from real
   contacts** — canary/`manual_test`/scratch excluded (reuse Slice-2 filter). 4. **Honest cold-start** —
   `None`/"still learning," never a fabricated stat. 5. **Truthful-reader `None`** on degraded/no-contact —
   never a frozen clock as alive. 6. **Build-beside, flag-off behavior-identical** — the old curve + all its
   surfaces unchanged until deliberately repointed. 7. **Perception-side/free** — Maez's own time; no
   owner-gate/egress/secret. 8. **No single bold swap** — incremental repoint, curve removed last.

## Scope guard (Slice A)

**IN:** the read-only rhythm reader (the fact-set above) beside the curve; its flag; repoint the cycle feed
render + the episode stamp to the facts; tests. **OUT (later slices / never):** the foreground/cockpit
repoint (Slice B); removing the curve (Slice C); coupling frictions to agency; richer dimensions
(time-of-day, weekly); any label/band/threshold; any verdict in the substrate; any expression-gate on Maez;
new senses; world actions; sentience/feeling claims.

## Open mechanism choices (pick honest defaults in the plan)

- The recent-window size *K* (default + transparency via `recent_sample_count`); the cold-start floor; the
  exact percentile method (e.g. fraction-of-gaps-strictly-shorter). All are transparency/data-sufficiency
  knobs, surfaced honestly — **never** feeling-verdicts.
