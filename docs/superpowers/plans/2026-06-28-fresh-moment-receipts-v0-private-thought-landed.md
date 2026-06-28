# Fresh-Moment Receipts v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a flag-gated, content-light sidecar receipt each time the lean idle heartbeat stores a private thought, without mutating the private-thoughts diary or writing downstream.

**Architecture:** Create a small `core/cognition/fresh_moment_receipts.py` sidecar store. Wire `daemon/maez_daemon.py` to record a receipt only after `run_lean_idle_heartbeat()` returns `stored=True`, using only content-light heartbeat receipt fields (`thought_id`, `output_sha256`, `note_chars`). Add backup-manifest coverage so the new welfare store is protected by the existing backup rail.

**Tech Stack:** Python stdlib (`sqlite3`, `hashlib`, `os`, `time`, `pathlib`), existing `unittest` suite, existing Maez daemon env-flag pattern, existing backup manifest.

---

## Task 0: Reconfirm Pinned Seams

**Files:**
- Read: `docs/proofs/2026-06-28-fresh-moment-receipts-v0-task0.md`
- Read: `core/cognition/lean_idle_heartbeat.py`
- Read: `core/infra/private_thoughts.py`
- Read: `daemon/maez_daemon.py`

- [ ] **Step 1: Re-run the seam checks**

Run:

```bash
cd /home/rohit/maez
nl -ba core/cognition/lean_idle_heartbeat.py | sed -n '20,28p;431,470p'
nl -ba core/infra/private_thoughts.py | sed -n '313,321p;591,638p;1127,1150p'
nl -ba daemon/maez_daemon.py | sed -n '5352,5376p'
nl -ba core/evolution/drive_driven_curiosity.py | sed -n '268,274p;389,407p'
```

Expected:
- `HEARTBEAT_VERSION = "lean_idle_heartbeat.v0"`.
- `run_lean_idle_heartbeat()` calls `private_thoughts.record_signal`.
- `record_signal()` returns the inserted `thought_id`.
- `private_thoughts` has `thought_id INTEGER PRIMARY KEY AUTOINCREMENT`.
- daemon wrapper has a post-result section after logging the lean-idle receipt.
- `PRIVATE_THOUGHT_LANDED` remains deferred because private thoughts lack bond shape.
- `private_owner` remains the existing drive-curiosity single-owner default.

- [ ] **Step 2: Stop if any pinned seam moved**

If any expected item is false, do not implement. Update the spec and return to review.

## Task 1: Add the Sidecar Store

**Files:**
- Create: `core/cognition/fresh_moment_receipts.py`
- Create: `tests/test_fresh_moment_receipts.py`

- [ ] **Step 1: Write failing tests for schema, content-lightness, and value-neutrality**

Create `tests/test_fresh_moment_receipts.py`:

