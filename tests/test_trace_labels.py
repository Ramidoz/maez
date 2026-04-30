# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Trace-label store tests (Slice 5 — annotation CLI / labeled corpus).

Adapted from KTO (Kahneman-Tversky Optimization) preference-learning
shape: binary thumbs-up / thumbs-down pinned to a specific
conversational turn (``trace_id``) is the foundation the audit
identified for owner-feedback training.

What this slice ships:

- ``TraceLabel`` row shape with id / trace_id / label / kind / note /
  labeler / created_at
- ``LabelStore`` class with ``add_label``, ``recent``,
  ``labels_for_trace``, ``stats`` methods
- Idempotent upsert semantics on ``(trace_id, kind, labeler)`` so
  re-labelling the same turn updates rather than duplicates
- Label kinds keep the binary KTO shape (``"good"`` / ``"bad"``)
  with optional ``kind`` qualifier (e.g., ``"voice"``,
  ``"initiative"``, ``"fabrication"``) for future per-axis
  training data shaping. Default kind is ``"overall"``.

The CLI integration ships in a sibling slice file; this module is
the storage foundation tested in isolation.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _store():
    from core.feedback.labels import LabelStore

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    p = Path(f.name)

    def cleanup():
        p.unlink(missing_ok=True)

    return LabelStore(db_path=p), cleanup


# ── schema ──────────────────────────────────────────────────────────


class TestSchema(unittest.TestCase):
    def test_trace_labels_table_exists(self):
        store, cleanup = _store()
        try:
            with sqlite3.connect(str(store.db_path)) as c:
                rows = c.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='trace_labels'"
                ).fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            cleanup()

    def test_required_columns_present(self):
        store, cleanup = _store()
        try:
            with sqlite3.connect(str(store.db_path)) as c:
                cols = [
                    row[1]
                    for row in c.execute(
                        "PRAGMA table_info(trace_labels)"
                    ).fetchall()
                ]
            for required in (
                "id", "trace_id", "label", "kind",
                "note", "labeler", "created_at",
            ):
                self.assertIn(required, cols, f"missing column: {required}")
        finally:
            cleanup()


# ── add_label ───────────────────────────────────────────────────────


class TestAddLabel(unittest.TestCase):
    def test_basic_label_persists(self):
        store, cleanup = _store()
        try:
            store.add_label(
                trace_id="abc123",
                label="good",
                note="this reply landed perfectly",
            )
            rows = store.labels_for_trace("abc123")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["label"], "good")
            self.assertEqual(rows[0]["kind"], "overall")
            self.assertEqual(rows[0]["note"], "this reply landed perfectly")
            self.assertEqual(rows[0]["labeler"], "owner")
        finally:
            cleanup()

    def test_label_value_must_be_good_or_bad(self):
        store, cleanup = _store()
        try:
            with self.assertRaises(ValueError):
                store.add_label(
                    trace_id="abc123",
                    label="meh",  # not in {good, bad}
                )
        finally:
            cleanup()

    def test_empty_trace_id_rejected(self):
        store, cleanup = _store()
        try:
            with self.assertRaises(ValueError):
                store.add_label(trace_id="", label="good")
            with self.assertRaises(ValueError):
                store.add_label(trace_id="   ", label="good")
        finally:
            cleanup()

    def test_kind_qualifier_persists(self):
        """Beyond the default ``"overall"`` kind, labels can be
        scoped to a specific axis like ``"voice"`` or ``"initiative"``
        — useful for future per-axis training-data shaping."""
        store, cleanup = _store()
        try:
            store.add_label(
                trace_id="abc123", label="good", kind="voice",
            )
            store.add_label(
                trace_id="abc123", label="bad", kind="initiative",
            )
            rows = store.labels_for_trace("abc123")
            self.assertEqual(len(rows), 2)
            kinds = {(r["kind"], r["label"]) for r in rows}
            self.assertEqual(
                kinds, {("voice", "good"), ("initiative", "bad")},
            )
        finally:
            cleanup()


class TestUpsertSemantics(unittest.TestCase):
    """Re-labelling the same ``(trace_id, kind, labeler)`` triple
    updates the existing row rather than duplicating. Owners change
    their minds; the store tracks the latest verdict."""

    def test_relabel_overwrites(self):
        store, cleanup = _store()
        try:
            store.add_label(trace_id="abc", label="good", note="first take")
            store.add_label(trace_id="abc", label="bad", note="changed mind")
            rows = store.labels_for_trace("abc")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["label"], "bad")
            self.assertEqual(rows[0]["note"], "changed mind")
        finally:
            cleanup()

    def test_different_kinds_dont_collide(self):
        store, cleanup = _store()
        try:
            store.add_label(trace_id="abc", label="good", kind="overall")
            store.add_label(trace_id="abc", label="bad", kind="voice")
            rows = store.labels_for_trace("abc")
            self.assertEqual(len(rows), 2)
        finally:
            cleanup()


# ── recent + stats ──────────────────────────────────────────────────


