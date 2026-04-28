# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.

import json
import tempfile
import unittest
from unittest import mock
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

    def test_split_csv_trims_empty_parts(self):
        self.assertEqual(
            harness._split_csv(" maez.service, ,llama-server.service "),
            ["maez.service", "llama-server.service"],
        )

    def test_git_clean_warns_on_dirty_tree(self):
        with mock.patch.object(
            harness,
            "_run_command",
            return_value=(0, " M core/foo.py\n?? scratch.txt\n", "", 0.01),
        ):
            result = harness.check_git_clean()

        self.assertEqual(result.status, "WARN")
        self.assertFalse(result.required)
        self.assertIn("2 changed", result.detail)

    def test_required_service_failure_is_hard_gate(self):
        def fake_run(cmd, *, timeout=None):
            service = cmd[-1]
            if service == "maez.service":
                return 0, "active\n", "", 0.01
            return 3, "inactive\n", "", 0.01

        with mock.patch.object(harness, "_run_command", side_effect=fake_run):
            result = harness.check_services(
                services=["maez.service", "llama-server.service"],
                required=True,
            )

        self.assertEqual(result.status, "FAIL")
        self.assertTrue(result.required)
        self.assertIn("llama-server.service:inactive", result.detail)

    def test_advisory_service_failure_warns(self):
        with mock.patch.object(
            harness,
            "_run_command",
            return_value=(3, "inactive\n", "", 0.01),
        ):
            result = harness.check_services(
                services=["maez-web.service"],
                required=False,
            )

        self.assertEqual(result.status, "WARN")
        self.assertFalse(result.required)


if __name__ == "__main__":
    unittest.main()
