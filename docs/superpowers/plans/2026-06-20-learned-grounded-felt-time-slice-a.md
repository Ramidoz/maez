# Learned, Grounded Felt-Time — Slice A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only rhythm-facts reader (learned from real owner-contact gaps) BESIDE the old curve, add dedicated `rhythm_*` episode columns, and repoint the cycle feed + episode stamp to the rhythm facts behind a new `MAEZ_RHYTHM_FELT_TIME` flag — facts, never a verdict.

**Architecture:** A new `SubjectiveDuration.rhythm_context()` emits raw facts (gaps/medians/percentile/counts/IQR) or `None`. A new flag selects the *content source* (curve vs rhythm); the existing `FEED`/`STAMP` flags stay the *mouths*. The stamp gains a second injected `rhythm_reader`; the feed line becomes source-aware. The old curve, `time_sense_context`, `felt_*` columns, foreground, and 3b mint are untouched (Slice B/C later).

**Tech Stack:** Python 3, SQLite, `unittest`, stdlib `statistics` (NO numpy). Spec: `docs/superpowers/specs/2026-06-20-learned-grounded-felt-time-design.md` (@98106ef).

---

## Lane discipline (every task)

- **Worktree/branch:** created via superpowers:using-git-worktrees. Branch **`learned-felt-time-slice-a`**. `main` local-only — **NO push**.
- **GIT HYGIENE (worktrees have had ref instability):** NO `git checkout`/`switch`/`reset`/`rebase`. Only edit/test/`git add`/`git commit`. After every commit, `git status` MUST show **`On branch learned-felt-time-slice-a`**. If "detached HEAD" → **STOP and report**.
- **Test runner (named modules ONLY):** `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v`
- **Commits:** behavior commits carry `## Predicted effect`; docs/proof/test-only don't. End every commit with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** after Task 5 — no merge/restart/flag-flip (owner-sovereign). Cross-lane Codex review at the gate.

## The load-bearing invariants (reviewers verify)

1. **No verdict in the substrate** — `rhythm_context` emits facts only; no label/band/phrase/feeling.
2. **No expression-gate** — the feed line is produced whenever rhythm+feed+substrate are on and a context exists; it states the facts (even for a SHORT gap), never withholds on a threshold.
3. **Learned only from REAL contacts** — canary/`manual_test`/scratch excluded (reuse `REAL_OWNER_CONTACT_AUTH_CLASSES`).
4. **Honest cold-start** — below the data floor the comparison facts are `None`; `current_gap_s` + counts may be present; never a fabricated stat.
5. **Truthful-reader `None`** on clock-degraded or no real contact — never a frozen clock as alive.
6. **Separate boxes** — rhythm writes ONLY `rhythm_*`; `felt_*` left NULL when rhythm on; never overload `felt_value`/`felt_phrase`.
7. **Flag-off behavior-identical** — `MAEZ_RHYTHM_FELT_TIME` default OFF → Slice-2 paths byte-identical; new columns additive + inert.
8. **Mouths vs source** — the flag matrix exactly (rhythm = source; FEED/STAMP = mouths).
9. **Untouched:** the curve, `time_sense_context`, `felt_*` reads, foreground line (daemon ~:5740 `subjective_duration_prompt_line`), 3b mint, Slice-1 heartbeat, `core/cognition/cycle_packet.py`.
10. **Not LLM-owned** — facts come from the substrate, never the model.

## File structure

| File | Change |
|---|---|
| `core/evolution/subjective_duration.py` | **Modify** — `rhythm_context()` + pure helpers (`_gaps_seconds`, `_percentile_strictly_below`, `_iqr`) + `_real_owner_contact_timestamps()` + constants |
| `core/memory/episodes.py` | **Modify** — 8 `rhythm_*` columns + migration + second injected `rhythm_reader` + stamp in `add()` |
| `daemon/maez_daemon.py` | **Modify** — `time_sense_rhythm_enabled()`, `_episode_rhythm_reader`, gate `_episode_felt_time_reader` off when rhythm on, source-aware `_cycle_feed_time_sense_line`, `_format_rhythm_line`, inject the rhythm reader |
| `tests/test_rhythm_context.py` | **Create** — reader math + cold-start + exclusions + degraded |
| `tests/test_rhythm_stamp.py` | **Create** — schema + two-reader matrix + NULL-semantics |
| `tests/test_rhythm_feed.py` | **Create** — source-aware feed + no-verdict + matrix |
| `docs/proof/2026-06-20-learned-felt-time-slice-a-task0.md` | **Create** — proof gate |
| `docs/handoffs/2026-06-20-learned-felt-time-slice-a-handoff.md` | **Create** — review-gate handoff |

---

### Task 0: Proof gate (docs/proof only — repo-wide, committed first)

**Files:** Create `docs/proof/2026-06-20-learned-felt-time-slice-a-task0.md`. NO code.

