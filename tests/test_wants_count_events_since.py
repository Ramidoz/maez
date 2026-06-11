# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Valence v0.2 read-only wants event count helper tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.evolution.wants import Wants


def _satisfied_evidence() -> dict[str, str]:
    return {
        "basis": "owner_confirmed",
        "source": "owner",
        "summary": "The external object was met.",
        "external_object_ref": "object:blanket",
    }


class WantsCountEventsSinceTest(unittest.TestCase):
    def _store(self, temp_dir: str) -> Wants:
        return Wants(Path(temp_dir) / "wants.db")

    def _satisfy(self, store: Wants, statement: str = "I want a quiet corner.") -> str:
        want_id = store.record_event(statement=statement, evidence={"seed": True})
        store.record_event(
            want_id=want_id,
            event_type="satisfied",
            statement=statement,
            evidence=_satisfied_evidence(),
        )
        return want_id

    def test_counts_satisfied_event_after_cursor(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)
            want_id = self._satisfy(store)
            satisfied_event = store.history(want_id)[0]

            count = store.count_events_since(
                float(satisfied_event["ts"]) - 0.001,
                "satisfied",
            )

            self.assertEqual(count, 1)

    def test_does_not_count_event_at_or_before_cursor(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)
            want_id = self._satisfy(store)
            satisfied_event = store.history(want_id)[0]

            count_at_cursor = store.count_events_since(
                float(satisfied_event["ts"]),
                "satisfied",
            )
            count_after_cursor = store.count_events_since(
                float(satisfied_event["ts"]) + 0.001,
                "satisfied",
            )

            self.assertEqual(count_at_cursor, 0)
            self.assertEqual(count_after_cursor, 0)

    def test_does_not_count_created_event_when_asking_satisfied(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)
            want_id = store.record_event(
                statement="I want a quiet corner.",
                evidence={"seed": True},
            )
            created_event = store.history(want_id)[0]

            count = store.count_events_since(
                float(created_event["ts"]) - 0.001,
                "satisfied",
            )

            self.assertEqual(count, 0)

    def test_counts_known_non_satisfied_type_created(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)
            want_id = store.record_event(
                statement="I want a quiet corner.",
                evidence={"seed": True},
            )
            created_event = store.history(want_id)[0]

            count = store.count_events_since(
                float(created_event["ts"]) - 0.001,
                "created",
            )

            self.assertEqual(count, 1)

    def test_unknown_event_type_blocked_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)

            with self.assertRaises(ValueError):
                store.count_events_since(0.0, "blocked")


if __name__ == "__main__":
    unittest.main()
