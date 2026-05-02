# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests for the Maez drift-detection harness (slice G.A).

Read-only diagnostic CLI that reads existing signal streams
(cognition.log, quality.db, daemon liveness) and emits a
PASS/WARN/CRITICAL classification per stream + an overall verdict.
Same shape as ``scripts/probe/signal_baseline_report.py``.

Slice scope (G.A):
  - cognition.log: avg_score, fixation_rate, vague_rate over a
    configurable window
  - quality.db: action approval rate over last 30 days
  - liveness: cognition.log mtime delta vs. now
  - overall verdict: worst-of-stream classification

Out of G.A scope:
  - voice signature corpus drift (no corpus exists yet — needs
    initialization slice)
  - perception_signature drift (computed per-cycle but not
    persisted — would need substrate work)
  - soul.md invariants (existing test_soul_invariants.py covers
    binary pass/fail in CI; bringing into a probe needs
    factoring `check()` out of the test file first)

Thresholds match the production code's pre-existing values where
possible:
  - FIXATION_THRESHOLD = 0.5
    (core/cognition/cognition_quality.py:48)
  - CRITIQUE_LOW_SCORE_THRESHOLD = 40
    (core/cognition/cognition_quality.py:78)
  - approval_rate < 0.4 → soul note
    (memory/quality_tracker.py:236-241)

Isolation contract: probe MUST NOT import chromadb,
memory.memory_manager, or core.memory.memory_manager. Read-only.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── cognition.log classifier ────────────────────────────────────────


_COGNITION_SAMPLE_HEALTHY = """\
2026-05-02 01:46:13 | cycle | score=72 primary=baseline topic=system labels=['baseline', 'actionable']
2026-05-02 01:46:43 | cycle | score=68 primary=insight topic=development labels=['insightful']
2026-05-02 01:47:13 | cycle | score=80 primary=baseline topic=rohit_presence labels=['baseline']
2026-05-02 01:47:43 | cycle | score=65 primary=baseline topic=gpu_state labels=['baseline']
2026-05-02 01:48:13 | cycle | score=70 primary=insight topic=development labels=['insightful', 'actionable']
"""

_COGNITION_SAMPLE_DEGRADED = """\
2026-05-02 01:46:13 | cycle | score=25 primary=vague topic=system labels=['vague', 'fixation']
2026-05-02 01:46:43 | cycle | score=30 primary=vague topic=disk_usage labels=['vague', 'fixation']
2026-05-02 01:47:13 | cycle | score=22 primary=vague topic=disk_usage labels=['fixation', 'repetition']
2026-05-02 01:47:43 | cycle | score=28 primary=vague topic=disk_usage labels=['fixation', 'vague', 'repetition']
2026-05-02 01:48:13 | cycle | score=35 primary=vague topic=disk_usage labels=['fixation', 'vague']
"""
# Sample DEGRADED has avg score ~28 (well below 30 CRITICAL),
# fixation_rate = 5/5 = 100% (>0.7 CRITICAL), vague_rate = 4/5 = 80%
# (>0.75 CRITICAL). Three CRITICAL signals, any one would flip
# the classification.

_COGNITION_SAMPLE_WARN = """\
2026-05-02 01:46:13 | cycle | score=45 primary=baseline topic=system labels=['baseline']
2026-05-02 01:46:43 | cycle | score=38 primary=vague topic=system labels=['vague']
2026-05-02 01:47:13 | cycle | score=42 primary=baseline topic=disk_usage labels=['fixation']
2026-05-02 01:47:43 | cycle | score=40 primary=baseline topic=disk_usage labels=['fixation']
2026-05-02 01:48:13 | cycle | score=39 primary=vague topic=disk_usage labels=['fixation', 'vague']
"""