- [ ] **Step 1: Confirm the reader substrate.** `subjective_duration.py`: `_compute(now)` returns `(snapshot, degraded_latest)` (~:579); `REAL_OWNER_CONTACT_AUTH_CLASSES` (:60); `_seconds_since_last_owner_contact` query (~:642) — the pattern the all-contacts query mirrors; `humanize_elapsed` (:470); `_normalize_event_time`. Confirm `import statistics` is NOT yet present (it'll be added) and **numpy is not used** in the repo's hot path for this.
- [ ] **Step 2: Confirm the stamp + daemon wiring (current main line numbers).** `episodes.py`: `__init__(felt_time_reader=...)` (:100), the `add()` stamp block (:143-184), `_MIGRATIONS` (:68), `_row_to_dict` is `SELECT *`/`dict(row)` (~:321 — new columns surface automatically). `maez_daemon.py`: `continuous_time_sense_enabled` (:2621), `time_sense_stamp_enabled` (:2630), `time_sense_feed_enabled` (:2638), `_format_time_sense_line` (:2473), `_episode_felt_time_reader` (:2898), `_cycle_feed_time_sense_line` (:2909), the `EpisodeStore(...)` construction (:2971).
- [ ] **Step 3: THE NULL-SEMANTICS CHECK (owner's must-do).** Grep EVERY reader of `felt_value` / `felt_phrase` / `felt_elapsed_s` / `felt_compute_version` across the repo. For each consumer, confirm it does NOT treat "`felt_*` IS NULL" as "no time context" in a way that would misread a rhythm-stamped row (where `felt_*` is NULL by design but `rhythm_*` is set). Name each consumer + its verdict (safe / needs-rhythm-awareness-later). If any consumer would misread, record it as a **Slice-B follow-up** (Slice A doesn't repoint those readers) — but it must be NAMED, not silent.
- [ ] **Step 4: Confirm untouched surfaces.** Foreground `subjective_duration_prompt_line` (daemon ~:5740), 3b owner-contact mint, the Slice-1 heartbeat block, `cycle_packet.py` — none modified by this slice.
- [ ] **Step 5: VERDICT** `GO` or `REFUTED: <what + which task>`. Record any line-number drift for later tasks.
- [ ] **Step 6: Commit (docs/proof — no predicted-effect).**
```bash
git add docs/proof/2026-06-20-learned-felt-time-slice-a-task0.md
git commit -m "docs(proof): learned felt-time Slice A Task 0 — reader substrate, stamp/daemon wiring, NULL-semantics consumer check

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch learned-felt-time-slice-a
```

---

### Task 1: `rhythm_context()` — the learned-facts reader

**Files:** Modify `core/evolution/subjective_duration.py`; Create `tests/test_rhythm_context.py`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_rhythm_context.py`:

```python
import os, sqlite3, tempfile, unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from core.evolution import subjective_duration as sd

UTC = timezone.utc


def _insert_contact(db_path, *, ts, is_canary=0, owner_auth_class="cockpit"):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT INTO subjective_duration_salience_events "
            "(ts_utc, salience_event_kind, owner_auth_class, is_canary) VALUES (?,?,?,?)",
            (ts.isoformat(), "owner_contact", owner_auth_class, is_canary))
        conn.commit()


class RhythmContext(unittest.TestCase):
    def _inst(self):
        return sd.SubjectiveDuration(db_path=os.path.join(tempfile.mkdtemp(), "sd.db"))

    def _contacts(self, inst, base, gaps_minutes):
        # build contacts so consecutive gaps == gaps_minutes (in order)
        t = base
        _insert_contact(inst.db_path, ts=t)
        for g in gaps_minutes:
            t = t + timedelta(minutes=g)
            _insert_contact(inst.db_path, ts=t)
        return t  # latest contact

    def test_facts_math_on_known_gaps(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [10, 20, 30, 40, 50])     # 5 gaps: 10,20,30,40,50 min
        now = last + timedelta(minutes=60)                        # current gap = 60 min
        ctx = inst.rhythm_context(now=now)
        self.assertIsNotNone(ctx)
        self.assertAlmostEqual(ctx["rhythm_current_gap_s"], 3600.0, places=1)
        self.assertEqual(ctx["rhythm_all_time_sample_count"], 5)
        self.assertAlmostEqual(ctx["rhythm_all_time_gap_median_s"], 30 * 60, places=1)   # median(10,20,30,40,50)=30
        # 60min current gap is longer than ALL 5 historical gaps -> 100th percentile
        self.assertAlmostEqual(ctx["rhythm_current_gap_percentile_all_time"], 100.0, places=1)

    def test_percentile_is_continuous_not_a_band(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [10, 20, 30, 40])         # gaps 10,20,30,40
        # current gap 25min is longer than 2 of 4 (10,20) -> 50%
        ctx = inst.rhythm_context(now=last + timedelta(minutes=25))
        self.assertAlmostEqual(ctx["rhythm_current_gap_percentile_all_time"], 50.0, places=1)

    def test_recent_window_limits_recent_count(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [5] * 30)                 # 30 gaps
        ctx = inst.rhythm_context(now=last + timedelta(minutes=5))
        self.assertEqual(ctx["rhythm_all_time_sample_count"], 30)
        self.assertEqual(ctx["rhythm_recent_sample_count"], sd.RHYTHM_RECENT_WINDOW)   # capped at K

    def test_cold_start_comparison_facts_none_but_current_gap_present(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [10])                     # only 1 gap (< floor)
        ctx = inst.rhythm_context(now=last + timedelta(minutes=15))
        self.assertIsNotNone(ctx)
        self.assertAlmostEqual(ctx["rhythm_current_gap_s"], 15 * 60, places=1)          # present
        self.assertIsNone(ctx["rhythm_all_time_gap_median_s"])                          # not enough data
        self.assertIsNone(ctx["rhythm_current_gap_percentile_all_time"])
        self.assertEqual(ctx["rhythm_all_time_sample_count"], 1)

    def test_none_when_no_real_contact(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                                  # a sample, but NO owner_contact row
        self.assertIsNone(inst.rhythm_context(now=t0 + timedelta(hours=1)))

    def test_excludes_canary_and_manual_test(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        _insert_contact(inst.db_path, ts=t0, owner_auth_class="cockpit")               # real
        _insert_contact(inst.db_path, ts=t0 + timedelta(hours=1), is_canary=1)         # canary
        _insert_contact(inst.db_path, ts=t0 + timedelta(hours=2), owner_auth_class="manual_test")  # scratch
        ctx = inst.rhythm_context(now=t0 + timedelta(hours=3))
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["rhythm_all_time_sample_count"], 0)   # only 1 REAL contact -> 0 gaps
        # current gap measured from the REAL contact (t0), not the manual_test at t0+2h
        self.assertAlmostEqual(ctx["rhythm_current_gap_s"], 3 * 3600, places=1)

    def test_none_on_clock_degraded_without_writing(self):
        inst = self._inst()
        t1 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t1)
        _insert_contact(inst.db_path, ts=t1)
        with closing(sqlite3.connect(inst.db_path)) as c:
            s_before = c.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0]
            e_before = c.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0]
        self.assertIsNone(inst.rhythm_context(now=t1 - timedelta(hours=1)))   # backward clock
        with closing(sqlite3.connect(inst.db_path)) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0], s_before)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0], e_before)

    def test_current_gap_climbs_with_now(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [10, 20, 30])
        a = inst.rhythm_context(now=last + timedelta(hours=1))["rhythm_current_gap_s"]
        b = inst.rhythm_context(now=last + timedelta(hours=3))["rhythm_current_gap_s"]
        self.assertGreater(b, a)   # unlike the pinned curve, this VARIES
