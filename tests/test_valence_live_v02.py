import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution import valence_live
from core.evolution.valence.reading import Sign


class ValenceLiveV02(unittest.TestCase):
    def test_last_pulse_epoch_converts_iso_timestamp_to_epoch(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"
            log.write_text(
                json.dumps({"ts": "2026-06-10T00:00:00+00:00"}) + "\n",
                encoding="utf-8",
            )

            epoch = valence_live.last_pulse_epoch(log)

            expected = datetime(2026, 6, 10, tzinfo=timezone.utc).timestamp()
            self.assertAlmostEqual(epoch, expected)

    def test_last_pulse_epoch_returns_none_when_timestamp_is_naive(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"
            log.write_text(
                json.dumps({"ts": "2026-06-10T00:00:00"}) + "\n",
                encoding="utf-8",
            )

            self.assertIsNone(valence_live.last_pulse_epoch(log))

    def test_last_pulse_epoch_returns_none_when_no_log(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "missing.jsonl"

            self.assertIsNone(valence_live.last_pulse_epoch(log))

    def test_last_pulse_epoch_returns_none_when_ts_is_unparseable(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"
            log.write_text(json.dumps({"ts": "not-a-time"}) + "\n", encoding="utf-8")

            self.assertIsNone(valence_live.last_pulse_epoch(log))

    def test_last_pulse_epoch_returns_none_when_record_is_corrupt_json(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"
            log.write_text("{not-json\n", encoding="utf-8")

            self.assertIsNone(valence_live.last_pulse_epoch(log))

    def test_resolved_delta_yields_positive_and_records_coverage(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"

            reading = valence_live.read_and_log_valence(
                audit_flags=[],
                open_want_count=0,
                continuity_state={},
                now="2026-06-10T00:00:00+00:00",
                resolved=2,
                log_path=log,
            )

            self.assertEqual(reading.sign, Sign.POSITIVE)
            record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(record["want_snapshot"]["resolved"], 2)
            self.assertEqual(
                record["want_coverage"],
                {
                    "resolved": "satisfied_events_delta",
                    "blocked": "not_live_derived",
                    "stale": "not_live_derived",
                },
            )

    def test_zero_resolved_is_preserved_in_snapshot(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"

            valence_live.read_and_log_valence(
                audit_flags=[],
                open_want_count=0,
                continuity_state={},
                now="2026-06-10T00:00:00+00:00",
                resolved=0,
                log_path=log,
            )

            record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(record["want_snapshot"]["resolved"], 0)


if __name__ == "__main__":
    unittest.main()