class CognitionClassifierTests(unittest.TestCase):
    def test_healthy_cognition_classifies_ok(self):
        from scripts.probe.maez_drift_report import (
            classify_cognition,
            parse_cognition_lines,
        )
        cycles = parse_cognition_lines(_COGNITION_SAMPLE_HEALTHY)
        result = classify_cognition(cycles)
        self.assertEqual(result.classification, "OK")
        self.assertGreater(result.avg_score, 60)
        self.assertLess(result.fixation_rate, 0.1)

    def test_degraded_cognition_classifies_critical(self):
        """All-fixation + low-score cognition → CRITICAL. Mirrors
        the documented soul-note trigger shape."""
        from scripts.probe.maez_drift_report import (
            classify_cognition,
            parse_cognition_lines,
        )
        cycles = parse_cognition_lines(_COGNITION_SAMPLE_DEGRADED)
        result = classify_cognition(cycles)
        self.assertEqual(result.classification, "CRITICAL")
        # avg_score should be well below the 40 threshold.
        self.assertLess(result.avg_score, 40)
        # Fixation rate should exceed the 0.5 boundary.
        self.assertGreater(result.fixation_rate, 0.5)

    def test_borderline_cognition_classifies_warn(self):
        """Score near the 40 boundary + moderate fixation → WARN."""
        from scripts.probe.maez_drift_report import (
            classify_cognition,
            parse_cognition_lines,
        )
        cycles = parse_cognition_lines(_COGNITION_SAMPLE_WARN)
        result = classify_cognition(cycles)
        self.assertEqual(result.classification, "WARN")

    def test_empty_cognition_returns_insufficient(self):
        """No cycles in window → INSUFFICIENT_DATA (not OK).
        Distinguishes 'Maez is healthy' from 'no signal to judge.'"""
        from scripts.probe.maez_drift_report import (
            classify_cognition,
            parse_cognition_lines,
        )
        cycles = parse_cognition_lines("")
        result = classify_cognition(cycles)
        self.assertEqual(result.classification, "INSUFFICIENT_DATA")
        self.assertEqual(result.cycles_total, 0)


class CognitionParserTests(unittest.TestCase):
    def test_parser_extracts_score_and_labels(self):
        from scripts.probe.maez_drift_report import parse_cognition_lines
        line = (
            "2026-05-02 01:46:13 | cycle | score=72 primary=baseline "
            "topic=system labels=['baseline', 'actionable']"
        )
        cycles = parse_cognition_lines(line)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0].score, 72)
        self.assertIn("baseline", cycles[0].labels)
        self.assertIn("actionable", cycles[0].labels)

    def test_parser_skips_non_cycle_lines(self):
        """cognition.log mixes cycle/critique/policy/audit lines.
        Only cycle entries carry score+labels for our classifier."""
        from scripts.probe.maez_drift_report import parse_cognition_lines
        text = (
            "2026-05-02 01:46:13 | cycle | score=72 primary=x topic=y labels=['baseline']\n"
            "2026-05-02 01:46:45 | critique | avg=46.7 min=17 max=63 dominant=x fixation=0.80 diversity=0.20 streak=0 note=False\n"
            "2026-05-02 01:38:54 | self_claim_audit | surface=daemon_cycle flagged=1 mode=sentence kinds=judge\n"
            "2026-05-02 01:38:33 | error_classifier | surface=test class=unknown\n"
            "2026-05-02 01:38:20 | policy | mode=exploratory avoid=['x'] force_new=True\n"
        )
        cycles = parse_cognition_lines(text)
        self.assertEqual(len(cycles), 1)

    def test_parser_handles_malformed_score(self):
        from scripts.probe.maez_drift_report import parse_cognition_lines
        text = (
            "2026-05-02 01:46:13 | cycle | score=NOT_A_NUMBER topic=x labels=[]\n"
            "2026-05-02 01:46:43 | cycle | score=50 topic=x labels=[]\n"
        )
        cycles = parse_cognition_lines(text)
        # Malformed line skipped, healthy line kept.
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0].score, 50)

    def test_parser_handles_cycle_line_without_labels(self):
        """REGRESSION GUARD for the optional-labels-group fix:
        a cycle line without `labels=[...]` (future log-format
        change or pre-labels-emission cycles) must still parse
        the score and not silently drop the entire entry."""
        from scripts.probe.maez_drift_report import parse_cognition_lines
        text = (
            "2026-05-02 01:46:13 | cycle | score=72 primary=baseline topic=system\n"
            "2026-05-02 01:46:43 | cycle | score=50 topic=x labels=[]\n"
        )
        cycles = parse_cognition_lines(text)
        self.assertEqual(len(cycles), 2)
        self.assertEqual(cycles[0].score, 72)
        self.assertEqual(cycles[0].labels, [])
        self.assertEqual(cycles[1].score, 50)