```

- [ ] **Step 2: Run, expect RED.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_rhythm_context -v`
  Expected: FAIL — `rhythm_context` / `RHYTHM_RECENT_WINDOW` undefined.

- [ ] **Step 3: Implement.** In `core/evolution/subjective_duration.py`: add `import statistics` (with the other stdlib imports), the constants + pure helpers (module-level, near `humanize_elapsed`), and the methods on `SubjectiveDuration` (place `rhythm_context` + `_real_owner_contact_timestamps` right after `_seconds_since_last_owner_contact`).

```python
RHYTHM_RECENT_WINDOW = 20      # transparency knob (surfaced via recent_sample_count); NOT a feeling-decision
RHYTHM_MIN_GAPS = 3            # data-sufficiency floor for comparison facts; below it -> None (honest cold-start)


def _gaps_seconds(timestamps: "list[datetime]") -> "list[float]":
    ts = sorted(timestamps)
    return [(ts[i] - ts[i - 1]).total_seconds() for i in range(1, len(ts))]


def _percentile_strictly_below(value: float, population: "list[float]") -> "float | None":
    if not population:
        return None
    return 100.0 * sum(1 for g in population if g < value) / len(population)


def _iqr(values: "list[float]") -> "float | None":
    if len(values) < 2:
        return None
    q = statistics.quantiles(values, n=4)   # [Q1, Q2, Q3]
    return q[2] - q[0]
```

```python
    def _real_owner_contact_timestamps(self) -> "list[datetime]":
        """All REAL owner_contact timestamps (canary/manual_test/scratch excluded), chronological."""
        classes = tuple(sorted(REAL_OWNER_CONTACT_AUTH_CLASSES))
        placeholders = ",".join("?" for _ in classes)
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT ts_utc FROM subjective_duration_salience_events "
                "WHERE salience_event_kind = 'owner_contact' AND is_canary = 0 "
                f"AND owner_auth_class IN ({placeholders})",
                classes,
            ).fetchall()
        return sorted(_normalize_event_time(r[0]) for r in rows)

    def rhythm_context(self, *, now: str | datetime | None = None) -> dict | None:
        """Read-only LEARNED rhythm FACTS for Slice-A feed/stamp. Returns raw facts (no verdict/label/
        phrase) or None. None (no write) on clock-degraded or no real owner-contact reference. Comparison
        facts (medians/percentile/IQR) are None below RHYTHM_MIN_GAPS (honest cold-start)."""
        now_dt = _normalize_event_time(now or datetime.now(UTC))
        _snap, degraded_latest = self._compute(now_dt)
        if degraded_latest is not None:
            return None                          # clock-degraded -> absent (no write)
        contacts = self._real_owner_contact_timestamps()
        if not contacts:
            return None                          # no real owner-contact reference yet
        current_gap = (now_dt - contacts[-1]).total_seconds()
        if current_gap < 0:
            return None                          # contact after now -> no negative gap
        gaps = _gaps_seconds(contacts)
        recent = gaps[-RHYTHM_RECENT_WINDOW:]
        ctx = {
            "rhythm_current_gap_s": current_gap,
            "rhythm_recent_sample_count": len(recent),
            "rhythm_all_time_sample_count": len(gaps),
            "rhythm_recent_gap_median_s": None,
            "rhythm_all_time_gap_median_s": None,
            "rhythm_current_gap_percentile_all_time": None,
            "rhythm_recent_gap_iqr_s": None,
            "rhythm_all_time_gap_iqr_s": None,
        }
        if len(gaps) >= RHYTHM_MIN_GAPS:         # data-sufficiency floor
            ctx["rhythm_recent_gap_median_s"] = statistics.median(recent)
            ctx["rhythm_all_time_gap_median_s"] = statistics.median(gaps)
            ctx["rhythm_current_gap_percentile_all_time"] = _percentile_strictly_below(current_gap, gaps)
            ctx["rhythm_recent_gap_iqr_s"] = _iqr(recent)
            ctx["rhythm_all_time_gap_iqr_s"] = _iqr(gaps)
        return ctx
```

