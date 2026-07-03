# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Receipt-id plumbing for A1 Scar Tissue.

Scar episodes cite durable receipts. Judge-rewrite fabrications already
write durable rows, but before A1 the write path discarded their ids.
These tests lock the full chain: fabrication_memory row id -> audit _emit
collection -> AuditResult field. Action-claim mismatches remain outside the
fabrication class and carry no fabrication ids.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

os.environ["MAEZ_TEST_MODE"] = "1"


@dataclass
class _FakeFlag:
    kind: str
    text: str
    reason: str = "not grounded"


class FabricationReceiptIdTests(unittest.TestCase):
    def setUp(self):
        from core import fabrication_memory as fm

        self.fm = fm
        self.tmp = tempfile.TemporaryDirectory(prefix="scar_receipts_fab_")
        self.old_db_path = fm._DB_PATH
        self.old_initialized = fm._initialized
        fm._DB_PATH = Path(self.tmp.name) / "fabrication_log.db"
        fm._initialized = False
        fm._diag_clear_for_test()
        fm._diag_clear_events_for_test()

    def tearDown(self):
        self.fm._diag_clear_for_test()
        self.fm._diag_clear_events_for_test()
        self.fm._DB_PATH = self.old_db_path
        self.fm._initialized = self.old_initialized
        self.tmp.cleanup()

    def test_record_event_returns_row_id(self):
        first = self.fm.record_event(
            surface="test",
            text="The disk has been climbing for weeks.",
            signals_absent=["disk trend"],
            reason="no trend signal",
            mode="judge",
        )
        second = self.fm.record_event(
            surface="test",
            text="A different unsupported sentence.",
            signals_absent=["screen"],
            reason="no screen signal",
            mode="judge",
        )

        self.assertIsInstance(first, int)
        self.assertGreater(first, 0)
        self.assertIsInstance(second, int)
        self.assertGreater(second, 0)
        self.assertNotEqual(first, second)

    def test_record_event_empty_text_returns_none(self):
        self.assertIsNone(
            self.fm.record_event(
                surface="test",
                text="",
                signals_absent=[],
                reason="empty",
                mode="judge",
            )
        )


class AuditResultReceiptPlumbingTests(unittest.TestCase):
    def test_audit_result_default_has_no_fabrication_ids(self):
        from core.safety.self_claim_audit import AuditResult

        result = AuditResult(text="x", rewritten=False, mode="noop")

        self.assertIsNone(result.fabrication_receipt_ids)

    def test_emit_returns_collected_ids(self):
        from core.safety import self_claim_audit as audit_mod

        flags = [
            _FakeFlag(kind="judge", text="claim one", reason="r1"),
            _FakeFlag(kind="judge", text="claim two", reason="r2"),
        ]
        with (
            mock.patch("core.fabrication_memory.record_event", side_effect=[7, 8]),
            mock.patch("core.inner_residue.record"),
        ):
            ids = audit_mod._emit(
                surface="test",
                flags=flags,
                mode="judge",
                signals_absent=["screen"],
                signals_present=["memory"],
            )

        self.assertEqual(ids, [7, 8])

    def test_emit_without_flags_returns_empty_ids(self):
        from core.safety import self_claim_audit as audit_mod

        with mock.patch("core.fabrication_memory.record_event") as record_event:
            ids = audit_mod._emit(surface="test", flags=[], mode="noop")

        self.assertEqual(ids, [])
        record_event.assert_not_called()

    def test_action_claim_mismatch_result_has_no_fabrication_ids(self):
        from core.safety.self_claim_audit import audit

        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
                "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
            },
            clear=False,
        ):
            result = audit(
                "Initiating live search now.",
                surface="telegram",
                evidence_envelope={"tool_results": []},
            )

        self.assertIsNotNone(result.action_mismatch)
        self.assertIsNone(result.fabrication_receipt_ids)


if __name__ == "__main__":
    unittest.main()
