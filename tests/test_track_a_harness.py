# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate import track_a_harness as harness


class TrackAHarnessTests(unittest.TestCase):
    def test_status_from_score_uses_threshold(self):
        self.assertEqual(harness._status_from_score(0.86, 0.85), "PASS")
        self.assertEqual(harness._status_from_score(0.84, 0.85), "FAIL")

    def test_count_jsonl_ignores_blank_lines(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "data.jsonl"
            path.write_text('{"a":1}\n\n{"b":2}\n')
            self.assertEqual(harness._count_jsonl(path), 2)

    def test_write_report_marks_required_and_advisory(self):
        results = [
            harness.CheckResult("unit_tests", "PASS", "ok", 1.0),
            harness.CheckResult("voice_dataset", "WARN", "not enough", 1.0, required=False),
        ]
        with tempfile.TemporaryDirectory() as td:
            report = harness.write_report(results, report_dir=Path(td))
            payload = json.loads(report.read_text())
            latest = Path(td) / "track_a_harness_latest.json"
            latest_exists = latest.exists()

        self.assertTrue(payload["required_pass"])
        self.assertEqual(payload["advisory_warn"], ["voice_dataset"])
        self.assertTrue(latest_exists)


if __name__ == "__main__":
    unittest.main()
