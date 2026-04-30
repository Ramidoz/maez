# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Wondering-pursuit history tests (Slice 2 Session 3 — observability).

Session-2 wiring landed pursuit decisions in the Trace JSONL. This
session adds **per-wondering** observability: a new
``wondering_pursuits`` table records each successful surface event
(decision="surface") against the specific wondering, with score +
per-axis components.

Per the 2026-04-29 audit (B1): only ``"surface"`` decisions are
recorded per-wondering. ``"hold"`` and ``"errored"`` are
*per-evaluation* events (no specific wondering target —
``decide_pursuit`` returns None for both), and stay in the
Trace JSONL where they already live. The store API still accepts
all three decision strings for completeness (so callers building
wondering-targeted traces can record holds against a known
candidate id), but the daemon's normal flow only records
``"surface"``.

This gives:

- Per-wondering surface history (cockpit + CLI display)
- Probe-loop awareness — ``pick_next`` deprioritises recently
  surfaced wonderings to avoid double-touching
- Salience tracking — the Session-1 audit's "salience axis" now
  has a data foundation
- Schema migration that's idempotent + cross-process race-safe
  (existing wonderings DBs in the wild get the new columns + table
  on first daemon restart, even when CLI is concurrently reading)

Tests cover:

- New columns ``last_pursuit_at`` + ``pursuit_count`` on
  ``wonderings`` table (idempotent ALTER)
- New ``wondering_pursuits`` table with per-decision history
- ``record_pursuit(wid, decision, ...)`` method writes both the
  history row AND updates the parent wondering's counter columns
- ``recent_pursuits(wondering_id)`` returns history rows
- ``pick_next`` deprioritises recently-surfaced wonderings
- Migration on a pre-existing schema (no new columns) succeeds
  without data loss
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
    """Fresh Wonderings store on a tempfile DB."""
    from core.evolution.wonderings import Wonderings

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    path = Path(f.name)

    def cleanup():
        path.unlink(missing_ok=True)

    return Wonderings(db_path=path), cleanup


# ── schema migration ─────────────────────────────────────────────────


class TestSchemaMigration(unittest.TestCase):
    def test_wonderings_table_has_pursuit_columns(self):
        store, cleanup = _store()
        try:
            with sqlite3.connect(str(store.db_path)) as c:
                cols = [
                    row[1]
                    for row in c.execute(
                        "PRAGMA table_info(wonderings)"
                    ).fetchall()
                ]
            self.assertIn("last_pursuit_at", cols)
            self.assertIn("pursuit_count", cols)
        finally:
            cleanup()

    def test_wondering_pursuits_table_exists(self):
        store, cleanup = _store()
        try:
            with sqlite3.connect(str(store.db_path)) as c:
                rows = c.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='wondering_pursuits'"
                ).fetchall()
            self.assertEqual(len(rows), 1,
                             "wondering_pursuits table must exist")
        finally:
            cleanup()

    def test_migration_idempotent_on_old_schema(self):
        """A wonderings DB created before Session 3 must migrate
        cleanly on first read — no exceptions, existing data
        preserved, new columns / table added."""
        from core.evolution.wonderings import Wonderings

        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        path = Path(f.name)
        try:
            # Simulate a pre-Session-3 DB: only the original two
            # tables, none of the new pursuit columns.
            with sqlite3.connect(str(path)) as c:
                c.execute(
                    """
                    CREATE TABLE wonderings (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at          REAL NOT NULL,
                        question            TEXT NOT NULL,
                        status              TEXT NOT NULL DEFAULT 'open',
                        advance_count       INTEGER NOT NULL DEFAULT 0,
                        deferral_count      INTEGER NOT NULL DEFAULT 0,
                        pending_card_id     INTEGER,
                        last_advanced       REAL,
                        source              TEXT,
                        conclusion          TEXT
                    )
                    """
                )
                c.execute(
                    "INSERT INTO wonderings (created_at, question, source) "
                    "VALUES (?, ?, ?)",
                    (time.time(), "pre-existing data", "test"),
                )
                c.commit()

            # Now construct the new-shape store on top of the old
            # DB. Migration should add the missing columns + table
            # idempotently and preserve the existing row.
            store = Wonderings(db_path=path)
            self.assertEqual(len(store.list_all()), 1)
            existing = store.list_all()[0]
            self.assertEqual(existing["question"], "pre-existing data")
            # New columns exist + default to 0/None.
            self.assertEqual(existing.get("pursuit_count", 0), 0)
            self.assertIsNone(existing.get("last_pursuit_at"))
        finally:
            path.unlink(missing_ok=True)