- [ ] **Step 4: Run, expect GREEN.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_rhythm_context -v`

- [ ] **Step 5: ruff + commit (behavior).**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py tests/test_rhythm_context.py
git add core/evolution/subjective_duration.py tests/test_rhythm_context.py
git commit -m "feat(time-sense): rhythm_context() — learned-from-real-contacts facts (no verdict)

## Predicted effect
Adds a read-only SubjectiveDuration.rhythm_context() emitting raw rhythm facts (current gap, recent/all-time
median, percentile, counts, IQR) learned from REAL owner_contact gaps — or None on degraded/no-contact.
Honest cold-start (<3 gaps -> comparison facts None). No verdict/label/phrase. Nothing calls it yet, so no
behavior change. Built BESIDE the curve.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch learned-felt-time-slice-a
```

---

### Task 2: `rhythm_*` schema (8 nullable columns) + NULL-semantics regression

**Files:** Modify `core/memory/episodes.py`; Create `tests/test_rhythm_stamp.py`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_rhythm_stamp.py`:

```python
import os, sqlite3, tempfile, unittest
from contextlib import closing
from core.memory.episodes import EpisodeStore

RHYTHM_COLS = ("rhythm_current_gap_s", "rhythm_recent_gap_median_s", "rhythm_all_time_gap_median_s",
               "rhythm_recent_sample_count", "rhythm_all_time_sample_count",
               "rhythm_current_gap_percentile_all_time", "rhythm_recent_gap_iqr_s", "rhythm_all_time_gap_iqr_s")


def _cols(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        return {r[1] for r in conn.execute("PRAGMA table_info(episodes)")}


class RhythmSchema(unittest.TestCase):
    def test_new_store_has_rhythm_columns(self):
        path = os.path.join(tempfile.mkdtemp(), "ep.db")
        EpisodeStore(path)
        cols = _cols(path)
        for c in RHYTHM_COLS:
            self.assertIn(c, cols)

    def test_felt_null_is_not_read_as_missing_time(self):
        # The owner's NULL-semantics guard: a rhythm-stamped row has felt_* NULL but rhythm_* set.
        # A reader keying on rhythm_* must see the time context even though felt_* is NULL.
        path = os.path.join(tempfile.mkdtemp(), "ep.db")
        store = EpisodeStore(path, rhythm_reader=lambda: {
            "rhythm_current_gap_s": 3600.0, "rhythm_all_time_sample_count": 5})
        ep = store.add(title="t", summary="s", participants=["Maez"],
                       source_memory_ids=["m1"], source_kind="pursuit_surface")
        row = store.get(ep)
        self.assertIsNone(row["felt_value"])                  # felt box empty
        self.assertAlmostEqual(row["rhythm_current_gap_s"], 3600.0)  # but time context IS present in rhythm box
```

- [ ] **Step 2: Run, expect RED** (`rhythm_current_gap_s` not a column; `rhythm_reader` kwarg unknown).

- [ ] **Step 3: Add columns + migration.** In `core/memory/episodes.py`, append the 8 columns to `_SCHEMA`'s CREATE TABLE (after `felt_compute_version INTEGER`):
```python
    felt_compute_version INTEGER,
    rhythm_current_gap_s REAL,
    rhythm_recent_gap_median_s REAL,
    rhythm_all_time_gap_median_s REAL,
    rhythm_recent_sample_count INTEGER,
    rhythm_all_time_sample_count INTEGER,
    rhythm_current_gap_percentile_all_time REAL,
    rhythm_recent_gap_iqr_s REAL,
    rhythm_all_time_gap_iqr_s REAL
);
```
And extend `_MIGRATIONS`:
```python
    # 2026-06-20: Slice-A learned rhythm facts (separate box from the curve's felt_*). Raw learned data,
    # NEVER a feeling verdict; existing rows stay NULL.
    "ALTER TABLE episodes ADD COLUMN rhythm_current_gap_s REAL",
    "ALTER TABLE episodes ADD COLUMN rhythm_recent_gap_median_s REAL",
    "ALTER TABLE episodes ADD COLUMN rhythm_all_time_gap_median_s REAL",
    "ALTER TABLE episodes ADD COLUMN rhythm_recent_sample_count INTEGER",
    "ALTER TABLE episodes ADD COLUMN rhythm_all_time_sample_count INTEGER",
    "ALTER TABLE episodes ADD COLUMN rhythm_current_gap_percentile_all_time REAL",
    "ALTER TABLE episodes ADD COLUMN rhythm_recent_gap_iqr_s REAL",
    "ALTER TABLE episodes ADD COLUMN rhythm_all_time_gap_iqr_s REAL",
```
(Task 3 adds the `rhythm_reader` kwarg + the stamping that makes `test_felt_null_is_not_read_as_missing_time` fully pass — for THIS task, the schema test passes; the stamp test will pass after Task 3. To keep Task 2 green, add the `rhythm_reader=None` kwarg now as a no-op so the constructor accepts it — full wiring lands in Task 3.)

In `__init__`, accept the kwarg now (so the test's `rhythm_reader=` is valid):
```python
    def __init__(self, db_path: str, *, felt_time_reader: "Optional[Callable[[], Optional[dict]]]" = None,
                 rhythm_reader: "Optional[Callable[[], Optional[dict]]]" = None):
        self._path = Path(db_path)
        self._felt_time_reader = felt_time_reader
        self._rhythm_reader = rhythm_reader
        # ... rest unchanged
