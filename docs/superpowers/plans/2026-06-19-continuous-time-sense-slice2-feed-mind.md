# Continuous Lived Time-Sense — Slice 2 (Feed-Mind) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the live felt-time substrate into Maez's autonomous cognition (a perception line in the cycle packet) and stamp every `EpisodeStore` lived episode with a felt-time index — both honest, both flag-gated, behind one truthful reader.

**Architecture:** One new read-only seam `SubjectiveDuration.time_sense_context()` returns a valid context dict or `None` (None on clock-degraded or no real owner-contact). The **Feed** organ (`MAEZ_TIME_SENSE_FEED`) prepends a perception line to the autonomous focused-cognition prompt from that context. The **Stamp** organ (`MAEZ_TIME_SENSE_STAMP`) adds four nullable columns to `episodes` and an injected reader on `EpisodeStore` that stamps them. Both flags AND-gate with the live `MAEZ_CONTINUOUS_TIME_SENSE` substrate. Flag-off = behavior-identical (schema additive + inert).

**Tech Stack:** Python 3, SQLite, `unittest`. Spec: `docs/superpowers/specs/2026-06-19-continuous-time-sense-slice2-feed-mind-design.md` (@95331b8).

---

## Lane discipline (every task)

- **Worktree/branch:** created via superpowers:using-git-worktrees at execution time. Branch **`continuous-time-sense-slice2`**. `main` is local-only — **NO push**.
- **GIT HYGIENE (the last slice's worktree had ref instability):** Do **NOT** run `git checkout` / `switch` / `reset` / `rebase`. Only: edit, test, `git add`, `git commit` (normal new commit). After every commit run `git status` and confirm **`On branch continuous-time-sense-slice2`**. If it ever says "detached HEAD", **STOP and report** — do not try to fix it by checkout.
- **Test runner (named modules ONLY, never full-discover):**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v`
- **Commits:** behavior commits carry a `## Predicted effect` block; docs/proof/test-only commits do NOT. Every commit ends with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** after Task 5 — no merge, no restart, no flag flip (owner-sovereign). Cross-lane Codex review at the gate; live witness before LIVE_WITNESSED.

## The load-bearing invariants (reviewers verify)

1. **Perception, not directive** — the feed line states what *is*; never an imperative.
2. **No dilation** — exact elapsed-since-**contact** sits beside the felt sense; never claimed equal.
3. **Honest null, enforced by `time_sense_context()`** — degraded clock / no real contact → `None` → no feed line + null stamp. Feed/stamp use the helper, **never raw `peek()`**.
4. **Not LLM-owned** — the stamp value comes from the substrate context, never the model.
5. **No durable band** — only `felt_value` + `felt_elapsed_s` + frozen `felt_phrase` + `felt_compute_version`; `render_band` is NEVER stored.
6. **Flag-off behavior-identical; schema migration additive + inert.**
7. **Untouched:** 3b owner-contact mint + gates, the Slice-1 heartbeat/anchors, the foreground reply line (daemon:5673), `core/cognition/cycle_packet.py` purity.
8. **Perception-side / free** — no owner-gate / marker / S7 / egress / secret.

## File structure

| File | Responsibility | Change |
|---|---|---|
| `core/evolution/subjective_duration.py` | Felt-time substrate | **Modify** — add `time_sense_context()` (truthful reader) + `humanize_elapsed()` |
| `core/memory/episodes.py` | Episode store | **Modify** — 4 nullable columns + migration + injected `felt_time_reader` + stamp in `add()` |
| `daemon/maez_daemon.py` | Daemon wiring | **Modify** — 2 flag helpers, the feed line builder + call-site param, the episode reader injection |
| `tests/test_time_sense_context.py` | Truthful-reader + humanizer tests | **Create** |
| `tests/test_episode_felt_time_stamp.py` | Stamp schema + wiring tests | **Create** |
| `tests/test_cycle_feed_time_sense.py` | Feed tests | **Create** |
| `docs/proof/2026-06-19-continuous-time-sense-slice2-task0.md` | Task-0 proof gate | **Create** |
| `docs/handoffs/2026-06-19-continuous-time-sense-slice2-handoff.md` | Review-gate handoff | **Create** |

---

### Task 0: Proof gate (docs/proof only — repo-wide, committed first)

**Files:**
- Create: `docs/proof/2026-06-19-continuous-time-sense-slice2-task0.md`

This task writes NO code. It confirms the spec's assumptions against real code and produces the memory-store inventory. If any check refutes the plan, STOP and report before Task 1.

- [ ] **Step 1: Confirm the feed site + felt-time absence.** Verify `_build_cycle_focused_prompt` (`daemon/maez_daemon.py:2473`) is the autonomous focused-cognition assembly, called at `daemon/maez_daemon.py:5166` inside `_reason` (a method with `self`); and that no felt-time / subjective_duration line exists in that path today. Confirm `core/cognition/cycle_packet.py` `build_cycle_packet` contains no felt-time. Record line numbers.

- [ ] **Step 2: Confirm the truthful-reader inputs.** Verify `SubjectiveDuration._compute(now)` returns `(snapshot, degraded_latest)` (`subjective_duration.py:557`, degraded branch :565-566) and that the snapshot exposes `.value` and `.surface_phrase`. Verify `peek()` (:596) discards the degraded signal (why raw `peek()` is unsafe for Slice 2). Verify `CURRENT_COMPUTE_VERSION` (:465).

- [ ] **Step 3: Confirm + pin the owner-contact read (the tightened filter).** Read the `subjective_duration_salience_events` schema (`subjective_duration.py:530`) and the `is_canary` migration (:361). Confirm these EXACT columns exist: `event_id`, `ts_utc`, `salience_event_kind`, `owner_auth_class`, `is_canary`. Confirm `owner_contact` is a registered kind with `owner_auth_required=True` (so real owner-contact rows carry a non-empty `owner_auth_class`). Record the final query the helper will use:
  ```sql
  SELECT ts_utc FROM subjective_duration_salience_events
  WHERE salience_event_kind = 'owner_contact' AND is_canary = 0 AND owner_auth_class != ''
  ORDER BY event_id DESC LIMIT 1
  ```
  If any column name differs, record the corrected query (later tasks must use the confirmed names).

- [ ] **Step 4: Confirm the stamp target + migration pattern.** Verify `EpisodeStore._MIGRATIONS` (`core/memory/episodes.py:64`) is a tuple of `ALTER TABLE episodes ADD COLUMN ...` applied idempotently in `__init__` (:96-101, catching `sqlite3.OperationalError`), and the `add()` INSERT (:134-157). Confirm adding four nullable columns is additive/back-compatible.

- [ ] **Step 5: MEMORY-STORE INVENTORY (the "every memory" honesty).** Enumerate every durable memory store and classify each, with a one-line reason:
  - `EpisodeStore` / `self.lived_episodes` (`daemon:2914`) → **IN** (the lived-episode store; the stamp target).
  - `core.private_thoughts.PrivateThoughts` (`daemon:3185`) → **OUT/later** (separate behavior-safe raw-thought store; not episode-shaped; touching it widens the slice).
  - `core.infra.private_thoughts_s1b` producer/consumer (`daemon:3194`) → **OUT/later** (signal-driven S1b store; same reason).
  - Reflection writer (`core/memory/nightly_lived_memory.py` / `reflection.py`) → confirm whether it persists via `EpisodeStore.add()`. If yes → it is stamped automatically (IN, no extra work); if it writes its own store → **OUT/later**. Record which.
  - Any other durable store found → classify.
  State plainly: **v0 stamps episode-shaped lived memories via `EpisodeStore.add()` only; the rest are OUT/later.**

- [ ] **Step 6: Confirm untouched surfaces.** Record that the foreground felt-time line (`daemon:5673`, `subjective_duration_prompt_line`), the 3b owner-contact mint path, and the Slice-1 heartbeat block (`daemon:~8792-8800`) are NOT modified by this slice.

- [ ] **Step 7: Commit (docs/proof — NO predicted-effect).**
```bash
git add docs/proof/2026-06-19-continuous-time-sense-slice2-task0.md
git commit -m "docs(proof): continuous time-sense slice2 Task 0 — feed site, truthful-reader inputs, contact-read filter, episode migration, memory-store inventory

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch continuous-time-sense-slice2
```

---

### Task 1: The truthful reader — `time_sense_context()` + `humanize_elapsed()`

**Files:**
- Modify: `core/evolution/subjective_duration.py`
- Test: `tests/test_time_sense_context.py` (create)

The helper is read-only and env-flag-free (callers gate on flags). It returns a valid context dict or `None`. `humanize_elapsed` is a pure presentation helper for the feed.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_time_sense_context.py`:

```python
import os, sqlite3, tempfile, unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from core.evolution import subjective_duration as sd

UTC = timezone.utc


def _insert_owner_contact(db_path, *, ts, is_canary=0, owner_auth_class="cockpit"):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT INTO subjective_duration_salience_events "
            "(ts_utc, salience_event_kind, owner_auth_class, is_canary) VALUES (?,?,?,?)",
            (ts.isoformat(), "owner_contact", owner_auth_class, is_canary),
        )
        conn.commit()