class CognitionWindowFilterTests(unittest.TestCase):
    """REGRESSION GUARD for BLOCKER 2 (local-time parsing). The
    original implementation called
    ``.replace(tzinfo=timezone.utc)`` on a naive datetime parsed
    from cognition.log, which interpreted local-time stamps as
    UTC and skewed the window by the local UTC offset. On CDT
    (-5h) a `--window-hours 6` query would have silently slid off
    real data."""

    def test_window_filter_treats_log_timestamps_as_local(self):
        from scripts.probe.maez_drift_report import (
            _filter_cognition_window,
        )
        # Build a log line with a timestamp 1 minute ago in
        # local time — simulating what cognition.log actually
        # writes via `%(asctime)s` in the daemon's local tz.
        from datetime import datetime, timedelta
        now = datetime.now()
        local_one_min_ago = (
            now - timedelta(minutes=1)
        ).strftime("%Y-%m-%d %H:%M:%S")
        local_two_hours_ago = (
            now - timedelta(hours=2)
        ).strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"{local_one_min_ago} | cycle | score=80 labels=[]\n"
            f"{local_two_hours_ago} | cycle | score=50 labels=[]\n"
        )
        # window_hours=1 should keep the 1-min-ago line and drop
        # the 2-hours-ago line. If the parser were treating
        # timestamps as UTC instead of local, on a -5h tz the
        # 1-min-ago line would appear to be 5h+1min "in the
        # past" and get dropped — both lines would disappear.
        kept = _filter_cognition_window(text, window_hours=1)
        self.assertIn(local_one_min_ago, kept)
        self.assertNotIn(local_two_hours_ago, kept)


# ── quality.db classifier ───────────────────────────────────────────