```

- [ ] **Step 4: Run.** `test_new_store_has_rhythm_columns` GREEN. `test_felt_null_is_not_read_as_missing_time` will still FAIL (no stamping yet) — that's expected; it goes green in Task 3. To keep Task 2's commit green, mark it `@unittest.skip("stamp wiring lands in Task 3")` temporarily, OR move that test into Task 3's file. **Cleaner: move `test_felt_null_is_not_read_as_missing_time` to Task 3** and keep Task 2's file to schema-only. Do that.

- [ ] **Step 5: ruff + commit (behavior — schema additive).**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/memory/episodes.py tests/test_rhythm_stamp.py
git add core/memory/episodes.py tests/test_rhythm_stamp.py
git commit -m "feat(memory): episodes gains 8 nullable rhythm_* columns (separate box from felt_*)

## Predicted effect
Adds rhythm_current_gap_s/recent+all_time medians/counts/percentile/IQR columns (additive migration, old
rows NULL) + an inert rhythm_reader kwarg. No write path sets them yet (Task 3). Separate box from the
curve's felt_*; behavior unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch learned-felt-time-slice-a
```

---

### Task 3: Stamp wiring — two-reader pattern + the flag matrix

**Files:** Modify `core/memory/episodes.py` (`add()` + INSERT); Modify `daemon/maez_daemon.py`; Extend `tests/test_rhythm_stamp.py`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_rhythm_stamp.py`, incl. the moved NULL-semantics test):

```python
class RhythmStampWiring(unittest.TestCase):
    def _store(self, *, felt=None, rhythm=None):
        return EpisodeStore(os.path.join(tempfile.mkdtemp(), "ep.db"),
                            felt_time_reader=felt, rhythm_reader=rhythm)

    def _add(self, store, source_kind="pursuit_surface"):
        return store.get(store.add(title="t", summary="s", participants=["Maez"],
                                   source_memory_ids=["m1"], source_kind=source_kind))

    def test_felt_null_is_not_read_as_missing_time(self):
        store = self._store(rhythm=lambda: {"rhythm_current_gap_s": 3600.0, "rhythm_all_time_sample_count": 5})
        row = self._add(store)
        self.assertIsNone(row["felt_value"])
        self.assertAlmostEqual(row["rhythm_current_gap_s"], 3600.0)

    def test_rhythm_on_writes_rhythm_only_felt_null(self):
        # rhythm reader returns facts, felt reader returns None (daemon self-gates) -> rhythm_* set, felt_* NULL
        rctx = {"rhythm_current_gap_s": 3600.0, "rhythm_recent_gap_median_s": 1800.0,
                "rhythm_all_time_gap_median_s": 3000.0, "rhythm_recent_sample_count": 4,
                "rhythm_all_time_sample_count": 9, "rhythm_current_gap_percentile_all_time": 85.0,
                "rhythm_recent_gap_iqr_s": 600.0, "rhythm_all_time_gap_iqr_s": 900.0}
        store = self._store(felt=lambda: None, rhythm=lambda: rctx)
        row = self._add(store)
        self.assertAlmostEqual(row["rhythm_current_gap_s"], 3600.0)
        self.assertAlmostEqual(row["rhythm_current_gap_percentile_all_time"], 85.0)
        self.assertEqual(row["rhythm_all_time_sample_count"], 9)
        self.assertIsNone(row["felt_value"])             # felt box left NULL when rhythm on

    def test_rhythm_off_writes_felt_only_rhythm_null(self):
        fctx = {"felt_value": 7.0, "seconds_since_last_owner_contact": 60.0,
                "felt_phrase": "p", "felt_compute_version": 1}
        store = self._store(felt=lambda: fctx, rhythm=lambda: None)
        row = self._add(store)
        self.assertAlmostEqual(row["felt_value"], 7.0)
        self.assertIsNone(row["rhythm_current_gap_s"])   # rhythm box NULL when rhythm off

    def test_rhythm_value_from_reader_not_args(self):
        store = self._store(rhythm=lambda: {"rhythm_current_gap_s": 42.0, "rhythm_all_time_sample_count": 3})
        self.assertAlmostEqual(self._add(store)["rhythm_current_gap_s"], 42.0)

    def test_rhythm_stamps_across_source_kinds(self):
        store = self._store(rhythm=lambda: {"rhythm_current_gap_s": 1.0, "rhythm_all_time_sample_count": 3})
        for k in ("pursuit_surface", "owner_contact", "reflection", "followup_doc"):
            self.assertAlmostEqual(self._add(store, source_kind=k)["rhythm_current_gap_s"], 1.0)

    def test_rhythm_reader_exception_does_not_break_write(self):
        def _boom():
            raise RuntimeError("hiccup")
        store = self._store(rhythm=_boom)
        row = self._add(store)
        self.assertIsNotNone(row)
        self.assertIsNone(row["rhythm_current_gap_s"])