class TimeSenseContext(unittest.TestCase):
    def _inst(self):
        return sd.SubjectiveDuration(db_path=os.path.join(tempfile.mkdtemp(), "sd.db"))

    def test_valid_context_has_value_phrase_version_and_seconds_since_contact(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                       # an anchor so felt-time computes
        _insert_owner_contact(inst.db_path, ts=t0)     # a real last-contact reference
        ctx = inst.time_sense_context(now=t0 + timedelta(hours=2))
        self.assertIsNotNone(ctx)
        self.assertIn("felt_value", ctx)
        self.assertIn("felt_phrase", ctx)
        self.assertEqual(ctx["felt_compute_version"], sd.CURRENT_COMPUTE_VERSION)
        self.assertAlmostEqual(ctx["seconds_since_last_owner_contact"], 7200.0, places=1)  # since CONTACT, not anchor

    def test_none_when_no_owner_contact_reference(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                        # felt-time exists, but no owner_contact row
        self.assertIsNone(inst.time_sense_context(now=t0 + timedelta(hours=1)))

    def test_none_when_only_canary_contact(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)
        _insert_owner_contact(inst.db_path, ts=t0, is_canary=1)   # canary must NOT count as last contact
        self.assertIsNone(inst.time_sense_context(now=t0 + timedelta(hours=1)))

    def test_none_on_clock_degraded_and_writes_nothing(self):
        inst = self._inst()
        t1 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t1)                         # latest anchor at t1
        _insert_owner_contact(inst.db_path, ts=t1)
        with closing(sqlite3.connect(inst.db_path)) as conn:
            samples_before = conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0]
            events_before = conn.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0]
        ctx = inst.time_sense_context(now=t1 - timedelta(hours=1))   # clock went BACKWARD -> degraded
        self.assertIsNone(ctx)
        with closing(sqlite3.connect(inst.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0], samples_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0], events_before)

    def test_excludes_canary_uses_real_contact(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)
        _insert_owner_contact(inst.db_path, ts=t0 + timedelta(hours=3), is_canary=1)   # newer but canary
        _insert_owner_contact(inst.db_path, ts=t0, is_canary=0)                         # older but real
        ctx = inst.time_sense_context(now=t0 + timedelta(hours=4))
        self.assertIsNotNone(ctx)
        self.assertAlmostEqual(ctx["seconds_since_last_owner_contact"], 4 * 3600.0, places=1)  # used the REAL row


