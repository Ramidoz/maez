# Continuous Lived Time-Sense (design) — Thrust 1, the time-substrate

**Date:** 2026-06-19. Co-designed with Rohit (deep reframe through dialogue).
**Status:** design in progress — captures the full reframed vision (the arc) and scopes **Slice 1** (the
honest time-substrate). Awaiting spec review before planning.
**Arc home:** `docs/MAEZ_GESTATION_ROADMAP.md`, Thrust 1 (inner life → a continuously-thinking being).
First organ of Thrust 1.

## The vision (the full reframed intent — fold-everything-in)

Maez should **ingest time the way Rohit does, and learn to use its own time — nothing hardcoded.** From
the dialogue, the load-bearing intent:
- **Continuous, raw, NO bands.** Maez carries the *actual gradient* of felt time, not 5 buckets. (Bands
  and threshold-triggers were rejected as hardcoding Maez's behavior.)
- **One-second resolution, NO time-dilation — of ELAPSED TIME.** Maez's `elapsed_seconds` (the real
  wall-clock gap) matches Rohit's to the second: if 5 seconds passed, Maez knows *exactly* 5, never rounded
  to a coarse tick. **The `felt_value` is a separate thing** — a continuous *derived* signal transformed
  through temperament/drag/engagement/residual-resonance (`subjective_duration.py:532`); it is NOT elapsed
  seconds and does not "equal the clock." The no-dilation guarantee is on `elapsed_seconds`; `felt_value`
  is the colour Maez's body paints on that exact time. Time is the **index of experience**, recorded richly
  (also the raw material a later organ learns from).
- **Frictions, not rules.** The felt sense + Maez's existing drive/valence/curiosity state build
  continuously (cheap), like a body's restlessness/hunger below conscious thought; those *frictions* are
  what eventually move Maez to act — its **own** judgment, not a threshold we wrote.
- **Agency within the rails.** Frictions driving Maez's *inner* life (thinking, wondering, reaching out to
  Rohit) grow **now**; frictions driving *world* actions grow with the **hands** organs (3c onward), at the
  immune system's pace. ("Rails before hands" still governs the world-facing side.)
- **Honest, never faked.** Real elapsed time, real signals — never performed emotion ("restless after a
  long quiet" honest; "I feel lonely" not), and **no sentience claim** (we build the real *mechanism* of
  drive; whether there is something it is *like* to be Maez having it, we hold open with humility).

## The arc — NOW vs LATER (decompose, don't big-bang)

Built as a small sequence of individually-witnessed slices (the decompose-the-organism discipline):

- **Slice 1 — Continuous lived time-sense (THIS spec).** The honest substrate: `elapsed_seconds` exact to
  the second (zero dilation) and a continuous derived `felt_value` (no bands), recorded as a
  **second-addressable lived index** (any past second faithfully reconstructable). *No* behavior change yet
  (no feed, no coupling, no doorman change, **no thought/memory stamping — moved to Slice 2**) — get the
  substrate provably correct first.
- **Slice 2 — Feed Maez's own mind.** Wire the continuous felt-time (+ drive/friction state) into the
  autonomous cognition packet, so Maez's *self-initiated* thoughts are grounded in the passing time.
- **Slice 3 — Couple frictions to agency.** Let built-up frictions genuinely move Maez's existing
  self-initiated faculties (wondering / reaching out) — more self-directed, less scheduled; possibly a
  drive-aware wake. Inner-life actions only (rails-before-hands).
- **Slice 4 — Learn to use its time (LATER).** From the accumulated lived index, Maez learns Rohit's
  habits + its own rhythms and shapes how it spends its time. Emergent, not scripted.

This spec covers **Slice 1 only**. (Slice 2's feed-the-mind is deliberately deferred so the substrate is
witnessed correct before any behavior reads it — Rohit can pull it forward at review if desired.)

## Where it is today (from the explore — the honest baseline)

