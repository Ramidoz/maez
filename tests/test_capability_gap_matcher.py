# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability gap-matcher tests (Step 2 of the Decision-19/20
capability-acquisition pipeline arc).

Lexical-only matching, deterministic. Pin the documented v1
contract so a future v1.5 (semantic upgrade) can't silently regress
the explainability surface.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── synthetic manual fixture ───────────────────────────────────────


def _entry_text(
    *,
    capability_id: str,
    title: str,
    status: str = "stable",
    gap_signals: list[str],
    body: str = "Body.\n",
) -> str:
    """Produce a valid manual entry as text. Mirrors the
    capability_manual loader's expected shape."""
    sigs = "\n".join(f"  - {json.dumps(s)}" for s in gap_signals)
    return (
        "---\n"
        f"capability_id: {capability_id}\n"
        f"title: {title}\n"
        f"status: {status}\n"
        f"gap_signals:\n{sigs}\n"
        "prerequisites: []\n"
        "external_prerequisites: []\n"
        "acquisition: self-dev\n"
        "covenant:\n"
        "  consent-card-required: true\n"
        "  exact-phrase-ratification: false\n"
        "  covenant-touch: low\n"
        "conflicts_with: []\n"
        "reference_papers: []\n"
        "implementation_files: []\n"
        f"---\n{body}"
    )


def _build_three_entry_manual(root: Path) -> None:
    """Write the three seed-shaped entries into ``root``."""
    (root / "recursive-context-engine.md").write_text(_entry_text(
        capability_id="recursive-context-engine",
        title="Recursive Context Engine (RLM)",
        gap_signals=[
            "user requests synthesis across more than 30 days of memory",
            "user requests audit-style summary of repo or codebase",
            "Maez surfaces 'context too long' or truncates synthesis",
        ],
    ))
    (root / "multi-session-entity-linking.md").write_text(_entry_text(
        capability_id="multi-session-entity-linking",
        title="Multi-session entity linking",
        gap_signals=[
            "user asks about a person mentioned across multiple sessions",
            "answer requires synthesizing evidence from two or more sessions",
            "Maez finds session A and session B individually but cannot connect them",
        ],
    ))
    (root / "temporal-arithmetic-at-recall.md").write_text(_entry_text(
        capability_id="temporal-arithmetic-at-recall",
        title="Temporal arithmetic at recall time",
        gap_signals=[
            "user asks 'when did X happen?'",
            "user asks 'how long after Y did Z happen?'",
            "user asks 'before X happened, what did I say?'",
        ],
    ))


# ── ranking tests ──────────────────────────────────────────────────


