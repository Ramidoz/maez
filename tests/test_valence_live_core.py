import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution.valence.reading import Sign
from core.evolution.valence_live import read_and_log_valence


class ValenceLiveCore(unittest.TestCase):
    def test_happy_path_appends_record_matching_pure_reading(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "valence_telemetry.jsonl"
            reading = read_and_log_valence(
                audit_flags=["completion_rail"],
                open_want_count=2,
                continuity_state={"capsule_expected": False, "capsule_present": False},
                now="2026-06-10T00:00:00Z",
                log_path=log,
            )
            self.assertEqual(reading.sign, Sign.NEGATIVE)
            rec = json.loads(log.read_text().splitlines()[-1])
            self.assertEqual(rec["sign"], "negative")
            self.assertEqual(rec["want_snapshot"]["open"], 2)
            self.assertEqual(rec["want_snapshot"]["resolved"], 0)
            self.assertEqual(rec["provenance"], "computed_valence")
            self.assertNotIn("feel", rec["telemetry"].lower())

    def test_backlog_grew_uses_prior_open(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"
            read_and_log_valence(
                audit_flags=[],
                open_want_count=1,
                continuity_state={},
                now="t1",
                log_path=log,
            )
            r2 = read_and_log_valence(
                audit_flags=[],
                open_want_count=3,
                continuity_state={},
                now="t2",
                log_path=log,
            )
            self.assertEqual(r2.sign, Sign.NEGATIVE)
