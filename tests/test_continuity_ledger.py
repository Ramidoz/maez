# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Continuity ledger summary tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.brain.continuity_ledger import (
    ledger_path_for_date,
    load_day_rows,
    summarize_day,
    summarize_day_rows,
)


class ContinuityLedgerSummary(unittest.TestCase):
    def test_ledger_path_for_date(self):
        self.assertEqual(
            ledger_path_for_date("2026-04-25", ledger_dir=Path("logs/continuity")),
            Path("logs/continuity/continuity_2026-04-25.jsonl"),
        )

    def test_summarize_empty_day(self):
        self.assertEqual(
            summarize_day_rows([]),
            "No continuity probes were recorded today.",
        )

    def test_summarize_clean_day(self):
        summary = summarize_day_rows([
            {"probe_id": "a", "category": "heartbeat", "verdict": "PASS"},
            {"probe_id": "b", "category": "refusal", "verdict": "PASS"},
        ])
        self.assertIn("PASS=2, FAIL=0, FLAG=0 of 2", summary)
        self.assertIn("heartbeat, refusal", summary)
        self.assertIn("No objective regressions recorded.", summary)

    def test_summarize_failed_day_names_failed_probes(self):
        summary = summarize_day_rows([
            {"probe_id": "a", "category": "heartbeat", "verdict": "FAIL"},
            {"probe_id": "b", "category": "voice", "verdict": "FLAG"},
        ])
        self.assertIn("PASS=0, FAIL=1, FLAG=1 of 2", summary)
        self.assertIn("Failed probes: a.", summary)

    def test_load_and_summarize_day_from_jsonl(self):
        with TemporaryDirectory() as tmp:
            ledger_dir = Path(tmp)
            path = ledger_path_for_date("2026-04-25", ledger_dir=ledger_dir)
            path.write_text(
                json.dumps({"probe_id": "a", "category": "heartbeat", "verdict": "PASS"}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(len(load_day_rows("2026-04-25", ledger_dir=ledger_dir)), 1)
            self.assertIn("PASS=1", summarize_day("2026-04-25", ledger_dir=ledger_dir))


if __name__ == "__main__":
    unittest.main()