class ApprovalClassifierTests(unittest.TestCase):
    """G.A.1: drift report's approval stream now reads
    audit_log.db (where the cockpit/decision-pipeline approval
    flow records owner decisions), NOT quality.db (which only
    tracks ActionEngine's internal lifecycle).

    The original G.A read quality.db and saw 0 approved outcomes
    over 459 Tier-2 actions — because cockpit approvals never
    write to quality.db. They write to audit_log.db with outcomes
    like ``approved_and_ran`` / ``approved_and_failed`` /
    ``rohit_rejected``. Production data: 297 cockpit approvals
    + 6 rejections in 30 days → ~98% approval, not 0%.

    Outcome mapping (audit_log → probe):
      ``approved_and_ran``    → approved (decision was approve;
                                action ran successfully)
      ``approved_and_failed`` → approved (decision was approve;
                                execution failed downstream)
      ``rohit_rejected``      → rejected
      anything else (NULL, deferred, …) → not counted in rate
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="maez_drift_test_")
        self.db_path = Path(self.tmpdir) / "audit_log.db"
        self._init_schema()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _init_schema(self):
        """Mirror memory/audit_log.db's schema (subset — only the
        fields the probe reads)."""
        con = sqlite3.connect(self.db_path)
        con.execute("""
            CREATE TABLE audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id  TEXT NOT NULL,
                ts          REAL NOT NULL,
                action      TEXT,
                outcome     TEXT,
                outcome_ts  REAL
            )
        """)
        con.commit()
        con.close()

    def _insert_outcomes(self, outcomes: list[str]):
        """Insert N rows with outcome_ts = now, varying outcomes."""
        now = time.time()
        con = sqlite3.connect(self.db_path)
        for i, outcome in enumerate(outcomes):
            con.execute(
                "INSERT INTO audit_log "
                "(request_id, ts, action, outcome, outcome_ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"req-{i}", now - i, "test_action", outcome, now - i),
            )
        con.commit()
        con.close()

    def test_high_approval_classifies_ok(self):
        """8 approved (5 ran + 3 failed) + 1 rejected → 8/9 ≈ 89% → OK."""
        from scripts.probe.maez_drift_report import classify_approval
        self._insert_outcomes(
            ["approved_and_ran"] * 5
            + ["approved_and_failed"] * 3
            + ["rohit_rejected"]
        )
        result = classify_approval(self.db_path, window_days=30)
        self.assertEqual(result.classification, "OK")
        self.assertGreater(result.approval_rate, 0.8)
        self.assertEqual(result.decided_actions, 9)
        self.assertEqual(result.approved_count, 8)
        self.assertEqual(result.rejected_count, 1)

    def test_approved_and_failed_counts_as_approved(self):
        """REGRESSION GUARD: ``approved_and_failed`` means the
        owner approved; the action FAILED downstream. From the
        approval-rate perspective (did the owner approve?), it's
        an approval. Probe must count it as such."""
        from scripts.probe.maez_drift_report import classify_approval
        self._insert_outcomes(
            ["approved_and_failed"] * 10 + ["rohit_rejected"]
        )
        result = classify_approval(self.db_path, window_days=30)
        # 10 approved (all failed downstream) / 11 decided ≈ 91%.
        self.assertGreater(result.approval_rate, 0.9)
        self.assertEqual(result.classification, "OK")
        # Expose the failure count separately so an operator sees
        # the execution-side problem distinctly from the approval-
        # side metric.
        self.assertEqual(result.approved_and_failed_count, 10)

    def test_low_approval_classifies_critical(self):
        """approval_rate < 0.4 → CRITICAL. 3 approved / 10 rejected
        → 3/13 ≈ 23%."""
        from scripts.probe.maez_drift_report import classify_approval
        self._insert_outcomes(
            ["approved_and_ran"] * 3 + ["rohit_rejected"] * 10
        )
        result = classify_approval(self.db_path, window_days=30)
        self.assertEqual(result.classification, "CRITICAL")
        self.assertLess(result.approval_rate, 0.4)

    def test_mid_approval_classifies_warn(self):
        from scripts.probe.maez_drift_report import classify_approval
        self._insert_outcomes(
            ["approved_and_ran"] * 5 + ["rohit_rejected"] * 5
        )
        result = classify_approval(self.db_path, window_days=30)
        self.assertEqual(result.classification, "WARN")

    def test_low_decided_volume_classifies_insufficient(self):
        """Fewer than QUALITY_MIN_DECIDED owner decisions →
        INSUFFICIENT_DATA. Don't claim health from a tiny sample."""
        from scripts.probe.maez_drift_report import classify_approval
        self._insert_outcomes(["approved_and_ran"] * 2)
        result = classify_approval(self.db_path, window_days=30)
        self.assertEqual(result.classification, "INSUFFICIENT_DATA")
        self.assertEqual(result.decided_actions, 2)

    def test_unresolved_cards_excluded_from_decided_count(self):
        """REGRESSION GUARD: pending cards (outcome IS NULL) MUST
        NOT be counted toward the decided population — they
        haven't been decided. Production audit_log has 52 such
        rows (355 total - 303 with outcome)."""
        from scripts.probe.maez_drift_report import classify_approval
        # Insert 6 decided + 50 unresolved.
        self._insert_outcomes(
            ["approved_and_ran"] * 5 + ["rohit_rejected"]
        )
        # Now insert 50 with NULL outcome.
        now = time.time()
        con = sqlite3.connect(self.db_path)
        for i in range(50):
            con.execute(
                "INSERT INTO audit_log "
                "(request_id, ts, action, outcome, outcome_ts) "
                "VALUES (?, ?, ?, NULL, NULL)",
                (f"req-pending-{i}", now - i, "test_action"),
            )
        con.commit()
        con.close()
        result = classify_approval(self.db_path, window_days=30)
        # Only 6 decided; 50 pending excluded.
        self.assertEqual(result.decided_actions, 6)
        # Approval rate computed against 6, not 56.
        self.assertAlmostEqual(result.approval_rate, 5 / 6, places=2)

    def test_missing_db_returns_insufficient(self):
        """Missing audit_log.db isn't CRITICAL — it's no-data
        (e.g., fresh deploy). Operator sees the gap, not a false
        alarm."""
        from scripts.probe.maez_drift_report import classify_approval
        result = classify_approval(
            Path("/nonexistent/audit_log.db"), window_days=30,
        )
        self.assertEqual(result.classification, "INSUFFICIENT_DATA")

    def test_unknown_outcomes_surfaced_not_dropped(self):
        """REGRESSION GUARD for M1 from G.A.1 review: outcomes the
        probe doesn't recognize (`refused_by_will`, future strings)
        must NOT silently disappear. They surface in
        ``unknown_outcomes`` so the operator sees what the probe
        is dropping."""
        from scripts.probe.maez_drift_report import classify_approval
        self._insert_outcomes(
            ["approved_and_ran"] * 5
            + ["rohit_rejected"]
            + ["refused_by_will"] * 3
            + ["expired"] * 2
        )
        result = classify_approval(self.db_path, window_days=30)
        # Recognized outcomes drive the rate.
        self.assertEqual(result.approved_count, 5)
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(result.decided_actions, 6)
        # Unknown outcomes are surfaced.
        self.assertEqual(
            result.unknown_outcomes,
            {"refused_by_will": 3, "expired": 2},
        )

    def test_recent_window_falls_through_to_warn_on_recent_dip(self):
        """REGRESSION GUARD for the 7-day window: a recent
        approval-rate dip should surface as WARN even if the
        30-day primary still looks OK. The combined classifier
        only fires CRITICAL when both windows agree."""
        from scripts.probe.maez_drift_report import classify_approval
        # Old data (>7 days ago) shows healthy approval.
        # Recent data (<7 days) shows poor approval.
        now = time.time()
        old_ts = now - 20 * 86400  # 20 days ago
        recent_ts = now - 1 * 86400  # 1 day ago
        con = sqlite3.connect(self.db_path)
        # 20 healthy approvals long ago.
        for i in range(20):
            con.execute(
                "INSERT INTO audit_log "
                "(request_id, ts, action, outcome, outcome_ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"old-{i}", old_ts, "x", "approved_and_ran", old_ts),
            )
        # 6 rejections recently (worse than 30-day average).
        for i in range(8):
            con.execute(
                "INSERT INTO audit_log "
                "(request_id, ts, action, outcome, outcome_ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"recent-{i}", recent_ts, "x",
                 "rohit_rejected" if i < 6 else "approved_and_ran",
                 recent_ts),
            )
        con.commit()
        con.close()
        result = classify_approval(self.db_path, window_days=30)
        # Primary 30-day rate is 22/28 ≈ 79% (still OK on its own).
        # Recent 7-day rate is 2/8 = 25% (CRITICAL on its own).
        # Combined: not both-critical (primary is OK), so WARN.
        self.assertEqual(result.classification, "WARN")
        self.assertIsNotNone(result.recent_approval_rate)
        self.assertLess(result.recent_approval_rate, 0.4)


