import os, sqlite3, tempfile, unittest
from contextlib import closing
from core.memory.episodes import EpisodeStore


def _cols(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        return {r[1] for r in conn.execute("PRAGMA table_info(episodes)")}


class StampSchema(unittest.TestCase):
    def test_new_store_has_felt_columns(self):
        path = os.path.join(tempfile.mkdtemp(), "ep.db")
        EpisodeStore(path)
        cols = _cols(path)
        for c in ("felt_value", "felt_elapsed_s", "felt_phrase", "felt_compute_version"):
            self.assertIn(c, cols)
        self.assertNotIn("felt_band", cols)        # NO durable band/bucket column

    def test_old_db_migrates_additively_and_reads_back(self):
        # Simulate a pre-Slice-2 episodes DB (no felt columns), then open with the new store.
        path = os.path.join(tempfile.mkdtemp(), "ep.db")
        with closing(sqlite3.connect(path)) as conn:
            conn.execute(
                "CREATE TABLE episodes (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, occurred_at TEXT,"
                " title TEXT NOT NULL, summary TEXT NOT NULL, participants_json TEXT NOT NULL,"
                " emotional_tone TEXT, importance INTEGER NOT NULL DEFAULT 3, open_loop TEXT,"
                " source_memory_ids_json TEXT NOT NULL, source_kind TEXT NOT NULL,"
                " status TEXT NOT NULL DEFAULT 'active')")
            conn.execute(
                "INSERT INTO episodes (id, created_at, title, summary, participants_json,"
                " source_memory_ids_json, source_kind) VALUES "
                "('ep-old','2026-01-01T00:00:00+00:00','t','s','[\"Maez\"]','[\"m1\"]','seed')")
            conn.commit()
        EpisodeStore(path)                          # __init__ migrates additively
        self.assertIn("felt_value", _cols(path))
        with closing(sqlite3.connect(path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM episodes WHERE id='ep-old'").fetchone()
        self.assertIsNone(row["felt_value"])        # old row keeps felt-* NULL (historical meaning preserved)
