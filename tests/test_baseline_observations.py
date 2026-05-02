# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""F1.A — baseline observation store + lexical detector.

5x.D.B2 closed the audit-bypass for `_do_update_baseline` but the
through-quotation surface remains open (probe 1e0f0fb confirmed
structurally). The future fix is split:

  F1: observation mode — capture baseline writes + recall context
      + lexical detector signals, no behavior change. Build labeled
      ground truth before designing enforcement.

  F2: measured downgrade gate — once F1 has labeled data, downgrade
      derived baselines to untrusted when the detector says they
      depend on untrusted recall.

This slice (F1.A) builds the isolated SQLite observation store + a
substring detector. It does NOT wire `action_engine`. F1.B will
thread recall context through and call into this store.

Critical isolation contracts:
  - Store is SQLite, NOT Chroma. Anything Chroma-shaped risks
    becoming recall material later.
  - The module must NOT import chromadb or MemoryManager. Any
    coupling to Maez's lived-memory substrate would turn this
    audit log into a recall surface — exactly the laundering
    vector we're trying to close.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _isolate_db():
    """Helper: point MAEZ_BASELINE_OBSERVATIONS_DB at a tmpdir before
    importing the module under test, so each test starts with a
    fresh DB file. Returns (tmpdir, original_env)."""
    tmpdir = tempfile.mkdtemp(prefix="baseline_obs_test_")
    db_path = Path(tmpdir) / "baseline_observations.db"
    original = os.environ.get("MAEZ_BASELINE_OBSERVATIONS_DB")
    os.environ["MAEZ_BASELINE_OBSERVATIONS_DB"] = str(db_path)
    return tmpdir, original


def _restore_env(original):
    if original is None:
        os.environ.pop("MAEZ_BASELINE_OBSERVATIONS_DB", None)
    else:
        os.environ["MAEZ_BASELINE_OBSERVATIONS_DB"] = original


# ── substring detector ──────────────────────────────────────────────


class SubstringDetectorTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir, self.original_env = _isolate_db()

    def tearDown(self):
        _restore_env(self.original_env)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_detector_catches_long_verbatim_quote(self):
        """A baseline that contains a long substring of an untrusted
        memory's content should produce a hit naming the memory_id."""
        from core.memory.baseline_observations import substring_hits

        untrusted = [{
            "id": "raw-evil",
            "content": (
                "the company's quarterly earnings dropped 47% according "
                "to ExternalNewsBlog dated 2026-04-30"
            ),
        }]
        baseline = (
            "Earlier today I noticed the company's quarterly "
            "earnings dropped 47% according to ExternalNewsBlog. "
            "Worth recording."
        )
        hits = substring_hits(baseline, untrusted)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["memory_id"], "raw-evil")
        self.assertGreaterEqual(hits[0]["match_length"], 20)
        self.assertIn("quarterly earnings", hits[0]["matched_text"])

    def test_detector_ignores_short_overlap(self):
        """Trivial common-word overlap (e.g. 'the company') must not
        produce a hit. F1.A uses a conservative minimum-length
        threshold; topical-only overlap is below it."""
        from core.memory.baseline_observations import substring_hits

        untrusted = [{
            "id": "raw-evil",
            "content": "the company is fascinating",
        }]
        baseline = "the company has interesting metrics today"
        hits = substring_hits(baseline, untrusted)
        self.assertEqual(hits, [])

    def test_detector_returns_empty_on_no_untrusted(self):
        from core.memory.baseline_observations import substring_hits
        self.assertEqual(substring_hits("anything", []), [])

    def test_detector_handles_multiple_untrusted_memories(self):
        from core.memory.baseline_observations import substring_hits

        untrusted = [
            {"id": "raw-a",
             "content": "the alpha experimental result that nobody can verify"},
            {"id": "raw-b",
             "content": "and beta probability distribution shows otherwise"},
        ]
        baseline = (
            "Today's reasoning: the alpha experimental result that "
            "nobody can verify combined with the beta probability "
            "distribution shows otherwise."
        )
        hits = substring_hits(baseline, untrusted)
        self.assertEqual(
            sorted(h["memory_id"] for h in hits),
            ["raw-a", "raw-b"],
        )

    def test_detector_boundary_at_min_match_length(self):
        """A match exactly at MIN_MATCH_LEN must hit; one char shorter
        must not. Locks the threshold semantics so a future agent
        tuning MIN_MATCH_LEN sees both sides of the boundary."""
        from core.memory.baseline_observations import (
            MIN_MATCH_LEN, substring_hits,
        )

        exact = "x" * MIN_MATCH_LEN
        below = "x" * (MIN_MATCH_LEN - 1)

        untrusted_exact = [{"id": "raw-x", "content": exact}]
        self.assertEqual(len(substring_hits(exact, untrusted_exact)), 1)

        untrusted_below = [{"id": "raw-x", "content": below}]
        self.assertEqual(substring_hits(below, untrusted_below), [])

    def test_detector_marks_case_normalized_on_unicode_length_drift(self):
        """``"İ".lower() == "i\\u0307"`` (1 char → 2). When
        ``len(audited.lower()) != len(audited)``, the slice on the
        original-case string would mis-align; the detector falls back
        to the lowercased slice and flags ``case_normalized=True`` so
        labelers see the evidence is normalized rather than verbatim."""
        from core.memory.baseline_observations import substring_hits

        # Build an audited observation whose lowercased form is
        # longer than itself, then a matching untrusted memory.
        prefix = "İ" + "the alpha experimental result that nobody"
        # `prefix.lower()` is `"i̇" + "the alpha..."`.
        # The DP will find the long ASCII overlap below MIN; build a
        # tail past 20 chars to ensure a hit.
        audited = prefix + " can verify "
        untrusted = [{
            "id": "raw-uni",
            "content": "the alpha experimental result that nobody can verify",
        }]
        hits = substring_hits(audited, untrusted)
        self.assertEqual(len(hits), 1)
        # On Unicode-divergent input the case_normalized flag is
        # True and matched_text is sourced from the lowercased
        # string; both signals go to F1.C labelers.
        self.assertTrue(hits[0]["case_normalized"])
        self.assertGreaterEqual(hits[0]["match_length"], 20)

    def test_detector_does_not_mark_case_normalized_on_ascii(self):
        """Pure-ASCII input is the hot path; case_normalized must be
        False so labelers see the original-case evidence verbatim."""
        from core.memory.baseline_observations import substring_hits

        untrusted = [{
            "id": "raw-x",
            "content": "the alpha experimental result that nobody can verify",
        }]
        baseline = "Today: the alpha experimental result that nobody can verify."
        hits = substring_hits(baseline, untrusted)
        self.assertEqual(len(hits), 1)
        self.assertFalse(hits[0]["case_normalized"])


