import os, sqlite3, tempfile, unittest
from contextlib import closing
from core.memory.episodes import EpisodeStore

RHYTHM_COLS = ("rhythm_current_gap_s", "rhythm_recent_gap_median_s", "rhythm_all_time_gap_median_s",
               "rhythm_recent_sample_count", "rhythm_all_time_sample_count",
               "rhythm_current_gap_percentile_all_time", "rhythm_recent_gap_iqr_s", "rhythm_all_time_gap_iqr_s")


def _cols(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        return {r[1] for r in conn.execute("PRAGMA table_info(episodes)")}


class RhythmSchema(unittest.TestCase):
    def test_new_store_has_rhythm_columns(self):
        path = os.path.join(tempfile.mkdtemp(), "ep.db")
        EpisodeStore(path)
        cols = _cols(path)
        for c in RHYTHM_COLS:
            self.assertIn(c, cols)


class RhythmStampWiring(unittest.TestCase):
    def _store(self, *, felt=None, rhythm=None):
        return EpisodeStore(os.path.join(tempfile.mkdtemp(), "ep.db"),
                            felt_time_reader=felt, rhythm_reader=rhythm)

    def _add(self, store, source_kind="pursuit_surface"):
        return store.get(store.add(title="t", summary="s", participants=["Maez"],
                                   source_memory_ids=["m1"], source_kind=source_kind))

    def test_felt_null_is_not_read_as_missing_time(self):
        store = self._store(rhythm=lambda: {"rhythm_current_gap_s": 3600.0, "rhythm_all_time_sample_count": 5})
        row = self._add(store)
        self.assertIsNone(row["felt_value"])
        self.assertAlmostEqual(row["rhythm_current_gap_s"], 3600.0)

    def test_rhythm_on_writes_rhythm_only_felt_null(self):
        # rhythm reader returns facts, felt reader returns None (daemon self-gates) -> rhythm_* set, felt_* NULL
        rctx = {"rhythm_current_gap_s": 3600.0, "rhythm_recent_gap_median_s": 1800.0,
                "rhythm_all_time_gap_median_s": 3000.0, "rhythm_recent_sample_count": 4,
                "rhythm_all_time_sample_count": 9, "rhythm_current_gap_percentile_all_time": 85.0,
                "rhythm_recent_gap_iqr_s": 600.0, "rhythm_all_time_gap_iqr_s": 900.0}
        store = self._store(felt=lambda: None, rhythm=lambda: rctx)
        row = self._add(store)
        self.assertAlmostEqual(row["rhythm_current_gap_s"], 3600.0)
        self.assertAlmostEqual(row["rhythm_current_gap_percentile_all_time"], 85.0)
        self.assertEqual(row["rhythm_all_time_sample_count"], 9)
        self.assertIsNone(row["felt_value"])             # felt box left NULL when rhythm on

    def test_rhythm_off_writes_felt_only_rhythm_null(self):
        fctx = {"felt_value": 7.0, "seconds_since_last_owner_contact": 60.0,
                "felt_phrase": "p", "felt_compute_version": 1}
        store = self._store(felt=lambda: fctx, rhythm=lambda: None)
        row = self._add(store)
        self.assertAlmostEqual(row["felt_value"], 7.0)
        self.assertIsNone(row["rhythm_current_gap_s"])   # rhythm box NULL when rhythm off

    def test_rhythm_value_from_reader_not_args(self):
        store = self._store(rhythm=lambda: {"rhythm_current_gap_s": 42.0, "rhythm_all_time_sample_count": 3})
        self.assertAlmostEqual(self._add(store)["rhythm_current_gap_s"], 42.0)

    def test_rhythm_stamps_across_source_kinds(self):
        store = self._store(rhythm=lambda: {"rhythm_current_gap_s": 1.0, "rhythm_all_time_sample_count": 3})
        for k in ("pursuit_surface", "owner_contact", "reflection", "followup_doc"):
            self.assertAlmostEqual(self._add(store, source_kind=k)["rhythm_current_gap_s"], 1.0)

    def test_rhythm_reader_exception_does_not_break_write(self):
        def _boom():
            raise RuntimeError("hiccup")
        store = self._store(rhythm=_boom)
        row = self._add(store)
        self.assertIsNotNone(row)
        self.assertIsNone(row["rhythm_current_gap_s"])
