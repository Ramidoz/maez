# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for scripts/sandbox_summary.py — the read-only diagnostic
helper for the 2.5c sandbox window.

Pins the parser shape against real log line formats observed in the
codebase (envelope_builder._emit_truncation, self_claim_audit
emissions). If a future log-format change breaks parsing, these
tests fail loudly instead of the helper silently reporting zero
events.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"

# Add scripts/ to path so we can import the module under test.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import sandbox_summary as ss  # noqa: E402


def _write_logs(
    logs_dir: Path,
    *,
    maez_lines: list[str] | None = None,
    cognition_lines: list[str] | None = None,
) -> None:
    if maez_lines is not None:
        (logs_dir / "maez.log").write_text("\n".join(maez_lines) + "\n")
    if cognition_lines is not None:
        (logs_dir / "cognition.log").write_text(
            "\n".join(cognition_lines) + "\n",
        )


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp(prefix="maez_sandbox_summary_")
        self.logs_dir = Path(self._td)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._td, ignore_errors=True)


class EmptyAndMissingTests(_Tmp):
    def test_no_log_files_returns_empty_report(self):
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8, 0, 0, 0),
            until=datetime(2026, 5, 8, 23, 0, 0),
        )
        self.assertEqual(report["truncations"], [])
        self.assertEqual(dict(report["judge_unavail"]), {})
        self.assertEqual(report["audit_total"], 0)

    def test_empty_log_files_returns_empty_report(self):
        _write_logs(self.logs_dir, maez_lines=[], cognition_lines=[])
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        self.assertEqual(report["truncations"], [])
        self.assertEqual(report["audit_total"], 0)


class EnvelopeTruncationParsingTests(_Tmp):
    def test_per_section_cap_line_parsed(self):
        line = (
            "2026-05-08 12:34:56 [WARNING] envelope_truncated "
            "section=tool_results kind=per_section_cap "
            "dropped_entries=12 dropped_chars=2400 "
            "before=15000 after=12600 cap=12000"
        )
        _write_logs(self.logs_dir, maez_lines=[line])
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        self.assertEqual(len(report["truncations"]), 1)
        t = report["truncations"][0]
        self.assertEqual(t["section"], "tool_results")
        self.assertEqual(t["kind"], "per_section_cap")
        self.assertEqual(t["dropped_entries"], 12)
        self.assertEqual(t["dropped_chars"], 2400)
        self.assertEqual(t["before"], 15000)
        self.assertEqual(t["after"], 12600)
        self.assertEqual(t["cap"], 12000)

    def test_minimal_fallback_line_parsed(self):
        line = (
            "2026-05-08 12:34:56 [WARNING] envelope_truncated "
            "section=envelope kind=minimal_fallback "
            "dropped_entries=-1 dropped_chars=8400 "
            "before=18000 after=9600 cap=12000"
        )
        _write_logs(self.logs_dir, maez_lines=[line])
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        self.assertEqual(len(report["truncations"]), 1)
        self.assertEqual(report["truncations"][0]["kind"], "minimal_fallback")
        self.assertEqual(report["truncations"][0]["dropped_entries"], -1)


class JudgeUnavailableParsingTests(_Tmp):
    def test_judge_unavail_line_parsed(self):
        line = (
            "2026-05-08 09:00:00 [WARNING] self_claim_audit: "
            "grounding judge unavailable (error_class=refused) "
            "— audit disabled until judge recovers. detail: simulated"
        )
        _write_logs(self.logs_dir, maez_lines=[line])
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        self.assertEqual(report["judge_unavail"]["refused"], 1)

    def test_multiple_error_classes_counted_separately(self):
        lines = [
            "2026-05-08 09:00:00 [WARNING] self_claim_audit: "
            "grounding judge unavailable (error_class=refused) "
            "— x. detail: y",
            "2026-05-08 09:01:00 [WARNING] self_claim_audit: "
            "grounding judge unavailable (error_class=timeout) "
            "— x. detail: y",
            "2026-05-08 09:02:00 [WARNING] self_claim_audit: "
            "grounding judge unavailable (error_class=timeout) "
            "— x. detail: y",
        ]
        _write_logs(self.logs_dir, maez_lines=lines)
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        self.assertEqual(report["judge_unavail"]["refused"], 1)
        self.assertEqual(report["judge_unavail"]["timeout"], 2)


