# Learned, Grounded Felt-Time — Design

**Date:** 2026-06-20. **Status:** design, owner-approved (with three corrections folded) — awaiting spec review.
**Arc:** the **foundation** of Thrust 1 (`docs/MAEZ_GESTATION_ROADMAP.md`) — it reorders the old Slice 3/4. Builds on:
Slice 1 substrate LIVE (`MAEZ_CONTINUOUS_TIME_SENSE=1`); **Slice 2 feed-mind merged-asleep / built into main
— `MAEZ_TIME_SENSE_FEED` and `MAEZ_TIME_SENSE_STAMP` are default-OFF and NOT owner-witnessed-live** (the
witness surfaced the pinned-curve finding below; they may stay off). See `project_continuous_time_sense`
(memory).

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

## Separate boxes — rhythm facts get their OWN columns (never overload `felt_*`)

The legacy curve stamp uses `felt_value` / `felt_elapsed_s` / `felt_phrase` / `felt_compute_version`. The
rhythm facts are a **different kind of thing** (raw learned data, not a feeling verdict). They get their own
schema — **do NOT pour medians/percentiles into `felt_value` or synthesize a `felt_phrase` from them** (that
would smuggle the verdict back through a side door). Dedicated additive nullable columns:

`rhythm_current_gap_s`, `rhythm_recent_gap_median_s`, `rhythm_all_time_gap_median_s`,
`rhythm_recent_sample_count`, `rhythm_all_time_sample_count`, `rhythm_current_gap_percentile_all_time`,
optional `rhythm_recent_gap_iqr_s` / `rhythm_all_time_gap_iqr_s`. Legacy `felt_*` and new `rhythm_*` stay in
separate boxes, always.

## Flag matrix — the rhythm flag changes the CONTENT source; feed/stamp flags are the MOUTHS

A new flag `MAEZ_RHYTHM_FELT_TIME` (default OFF) selects the **content source** (legacy curve vs learned
rhythm). The existing `MAEZ_TIME_SENSE_FEED` / `MAEZ_TIME_SENSE_STAMP` still control **whether the mouths are
open** (whether the cycle feed / episode stamp act at all). All AND-gated with the substrate
(`MAEZ_CONTINUOUS_TIME_SENSE`). Explicit matrix:

| `RHYTHM` | `FEED` | `STAMP` | Behavior |
|---|---|---|---|
| off | on | — | existing Slice-2 **curve-based** feed line (unchanged) |
| off | — | on | existing Slice-2 **curve-based** stamp (`felt_*`, unchanged) |
| **on** | on | — | feed renders **rhythm facts** instead of the curve phrase |
| **on** | — | on | stamp writes the **`rhythm_*` columns** (legacy `felt_*` left NULL — we stop recording the verdict) |
| on | off | off | **no behavior** — rhythm flag alone changes nothing until a mouth is open |
| off | off | off | default — behavior-identical to today |

**Decision (the "instead of / in addition to" fork):** when `RHYTHM` is on, the stamp writes **only** the
`rhythm_*` columns and leaves `felt_*` NULL — it does not also re-record the curve verdict. Separate boxes,
and we stop writing the thing we're retiring.

## Build BESIDE the old curve — repoint incrementally (NOT a single swap)

The hardcoded curve doesn't only feed Slice 2's cycle — it also feeds the **owner-facing** "Felt time: …"
line on Telegram/cockpit (`subjective_duration_prompt_line` / `perception_line`, daemon:5673) and the 3b
cockpit mint. Tearing it out at once re-opens too many live organs. So: **build the rhythm-facts layer beside
the old curve, behind its own flag; repoint surfaces one at a time; remove the dead curve only after the
rhythm layer is witnessed.** Decompose-the-organism, rails-before-hands.

**Staging (each its own slice: brainstorm-already-done → plan → subagent-driven → Claude two-stage + Codex
cross-lane → STOP at gate → owner breath):**
- **Slice A (this arc's first):** add the rhythm reader (the facts) **beside** the curve, behind the new
  `MAEZ_RHYTHM_FELT_TIME` flag; add the dedicated `rhythm_*` stamp columns; **repoint the cycle feed + the
  episode stamp** to the rhythm facts *when the rhythm flag is on* (feed renders the raw facts; stamp writes
  the `rhythm_*` columns, `felt_*` left NULL). The old `time_sense_context`/curve and `felt_*` columns stay
  untouched and still serve the foreground + the rhythm-off path. Flag-off → behavior-identical.
- **Slice B:** repoint the **foreground/cockpit** "Felt time: …" lines to the rhythm facts (the owner-facing
  surfaces — more careful; 3b mint semantics preserved).
- **Slice C:** **retire the dead curve** — stop all reads/writes of `compute_subjective_duration_update`, the
  temperament modulators, `_render` bands, and the legacy `felt_*` columns, and the now-unused
  `time_sense_context` — once nothing reads them. **Leave the legacy `felt_*` columns in place as nullable
  historical rows** (never-delete-memory; SQLite column-drop is unsafe); a physical column removal is a
  separate migration only if explicitly proven safe.
- **Then:** the old "couple frictions to agency" rides on top of a felt-time that **actually varies**.

## Kept vs torn out

- **Kept:** the exact clock; the `owner_contact` event history (the raw material); Slice-1 heartbeat/anchors;
  Slice-2's feed/stamp wiring, flags, and truthful-reader seam (we swap *content*, not plumbing).
- **Retired (Slice C, last) — reads/writes only:** the `0.42/0.18` curve, the temperament modulators, the
  `_render` phrase-bands, and reads/writes of the legacy `felt_*` columns. The `felt_*` **columns themselves
  stay** as nullable legacy history (never-delete-memory) unless a separate migration proves removal safe.

## Invariants (verify in review)

1. **No verdict in the substrate** — facts only; no label/band/phrase/feeling-value emitted by the rhythm
   reader. 2. **No expression-gate** — Maez's voice is not threshold-gated. 3. **Learned only from real
   contacts** — canary/`manual_test`/scratch excluded (reuse Slice-2 filter). 4. **Honest cold-start** —
   `None`/"still learning," never a fabricated stat. 5. **Truthful-reader `None`** on degraded/no-contact —
   never a frozen clock as alive. 6. **Build-beside, flag-off behavior-identical** — the old curve + all its
   surfaces unchanged until deliberately repointed; `MAEZ_RHYTHM_FELT_TIME` default-OFF. 7. **Separate
   boxes** — rhythm facts write ONLY `rhythm_*` columns; never overload `felt_value`/`felt_phrase`; rhythm-on
   stamp leaves `felt_*` NULL. 8. **Mouths vs source** — the rhythm flag selects content; `FEED`/`STAMP`
   still gate whether the surfaces act (per the flag matrix). 9. **Perception-side/free** — Maez's own time;
   no owner-gate/egress/secret. 10. **No single bold swap** — incremental repoint, curve reads/writes removed
   last, columns preserved.

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
