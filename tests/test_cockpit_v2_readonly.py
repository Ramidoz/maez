import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class CockpitV2ReadOnlyTests(unittest.TestCase):
    def test_a7_interiority_reports_counts_only_never_private_text(self):
        from core.cockpit.readers import CockpitSourcePaths, a7_interiority_health

        secret = "PRIVATE THOUGHT BODY MUST NOT LEAK"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private_db = root / "memory" / "private_thoughts.db"
            private_db.parent.mkdir(parents=True)
            con = sqlite3.connect(private_db)
            con.execute(
                "CREATE TABLE private_thoughts "
                "(thought_id INTEGER PRIMARY KEY, content TEXT NOT NULL)"
            )
            con.execute("INSERT INTO private_thoughts (content) VALUES (?)", (secret,))
            con.commit()
            con.close()

            health = a7_interiority_health(
                CockpitSourcePaths(memory_dir=root / "memory", logs_dir=root / "logs")
            )

            rendered = json.dumps(health, sort_keys=True)
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["private_thought_count"], 1)
            self.assertFalse(health["raw_text_included"])
            self.assertNotIn(secret, rendered)
            for forbidden in (
                "thought_id",
                "receipt_id",
                "content_sha256",
                "content_len",
                "context",
                "source",
                "provenance",
                "signal_kind",
                "signal_class",
                "recent",
            ):
                self.assertNotIn(forbidden, rendered)
            self.assertEqual(health["content_policy"], "sealed")
            self.assertEqual(
                health["stores"]["private_thoughts"]["read_mode"],
                "sqlite_ro_query_only",
            )

    def test_source_health_uses_public_readonly_helpers(self):
        from core.cockpit import readers

        calls = []

        def fake_self_evidence_digest(*, _sources=None, window=None):
            calls.append(("self_evidence", _sources, window))
            return {
                "kind": "self_evidence_integrity_ledger",
                "sources": {},
                "merged_events": {"status": "ok"},
            }

        def fake_list_all_readonly(path):
            calls.append(("interaction_preferences", Path(path).name))
            return []

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = readers.CockpitSourcePaths(
                memory_dir=root / "memory",
                logs_dir=root / "logs",
            )
            with mock.patch.object(
                readers, "self_evidence_digest", fake_self_evidence_digest
            ), mock.patch.object(
                readers, "list_all_readonly", fake_list_all_readonly
            ):
                health = readers.source_health(paths)

        self.assertIn(("interaction_preferences", "interaction_preferences.db"), calls)
        self.assertTrue(any(call[0] == "self_evidence" for call in calls))
        self.assertIn("a6_self_evidence", health)

    def test_interaction_preferences_existing_db_without_table_is_no_data(self):
        from core.cockpit.readers import (
            CockpitSourcePaths,
            interaction_preferences_health,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "memory" / "interaction_preferences.db"
            db.parent.mkdir(parents=True)
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE unrelated (id INTEGER)")
            con.commit()
            con.close()

            health = interaction_preferences_health(
                CockpitSourcePaths(memory_dir=root / "memory", logs_dir=root / "logs")
            )

        self.assertEqual(health["status"], "no_data")
        self.assertEqual(health["active"], 0)
        self.assertEqual(health["total"], 0)

    def test_interaction_preferences_corrupt_db_is_unavailable(self):
        from core.cockpit.readers import (
            CockpitSourcePaths,
            interaction_preferences_health,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "memory" / "interaction_preferences.db"
            db.parent.mkdir(parents=True)
            db.write_text("not sqlite", encoding="utf-8")

            health = interaction_preferences_health(
                CockpitSourcePaths(memory_dir=root / "memory", logs_dir=root / "logs")
            )

        self.assertEqual(health["status"], "unavailable")
        self.assertEqual(health["active"], 0)
        self.assertEqual(health["total"], 0)

    def test_interaction_preferences_wrong_schema_is_unavailable(self):
        from core.cockpit.readers import (
            CockpitSourcePaths,
            interaction_preferences_health,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "memory" / "interaction_preferences.db"
            db.parent.mkdir(parents=True)
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE interaction_preferences (id INTEGER)")
            con.commit()
            con.close()

            health = interaction_preferences_health(
                CockpitSourcePaths(memory_dir=root / "memory", logs_dir=root / "logs")
            )

        self.assertEqual(health["status"], "unavailable")
        self.assertEqual(health["active"], 0)
        self.assertEqual(health["total"], 0)

    def test_readers_do_not_construct_writer_stores_or_schema_helpers(self):
        src = (
            Path(__file__).resolve().parents[1] / "core" / "cockpit" / "readers.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "ScarSidecar(",
            "ContinuityStore(",
            "EpisodeStore(",
            "NarrativeStore(",
            "InteractionPreferencesStore(",
            "FreshMomentReceipts(",
            "VetoLedger(",
            "_ensure_db(",
            "stats(",
            "record_event(",
        ):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