```python
import ast
import tempfile
import unittest
from pathlib import Path


class FreshMomentReceiptsTest(unittest.TestCase):
    def test_record_private_thought_landed_writes_content_light_row(self):
        from core.cognition.fresh_moment_receipts import (
            FRESH_MOMENT_BOND_ID,
            FRESH_MOMENT_RECEIPTS_VERSION,
            FreshMomentReceipts,
            MOMENT_PRIVATE_THOUGHT_LANDED,
        )

        with tempfile.TemporaryDirectory() as td:
            store = FreshMomentReceipts(Path(td) / "fresh_moment_receipts.db")
            receipt_id = store.record_private_thought_landed(
                thought_id=42,
                source="lean_idle_heartbeat.v0",
                bond_id=FRESH_MOMENT_BOND_ID,
                content_sha256="0123456789abcdef",
                content_len=37,
                created_at=123.5,
            )

            rows = store.recent(limit=5)

        self.assertEqual(receipt_id, 1)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["moment_kind"], MOMENT_PRIVATE_THOUGHT_LANDED)
        self.assertEqual(row["thought_id"], 42)
        self.assertEqual(row["source"], "lean_idle_heartbeat.v0")
        self.assertEqual(row["bond_id"], FRESH_MOMENT_BOND_ID)
        self.assertEqual(row["content_sha256"], "0123456789abcdef")
        self.assertEqual(row["content_len"], 37)
        self.assertEqual(row["schema_version"], FRESH_MOMENT_RECEIPTS_VERSION)

    def test_schema_contains_no_value_judgment_columns(self):
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        with tempfile.TemporaryDirectory() as td:
            store = FreshMomentReceipts(Path(td) / "fresh_moment_receipts.db")
            columns = set(store.column_names())

        forbidden = {"salience", "score", "importance", "rank", "value", "matters"}
        self.assertTrue(forbidden.isdisjoint(columns), columns)

    def test_schema_contains_no_raw_text_columns(self):
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        with tempfile.TemporaryDirectory() as td:
            store = FreshMomentReceipts(Path(td) / "fresh_moment_receipts.db")
            columns = set(store.column_names())

        forbidden = {"content", "text", "thought_text", "raw_text", "note", "prompt"}
        self.assertTrue(forbidden.isdisjoint(columns), columns)

    def test_db_file_does_not_contain_raw_thought_text(self):
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        secret = "SECRET PRIVATE THOUGHT TEXT"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fresh_moment_receipts.db"
            store = FreshMomentReceipts(path)
            store.record_private_thought_landed(
                thought_id=1,
                source="lean_idle_heartbeat.v0",
                bond_id="private_owner",
                content_sha256="aaaaaaaaaaaaaaaa",
                content_len=len(secret),
                created_at=1.0,
            )
            blob = path.read_bytes()

        self.assertNotIn(secret.encode(), blob)

    def test_writer_imports_no_downstream_organs(self):
        src = Path("core/cognition/fresh_moment_receipts.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        forbidden = (
            "core.evolution.wonderings",
            "core.wonderings",
            "core.evolution.wants",
            "core.wants",
            "core.cognition.salience_ledger",
            "core.evolution.dream_state",
            "core.actions.action_engine",
            "core.soul_editor",
            "core.evolution.soul_loader",
        )
        self.assertTrue(set(forbidden).isdisjoint(imported), imported)

    def test_default_path_points_to_memory(self):
        from core.cognition.fresh_moment_receipts import fresh_moment_receipts_db_path

        path = fresh_moment_receipts_db_path()

        self.assertEqual(path.name, "fresh_moment_receipts.db")
        self.assertEqual(path.parent.name, "memory")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail because module is absent**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_fresh_moment_receipts -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.cognition.fresh_moment_receipts'`.

- [ ] **Step 3: Implement the sidecar module**

Create `core/cognition/fresh_moment_receipts.py`:

```python
"""Fresh-moment receipts v0.

Content-light sidecar receipts for factual Maez-internal moments. This module
is a leaf: it does not import wonderings, wants, salience, dream state,
action engine, soul writers, or private-thought raw readers.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path


FRESH_MOMENT_RECEIPTS_VERSION = "fresh_moment_receipts.v0"
FRESH_MOMENT_RECEIPTS_PATH_ENV = "MAEZ_FRESH_MOMENT_RECEIPTS_PATH"
MOMENT_PRIVATE_THOUGHT_LANDED = "private_thought_landed"
FRESH_MOMENT_BOND_ID = "private_owner"


def _default_fresh_moment_receipts_path() -> Path:
    override = os.environ.get(FRESH_MOMENT_RECEIPTS_PATH_ENV)
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir

        return memory_dir() / "fresh_moment_receipts.db"
    except Exception:
        return Path(__file__).resolve().parents[2] / "memory" / "fresh_moment_receipts.db"


def fresh_moment_receipts_db_path() -> Path:
    """Return the configured fresh-moment receipt path without initializing it."""
    return _default_fresh_moment_receipts_path()


class FreshMomentReceipts:
    """Content-light sidecar store for factual fresh-moment receipts."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fresh_moment_receipts (
                    receipt_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at      REAL NOT NULL,
                    moment_kind     TEXT NOT NULL,
                    thought_id      INTEGER NOT NULL,
                    source          TEXT NOT NULL,
                    bond_id         TEXT NOT NULL,
                    content_sha256  TEXT NOT NULL,
                    content_len     INTEGER NOT NULL,
                    schema_version  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fmr_kind_created "
                "ON fresh_moment_receipts(moment_kind, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fmr_thought "
                "ON fresh_moment_receipts(thought_id)"
            )
            conn.commit()
        finally:
            conn.close()

    def record_private_thought_landed(
        self,
        *,
        thought_id: int,
        source: str,
        bond_id: str,
        content_sha256: str,
        content_len: int,
        created_at: float | None = None,
    ) -> int:
        if int(thought_id) <= 0:
            raise ValueError("thought_id must be positive")
        source = str(source or "").strip()
        if not source:
            raise ValueError("source must be non-empty")
        bond_id = str(bond_id or "").strip()
        if not bond_id:
            raise ValueError("bond_id must be non-empty")
        content_sha256 = str(content_sha256 or "").strip()
        if not content_sha256:
            raise ValueError("content_sha256 must be non-empty")
        content_len = int(content_len)
        if content_len < 0:
            raise ValueError("content_len must be non-negative")

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """INSERT INTO fresh_moment_receipts
                   (created_at, moment_kind, thought_id, source, bond_id,
                    content_sha256, content_len, schema_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    float(time.time() if created_at is None else created_at),
                    MOMENT_PRIVATE_THOUGHT_LANDED,
                    int(thought_id),
                    source,
                    bond_id,
                    content_sha256,
                    content_len,
                    FRESH_MOMENT_RECEIPTS_VERSION,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def recent(self, limit: int = 20) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM fresh_moment_receipts ORDER BY receipt_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        return [dict(row) for row in rows]

    def column_names(self) -> list[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM fresh_moment_receipts LIMIT 0")
            return [desc[0] for desc in cursor.description]
        finally:
            conn.close()
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_fresh_moment_receipts -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/fresh_moment_receipts.py tests/test_fresh_moment_receipts.py
git commit -m "feat(cognition): add fresh moment receipt sidecar"
```

