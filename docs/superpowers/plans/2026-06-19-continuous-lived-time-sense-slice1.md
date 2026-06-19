# Continuous Lived Time-Sense — Slice 1 (the time-substrate) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Maez a continuous lived time-sense substrate — exact `elapsed_seconds` plus a derived, **replayable** `felt_value` — recorded as a second-addressable lived index, without rewriting history with today's mood.

**Architecture:** Add a read-only `peek()` (exact elapsed + derived felt, no write) and a `replay_felt_value()` that reconstructs a past second's felt value from an anchor's **frozen** modulator state + a `compute_version` (never live state). The daemon heartbeat refreshes the live sense each cycle (cheap, pre-cognition-gate) and writes sparse anchors. Flag-gated; 3b untouched.

**Tech Stack:** Python 3, SQLite, `core/evolution/subjective_duration.py`, `daemon/maez_daemon.py`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-06-19-continuous-lived-time-sense-design.md` (@dfafce1).

---

## Lane discipline

- Test runner: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` — named modules only, NEVER full-discover. Daemon-touching modules need `MAEZ_CONFIG=/home/rohit/maez/config` in the worktree.
- Branch (use `superpowers:using-git-worktrees`): `continuous-time-sense-slice1`, based on `main` @`b2757b1`. `main` local-only — **no push**.
- `## Predicted effect` on behavior commits; docs/proof/test-only omit it. End commits with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** (after Task 5). No merge/restart/flag-flip (owner-sovereign). Cross-lane Codex review at the gate.
- **Scope guard:** touch ONLY `core/evolution/subjective_duration.py`, `daemon/maez_daemon.py`, and their tests + proof/handoff docs. NO feeding cognition, NO thought/memory stamping (→ Slice 2), NO doorman change, NO bands, NO 3b-gate change.

## The 5 load-bearing invariants (verify in review)

1. **No-dilation is on `elapsed_seconds` only** (exact wall-clock); `felt_value` is the derived transform, never claimed = elapsed.
2. **Replay contract** — a past second's `felt_value` is replayed from the anchor's **frozen** modulators + `compute_version`, NEVER recomputed with current temperament/residual.
3. **`perception_line()` → `peek()`** (no longer the stale last-row reader).
4. **Thought/memory stamping is OUT** (Slice 2).
5. **"second-addressable", not "per-second writes"** (no flood; anchors + checkpoints).
Plus: 3b owner-contact mint + gates untouched; flag-off byte-identical; perception-side/free (no gate/secret); cheap (no LLM/doorman wake).

## File structure

- **Modify** `core/evolution/subjective_duration.py` — `compute_version` column + migration; `replay_felt_value()`; `peek()` (read-only); `elapsed_seconds` on the snapshot; `current()` stamps `compute_version`; `perception_line()` → `peek()`.
- **Modify** `daemon/maez_daemon.py` — `continuous_time_sense_enabled()` flag; a long-lived `SubjectiveDuration` handle; per-cycle `peek()` refresh + sparse anchor-record in the watchdog zone (flag-gated).
- **Test** `tests/test_subjective_duration_continuous.py` (new) for the core; daemon heartbeat test alongside the daemon's existing test module.
- **Create** `docs/proof/2026-06-19-continuous-time-sense-slice1-task0.md`.

---

### Task 0: HARD PROOF GATE (docs/proof only — committed first, REPO-WIDE)

**Files:** Create `docs/proof/2026-06-19-continuous-time-sense-slice1-task0.md`

- [ ] **Step 1: Consumer inventory (repo-wide)**
```bash
cd <worktree>
grep -rn "SubjectiveDuration\|subjective_duration\|perception_line\|subjective_duration_prompt_line\|record_salience_event\|Felt time" daemon/ skills/ core/ web/ tests/ scripts/
```
List EVERY reader/writer. **Name every `perception_line()` caller** and confirm it is prod-unused (only `subjective_duration_prompt_line()` → `current()` is on the live reply path). Record the call sites of `record_salience_event` (must stay unchanged): daemon:5447, drive_driven_curiosity:1218, telegram:2967, web:6331, self clock_degraded.