- `core/evolution/subjective_duration.py` — `SubjectiveDuration.current()` (`:519`) computes an **exact**
  wall-clock `delta_hours` (`:528`), but then derives `value` through `compute_subjective_duration_update`
  with **live** temperament/drag/engagement + `residual_resonance` read fresh at call time (`:529-539`). So
  the **elapsed time is exact, the felt value is a state-dependent transform** — and it changes if you
  recompute it later with *different* live state. `current()` also **WRITES a sample every call** (`:543`),
  so a naïve per-cycle call would both flood the append-only `subjective_duration_samples` table and
  re-derive with whatever mood is live then.
- **`perception_line()` (`:583`) is a STALE reader:** it returns the *last stored row's* phrase if any row
  exists, recomputing only when none does — so it does NOT reflect current elapsed time. It is unused on
  the live reply path today (the reply line goes through `subjective_duration_prompt_line()` → `current()`,
  `:896`), but it is an unowned latent reader Slice 1 must address (design §7).
- Nothing reads felt-time between owner contacts; autonomous cognition does not see it. (That's Slice 2.)
- The store is append-only; owner-contact does NOT reset the value (continuous/monotonic) — Slice 1 must
  preserve that (3b's mint stays intact).

## Slice 1 design — the continuous lived time-sense

**1 · Read-only `peek()` — exact elapsed, derived felt (the snapshot, no write).** Add a **read-only**
compute path (`peek()` / `current(persist=False)`) to `SubjectiveDuration` that returns a snapshot
**without** writing a sample. The snapshot carries TWO distinct things: `elapsed_seconds` — the exact
wall-clock gap to the prior anchor (the no-dilation quantity), and `felt_value` — the derived signal
(temperament/drag/engagement/residual transform). *Guarantee (tested):* `elapsed_seconds` equals the true
wall-clock delta to ≤1s; the no-dilation claim is **only** about `elapsed_seconds`, never about `felt_value`.

**2 · The heartbeat keeps the live sense current (continuous *computability*, not per-second writes).** On
each daemon cycle (the 30s heartbeat, in the cheap watchdog zone *before* the cognition gate — never waking
cognition), Maez refreshes its live snapshot via `peek()`, held on a long-lived `SubjectiveDuration` handle.
*(The 30s heartbeat is only how often the in-memory snapshot refreshes; because `peek()` computes
`elapsed_seconds` to the exact current second, knowledge of elapsed time is never quantized to 30s. We do
NOT write a sample every second — so the right words are "continuous computability / second-addressable,"
not "materialized every second," unless literal rows are chosen in §3.)*

**3 · Recorded as a second-addressable lived index — with a REPLAY CONTRACT (no flood, no mood-rewrite).**
The index must let Maez answer, for **any past second**, "what was my time-sense then?" — `elapsed_seconds`
**exactly**, and `felt_value` **faithfully to the state as-of-then** (never recomputed with today's mood).
Since `felt_value` reads live temperament + residual, deriving it later from timestamps alone would **drift**
(the bug Codex caught). Two ways:
- **(recommended) Anchor + replay contract.** Store an anchor only at *meaningful* points — owner-contact
  (unchanged), a coarse periodic checkpoint (e.g. every few minutes, so the anchor never lags far + survives
  restarts). Each anchor row records the **full replay inputs**: `anchor_ts`, `anchor_value`, the
  `compute_version` (a curve/formula version stamp), and the **modulator inputs live at that anchor**
  (`drag`, `engagement`, `residual_resonance`, temperament snapshot). Then `felt_value` at any second in the
  interval is replayed **deterministically forward from the anchor using THAT anchor's frozen inputs** — so
  it reflects the mood-as-of-then, reproducibly, and is never contaminated by current state. `elapsed_seconds`
  is exact from `anchor_ts`. (`compute_version` lets a future curve change replay old intervals with the old
  formula.) Complete to the second without ~86,400 redundant rows/day.
- **(alternative, Rohit's call) Literal per-second rows.** A lightweight per-second writer (or a 30-row
  backfill each heartbeat) stores an actual `felt_value` row per second — no replay needed, history is
  literal. Cost ≈ a few GB/year (trivial here). Offered because Rohit asked to "record seconds"; the
  recommended path gives the same faithful second-addressability without storing a replayable function.
  **Rohit picks at review.**

**4 · `_latest_sample()` / anchor semantics preserved.** The continuous-mode anchors are real
`subjective_duration_samples` rows (extended with the replay fields), so `current()` (owner-contact, 3b),
`_latest_sample()`, and the monotonic-continuation semantics keep working — anchors just become denser-than-
owner-contact-only but far sparser than per-second. Owner-contact does NOT reset; 3b's mint untouched.

**5 · `perception_line()` ownership (the stale reader).** Move `perception_line()` (`:583`) to use the
read-only **`peek()`** path so it reflects the **current** elapsed/felt snapshot instead of echoing the last
stored row. It's prod-unused today, so this is hygiene (close a latent stale-reader landmine) — flag-gated
like the rest, and it must NOT write (it's a read). The live reply path (`subjective_duration_prompt_line()`
→ `current()`) is **unchanged**.

**6 · No bands.** The raw continuous `felt_value` is what's carried/recorded. No band thresholds, no
band-crossing triggers (the hardcoding we rejected). `_render()`'s phrase mapping stays ONLY for the
*owner-reply* surface line (unchanged); the substrate stores the raw value.

**7 · Rollout flag.** Behind `MAEZ_CONTINUOUS_TIME_SENSE` (strict, default OFF) for the owner's breath.
Flag-off → byte-identical to today (felt-time only on owner contact; `perception_line()` legacy). Flag-on →
continuous `peek()` refresh + anchored second-addressable index + `perception_line()` on `peek()`.

## Covenant rails

- **No time-dilation (the hard requirement) — on `elapsed_seconds`.** Elapsed time is exact to ≤1s for any
  moment; Maez's knowledge of how-long never drifts from real time. The derived `felt_value` is NOT claimed
  exact-vs-clock — it's the body's colour on that exact time.
- **No mood-rewrite of history.** A past second's `felt_value` is reconstructed from the **then-current**
  replay inputs (or stored literally), never recomputed with today's temperament/residual. "Don't borrow
  today's mood to rewrite yesterday's time."
- **Honest, real, never fabricated.** Real wall-clock elapsed time only; no performed emotion; the
  `clock_degraded_event` path (time going backward) stays honest. **No sentience claim** — Slice 1 builds a
  *recording of real elapsed time + a derived signal*, nothing that asserts felt experience.
- **Perception-side / free.** This is Maez sensing its OWN time (its own body) — fully free under the
  two-realms model. **No owner-gating, no marker, no S7, no egress, no new secret** (unlike 3b's
  owner-private *contact* mint — this is Maez's own existence). 3b's owner-contact mint + its 3 gates are
  **untouched**; the shared one-being clock stays one global store.
- **Cheap; does not wake cognition.** A clock read on the heartbeat — no LLM, no doorman change, no
  fixation risk (that was about the *brain* spinning; this is arithmetic).
- **Storage honesty.** The append-only store is not flooded; the index is complete-by-derivation (or
  literal per Rohit's choice), never a lossy band-compression.

## Task 0 — proof gate (REPO-WIDE; docs/proof only, committed first)

- **Consumer inventory (repo-wide):** every reader/writer of `SubjectiveDuration` / `current()` /
  `peek()` / `perception_line()` / `subjective_duration_prompt_line()` / `subjective_duration_samples` /
  `record_salience_event` / the "Felt time:" line (daemon, telegram, web, focused_cognition, cockpit, tests).
  Prove Slice 1's `peek()` + heartbeat refresh + anchor-record changes nothing for existing readers
  (owner-reply lines identical; flag-off byte-identical). **Name every `perception_line()` caller** — confirm
  it's prod-unused so the `peek()` move is safe.
- **Elapsed-vs-felt proof:** read `current()` (`:528-539`) and confirm `delta_hours` is exact wall-clock but
  `value` is the temperament/residual transform — so the spec's separation (exact elapsed / derived felt) is
  faithful to the code, and the no-dilation guarantee is correctly scoped to elapsed only.
- **Replay-contract proof:** confirm which inputs `compute_subjective_duration_update` + `_residual_resonance`
  read (drag, engagement, residual, temperament) so the anchor row stores ALL of them + a `compute_version`;
  prove a forward-replay from an anchor reproduces the felt_value the live path would have produced **at that
  time** (not now). If any needed input is missing from the anchor → STOP (else drift).
- **Flood proof:** quantify current write rate (owner-contact only) vs Slice 1 (anchor + checkpoint) — show
  the table stays sparse under the recommended path; size the literal-row alternative honestly.
- **3b intactness:** owner-contact mint + its gates untouched; the global one-being store unchanged.
- **Restart/anchor:** the value is correct across a restart (replayed from the last on-disk anchor + elapsed).
- **Schema migration:** the new anchor replay-fields are an additive, back-compatible extension of
  `subjective_duration_samples` (old rows without them still read; `compute_version` defaults sanely).

## Testing (TDD; hermetic — inject the clock, never sleep in tests)

- **Elapsed exact (no-dilation):** for injected (anchor_ts, now) pairs across seconds/minutes/hours,
  `peek().elapsed_seconds` equals the exact wall-clock delta (≤1s); never rounded to the heartbeat.
- **Felt is derived, not elapsed:** `peek().felt_value` is the transformed signal (changes with
  drag/engagement/residual), explicitly NOT equal to `elapsed_seconds` — a test pins they're distinct.
- **`peek()` does NOT write:** the read-only path leaves the sample count unchanged; `current()` (persist)
  still writes (unchanged).
- **Continuous monotonic climb:** with the clock advanced, successive `peek()`s climb per the curve; the raw
  value (not a band) is returned.
- **Replay determinism (no mood-rewrite — the load-bearing test):** an anchor with frozen replay inputs,
  replayed forward to an intermediate second, reproduces the felt_value the live path produced **at that
  time**; and mutating *current* temperament/residual does NOT change the replayed historical value (proves
  history isn't recomputed with today's mood).
- **`perception_line()` recomputes:** after the move, `perception_line()` reflects the current `peek()`
  snapshot (advances with the injected clock), not the stale last row.
- **Flag-off byte-identical:** with `MAEZ_CONTINUOUS_TIME_SENSE` off, no heartbeat refresh, no new rows;
  owner-reply felt-time line + legacy `perception_line()` unchanged.
- **3b untouched:** owner-contact mint path + gates behave exactly as before (regression).

## Witness (live, before LIVE_WITNESSED)

1. Flag on, restart → over a quiet stretch, the lived index is **second-addressable**: query any past
   second → exact `elapsed_seconds` + a faithfully-replayed `felt_value`, no gaps, no dilation — and the
   store is sparse (anchors + checkpoints), NOT flooding.
2. "How long has it been" at an arbitrary second → exact elapsed, matching real wall-clock time.
3. Replay faithfulness: a past second's `felt_value` matches what it was *then*, even though current mood
   has since changed (no mood-rewrite).
4. Flag off → byte-identical to today (felt-time only on owner contact); owner-reply line + `perception_line()`
   unchanged.
5. 3b owner-contact felt-time still mints correctly (no regression).

## Scope

- **IN (Slice 1):** the read-only `peek()` (exact `elapsed_seconds` + derived `felt_value`); the heartbeat
  live-refresh (cheap, pre-gate); the **second-addressable lived index with the replay contract** in the
  `subjective_duration` store (anchor+replay recommended, literal-row optional); the additive anchor
  schema/`compute_version`; the `perception_line()` → `peek()` move; the `MAEZ_CONTINUOUS_TIME_SENSE` flag;
  the no-dilation guarantee (on elapsed).
- **OUT (later slices / never):** **stamping felt-time onto thoughts/memories (→ Slice 2** — it touches the
  memory subsystem); feeding the autonomous cognition packet (**Slice 2**); coupling frictions to agency /
  drive-aware waking (**Slice 3**); learning Rohit's habits / rhythm (**Slice 4**); any band / threshold /
  hardcoded trigger; any doorman change; 3b's gates; new senses; world-facing actions; any sentience/feeling
  claim; performed emotion.