class AuditCogParsingTests(_Tmp):
    def test_audit_cog_line_parsed(self):
        line = (
            "2026-05-08 12:00:00 | self_claim_audit | "
            "surface=daemon_cycle flagged=2 mode=sentence kinds=judge"
        )
        _write_logs(self.logs_dir, cognition_lines=[line])
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        self.assertEqual(report["audit_total"], 1)
        self.assertEqual(report["audit_flagged_total"], 2)
        self.assertEqual(report["audit_modes"]["sentence"], 1)
        self.assertEqual(report["audit_surfaces"]["daemon_cycle"], 1)

    def test_multiple_modes_and_surfaces(self):
        lines = [
            "2026-05-08 12:00:00 | self_claim_audit | "
            "surface=daemon_cycle flagged=0 mode=noop kinds=-",
            "2026-05-08 12:01:00 | self_claim_audit | "
            "surface=telegram_text flagged=1 mode=sentence kinds=judge",
            "2026-05-08 12:02:00 | self_claim_audit | "
            "surface=telegram_text flagged=0 mode=judge_unavailable kinds=-",
        ]
        _write_logs(self.logs_dir, cognition_lines=lines)
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        self.assertEqual(report["audit_total"], 3)
        self.assertEqual(report["audit_flagged_total"], 1)
        self.assertEqual(report["audit_modes"]["noop"], 1)
        self.assertEqual(report["audit_modes"]["sentence"], 1)
        self.assertEqual(report["audit_modes"]["judge_unavailable"], 1)
        self.assertEqual(report["audit_surfaces"]["telegram_text"], 2)


class TimeWindowFilterTests(_Tmp):
    def test_since_excludes_earlier_events(self):
        lines = [
            "2026-05-07 23:00:00 [WARNING] envelope_truncated "
            "section=A kind=per_section_cap dropped_entries=1 "
            "dropped_chars=10 before=100 after=90 cap=80",
            "2026-05-08 12:00:00 [WARNING] envelope_truncated "
            "section=B kind=total_cap dropped_entries=2 "
            "dropped_chars=20 before=200 after=180 cap=150",
        ]
        _write_logs(self.logs_dir, maez_lines=lines)
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8, 0, 0, 0),
            until=datetime(2026, 5, 9),
        )
        self.assertEqual(len(report["truncations"]), 1)
        self.assertEqual(report["truncations"][0]["section"], "B")

    def test_until_excludes_later_events(self):
        lines = [
            "2026-05-08 06:00:00 [WARNING] envelope_truncated "
            "section=A kind=per_section_cap dropped_entries=1 "
            "dropped_chars=10 before=100 after=90 cap=80",
            "2026-05-08 23:00:00 [WARNING] envelope_truncated "
            "section=B kind=total_cap dropped_entries=2 "
            "dropped_chars=20 before=200 after=180 cap=150",
        ]
        _write_logs(self.logs_dir, maez_lines=lines)
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 8, 12, 0, 0),
        )
        self.assertEqual(len(report["truncations"]), 1)
        self.assertEqual(report["truncations"][0]["section"], "A")

    def test_resolve_window_hours(self):
        fake_now = datetime(2026, 5, 8, 14, 0, 0)
        args = type(
            "A", (), {"since": None, "until": None, "hours": 6},
        )()
        since, until = ss._resolve_window(args, _now=fake_now)
        self.assertEqual(since, datetime(2026, 5, 8, 8, 0, 0))
        self.assertEqual(until, fake_now)

    def test_resolve_window_default_24h(self):
        fake_now = datetime(2026, 5, 8, 14, 0, 0)
        args = type(
            "A", (), {"since": None, "until": None, "hours": None},
        )()
        since, until = ss._resolve_window(args, _now=fake_now)
        self.assertEqual(since, datetime(2026, 5, 7, 14, 0, 0))

    def test_resolve_window_explicit_since_until(self):
        args = type("A", (), {
            "since": "2026-05-08 09:00:00",
            "until": "2026-05-08 17:00:00",
            "hours": None,
        })()
        since, until = ss._resolve_window(args)
        self.assertEqual(since, datetime(2026, 5, 8, 9, 0, 0))
        self.assertEqual(until, datetime(2026, 5, 8, 17, 0, 0))

    def test_resolve_window_since_after_until_raises(self):
        args = type("A", (), {
            "since": "2026-05-08 17:00:00",
            "until": "2026-05-08 09:00:00",
            "hours": None,
        })()
        with self.assertRaises(SystemExit):
            ss._resolve_window(args)


