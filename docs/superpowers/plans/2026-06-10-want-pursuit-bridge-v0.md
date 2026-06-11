# Want→Pursuit Bridge v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bridge dormant wants to the existing wondering workshop — an active want seeds a templated, want-sourced pursuit question; the existing worker probes it under its own rails; a resolved pursuit raises an *advisory* `satisfied` proposal card; nothing writes the want ledger.

**Architecture:** A new pure-ish module `core/evolution/want_pursuit_bridge.py` plus two small read-only store helpers, wired into the daemon **after** the existing `advance_one(self)` call behind a default-OFF flag. The worker (`daemon/wondering_cycle.py`) is **not touched**. The bridge calls only `wonderings.add` + `PendingCardStore.create_card` (writes) and read helpers — **never** `wants.record_event` on any path.

**Tech Stack:** Python 3.11+, stdlib `sqlite3`, `unittest`. Runner: `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest). Branch `want-pursuit-bridge-v0` from `4714bd1`.

**Verified interfaces (from exploration):**
- `WonderingStore` (via `core.evolution.wonderings.get_store()`): `add(question, source="manual", *, bond_id="_LEGACY")->int`; `get(id)->dict|None` (row has `id, created_at, question, status, last_advanced, source, bond_id, conclusion?`); `list_open(limit)->list[dict]` (status in `open|active`); `list_all(limit)`. Statuses: `open|active|resolved|abandoned|blocked_pending_approval`.
- `advance_one(daemon, deadline)->dict|None`: `{"wondering_id", "action", "text": <conclusion>}` for `resolved`/`abandoned`; `{"wondering_id","action":"advanced"/"card_queued"/"no_probe", ...}` otherwise. **No `source` key** — look it up via `store.get(wondering_id)`.
- `PendingCardStore` (`core/decision/pending_cards.py`): `create_card(*, action, params, reason=None, plain_english=None, ...)->CardRecord` (`CardRecord.request_id`, `.params`, `.action`, `.status`, `.is_awaiting()`). `AWAITING_STATUSES = {OPEN, DEFERRED}`. Has `get`/`get_open_for_user`/`get_open_for_channel` but **no list-by-action** (Task 2 adds one).
- `Wants.active_wants()->list[dict]`: each row has `want_id`, `statement`, `active_state=="active"`.
- Daemon flag idiom: `(os.environ.get("MAEZ_X","") or "").strip() == "1"` (see `_cycle_doorman_enabled`, `maez_daemon.py:1680`). Attach point: right after `w_result = advance_one(self, deadline=cycle_deadline)` (`maez_daemon.py:~8981`), inside the existing wondering `try/except`.

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `core/evolution/wonderings.py` | Modify (+1 read method) | `list_by_source(source)` — want-pursuit trail / cooldown / per-want lookups |
| `core/decision/pending_cards.py` | Modify (+1 read method) | `list_open_by_action(action)` — open-proposal-card in-flight check |
| `core/evolution/want_pursuit_bridge.py` | Create | the bridge: template, trail, select, seed, advisory propose |
| `daemon/maez_daemon.py` | Modify (wondering stage) | flag-gated wiring after `advance_one`; heartbeat-safe |
| `tests/test_want_pursuit_bridge.py` | Create | bridge unit tests |
| `tests/test_want_pursuit_store_helpers.py` | Create | the two read-helper tests |
| `tests/test_want_pursuit_boundary.py` | Create | no `record_event`; worker untouched |

The worker `daemon/wondering_cycle.py` is **not modified** (a boundary test asserts it).

---

## Task 1: `WonderingStore.list_by_source` (read-only)

**Files:** Modify `core/evolution/wonderings.py` (add a method to the store class, near `list_open`); Test `tests/test_want_pursuit_store_helpers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_want_pursuit_store_helpers.py`:

```python
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution import wonderings


class ListBySourceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = wonderings.WonderingStore(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_list_by_source_returns_only_matching_source(self):
        a = self.store.add("q1", source="want:abc")
        self.store.add("q2", source="manual")
        c = self.store.add("q3", source="want:abc")
        ids = sorted(r["id"] for r in self.store.list_by_source("want:abc"))
        self.assertEqual(ids, sorted([a, c]))

    def test_list_by_source_empty_when_none_match(self):
        self.store.add("q", source="manual")
        self.assertEqual(self.store.list_by_source("want:zzz"), [])
```

(If `WonderingStore` is not the class name or it needs a different constructor, adjust to the real accessor found in `wonderings.py` — do not weaken the assertions.)

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_store_helpers.ListBySourceTests -v`
Expected: FAIL — `AttributeError: ... has no attribute 'list_by_source'`

- [ ] **Step 3: Write minimal implementation**

In `core/evolution/wonderings.py`, add to the store class (mirror `list_open`'s `self._lock, self._conn()` idiom):

```python
    def list_by_source(self, source: str) -> list[dict]:
        """Read-only: all wonderings with an exact source (any status), oldest first."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM wonderings WHERE source = ? "
                "ORDER BY COALESCE(last_advanced, created_at) ASC",
                (source,),
            ).fetchall()
            return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_store_helpers.ListBySourceTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/evolution/wonderings.py tests/test_want_pursuit_store_helpers.py
git commit -m "feat(wonderings): read-only list_by_source for want-pursuit bridge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `PendingCardStore.list_open_by_action` (read-only)

**Files:** Modify `core/decision/pending_cards.py` (add a method to `PendingCardStore`, near `get_open_for_user`); Test `tests/test_want_pursuit_store_helpers.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_want_pursuit_store_helpers.py`:

```python
from core.decision.pending_cards import PendingCardStore


class ListOpenByActionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = PendingCardStore(Path(self._tmp.name) / "cards.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_list_open_by_action_filters_by_action_and_open_status(self):
        self.store.create_card(action="want_terminal_proposal", params={"want_id": "a"})
        self.store.create_card(action="run_command", params={"cmd": "ls"})
        out = self.store.list_open_by_action("want_terminal_proposal")
        self.assertEqual([c.params.get("want_id") for c in out], ["a"])

    def test_list_open_by_action_empty_when_none(self):
        self.assertEqual(self.store.list_open_by_action("want_terminal_proposal"), [])
```

(Verify `PendingCardStore(db_path)` is the real constructor; adjust the path arg to match if needed.)

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_store_helpers.ListOpenByActionTests -v`
Expected: FAIL — `AttributeError: ... 'list_open_by_action'`

- [ ] **Step 3: Write minimal implementation**

In `core/decision/pending_cards.py`, add to `PendingCardStore` (mirror `get_open_for_user`'s connection + `_from_row` idiom; `AWAITING_STATUSES` is module-level):

```python
    def list_open_by_action(self, action: str) -> list["CardRecord"]:
        """Read-only: awaiting (OPEN/DEFERRED) cards with the given action."""
        placeholders = ",".join("?" for _ in AWAITING_STATUSES)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM pending_cards WHERE action = ? "
                f"AND status IN ({placeholders})",
                (action, *sorted(AWAITING_STATUSES)),
            ).fetchall()
        return [self._from_row(row) for row in rows]
```

(Match the real connection helper — `get_open_for_user` shows whether it's `self._connect()`/`self._conn()` and the row→record method name `_from_row`. Adjust names to the real ones; keep it read-only.)

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_store_helpers.ListOpenByActionTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/decision/pending_cards.py tests/test_want_pursuit_store_helpers.py
git commit -m "feat(pending_cards): read-only list_open_by_action for want-pursuit in-flight check

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Bridge — `template_question`, source helpers, `want_pursuit_trail`

**Files:** Create `core/evolution/want_pursuit_bridge.py`; Test `tests/test_want_pursuit_bridge.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_want_pursuit_bridge.py`:

```python
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution import wonderings, want_pursuit_bridge as wpb


class TemplateAndTrailTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.w = wonderings.WonderingStore(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_template_question_is_deterministic_and_bounded(self):
        q = wpb.template_question("I want the daemon logs to stay quiet at night")
        self.assertEqual(
            q,
            "What bounded, read-only investigation would advance this want: "
            "I want the daemon logs to stay quiet at night?",
        )

    def test_source_for_and_want_id_from(self):
        self.assertEqual(wpb.source_for("abc123"), "want:abc123")
        self.assertEqual(wpb.want_id_from_source("want:abc123"), "abc123")
        self.assertIsNone(wpb.want_id_from_source("manual"))

    def test_want_pursuit_trail_returns_source_linked(self):
        self.w.add("q1", source="want:abc")
        self.w.add("other", source="manual")
        trail = wpb.want_pursuit_trail(self.w, "abc")
        self.assertEqual([t["question"] for t in trail], ["q1"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge.TemplateAndTrailTests -v`
Expected: FAIL — `ModuleNotFoundError`/`AttributeError`

- [ ] **Step 3: Write minimal implementation**

Create `core/evolution/want_pursuit_bridge.py`:

```python
"""Want→Pursuit bridge v0 — seed work orders into the existing wondering
workshop and raise advisory satisfied-proposals. Writes nothing to the want
ledger; calls only wonderings.add + PendingCardStore.create_card (+ reads)."""

from __future__ import annotations

import logging
from typing import Any, Optional

_LOG = logging.getLogger(__name__)

WANT_SOURCE_PREFIX = "want:"
TERMINAL_PROPOSAL_ACTION = "want_terminal_proposal"


def template_question(want_statement: str) -> str:
    return (
        "What bounded, read-only investigation would advance this want: "
        f"{(want_statement or '').strip()}?"
    )


def source_for(want_id: str) -> str:
    return f"{WANT_SOURCE_PREFIX}{want_id}"


def want_id_from_source(source: str) -> Optional[str]:
    s = str(source or "")
    return s[len(WANT_SOURCE_PREFIX):] if s.startswith(WANT_SOURCE_PREFIX) else None


def want_pursuit_trail(wonderings_store, want_id: str) -> list[dict]:
    return wonderings_store.list_by_source(source_for(want_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge.TemplateAndTrailTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/evolution/want_pursuit_bridge.py tests/test_want_pursuit_bridge.py
git commit -m "feat(want-pursuit): bridge template + source helpers + trail

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Bridge — `select_want` (eligibility + one-in-flight + cooldown)

**Files:** Modify `core/evolution/want_pursuit_bridge.py`; Test `tests/test_want_pursuit_bridge.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_want_pursuit_bridge.py`:

```python
class _FakeWants:
    def __init__(self, rows):
        self._rows = rows

    def active_wants(self, limit=None):
        return list(self._rows)


class _FakeCards:
    def __init__(self, open_want_ids=()):
        self._ids = list(open_want_ids)

    def list_open_by_action(self, action):
        class _C:
            def __init__(self, wid):
                self.params = {"want_id": wid}
        return [_C(w) for w in self._ids]


class SelectWantTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.w = wonderings.WonderingStore(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def _want(self, wid, stmt="x"):
        return {"want_id": wid, "statement": stmt, "active_state": "active"}

    def test_no_active_wants_returns_none(self):
        got = wpb.select_want(_FakeWants([]), self.w, _FakeCards(), cooldown_s=3600, now=1000.0)
        self.assertIsNone(got)

    def test_global_one_in_flight_blocks_all(self):
        self.w.add("pursuing", source="want:other")  # open want-sourced wondering exists
        got = wpb.select_want(_FakeWants([self._want("a")]), self.w, _FakeCards(), cooldown_s=3600, now=1000.0)
        self.assertIsNone(got)

    def test_want_with_open_proposal_card_is_excluded(self):
        got = wpb.select_want(
            _FakeWants([self._want("a")]), self.w, _FakeCards(open_want_ids=["a"]),
            cooldown_s=3600, now=1000.0,
        )
        self.assertIsNone(got)

    def test_least_recently_pursued_chosen_never_pursued_first(self):
        # 'a' pursued recently (resolved so not open), 'b' never pursued
        wid = self.w.add("old", source="want:a")
        self.w.resolve(wid, "done", resolved_at=10.0)
        got = wpb.select_want(
            _FakeWants([self._want("a"), self._want("b")]), self.w, _FakeCards(),
            cooldown_s=1.0, now=10000.0,
        )
        self.assertEqual(got["want_id"], "b")

    def test_cooldown_excludes_recently_pursued(self):
        wid = self.w.add("recent", source="want:a")
        self.w.resolve(wid, "done", resolved_at=9999.0)
        got = wpb.select_want(
            _FakeWants([self._want("a")]), self.w, _FakeCards(),
            cooldown_s=3600, now=10000.0,
        )
        self.assertIsNone(got)  # within cooldown, no other candidate
```

(If `resolve(...)` signature differs, match the real one from Task-0 exploration of `wonderings.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge.SelectWantTests -v`
Expected: FAIL — `AttributeError: ... 'select_want'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/evolution/want_pursuit_bridge.py`:

```python
def _has_open_want_wondering(wonderings_store) -> bool:
    for w in wonderings_store.list_open(limit=200):
        if str(w.get("source", "")).startswith(WANT_SOURCE_PREFIX):
            return True
    return False


def _wants_with_open_proposal(cards_store) -> set[str]:
    out: set[str] = set()
    for card in cards_store.list_open_by_action(TERMINAL_PROPOSAL_ACTION):
        wid = (getattr(card, "params", None) or {}).get("want_id")
        if wid:
            out.add(str(wid))
    return out


def _last_pursuit_ts(wonderings_store, want_id: str) -> float:
    rows = want_pursuit_trail(wonderings_store, want_id)
    if not rows:
        return 0.0
    return max(float(r.get("created_at") or 0.0) for r in rows)


def select_want(wants_store, wonderings_store, cards_store, *, cooldown_s: float, now: float) -> Optional[dict]:
    """Least-recently-pursued eligible active want, or None.

    Eligible = active AND no open want_terminal_proposal card AND past cooldown.
    Returns None entirely if ANY want-sourced wondering is open (one in flight).
    """
    if _has_open_want_wondering(wonderings_store):
        return None
    blocked = _wants_with_open_proposal(cards_store)
    candidates = []
    for want in wants_store.active_wants():
        wid = str(want.get("want_id") or "")
        if not wid or wid in blocked:
            continue
        last = _last_pursuit_ts(wonderings_store, wid)
        if last and (now - last) < cooldown_s:
            continue
        candidates.append((last, want))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])  # never-pursued (0.0) first
    return candidates[0][1]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge.SelectWantTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/evolution/want_pursuit_bridge.py tests/test_want_pursuit_bridge.py
git commit -m "feat(want-pursuit): select_want (one-in-flight, open-card exclusion, cooldown, LRU)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Bridge — `seed_work_order` + `maybe_propose_terminal` (advisory, no ledger write)

**Files:** Modify `core/evolution/want_pursuit_bridge.py`; Test `tests/test_want_pursuit_bridge.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_want_pursuit_bridge.py`:

```python
class _RecordingCards:
    def __init__(self):
        self.created = []

    def create_card(self, *, action, params, reason=None, plain_english=None, **kw):
        self.created.append({"action": action, "params": params})
        class _R:
            request_id = "card-1"
        return _R()

    def list_open_by_action(self, action):
        return []


class SeedAndProposeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.w = wonderings.WonderingStore(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_seed_work_order_adds_want_sourced_wondering(self):
        wid = wpb.seed_work_order(self.w, {"want_id": "abc", "statement": "stay honest"})
        row = self.w.get(wid)
        self.assertEqual(row["source"], "want:abc")
        self.assertIn("stay honest", row["question"])

    def test_resolved_want_wondering_creates_advisory_card(self):
        wid = self.w.add("q", source="want:abc")
        cards = _RecordingCards()
        rid = wpb.maybe_propose_terminal(
            {"wondering_id": wid, "action": "resolved", "text": "found the cause"},
            self.w, cards,
        )
        self.assertEqual(rid, "card-1")
        self.assertEqual(len(cards.created), 1)
        c = cards.created[0]
        self.assertEqual(c["action"], "want_terminal_proposal")
        self.assertEqual(c["params"]["want_id"], "abc")
        self.assertEqual(c["params"]["proposed"], "satisfied")
        self.assertEqual(c["params"]["conclusion"], "found the cause")
        self.assertEqual(c["params"]["wondering_id"], wid)

    def test_abandoned_want_wondering_proposes_nothing(self):
        wid = self.w.add("q", source="want:abc")
        cards = _RecordingCards()
        rid = wpb.maybe_propose_terminal(
            {"wondering_id": wid, "action": "abandoned", "text": "dead end"}, self.w, cards
        )
        self.assertIsNone(rid)
        self.assertEqual(cards.created, [])

    def test_resolved_non_want_wondering_proposes_nothing(self):
        wid = self.w.add("q", source="manual")
        cards = _RecordingCards()
        rid = wpb.maybe_propose_terminal(
            {"wondering_id": wid, "action": "resolved", "text": "x"}, self.w, cards
        )
        self.assertIsNone(rid)
        self.assertEqual(cards.created, [])

    def test_non_resolved_actions_propose_nothing(self):
        wid = self.w.add("q", source="want:abc")
        cards = _RecordingCards()
        for action in ("advanced", "card_queued", "no_probe", "safety_refused"):
            self.assertIsNone(
                wpb.maybe_propose_terminal({"wondering_id": wid, "action": action}, self.w, cards)
            )
        self.assertEqual(cards.created, [])

    def test_none_result_is_safe(self):
        self.assertIsNone(wpb.maybe_propose_terminal(None, self.w, _RecordingCards()))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge.SeedAndProposeTests -v`
Expected: FAIL — `AttributeError: ... 'seed_work_order'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/evolution/want_pursuit_bridge.py`:

```python
def seed_work_order(wonderings_store, want: dict) -> int:
    want_id = str(want.get("want_id") or "")
    question = template_question(str(want.get("statement") or ""))
    wid = wonderings_store.add(question, source=source_for(want_id))
    _LOG.info("want-pursuit seeded work order: want=%s wondering=%s", want_id, wid)
    return wid


def maybe_propose_terminal(advance_result, wonderings_store, cards_store) -> Optional[str]:
    """Advisory only: a RESOLVED want-sourced wondering -> a satisfied proposal
    card. Abandoned / non-want / non-resolved -> nothing. NEVER writes the want
    ledger; NEVER applies a terminal."""
    if not advance_result or advance_result.get("action") != "resolved":
        return None
    wid = advance_result.get("wondering_id")
    row = wonderings_store.get(wid) if wid is not None else None
    if not row:
        return None
    want_id = want_id_from_source(str(row.get("source", "")))
    if not want_id:
        return None
    conclusion = str(advance_result.get("text") or row.get("conclusion") or "")
    card = cards_store.create_card(
        action=TERMINAL_PROPOSAL_ACTION,
        params={
            "want_id": want_id,
            "proposed": "satisfied",
            "conclusion": conclusion,
            "wondering_id": wid,
        },
        reason="want-pursuit: a resolved pursuit suggests this want may be satisfied",
        plain_english=(
            f"I pursued the want '{want_id}' and reached a conclusion. "
            "Do you want to mark it satisfied? (I won't close it myself.)"
        ),
    )
    rid = getattr(card, "request_id", None) or getattr(card, "id", None)
    _LOG.info("want-pursuit advisory proposal: want=%s wondering=%s card=%s", want_id, wid, rid)
    return rid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge.SeedAndProposeTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/evolution/want_pursuit_bridge.py tests/test_want_pursuit_bridge.py
git commit -m "feat(want-pursuit): seed_work_order + advisory maybe_propose_terminal (no ledger write)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Daemon wiring (flag-gated, heartbeat-safe) — `## Predicted effect`

**Files:** Modify `daemon/maez_daemon.py` (a flag helper near the other `_*_enabled` helpers; the wiring after `advance_one` at ~8981); Test `tests/test_want_pursuit_bridge.py`

**Exploration before coding:** confirm the wondering store accessor used by the worker (`from core.evolution.wonderings import get_store`), the card store accessor (the worker's `_queue_card` reads `pipe.card_store` — find how the daemon reaches the decision pipeline / card store), and `daemon.wants`. The bridge functions take stores as params; the wiring passes the real ones.

- [ ] **Step 1: Write the failing test (flag helper + structural wiring)**

Append to `tests/test_want_pursuit_bridge.py`:

```python
import inspect
import os


class DaemonFlagAndWiringTests(unittest.TestCase):
    def test_flag_default_off(self):
        from daemon import maez_daemon
        old = os.environ.pop("MAEZ_WANT_PURSUIT_ENABLED", None)
        try:
            self.assertFalse(maez_daemon._want_pursuit_enabled())
            os.environ["MAEZ_WANT_PURSUIT_ENABLED"] = "1"
            self.assertTrue(maez_daemon._want_pursuit_enabled())
        finally:
            os.environ.pop("MAEZ_WANT_PURSUIT_ENABLED", None)
            if old is not None:
                os.environ["MAEZ_WANT_PURSUIT_ENABLED"] = old

    def test_loop_wires_bridge_after_advance_one_and_behind_flag(self):
        from daemon import maez_daemon
        src = inspect.getsource(maez_daemon.MaezDaemon._loop)
        advance_idx = src.index("advance_one(self")
        backward_idx = src.index("maybe_propose_terminal", advance_idx)
        flag_idx = src.index("_want_pursuit_enabled(", advance_idx)
        seed_idx = src.index("seed_work_order", advance_idx)
        self.assertLess(advance_idx, backward_idx)   # backward after advance_one
        self.assertLess(backward_idx, flag_idx)      # forward (flag) after backward
        self.assertLess(flag_idx, seed_idx)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge.DaemonFlagAndWiringTests -v`
Expected: FAIL — `_want_pursuit_enabled` missing / substring not found.

- [ ] **Step 3: Write minimal implementation**

(a) Add the flag helper near `_cycle_doorman_enabled` (`maez_daemon.py:~1680`):

```python
def _want_pursuit_enabled(environ: object | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return (env.get("MAEZ_WANT_PURSUIT_ENABLED", "") or "").strip() == "1"
```

(b) At the wondering site, right after the existing `if w_result: logger.info("Wondering advance: %s", w_result)` block and still inside the same `try`, add:

```python
                    # Want→Pursuit bridge (default-OFF). Backward first (advisory
                    # proposal for a resolved want-wondering), then a flag-gated
                    # forward seed. Both fully wrapped — never break the heartbeat.
                    if _want_pursuit_enabled():
                        try:
                            from core.evolution import want_pursuit_bridge as _wpb
                            from core.evolution.wonderings import get_store as _w_get_store
                            _w_store = _w_get_store()
                            _cards = self._want_pursuit_card_store()
                            if _cards is not None:
                                _wpb.maybe_propose_terminal(w_result, _w_store, _cards)
                                if not _wpb._has_open_want_wondering(_w_store):
                                    _wants = getattr(self, "wants", None)
                                    if _wants is not None:
                                        _picked = _wpb.select_want(
                                            _wants, _w_store, _cards,
                                            cooldown_s=WANT_PURSUIT_COOLDOWN_S,
                                            now=time.time(),
                                        )
                                        if _picked is not None:
                                            _wpb.seed_work_order(_w_store, _picked)
                        except Exception:
                            logger.warning("want-pursuit bridge step failed; skipping", exc_info=True)
```

Add a module constant near the other cycle constants: `WANT_PURSUIT_COOLDOWN_S = 6 * 3600` (6h — conservative; one pursuit per want per ~6h). Add a small method `_want_pursuit_card_store(self)` that returns the pending-card store the worker uses (mirror `wondering_cycle._queue_card`'s `pipe.card_store` path; return `None` on any failure). Confirm `time` and `os` are imported at module scope (they are — used by the doorman/flag helpers).

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge.DaemonFlagAndWiringTests -v`
Expected: PASS

- [ ] **Step 5: Commit (`## Predicted effect`)**

```bash
git add daemon/maez_daemon.py tests/test_want_pursuit_bridge.py
git commit -m "feat(want-pursuit): wire bridge into the wondering stage (default-OFF, heartbeat-safe)

## Predicted effect
While MAEZ_WANT_PURSUIT_ENABLED is unset (default), nothing changes. When the
owner enables it: after the existing wondering probe each cycle, a resolved
want-sourced wondering raises an advisory want_terminal_proposal card (never an
applied terminal); then, if no want-sourced wondering is open, one least-
recently-pursued eligible active want (past cooldown, no open proposal card) is
seeded as a new want-sourced wondering for the worker to probe next cycle. No
want ledger event is ever written by the bridge; any failure is swallowed and
the heartbeat continues.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Boundary test + floor + handoff + STOP

**Files:** Create `tests/test_want_pursuit_boundary.py`; Create `docs/handoffs/2026-06-10-want-pursuit-bridge-v0-for-review.md`

- [ ] **Step 1: Write the boundary test**

Create `tests/test_want_pursuit_boundary.py`:

```python
import ast
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "core" / "evolution" / "want_pursuit_bridge.py"


class BoundaryTests(unittest.TestCase):
    def test_bridge_never_references_record_event_or_wants_writer(self):
        src = BRIDGE.read_text(encoding="utf-8")
        self.assertNotIn("record_event", src)
        self.assertNotIn("from core.evolution.wants", src)
        self.assertNotIn("import wants", src)

    def test_bridge_imports_no_lifecycle_writer(self):
        tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
            elif isinstance(node, ast.Import):
                names += [a.name for a in node.names]
        for n in names:
            self.assertNotIn("wants", n.split("."))

    def test_worker_file_untouched(self):
        # wondering_cycle.py must have no diff vs main on this branch
        out = subprocess.run(
            ["git", "diff", "--name-only", "62e2c8a..HEAD"],
            cwd=str(ROOT), capture_output=True, text=True,
        ).stdout
        self.assertNotIn("daemon/wondering_cycle.py", out)
```

(Use the real merge-base `4714bd1` if `62e2c8a` is not the base on this branch; the point is "worker file unchanged on this branch.")

- [ ] **Step 2: Run it**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_boundary -v`
Expected: PASS (the bridge holds the boundary).

- [ ] **Step 3: Full focused floor**

Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_want_pursuit_store_helpers \
  tests.test_want_pursuit_bridge \
  tests.test_want_pursuit_boundary \
  tests.test_wants_lifecycle_d16 -v
```
Expected: all PASS. Then ruff: `cd /home/rohit/maez && .venv/bin/ruff check core/evolution/want_pursuit_bridge.py core/evolution/wonderings.py core/decision/pending_cards.py daemon/maez_daemon.py tests/test_want_pursuit_*.py` → `All checks passed!`. Then `git diff --check 4714bd1..HEAD` → clean.

- [ ] **Step 4: Handoff doc + STOP**

Create `docs/handoffs/2026-06-10-want-pursuit-bridge-v0-for-review.md` (Codex→Claude review brief) documenting: the bridge shape; the **review anchors** (below); verification outputs; and the owner-breath sequence — merge (local ff, no push) → enable `MAEZ_WANT_PURSUIT_ENABLED=1` → restart → witness (one active want → seeded want-wondering → worker read-only probe → receipt via `want_pursuit_trail` → on resolve, an advisory `satisfied` card, NOT an applied terminal; confirm the want ledger gains no event). Mark: no merge, no flag-enable, no restart, no witness.

**Review anchors (the acceptance contract):**
1. The bridge calls **only** `wonderings.add` + `PendingCardStore.create_card` for writes; it never imports or calls `wants.record_event` (boundary test).
2. `satisfied`-only; a worker-`abandoned` want-wondering proposes nothing; non-want / non-resolved propose nothing.
3. One pursuit in flight (no open want-sourced wondering) AND a want with an open `want_terminal_proposal` card is excluded from selection.
4. `daemon/wondering_cycle.py` is untouched.
5. Default-OFF: with the flag unset, the wiring is fully dormant (no seed, no proposal).
6. Heartbeat-safe: every bridge step is wrapped; a failure is logged and the cycle continues.
7. Attach point: bridge runs after `advance_one`; backward before forward; new want-wondering probed next cycle.

- [ ] **Step 5: Commit + STOP**

```bash
git add docs/handoffs/2026-06-10-want-pursuit-bridge-v0-for-review.md
git commit -m "docs(want-pursuit): v0 review handoff + STOP before merge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**STOP. No merge, no flag-enable, no restart, no witness.** Report branch tip + verification outputs; Claude reviews against the seven anchors.

---

## Self-Review (against the spec)

- Forward (template, not LLM; LRU + cooldown selection; `source="want:<id>"` seed): Tasks 3–5. ✓
- One-in-flight = open want-wondering OR open proposal card: Task 4 (`_has_open_want_wondering` + `_wants_with_open_proposal`). ✓
- Worker reused, zero edits: Task 7 boundary test. ✓
- Backward advisory-only, `satisfied`-only, abandoned→nothing, never `record_event`: Task 5 + Task 7 boundary. ✓
- Receipt = source-link, no want event: Task 3 `want_pursuit_trail`; no `record_event` anywhere. ✓
- Attach point after `advance_one`, backward-then-forward, one-cycle buffer: Task 6 structural test. ✓
- Default-OFF flag, heartbeat-safe, logged: Task 6. ✓
- Read helpers in schema-owner modules (read-only): Tasks 1–2. ✓

Placeholder scan: none. Signature consistency: `template_question`, `source_for`, `want_id_from_source`, `want_pursuit_trail`, `select_want(wants, wonderings, cards, *, cooldown_s, now)`, `seed_work_order(wonderings, want)`, `maybe_propose_terminal(result, wonderings, cards)`, `list_by_source`, `list_open_by_action` — consistent across tasks.