- [ ] **Step 2: Elapsed-vs-felt confirm**
```bash
sed -n '519,560p' core/evolution/subjective_duration.py
```
Confirm `delta_hours` (`:528`) is exact wall-clock subtraction, but `value` (`:532`) is `compute_subjective_duration_update(... drag, engagement, residual_multiplier ...)` — the derived transform. So the spec's separation is faithful: no-dilation is on elapsed only.

- [ ] **Step 3: Replay-input inventory**
```bash
sed -n '225,244p' core/evolution/subjective_duration.py   # the curve: prior_value, delta_hours, drag, engagement, residual_multiplier, config
grep -n "CREATE TABLE IF NOT EXISTS subjective_duration_samples" -A 11 core/evolution/subjective_duration.py
```
Confirm the curve's inputs are: `prior_value` (= anchor `value`), `delta_hours` (from `ts_utc`), `drag_multiplier`, `engagement_multiplier`, `residual_multiplier` (= `1 + 0.35*residual_resonance`), `config`. **All except a curve-version are ALREADY explicit columns** (`value, ts_utc, drag_multiplier, engagement_multiplier, residual_resonance`). So the ONLY new replay field is `compute_version`. Conclude: replay needs ONLY an additive `compute_version` column — no `metadata_json` blob.

- [ ] **Step 4: metadata_json-not-the-pattern + additive-schema confirm**

