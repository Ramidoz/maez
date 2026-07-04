import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from tests.test_narrative_detectors import RAW_ID


def _link_rows(path: Path) -> list[tuple]:
    with closing(sqlite3.connect(path)) as con:
        rows = con.execute(
            "SELECT link_key, link_type, trust, evidence_json FROM narrative_links "
            "ORDER BY link_key"
        ).fetchall()
    return [tuple(row) for row in rows]


class NarrativeBackfillTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db = Path(self._td.name) / "lived_episodes.db"
        from core.memory.episodes import EpisodeStore

        store = EpisodeStore(str(self.db))
        self.old_id = store.add(
            title="old",
            summary="old",
            participants=["Maez"],
            source_memory_ids=[RAW_ID],
            source_kind="telegram_exchange",
        )
        self.new_id = store.add(
            title="new",
            summary="new",
            participants=["Maez"],
            source_memory_ids=[RAW_ID, self.old_id],
            source_kind="reflection",
        )

    def tearDown(self):
        self._td.cleanup()

    def test_list_backfill_reports_counts_without_mutation(self):
        from scripts.narrative_backfill import list_backfill

        report = list_backfill(self.db)

        self.assertEqual(report["counts"], {"same_thread": 1, "strings": 1, "because_of": 0})
        with closing(sqlite3.connect(self.db)) as con:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE name = 'narrative_links'"
            ).fetchone()
        self.assertIsNone(row)

    def test_apply_backfill_is_owner_gated_and_idempotent(self):
        from scripts.narrative_backfill import apply_backfill

        with self.assertRaises(PermissionError):
            apply_backfill(self.db, owner_approved=False)

        first = apply_backfill(self.db, owner_approved=True)
        rows_after_first = _link_rows(self.db)
        second = apply_backfill(self.db, owner_approved=True)
        rows_after_second = _link_rows(self.db)

        self.assertEqual(first["written"], 2)
        self.assertEqual(second["written"], 2)
        self.assertEqual(rows_after_first, rows_after_second)


if __name__ == "__main__":
    unittest.main()
