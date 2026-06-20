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


class StampWiring(unittest.TestCase):
    def _store(self, reader):
        return EpisodeStore(os.path.join(tempfile.mkdtemp(), "ep.db"), felt_time_reader=reader)

    def _add(self, store, source_kind="pursuit_surface"):
        return store.add(title="t", summary="s", participants=["Maez"],
                         source_memory_ids=["m1"], source_kind=source_kind)

    def _row(self, store, ep_id):
        return store.get(ep_id)

    def test_stamps_from_context_when_reader_returns_context(self):
        ctx = {"felt_value": 7.65, "felt_elapsed_s": 11520.0,
               "felt_phrase": "a long quiet stretch", "felt_compute_version": 1}
        store = self._store(lambda: ctx)
        row = self._row(store, self._add(store))
        self.assertAlmostEqual(row["felt_value"], 7.65)
        self.assertAlmostEqual(row["felt_elapsed_s"], 11520.0)
        self.assertEqual(row["felt_phrase"], "a long quiet stretch")
        self.assertEqual(row["felt_compute_version"], 1)

    def test_null_when_reader_returns_none(self):
        store = self._store(lambda: None)
        row = self._row(store, self._add(store))
        self.assertIsNone(row["felt_value"])
        self.assertIsNone(row["felt_elapsed_s"])
        self.assertIsNone(row["felt_phrase"])

    def test_null_when_no_reader_injected(self):
        store = EpisodeStore(os.path.join(tempfile.mkdtemp(), "ep.db"))   # reader defaults None
        row = self._row(store, self._add(store))
        self.assertIsNone(row["felt_value"])

    def test_value_comes_from_reader_not_args(self):
        # The stamp must come from the injected substrate reader, never from add() arguments.
        ctx = {"felt_value": 3.0, "felt_elapsed_s": 60.0, "felt_phrase": "p", "felt_compute_version": 1}
        store = self._store(lambda: ctx)
        row = self._row(store, self._add(store))
        self.assertAlmostEqual(row["felt_value"], 3.0)   # from the reader

    def test_stamps_across_source_kinds(self):
        ctx = {"felt_value": 1.0, "felt_elapsed_s": 1.0, "felt_phrase": "p", "felt_compute_version": 1}
        store = self._store(lambda: ctx)
        for kind in ("pursuit_surface", "owner_contact", "reflection", "followup_doc"):
            row = self._row(store, self._add(store, source_kind=kind))
            self.assertAlmostEqual(row["felt_value"], 1.0)   # EVERY EpisodeStore episode

    def test_reader_exception_does_not_break_the_write(self):
        def _boom():
            raise RuntimeError("substrate hiccup")
        store = self._store(_boom)
        ep_id = self._add(store)                 # a memory write must NEVER fail due to the stamp
        self.assertIsNotNone(self._row(store, ep_id))
        self.assertIsNone(self._row(store, ep_id)["felt_value"])
