# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests for the signal-baseline sufficiency report (Phase 2 prep).

The probe is read-only diagnostic infrastructure: read the JSONL
signal logs, classify per-kind data sufficiency, surface gaps. NO
daemon hook in this slice; build the discrimination layer before
acting on it.

Sufficiency thresholds (user-pinned):

  insufficient: count <5 OR span_days <7
  emerging:     count >=5 AND span_days >=7 (and not usable)
  usable:       count >=21 AND span_days >=14 AND distinct_active_days >=3

Special granularity flag for sparse high-value kinds (location):
when distinct_places <2, set ``needs_more_granularity`` regardless
of span — two GPS pings at the same address aren't a baseline
even if they're 10 days apart.

Expected-but-missing whitelist (advisory, not ontology):
``{location, arrive_home, focus_mode, workout, sleep, calendar,
battery}``. Missing kinds reported as "not present in logs," NOT
"broken" — Maez doesn't know every signal it should have.

Isolation contract: probe MUST NOT import chromadb,
memory.memory_manager, or core.memory.memory_manager. Read-only
JSONL; AST-parse test enforces structurally.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _entry(kind: str, ts: str, **data) -> dict:
    """Build a JSONL-shape entry matching production's ingest format
    (skills/iphone_ingest.py:105–122)."""
    return {
        "timestamp": ts,
        "kind": kind,
        "data": data,
        "source": "ios_shortcuts",
    }


def _write_jsonl(dir_path: Path, fname: str, entries: list[dict]) -> Path:
    path = dir_path / fname
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path


# ── classifier ──────────────────────────────────────────────────────


class ClassifierTests(unittest.TestCase):
    """Lock the three-region thresholds. Boundary tests use the
    user's explicit cutoffs (count >=21, span >=14, active >=3)."""

    def _classify(self, count, span_days, active_days):
        from scripts.probe.signal_baseline_report import classify
        return classify(count, span_days, active_days)

    def test_insufficient_when_count_below_5(self):
        self.assertEqual(self._classify(4, 30.0, 4), "insufficient")

    def test_insufficient_when_span_below_7_days(self):
        self.assertEqual(self._classify(50, 6.9, 5), "insufficient")

    def test_emerging_at_lower_boundary(self):
        # count=5, span=7.0, active=2 → emerging
        self.assertEqual(self._classify(5, 7.0, 2), "emerging")

    def test_emerging_at_upper_boundary(self):
        # count=20, span=13.0 → emerging (count <21 OR span<14)
        self.assertEqual(self._classify(20, 13.0, 3), "emerging")

    def test_usable_at_exact_threshold(self):
        # count>=21, span>=14, active>=3 → usable
        self.assertEqual(self._classify(21, 14.0, 3), "usable")

    def test_usable_with_higher_volume(self):
        self.assertEqual(self._classify(100, 30.0, 14), "usable")

    def test_count_21_but_span_below_14_falls_to_emerging(self):
        # >=21 events but span <14 → not usable; still meets emerging
        # because count >=5 AND span >=7.
        self.assertEqual(self._classify(21, 10.0, 5), "emerging")

    def test_active_days_below_3_falls_to_emerging(self):
        # >=21 events, span >=14, but active_days=2 → not usable.
        self.assertEqual(self._classify(25, 14.0, 2), "emerging")


# ── parser + report ─────────────────────────────────────────────────


class ParseAndReportTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="signal_baseline_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_directory_yields_empty_report(self):
        from scripts.probe.signal_baseline_report import build_report
        rep = build_report(Path(self.tmpdir))
        self.assertEqual(rep.total_events, 0)
        self.assertEqual(rep.kinds_observed, {})
        # Whitelist still reports missing — operator sees the gap.
        self.assertIn("location", rep.kinds_missing)
        self.assertIn("arrive_home", rep.kinds_missing)

    def test_nonexistent_directory_yields_empty_report_no_crash(self):
        """Defensive: a freshly-cloned repo or a misconfigured
        --dir path must produce a zero-count report rather than
        raise. The operator sees an empty kinds_observed and a
        full kinds_missing list, which is the correct
        diagnostic — 'no logs at this path,' not a stack trace."""
        from scripts.probe.signal_baseline_report import build_report
        rep = build_report(Path("/nonexistent/path/xyzzy/signals"))
        self.assertEqual(rep.total_events, 0)
        self.assertEqual(rep.kinds_observed, {})
        self.assertEqual(rep.parse_stats.files_read, 0)
        self.assertEqual(rep.parse_stats.total_lines, 0)
        # Missing list still populated with the whitelist so an
        # operator running --json against a misconfigured path
        # still sees the expected-kind list.
        self.assertIn("location", rep.kinds_missing)

    def test_single_kind_with_15_events_classifies_emerging(self):
        """Mirrors current production: 15 arrive_home over ~14 days
        → emerging. The probe should match this prediction."""
        from scripts.probe.signal_baseline_report import build_report
        # 15 events spread across 14 days — 8 distinct active days.
        entries = []
        for i, day_offset in enumerate([0, 1, 2, 4, 6, 7, 9, 10]):
            for j in range(2 if day_offset < 7 else 1):  # 8 days, mix
                ts = (
                    f"2026-04-{18 + day_offset:02d}T"
                    f"{12 + j:02d}:00:00+00:00"
                )
                entries.append(_entry("arrive_home", ts))
        # Pad to 15 events.
        while len(entries) < 15:
            entries.append(_entry(
                "arrive_home",
                f"2026-04-{28 + (len(entries) - 13):02d}T15:00:00+00:00",
            ))
        _write_jsonl(Path(self.tmpdir), "2026-04-18.jsonl", entries)
        rep = build_report(Path(self.tmpdir))
        kind_stat = rep.kinds_observed["arrive_home"]
        self.assertEqual(kind_stat.count, 15)
        self.assertGreaterEqual(kind_stat.span_days, 7.0)
        self.assertEqual(kind_stat.classification, "emerging")
        # arrive_home no longer in missing list.
        self.assertNotIn("arrive_home", rep.kinds_missing)

    def test_location_with_2_events_gets_granularity_note(self):
        """Sparse high-value kinds: distinct_places <2 must flag
        needs_more_granularity regardless of span. Two GPS pings at
        the same address aren't a baseline."""
        from scripts.probe.signal_baseline_report import build_report
        # Two location events at the same place.
        entries = [
            _entry("location",
                   "2026-04-20T10:00:00+00:00",
                   lat=38.905, lon=-92.328,
                   place="4001 State Farm Pkwy"),
            _entry("location",
                   "2026-05-01T10:00:00+00:00",
                   lat=38.905, lon=-92.328,
                   place="4001 State Farm Pkwy"),
        ]
        _write_jsonl(Path(self.tmpdir), "2026-04-20.jsonl", entries)
        rep = build_report(Path(self.tmpdir))
        stat = rep.kinds_observed["location"]
        # Count is 2 → insufficient by count regardless.
        self.assertEqual(stat.classification, "insufficient")
        # Distinct places = 1.
        self.assertEqual(stat.distinct_places, 1)
        self.assertIsNotNone(stat.granularity_note)
        self.assertIn("distinct_places", stat.granularity_note.lower())

    def test_location_with_2_distinct_places_no_granularity_note(self):
        """If distinct_places >=2, the granularity flag does NOT
        fire — even though count is still <5 (insufficient by count
        alone)."""
        from scripts.probe.signal_baseline_report import build_report
        entries = [
            _entry("location",
                   "2026-04-20T10:00:00+00:00",
                   lat=38.905, lon=-92.328,
                   place="4001 State Farm Pkwy"),
            _entry("location",
                   "2026-05-01T10:00:00+00:00",
                   lat=40.0, lon=-93.0,
                   place="A different address"),
        ]
        _write_jsonl(Path(self.tmpdir), "2026-04-20.jsonl", entries)
        rep = build_report(Path(self.tmpdir))
        stat = rep.kinds_observed["location"]
        self.assertEqual(stat.distinct_places, 2)
        self.assertIsNone(stat.granularity_note)


# ── parser robustness ───────────────────────────────────────────────


class ParserRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="signal_baseline_robust_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_parser_skips_malformed_json_lines(self):
        from scripts.probe.signal_baseline_report import build_report
        path = Path(self.tmpdir) / "2026-05-01.jsonl"
        path.write_text(
            json.dumps(_entry("arrive_home", "2026-05-01T10:00:00+00:00"))
            + "\n"
            + "{not valid json\n"
            + json.dumps(_entry("arrive_home", "2026-05-01T11:00:00+00:00"))
            + "\n"
        )
        rep = build_report(Path(self.tmpdir))
        self.assertEqual(rep.parse_stats.malformed_json, 1)
        self.assertEqual(rep.parse_stats.parsed, 2)
        self.assertEqual(rep.total_events, 2)

    def test_parser_skips_entries_missing_kind(self):
        from scripts.probe.signal_baseline_report import build_report
        path = Path(self.tmpdir) / "2026-05-01.jsonl"
        # One valid + one missing kind + one with empty kind.
        path.write_text(
            json.dumps(_entry("arrive_home", "2026-05-01T10:00:00+00:00"))
            + "\n"
            + json.dumps({"timestamp": "2026-05-01T11:00:00+00:00",
                          "data": {}, "source": "ios_shortcuts"})
            + "\n"
            + json.dumps({"timestamp": "2026-05-01T12:00:00+00:00",
                          "kind": "", "data": {},
                          "source": "ios_shortcuts"})
            + "\n"
        )
        rep = build_report(Path(self.tmpdir))
        self.assertEqual(rep.parse_stats.missing_kind, 2)
        self.assertEqual(rep.total_events, 1)

    def test_parser_handles_iso_z_suffix(self):
        """ambient.py:89,120 calls .replace('Z', '+00:00') before
        fromisoformat. Probe must match that contract — locale-Z
        timestamps must parse and contribute to span computation."""
        from scripts.probe.signal_baseline_report import build_report
        entries = [
            _entry("arrive_home", "2026-04-20T10:00:00Z"),
            _entry("arrive_home", "2026-05-01T10:00:00Z"),
        ]
        _write_jsonl(Path(self.tmpdir), "2026-04-20.jsonl", entries)
        rep = build_report(Path(self.tmpdir))
        stat = rep.kinds_observed["arrive_home"]
        self.assertEqual(stat.count, 2)
        # Span should be ~11 days (Apr 20 → May 1).
        self.assertGreater(stat.span_days, 10.0)
        self.assertLess(stat.span_days, 12.0)