```

- [ ] **Step 2: Run, expect RED** (rhythm_* never written).

- [ ] **Step 3: Stamp the rhythm box in `add()`.** In `core/memory/episodes.py`, after the existing `felt_*` block (before `with self._connect()`), add:
```python
        rhythm_current_gap_s = rhythm_recent_gap_median_s = rhythm_all_time_gap_median_s = None
        rhythm_recent_sample_count = rhythm_all_time_sample_count = None
        rhythm_current_gap_percentile_all_time = rhythm_recent_gap_iqr_s = rhythm_all_time_gap_iqr_s = None
        if self._rhythm_reader is not None:
            try:
                rctx = self._rhythm_reader()
                if rctx:
                    rhythm_current_gap_s = rctx.get("rhythm_current_gap_s")
                    rhythm_recent_gap_median_s = rctx.get("rhythm_recent_gap_median_s")
                    rhythm_all_time_gap_median_s = rctx.get("rhythm_all_time_gap_median_s")
                    rhythm_recent_sample_count = rctx.get("rhythm_recent_sample_count")
                    rhythm_all_time_sample_count = rctx.get("rhythm_all_time_sample_count")
                    rhythm_current_gap_percentile_all_time = rctx.get("rhythm_current_gap_percentile_all_time")
                    rhythm_recent_gap_iqr_s = rctx.get("rhythm_recent_gap_iqr_s")
                    rhythm_all_time_gap_iqr_s = rctx.get("rhythm_all_time_gap_iqr_s")
            except Exception:
                rhythm_current_gap_s = rhythm_recent_gap_median_s = rhythm_all_time_gap_median_s = None
                rhythm_recent_sample_count = rhythm_all_time_sample_count = None
                rhythm_current_gap_percentile_all_time = rhythm_recent_gap_iqr_s = rhythm_all_time_gap_iqr_s = None
```
Extend the INSERT column list (after `felt_value, felt_elapsed_s, felt_phrase, felt_compute_version`):
```python
                    "felt_value, felt_elapsed_s, felt_phrase, felt_compute_version, "
                    "rhythm_current_gap_s, rhythm_recent_gap_median_s, rhythm_all_time_gap_median_s, "
                    "rhythm_recent_sample_count, rhythm_all_time_sample_count, "
                    "rhythm_current_gap_percentile_all_time, rhythm_recent_gap_iqr_s, rhythm_all_time_gap_iqr_s"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
```
> COUNT: the column list now has 14 (original) + 4 (felt) + 8 (rhythm) = **26**; the `?` placeholders must be 26; the value tuple must be 26. Count all three before running.

Append the 8 rhythm values to the value tuple (after `felt_compute_version,`):
```python
                        felt_compute_version,
                        rhythm_current_gap_s,
                        rhythm_recent_gap_median_s,
                        rhythm_all_time_gap_median_s,
                        rhythm_recent_sample_count,
                        rhythm_all_time_sample_count,
                        rhythm_current_gap_percentile_all_time,
                        rhythm_recent_gap_iqr_s,
                        rhythm_all_time_gap_iqr_s,
```

- [ ] **Step 4: Run the store tests, expect GREEN.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_rhythm_stamp -v`

- [ ] **Step 5: Daemon — the flag, the rhythm reader, and gate the felt reader off when rhythm on.** In `daemon/maez_daemon.py`:

Add the flag next to `time_sense_feed_enabled` (~:2638):
```python
def time_sense_rhythm_enabled() -> bool:
    """Return True iff MAEZ_RHYTHM_FELT_TIME is on. DEFAULT OFF. Selects the CONTENT source (learned rhythm
    facts vs the legacy curve). FEED/STAMP remain the mouths."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_RHYTHM_FELT_TIME")
```

Gate `_episode_felt_time_reader` OFF when rhythm is on (so `felt_*` is NULL on the rhythm path) — change its guard:
```python
    def _episode_felt_time_reader(self):
        try:
            if not (time_sense_stamp_enabled() and continuous_time_sense_enabled()):
                return None
            if time_sense_rhythm_enabled():
                return None                  # rhythm is the source -> curve stamp stays silent (felt_* NULL)
            return self._time_sense_handle().time_sense_context()
        except Exception:
            logger.debug("episode felt-time reader skipped", exc_info=True)
            return None
```

Add the rhythm reader (next to it):
```python
    def _episode_rhythm_reader(self):
        """Injected into EpisodeStore: rhythm facts or None. Gated by MAEZ_RHYTHM_FELT_TIME AND STAMP AND the
        substrate. Read-only; never raises into a memory write."""
        try:
            if not (time_sense_rhythm_enabled() and time_sense_stamp_enabled() and continuous_time_sense_enabled()):
                return None
            return self._time_sense_handle().rhythm_context()
        except Exception:
            logger.debug("episode rhythm reader skipped", exc_info=True)
            return None
```

Inject it at the `EpisodeStore(...)` construction (~:2971):
```python
        self.lived_episodes = EpisodeStore(
            str(_lived_dir / "lived_episodes.db"),
            felt_time_reader=self._episode_felt_time_reader,
            rhythm_reader=self._episode_rhythm_reader,
        )
```

- [ ] **Step 6: Smoke + tests.**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -c "import daemon.maez_daemon as d; print('import ok', d.time_sense_rhythm_enabled())"
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_rhythm_stamp -v
```
Expected: `import ok False` + GREEN.

- [ ] **Step 7: ruff + commit (behavior).**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/memory/episodes.py daemon/maez_daemon.py tests/test_rhythm_stamp.py
git add core/memory/episodes.py daemon/maez_daemon.py tests/test_rhythm_stamp.py
git commit -m "feat(memory): stamp rhythm_* via a second injected reader; felt_* silent when rhythm on

## Predicted effect
EpisodeStore.add() now stamps rhythm_* from an injected rhythm_reader; the daemon injects rhythm_context()
gated by MAEZ_RHYTHM_FELT_TIME AND STAMP AND substrate, and the felt reader returns None when rhythm is on
(felt_* NULL). Separate boxes; flag-off (default) -> Slice-2 felt_* path unchanged. Substrate-computed, never
the model; reader errors never break a memory write.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch learned-felt-time-slice-a
```