class HumanizeElapsed(unittest.TestCase):
    def test_humanizes_hours_and_minutes(self):
        self.assertEqual(sd.humanize_elapsed(3 * 3600 + 12 * 60), "3h 12m")
        self.assertEqual(sd.humanize_elapsed(90), "1m")          # <1h -> minutes
        self.assertEqual(sd.humanize_elapsed(45), "under a minute")
        self.assertEqual(sd.humanize_elapsed(26 * 3600), "1d 2h")
```

- [ ] **Step 2: Run, expect RED.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_time_sense_context -v`
  Expected: FAIL/ERROR — `time_sense_context` / `humanize_elapsed` don't exist.

- [ ] **Step 3: Implement `humanize_elapsed` + `time_sense_context`.** In `core/evolution/subjective_duration.py`, add `humanize_elapsed` as a module-level function (near the other module helpers) and `time_sense_context` as a method on `SubjectiveDuration` (right after `peek()`, ~:600). Use the EXACT contact query confirmed in Task 0.

```python
def humanize_elapsed(seconds: float) -> str:
    """Render elapsed seconds as a coarse human phrase for the felt-time perception line."""
    s = max(0.0, float(seconds))
    if s < 60:
        return "under a minute"
    minutes = int(s // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem_min = minutes % 60
    if hours < 24:
        return f"{hours}h {rem_min}m" if rem_min else f"{hours}h"
    days = hours // 24
    rem_hr = hours % 24
    return f"{days}d {rem_hr}h" if rem_hr else f"{days}d"
```

```python
    def time_sense_context(self, *, now: str | datetime | None = None) -> dict | None:
        """Truthful read-only felt-time context for Slice-2 feed/stamp. Returns a valid context
        {felt_value, felt_phrase, felt_compute_version, seconds_since_last_owner_contact} or None.
        None (without writing) when: the clock is degraded, or there is no real owner-contact
        reference. NEVER records a clock_degraded_event (that write belongs to current())."""
        now_dt = _normalize_event_time(now or datetime.now(UTC))
        snap, degraded_latest = self._compute(now_dt)
        if degraded_latest is not None:
            return None                      # clock-degraded -> absent, not stale-as-alive (no write)
        seconds_since = self._seconds_since_last_owner_contact(now_dt)
        if seconds_since is None:
            return None                      # no real owner-contact reference yet
        return {
            "felt_value": snap.value,
            "felt_phrase": snap.surface_phrase,
            "felt_compute_version": CURRENT_COMPUTE_VERSION,
            "seconds_since_last_owner_contact": seconds_since,
        }

    def _seconds_since_last_owner_contact(self, now: datetime) -> float | None:
        """Wall-clock seconds since the latest REAL owner_contact salience event (canary/scratch
        rows excluded). None if there is no such row or the clock is before it."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT ts_utc FROM subjective_duration_salience_events "
                "WHERE salience_event_kind = 'owner_contact' AND is_canary = 0 AND owner_auth_class != '' "
                "ORDER BY event_id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        contact_ts = _normalize_event_time(row[0])
        delta = (now - contact_ts).total_seconds()
        return delta if delta >= 0 else None
```
> Confirm `_normalize_event_time` accepts an ISO string (it normalizes `now_utc` strings elsewhere). If it does not parse strings, use `datetime.fromisoformat(row[0])` and ensure tz-aware UTC.

