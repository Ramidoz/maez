# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Replay harness slice — fixture loader, probe runner, two-mode comparator.

Per docs/SLICE_GESTATION_BOUNDARY_MEMO.md §5:
  - Birth-readiness probes replace the 2.5c volume gate. Each probe
    targets one of the missing behavior classes (continuity, surface
    interleaving, real-content claims, envelope pressure, concurrency,
    multi-turn self-history).
  - Probes write to a SEPARATE test ledger DB (probe_ledger.db /
    in-memory), never the production gestation ledger.

The harness has two modes:
  - regression  — compare current vs stored baseline (detect drift)
  - birth_readiness — compare current vs expected post-birth behavior
                      (gap to birth criteria)
"""
from __future__ import annotations

import io
import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import replay_harness as rh  # noqa: E402

_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_replay_harness_")


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_probe_db(name: str) -> str:
    from core.ledger import migrate
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


_CORPUS_PATH = (
    Path(__file__).resolve().parent / "probes" / "birth_readiness_corpus.jsonl"
)


class FixtureLoaderTests(unittest.TestCase):
    """Probes load from JSONL — one probe per line, validated against
    the schema. Malformed lines fail loudly."""

    def test_corpus_file_exists(self):
        self.assertTrue(_CORPUS_PATH.exists(), _CORPUS_PATH)

    def test_corpus_loads_all_six_categories(self):
        probes = rh.load_probes(_CORPUS_PATH)
        categories = {p.category for p in probes}
        self.assertEqual(
            categories,
            {
                "multi_turn_continuity",
                "surface_interleaving",
                "real_content_claims",
                "envelope_pressure",
                "concurrency",
                "multi_turn_self_history",
            },
            "corpus must cover all 6 missing 2.5c behavior classes",
        )

    def test_each_probe_has_required_fields(self):
        probes = rh.load_probes(_CORPUS_PATH)
        for p in probes:
            self.assertTrue(p.id, "probe missing id")
            self.assertTrue(p.category, "probe missing category")
            self.assertTrue(p.purpose, "probe missing purpose")
            self.assertEqual(p.expected_lifecycle_target, "birth_ready")

    def test_malformed_jsonl_line_raises(self):
        bad = io.StringIO('{"id": "x", "category": "x"}\n{not valid json\n')
        with self.assertRaises(rh.ProbeCorpusError):
            list(rh._iter_probes_from_handle(bad, source="<test>"))

    def test_missing_required_field_raises(self):
        bad = io.StringIO('{"id": "x"}\n')  # no category, no purpose
        with self.assertRaises(rh.ProbeCorpusError):
            list(rh._iter_probes_from_handle(bad, source="<test>"))


class TelemetryCaptureTests(unittest.TestCase):
    """The harness's _LogCapture handler captures structured records
    from maez.envelope and maez.cognition during a probe run.
    Pattern is identical to test_envelope_builder_budget.py."""

    def test_log_capture_records_envelope_warnings(self):
        from core.cognition import envelope_builder as eb
        with rh.capture_logs(["maez.envelope"]) as cap:
            builder = eb.BoundedEnvelopeBuilder()
            # Force a per_section truncation: too many tool_results.
            builder.build(
                ledger_db_path=None,
                signals_present=[], signals_absent=[],
                tool_results=[
                    {"name": f"t{i}", "status": "ok", "summary": "x"}
                    for i in range(20)
                ],
            )
        kinds = {
            getattr(r, "truncation_kind", None)
            for r in cap.records
            if getattr(r, "truncation_kind", None) is not None
        }
        self.assertIn("per_section_cap", kinds)


class ProbeLedgerIsolationTests(unittest.TestCase):
    """Probes MUST write to a separate test ledger, never production
    gestation ledger. Verified by source-check + behavior."""

    def test_probe_runner_uses_supplied_db_path(self):
        db = _fresh_probe_db("isolation")
        # The runner takes a db_path arg; if supplied, that's where
        # writes go. Source-check + light behavior test.
        self.assertTrue(callable(rh.run_probe))
        # The first probe in the corpus is continuity; load it.
        probes = rh.load_probes(_CORPUS_PATH)
        prob = next(p for p in probes if p.category == "multi_turn_continuity")
        # Run with the supplied probe DB; harness should not touch
        # any other DB. We don't assert on outcome here — just on
        # isolation: probe DB should still be usable after.
        rh.run_probe(prob, probe_db_path=db, mode="birth_readiness")
        # DB should still be a valid ledger.
        import sqlite3
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT count(*) FROM turns"
            ).fetchone()
            self.assertGreaterEqual(row[0], 1)  # at least genesis

    def test_runner_never_writes_to_production_ledger(self):
        # Source-check the harness: the runner's invocations of
        # the writer must explicitly pass probe_db_path; no
        # default-path fallback should exist.
        src = (Path(_SCRIPTS) / "replay_harness.py").read_text()
        # Forbidden: the production path string MUST NOT appear
        # anywhere in the script.
        self.assertNotIn("memory/ledger.db", src,
            "harness must not reference production ledger path")
        self.assertNotIn("MAEZ_LEDGER_DB_PATH", src,
            "harness must not read the env var that points at "
            "the production ledger; it should always use its own "
            "explicit probe_db_path")


class ConcurrencyProbeTests(unittest.TestCase):
    """The concurrency probe writes N rows in parallel and asserts
    chain integrity. Closes the 2.5c gap on overlap/concurrency."""

    def test_concurrency_probe_passes_with_clean_chain(self):
        db = _fresh_probe_db("concurrency")
        probes = rh.load_probes(_CORPUS_PATH)
        prob = next(p for p in probes if p.category == "concurrency")
        result = rh.run_probe(prob, probe_db_path=db, mode="birth_readiness")
        self.assertEqual(result.verdict, "PASS",
            f"concurrency probe failed: {result.reason}")
        # 10 concurrent writes should land cleanly.
        from core.ledger import chain
        import sqlite3
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM turns ORDER BY timestamp ASC"
            ).fetchall()]
        violations = chain.verify_chain(rows)
        self.assertEqual(violations, [],
            f"chain integrity violated: {violations!r}")


class EnvelopePressureProbeTests(unittest.TestCase):
    """The envelope pressure probe forces truncation and asserts
    correct telemetry shape."""

    def test_envelope_pressure_probe_emits_truncation(self):
        db = _fresh_probe_db("env_pressure")
        probes = rh.load_probes(_CORPUS_PATH)
        prob = next(p for p in probes if p.category == "envelope_pressure")
        result = rh.run_probe(prob, probe_db_path=db, mode="birth_readiness")
        self.assertEqual(result.verdict, "PASS",
            f"envelope pressure probe failed: {result.reason}")
        # Per probe spec: at least 1 truncation event.
        self.assertGreaterEqual(
            result.metrics.get("truncation_events", 0), 1,
        )


class GestationRecallProbeTests(unittest.TestCase):
    """Multi-turn self-history probe: gestation rows downweight behind
    lived rows; pre-birth label surfaces."""

    def test_lived_rows_rank_before_gestation(self):
        db = _fresh_probe_db("gest_recall")
        probes = rh.load_probes(_CORPUS_PATH)
        prob = next(
            p for p in probes
            if p.category == "multi_turn_self_history"
        )
        result = rh.run_probe(prob, probe_db_path=db, mode="birth_readiness")
        self.assertEqual(result.verdict, "PASS",
            f"gestation recall probe failed: {result.reason}")


class BirthReadinessReportTests(unittest.TestCase):
    """When all probes pass, the harness reports overall PASS.
    When any fail, the gap-to-birth metric is non-zero."""

    def test_full_corpus_run_produces_report(self):
        report = rh.run_corpus(
            corpus_path=_CORPUS_PATH,
            probe_db_factory=_fresh_probe_db,
            mode="birth_readiness",
        )
        self.assertGreaterEqual(len(report.results), 6)
        # Overall verdict aggregates per-probe verdicts.
        self.assertIn(report.overall, {"PASS", "FAIL", "PARTIAL"})
        # Birth-readiness gap is the count of non-PASS probes.
        self.assertEqual(
            report.gap_to_birth,
            sum(1 for r in report.results if r.verdict != "PASS"),
        )

    def test_report_renders_human_readable(self):
        report = rh.run_corpus(
            corpus_path=_CORPUS_PATH,
            probe_db_factory=_fresh_probe_db,
            mode="birth_readiness",
        )
        text = rh.format_report(report)
        self.assertIn("BIRTH-READINESS PROBE REPORT", text)
        self.assertIn("overall:", text.lower())


class EnvelopePressureMinFloorTests(unittest.TestCase):
    """Adversarial-review-flagged: a probe with
    expected_truncation_events_min=0 (or missing) would false-PASS
    if a future regression silently disabled truncation entirely.
    The runner enforces a floor of 1."""

    def test_zero_expected_min_does_not_false_pass_on_no_truncations(self):
        # Construct a probe with expected_min=0 + envelope inputs
        # designed NOT to trigger truncation (small char_cap budget
        # but tiny inputs). The runner should still FAIL because the
        # min-floor of 1 forces "at least one truncation must fire."
        bad_probe = rh.Probe(
            id="false_pass_test",
            category="envelope_pressure",
            purpose="adversarial test",
            expected_lifecycle_target="birth_ready",
            raw={
                "id": "false_pass_test",
                "category": "envelope_pressure",
                "purpose": "x",
                "expected_truncation_events_min": 0,  # the trap
                "synthetic_envelope_input": {
                    "tool_results_count": 1,
                    "tool_results_summary_chars": 10,
                    "claimable_count": 0,
                    "forbidden_count": 0,
                    "char_cap": 12000,  # plenty of room
                },
            },
        )
        db = _fresh_probe_db("false_pass_test")
        result = rh.run_probe(bad_probe, probe_db_path=db,
                              mode="birth_readiness")
        # The min-floor of 1 forces FAIL: no truncations occurred,
        # but the runner expected at least 1.
        self.assertEqual(
            result.verdict, "FAIL",
            "expected_truncation_events_min=0 must not allow false-PASS "
            "on a no-truncation envelope; runner forces min>=1",
        )


class ReadOnlyContractTests(unittest.TestCase):
    """The harness script must not import production daemon
    initialization paths that would touch the real ledger or
    network. Pinned by source-check."""

    def test_no_forbidden_imports(self):
        src = (Path(_SCRIPTS) / "replay_harness.py").read_text()
        forbidden = (
            "from daemon.maez_daemon import",  # full daemon init touches network
            "import ollama",
        )
        for bad in forbidden:
            for line in src.splitlines():
                stripped = line.strip()
                self.assertFalse(
                    stripped.startswith(bad),
                    f"forbidden import in replay_harness.py: {line!r}",
                )


if __name__ == "__main__":
    unittest.main()