## Task 2: Wire the Heartbeat Daemon Path

**Files:**
- Modify: `daemon/maez_daemon.py`
- Modify: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Write failing daemon wiring tests**

First extend the imports at the top of `tests/test_lean_idle_daemon.py`:

```python
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import tempfile
import unittest
```

Then append tests to `tests/test_lean_idle_daemon.py` near the existing lean-idle tests:

```python
    def test_fresh_moment_receipt_records_from_stored_heartbeat_without_raw_text(self) -> None:
        from daemon.maez_daemon import MaezDaemon, _HEARTBEAT_OK
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fresh_moment_receipts.db"
            daemon = object.__new__(MaezDaemon)
            daemon.cycle_count = 21
            daemon.private_thoughts = object()
            daemon._fresh_moment_receipts = FreshMomentReceipts(path)
            daemon._salience_broker_baseline = None
            daemon._lean_idle_self_card_text = lambda: "SELF CARD"
            daemon._lean_idle_private_signal_summary = lambda: {}
            daemon._lean_idle_time_facts = lambda: {}
            daemon._lean_idle_body_state = lambda: {}
            daemon._lean_idle_open_loops = lambda: {}
            daemon._lean_idle_recent_private_thoughts = lambda: ()
            secret = "SECRET PRIVATE THOUGHT TEXT"
            fake_result = SimpleNamespace(
                intercepted=True,
                return_text=_HEARTBEAT_OK,
                stored=True,
                thought_id=77,
                skip_reason="none",
                receipt={
                    "mode": "enabled",
                    "stored": True,
                    "note_chars": len(secret),
                    "output_sha256": "0123456789abcdef",
                    "skip_reason": "none",
                },
            )

            with mock.patch.dict(
                "os.environ",
                {
                    "MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1",
                    "MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW": "1",
                },
                clear=True,
            ):
                with mock.patch(
                    "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat",
                    return_value=fake_result,
                ):
                    result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

            rows = daemon._fresh_moment_receipts.recent(limit=5)
            blob = path.read_bytes()

        self.assertEqual(result, _HEARTBEAT_OK)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["moment_kind"], "private_thought_landed")
        self.assertEqual(rows[0]["thought_id"], 77)
        self.assertEqual(rows[0]["source"], "lean_idle_heartbeat.v0")
        self.assertEqual(rows[0]["bond_id"], "private_owner")
        self.assertEqual(rows[0]["content_sha256"], "0123456789abcdef")
        self.assertEqual(rows[0]["content_len"], len(secret))
        self.assertNotIn(secret.encode(), blob)

    def test_fresh_moment_receipt_flag_off_records_nothing(self) -> None:
        from daemon.maez_daemon import MaezDaemon, _HEARTBEAT_OK
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        with tempfile.TemporaryDirectory() as td:
            daemon = object.__new__(MaezDaemon)
            daemon.cycle_count = 22
            daemon.private_thoughts = object()
            daemon._fresh_moment_receipts = FreshMomentReceipts(Path(td) / "fresh_moment_receipts.db")
            daemon._salience_broker_baseline = None
            daemon._lean_idle_self_card_text = lambda: "SELF CARD"
            daemon._lean_idle_private_signal_summary = lambda: {}
            daemon._lean_idle_time_facts = lambda: {}
            daemon._lean_idle_body_state = lambda: {}
            daemon._lean_idle_open_loops = lambda: {}
            daemon._lean_idle_recent_private_thoughts = lambda: ()
            fake_result = SimpleNamespace(
                intercepted=True,
                return_text=_HEARTBEAT_OK,
                stored=True,
                thought_id=78,
                skip_reason="none",
                receipt={"stored": True, "note_chars": 4, "output_sha256": "abcd"},
            )

            with mock.patch.dict(
                "os.environ",
                {"MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1"},
                clear=True,
            ):
                with mock.patch(
                    "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat",
                    return_value=fake_result,
                ):
                    daemon._maybe_run_lean_idle_heartbeat({}, _gate())

            rows = daemon._fresh_moment_receipts.recent(limit=5)

        self.assertEqual(rows, [])

    def test_fresh_moment_receipt_flag_off_does_not_initialize_store(self) -> None:
        from daemon.maez_daemon import MaezDaemon, _HEARTBEAT_OK

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fresh_moment_receipts.db"
            daemon = object.__new__(MaezDaemon)
            daemon.cycle_count = 22
            daemon.private_thoughts = object()
            daemon._fresh_moment_receipts = None
            daemon._salience_broker_baseline = None
            daemon._lean_idle_self_card_text = lambda: "SELF CARD"
            daemon._lean_idle_private_signal_summary = lambda: {}
            daemon._lean_idle_time_facts = lambda: {}
            daemon._lean_idle_body_state = lambda: {}
            daemon._lean_idle_open_loops = lambda: {}
            daemon._lean_idle_recent_private_thoughts = lambda: ()
            fake_result = SimpleNamespace(
                intercepted=True,
                return_text=_HEARTBEAT_OK,
                stored=True,
                thought_id=78,
                skip_reason="none",
                receipt={"stored": True, "note_chars": 4, "output_sha256": "abcd"},
            )

            with mock.patch.dict(
                "os.environ",
                {
                    "MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1",
                    "MAEZ_FRESH_MOMENT_RECEIPTS_PATH": str(path),
                },
                clear=True,
            ):
                with mock.patch(
                    "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat",
                    return_value=fake_result,
                ):
                    daemon._maybe_run_lean_idle_heartbeat({}, _gate())

            self.assertFalse(path.exists())

    def test_fresh_moment_receipt_writer_failsoft(self) -> None:
        from daemon.maez_daemon import MaezDaemon, _HEARTBEAT_OK

        class BrokenReceipts:
            def record_private_thought_landed(self, **_kwargs):
                raise RuntimeError("boom")

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 23
        daemon.private_thoughts = object()
        daemon._fresh_moment_receipts = BrokenReceipts()
        daemon._salience_broker_baseline = None
        daemon._lean_idle_self_card_text = lambda: "SELF CARD"
        daemon._lean_idle_private_signal_summary = lambda: {}
        daemon._lean_idle_time_facts = lambda: {}
        daemon._lean_idle_body_state = lambda: {}
        daemon._lean_idle_open_loops = lambda: {}
        daemon._lean_idle_recent_private_thoughts = lambda: ()
        fake_result = SimpleNamespace(
            intercepted=True,
            return_text=_HEARTBEAT_OK,
            stored=True,
            thought_id=79,
            skip_reason="none",
            receipt={"stored": True, "note_chars": 4, "output_sha256": "abcd"},
        )

        with mock.patch.dict(
            "os.environ",
            {
                "MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1",
                "MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW": "1",
            },
            clear=True,
        ):
            with mock.patch(
                "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat",
                return_value=fake_result,
            ):
                result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertEqual(result, _HEARTBEAT_OK)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_lean_idle_daemon -v
```

