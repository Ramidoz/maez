import unittest
import daemon.maez_daemon as d

_VERDICT_WORDS = ("long quiet", "stretch", "a while", "unusual", "lonely", "feels", "felt like")


class RhythmLineFormat(unittest.TestCase):
    def test_full_facts_line_has_no_verdict_words(self):
        ctx = {"rhythm_current_gap_s": 3 * 3600, "rhythm_recent_gap_median_s": 30 * 60,
               "rhythm_all_time_gap_median_s": 50 * 60, "rhythm_recent_sample_count": 20,
               "rhythm_all_time_sample_count": 227, "rhythm_current_gap_percentile_all_time": 85.0,
               "rhythm_recent_gap_iqr_s": 600.0, "rhythm_all_time_gap_iqr_s": 900.0}
        line = d._format_rhythm_line(ctx)
        self.assertIn("3h", line)
        self.assertIn("85", line)           # the raw percentile fact
        low = line.lower()
        for w in _VERDICT_WORDS:
            self.assertNotIn(w, low)        # facts, never a feeling-verdict
        self.assertTrue(line.startswith("Time:"))

    def test_short_gap_still_produces_a_line_no_expression_gate(self):
        # A SHORT gap (low percentile) must STILL produce a facts line — no threshold gating of expression.
        ctx = {"rhythm_current_gap_s": 60, "rhythm_recent_gap_median_s": 30 * 60,
               "rhythm_all_time_gap_median_s": 50 * 60, "rhythm_recent_sample_count": 20,
               "rhythm_all_time_sample_count": 227, "rhythm_current_gap_percentile_all_time": 3.0,
               "rhythm_recent_gap_iqr_s": 600.0, "rhythm_all_time_gap_iqr_s": 900.0}
        line = d._format_rhythm_line(ctx)
        self.assertTrue(line.startswith("Time:"))
        self.assertIn("3", line)            # the percentile fact is still stated, not withheld

    def test_cold_start_line_states_still_learning(self):
        ctx = {"rhythm_current_gap_s": 900, "rhythm_recent_gap_median_s": None,
               "rhythm_all_time_gap_median_s": None, "rhythm_recent_sample_count": 1,
               "rhythm_all_time_sample_count": 1, "rhythm_current_gap_percentile_all_time": None,
               "rhythm_recent_gap_iqr_s": None, "rhythm_all_time_gap_iqr_s": None}
        line = d._format_rhythm_line(ctx).lower()
        self.assertIn("still learning", line)
        self.assertNotIn("%", line)         # no fabricated percentile in cold-start


class CycleFeedSource(unittest.TestCase):
    def test_cycle_packet_module_has_no_rhythm_or_felt(self):
        import inspect, core.cognition.cycle_packet as cp
        src = inspect.getsource(cp).lower()
        for token in ("rhythm", "felt_time", "time_sense", "subjective_duration"):
            self.assertNotIn(token, src)    # still pure