# ── expected-but-missing whitelist ──────────────────────────────────


class ExpectedMissingTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="signal_baseline_missing_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_kinds_list_advisory_only(self):
        """The whitelist {location, arrive_home, focus_mode, workout,
        sleep, calendar, battery} is reported when absent from logs.
        Mark as 'not present in logs', not 'broken'."""
        from scripts.probe.signal_baseline_report import (
            EXPECTED_KINDS, build_report,
        )
        entries = [_entry("arrive_home", "2026-05-01T10:00:00+00:00")]
        _write_jsonl(Path(self.tmpdir), "2026-05-01.jsonl", entries)
        rep = build_report(Path(self.tmpdir))
        # arrive_home present → not missing.
        self.assertNotIn("arrive_home", rep.kinds_missing)
        # The other 6 expected kinds → all missing.
        for k in EXPECTED_KINDS:
            if k != "arrive_home":
                self.assertIn(k, rep.kinds_missing)

    def test_observed_non_whitelist_kinds_still_classified(self):
        """A kind in VALID_KINDS but not in EXPECTED_KINDS (e.g.
        manual_note) still gets classified normally — the whitelist
        is for missing-detection only, not for what's reported."""
        from scripts.probe.signal_baseline_report import build_report
        entries = [
            _entry("manual_note", f"2026-05-01T{i:02d}:00:00+00:00",
                   text="something")
            for i in range(10)
        ]
        _write_jsonl(Path(self.tmpdir), "2026-05-01.jsonl", entries)
        rep = build_report(Path(self.tmpdir))
        self.assertIn("manual_note", rep.kinds_observed)
        # 10 events on 1 day → span = 0.something → insufficient.
        self.assertEqual(
            rep.kinds_observed["manual_note"].classification,
            "insufficient",
        )


# ── output ──────────────────────────────────────────────────────────


class OutputShapeTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="signal_baseline_output_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_json_output_has_stable_top_level_schema(self):
        from scripts.probe.signal_baseline_report import (
            build_report, to_json_payload,
        )
        entries = [_entry("arrive_home", "2026-05-01T10:00:00+00:00")]
        _write_jsonl(Path(self.tmpdir), "2026-05-01.jsonl", entries)
        rep = build_report(Path(self.tmpdir))
        payload = to_json_payload(rep)
        for required in (
            "source", "total_events", "kinds_observed",
            "kinds_missing", "parse_stats",
        ):
            self.assertIn(required, payload)
        # JSON-serializable.
        s = json.dumps(payload, sort_keys=True)
        self.assertGreater(len(s), 0)

    def test_human_output_includes_classification_per_kind(self):
        from scripts.probe.signal_baseline_report import (
            build_report, format_human,
        )
        entries = [
            _entry("arrive_home", f"2026-04-{18 + i:02d}T10:00:00+00:00")
            for i in range(10)
        ]
        _write_jsonl(Path(self.tmpdir), "2026-04-18.jsonl", entries)
        rep = build_report(Path(self.tmpdir))
        out = format_human(rep)
        self.assertIn("arrive_home", out)
        self.assertIn("emerging", out.lower())


# ── isolation contract ──────────────────────────────────────────────


class IsolationContractTests(unittest.TestCase):
    """The probe is read-only diagnostic infrastructure. It must NOT
    couple to Chroma or MemoryManager — coupling here would make the
    report a recall surface, exactly the laundering vector earlier
    F arc work closed. AST parse rather than text grep so a comment
    that mentions 'chromadb' by name does not false-positive."""

    def test_probe_does_not_import_chromadb_or_memory_manager(self):
        import ast
        path = (_REPO / "scripts" / "probe"
                / "signal_baseline_report.py")
        self.assertTrue(path.exists(), f"missing {path}")
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
