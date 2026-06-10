import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core.evolution.valence_live import read_and_log_valence


def _run(log, **kw):
    base = {
        "audit_flags": [],
        "open_want_count": 0,
        "continuity_state": {},
        "now": "t",
        "log_path": log,
    }
    base.update(kw)
    return read_and_log_valence(**base)


class ValenceLiveGuardrails(unittest.TestCase):
    def test_first_run_no_fake_backlog_grew(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"

            reading = _run(log, open_want_count=5)

            self.assertEqual(reading.sign.value, "neutral")
            record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
            self.assertFalse(record["want_snapshot"]["backlog_grew"])

    def test_corrupt_log_neutral_no_crash(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"
            log.write_text("{ not json\n", encoding="utf-8")

            reading = _run(log, open_want_count=9)

            self.assertIsNotNone(reading)
            self.assertEqual(reading.sign.value, "neutral")

    def test_retention_keeps_last_n_never_zero(self):
        with TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"VALENCE_LOG_RETENTION": "2"}):
                log = Path(d) / "v.jsonl"

                for i in range(5):
                    _run(log, now=f"t{i}", open_want_count=i)

            lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 2)
            self.assertGreaterEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["ts"], "t3")
            self.assertEqual(json.loads(lines[1])["ts"], "t4")

    def test_no_owner_text_in_record(self):
        owner_texts = ("secret diary", "my password is", "rohit said")
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"

            _run(log, audit_flags=list(owner_texts), open_want_count=1)

            blob = log.read_text(encoding="utf-8").lower()
            for owner_text in owner_texts:
                self.assertNotIn(owner_text, blob)

    def test_append_failure_returns_none_and_logs_warning(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"

            with self.assertLogs("core.evolution.valence_live", level="WARNING") as logs:
                with mock.patch(
                    "core.evolution.valence_live._append_and_prune",
                    side_effect=OSError("disk full"),
                ):
                    reading = _run(log, audit_flags=["completion_rail"])

            self.assertIsNone(reading)
            self.assertIn("failed to read and log valence", "\n".join(logs.output))

    def test_any_internal_failure_never_raises_and_logs_warning(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"

            with self.assertLogs("core.evolution.valence_live", level="WARNING") as logs:
                with mock.patch(
                    "core.evolution.valence_live.read_valence",
                    side_effect=RuntimeError("boom"),
                ):
                    reading = _run(log)

            self.assertIsNone(reading)
            self.assertIn("failed to read and log valence", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