# ── record_observation round-trip ───────────────────────────────────


class RecordObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir, self.original_env = _isolate_db()

    def tearDown(self):
        _restore_env(self.original_env)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_record_observation_round_trips_json_fields(self):
        from core.memory.baseline_observations import (
            record_observation, recent,
        )
        row_id = record_observation(
            observation="raw observation",
            audited_observation="audited observation",
            recall_ids=["raw-1", "raw-2", "core-3"],
            recall_tiers={"raw-1": "lived", "raw-2": "untrusted",
                          "core-3": "covenant"},
            untrusted_ids=["raw-2"],
            substring_hits_=[{
                "memory_id": "raw-2",
                "matched_text": "some matched phrase here",
                "match_length": 24,
            }],
        )
        self.assertIsNotNone(row_id)
        self.assertGreaterEqual(row_id, 1)

        rows = recent(limit=10)
        self.assertEqual(len(rows), 1)
        rec = rows[0]
        self.assertEqual(rec.observation, "raw observation")
        self.assertEqual(rec.audited_observation, "audited observation")
        self.assertEqual(rec.recall_ids, ["raw-1", "raw-2", "core-3"])
        self.assertEqual(rec.recall_tiers["raw-2"], "untrusted")
        self.assertEqual(rec.untrusted_ids, ["raw-2"])
        self.assertEqual(len(rec.substring_hits), 1)
        self.assertEqual(rec.substring_hits[0]["memory_id"], "raw-2")
        # Pinned constants
        self.assertEqual(rec.surface, "action_baseline_update")
        self.assertEqual(rec.action, "update_baseline")
        self.assertEqual(rec.decision, "observe_only")
        self.assertEqual(rec.detector_version, "substring-v1")


class RecentFilterTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir, self.original_env = _isolate_db()

    def tearDown(self):
        _restore_env(self.original_env)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_recent_only_with_untrusted_filters_clean_rows(self):
        from core.memory.baseline_observations import (
            record_observation, recent,
        )
        record_observation(
            observation="clean baseline",
            audited_observation="clean baseline",
            recall_ids=["raw-1"],
            recall_tiers={"raw-1": "lived"},
            untrusted_ids=[],
            substring_hits_=[],
        )
        record_observation(
            observation="suspicious baseline",
            audited_observation="suspicious baseline",
            recall_ids=["raw-2"],
            recall_tiers={"raw-2": "untrusted"},
            untrusted_ids=["raw-2"],
            substring_hits_=[{
                "memory_id": "raw-2",
                "matched_text": "long verbatim phrase quoted from raw-2",
                "match_length": 38,
            }],
        )
        all_rows = recent(limit=10)
        self.assertEqual(len(all_rows), 2)

        flagged = recent(limit=10, only_with_untrusted=True)
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0].observation, "suspicious baseline")


