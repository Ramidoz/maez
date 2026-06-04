import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.information_limb.github_store import GithubStore, GithubStoreError


class GithubStoreTests(unittest.TestCase):
    def test_minimized_row_roundtrip_content_free_health(self):
        with tempfile.TemporaryDirectory() as d:
            store = GithubStore(Path(d) / "github_v1.db")
            store.initialize()

            record = store.stage_repo_count(
                ingest_record_id="ir-1",
                fetch_batch_id="fb-1",
                repo_count=7,
                count_field="public_repos",
            )

            self.assertEqual(record["ingest_record_id"], "ir-1")
            self.assertEqual(record["fetch_batch_id"], "fb-1")
            self.assertEqual(record["record_state"], "active")
            health = store.health()
            self.assertEqual(health["staged_records"], 1)
            self.assertEqual(health["source_kind"], "github.repo_count")
            self.assertNotIn("7", repr(health))

    def test_raw_provider_fields_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store = GithubStore(Path(d) / "github_v1.db")
            store.initialize()
            with self.assertRaises(GithubStoreError):
                store.stage_repo_count(
                    ingest_record_id="ir-1",
                    fetch_batch_id="fb-1",
                    repo_count=7,
                    count_field="private_repos",
                )

    def test_schema_mismatch_raises(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "github_v1.db"
            store = GithubStore(db)
            store.initialize()
            with sqlite3.connect(db) as conn:
                conn.execute("ALTER TABLE github_provider_mirror ADD COLUMN raw_response TEXT")
            with self.assertRaises(GithubStoreError):
                store.validate_schema()


if __name__ == "__main__":
    unittest.main()