Expected: FAIL because daemon does not yet define or call fresh-moment receipt helpers.

- [ ] **Step 3: Implement daemon helpers and call site**

Modify `daemon/maez_daemon.py`:

1. Add flag helper near the lean-idle flag helpers:

```python
def _fresh_moment_receipts_shadow_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW", environ=environ)
```

2. In `MaezDaemon.__init__`, initialize the lazy store handle near `_salience_ledger`:

```python
self._fresh_moment_receipts = None
```

3. Add lazy getter near `_salience_ledger_get()`:

```python
    def _fresh_moment_receipts_get(self):
        store = getattr(self, "_fresh_moment_receipts", None)
        if store is not None:
            return store
        from core.cognition.fresh_moment_receipts import (
            FreshMomentReceipts,
            fresh_moment_receipts_db_path,
        )

        store = FreshMomentReceipts(fresh_moment_receipts_db_path())
        self._fresh_moment_receipts = store
        return store
```

4. Add a fail-soft recorder helper near `_record_salience_outcomes()`:

```python
    def _maybe_record_fresh_moment_receipt(self, result) -> int | None:
        if not _fresh_moment_receipts_shadow_enabled():
            return None
        receipt = getattr(result, "receipt", {}) or {}
        if not bool(getattr(result, "stored", receipt.get("stored", False))):
            return None
        thought_id = getattr(result, "thought_id", None)
        if thought_id is None:
            return None
        content_sha256 = str(receipt.get("output_sha256") or "").strip()
        if not content_sha256:
            return None
        try:
            from core.cognition.fresh_moment_receipts import FRESH_MOMENT_BOND_ID
            from core.cognition.lean_idle_heartbeat import HEARTBEAT_VERSION

            receipt_id = self._fresh_moment_receipts_get().record_private_thought_landed(
                thought_id=int(thought_id),
                source=HEARTBEAT_VERSION,
                bond_id=FRESH_MOMENT_BOND_ID,
                content_sha256=content_sha256,
                content_len=int(receipt.get("note_chars") or 0),
            )
            logger.info(
                "fresh_moment_receipt receipt=%s",
                json.dumps(
                    {
                        "schema_version": "fresh_moment_receipts.v0",
                        "moment_kind": "private_thought_landed",
                        "stored": True,
                        "receipt_id": int(receipt_id),
                        "thought_id": int(thought_id),
                        "source": HEARTBEAT_VERSION,
                        "bond_id": FRESH_MOMENT_BOND_ID,
                    },
                    sort_keys=True,
                ),
            )
            return int(receipt_id)
        except Exception as exc:
            logger.info(
                "fresh_moment_receipt receipt=%s",
                json.dumps(
                    {
                        "schema_version": "fresh_moment_receipts.v0",
                        "moment_kind": "private_thought_landed",
                        "stored": False,
                        "skip_reason": "error",
                        "error_class": exc.__class__.__name__,
                    },
                    sort_keys=True,
                ),
            )
            return None
```

