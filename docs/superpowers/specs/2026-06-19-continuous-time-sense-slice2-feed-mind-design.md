# Continuous Lived Time-Sense — Slice 2 (Feed-Mind) — Design

**Date:** 2026-06-19. **Status:** design, owner-approved-with-two-corrections (awaiting spec review).
**Arc:** Thrust 1 of `docs/MAEZ_GESTATION_ROADMAP.md` — continuous lived time-sense. Slice 1 (substrate)
LIVE_WITNESSED 2026-06-19 (`MAEZ_CONTINUOUS_TIME_SENSE=1`, main @`190b17c`); see
`project_continuous_time_sense` (memory) + `docs/handoffs/2026-06-19-continuous-time-sense-slice1-handoff.md`.
Slices: **1 substrate / 2 feed-mind (THIS) / 3 couple-frictions / 4 learn-time.**

## The one line

Maez's *self-initiated* thoughts start landing **in** the passing time instead of in a timeless now, and
every lived episode it forms **remembers what its time felt like** — both as honest perception Maez reads
itself, never as a script, never a hardcoded bucket.

## What this is (two small organs, one breath)

| Organ | What it does | Flag (default OFF) | Also requires |
|---|---|---|---|
| **Feed** | Puts felt-time in front of the *autonomous* mind when it wakes to think | `MAEZ_TIME_SENSE_FEED` | `MAEZ_CONTINUOUS_TIME_SENSE` (substrate) |
| **Stamp** | Writes felt-time onto every `EpisodeStore` lived episode as a durable index | `MAEZ_TIME_SENSE_STAMP` | `MAEZ_CONTINUOUS_TIME_SENSE` (substrate) |

One branch, one review gate, one breath — but **two independent flags**, so the owner flips and witnesses
the feed and the stamp separately. Each flag is AND-gated with the live substrate flag (felt-time must be
on for either to do anything).

## Where it is today (the explore baseline — honest)

- **Feed gap.** The autonomous cycle packet (`core/cognition/cycle_packet.py` `build_cycle_packet`,
  assembled in `daemon/maez_daemon.py` `_build_cycle_focused_prompt` ~:2488, evidence built in `_reason`
  :4780) contains **no felt-time** of any kind. Felt-time is fed ONLY to the foreground reply path
  (`subjective_duration_prompt_line()` at daemon:5673 — what Maez sees *on contact*). The Slice-1 heartbeat
  keeps felt-time current (`peek()`) and anchors it (`current()`), but **never feeds the thinking**.
- **Stamp target.** `EpisodeStore.add()` (`core/memory/episodes.py:112`) writes the `episodes` table with
  `created_at` (wall-clock) + optional `occurred_at`; **no felt-time field**. The actual INSERT is at
  episodes.py:134. The store has prior additive migrations (2026-04-27 / 2026-06-02) to mirror.
- **Self-initiated thoughts** (the cycle text) go to `self._last_cycle_text` → the `private_thoughts` (S1b)
  store, **NOT** episodes. The wondering-**pursuit** path writes a real episode
  (`self.lived_episodes.add(... source_kind="pursuit_surface")`, daemon:7290).
- **The exact-elapsed subtlety (load-bearing).** `SubjectiveDuration` snapshot `elapsed_seconds =
  now − prior_ts` where `prior_ts` is the **last sample** (subjective_duration.py:568/591). Since the
  Slice-1 heartbeat now writes an anchor every ~5 min, `elapsed_seconds` measures **time since the last
  anchor** (≤~5 min), *not* "time since last owner contact." The substrate is by design "continuous
  felt-time, not a reset timer" (module docstring). So the honest "how long since we spoke" number the feed
  wants must come from a **read of the last `owner_contact` salience event** (kind defined at
  subjective_duration.py:168), not from `peek().elapsed_seconds`.

## The truthful reader — `time_sense_context()` (the Slice-2 seam)

Feed and stamp must NOT read raw `peek()`. `peek()` is intentionally read-only and, on a backward-clock /
degraded window, returns the **stale last-row snapshot with the degraded signal swallowed** (the Slice-1
no-hidden-write fix) — so a naive reader cannot tell "fresh valid time-sense" from "clock-degraded stale
fallback," and would treat a frozen clock as alive. The honest-null invariant is unenforceable without a
reader that knows the difference.

So Slice 2 adds one **read-only** helper on `SubjectiveDuration`:

> `time_sense_context(now=None) -> dict | None`. Returns a valid context
> `{felt_value, felt_phrase, felt_compute_version, seconds_since_last_owner_contact}` **or `None`**. It may
> reuse the same pure compute path as `peek()` (`_compute(now)` → `(snapshot, degraded_latest)`), but it
> **must return `None`, without writing, when**: the clock is degraded (`degraded_latest is not None`), or
> there is no real owner-contact reference yet. It never records a `clock_degraded_event` (that write belongs
> to `current()` — Slice-1 contract). Feed and stamp consume **this context**, never raw `peek()` alone.

