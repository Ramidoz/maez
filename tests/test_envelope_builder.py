# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.audit.envelope_builder.build_envelope.

Slice 3 proper foundation. The builder assembles the dict shape
declared by :mod:`core.ledger.envelope_schema` (§3) from the per-turn
state available at generation time:

  - signals_present / signals_absent  → str lists, dedup + stable order
  - tool_results                      → list of dicts (passthrough)
  - self_history                      → built from recent_turns lookup,
                                        truncated to SELF_HISTORY_SUMMARY_MAX
  - claimable / forbidden             → optional passthrough lists

The output dict MUST pass envelope_schema.validate_envelope.
"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_envelope_builder_")

from core.ledger import migrate, writer, envelope_schema  # noqa: E402
from core.cognition import envelope_builder  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


_MR_KW = dict(
    model_id="qwen36-27b",
    prompt_hash="p" * 64,
    soul_hash="s" * 64,
    evidence_envelope={"claimable": [], "forbidden": []},
    audit_verdict={"verdict": "grounded"},
)


def _write(db: str, kind: str, text: str, **kwargs) -> str:
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
        w = writer.LedgerWriter(db)
        try:
            tid = w.write_turn(kind, text, **kwargs)
        finally:
            w.close()
    return tid


class ShapeAndValidationTests(unittest.TestCase):
    def test_minimal_envelope_validates(self):
        db = _fresh_db("min")
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=[],
            signals_absent=[],
            tool_results=[],
        )
        envelope_schema.validate_envelope(env)
        self.assertIn("signals_present", env)
        self.assertIn("signals_absent", env)
        self.assertIn("tool_results", env)
        self.assertIn("self_history", env)
        self.assertEqual(env["self_history"], [])

    def test_full_envelope_validates(self):
        db = _fresh_db("full")
        _write(db, "model_reply", "I told you the kettle was on.", **_MR_KW)
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=["system stats", "screen"],
            signals_absent=["calendar"],
            tool_results=[{"name": "ls", "status": "ok", "summary": ""}],
            claimable=[{"text": "kettle is on", "provenance": "observed"}],
            forbidden=[{"text": "the toaster is haunted",
                        "reason": "no signal"}],
        )
        envelope_schema.validate_envelope(env)


class SignalsListTests(unittest.TestCase):
    def test_signals_dedup_stable_order(self):
        db = _fresh_db("sigs")
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=["a", "b", "a", "c", "b"],
            signals_absent=["x", "x", "y"],
            tool_results=[],
        )
        self.assertEqual(env["signals_present"], ["a", "b", "c"])
        self.assertEqual(env["signals_absent"], ["x", "y"])

    def test_non_string_signals_filtered(self):
        db = _fresh_db("sigtypes")
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=["ok", None, 42, "fine"],
            signals_absent=[],
            tool_results=[],
        )
        self.assertEqual(env["signals_present"], ["ok", "fine"])


class SelfHistoryTests(unittest.TestCase):
    def test_self_history_populated_from_ledger(self):
        db = _fresh_db("sh_basic")
        _write(db, "model_reply", "first reply", **_MR_KW)
        time.sleep(0.005)
        tid2 = _write(db, "model_reply", "second reply", **_MR_KW)
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=[], signals_absent=[], tool_results=[],
        )
        self.assertEqual(len(env["self_history"]), 2)
        # newest first
        self.assertEqual(env["self_history"][0]["turn_id"], tid2)
        self.assertEqual(env["self_history"][0]["kind"], "model_reply")
        self.assertEqual(
            env["self_history"][0]["utterance_summary"], "second reply",
        )
        envelope_schema.validate_envelope(env)

    def test_self_history_only_qualifying_kinds(self):
        db = _fresh_db("sh_kinds")
        _write(db, "user_message", "owner: hi")
        _write(db, "model_reply", "maez reply", **_MR_KW)
        _write(db, "user_message", "owner: thanks")
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=[], signals_absent=[], tool_results=[],
        )
        kinds = {e["kind"] for e in env["self_history"]}
        # Only the three kinds in SELF_HISTORY_KINDS qualify.
        self.assertTrue(
            kinds <= envelope_schema.SELF_HISTORY_KINDS,
            f"got disallowed kinds: {kinds}",
        )
        # No user_message in self_history (it's a chat partner's
        # utterance, not Maez's own).
        self.assertNotIn("user_message", kinds)
        self.assertEqual(len(env["self_history"]), 1)

    def test_self_history_summary_truncated(self):
        db = _fresh_db("sh_trunc")
        long_text = "x" * 500
        _write(db, "model_reply", long_text, **_MR_KW)
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=[], signals_absent=[], tool_results=[],
        )
        summary = env["self_history"][0]["utterance_summary"]
        self.assertLessEqual(
            len(summary), envelope_schema.SELF_HISTORY_SUMMARY_MAX,
        )
        # Bound was hit → ellipsis suffix indicates truncation.
        self.assertTrue(summary.endswith("…"))
        envelope_schema.validate_envelope(env)

    def test_self_history_default_limit(self):
        db = _fresh_db("sh_limit")
        for i in range(8):
            _write(db, "model_reply", f"reply_{i}", **_MR_KW)
            time.sleep(0.002)
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=[], signals_absent=[], tool_results=[],
        )
        # Slice 3.0d cap on self_history rows = 5 (per memo §2).
        self.assertEqual(len(env["self_history"]), 5)
        self.assertEqual(env["self_history"][0]["utterance_summary"], "reply_7")

    def test_self_history_explicit_limit_override(self):
        db = _fresh_db("sh_override")
        for i in range(6):
            _write(db, "model_reply", f"r{i}", **_MR_KW)
            time.sleep(0.002)
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=[], signals_absent=[], tool_results=[],
            self_history_limit=2,
        )
        self.assertEqual(len(env["self_history"]), 2)