# ── record_pursuit ───────────────────────────────────────────────────


class TestRecordPursuit(unittest.TestCase):
    def test_record_pursuit_writes_history_row(self):
        store, cleanup = _store()
        try:
            wid = store.add("test wondering", source="test")
            store.record_pursuit(
                wid,
                decision="surface",
                score=0.72,
                components={
                    "goal": 0.8, "recency": 1.0,
                    "register": 0.9, "quality": 0.5,
                },
            )
            history = store.recent_pursuits(wid)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["decision"], "surface")
            self.assertAlmostEqual(history[0]["score"], 0.72, places=2)
        finally:
            cleanup()

    def test_record_pursuit_updates_parent_counters_on_surface(self):
        store, cleanup = _store()
        try:
            wid = store.add("counter test", source="test")
            store.record_pursuit(wid, decision="surface", score=0.7)
            w = store.get(wid)
            self.assertEqual(w["pursuit_count"], 1)
            self.assertIsNotNone(w["last_pursuit_at"])
        finally:
            cleanup()

    def test_record_pursuit_hold_does_not_advance_counter(self):
        """Only ``surface`` decisions tick the counter — holds and
        errors are observability artefacts, not surface events."""
        store, cleanup = _store()
        try:
            wid = store.add("hold test", source="test")
            store.record_pursuit(wid, decision="hold", score=0.4)
            store.record_pursuit(wid, decision="errored", score=0.0)
            w = store.get(wid)
            self.assertEqual(w["pursuit_count"], 0)
            self.assertIsNone(w["last_pursuit_at"])
        finally:
            cleanup()

    def test_record_pursuit_history_rows_for_all_decisions(self):
        """All three outcomes (surface / hold / errored) write a
        history row — only the counter-update branch is gated."""
        store, cleanup = _store()
        try:
            wid = store.add("audit trail test", source="test")
            for decision in ("surface", "hold", "errored"):
                store.record_pursuit(wid, decision=decision, score=0.5)
            history = store.recent_pursuits(wid)
            self.assertEqual(len(history), 3)
            self.assertEqual(
                {row["decision"] for row in history},
                {"surface", "hold", "errored"},
            )
        finally:
            cleanup()

    def test_record_pursuit_components_serialised_as_json(self):
        store, cleanup = _store()
        try:
            wid = store.add("json test", source="test")
            store.record_pursuit(
                wid,
                decision="surface",
                score=0.7,
                components={"goal": 0.8, "recency": 0.9, "register": 0.7, "quality": 0.6},
            )
            history = store.recent_pursuits(wid)
            self.assertEqual(len(history), 1)
            comps = history[0].get("components") or {}
            self.assertAlmostEqual(comps["goal"], 0.8, places=2)
            self.assertAlmostEqual(comps["register"], 0.7, places=2)
        finally:
            cleanup()

    def test_record_pursuit_skip_unknown_wondering(self):
        """Recording against a wondering id that doesn't exist must
        not raise (defensive — daemon may have stale ids)."""
        store, cleanup = _store()
        try:
            # No exception expected.
            store.record_pursuit(99999, decision="surface", score=0.5)
        finally:
            cleanup()


# ── pick_next awareness ──────────────────────────────────────────────


