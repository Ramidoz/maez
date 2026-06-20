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