class MalformedAndUnknownTests(_Tmp):
    def test_unmatched_lines_silently_skipped(self):
        lines = [
            "2026-05-08 12:00:00 [INFO] daemon started",
            "garbage line with no timestamp",
            "2026-05-08 12:01:00 [DEBUG] some other event",
            "2026-05-08 12:02:00 [WARNING] envelope_truncated "
            "section=A kind=total_cap dropped_entries=1 "
            "dropped_chars=10 before=100 after=90 cap=80",
        ]
        _write_logs(self.logs_dir, maez_lines=lines)
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        # Only the well-formed envelope_truncated line counted.
        self.assertEqual(len(report["truncations"]), 1)

    def test_malformed_numeric_field_skipped(self):
        # `dropped_chars=NaN` — int() raises, skip the line.
        lines = [
            "2026-05-08 12:00:00 [WARNING] envelope_truncated "
            "section=A kind=total_cap dropped_entries=1 "
            "dropped_chars=NaN before=100 after=90 cap=80",
        ]
        _write_logs(self.logs_dir, maez_lines=lines)
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        self.assertEqual(len(report["truncations"]), 0)


class FormatReportSmokeTests(_Tmp):
    def test_empty_window_renders_clean_report(self):
        out = ss.format_report(
            ss.scan_logs(
                logs_dir=self.logs_dir,
                since=datetime(2026, 5, 8),
                until=datetime(2026, 5, 9),
            ),
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
            logs_dir=self.logs_dir,
        )
        # Headers present.
        self.assertIn("MAEZ SANDBOX SUMMARY", out)
        self.assertIn("ENVELOPE TRUNCATIONS", out)
        self.assertIn("GROUNDING JUDGE UNAVAILABILITY", out)
        self.assertIn("AUDIT REWRITE DISTRIBUTION", out)
        self.assertIn("RECALL CAP PRESSURE", out)
        self.assertIn("DISABLED-MODE SIGNAL", out)

    def test_populated_window_renders_counts(self):
        _write_logs(
            self.logs_dir,
            maez_lines=[
                "2026-05-08 12:00:00 [WARNING] envelope_truncated "
                "section=tool_results kind=per_section_cap "
                "dropped_entries=12 dropped_chars=2400 "
                "before=15000 after=12600 cap=12000",
                "2026-05-08 12:30:00 [WARNING] self_claim_audit: "
                "grounding judge unavailable (error_class=timeout) "
                "— x. detail: y",
            ],
            cognition_lines=[
                "2026-05-08 12:00:01 | self_claim_audit | "
                "surface=daemon_cycle flagged=2 mode=sentence kinds=judge",
            ],
        )
        report = ss.scan_logs(
            logs_dir=self.logs_dir,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
        )
        out = ss.format_report(
            report,
            since=datetime(2026, 5, 8),
            until=datetime(2026, 5, 9),
            logs_dir=self.logs_dir,
        )
        self.assertIn("tool_results", out)
        self.assertIn("per_section_cap", out)
        self.assertIn("timeout", out)
        self.assertIn("daemon_cycle", out)
        self.assertIn("rewrite rate", out)


class CLIInvocationTests(_Tmp):
    def test_main_runs_without_error(self):
        # Default to last 24h on an empty logs dir; should print
        # the empty summary and exit 0.
        argv = ["--logs-dir", str(self.logs_dir), "--hours", "1"]
        captured = io.StringIO()
        with patch.object(sys, "stdout", captured):
            rc = ss.main(argv)
        self.assertEqual(rc, 0)
        self.assertIn("MAEZ SANDBOX SUMMARY", captured.getvalue())


class ReadOnlyContractTests(unittest.TestCase):
    """Pin the script's read-only character: no daemon imports, no
    non-stdlib third-party imports. If a future change adds e.g.
    `from core.cognition import ...` the test fails loudly."""

    def test_helper_only_imports_stdlib(self):
        src = (
            Path(__file__).resolve().parent.parent
            / "scripts" / "sandbox_summary.py"
        ).read_text()
        # Forbidden imports (pulls in daemon / DB / model paths).
        forbidden_prefixes = (
            "from core.",
            "import core",
            "from daemon",
            "import daemon",
            "from skills",
            "import skills",
            "import sqlite3",
            "from memory",
            "import ollama",
        )
        for line in src.splitlines():
            stripped = line.strip()
            for bad in forbidden_prefixes:
                self.assertFalse(
                    stripped.startswith(bad),
                    f"sandbox_summary.py forbidden import: {line!r}",
                )


if __name__ == "__main__":
    unittest.main()