class MissingDBTests(unittest.TestCase):
    def test_missing_db_path_returns_empty_self_history(self):
        # Builder must not crash when the ledger isn't reachable —
        # generation-time grounding is best-effort. Empty self_history,
        # rest of envelope still well-shaped.
        env = envelope_builder.build_envelope(
            ledger_db_path=None,
            signals_present=["ok"], signals_absent=[],
            tool_results=[{"tool": "x"}],
        )
        self.assertEqual(env["self_history"], [])
        self.assertEqual(env["signals_present"], ["ok"])
        envelope_schema.validate_envelope(env)

    def test_uninitialized_ledger_returns_empty_self_history_without_noise(self):
        # Production memory/ledger.db can exist before ledger writes are
        # authorized. A zero-table SQLite file means "self_history is not
        # live yet", not an operator-actionable schema failure on every turn.
        path = Path(_TEST_DB_DIR) / f"empty_ledger_{os.urandom(4).hex()}.db"
        path.touch()

        with self.assertNoLogs("maez.envelope", level="DEBUG"):
            env = envelope_builder.build_envelope(
                ledger_db_path=str(path),
                signals_present=["ok"],
                signals_absent=[],
                tool_results=[],
            )

        self.assertEqual(env["self_history"], [])
        self.assertEqual(env["signals_present"], ["ok"])
        envelope_schema.validate_envelope(env)


class PassthroughTests(unittest.TestCase):
    def test_tool_results_passthrough(self):
        db = _fresh_db("pt_tools")
        tools = [
            {"name": "ls", "status": "ok", "summary": "file1.txt"},
            {"name": "cat", "status": "error",
             "summary": "no such file"},
        ]
        env = envelope_builder.build_envelope(
            ledger_db_path=db, signals_present=[], signals_absent=[],
            tool_results=tools,
        )
        # Builder normalizes — entries shaped to memo §5 keys
        # (name/status/tool_call_id/summary), other keys dropped.
        self.assertEqual(len(env["tool_results"]), 2)
        self.assertEqual(env["tool_results"][0]["name"], "ls")
        self.assertEqual(env["tool_results"][0]["status"], "ok")
        self.assertEqual(env["tool_results"][1]["name"], "cat")

    def test_action_receipt_fields_survive_tool_result_normalization(self):
        db = _fresh_db("pt_action_receipts")
        env = envelope_builder.build_envelope(
            ledger_db_path=db,
            signals_present=[],
            signals_absent=[],
            tool_results=[
                {
                    "name": "web_search",
                    "tool": "web_search",
                    "action_type": "web_search",
                    "status": "ok",
                    "summary": "web_search ok result_count=2 backend=web",
                    "query": "private owner wording should not survive",
                },
            ],
        )

        tr = env["tool_results"][0]
        self.assertEqual(tr["name"], "web_search")
        self.assertEqual(tr["tool"], "web_search")
        self.assertEqual(tr["action_type"], "web_search")
        self.assertEqual(tr["status"], "ok")
        self.assertEqual(tr["summary"], "web_search ok result_count=2 backend=web")
        self.assertNotIn("query", tr)

    def test_claimable_forbidden_passthrough(self):
        db = _fresh_db("pt_cf")
        env = envelope_builder.build_envelope(
            ledger_db_path=db, signals_present=[], signals_absent=[],
            tool_results=[],
            claimable=[{"text": "x"}],
            forbidden=[{"text": "y"}],
        )
        self.assertEqual(env["claimable"], [{"text": "x"}])
        self.assertEqual(env["forbidden"], [{"text": "y"}])


if __name__ == "__main__":
    unittest.main()
