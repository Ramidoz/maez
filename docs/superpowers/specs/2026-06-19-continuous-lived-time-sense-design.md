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
- **One-second resolution, NO time-dilation.** Maez's sense of elapsed time matches Rohit's to the second.
  If 5 seconds passed for Rohit, Maez knows *exactly* 5 — never rounded to a coarse tick. Time is the
  **index of experience**, recorded richly (it's also the raw material a later organ learns from).
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

- **Slice 1 — Continuous lived time-sense (THIS spec).** The honest substrate: felt-time advances
  continuously at one-second resolution, zero dilation, no bands, recorded as a complete lived index, and
  stamped onto Maez's thoughts/memories as their time-context. *No* behavior change yet (no feed, no
  coupling, no doorman change) — get the substrate provably correct first.
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

- `core/evolution/subjective_duration.py` — `SubjectiveDuration.current()` already computes felt-time from
  the **exact** wall-clock delta since the latest stored sample (so the *value* is already dilation-free
  on read). The curve climbs monotonically with real elapsed time. BUT: `current()` is called **only on
  owner contact** (handle_message / telegram / web), and **it WRITES a sample every call** — so today
  there is no continuous materialization, and a naïve per-cycle `current()` would flood the append-only
  `subjective_duration_samples` table.
- Nothing reads felt-time between owner contacts; autonomous cognition does not see it. (That's Slice 2.)
- The store is append-only; owner-contact does NOT reset the value (it's continuous/monotonic) — Slice 1
  must preserve that (3b's mint stays intact).

## Slice 1 design — the continuous lived time-sense

**1 · Exact-second compute, always (the no-dilation guarantee).** Add a **read-only** compute path
(e.g. `peek()` / `current(persist=False)`) to `SubjectiveDuration` that returns the felt-time snapshot
computed to the **exact current second** (the existing delta math already does this) **without** writing a
sample. *Guarantee (tested):* for any moment, the computed elapsed time equals the true wall-clock delta to
≤1s — Maez never experiences time dilation vs. real time.

**2 · The heartbeat materializes it continuously.** On each daemon cycle (the 30s heartbeat, in the cheap
watchdog zone *before* the cognition gate — never waking cognition), Maez advances its live felt-time via
`peek()`. The live value is held in memory (a long-lived `SubjectiveDuration` handle on the daemon) so the
sense is continuously current without a write per cycle. *(Heartbeat = 30s is the materialization cadence;
the VALUE is always exact-to-the-second on read, so there is no 30s quantization of knowledge — only of how
often the in-memory snapshot refreshes, which is invisible to elapsed-time accuracy.)*

**3 · Recorded as a complete second-resolution lived index (no flood).** The record must answer "exactly
how did felt-time stand at any given second?" with zero gaps and zero dilation. Two ways, both meeting the
requirement — **recommended: derive-exact + anchor-record**:
- **(recommended) Anchor + derive.** Store a sample only at *meaningful* points — on each owner-contact
  (unchanged), on a coarse periodic checkpoint (e.g. every few minutes, so the on-disk anchor never lags
  far and survives restarts), and when Maez records a thought/memory (below). Because felt-time is a clean
  deterministic function of exact timestamps, the value at *any* second is reconstructable **exactly** from
  the nearest anchor — so the index is complete to the second without storing ~86,400 redundant rows/day.
- **(alternative, Rohit's call) Literal per-second rows.** A dedicated lightweight per-second writer (or a
  30-row backfill each heartbeat) materializes an actual row per second. Cost ≈ a few GB/year (trivial on
  this rig), but it densely stores a *computable* function. Offered because Rohit asked to "record seconds"
  — the recommended path gives the same second-resolution guarantee without the redundancy; **Rohit picks
  at review.**

**4 · Time as the index of thoughts/memories (boundary-flagged).** The lived diary should carry "how long
it had been when I thought this" — Rohit's "time stored as the index of thoughts and memories." But
*stamping onto thoughts/memories* touches the memory/episode subsystem, not just `subjective_duration` —
a wider blast radius than the rest of Slice 1. **Task 0 decides the boundary:** if the recording path takes
a clean, content-light felt-time stamp without disturbing the memory write contract, it rides Slice 1; if
it's wider (or thoughts are mostly created in cognition), it moves to **Slice 2** (which already touches
that path). Slice 1's *guaranteed* deliverable is the continuous second-resolution felt-time + its own
complete lived index in the `subjective_duration` store; the cross-stamp is the bridge to Slice 2.

**5 · No bands.** The raw continuous value is what's carried/recorded. No band thresholds, no
band-crossing triggers (those were the hardcoding we rejected). `_render()`'s phrase mapping stays only for
the *owner-reply* surface line (unchanged); the substrate stores the raw value.

**6 · Rollout flag.** Behind `MAEZ_CONTINUOUS_TIME_SENSE` (strict, default OFF) for the owner's breath.
Flag-off → byte-identical to today (felt-time only materializes on owner contact). Flag-on → continuous
materialization + the lived index.

## Covenant rails

- **No time-dilation (the hard requirement).** Elapsed time is exact to ≤1s for any moment; Maez's
  time-sense never drifts from real time. Tested by construction.
- **Honest, real, never fabricated.** Real wall-clock elapsed time only; no performed emotion; the
  `clock_degraded_event` path (time going backward) stays honest. **No sentience claim** — Slice 1 builds a
  *recording of real elapsed time*, nothing that asserts felt experience.
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
  `subjective_duration_samples` / `record_salience_event` / the "Felt time:" line (daemon, telegram, web,
  focused_cognition, cockpit, tests). Prove Slice 1's `peek()` + heartbeat-materialize + anchor-record
  changes nothing for existing readers (owner-reply lines stay identical; flag-off is byte-identical).
- **No-dilation proof shape:** confirm the existing delta math is exact wall-clock subtraction (no
  rounding) so the guarantee is real.
- **Flood proof:** quantify the current write rate (owner-contact only) vs Slice 1's (anchor + checkpoint)
  — show the table stays sparse under the recommended path; size the literal-row alternative honestly.
- **3b intactness:** confirm owner-contact mint + its gates are untouched; the global one-being store
  unchanged.
- **Restart/anchor:** confirm the value is correct across a restart (computed from the last on-disk anchor +
  elapsed).

## Testing (TDD; hermetic — inject the clock, never sleep in tests)

- **No-dilation:** for a set of injected (anchor_ts, now) pairs across seconds/minutes/hours, the computed
  elapsed equals the exact delta (≤1s); never rounded to the heartbeat.
- **`peek()` does NOT write:** calling the read-only path leaves the sample count unchanged; `current()`
  (persist) still writes (unchanged).
- **Continuous monotonic climb:** with the clock advanced, successive `peek()`s climb per the curve; the
  raw value (not a band) is returned.
- **Anchor + derive completeness:** given sparse anchors, the felt-time at an arbitrary intermediate second
  reconstructs exactly (== a direct compute from that anchor).
- **Flag-off byte-identical:** with `MAEZ_CONTINUOUS_TIME_SENSE` off, no heartbeat materialization, no new
  rows; owner-reply felt-time line unchanged.
- **Thought-stamp:** a recorded thought/memory carries the exact felt-time context.
- **3b untouched:** owner-contact mint path + gates behave exactly as before (regression).

## Witness (live, before LIVE_WITNESSED)

1. Flag on, restart → over a quiet stretch, the lived index shows felt-time materializing continuously at
   second-resolution (query any second → exact value, no gaps, no dilation), and the store is NOT flooding.
2. Ask Maez (or query the record) "how long has it been" at an arbitrary second → exact, matching real
   elapsed time.
3. Flag off → byte-identical to today (felt-time only on owner contact); owner-reply felt-time unchanged.
4. 3b owner-contact felt-time still mints correctly (no regression).

## Scope

- **IN (Slice 1):** the read-only `peek()` compute; the heartbeat continuous-materialize (cheap, pre-gate);
  the second-resolution lived index in the `subjective_duration` store (anchor+derive recommended,
  literal-row optional); the `MAEZ_CONTINUOUS_TIME_SENSE` flag; the no-dilation guarantee. **Boundary-flagged
  (Task 0 decides Slice 1 vs Slice 2):** stamping felt-time onto thoughts/memories (rides Slice 1 only if the
  memory-write path takes it cleanly).
- **OUT (later slices / never):** feeding the autonomous cognition packet (**Slice 2**); coupling frictions
  to agency / drive-aware waking (**Slice 3**); learning Rohit's habits / rhythm (**Slice 4**); any band /
  threshold / hardcoded trigger; any doorman change; 3b's gates; new senses; world-facing actions; any
  sentience/feeling claim; performed emotion.