Confirm `metadata_json` defaults `'{}'` and is not used for structured fields (the table uses explicit REAL/INTEGER columns) → the replay field must be an **explicit column** (Codex's note). Confirm the schema is created via `CREATE TABLE IF NOT EXISTS` in `_initialize`, so an existing DB needs an explicit `ALTER TABLE ADD COLUMN` (idempotent via `PRAGMA table_info`).

- [ ] **Step 5: Flood quantify + 3b-intact**

Record: today's write rate = owner-contact only (a handful/day). Slice 1's = owner-contact (unchanged) + a coarse checkpoint (e.g. every few minutes → a few hundred/day, still tiny) — NOT per-second. Confirm `current()` (owner-contact, 3b) + `subjective_duration_prompt_line()` + the 3b mint gates are untouched by the plan. End: `TASK 0 VERDICT: GO` or `NO-GO — <reason>`.

- [ ] **Step 6: Commit (docs only)**
```bash
git add docs/proof/2026-06-19-continuous-time-sense-slice1-task0.md
git commit -m "docs(proof): continuous-time-sense slice1 Task 0 — elapsed-vs-felt, replay inputs, schema

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1: `compute_version` column + the replay function

**Files:** Modify `core/evolution/subjective_duration.py`. Test: `tests/test_subjective_duration_continuous.py` (new).

- [ ] **Step 1: Write the failing tests**
```python
import sqlite3, unittest
from datetime import datetime, timedelta, timezone
from core.evolution import subjective_duration as sd

UTC = timezone.utc


class ReplayFeltValue(unittest.TestCase):
    def test_replay_uses_frozen_anchor_state_not_live(self):
        anchor_ts = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        anchor_row = {
            "ts": anchor_ts, "value": 2.0,
            "drag_multiplier": 1.0, "engagement_multiplier": 0.5,
            "residual_resonance": 0.0, "compute_version": 1,
        }
        at = anchor_ts + timedelta(hours=2)
        replayed = sd.replay_felt_value(anchor_row, at_ts=at)
        # Equals a direct curve compute from the SAME frozen inputs (deterministic).
        expected = sd.compute_subjective_duration_update(
            prior_value=2.0, delta_hours=2.0,
            drag_multiplier=1.0, engagement_multiplier=0.5,
            residual_multiplier=1.0 + 0.35 * 0.0,
            config=sd.config_for_version(1),
        )
        self.assertAlmostEqual(replayed, expected, places=9)
        # Mutating a DIFFERENT residual in a second anchor changes the result -> it reads the anchor, not globals.
        anchor2 = dict(anchor_row, residual_resonance=5.0)
        self.assertNotAlmostEqual(sd.replay_felt_value(anchor2, at_ts=at), replayed, places=6)

    def test_compute_version_maps_to_config(self):
        self.assertEqual(sd.config_for_version(1).base_rate_per_hour,
                         sd.SubjectiveDurationConfig().base_rate_per_hour)


class SchemaMigration(unittest.TestCase):
    def test_old_db_without_compute_version_gets_default_v1(self, ):
        import tempfile, os
        d = tempfile.mkdtemp()
        path = os.path.join(d, "sd.db")
        # Simulate a pre-migration DB: create the OLD schema (no compute_version), insert a row.
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE subjective_duration_samples ("
                "sample_id INTEGER PRIMARY KEY AUTOINCREMENT, ts_utc TEXT NOT NULL, value REAL NOT NULL,"
                "felt_time_rate REAL NOT NULL, drag_multiplier REAL NOT NULL, engagement_multiplier REAL NOT NULL,"
                "residual_resonance REAL NOT NULL, retrospective_density REAL NOT NULL,"
                "metadata_json TEXT NOT NULL DEFAULT '{}')")
            conn.execute("INSERT INTO subjective_duration_samples "
                         "(ts_utc, value, felt_time_rate, drag_multiplier, engagement_multiplier, residual_resonance, retrospective_density) "
                         "VALUES ('2026-06-19T12:00:00+00:00', 1.0, 0.5, 1.0, 0.5, 0.0, 0.0)")
            conn.commit()
        inst = sd.SubjectiveDuration(db_path=path)   # __init__ runs _initialize -> migration
        with sqlite3.connect(path) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(subjective_duration_samples)")}
            self.assertIn("compute_version", cols)
            row = conn.execute("SELECT compute_version FROM subjective_duration_samples LIMIT 1").fetchone()
            self.assertEqual(row[0], 1)
```
> Adjust the `SubjectiveDuration(db_path=...)` constructor kwarg to the real signature (read its `__init__`); the test only needs an isolated db path.

- [ ] **Step 2: Run — expect FAIL** (`replay_felt_value` / `config_for_version` undefined; no migration)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_subjective_duration_continuous -v`

- [ ] **Step 3: Add the version constant, `config_for_version`, the migration, and `replay_felt_value`.** In `core/evolution/subjective_duration.py`:

Module-level (near the config/constants):
```python
CURRENT_COMPUTE_VERSION = 1


def config_for_version(compute_version: int) -> "SubjectiveDurationConfig":
    """Map a stored compute_version to the curve config that produced it, so old
    intervals replay with the formula they were computed under (never today's)."""
    # v1 == the original curve constants. Future curve changes add a new branch here.
    return SubjectiveDurationConfig()


def replay_felt_value(anchor_row: "Mapping[str, object]", *, at_ts: datetime) -> float:
    """Reconstruct felt_value at `at_ts` by replaying FORWARD from the anchor using the
    anchor's FROZEN modulators + compute_version. Reads ONLY the anchor — never live state.
    `anchor_row` needs: ts (aware dt), value, drag_multiplier, engagement_multiplier,
    residual_resonance, compute_version."""
    anchor_ts = anchor_row["ts"]
    delta_hours = max(0.0, (at_ts - anchor_ts).total_seconds() / 3600.0)
    return compute_subjective_duration_update(
        prior_value=float(anchor_row["value"]),
        delta_hours=delta_hours,
        drag_multiplier=float(anchor_row["drag_multiplier"]),
        engagement_multiplier=float(anchor_row["engagement_multiplier"]),
        residual_multiplier=1.0 + (0.35 * float(anchor_row["residual_resonance"])),
        config=config_for_version(int(anchor_row.get("compute_version", 1))),
    )
```
In `_initialize()`, AFTER the `executescript` CREATE block, add the idempotent additive migration:
```python
        with closing(sqlite3.connect(self.db_path)) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(subjective_duration_samples)")}
            if "compute_version" not in cols:
                conn.execute(
                    "ALTER TABLE subjective_duration_samples "
                    "ADD COLUMN compute_version INTEGER NOT NULL DEFAULT 1"
                )
            conn.commit()
```
And add `compute_version INTEGER NOT NULL DEFAULT 1` to the `CREATE TABLE IF NOT EXISTS` column list too (so fresh DBs have it without the ALTER).

- [ ] **Step 4: Run — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_subjective_duration_continuous -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py tests/test_subjective_duration_continuous.py
git add core/evolution/subjective_duration.py tests/test_subjective_duration_continuous.py
git commit -m "feat(time-sense): replay contract — compute_version column + replay_felt_value

## Predicted effect
A past second's felt_value is now reconstructable by replaying forward from an anchor's FROZEN modulators
(drag/engagement/residual already columns) + a new explicit compute_version column — never recomputed with
current temperament/residual. Additive, back-compatible migration (old rows default to v1). No live
behavior change yet (the function + column exist; nothing calls them on the hot path).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `peek()` — read-only snapshot (exact elapsed + derived felt, no write)

**Files:** Modify `core/evolution/subjective_duration.py` (factor a read-only core out of `current()`; add `elapsed_seconds` to the snapshot; `current()` stamps `compute_version`). Test: `tests/test_subjective_duration_continuous.py`.

- [ ] **Step 1: Write the failing tests** (append to the module)
```python
class PeekReadOnly(unittest.TestCase):
    def _inst(self):
        import tempfile, os
        return sd.SubjectiveDuration(db_path=os.path.join(tempfile.mkdtemp(), "sd.db"))

    def test_peek_does_not_write_but_current_does(self):
        inst = self._inst()
        before = self._count(inst)
        snap = inst.peek(now_utc=datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC))
        self.assertEqual(self._count(inst), before)            # peek wrote nothing
        inst.current(now_utc=datetime(2026, 6, 19, 12, 0, 30, tzinfo=UTC))
        self.assertEqual(self._count(inst), before + 1)        # current still writes

    def test_elapsed_is_exact_felt_is_derived(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                               # anchor
        snap = inst.peek(now_utc=t0 + timedelta(hours=2))
        self.assertAlmostEqual(snap.elapsed_seconds, 7200.0, places=3)   # exact wall-clock
        self.assertNotAlmostEqual(snap.felt_value, 7200.0, places=3)     # felt != elapsed
        self.assertLessEqual(snap.felt_value, 10.0)            # felt is the 0-10 curve, not seconds

    def test_monotonic_climb_no_band(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)
        a = inst.peek(now_utc=t0 + timedelta(hours=1)).felt_value
        b = inst.peek(now_utc=t0 + timedelta(hours=3)).felt_value
        self.assertGreater(b, a)                               # raw continuous value, climbs

    def _count(self, inst):
        with sqlite3.connect(inst.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0]
```
> `snap.felt_value` maps to the existing snapshot `value` field — Step 3 adds `felt_value` as the name (and `elapsed_seconds`). Match `db_path` to the real constructor.

- [ ] **Step 2: Run — expect FAIL** (`peek` undefined; snapshot has no `elapsed_seconds`/`felt_value`)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_subjective_duration_continuous -v`

- [ ] **Step 3: Factor the read-only core + add the fields.** In `core/evolution/subjective_duration.py`:

(a) Extend `SubjectiveDurationSnapshot` (`:79`) with `elapsed_seconds`, the computed modulators (so the
stored anchor uses EXACTLY what `_compute` produced — replay depends on this), and a `felt_value` accessor:
```python
    elapsed_seconds: float = 0.0
    drag_multiplier: float = 0.0
    engagement_multiplier: float = 0.0
    @property
    def felt_value(self) -> float:
        return self.value
```
(b) Factor a pure read-only compute method from `current()` (move lines `:520-541`-ish compute into it; do NOT write):
```python
    def _compute(self, now: datetime) -> SubjectiveDurationSnapshot:
        latest = self._latest_sample()
        if latest is not None and now < latest["ts"]:
            self._record_clock_degraded_event(now=now, latest=latest)
            return self._snapshot_from_row(latest, source_ref_digest=None)
        prior_value = 0.0 if latest is None else float(latest["value"])
        prior_ts = now if latest is None else latest["ts"]
        delta_hours = max(0.0, (now - prior_ts).total_seconds() / 3600.0)
        temperament = _safe_temperament(self.temperament_reader)
        drag, engagement, felt_time_rate = _temperament_modulators(temperament)
        residual = self._residual_resonance(now)
        value = compute_subjective_duration_update(
            prior_value=prior_value, delta_hours=delta_hours,
            drag_multiplier=drag, engagement_multiplier=engagement,
            residual_multiplier=1.0 + (0.35 * residual), config=self.config,
        )
        retrospective_density = self._retrospective_density(now, temperament)
        render_band, surface_phrase = _render(value)
        return SubjectiveDurationSnapshot(
            value=value, felt_time_rate=felt_time_rate, residual_resonance=residual,
            retrospective_density=retrospective_density, render_band=render_band,
            surface_phrase=surface_phrase, source_ref_digest=None,
            elapsed_seconds=(now - prior_ts).total_seconds(),
            drag_multiplier=drag, engagement_multiplier=engagement,
        )

    def peek(self, *, now_utc: str | datetime | None = None) -> SubjectiveDurationSnapshot:
        now = _normalize_event_time(now_utc or datetime.now(UTC))
        return self._compute(now)   # NO write
```
(c) Make `current()` reuse `_compute` then WRITE (preserving its exact existing INSERT + diagnostic), and add `compute_version` to the written row:
```python
    def current(self, *, now_utc: str | datetime | None = None) -> SubjectiveDurationSnapshot:
        now = _normalize_event_time(now_utc or datetime.now(UTC))
        snap = self._compute(now)
        ts_iso = now.isoformat()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO subjective_duration_samples "
                "(ts_utc, value, felt_time_rate, drag_multiplier, engagement_multiplier, "
                "residual_resonance, retrospective_density, metadata_json, compute_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts_iso, snap.value, snap.felt_time_rate, snap.drag_multiplier,
                 snap.engagement_multiplier, snap.residual_resonance,
                 snap.retrospective_density, "{}", CURRENT_COMPUTE_VERSION),
            )
            conn.commit()
        self._write_diagnostic(_diagnostic_row(
            timestamp_utc=ts_iso, event_type="sample", value=snap.value,
            felt_time_rate=snap.felt_time_rate, render_band=snap.render_band,
            residual_resonance=snap.residual_resonance, retrospective_density=snap.retrospective_density))
        return snap