# ── fail-soft on DB failure ─────────────────────────────────────────


class FailSoftTests(unittest.TestCase):
    def test_record_observation_returns_none_on_db_failure(self):
        """Mirrors consequence_memory's fail-soft contract: a broken
        observation log MUST NOT crash the caller. F1.A is observation-
        only; losing rows is preferable to breaking action paths."""
        # Point at a path that cannot be created (a file masquerading
        # as a directory parent). Also clear cached connection state.
        original = os.environ.get("MAEZ_BASELINE_OBSERVATIONS_DB")
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        tmp_file.write(b"not-a-directory")
        tmp_file.close()
        # The DB path now claims `/<file>/x.db`, where parent is a
        # regular file → mkdir fails → connect fails → fail-soft.
        os.environ["MAEZ_BASELINE_OBSERVATIONS_DB"] = (
            tmp_file.name + "/baseline.db"
        )
        try:
            # Reload module so it picks up the bad env var. The module
            # caches DB_PATH at import time per consequence_memory's
            # pattern, so a fresh import is needed.
            for mod_name in list(sys.modules):
                if "baseline_observations" in mod_name:
                    del sys.modules[mod_name]
            from core.memory.baseline_observations import record_observation
            row_id = record_observation(
                observation="x", audited_observation="x",
                recall_ids=[], recall_tiers={}, untrusted_ids=[],
                substring_hits_=[],
            )
            self.assertIsNone(row_id)
        finally:
            os.unlink(tmp_file.name)
            if original is None:
                os.environ.pop("MAEZ_BASELINE_OBSERVATIONS_DB", None)
            else:
                os.environ["MAEZ_BASELINE_OBSERVATIONS_DB"] = original
            for mod_name in list(sys.modules):
                if "baseline_observations" in mod_name:
                    del sys.modules[mod_name]


class SchemaMismatchFailSoftTests(unittest.TestCase):
    """Fail-soft contract under realistic failure shapes. The
    blanket ``except Exception`` must catch a pre-existing table
    whose schema is incompatible — most likely future regression:
    a future migration adds a NOT NULL column without a default,
    every insert raises, every observation row is silently dropped
    rather than crashing the action path."""

    def setUp(self):
        self.tmpdir, self.original_env = _isolate_db()
        # Pre-create a malformed table at the env-var path so the
        # CREATE TABLE IF NOT EXISTS in _connect skips it and the
        # subsequent INSERT mismatches.
        import sqlite3 as _sql
        db_path = Path(os.environ["MAEZ_BASELINE_OBSERVATIONS_DB"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with _sql.connect(db_path) as con:
            con.execute(
                "CREATE TABLE baseline_observations ("
                "id INTEGER PRIMARY KEY, "
                "wrong_column_a TEXT NOT NULL, "
                "wrong_column_b TEXT NOT NULL"
                ")"
            )
            con.commit()

    def tearDown(self):
        _restore_env(self.original_env)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_record_observation_returns_none_on_schema_mismatch(self):
        from core.memory.baseline_observations import record_observation
        row_id = record_observation(
            observation="x", audited_observation="x",
            recall_ids=[], recall_tiers={}, untrusted_ids=[],
            substring_hits_=[],
        )
        self.assertIsNone(row_id)

    def test_recent_returns_empty_on_schema_mismatch(self):
        from core.memory.baseline_observations import recent
        self.assertEqual(recent(limit=10), [])


# ── isolation contract ──────────────────────────────────────────────


class IsolationContractTests(unittest.TestCase):
    """The most load-bearing test in this suite: the module MUST NOT
    import chromadb or MemoryManager. Any coupling to Maez's lived-
    memory substrate would turn this audit log into a recall surface
    — exactly the laundering vector F1 exists to close.

    AST parse rather than text grep so a comment that mentions
    'chromadb' by name does not false-positive."""

    def test_module_does_not_import_chromadb_or_memory_manager(self):
        import ast
        path = (_REPO / "core" / "memory"
                / "baseline_observations.py")
        self.assertTrue(path.exists(), f"missing {path}")
        tree = ast.parse(path.read_text(encoding="utf-8"))

        forbidden = {"chromadb", "memory.memory_manager"}
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

        self.assertEqual(
            leaked, [],
            f"baseline_observations.py imported forbidden module(s): "
            f"{leaked}. F1.A's isolation contract requires this "
            f"module to stay decoupled from Chroma / MemoryManager so "
            f"its observation log cannot become recall material.",
        )


if __name__ == "__main__":
    unittest.main()