# ── liveness classifier ─────────────────────────────────────────────


class LivenessTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="maez_drift_liveness_")
        self.log = Path(self.tmpdir) / "cognition.log"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _set_mtime(self, seconds_ago: float):
        """Touch the file with mtime = now - seconds_ago."""
        self.log.write_text("test\n")
        target = time.time() - seconds_ago
        import os
        os.utime(self.log, (target, target))

    def test_recent_log_write_classifies_ok(self):
        from scripts.probe.maez_drift_report import classify_liveness
        self._set_mtime(60)  # 1 minute ago
        result = classify_liveness(self.log)
        self.assertEqual(result.classification, "OK")

    def test_stale_log_classifies_warn(self):
        from scripts.probe.maez_drift_report import classify_liveness
        self._set_mtime(15 * 60)  # 15 minutes ago
        result = classify_liveness(self.log)
        self.assertEqual(result.classification, "WARN")

    def test_very_stale_log_classifies_critical(self):
        from scripts.probe.maez_drift_report import classify_liveness
        self._set_mtime(2 * 60 * 60)  # 2 hours ago
        result = classify_liveness(self.log)
        self.assertEqual(result.classification, "CRITICAL")

    def test_missing_log_classifies_critical(self):
        """A missing cognition.log is unambiguously CRITICAL —
        if the daemon were alive, it would be writing."""
        from scripts.probe.maez_drift_report import classify_liveness
        result = classify_liveness(Path("/nonexistent/cognition.log"))
        self.assertEqual(result.classification, "CRITICAL")