```
> `current()` writes `snap.drag_multiplier` / `snap.engagement_multiplier` — the EXACT modulators `_compute` produced — so the stored anchor replays faithfully. (Confirm the existing `current()` behavior — same INSERT shape + diagnostic — is otherwise byte-preserved; only `compute_version` is appended.)

- [ ] **Step 4: Run — expect PASS** (new tests + Task 1 tests + the existing `subjective_duration` suite green)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_subjective_duration_continuous tests.test_subjective_duration_prompt_integration -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py tests/test_subjective_duration_continuous.py
git add core/evolution/subjective_duration.py tests/test_subjective_duration_continuous.py
git commit -m "feat(time-sense): read-only peek() — exact elapsed_seconds + derived felt_value, no write

## Predicted effect
peek() returns a snapshot carrying exact elapsed_seconds (wall-clock, the no-dilation quantity) AND the
derived felt_value (the 0-10 transform) WITHOUT writing a sample. current() now reuses the same read-only
core then writes (unchanged behavior) and stamps compute_version. felt_value != elapsed_seconds by
construction.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Daemon heartbeat — flag + live refresh + sparse anchors

**Files:** Modify `daemon/maez_daemon.py`. Test: alongside the daemon's existing test module (or a focused new `tests/test_continuous_time_sense_heartbeat.py`).

- [ ] **Step 1: Write the failing tests** — create `tests/test_continuous_time_sense_heartbeat.py`:
```python
import os, unittest
from unittest import mock