class TestRecent(unittest.TestCase):
    def test_recent_returns_newest_first(self):
        store, cleanup = _store()
        try:
            store.add_label(trace_id="t1", label="good")
            time.sleep(0.001)
            store.add_label(trace_id="t2", label="bad")
            rows = store.recent(limit=10)
            self.assertEqual(rows[0]["trace_id"], "t2")
            self.assertEqual(rows[1]["trace_id"], "t1")
        finally:
            cleanup()

    def test_recent_respects_limit(self):
        store, cleanup = _store()
        try:
            for i in range(5):
                store.add_label(trace_id=f"t{i}", label="good")
            rows = store.recent(limit=3)
            self.assertEqual(len(rows), 3)
        finally:
            cleanup()


class TestStats(unittest.TestCase):
    """Quick summary for cockpit / CLI display: total per
    label/kind, plus most-recent-label timestamp."""

    def test_stats_returns_counts(self):
        store, cleanup = _store()
        try:
            store.add_label(trace_id="t1", label="good")
            store.add_label(trace_id="t2", label="good")
            store.add_label(trace_id="t3", label="bad")
            stats = store.stats()
            self.assertEqual(stats["good"], 2)
            self.assertEqual(stats["bad"], 1)
            self.assertEqual(stats["total"], 3)
        finally:
            cleanup()

    def test_stats_empty_store(self):
        store, cleanup = _store()
        try:
            stats = store.stats()
            self.assertEqual(stats["total"], 0)
            self.assertEqual(stats.get("good", 0), 0)
            self.assertEqual(stats.get("bad", 0), 0)
        finally:
            cleanup()


# ── KTO export ──────────────────────────────────────────────────────


class TestKtoExport(unittest.TestCase):
    """Foundation for KTO training: emit ``(prompt, completion,
    label_bool)`` triples by joining labels against trace JSONL.
    The label store has the labels; the exporter reads JSONL trace
    files for prompt / completion. This test focuses on the store
    side: a method that lists ``(trace_id, label_bool)`` pairs
    suitable for joining."""

    def test_kto_pairs_emits_binary_pairs(self):
        store, cleanup = _store()
        try:
            store.add_label(trace_id="t1", label="good")
            store.add_label(trace_id="t2", label="bad")
            store.add_label(trace_id="t3", label="good", kind="voice")
            # Default: only overall-kind pairs (most aligned with KTO
            # preference shape).
            pairs = store.kto_pairs()
            ids = {p["trace_id"] for p in pairs}
            self.assertEqual(ids, {"t1", "t2"})
            label_for = {p["trace_id"]: p["label"] for p in pairs}
            self.assertTrue(label_for["t1"])
            self.assertFalse(label_for["t2"])
        finally:
            cleanup()


class TestConcurrentWrites(unittest.TestCase):
    """Audit B1 fix: cross-process upsert race. Two LabelStore
    instances (cross-process; per-process RLock doesn't help) writing
    the same ``(trace_id, kind, labeler)`` triple must not raise
    IntegrityError. Atomic ``INSERT ... ON CONFLICT DO UPDATE``
    handles this without requiring app-side serialisation."""

    def test_concurrent_label_writes_dont_raise(self):
        import threading
        from core.feedback.labels import LabelStore

        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        path = Path(f.name)
        errors: list[BaseException] = []

        def writer(label: str):
            try:
                store = LabelStore(db_path=path)
                for _ in range(20):
                    store.add_label(
                        trace_id="contended",
                        label=label,
                    )
            except BaseException as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=("good" if i % 2 else "bad",))
            for i in range(8)
        ]
        try:
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(
                errors, [],
                f"concurrent writes must not raise; got {errors!r}",
            )
            # File must still be parseable + last-write-wins on the
            # one row.
            store = LabelStore(db_path=path)
            rows = store.labels_for_trace("contended")
            self.assertEqual(
                len(rows), 1,
                "upsert semantics must produce exactly one row "
                "for a contended (trace_id, kind, labeler) triple",
            )
        finally:
            path.unlink(missing_ok=True)


class TestFreshDbAutoMigrates(unittest.TestCase):
    """Audit Explore #10: a non-existent DB path must self-create
    on first ``LabelStore()`` call. Defensive: a future contributor
    deleting ``trace_labels.db`` between deployments must not see
    the next labelling attempt crash."""

    def test_fresh_db_initialises_clean(self):
        from core.feedback.labels import LabelStore

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "subdir" / "fresh.db"
            self.assertFalse(path.exists())
            store = LabelStore(db_path=path)
            self.assertTrue(path.exists())
            store.add_label(trace_id="t1", label="good")
            rows = store.labels_for_trace("t1")
            self.assertEqual(len(rows), 1)


class TestTraceIdSanitisation(unittest.TestCase):
    """Audit L2: control chars / huge inputs sanitised at the
    boundary so cockpit table rendering and JSONL lookups don't
    choke on embedded newlines."""

    def test_trace_id_with_control_chars_rejected(self):
        store, cleanup = _store()
        try:
            with self.assertRaises(ValueError):
                store.add_label(
                    trace_id="abc\n\tdef", label="good",
                )
        finally:
            cleanup()

    def test_oversized_note_truncated(self):
        store, cleanup = _store()
        try:
            store.add_label(
                trace_id="abc", label="good",
                note="x" * 10000,
            )
            rows = store.labels_for_trace("abc")
            # Note must be capped (defensive — cockpit response
            # bounded). Implementation chooses an upper bound; test
            # asserts the bound is enforced.
            self.assertLess(len(rows[0]["note"]), 5000)
        finally:
            cleanup()


if __name__ == "__main__":
    unittest.main()