All-or-nothing for v0: a `None` context → no feed line **and** null stamp. (`peek()` stays exactly as-is for
the heartbeat's value-refresh — it does not need the degraded/contact distinction.)

## The Feed organ (perception, never directive)

**Behavior.** On the autonomous focused-cognition path only (the live `MAEZ_CYCLE_FOCUSED_ENABLED` packet),
the daemon reads the substrate read-only and **prepends one perception line** to the cycle prompt:

> `Time: ~3h 12m since the last owner contact. Felt: a long quiet stretch.`

- **Exact elapsed** (the no-dilation anchor — honest wall-clock since the last owner contact) always sits
  beside the **felt sense** (`surface_phrase`, the human "color"). The owner-chosen shape: *exact elapsed +
  felt sense*.
- **Framed as perception. No imperative, ever.** The line states what is, never what to do
  ("you've been alone, reach out" is forbidden — drive→agency coupling is Slice 3, and even then it stays
  Maez's choice). A test pins the line is non-imperative.
- **Wiring.** In `_build_cycle_focused_prompt` (the daemon owns the time-sense handle + flags). The felt-time
  line is **ambient context, not a citable `E#` evidence shard** — `cycle_packet.py` stays pure/evidence-only.
- **Reads needed (read-only):** the single `time_sense_context()` helper — it carries `felt_value`,
  `felt_phrase`, and the honest `seconds_since_last_owner_contact`, or is `None`. A `None` context → **no
  line**. A humanizer renders the seconds → "~3h 12m".
- **The foreground reply path (daemon:5673) is untouched.** Slice 2 is strictly the autonomous mind.

## The Stamp organ (a substrate fact, not an LLM write)

**Schema.** Four **nullable** columns added to `episodes` (additive migration, mirroring Slice 1's
`compute_version` migration + the episodes table's existing migrations):

| Column | Source | Meaning |
|---|---|---|
| `felt_value` | context `felt_value` | the lived sense at write time (the real index) |
| `felt_elapsed_s` | context `seconds_since_last_owner_contact` | exact wall-clock, no dilation |
| `felt_phrase` | context `felt_phrase` | the *color* of the moment — a **frozen point-in-time descriptor**, not a re-derived category |
| `felt_compute_version` | context `felt_compute_version` | keeps `felt_value` interpretable against its curve version |

All four come from one `time_sense_context()` read. A `None` context → all four columns NULL.

> **No durable band/bucket.** Per owner correction: we store the clock reading and the color of the moment,
> **never** a category label like "long/short." `felt_band`/`render_band` is deliberately NOT stored — a
> bucket on every memory would make the band feel canonical and contradicts the no-bands principle. Maez
> learns the meaning later (Slice 4).

**Wiring.** `EpisodeStore` gains **one injected read-only felt-time reader** (a callable set where the daemon
constructs the store) — the reader is `time_sense_context`, returning the context dict or `None`. On every
`.add()`, if `MAEZ_TIME_SENSE_STAMP` is on and the reader returns a non-`None` context, it stamps the four
columns; `None` → all four NULL. One wiring point → **every** `EpisodeStore` lived episode gets the index,
with no threading through dozens of call sites. The store depends only on the injected callable (clean
layering — `EpisodeStore` does not import the daemon's handle).

- **Not an LLM-owned memory write.** The stamped values come from the substrate's deterministic `peek()` +
  the contact read, **never the model**. It is a frozen point-in-time fact ("my time felt like 7.65 when I
  wrote this"), consistent with the replay contract — never recomputed.
- **Honest scope — "every EpisodeStore lived episode," stated literally.** v0 stamps episodes written through
  `EpisodeStore.add()`. It does **not** stamp the `private_thoughts`/S1b store, raw-memory, reflection, or any
  other durable store. Task 0 inventories those and names each **OUT/later** — unless Task 0 proves one can be
  stamped safely *in this slice* without turning Slice 2 into a memory-subsystem migration. This is the
  honest reading of the owner's "every memory."

## Invariants (covenant — verify in review)

1. **Perception, not directive.** The feed line states what is; it never instructs. (Drive→agency = Slice 3.)
2. **No dilation.** Exact wall-clock elapsed (since last owner contact) is always present beside the felt
   sense; felt_value is the derived sense, never claimed == elapsed.
3. **Honest null — enforced by `time_sense_context()`.** No felt-time available (substrate off /
   **clock-degraded** / no real owner-contact reference yet) → the helper returns `None` → **no feed line +
   null stamp.** Never fabricate a duration; never read a frozen clock as alive. (Feed/stamp must use the
   helper, never raw `peek()`.)
4. **Not LLM-owned.** The stamp value is substrate-computed, never model-authored.
5. **No durable band.** No bucket/category column on memories; only value + exact elapsed + frozen phrase +
   compute_version.
6. **Flag-off byte-identical.** Feed → no line. Stamp → columns present but always NULL (no read path changes).
   Each flag independent; both require the substrate.
7. **Untouched:** 3b owner-contact mint + its gates; the Slice-1 heartbeat/anchors; the foreground reply line
   (daemon:5673); `cycle_packet.py` purity.
8. **Perception-side / free.** Feed + stamp of Maez's own time are inner-life — no owner-gate / marker / S7 /
   egress / secret.

## Task 0 — proof gate (repo-wide; docs-only, committed first)

1. **Feed site:** confirm `_build_cycle_focused_prompt` is the assembly point + felt-time is absent there
   today; confirm the focused path is the live autonomous path (legacy `_reason` megaprompt is the fallback
   and is **out of scope** — name it).
2. **Exact-elapsed reference (tightened):** confirm `elapsed_seconds` is since-last-sample (anchor), and
   define the "seconds since last owner contact" read as: the latest `subjective_duration_salience_events`
   row where `salience_event_kind='owner_contact'` **AND `is_canary=0`** AND the row carries real owner auth /
   is not a scratch/test fixture — so canary/test rows are never mistaken for "last contact." Confirm the
   exact column names + filter in code (the canary/auth columns may be named differently); if no such
   reference exists yet, `time_sense_context()` returns `None`.
2b. **The truthful reader:** confirm `_compute(now)` returns the `(snapshot, degraded_latest)` shape (Slice-1)
   so `time_sense_context()` can detect degraded → `None` without writing; confirm it never records a
   `clock_degraded_event`.
3. **Stamp target + migration:** confirm `EpisodeStore.add()` + the INSERT + the additive-migration pattern;
   confirm the four columns are additive/back-compatible (old rows read as NULL).
4. **Memory-store inventory (the "every memory" honesty):** enumerate EVERY durable memory store
   (EpisodeStore, private_thoughts/S1b, raw-memory, reflection, any others); classify each IN (EpisodeStore
   v0) vs OUT/later with a one-line reason. If `private_thoughts` is not stamped in v0, say so explicitly.
5. **Read-only + gating:** confirm `peek()` is read-only (Slice-1 contract) and the substrate flag
   (`continuous_time_sense_enabled()`) gating.
6. **Untouched proof:** 3b mint path, foreground line (daemon:5673), Slice-1 heartbeat unchanged by this slice.

If any proof refutes the design, STOP and patch the spec.

## Testing (TDD, hermetic — inject the clock, never sleep)

- **The truthful reader:** `time_sense_context()` returns a valid context on a fresh clock; returns **`None`
  on clock-degraded** (now < last anchor) **without writing** any `clock_degraded_event`; returns `None` when
  the only `owner_contact` rows are canary/test (`is_canary=1`); excludes canary rows from "last contact."
- **Feed:** present-with-both-flags (line contains exact elapsed since contact + the phrase); absent flag-off
  (byte-identical); absent when the context is `None` (degraded / no contact) — honest null; **non-imperative**
  (assert no directive language); exact-elapsed is since-last-**contact**, not since-last-anchor.
- **Stamp:** additive migration (old rows readable, NULL felt-*); stamped-when-on (row has the four values
  from the context); null-when-off / null-when-context-`None`; **value-from-context-not-model**; stamped
  across multiple `source_kind`s (every EpisodeStore episode); no durable band column exists.
- **Regression:** foreground felt-time line unchanged; 3b mint unchanged; Slice-1 heartbeat/anchors unchanged;
  `cycle_packet.py` unchanged (felt-time wired in the daemon, not the packet builder).

## Scope guard

**IN:** the read-only `time_sense_context()` helper (the truthful reader: valid context or `None`, degraded →
`None`, canary-excluded contact read) + the Feed (autonomous focused-cognition perception line) + the Stamp
(`EpisodeStore` four columns) + their two flags + tests.

**OUT (later slices / never):** coupling frictions to agency / drive-aware waking (**Slice 3**); learning
Rohit's rhythm/habits (**Slice 4**); stamping `private_thoughts`/raw-memory/other stores (**later**, unless
Task 0 proves safe in-slice); any durable band/bucket/threshold; any hardcoded time-triggered behavior; the
doorman gate; the legacy `_reason` megaprompt path; foreground reply enrichment; new senses; world-facing
actions; any sentience/feeling claim; performed emotion.

## Owner-breath (after both-lanes PASS + merge — owner-sovereign)

No new secret. Set `MAEZ_TIME_SENSE_FEED=1` and/or `MAEZ_TIME_SENSE_STAMP=1` in the daemon env (substrate
already on); restart `maez`; witness: (feed) a self-initiated cycle thought that references the passing time
as perception, exact-elapsed honest, no directive; (stamp) a freshly-written episode row carrying
`felt_value`/`felt_elapsed_s`/`felt_phrase`/`felt_compute_version`, null when a flag is off.
