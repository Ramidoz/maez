import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


def _snapshot(**overrides):
    base = {
        "base_model": "qwen36-27b-mtp",
        "soul_base_hash": "a" * 64,
        "soul_local_hash": "b" * 64,
        "frame_text_hash": "c" * 64,
        "policy_hash": "d" * 64,
        "self_card_applied": True,
    }
    base.update(overrides)
    return base


class ContinuityStoreTests(unittest.TestCase):
    def test_round_trips_runs_and_answers_ordered(self):
        from core.continuity_fingerprint.store import ContinuityStore

        with tempfile.TemporaryDirectory() as td:
            store = ContinuityStore(Path(td) / "continuity_fingerprint.db")
            store.record_run(
                run_id="r2",
                ts="2026-07-03T10:02:00Z",
                snapshot=_snapshot(base_model="model-b"),
                embedder_id="all-MiniLM-L6-v2:384",
                battery_version="v0",
                answers=[
                    {
                        "question_id": "attention",
                        "answer_text": "A later answer.",
                        "dist_short": 0.2,
                        "dist_mid": 0.3,
                        "dist_long": 0.4,
                    }
                ],
            )
            store.record_run(
                run_id="r1",
                ts="2026-07-03T10:01:00Z",
                snapshot=_snapshot(base_model="model-a"),
                embedder_id="all-MiniLM-L6-v2:384",
                battery_version="v0",
                answers=[
                    {
                        "question_id": "attention",
                        "answer_text": "An earlier answer.",
                        "dist_short": 0.1,
                        "dist_mid": 0.2,
                        "dist_long": 0.3,
                    }
                ],
            )

            runs = store.list_runs()
            answers = store.answers_for("r1")

        self.assertEqual([run["run_id"] for run in runs], ["r1", "r2"])
        self.assertEqual(runs[0]["base_model"], "model-a")
        self.assertEqual(answers[0]["question_id"], "attention")
        self.assertEqual(answers[0]["answer_text"], "An earlier answer.")
        self.assertEqual(answers[0]["dist_short"], 0.1)

    def test_first_run_distances_are_null_never_fake_zero(self):
        from core.continuity_fingerprint.store import ContinuityStore

        with tempfile.TemporaryDirectory() as td:
            store = ContinuityStore(Path(td) / "continuity_fingerprint.db")
            store.record_run(
                run_id="first",
                ts="2026-07-03T10:00:00Z",
                snapshot=_snapshot(),
                embedder_id="all-MiniLM-L6-v2:384",
                battery_version="v0",
                answers=[
                    {
                        "question_id": "attention",
                        "answer_text": "No anchor exists yet.",
                        "dist_short": None,
                        "dist_mid": None,
                        "dist_long": None,
                    }
                ],
            )
            answer = store.answers_for("first")[0]

        self.assertIsNone(answer["dist_short"])
        self.assertIsNone(answer["dist_mid"])
        self.assertIsNone(answer["dist_long"])
        self.assertNotEqual(answer["dist_short"], 0.0)

    def test_schema_has_no_vector_or_blob_columns(self):
        from core.continuity_fingerprint.store import ContinuityStore

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "continuity_fingerprint.db"
            ContinuityStore(path)
            with closing(sqlite3.connect(path)) as con:
                columns = []
                for table in ("probe_runs", "probe_answers"):
                    columns.extend(con.execute(f"PRAGMA table_info({table})").fetchall())

        names = [str(col[1]).lower() for col in columns]
        types = [str(col[2]).lower() for col in columns]
        self.assertFalse(any("vector" in name or "embedding" in name for name in names))
        self.assertNotIn("blob", types)


if __name__ == "__main__":
    unittest.main()