class TestRanking(unittest.TestCase):
    def test_rlm_query_ranks_recursive_context_engine_first(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            matches = match_gap(
                "audit the entire repo and produce a synthesis "
                "across many days of memory",
                manual=manual,
            )
        self.assertGreater(len(matches), 0)
        self.assertEqual(matches[0].capability_id, "recursive-context-engine")

    def test_multisession_entity_query_ranks_correct_first(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            matches = match_gap(
                "what did Maya say across multiple sessions about her school",
                manual=manual,
            )
        self.assertGreater(len(matches), 0)
        self.assertEqual(
            matches[0].capability_id, "multi-session-entity-linking",
        )

    def test_temporal_query_ranks_correct_first(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            matches = match_gap(
                "when did the move happen and how long after did "
                "Dad's health start getting worse",
                manual=manual,
            )
        self.assertGreater(len(matches), 0)
        self.assertEqual(
            matches[0].capability_id, "temporal-arithmetic-at-recall",
        )


# ── stopword + threshold tests ────────────────────────────────────


class TestStopwordsAndThresholds(unittest.TestCase):
    def test_pure_stopword_overlap_scores_zero(self):
        """Without stopword filtering, "the a is to in of" would
        match every entry on grammar glue. Pin that this doesn't
        happen."""
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            matches = match_gap(
                "the a is to in of and or but with from for at",
                manual=manual,
            )
        # All-stopword query → no useful matches.
        self.assertEqual(matches, [])

    def test_score_normalized_to_unit_interval(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            matches = match_gap(
                "synthesis across days of memory audit repo",
                manual=manual,
            )
        for m in matches:
            self.assertGreaterEqual(m.score, 0.0)
            self.assertLessEqual(m.score, 1.0)

    def test_matched_signals_excludes_pure_stopword_hits(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            matches = match_gap(
                "audit the entire repo across many days of memory",
                manual=manual,
            )
        for m in matches:
            for sig in m.matched_signals:
                # Each matched signal must share at least one
                # non-stopword token with the query (or have an
                # exact phrase hit; this corpus uses tokens).
                self.assertTrue(
                    bool(m.matched_terms),
                    f"signal {sig!r} matched but no terms recorded",
                )


# ── deprecated handling ────────────────────────────────────────────


class TestDeprecatedHandling(unittest.TestCase):
    def test_deprecated_excluded_by_default(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "old-thing.md").write_text(_entry_text(
                capability_id="old-thing",
                title="Deprecated old thing",
                status="deprecated",
                gap_signals=["user requests memory synthesis"],
            ))
            (root / "new-thing.md").write_text(_entry_text(
                capability_id="new-thing",
                title="New thing",
                gap_signals=["user requests memory synthesis"],
            ))
            manual = load_manual(root)
            matches = match_gap("memory synthesis", manual=manual)
        ids = [m.capability_id for m in matches]
        self.assertIn("new-thing", ids)
        self.assertNotIn("old-thing", ids)

    def test_deprecated_included_with_flag(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "old-thing.md").write_text(_entry_text(
                capability_id="old-thing",
                title="Deprecated old thing",
                status="deprecated",
                gap_signals=["user requests memory synthesis"],
            ))
            manual = load_manual(root)
            matches = match_gap(
                "memory synthesis", manual=manual,
                include_deprecated=True,
            )
        ids = [m.capability_id for m in matches]
        self.assertIn("old-thing", ids)


# ── empty / no-match cases ─────────────────────────────────────────


class TestEmptyCases(unittest.TestCase):
    def test_empty_query_returns_empty_list(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            self.assertEqual(match_gap("", manual=manual), [])
            self.assertEqual(match_gap("   ", manual=manual), [])

    def test_no_match_returns_empty_list_not_error(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            matches = match_gap(
                "completely unrelated knitting pattern instructions",
                manual=manual,
            )
        self.assertEqual(matches, [])


# ── tie-break determinism ──────────────────────────────────────────


class TestTieBreakDeterministic(unittest.TestCase):
    def test_equal_scores_break_by_capability_id_alpha(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Two entries with IDENTICAL gap_signals — same score
            # for any matching query.
            for cid in ("zebra-cap", "alpha-cap", "mango-cap"):
                (root / f"{cid}.md").write_text(_entry_text(
                    capability_id=cid, title=cid,
                    gap_signals=["user wants a synthesis"],
                ))
            manual = load_manual(root)
            matches = match_gap("synthesis", manual=manual)
        ids = [m.capability_id for m in matches]
        # Tie-break: capability_id alphabetical ascending.
        self.assertEqual(ids, sorted(ids))


# ── lazy-cached default manual ─────────────────────────────────────


class TestLazyCachedManual(unittest.TestCase):
    def test_manual_none_loads_default_via_cache(self):
        from core.capability_gap_matcher import match_gap, clear_cache

        clear_cache()
        # Default manual is the real docs/maez_manual — should
        # resolve without raising and return list (possibly empty).
        result = match_gap("anything")
        self.assertIsInstance(result, list)

    def test_clear_cache_forces_reload(self):
        from core.capability_gap_matcher import (
            clear_cache, _get_default_manual,
        )

        clear_cache()
        m1 = _get_default_manual()
        m2 = _get_default_manual()
        self.assertIs(m1, m2, "second call should hit cache")
        clear_cache()
        m3 = _get_default_manual()
        self.assertIsNot(m1, m3, "after clear, fresh load expected")


# ── known lexical-miss documentation test ─────────────────────────


class TestKnownLexicalMiss(unittest.TestCase):
    """Documents the v1 limitation: natural human phrasing of a
    temporal-reasoning gap doesn't match temporal-arithmetic-at-recall
    via lexical overlap. When v1.5 lands with semantic matching,
    this test should be flipped to assert the SUCCESSFUL match —
    that's the visible behavior change the upgrade delivers."""

    def test_known_lexical_miss_natural_phrasing(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            # Natural grandmother phrasing of a temporal question.
            # The right answer is temporal-arithmetic-at-recall, but
            # token overlap with that entry's gap_signals is zero.
            matches = match_gap(
                "I keep forgetting things from last spring",
                manual=manual,
            )
        # v1: no match. When v1.5 ships with semantic matching, flip
        # this assertion to assertEqual(matches[0].capability_id,
        # "temporal-arithmetic-at-recall"). The flip itself becomes
        # the regression test that semantic upgrade delivered.
        self.assertEqual(
            matches, [],
            "v1 expected to miss this naturally-phrased query — if "
            "this test is failing because matches were returned, "
            "either lexical scoring changed or v1.5 (semantic) landed; "
            "update the assertion accordingly.",
        )


# ── telemetry: best-effort, never breaks matching ─────────────────


class TestTelemetry(unittest.TestCase):
    def test_telemetry_write_failure_does_not_break_matching(self):
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            # Patch the telemetry writer to raise; matching must
            # still return correct ranked results.
            with patch(
                "core.infra.capability_gap_matcher._append_telemetry",
                side_effect=RuntimeError("simulated disk-full"),
            ):
                matches = match_gap(
                    "audit the entire repo and synthesize across "
                    "many days of memory",
                    manual=manual,
                )
        # Matching should still produce results — the failure was
        # swallowed.
        self.assertGreater(len(matches), 0)
        self.assertEqual(matches[0].capability_id, "recursive-context-engine")

    def test_telemetry_zero_match_writes_null_top_capability(self):
        """When no match is found, telemetry still fires (we want
        to know about misses). top_capability_id and top_score
        must be JSON null, not omitted."""
        from core.capability_gap_matcher import match_gap, clear_cache
        from core.capability_manual import load_manual

        clear_cache()
        captured = []

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_three_entry_manual(root)
            manual = load_manual(root)
            with patch(
                "core.infra.capability_gap_matcher._append_telemetry",
                side_effect=lambda payload: captured.append(payload),
            ):
                match_gap("knitting pattern instructions", manual=manual)
        self.assertEqual(len(captured), 1)
        self.assertIsNone(captured[0]["top_capability_id"])
        self.assertIsNone(captured[0]["top_score"])
        self.assertEqual(captured[0]["matched_count"], 0)


# ── real manual smoke ─────────────────────────────────────────────


class TestRealManualSmoke(unittest.TestCase):
    def test_real_manual_loads_and_matches(self):
        from core.capability_gap_matcher import match_gap, clear_cache

        clear_cache()
        # Direct query to the live manual — at least one of the three
        # seed entries should match this.
        matches = match_gap(
            "I need to synthesize across many months of memory and "
            "audit my codebase"
        )
        self.assertIsInstance(matches, list)
        # The real manual has recursive-context-engine; expect it to
        # win this query.
        ids = [m.capability_id for m in matches]
        self.assertIn("recursive-context-engine", ids)


if __name__ == "__main__":
    unittest.main()