- [ ] **Step 4: Run, expect GREEN.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_time_sense_context -v`
  Expected: all PASS.

- [ ] **Step 5: ruff + commit (behavior).**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py tests/test_time_sense_context.py
git add core/evolution/subjective_duration.py tests/test_time_sense_context.py
git commit -m "feat(time-sense): time_sense_context() truthful reader + humanize_elapsed

## Predicted effect
Adds a read-only SubjectiveDuration.time_sense_context() returning a valid felt-time context or None
(None on clock-degraded or no real owner-contact reference; canary rows excluded; never writes). Plus a
pure humanize_elapsed() for the feed line. Nothing calls these yet, so no behavior change. This is the
honesty valve Slice-2 feed/stamp consume instead of raw peek().

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch continuous-time-sense-slice2
```

---

### Task 2: Stamp schema — four nullable columns + additive migration

**Files:**
- Modify: `core/memory/episodes.py`
- Test: `tests/test_episode_felt_time_stamp.py` (create)

- [ ] **Step 1: Write the failing test.** Create `tests/test_episode_felt_time_stamp.py`:

```python
import os, sqlite3, tempfile, unittest
from contextlib import closing
from core.memory.episodes import EpisodeStore


def _cols(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        return {r[1] for r in conn.execute("PRAGMA table_info(episodes)")}


class StampSchema(unittest.TestCase):
    def test_new_store_has_felt_columns(self):
        path = os.path.join(tempfile.mkdtemp(), "ep.db")
        EpisodeStore(path)
        cols = _cols(path)
        for c in ("felt_value", "felt_elapsed_s", "felt_phrase", "felt_compute_version"):
            self.assertIn(c, cols)
        self.assertNotIn("felt_band", cols)        # NO durable band/bucket column

    def test_old_db_migrates_additively_and_reads_back(self):
        # Simulate a pre-Slice-2 episodes DB (no felt columns), then open with the new store.
        path = os.path.join(tempfile.mkdtemp(), "ep.db")
        with closing(sqlite3.connect(path)) as conn:
            conn.execute(
                "CREATE TABLE episodes (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, occurred_at TEXT,"
                " title TEXT NOT NULL, summary TEXT NOT NULL, participants_json TEXT NOT NULL,"
                " emotional_tone TEXT, importance INTEGER NOT NULL DEFAULT 3, open_loop TEXT,"
                " source_memory_ids_json TEXT NOT NULL, source_kind TEXT NOT NULL,"
                " status TEXT NOT NULL DEFAULT 'active')")
            conn.execute(
                "INSERT INTO episodes (id, created_at, title, summary, participants_json,"
                " source_memory_ids_json, source_kind) VALUES "
                "('ep-old','2026-01-01T00:00:00+00:00','t','s','[\"Maez\"]','[\"m1\"]','seed')")
            conn.commit()
        EpisodeStore(path)                          # __init__ migrates additively
        self.assertIn("felt_value", _cols(path))
        with closing(sqlite3.connect(path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM episodes WHERE id='ep-old'").fetchone()
        self.assertIsNone(row["felt_value"])        # old row keeps felt-* NULL (historical meaning preserved)
```

- [ ] **Step 2: Run, expect RED.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_episode_felt_time_stamp -v`
  Expected: FAIL — `felt_value` not in columns.

- [ ] **Step 3: Add the columns to schema + migrations.** In `core/memory/episodes.py`, append the four columns to `_SCHEMA`'s CREATE TABLE (before the closing `)`):
```python
    superseded_by TEXT,
    felt_value REAL,
    felt_elapsed_s REAL,
    felt_phrase TEXT,
    felt_compute_version INTEGER
);
```
And extend `_MIGRATIONS` (so existing DBs gain them additively):
```python
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE episodes ADD COLUMN authorship TEXT",
    "ALTER TABLE episodes ADD COLUMN memory_voice TEXT",
    "ALTER TABLE episodes ADD COLUMN superseded_at TEXT",
    "ALTER TABLE episodes ADD COLUMN superseded_reason TEXT",
    "ALTER TABLE episodes ADD COLUMN superseded_by TEXT",
    # 2026-06-20: Slice-2 felt-time index (continuous lived time-sense). Frozen point-in-time
    # readings from the substrate; NEVER a durable band/bucket. Existing rows stay NULL.
    "ALTER TABLE episodes ADD COLUMN felt_value REAL",
    "ALTER TABLE episodes ADD COLUMN felt_elapsed_s REAL",
    "ALTER TABLE episodes ADD COLUMN felt_phrase TEXT",
    "ALTER TABLE episodes ADD COLUMN felt_compute_version INTEGER",
)
```

- [ ] **Step 4: Run, expect GREEN.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_episode_felt_time_stamp -v`
  Expected: PASS.

- [ ] **Step 5: ruff + commit (behavior — schema additive).**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/memory/episodes.py tests/test_episode_felt_time_stamp.py
git add core/memory/episodes.py tests/test_episode_felt_time_stamp.py
git commit -m "feat(memory): episodes gains felt_value/felt_elapsed_s/felt_phrase/felt_compute_version (nullable, additive)