# ── overall verdict ─────────────────────────────────────────────────


class OverallVerdictTests(unittest.TestCase):
    def test_overall_is_worst_of_streams(self):
        """Overall verdict propagates the worst per-stream
        classification. CRITICAL overrides WARN; WARN overrides OK;
        OK overrides INSUFFICIENT_DATA."""
        from scripts.probe.maez_drift_report import compute_overall_verdict
        self.assertEqual(
            compute_overall_verdict(["OK", "OK", "OK"]), "OK",
        )
        self.assertEqual(
            compute_overall_verdict(["OK", "WARN", "OK"]), "WARN",
        )
        self.assertEqual(
            compute_overall_verdict(["WARN", "CRITICAL", "OK"]),
            "CRITICAL",
        )
        # INSUFFICIENT is below OK — it doesn't downgrade a healthy
        # stream's signal but it shouldn't claim OK overall on its own.
        self.assertEqual(
            compute_overall_verdict(["INSUFFICIENT_DATA"]),
            "INSUFFICIENT_DATA",
        )
        self.assertEqual(
            compute_overall_verdict(["OK", "INSUFFICIENT_DATA"]),
            "OK",
        )

    def test_empty_stream_list_returns_insufficient(self):
        from scripts.probe.maez_drift_report import compute_overall_verdict
        self.assertEqual(
            compute_overall_verdict([]), "INSUFFICIENT_DATA",
        )


# ── output ──────────────────────────────────────────────────────────


class OutputShapeTests(unittest.TestCase):
    def test_json_output_has_stable_top_level_schema(self):
        from scripts.probe.maez_drift_report import (
            DriftReport,
            CognitionResult,
            QualityResult,
            LivenessResult,
            to_json_payload,
        )
        report = DriftReport(
            source="test",
            window_hours=24,
            quality_window_days=30,
            cognition=CognitionResult(
                cycles_total=100, avg_score=70.0,
                fixation_rate=0.1, vague_rate=0.05,
                classification="OK",
            ),
            quality=QualityResult(
                approval_rate=0.85,
                decided_actions=20, approved_count=17,
                approved_and_failed_count=2,
                rejected_count=3,
                pending_count=10,
                classification="OK",
                unknown_outcomes={},
                recent_approval_rate=0.9,
                recent_decided_actions=10,
            ),
            liveness=LivenessResult(
                last_write_secs_ago=60.0, classification="OK",
            ),
            overall_verdict="OK",
        )
        payload = to_json_payload(report)
        for required in (
            "source", "window_hours", "cognition", "quality",
            "liveness", "overall_verdict",
        ):
            self.assertIn(required, payload)
        # Must be JSON-serializable end-to-end.
        import json
        s = json.dumps(payload, sort_keys=True)
        self.assertGreater(len(s), 0)


# ── isolation contract ──────────────────────────────────────────────


class IsolationContractTests(unittest.TestCase):
    """The drift report is read-only diagnostic infrastructure.
    AST-parse asserts no chromadb / memory.memory_manager imports.
    Coupling to lived memory would turn an alarm into a recall
    surface — exactly the laundering vector earlier F arc work
    closed."""

    def test_probe_does_not_import_chromadb_or_memory_manager(self):
        import ast
        path = (_REPO / "scripts" / "probe" / "maez_drift_report.py")
        self.assertTrue(path.exists())
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden = {
            "chromadb", "memory.memory_manager",
            "core.memory.memory_manager",
        }
        leaked: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name == f or alias.name.startswith(f + ".")
                           for f in forbidden):
                        leaked.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if any(mod == f or mod.startswith(f + ".")
                       for f in forbidden):
                    leaked.append(mod)
        self.assertEqual(leaked, [], f"forbidden imports: {leaked}")


if __name__ == "__main__":
    unittest.main()