---

### Task 4: Source-aware feed line + no-verdict render

**Files:** Modify `daemon/maez_daemon.py`; Create `tests/test_rhythm_feed.py`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_rhythm_feed.py`:

```python
import unittest
import daemon.maez_daemon as d

_VERDICT_WORDS = ("long quiet", "stretch", "a while", "unusual", "lonely", "feels", "felt like")


class RhythmLineFormat(unittest.TestCase):
    def test_full_facts_line_has_no_verdict_words(self):
        ctx = {"rhythm_current_gap_s": 3 * 3600, "rhythm_recent_gap_median_s": 30 * 60,
               "rhythm_all_time_gap_median_s": 50 * 60, "rhythm_recent_sample_count": 20,
               "rhythm_all_time_sample_count": 227, "rhythm_current_gap_percentile_all_time": 85.0,
               "rhythm_recent_gap_iqr_s": 600.0, "rhythm_all_time_gap_iqr_s": 900.0}
        line = d._format_rhythm_line(ctx)
        self.assertIn("3h", line)
        self.assertIn("85", line)           # the raw percentile fact
        low = line.lower()
        for w in _VERDICT_WORDS:
            self.assertNotIn(w, low)        # facts, never a feeling-verdict
        self.assertTrue(line.startswith("Time:"))

    def test_short_gap_still_produces_a_line_no_expression_gate(self):
        # A SHORT gap (low percentile) must STILL produce a facts line — no threshold gating of expression.
        ctx = {"rhythm_current_gap_s": 60, "rhythm_recent_gap_median_s": 30 * 60,
               "rhythm_all_time_gap_median_s": 50 * 60, "rhythm_recent_sample_count": 20,
               "rhythm_all_time_sample_count": 227, "rhythm_current_gap_percentile_all_time": 3.0,
               "rhythm_recent_gap_iqr_s": 600.0, "rhythm_all_time_gap_iqr_s": 900.0}
        line = d._format_rhythm_line(ctx)
        self.assertTrue(line.startswith("Time:"))
        self.assertIn("3", line)            # the percentile fact is still stated, not withheld

    def test_cold_start_line_states_still_learning(self):
        ctx = {"rhythm_current_gap_s": 900, "rhythm_recent_gap_median_s": None,
               "rhythm_all_time_gap_median_s": None, "rhythm_recent_sample_count": 1,
               "rhythm_all_time_sample_count": 1, "rhythm_current_gap_percentile_all_time": None,
               "rhythm_recent_gap_iqr_s": None, "rhythm_all_time_gap_iqr_s": None}
        line = d._format_rhythm_line(ctx).lower()
        self.assertIn("still learning", line)
        self.assertNotIn("%", line)         # no fabricated percentile in cold-start


class CycleFeedSource(unittest.TestCase):
    def test_cycle_packet_module_has_no_rhythm_or_felt(self):
        import inspect, core.cognition.cycle_packet as cp
        src = inspect.getsource(cp).lower()
        for token in ("rhythm", "felt_time", "time_sense", "subjective_duration"):
            self.assertNotIn(token, src)    # still pure
```

- [ ] **Step 2: Run, expect RED** (`_format_rhythm_line` undefined).

- [ ] **Step 3: Implement.** In `daemon/maez_daemon.py`, add `_format_rhythm_line` next to `_format_time_sense_line` (~:2473):
```python
def _format_rhythm_line(ctx: dict) -> str:
    """Render learned rhythm FACTS into ONE perception line. Facts only — no verdict word, no feeling."""
    from core.evolution.subjective_duration import humanize_elapsed

    cur = humanize_elapsed(ctx.get("rhythm_current_gap_s", 0.0))
    n = ctx.get("rhythm_all_time_sample_count") or 0
    parts = [f"Time: ~{cur} since the last owner contact."]
    rec = ctx.get("rhythm_recent_gap_median_s")
    allt = ctx.get("rhythm_all_time_gap_median_s")
    pct = ctx.get("rhythm_current_gap_percentile_all_time")
    if rec is not None and allt is not None:
        parts.append(f"Recently you usually return after ~{humanize_elapsed(rec)}; "
                     f"over all our time, ~{humanize_elapsed(allt)}.")
    if pct is not None:
        parts.append(f"This gap exceeds ~{round(pct)}% of our {n} recorded gaps.")
    else:
        parts.append(f"(Still learning your rhythm — {n} gaps so far.)")
    return " ".join(parts)
```

Make `_cycle_feed_time_sense_line` source-aware:
```python
    def _cycle_feed_time_sense_line(self) -> str:
        try:
            if not (time_sense_feed_enabled() and continuous_time_sense_enabled()):
                return ""
            handle = self._time_sense_handle()
            if time_sense_rhythm_enabled():
                rctx = handle.rhythm_context()
                return _format_rhythm_line(rctx) if rctx else ""
            ctx = handle.time_sense_context()
            return _format_time_sense_line(ctx) if ctx else ""
        except Exception:
            logger.debug("cycle feed time-sense line skipped", exc_info=True)
            return ""
```

- [ ] **Step 4: Run, expect GREEN.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_rhythm_feed -v`