class TestProbeLoopAwareness(unittest.TestCase):
    """The probe loop's ``pick_next`` should deprioritise wonderings
    surfaced via pursuit recently — surfacing AND probing the same
    wondering in adjacent cycles produces double-touching the owner
    on a topic that should be paced."""

    def test_recently_surfaced_wondering_deprioritised(self):
        store, cleanup = _store()
        try:
            old = store.add("old surfaced one", source="test")
            recent = store.add("recently surfaced one", source="test")

            # Both have last_advanced = None (never probed) so
            # without the pursuit-aware fix they'd be picked in
            # creation order. Surface ``recent`` just now to push
            # it down the pick order.
            store.record_pursuit(recent, decision="surface", score=0.7)

            picked = store.pick_next()
            self.assertIsNotNone(picked)
            self.assertEqual(
                picked["id"], old,
                "pick_next must deprioritise the recently-surfaced "
                "wondering to avoid double-touching the owner",
            )
        finally:
            cleanup()

    def test_old_pursuit_does_not_deprioritise(self):
        store, cleanup = _store()
        try:
            never_pursued = store.add("never pursued", source="test")
            old_pursued = store.add("old pursued", source="test")

            # Simulate a pursuit from way back in time.
            store.record_pursuit(old_pursued, decision="surface", score=0.7)
            with sqlite3.connect(str(store.db_path)) as c:
                # Backdate the surface to 24h ago.
                c.execute(
                    "UPDATE wonderings SET last_pursuit_at = ? WHERE id = ?",
                    (time.time() - 86400, old_pursued),
                )
                c.commit()

            picked = store.pick_next()
            self.assertIsNotNone(picked)
            # Both are eligible (old pursuit doesn't penalise);
            # creation order should hold — old_pursued was second
            # but ``never_pursued`` came first.
            self.assertEqual(picked["id"], never_pursued)
        finally:
            cleanup()


class TestDaemonRecordsPursuitOnSurface(unittest.TestCase):
    """Audit-driven (Session 3 review): the test suite should assert
    that the daemon actually CALLS ``record_pursuit`` after a surface
    decision, not just that the store-side method works in isolation.

    Source-level structural test — locks the contract that the daemon
    invokes the per-wondering history capture for surface events."""

    def test_daemon_calls_record_pursuit(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parent.parent
            / "daemon" / "maez_daemon.py"
        ).read_text()
        # The daemon must call record_pursuit somewhere inside
        # handle_message after a surface decision. Locate the call
        # and verify it's near the pursuit decision wiring.
        idx = src.find("record_pursuit(")
        self.assertGreater(
            idx, 0,
            "daemon must call record_pursuit() after surface decision "
            "(audit Session 3 — the central observability deliverable)",
        )
        # The call should be inside the same try/except block as the
        # pursuit evaluation, anchored by the surrounding context.
        before = src[max(0, idx - 800):idx]
        self.assertIn(
            "_pursuit_decision", before,
            "record_pursuit must be wired to the pursuit decision flow",
        )

    def test_daemon_record_pursuit_failure_silent(self):
        """``record_pursuit`` failure must not break the reply
        path. Wrapped in try/except like the rest of the pursuit
        block."""
        from pathlib import Path

        src = (
            Path(__file__).resolve().parent.parent
            / "daemon" / "maez_daemon.py"
        ).read_text()
        idx = src.find("record_pursuit(")
        self.assertGreater(idx, 0)
        # The call window. Find the immediately surrounding
        # try/except.
        before = src[max(0, idx - 200):idx]
        after = src[idx:idx + 400]
        self.assertIn("try:", before,
                      "record_pursuit must be inside a try block")
        self.assertRegex(after, r"except\s+Exception",
                         "record_pursuit must catch Exception "
                         "(silent fail-open)")


class TestEpisodeOnPursuitSurface(unittest.TestCase):
    """ADR 0019 lived-memory integrity: a successful pursuit surface
    is a high-signal moment that should land in the episode store
    as ``source_kind="pursuit_surface"`` so future reflection can
    later cite "Maez surfaced wondering X to owner at time T".

    The daemon-source-level check confirms the integration is
    wired; behavioural verification of episode contents is at a
    higher level than this test layer."""

    def test_daemon_emits_pursuit_surface_episode(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parent.parent
            / "daemon" / "maez_daemon.py"
        ).read_text()
        # Look for the source_kind tag near the pursuit block.
        self.assertIn(
            'source_kind="pursuit_surface"', src,
            "daemon must emit a 'pursuit_surface' episode after a "
            "successful surface — ADR 0019 lived-memory integrity",
        )


if __name__ == "__main__":
    unittest.main()