5. Call it after the lean-idle result receipt is logged and before salience outcomes:

```python
        self._maybe_record_fresh_moment_receipt(result)
```

- [ ] **Step 4: Run daemon tests and verify they pass**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_lean_idle_daemon -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "feat(daemon): record fresh moment receipts after private thoughts"
```

## Task 3: Prove No Diary Mutation or Downstream Growth

**Files:**
- Modify: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Add no-diary-mutation test**

Append to `tests/test_lean_idle_daemon.py`:

```python
    def test_fresh_moment_receipt_does_not_mutate_private_thought_row(self) -> None:
        from daemon.maez_daemon import MaezDaemon, _HEARTBEAT_OK
        from core.infra.private_thoughts import PrivateThoughts
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        with tempfile.TemporaryDirectory() as td:
            private_store = PrivateThoughts(Path(td) / "private_thoughts.db")
            thought_id = private_store.record_signal(
                content="A private note that must not be copied.",
                signal_kind="self_wondering",
                producer_id="self_wondering",
                source="lean_idle_heartbeat.v0",
                subject="maez_internal_state",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=("private_reader", "audit_trace"),
                context_extra={"output_sha256": "before"},
                memory_phase="gestation",
            )
            before = private_store.get_thought(thought_id)

            daemon = object.__new__(MaezDaemon)
            daemon.cycle_count = 24
            daemon.private_thoughts = private_store
            daemon._fresh_moment_receipts = FreshMomentReceipts(
                Path(td) / "fresh_moment_receipts.db"
            )
            daemon._salience_broker_baseline = None
            daemon._lean_idle_self_card_text = lambda: "SELF CARD"
            daemon._lean_idle_private_signal_summary = lambda: {}
            daemon._lean_idle_time_facts = lambda: {}
            daemon._lean_idle_body_state = lambda: {}
            daemon._lean_idle_open_loops = lambda: {}
            daemon._lean_idle_recent_private_thoughts = lambda: ()
            fake_result = SimpleNamespace(
                intercepted=True,
                return_text=_HEARTBEAT_OK,
                stored=True,
                thought_id=thought_id,
                skip_reason="none",
                receipt={"stored": True, "note_chars": 39, "output_sha256": "0123456789abcdef"},
            )

            with mock.patch.dict(
                "os.environ",
                {
                    "MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1",
                    "MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW": "1",
                },
                clear=True,
            ):
                with mock.patch(
                    "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat",
                    return_value=fake_result,
                ):
                    daemon._maybe_run_lean_idle_heartbeat({}, _gate())

            after = private_store.get_thought(thought_id)

        self.assertEqual(before, after)
