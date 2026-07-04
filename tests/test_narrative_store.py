import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


def _rows(path: Path, table: str) -> list[dict]:
    with closing(sqlite3.connect(path)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
    return [dict(row) for row in rows]


class NarrativeLinkKeyTests(unittest.TestCase):
    def test_same_thread_key_sorts_endpoints(self):
        from core.memory.narrative import link_key_for

        self.assertEqual(
            link_key_for("same_thread", "ep-b", "ep-a"),
            link_key_for("same_thread", "ep-a", "ep-b"),
        )
        self.assertEqual(
            link_key_for("same_thread", "ep-b", "ep-a"),
            "same_thread|ep-a|ep-b",
        )

    def test_directed_keys_preserve_order_and_hook_class(self):
        from core.memory.narrative import link_key_for

        self.assertEqual(link_key_for("strings", "ep-a", "ep-b"), "strings|ep-a|ep-b")
        self.assertEqual(
            link_key_for("because_of", "ep-a", "ep-b", hook_class="scar:dream_rejected"),
            "because_of|ep-a|ep-b|scar:dream_rejected",
        )
        self.assertNotEqual(
            link_key_for("because_of", "ep-a", "ep-b", hook_class="scar:dream_rejected"),
            link_key_for("because_of", "ep-a", "ep-b", hook_class="scar:claim_receipt_redo"),
        )
        with self.assertRaisesRegex(ValueError, "hook_class"):
            link_key_for("because_of", "ep-a", "ep-b")

    def test_unknown_link_type_raises_before_storage(self):
        from core.memory.narrative import link_key_for

        with self.assertRaisesRegex(ValueError, "link_type"):
            link_key_for("same_story", "ep-a", "ep-b")


class NarrativeStoreTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db = Path(self._td.name) / "lived_episodes.db"

    def tearDown(self):
        self._td.cleanup()

    def _store(self):
        from core.memory.narrative import NarrativeStore

        return NarrativeStore(self.db)

    def test_schema_rejects_follows_same_story_and_proposed_links(self):
        store = self._store()

        with self.assertRaises((sqlite3.IntegrityError, ValueError)):
            store.upsert_link(
                link_type="follows",
                from_episode_id="ep-a",
                to_episode_id="ep-b",
                trust="derived",
                evidence_ids=["raw-1"],
                detector_version="v0",
            )
        with self.assertRaises((sqlite3.IntegrityError, ValueError)):
            store.upsert_link(
                link_type="same_story",
                from_episode_id="ep-a",
                to_episode_id="ep-b",
                trust="derived",
                evidence_ids=["raw-1"],
                detector_version="v0",
            )
        with self.assertRaises((sqlite3.IntegrityError, ValueError)):
            store.upsert_link(
                link_type="same_thread",
                from_episode_id="ep-a",
                to_episode_id="ep-b",
                trust="proposed",
                evidence_ids=["raw-1"],
                detector_version="v0",
            )

    def test_same_evidence_upsert_is_byte_identical(self):
        store = self._store()
        first = store.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-b",
            to_episode_id="ep-a",
            trust="derived",
            evidence_ids=["raw-1"],
            detector_version="v0",
        )
        before = _rows(self.db, "narrative_links")

        second = store.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-a",
            to_episode_id="ep-b",
            trust="derived",
            evidence_ids=["raw-1"],
            detector_version="v0",
        )
        after = _rows(self.db, "narrative_links")

        self.assertEqual(first, second)
        self.assertEqual(before, after)
        self.assertEqual(len(after), 1)

    def test_new_evidence_appends_without_duplicate_link_row(self):
        store = self._store()
        link_id = store.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-a",
            to_episode_id="ep-b",
            trust="derived",
            evidence_ids=["raw-1"],
            detector_version="v0",
        )
        same_id = store.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-b",
            to_episode_id="ep-a",
            trust="derived",
            evidence_ids=["raw-2"],
            detector_version="v0",
        )

        rows = _rows(self.db, "narrative_links")
        self.assertEqual(link_id, same_id)
        self.assertEqual(len(rows), 1)
        evidence = json.loads(rows[0]["evidence_json"])
        self.assertEqual([entry["ids"] for entry in evidence], [["raw-1"], ["raw-2"]])
        self.assertEqual([entry["detector_version"] for entry in evidence], ["v0", "v0"])

    def test_proposals_round_trip_and_do_not_create_links(self):
        store = self._store()
        proposal_id = store.add_proposal(
            kind="same_story",
            ep_a="ep-a",
            ep_b="ep-b",
            embedder_id="minilm:test",
            distance=0.123,
        )

        pending = store.pending_proposals()
        self.assertEqual([p["proposal_id"] for p in pending], [proposal_id])
        self.assertEqual(pending[0]["kind"], "same_story")
        self.assertEqual(pending[0]["embedder_id"], "minilm:test")
        self.assertAlmostEqual(pending[0]["distance"], 0.123)
        self.assertEqual(_rows(self.db, "narrative_links"), [])


if __name__ == "__main__":
    unittest.main()