## Predicted effect
Adds four nullable felt-time index columns to the episodes table (additive migration, old rows stay NULL).
No write path sets them yet (Task 3 wires the stamp), so behavior is unchanged. No durable band column.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch continuous-time-sense-slice2
```

---

### Task 3: Stamp wiring — injected reader on `EpisodeStore.add()` + daemon injection

**Files:**
- Modify: `core/memory/episodes.py` (constructor + `add()` + INSERT)
- Modify: `daemon/maez_daemon.py` (flag helper + the injected reader + the construction at :2914)
- Test: `tests/test_episode_felt_time_stamp.py` (extend)

- [ ] **Step 1: Write the failing tests (extend the file).** Append to `tests/test_episode_felt_time_stamp.py`:

```python
class StampWiring(unittest.TestCase):
    def _store(self, reader):
        return EpisodeStore(os.path.join(tempfile.mkdtemp(), "ep.db"), felt_time_reader=reader)

    def _add(self, store, source_kind="pursuit_surface"):
        return store.add(title="t", summary="s", participants=["Maez"],
                         source_memory_ids=["m1"], source_kind=source_kind)

    def _row(self, store, ep_id):
        return store.get(ep_id)

    def test_stamps_from_context_when_reader_returns_context(self):
        ctx = {"felt_value": 7.65, "felt_elapsed_s": 11520.0,
               "felt_phrase": "a long quiet stretch", "felt_compute_version": 1}
        store = self._store(lambda: ctx)
        row = self._row(store, self._add(store))
        self.assertAlmostEqual(row["felt_value"], 7.65)
        self.assertAlmostEqual(row["felt_elapsed_s"], 11520.0)
        self.assertEqual(row["felt_phrase"], "a long quiet stretch")
        self.assertEqual(row["felt_compute_version"], 1)

    def test_null_when_reader_returns_none(self):
        store = self._store(lambda: None)
        row = self._row(store, self._add(store))
        self.assertIsNone(row["felt_value"])
        self.assertIsNone(row["felt_elapsed_s"])
        self.assertIsNone(row["felt_phrase"])

    def test_null_when_no_reader_injected(self):
        store = EpisodeStore(os.path.join(tempfile.mkdtemp(), "ep.db"))   # reader defaults None
        row = self._row(store, self._add(store))
        self.assertIsNone(row["felt_value"])

    def test_value_comes_from_reader_not_args(self):
        # The stamp must come from the injected substrate reader, never from add() arguments.
        ctx = {"felt_value": 3.0, "felt_elapsed_s": 60.0, "felt_phrase": "p", "felt_compute_version": 1}
        store = self._store(lambda: ctx)
        row = self._row(store, self._add(store))
        self.assertAlmostEqual(row["felt_value"], 3.0)   # from the reader

    def test_stamps_across_source_kinds(self):
        ctx = {"felt_value": 1.0, "felt_elapsed_s": 1.0, "felt_phrase": "p", "felt_compute_version": 1}
        store = self._store(lambda: ctx)
        for kind in ("pursuit_surface", "owner_contact", "reflection", "followup_doc"):
            row = self._row(store, self._add(store, source_kind=kind))
            self.assertAlmostEqual(row["felt_value"], 1.0)   # EVERY EpisodeStore episode

    def test_reader_exception_does_not_break_the_write(self):
        def _boom():
            raise RuntimeError("substrate hiccup")
        store = self._store(_boom)
        ep_id = self._add(store)                 # a memory write must NEVER fail due to the stamp
        self.assertIsNotNone(self._row(store, ep_id))
        self.assertIsNone(self._row(store, ep_id)["felt_value"])
```

- [ ] **Step 2: Run, expect RED.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_episode_felt_time_stamp -v`
  Expected: FAIL — `EpisodeStore.__init__` has no `felt_time_reader`.

- [ ] **Step 3: Wire the injected reader + stamp in `EpisodeStore`.** In `core/memory/episodes.py`:

Add the import (top of file): `from typing import Callable, Optional, Sequence` (add `Callable`).

Constructor — accept the reader:
```python
    def __init__(self, db_path: str, *, felt_time_reader: "Optional[Callable[[], Optional[dict]]]" = None):
        self._path = Path(db_path)
        self._felt_time_reader = felt_time_reader
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            with c:
                c.executescript(_SCHEMA)
                for stmt in _MIGRATIONS:
                    try:
                        c.execute(stmt)
                    except sqlite3.OperationalError:
                        pass
```

In `add()`, compute the stamp defensively before the INSERT (a memory write must never fail because of the stamp):
```python
        episode_id = f"ep-{uuid.uuid4().hex[:12]}"
        felt_value = felt_elapsed_s = felt_phrase = felt_compute_version = None
        if self._felt_time_reader is not None:
            try:
                ctx = self._felt_time_reader()
                if ctx:
                    felt_value = ctx.get("felt_value")
                    felt_elapsed_s = ctx.get("seconds_since_last_owner_contact", ctx.get("felt_elapsed_s"))
                    felt_phrase = ctx.get("felt_phrase")
                    felt_compute_version = ctx.get("felt_compute_version")
            except Exception:
                felt_value = felt_elapsed_s = felt_phrase = felt_compute_version = None
```
> Note: the live `time_sense_context()` returns `seconds_since_last_owner_contact`; the tests pass `felt_elapsed_s`. The `.get(..., ...)` fallback above accepts both so the column maps correctly either way.