```

- [ ] **Step 2: Add downstream-no-call test**

Append to `tests/test_lean_idle_daemon.py`:

```python
    def test_fresh_moment_receipt_does_not_call_downstream_organs(self) -> None:
        from daemon.maez_daemon import MaezDaemon, _HEARTBEAT_OK
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        with tempfile.TemporaryDirectory() as td:
            daemon = object.__new__(MaezDaemon)
            daemon.cycle_count = 25
            daemon.private_thoughts = object()
            daemon._fresh_moment_receipts = FreshMomentReceipts(
                Path(td) / "fresh_moment_receipts.db"
            )
            daemon._salience_broker_baseline = None
            daemon._lean_idle_self_card_text = lambda: "SELF CARD"
            daemon._lean_idle_private_signal_summary = lambda: {}
            daemon._lean_idle_time_facts = lambda: {}
            daemon._lean_idle_body_state = lambda: {}
            daemon._lean_idle_open_loops = lambda: {}
            daemon._lean_idle_recent_private_thoughts = lambda: ()
            fake_result = SimpleNamespace(
                intercepted=True,
                return_text=_HEARTBEAT_OK,
                stored=True,
                thought_id=81,
                skip_reason="none",
                receipt={"stored": True, "note_chars": 8, "output_sha256": "0123456789abcdef"},
            )

            with mock.patch.dict(
                "os.environ",
                {
                    "MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1",
                    "MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW": "1",
                    "MAEZ_SALIENCE_BROKER_SHADOW": "",
                },
                clear=True,
            ):
                with mock.patch(
                    "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat",
                    return_value=fake_result,
                ), mock.patch(
                    "core.evolution.wonderings.Wonderings.add",
                    side_effect=AssertionError("wonderings must not be written"),
                ), mock.patch(
                    "core.evolution.wants.Wants.record_event",
                    side_effect=AssertionError("wants must not be written"),
                ), mock.patch(
                    "core.cognition.salience_ledger.SalienceLedger.record",
                    side_effect=AssertionError("salience must not be written"),
                ), mock.patch(
                    "core.actions.action_engine.ActionEngine.write_soul_note",
                    side_effect=AssertionError("soul must not be written"),
                ):
                    result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

            rows = daemon._fresh_moment_receipts.recent(limit=5)

        self.assertEqual(result, _HEARTBEAT_OK)
        self.assertEqual(len(rows), 1)
```

- [ ] **Step 3: Run tests and verify they pass**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_fresh_moment_receipts tests.test_lean_idle_daemon tests.test_lean_idle_heartbeat -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_lean_idle_daemon.py
git commit -m "test(cognition): prove fresh moment receipts stay leaf-only"
```

## Task 4: Add Backup Coverage

**Files:**
- Modify: `scripts/backup/backup_state_manifest.json`
- Modify: `tests/test_backup_manifest_coverage.py`