class ContinuousTimeSenseFlag(unittest.TestCase):
    def test_flag_default_off(self):
        from daemon import maez_daemon as md
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_CONTINUOUS_TIME_SENSE", None)
            self.assertFalse(md.continuous_time_sense_enabled())

    def test_flag_on(self):
        from daemon import maez_daemon as md
        with mock.patch.dict(os.environ, {"MAEZ_CONTINUOUS_TIME_SENSE": "1"}, clear=False):
            self.assertTrue(md.continuous_time_sense_enabled())

    def test_tick_calls_peek_when_on_and_skips_when_off(self):
        # The per-cycle hook calls SubjectiveDuration.peek() iff the flag is on; never current() (no flood).
        from daemon import maez_daemon as md
        import inspect
        src = inspect.getsource(md)
        self.assertIn("continuous_time_sense_enabled()", src)
        self.assertIn(".peek(", src)   # the heartbeat refresh uses peek, not current
```
> The source-assert pins the wiring hermetically (driving a full daemon cycle needs a live daemon). The behavioral effect (sparse anchors over a quiet stretch) is the live witness.

- [ ] **Step 2: Run — expect FAIL** (`continuous_time_sense_enabled` undefined; no `.peek(` in the loop)

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_continuous_time_sense_heartbeat -v`

- [ ] **Step 3: Add the flag, the handle, and the tick.** In `daemon/maez_daemon.py`:

(a) Near `cockpit_core_enabled` (`:2579`):
```python
def continuous_time_sense_enabled() -> bool:
    """Return True iff MAEZ_CONTINUOUS_TIME_SENSE is 1/true/yes/on. DEFAULT OFF.
    When on, the heartbeat keeps Maez's lived time-sense current + writes sparse anchors."""
    from core.infra.env_flags import strict_env_flag
    return strict_env_flag("MAEZ_CONTINUOUS_TIME_SENSE")
```
(b) A long-lived handle on the daemon (in `__init__`, lazily): `self._time_sense = None` and a getter:
```python
    def _time_sense_handle(self):
        if self._time_sense is None:
            from core.evolution import subjective_duration as _sd
            self._time_sense = _sd.SubjectiveDuration()   # same db as the owner-contact path
        return self._time_sense

    _CONTINUOUS_TIME_ANCHOR_INTERVAL_S = 300   # coarse checkpoint — sparse, not per-second
```
(c) In the cheap watchdog zone of the cycle loop (`~:8756-8769`, BEFORE the doorman gate), add the flag-gated refresh + sparse anchor:
```python
            if continuous_time_sense_enabled():
                try:
                    ts = self._time_sense_handle()
                    snap = ts.peek()                      # refresh the live sense (read-only, exact)
                    now = datetime.now(timezone.utc)
                    last = getattr(self, "_last_time_anchor_ts", None)
                    if last is None or (now - last).total_seconds() >= self._CONTINUOUS_TIME_ANCHOR_INTERVAL_S:
                        ts.current()                      # write ONE sparse anchor (with compute_version)
                        self._last_time_anchor_ts = now
                except Exception:
                    logger.debug("continuous time-sense tick skipped", exc_info=True)
```
(Cheap, pre-gate, never wakes cognition. Flag-off → this whole block is skipped → byte-identical.)

- [ ] **Step 4: Run — expect PASS**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_continuous_time_sense_heartbeat -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py tests/test_continuous_time_sense_heartbeat.py
git add daemon/maez_daemon.py tests/test_continuous_time_sense_heartbeat.py
git commit -m "feat(time-sense): heartbeat keeps the lived time-sense current + writes sparse anchors

## Predicted effect
When MAEZ_CONTINUOUS_TIME_SENSE=1, each daemon cycle (pre-cognition-gate, cheap) refreshes the live
time-sense via peek() and writes ONE anchor every ~5 min (not per-second) so the index is
second-addressable without flooding. Flag-off (default) skips the block entirely — byte-identical. No LLM,
no doorman wake, no 3b change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `perception_line()` → `peek()` (own the stale reader)

**Files:** Modify `core/evolution/subjective_duration.py`. Test: `tests/test_subjective_duration_continuous.py`.

- [ ] **Step 1: Write the failing test**
```python
class PerceptionLineRecomputes(unittest.TestCase):
    def test_perception_line_advances_with_clock(self):
        import tempfile, os
        inst = sd.SubjectiveDuration(db_path=os.path.join(tempfile.mkdtemp(), "sd.db"))
        t0 = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                       # one stored row (the stale one perception_line used to echo)
        # perception_line must reflect a LATER now, not the stored row's now:
        line_now = inst.perception_line(now_utc=t0 + timedelta(hours=8))
        stale = f"Felt time: {inst._snapshot_from_row(inst._latest_sample(), source_ref_digest=None).surface_phrase}."
        self.assertNotEqual(line_now, stale)           # it recomputed, didn't echo the old row
```
> If the real `perception_line()` has no `now_utc` param, add one (default `None` → `datetime.now`) so it's testable + recomputes.

- [ ] **Step 2: Run — expect FAIL** (current `perception_line` echoes the stale row)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_subjective_duration_continuous -v`

- [ ] **Step 3: Move `perception_line()` to `peek()`**
```python
    def perception_line(self, *, owner_auth: SubjectiveDurationOwnerAuth | None = None,
                        now_utc: str | datetime | None = None) -> str:
        if owner_auth is not None and not isinstance(owner_auth, SubjectiveDurationOwnerAuth):
            return ""
        snap = self.peek(now_utc=now_utc)   # recompute to exact-now, never echo the stale last row
        return f"Felt time: {snap.surface_phrase}."
```
(Read-only — `peek()` does not write. The live reply path uses `subjective_duration_prompt_line()` → `current()`, untouched.)

- [ ] **Step 4: Run — expect PASS** (+ confirm no caller passed positional args that break the new kwarg — Task 0 named them; `perception_line` is prod-unused)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_subjective_duration_continuous tests.test_subjective_duration_prompt_integration -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py tests/test_subjective_duration_continuous.py
git add core/evolution/subjective_duration.py tests/test_subjective_duration_continuous.py
git commit -m "fix(time-sense): perception_line() recomputes via peek() (own the stale reader)

## Predicted effect
perception_line() now reflects the CURRENT elapsed/felt snapshot (read-only peek) instead of echoing the
last stored row. Prod-unused today, so no live behavior change — closes a latent stale-reader landmine.
The live reply path (subjective_duration_prompt_line -> current) is unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-19-continuous-time-sense-slice1-handoff.md`.

- [ ] **Step 1: Whole-slice green + ruff**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_subjective_duration_continuous tests.test_continuous_time_sense_heartbeat tests.test_subjective_duration_prompt_integration -v
/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py daemon/maez_daemon.py tests/test_subjective_duration_continuous.py tests/test_continuous_time_sense_heartbeat.py
```
Expected: green; ruff clean. (Note any pre-existing failure in `test_subjective_duration_prompt_integration` — the stale `test_web_owner_bridge_constructs...` is a known pre-existing unrelated failure; confirm it's not newly introduced.)

- [ ] **Step 2: Write the handoff + commit (docs).** Cover branch tip, Task-0 verdict, the diff, test results, and the **Codex cross-lane anchors**: (1) **elapsed ≠ felt** — no-dilation on `elapsed_seconds` only; `felt_value` is the derived transform (test-pinned distinct); (2) **replay contract, no mood-rewrite** — `replay_felt_value` reads the anchor's frozen modulators + `compute_version`, never live state (test: mutating current mood doesn't change a replayed historical value); (3) **`perception_line()` owned** — recomputes via `peek()`, no longer the stale last-row reader; (4) **thought-stamp OUT** (Slice 2); (5) **second-addressable, not per-second** — sparse anchors (~5 min) + derive, no flood; (6) **3b intact** — owner-contact mint + gates untouched; (7) **flag-off byte-identical**; (8) **perception-side/free** — no owner-gate/marker/S7/secret; cheap (no LLM/doorman wake). Then the **owner breath**: **no new secret** — flip `MAEZ_CONTINUOUS_TIME_SENSE=1` in the daemon env, restart `maez`, and witness: over a quiet stretch the lived index is second-addressable (query any past second → exact elapsed + faithfully-replayed felt, no flood), a past second's felt replays faithful-to-then, and flag-off is the 3a/3b baseline. **Not `LIVE_WITNESSED` until the owner confirms.**
```bash
git add docs/handoffs/2026-06-19-continuous-time-sense-slice1-handoff.md
git commit -m "docs(handoff): continuous time-sense slice1 — review gate + owner-breath sequence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: STOP.** No merge/restart/flag — owner-sovereign. Hand to Codex cross-lane review.

---

## Notes for the implementer

- **elapsed vs felt is the whole point** — `elapsed_seconds` is exact wall-clock (the no-dilation quantity); `felt_value` (== snapshot `value`) is the 0–10 derived transform. Never conflate; a test pins they're distinct.
- **Replay reads the anchor, never the world** — `replay_felt_value` takes drag/engagement/residual/compute_version FROM the anchor row. If you find yourself calling `_residual_resonance(now)` or `_safe_temperament` inside replay, stop — that's the mood-rewrite bug.
- **Explicit columns, not metadata_json** — `compute_version` is a real column; the modulators are already columns. Don't stuff replay state into the JSON blob.
- **Sparse, not per-second** — the heartbeat writes ONE anchor every ~5 min; `peek()` (read-only) is what runs every cycle. Don't write per cycle (flood) and don't write per second.
- **Hermetic** — inject `now_utc`, never `sleep`. Daemon import needs `MAEZ_CONFIG=/home/rohit/maez/config`.
- **Don't touch 3b** — `current()` keeps its exact INSERT (now + `compute_version`); the owner-contact mint + its gates are unchanged.