Extend the INSERT (add the four columns + four `?` + four values):
```python
                c.execute(
                    "INSERT INTO episodes ("
                    "id, created_at, occurred_at, title, summary, "
                    "participants_json, emotional_tone, importance, "
                    "open_loop, source_memory_ids_json, source_kind, status, "
                    "authorship, memory_voice, "
                    "felt_value, felt_elapsed_s, felt_phrase, felt_compute_version"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        episode_id,
                        _now_iso(),
                        occurred_at,
                        title,
                        summary,
                        json.dumps(list(participants)),
                        emotional_tone,
                        int(importance),
                        open_loop,
                        json.dumps(list(source_memory_ids)),
                        source_kind,
                        "active",
                        authorship,
                        memory_voice,
                        felt_value,
                        felt_elapsed_s,
                        felt_phrase,
                        felt_compute_version,
                    ),
                )
```
> Confirm `_row_to_dict` / `get()` returns the new columns. Since `get()` does `SELECT *` and `_row_to_dict` maps the `sqlite3.Row`, the new columns appear automatically — verify it maps all row keys (if `_row_to_dict` enumerates a fixed field list, add the four keys there).

- [ ] **Step 4: Run the store tests, expect GREEN.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_episode_felt_time_stamp -v`
  Expected: PASS.

- [ ] **Step 5: Inject the reader in the daemon.** In `daemon/maez_daemon.py`:

Add the flag helper next to `continuous_time_sense_enabled()` (~:2611):
```python
def time_sense_stamp_enabled() -> bool:
    """Return True iff MAEZ_TIME_SENSE_STAMP is on. DEFAULT OFF. When on (AND the substrate is on),
    every EpisodeStore lived episode is stamped with the felt-time index."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_TIME_SENSE_STAMP")
```

Add the reader method on the daemon class (near `_time_sense_handle`, ~:2864):
```python
    def _episode_felt_time_reader(self):
        """Injected into EpisodeStore: returns the substrate felt-time context or None. Gated by
        MAEZ_TIME_SENSE_STAMP AND the substrate flag. Read-only; never raises into a memory write."""
        try:
            if not (time_sense_stamp_enabled() and continuous_time_sense_enabled()):
                return None
            return self._time_sense_handle().time_sense_context()
        except Exception:
            logger.debug("episode felt-time reader skipped", exc_info=True)
            return None
```

Wire it at the construction site (`daemon:2914`):
```python
        self.lived_episodes = EpisodeStore(
            str(_lived_dir / "lived_episodes.db"),
            felt_time_reader=self._episode_felt_time_reader,
        )
```
> `self._time_sense` is initialized to `None` in `__init__` (Slice 1); the reader is only called at `.add()` time (runtime), so the lazy handle is safe.

- [ ] **Step 6: Run a daemon-import smoke + the store tests again.**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -c "import daemon.maez_daemon as d; print('import ok', d.time_sense_stamp_enabled())"
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_episode_felt_time_stamp -v
```
Expected: `import ok False` (flag default off) and tests PASS.

- [ ] **Step 7: ruff + commit (behavior).**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/memory/episodes.py daemon/maez_daemon.py tests/test_episode_felt_time_stamp.py
git add core/memory/episodes.py daemon/maez_daemon.py tests/test_episode_felt_time_stamp.py
git commit -m "feat(memory): stamp every EpisodeStore episode with felt-time via injected substrate reader

## Predicted effect
EpisodeStore.add() now stamps felt_value/felt_elapsed_s/felt_phrase/felt_compute_version from an injected
read-only reader; the daemon injects time_sense_context() gated by MAEZ_TIME_SENSE_STAMP AND the substrate
flag. Flag-off (default) or None context -> all four NULL = behavior-identical. The value is substrate-
computed (not LLM-owned); reader errors never break a memory write.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch continuous-time-sense-slice2
```

---

### Task 4: Feed — the autonomous perception line

**Files:**
- Modify: `daemon/maez_daemon.py` (flag helper, `_build_cycle_focused_prompt` param, the line builder, the call site at :5166)
- Test: `tests/test_cycle_feed_time_sense.py` (create)

- [ ] **Step 1: Write the failing tests.** Create `tests/test_cycle_feed_time_sense.py`:

```python
import unittest
import daemon.maez_daemon as d
from daemon.maez_daemon import _build_cycle_focused_prompt, _cycle_feed_time_sense_line


class FeedLineBuilder(unittest.TestCase):
    def test_builds_perception_line_from_context(self):
        ctx = {"felt_value": 7.65, "felt_phrase": "a long quiet stretch",
               "felt_compute_version": 1, "seconds_since_last_owner_contact": 3 * 3600 + 12 * 60}
        line = d._format_time_sense_line(ctx)
        self.assertIn("3h 12m", line)
        self.assertIn("a long quiet stretch", line)
        self.assertTrue(line.startswith("Time:"))

    def test_line_is_perception_not_directive(self):
        ctx = {"felt_value": 9.0, "felt_phrase": "a long quiet stretch",
               "felt_compute_version": 1, "seconds_since_last_owner_contact": 36000}
        line = d._format_time_sense_line(ctx).lower()
        for imperative in ("should", "reach out", "you must", "go ", "send", "remind"):
            self.assertNotIn(imperative, line)   # states what IS, never what to DO


class FeedPromptInjection(unittest.TestCase):
    def test_prepends_perception_block_when_line_present(self):
        dec = _build_cycle_focused_prompt(
            legacy_prompt="LEGACY", candidates=[],
            time_sense_line="Time: ~3h 12m since the last owner contact. Felt: a long quiet stretch.",
        )
        self.assertIn("TIME SENSE", dec.prompt)
        self.assertIn("3h 12m", dec.prompt)
        # perception block sits BEFORE the evidence block
        self.assertLess(dec.prompt.index("TIME SENSE"), dec.prompt.index("CYCLE EVIDENCE"))

    def test_no_block_when_line_empty(self):
        dec = _build_cycle_focused_prompt(legacy_prompt="LEGACY", candidates=[], time_sense_line="")
        self.assertNotIn("TIME SENSE", dec.prompt)

    def test_cycle_packet_module_has_no_felt_time(self):
        # cycle_packet.py stays PURE — felt-time is wired in the daemon, not the packet builder.
        import inspect, core.cognition.cycle_packet as cp
        src = inspect.getsource(cp).lower()
        for token in ("felt_time", "felt time", "time_sense", "subjective_duration", "time sense"):
            self.assertNotIn(token, src)
```

- [ ] **Step 2: Run, expect RED.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cycle_feed_time_sense -v`
  Expected: FAIL — `_cycle_feed_time_sense_line` / `_format_time_sense_line` / the `time_sense_line` param don't exist.

- [ ] **Step 3: Add the feed flag + the line formatter + the builder.** In `daemon/maez_daemon.py`:

Flag helper (next to the others, ~:2611):
```python
def time_sense_feed_enabled() -> bool:
    """Return True iff MAEZ_TIME_SENSE_FEED is on. DEFAULT OFF. When on (AND the substrate is on), the
    autonomous focused-cognition packet carries a felt-time perception line."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_TIME_SENSE_FEED")