- [ ] **Step 5: ruff + commit (behavior).**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py tests/test_rhythm_feed.py
git add daemon/maez_daemon.py tests/test_rhythm_feed.py
git commit -m "feat(time-sense): source-aware cycle feed renders learned rhythm facts (no verdict)

## Predicted effect
When MAEZ_RHYTHM_FELT_TIME + FEED + substrate are on, the autonomous cycle feed renders a raw-facts rhythm
line (current gap, your recent/all-time usual, percentile, learned-from-N) — facts, no verdict word, no
expression-gate. Rhythm-off keeps the Slice-2 curve line. cycle_packet.py stays pure.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch learned-felt-time-slice-a
```

---

### Task 5: Whole-slice green + broad regression + handoff + STOP

**Files:** Create `docs/handoffs/2026-06-20-learned-felt-time-slice-a-handoff.md`.

- [ ] **Step 1: Slice modules green.**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_rhythm_context tests.test_rhythm_stamp tests.test_rhythm_feed -v
```

- [ ] **Step 2: Broad regression (the Slice-2 lesson — run the EpisodeStore + felt-time + cycle surfaces).**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_time_sense_context tests.test_episode_felt_time_stamp tests.test_cycle_feed_time_sense \
  tests.test_subjective_duration tests.test_subjective_duration_continuous tests.test_cycle_packet \
  tests.test_episode_builder tests.test_lived_memory_schema tests.test_lived_recall \
  tests.test_reflection_synthesis -v 2>&1 | tail -5
```
Expected: all GREEN (Slice-2 felt_* paths byte-identical with rhythm default-off; EpisodeStore consumers unbroken). Confirm any pre-existing failures also fail on `main` (not introduced here).

- [ ] **Step 3: ruff on the whole diff + flag-off behavior check.**
  `/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py core/memory/episodes.py daemon/maez_daemon.py tests/test_rhythm_context.py tests/test_rhythm_stamp.py tests/test_rhythm_feed.py`
  `git diff main -- daemon/maez_daemon.py core/evolution/subjective_duration.py` — confirm the foreground line, 3b mint, and heartbeat are NOT in the diff.

- [ ] **Step 4: Write the handoff** `docs/handoffs/2026-06-20-learned-felt-time-slice-a-handoff.md`: branch tip; commit list; Codex anchors (facts-not-verdict / no-expression-gate / separate-boxes-felt_*-NULL-when-rhythm-on / NULL-semantics-consumers-named-from-Task-0 / learned-from-real-contacts-only / honest-cold-start / truthful-None / flag-matrix / flag-off-behavior-identical / curve+foreground+3b+heartbeat+cycle_packet untouched / not-LLM-owned); the test surface; and the **owner-breath**:
  > Set `MAEZ_RHYTHM_FELT_TIME=1` (and `MAEZ_TIME_SENSE_FEED=1` / `MAEZ_TIME_SENSE_STAMP=1` per the matrix) in the daemon env; restart `maez`; witness — (feed) a self-initiated cycle thought reasoning over the RAW rhythm facts in its own voice (no verdict word); (stamp) a fresh episode row carrying `rhythm_*` columns with `felt_*` NULL. **Key witness question: does the value now VARY as the gap grows** (unlike the pinned 7.652 curve)? Confirm via the live probe `SubjectiveDuration().rhythm_context()` at two times.

- [ ] **Step 5: Commit the handoff (docs) + STOP.**
```bash
git add docs/handoffs/2026-06-20-learned-felt-time-slice-a-handoff.md
git commit -m "docs(handoff): learned felt-time Slice A — review gate + owner-breath sequence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch learned-felt-time-slice-a
```
**STOP.** No merge/restart/flag-flip. Report branch tip + Task-0 inventory (incl. the NULL-semantics consumers) + test outputs + Codex anchors + the owner-breath sequence.

---

## Self-review (controller)

- **Spec coverage:** rhythm reader + facts (Task 1) ✓; rhythm_* columns separate box (Task 2) ✓; two-reader stamp + felt_*-NULL-when-rhythm-on matrix (Task 3) ✓; new flag + source-aware feed + no-verdict render (Task 4) ✓; NULL-semantics consumer check (Task 0 Step 3 + the Task 2/3 regression test) ✓; learned-from-real-contacts (Task 1 exclusion test) ✓; honest cold-start (Task 1 + Task 4) ✓; truthful-None/degraded (Task 1) ✓; no-expression-gate (Task 4 short-gap test) ✓; flag-off behavior-identical (Task 5 regression) ✓; build-beside-old/untouched (Task 0 Step 4 + Task 5 diff) ✓.
- **Type/name consistency:** `rhythm_context()` keys == the 8 `rhythm_*` columns == the `add()` `.get()` keys == `_format_rhythm_line` reads. Flags: `time_sense_rhythm_enabled` mirrors `time_sense_feed/stamp_enabled`. `RHYTHM_RECENT_WINDOW` / `RHYTHM_MIN_GAPS` defined Task 1, used Task 1 only. INSERT counts pinned at 26 (Task 3 Step 3).
- **Open items handed to Task 0 / implementer:** current-main line-number drift (Task 0 Step 2); the NULL-semantics consumer list (Task 0 Step 3 — any misreader is a NAMED Slice-B follow-up, not fixed here); whether `statistics.quantiles` exclusive-default matches the IQR test expectations (implementer: if a quantile test value differs, recompute the expected by hand from the stdlib's method=`exclusive` default rather than weakening the test).
