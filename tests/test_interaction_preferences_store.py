from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from core.interaction_preferences.store import InteractionPreferencesStore


class InteractionPreferencesStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "interaction_preferences.db"
        self.store = InteractionPreferencesStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _columns(self) -> set[str]:
        with closing(sqlite3.connect(self.db_path)) as con:
            return {
                row[1]
                for row in con.execute(
                    "PRAGMA table_info(interaction_preferences)"
                ).fetchall()
            }

    def test_capture_row_is_testimony_not_config(self):
        pref = self.store.record_capture(
            preference_id="pref-1",
            preference_class="question_cadence",
            owner_statement="stop asking me so many questions",
            source_ref="owner_turn:telegram:abc123:1000",
            surface="telegram",
            statement_sha256="a" * 64,
            created_at="2026-07-03T12:00:00Z",
        )

        self.assertEqual(pref.owner_statement, "stop asking me so many questions")
        self.assertEqual(pref.status, "active")

        columns = self._columns()
        self.assertIn("owner_statement", columns)
        for forbidden in {
            "fewer_questions",
            "question_limit",
            "policy_weight",
            "target",
            "modifier",
            "command",
            "normalized_fact",
        }:
            self.assertNotIn(forbidden, columns)

    def test_retraction_supersedes_without_deleting(self):
        original = self.store.record_capture(
            preference_id="pref-1",
            preference_class="question_cadence",
            owner_statement="stop asking me so many questions",
            source_ref="owner_turn:telegram:abc123:1000",
            surface="telegram",
            statement_sha256="a" * 64,
            created_at="2026-07-03T12:00:00Z",
        )

        retraction = self.store.record_retraction(
            preference_id="pref-2",
            preference_class="question_cadence",
            owner_statement="actually, ask away",
            source_ref="owner_turn:telegram:def456:2000",
            surface="telegram",
            statement_sha256="b" * 64,
            supersedes_preference_id=original.preference_id,
            retraction_reason="actually, ask away",
            created_at="2026-07-03T12:01:00Z",
        )

        stored_original = self.store.get("pref-1")
        self.assertIsNotNone(stored_original)
        assert stored_original is not None
        self.assertEqual(stored_original.owner_statement, "stop asking me so many questions")
        self.assertEqual(stored_original.status, "retracted")
        self.assertEqual(stored_original.superseded_by_preference_id, "pref-2")
        self.assertEqual(retraction.supersedes_preference_id, "pref-1")
        self.assertEqual(self.store.active_preferences("question_cadence"), [])

    def test_no_normalized_fact_field_in_v0(self):
        self.store.record_capture(
            preference_id="pref-1",
            preference_class="question_cadence",
            owner_statement="stop asking me so many questions",
            source_ref="owner_turn:telegram:abc123:1000",
            surface="telegram",
            statement_sha256="a" * 64,
            created_at="2026-07-03T12:00:00Z",
        )

        self.assertNotIn("normalized_fact", self._columns())
        active = self.store.active_preferences("question_cadence")
        self.assertEqual([p.owner_statement for p in active], ["stop asking me so many questions"])

    def test_paths_helper_points_to_runtime_memory_db(self):
        from core.infra import paths

        self.assertEqual(
            paths.interaction_preferences_db(),
            paths.memory_dir() / "interaction_preferences.db",
        )


if __name__ == "__main__":
    unittest.main()