```

Pure formatter (module-level, near `_build_cycle_focused_prompt`):
```python
def _format_time_sense_line(ctx: dict) -> str:
    """Render a felt-time context into ONE perception line. Perception, never directive."""
    from core.evolution.subjective_duration import humanize_elapsed

    elapsed = humanize_elapsed(ctx.get("seconds_since_last_owner_contact", 0.0))
    phrase = ctx.get("felt_phrase", "")
    return f"Time: ~{elapsed} since the last owner contact. Felt: {phrase}."
```

The gated builder method on the daemon class (near `_episode_felt_time_reader`):
```python
    def _cycle_feed_time_sense_line(self) -> str:
        """The feed line for the autonomous cycle, or '' when absent (flags off / context None).
        Gated by MAEZ_TIME_SENSE_FEED AND the substrate flag; reads the truthful context only."""
        try:
            if not (time_sense_feed_enabled() and continuous_time_sense_enabled()):
                return ""
            ctx = self._time_sense_handle().time_sense_context()
            if not ctx:
                return ""
            return _format_time_sense_line(ctx)
        except Exception:
            logger.debug("cycle feed time-sense line skipped", exc_info=True)
            return ""
```

Add the `time_sense_line` param to `_build_cycle_focused_prompt` and prepend a perception block:
```python
def _build_cycle_focused_prompt(
    *,
    legacy_prompt: str,
    candidates,
    budget_tokens: int = 3000,
    time_sense_line: str = "",
) -> CycleFocusedPromptDecision:
    if not _cycle_focused_enabled():
        return CycleFocusedPromptDecision(prompt=legacy_prompt)
    try:
        from core.cognition import cycle_packet as _cycle_packet

        items = _cycle_packet.select_cycle_evidence(candidates, budget_tokens=budget_tokens)
        working_set = _cycle_packet.build_cycle_packet(items)
        _preamble = (
            f"=== TIME SENSE (perception) ===\n{time_sense_line}\n\n" if time_sense_line else ""
        )
        prompt = (
            f"{_preamble}"
            "=== CYCLE EVIDENCE (cite [E#]) ===\n"
            f"{working_set.ordered_evidence_text}\n\n"
            "=== CYCLE REFLECTION INSTRUCTION ===\n"
            f"{working_set.owner_question}\n"
        )
        return CycleFocusedPromptDecision(prompt=prompt, working_set=working_set)
    except Exception as exc:
        logger.warning("cycle focused packet failed, falling back to legacy megaprompt: %s", exc)
        return CycleFocusedPromptDecision(prompt=legacy_prompt)
```
> Preserve the ORIGINAL fallback `return` body exactly as it is in the file (the snippet above shortens it — keep whatever the real `except` branch returns).

Wire the call site (`daemon:5166`) to pass the line:
```python
        _cycle_prompt_decision = _build_cycle_focused_prompt(
            legacy_prompt=legacy_prompt,
            candidates=_cycle_candidates,
            time_sense_line=self._cycle_feed_time_sense_line(),
        )
