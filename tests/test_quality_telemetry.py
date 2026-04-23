# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.quality_telemetry — log tail parser + DB readers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import quality_telemetry as qt
from core.quality_telemetry import (
    _parse_audit_lines, _parse_error_lines, _parse_consolidation_lines,
    build_rollup,
)


_FIXTURE_LOG = """
2026-04-21 11:51:15 [INFO] self_claim_audit | surface=daemon_cycle flagged=4 mode=shortcircuit kinds=judge
2026-04-21 11:51:48 [INFO] self_claim_audit | surface=daemon_cycle flagged=2 mode=shortcircuit kinds=judge
2026-04-21 11:52:24 [INFO] self_claim_audit | surface=daemon_cycle flagged=1 mode=sentence kinds=judge
2026-04-21 11:52:58 [INFO] self_claim_audit | surface=daemon_cycle flagged=0 mode=noop kinds=-
2026-04-21 11:53:30 [INFO] self_claim_audit | surface=telegram flagged=0 mode=prefilter_clean kinds=-
2026-04-21 11:55:01 [INFO] error_classifier | surface=daemon_cycle class=gpu_oom retryable=0 transient=0 structural=1 compress=0 msg='cudaMalloc failed'
2026-04-21 11:55:45 [INFO] error_classifier | surface=daemon_cycle class=backend_timeout retryable=1 transient=1 structural=0 compress=0 msg='Read timed out'
2026-04-21 11:56:12 [INFO] error_classifier | surface=daemon_cycle class=backend_timeout retryable=1 transient=1 structural=0 compress=0 msg='Read timed out'
2026-04-21 12:00:00 [INFO] consolidation_scores | n=47 min=0.042 median=0.118 max=0.431
2026-04-21 14:00:00 [INFO] consolidation_scores | n=53 min=0.055 median=0.142 max=0.480
""".strip()


# ── parsers ───────────────────────────────────────────────────────────

class ParseAuditLines(unittest.TestCase):

    def test_counts_total_and_by_mode(self):
        r = _parse_audit_lines(_FIXTURE_LOG, limit=100)
        self.assertEqual(r.total, 5)
        self.assertEqual(r.by_mode["shortcircuit"], 2)
        self.assertEqual(r.by_mode["sentence"], 1)
        self.assertEqual(r.by_mode["noop"], 1)
        self.assertEqual(r.by_mode["prefilter_clean"], 1)

    def test_by_surface_split(self):
        r = _parse_audit_lines(_FIXTURE_LOG, limit=100)
        self.assertEqual(r.by_surface["daemon_cycle"], 4)
        self.assertEqual(r.by_surface["telegram"], 1)

    def test_total_flags_and_flag_rate(self):
        r = _parse_audit_lines(_FIXTURE_LOG, limit=100)
        # 4 + 2 + 1 + 0 + 0 = 7 flags across 5 events
        self.assertEqual(r.total_flags, 7)
        # 3 of 5 events had flags > 0
        self.assertAlmostEqual(r.flag_rate, 0.6, places=2)

    def test_respects_limit(self):
        r = _parse_audit_lines(_FIXTURE_LOG, limit=2)
        self.assertEqual(r.total, 2)

    def test_empty_blob(self):
        r = _parse_audit_lines("", limit=10)
        self.assertEqual(r.total, 0)
        self.assertEqual(r.by_mode, {})
        self.assertEqual(r.flag_rate, 0.0)


class ParseErrorLines(unittest.TestCase):

    def test_counts_class_distribution(self):
        r = _parse_error_lines(_FIXTURE_LOG, limit=100)
        self.assertEqual(r.total, 3)
        self.assertEqual(r.by_class["backend_timeout"], 2)
        self.assertEqual(r.by_class["gpu_oom"], 1)

    def test_transient_vs_structural_counts(self):
        r = _parse_error_lines(_FIXTURE_LOG, limit=100)
        self.assertEqual(r.transient_count, 2)   # 2x backend_timeout
        self.assertEqual(r.structural_count, 1)  # 1x gpu_oom

    def test_empty_blob(self):
        r = _parse_error_lines("", limit=10)
        self.assertEqual(r.total, 0)


class ParseConsolidationLines(unittest.TestCase):

    def test_captures_latest_distribution(self):
        # Walking newest-first, the 14:00 entry should be "last_*"
        r = _parse_consolidation_lines(_FIXTURE_LOG, limit=10)
        self.assertEqual(r.last_n, 53)
        self.assertAlmostEqual(r.last_min, 0.055, places=3)
        self.assertAlmostEqual(r.last_median, 0.142, places=3)
        self.assertAlmostEqual(r.last_max, 0.480, places=3)
        self.assertEqual(r.observations, 2)

    def test_empty_blob(self):
        r = _parse_consolidation_lines("", limit=10)
        self.assertEqual(r.observations, 0)


# ── end-to-end rollup ────────────────────────────────────────────────

class BuildRollupContract(unittest.TestCase):

    def test_rollup_empty_when_no_log_exists(self):
        """If cognition.log is missing, every parser returns empty but
        build_rollup still returns a valid structure."""
        with tempfile.TemporaryDirectory() as td:
            fake_log = Path(td) / "cognition.log"  # doesn't exist
            with patch.object(qt, "_COG_LOG", fake_log):
                r = build_rollup()
        self.assertEqual(r.audit.total, 0)
        self.assertEqual(r.errors.total, 0)
        self.assertEqual(r.consolidation.observations, 0)

    def test_rollup_parses_real_fixture_log(self):
        with tempfile.TemporaryDirectory() as td:
            fake_log = Path(td) / "cognition.log"
            fake_log.write_text(_FIXTURE_LOG)
            with patch.object(qt, "_COG_LOG", fake_log):
                r = build_rollup()
        self.assertEqual(r.audit.total, 5)
        self.assertEqual(r.errors.total, 3)
        self.assertEqual(r.consolidation.observations, 2)

    def test_to_json_shape(self):
        r = build_rollup()
        data = r.to_json()
        # Top-level keys must all be present for the cockpit contract.
        for k in ("generated_at", "source_log_path", "audit", "errors",
                  "consolidation", "fabrication", "recall"):
            self.assertIn(k, data)
        self.assertIsInstance(data["audit"], dict)
        self.assertIsInstance(data["audit"]["by_mode"], dict)


# ── sidecar DBs ──────────────────────────────────────────────────────

class SidecarDBsFailSafe(unittest.TestCase):
    """Both sidecar DBs must return empty snapshots when files are missing
    or malformed, not raise."""

    def test_missing_fab_db(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(qt, "_FAB_DB", Path(td) / "nope.db"):
                snap = qt._fabrication_snapshot()
        self.assertEqual(snap.total_events, 0)
        self.assertEqual(snap.recent, [])

    def test_missing_recall_db(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(qt, "_RECALL_DB", Path(td) / "nope.db"):
                snap = qt._recall_snapshot()
        self.assertEqual(snap.total_memories_tracked, 0)
        self.assertEqual(snap.total_recalls, 0)


if __name__ == "__main__":
    unittest.main()