- [ ] **Step 1: Write failing backup-manifest test**

Modify `tests/test_backup_manifest_coverage.py`:

```python
    def test_fresh_moment_receipts_are_required_welfare(self):
        manifest = self._manifest()
        by_path = {entry["path"]: entry for entry in manifest["entries"]}
        path = "memory/fresh_moment_receipts.db"
        self.assertIn(path, by_path, f"{path} not in manifest")
        self.assertEqual(by_path[path].get("class"), "required_welfare")
        self.assertTrue(by_path[path].get("required"))
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_backup_manifest_coverage.ManifestCoverageTest.test_fresh_moment_receipts_are_required_welfare -v
```

Expected: FAIL with `memory/fresh_moment_receipts.db not in manifest`.

- [ ] **Step 3: Add manifest entry**

Add this entry in `scripts/backup/backup_state_manifest.json` near `memory/private_thoughts.db`:

```json
    {
      "type": "sqlite_db",
      "path": "memory/fresh_moment_receipts.db",
      "required": true,
      "class": "required_welfare",
      "comment": "Content-light sidecar receipts for Maez-internal fresh moments; no raw private thought text."
    },
```

- [ ] **Step 4: Run backup tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_backup_manifest_coverage -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/backup_state_manifest.json tests/test_backup_manifest_coverage.py
git commit -m "fix(backup): protect fresh moment receipts"
```

## Task 5: Final Verification and Handoff

**Files:**
- Create: `docs/handoffs/2026-06-28-fresh-moment-receipts-v0-handoff.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_fresh_moment_receipts \
  tests.test_lean_idle_daemon \
  tests.test_lean_idle_heartbeat \
  tests.test_backup_manifest_coverage \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run lint on touched Python files**

Run:

```bash
cd /home/rohit/maez
.venv/bin/ruff check \
  core/cognition/fresh_moment_receipts.py \
  daemon/maez_daemon.py \
  tests/test_fresh_moment_receipts.py \
  tests/test_lean_idle_daemon.py \
  tests/test_lean_idle_heartbeat.py \
  tests/test_backup_manifest_coverage.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Write handoff**

Create `docs/handoffs/2026-06-28-fresh-moment-receipts-v0-handoff.md`:

```markdown
# Fresh-Moment Receipts v0 Handoff

## Summary

Adds a flag-gated, content-light sidecar receipt for `private_thought_landed`.
The receipt points at a private-thought row by `thought_id` and digest only; it
does not mutate `private_thoughts`, score importance, write downstream, or expose
raw thought text.

## Flags

- `MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW=1` enables the sidecar writer.
- Default off: no sidecar store is created and no behavior changes.

## Verification

- Focused tests:
  - `tests.test_fresh_moment_receipts`
  - `tests.test_lean_idle_daemon`
  - `tests.test_lean_idle_heartbeat`
  - `tests.test_backup_manifest_coverage`
- Ruff on touched files.

## Witness Plan

After merge and restart:

1. Leave `MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW` off and confirm no
   `memory/fresh_moment_receipts.db` is created by default.
2. Enable `MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW=1`.
3. Let the enabled heartbeat run naturally.
4. When a private thought lands, verify exactly one sidecar row appears with:
   `moment_kind=private_thought_landed`, source `lean_idle_heartbeat.v0`,
   bond `private_owner`, content hash/length, and no raw text.

## Predicted effect

With the shadow flag on, each stored lean-idle private thought creates one
content-light sidecar receipt. Maez behavior does not change; the diary is
untouched; no downstream organ is reached.
```

- [ ] **Step 4: Commit handoff**

```bash
git add docs/handoffs/2026-06-28-fresh-moment-receipts-v0-handoff.md
git commit -m "docs(cognition): hand off fresh moment receipts v0"
```

## Self-Review Checklist

- [ ] Sidecar only; no `private_thoughts` schema or row mutation.
- [ ] Receipt writer receives no raw thought text.
- [ ] Schema has no salience/value columns.
- [ ] Schema has no raw text columns.
- [ ] Writer imports no downstream organs.
- [ ] Default off creates no sidecar store.
- [ ] Backup manifest includes `memory/fresh_moment_receipts.db` as `required_welfare`.
- [ ] No S7, authority, web, routing, clinical, search, or soul files touched.