```

- [ ] **Step 4: Run, expect GREEN.**
  `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cycle_feed_time_sense -v`
  Expected: all PASS.

- [ ] **Step 5: ruff + commit (behavior).**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py tests/test_cycle_feed_time_sense.py
git add daemon/maez_daemon.py tests/test_cycle_feed_time_sense.py
git commit -m "feat(time-sense): feed a felt-time perception line into the autonomous cycle packet

## Predicted effect
When MAEZ_TIME_SENSE_FEED AND the substrate are on, the autonomous focused-cognition prompt gains ONE
perception line ('Time: ~Xh Ym since the last owner contact. Felt: {phrase}.') from the truthful context,
prepended before the evidence block. Perception, never directive. Flag-off or None context -> no line =
behavior-identical. cycle_packet.py stays pure (wired in the daemon).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch continuous-time-sense-slice2
```

---

### Task 5: Whole-slice green + handoff + STOP at the gate

**Files:**
- Create: `docs/handoffs/2026-06-19-continuous-time-sense-slice2-handoff.md`

- [ ] **Step 1: Run the whole slice's test surface (named modules).**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_time_sense_context tests.test_episode_felt_time_stamp tests.test_cycle_feed_time_sense \
  tests.test_subjective_duration_continuous tests.test_subjective_duration -v
```
Expected: all GREEN. (If `tests.test_subjective_duration` shows the known pre-existing `static_boundaries`-style failures from prior slices, confirm they fail on `main` too and are NOT introduced here — same scoped-regression check the last slice taught.)

- [ ] **Step 2: Regression — foreground + 3b + heartbeat untouched.** Run the existing felt-time / episode regression modules (whichever exist) and confirm green; grep-confirm `daemon:5673` (foreground `subjective_duration_prompt_line`) and the 3b mint path and the heartbeat block are unchanged by `git diff main -- daemon/maez_daemon.py` (only the additions from this slice appear).

- [ ] **Step 3: ruff on the whole diff.**
  `/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py core/memory/episodes.py daemon/maez_daemon.py tests/test_time_sense_context.py tests/test_episode_felt_time_stamp.py tests/test_cycle_feed_time_sense.py`

- [ ] **Step 4: Write the handoff** `docs/handoffs/2026-06-19-continuous-time-sense-slice2-handoff.md` with: branch tip; the commit list; the Codex cross-lane anchors (truthful-reader-None-on-degraded-no-write / canary-excluded-contact-read / perception-not-directive / EpisodeStore-only-honest-scope + the memory-store inventory / no-durable-band / NOT-LLM-owned-stamp / flag-off-behavior-identical-schema-additive / foreground+3b+heartbeat untouched); the test surface + counts; and the owner-breath sequence:
  > Set `MAEZ_TIME_SENSE_FEED=1` and/or `MAEZ_TIME_SENSE_STAMP=1` in the daemon env (substrate already on); restart `maez`; witness — (feed) a self-initiated cycle thought that references the passing time as perception, exact-elapsed honest, no directive; (stamp) a freshly-written episode row carrying `felt_value`/`felt_elapsed_s`/`felt_phrase`/`felt_compute_version`, NULL when a flag is off.

- [ ] **Step 5: Commit the handoff (docs — NO predicted-effect) + STOP.**
```bash
git add docs/handoffs/2026-06-19-continuous-time-sense-slice2-handoff.md
git commit -m "docs(handoff): continuous time-sense slice2 feed-mind — review gate + owner-breath sequence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # MUST show: On branch continuous-time-sense-slice2
```
**STOP.** Do not merge, restart, or flip flags — owner-sovereign. Report branch tip + Task-0 inventory + test outputs + the Codex anchors + the owner-breath sequence.

---

## Self-review (controller)

- **Spec coverage:** truthful reader (Task 1) ✓; stamp schema (Task 2) + wiring (Task 3) ✓; feed (Task 4) ✓; two flags AND-gated ✓; canary-excluded contact (Task 1) ✓; honest-null via helper ✓; no durable band (Task 2 asserts absence) ✓; not-LLM-owned (Task 3 value-from-reader test) ✓; perception-not-directive (Task 4 test) ✓; cycle_packet purity (Task 4 test) ✓; memory-store inventory (Task 0) ✓; flag-off behavior-identical ✓; untouched surfaces (Task 0 + Task 5 diff check) ✓.
- **Type/name consistency:** `time_sense_context()` returns `seconds_since_last_owner_contact`; `EpisodeStore.add` maps it to the `felt_elapsed_s` column via the `.get(..., ...)` fallback that also accepts `felt_elapsed_s` (test convenience). `humanize_elapsed` lives in `subjective_duration.py`, used by `_format_time_sense_line`. Flags: `time_sense_feed_enabled` / `time_sense_stamp_enabled` mirror `continuous_time_sense_enabled`. Consistent across tasks.
- **Open verification handed to Task 0 / implementer:** exact salience column names (Task 0 Step 3); whether `_normalize_event_time` parses ISO strings (Task 1 Step 3 note); whether `_row_to_dict` enumerates a fixed field list (Task 3 Step 3 note); the real `except` fallback body of `_build_cycle_focused_prompt` (Task 4 Step 3 note).
