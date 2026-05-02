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


class QualityClassifierTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="maez_drift_test_")
        self.db_path = Path(self.tmpdir) / "quality.db"
        self._init_schema()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _init_schema(self):
        """Mirror memory/quality_tracker.py's schema."""
        con = sqlite3.connect(self.db_path)
        con.execute("""
            CREATE TABLE action_outcomes (
                action_id       TEXT PRIMARY KEY,
                tier            INTEGER NOT NULL,
                action_type     TEXT NOT NULL,
                reasoning       TEXT,
                parameters      TEXT,
                proposed_at     REAL NOT NULL,
                outcome         TEXT,
                resolved_at     REAL,
                rohit_feedback  TEXT,
                screen_activity TEXT,
                focus_level     TEXT
            )
        """)
        con.commit()
        con.close()

    def _insert_outcomes(self, outcomes: list[str]):
        """Insert N rows with proposed_at = now, varying outcomes."""
        now = time.time()
        con = sqlite3.connect(self.db_path)
        for i, outcome in enumerate(outcomes):
            con.execute(
                "INSERT INTO action_outcomes (action_id, tier, "
                "action_type, proposed_at, outcome, resolved_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f"a-{i}", 0, "test", now - i, outcome, now - i + 0.01),
            )
        con.commit()
        con.close()

    def test_high_approval_classifies_ok(self):
        """Production formula: approval_rate = approved / (approved
        + cancelled + rejected). 8 approved, 1 cancelled, 1 rejected
        → 8/10 = 80% → OK."""
        from scripts.probe.maez_drift_report import classify_quality
        self._insert_outcomes(
            ["approved"] * 8 + ["cancelled", "rejected"]
        )
        result = classify_quality(self.db_path, window_days=30)
        self.assertEqual(result.classification, "OK")
        self.assertEqual(result.approval_rate, 0.8)
        self.assertEqual(result.decided_actions, 10)

    def test_low_approval_classifies_critical(self):
        """approval_rate < 0.4 → CRITICAL. Mirrors the soul-note
        trigger at quality_tracker.py:236 (which also uses the
        approved/decided ratio, not approved/total)."""
        from scripts.probe.maez_drift_report import classify_quality
        # 3 approved / 7 cancelled / 3 rejected → 3/13 ≈ 23%.
        self._insert_outcomes(
            ["approved"] * 3 + ["cancelled"] * 7 + ["rejected"] * 3
        )
        result = classify_quality(self.db_path, window_days=30)
        self.assertEqual(result.classification, "CRITICAL")
        self.assertLess(result.approval_rate, 0.4)

    def test_mid_approval_classifies_warn(self):
        from scripts.probe.maez_drift_report import classify_quality
        # 5 approved / 5 cancelled → 50% → WARN (between 0.4 and 0.6).
        self._insert_outcomes(
            ["approved"] * 5 + ["cancelled"] * 5
        )
        result = classify_quality(self.db_path, window_days=30)
        self.assertEqual(result.classification, "WARN")

    def test_executed_excluded_from_approval_rate(self):
        """REGRESSION GUARD: production formula EXCLUDES executed
        from both numerator and denominator. A daemon doing 100
        auto-actions + 8 approved + 2 cancelled is NOT a 91%
        approval rate — it's 80% (8/10), and the 100 executed are
        surfaced separately as informational. Without this test
        the probe would report a different metric than the
        soul-note trigger fires on (the BLOCKER from G.A review)."""
        from scripts.probe.maez_drift_report import classify_quality
        self._insert_outcomes(
            ["executed"] * 100 + ["approved"] * 8 + ["cancelled"] * 2
        )
        result = classify_quality(self.db_path, window_days=30)
        self.assertEqual(result.total_actions, 110)
        self.assertEqual(result.executed_count, 100)
        self.assertEqual(result.decided_actions, 10)
        self.assertEqual(result.approval_rate, 0.8)
        self.assertEqual(result.classification, "OK")

    def test_low_decided_volume_classifies_insufficient(self):
        """N decided < QUALITY_MIN_DECIDED (5) → INSUFFICIENT_DATA.
        100 executed + 2 approved is NOT a basis for judging
        approval rate — owner has only made 2 decisions."""
        from scripts.probe.maez_drift_report import classify_quality
        self._insert_outcomes(
            ["executed"] * 100 + ["approved"] * 2
        )
        result = classify_quality(self.db_path, window_days=30)
        self.assertEqual(result.classification, "INSUFFICIENT_DATA")
        self.assertEqual(result.decided_actions, 2)

    def test_missing_db_returns_insufficient(self):
        """A missing quality.db isn't a CRITICAL — it's a no-data
        case (e.g., fresh deploy). Operator sees the gap, not a
        false alarm."""
        from scripts.probe.maez_drift_report import classify_quality
        result = classify_quality(
            Path("/nonexistent/quality.db"), window_days=30,
        )
        self.assertEqual(result.classification, "INSUFFICIENT_DATA")


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
                total_actions=50, approval_rate=0.85,
                decided_actions=20, approved_count=17,
                cancelled_count=5, rejected_count=2,
                executed_count=30,
                classification="OK",
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
