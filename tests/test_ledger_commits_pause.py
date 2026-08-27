# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""MAEZ_LEDGER_COMMITS_PAUSED — pause-with-custody (owner ruling 2026-08-26,
ninth council round, 3-0 on shape; junk polarity 2-1).

Pause stops COMMITS while custody continues: surfaces keep enqueueing,
the drainer refuses to touch anything, and the OWNER PROCESS BECOMES A
SPOOL PRODUCER — its writes neither commit, nor dead-letter (that would
manufacture replay debt), nor silently vanish. MAEZ_LEDGER_WRITES off
always wins: pause can never reopen pre-birth custody. This suspends
(never repeals) round-5 Overturn 1 — the owner-direct exception assumes
synchronous threading, which a paused ledger definitionally lacks."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DIR = tempfile.mkdtemp(prefix="maez_test_pause_")

from core.ledger import migrate, spool  # noqa: E402
from core.ledger import owner as ledger_owner  # noqa: E402
from core.ledger.writes_flag import ledger_commits_paused  # noqa: E402

_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}
_ON = {"MAEZ_LEDGER_WRITES": "1"}
_PAUSED = {"MAEZ_LEDGER_WRITES": "1", "MAEZ_LEDGER_COMMITS_PAUSED": "1"}


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


def _fresh(name: str) -> str:
    base = Path(_TEST_DIR) / f"{name}_{os.urandom(4).hex()}"
    base.mkdir()
    db = str(base / "ledger.db")
    migrate.run(db)
    return db


def _turns(db: str):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM turns WHERE chain_position > 0"
            " ORDER BY chain_position").fetchall()
    finally:
        conn.close()


class PredicateTests(unittest.TestCase):
    def test_absent_and_false_mean_not_paused(self):
        for env in ({}, {"MAEZ_LEDGER_COMMITS_PAUSED": "0"},
                    {"MAEZ_LEDGER_COMMITS_PAUSED": "false"}):
            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("MAEZ_LEDGER_COMMITS_PAUSED", None) if not env else None
                if env:
                    self.assertFalse(ledger_commits_paused())
        os.environ.pop("MAEZ_LEDGER_COMMITS_PAUSED", None)
        self.assertFalse(ledger_commits_paused())

    def test_junk_fails_closed_to_paused(self):
        """2-1 (Codex+Claude over Grok): junk never authorizes an
        irreversible commit; pause is reversible, commits are not."""
        with patch.dict(os.environ, {"MAEZ_LEDGER_COMMITS_PAUSED": "banana"}):
            self.assertTrue(ledger_commits_paused())

    def test_explicit_true_pauses(self):
        with patch.dict(os.environ, {"MAEZ_LEDGER_COMMITS_PAUSED": "1"}):
            self.assertTrue(ledger_commits_paused())


class PausedDrainTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)

    def test_paused_drain_touches_nothing(self):
        db = _fresh("draingate")
        root = spool.default_spool_root(db)
        sid = spool.enqueue(root, producer="web", turn_kind="user_message",
                            raw_text="waits", kwargs={"surface": "web_owner", **_STAMP})
        with patch.dict(os.environ, _PAUSED):
            ledger_owner.claim_ownership()
            report = spool.drain_once(root, db)
        self.assertTrue(report.get("skipped_paused"),
                        "paused drain must say so distinctly")
        self.assertTrue((Path(root) / "web" / "pending" / f"{sid}.json").exists())
        self.assertEqual(len(_turns(db)), 0)


class PausedOwnerWriteTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)

    def test_paused_owner_write_becomes_custody_not_commit(self):
        db = _fresh("ownercustody")
        with patch.dict(os.environ, _PAUSED):
            ledger_owner.claim_ownership()
            out = ledger_owner.owner_write_turn(
                db, "user_message", "held life", surface="telegram_text", **_STAMP)
        self.assertIsNone(out, "caller contract: turn_id or None, never a sid")
        self.assertEqual(len(_turns(db)), 0, "no commit under pause")
        self.assertEqual(
            len(list(Path(db).parent.glob("*.deadletter.*.jsonl"))), 0,
            "pause is not a failure; dead-lettering manufactures replay debt")
        pending = Path(spool.default_spool_root(db)) / "owner_daemon" / "pending"
        envs = [json.loads(p.read_text()) for p in pending.iterdir()
                if not p.name.startswith(".tmp-")]
        self.assertEqual(len(envs), 1)
        self.assertEqual(envs[0]["raw_text"], "held life")

    def test_caller_held_parent_turn_id_is_translated(self):
        """A parent committed PRE-pause: its turn_id is reverse-looked-up
        to its submission_id (7b7acb2 identity) — passing parent_turn_id
        through the door would self-quarantine."""
        db = _fresh("translate")
        with patch.dict(os.environ, _ON):
            ledger_owner.claim_ownership()
            parent_tid = ledger_owner.owner_write_turn(
                db, "user_message", "pre-pause parent",
                surface="telegram_text", **_STAMP)
        self.assertIsNotNone(parent_tid)
        with patch.dict(os.environ, _PAUSED):
            ledger_owner.owner_write_turn(
                db, "model_reply", "paused reply", surface="telegram_text",
                parent_turn_id=parent_tid, model_id="m",
                prompt_hash="p" * 64, soul_hash="s" * 64,
                evidence_envelope={"claimable": [], "forbidden": []},
                audit_verdict={"verdict": "ok"},
                taint_labels=["self_generated"], privacy_access="public")
        pending = Path(spool.default_spool_root(db)) / "owner_daemon" / "pending"
        env = [json.loads(p.read_text()) for p in pending.iterdir()
               if not p.name.startswith(".tmp-")][0]
        parent_row = [r for r in _turns(db) if r["turn_id"] == parent_tid][0]
        self.assertEqual(env["parent_submission_id"], parent_row["submission_id"])
        self.assertNotIn("parent_turn_id", env["kwargs"])
        # resume: drain commits with the REAL edge
        with patch.dict(os.environ, _ON):
            report = spool.drain_once(spool.default_spool_root(db), db)
        self.assertEqual(report["acked"], 1)
        reply = [r for r in _turns(db) if r["turn_kind"] == "model_reply"][0]
        self.assertEqual(reply["parent_turn_id"], parent_tid)

    def test_writes_off_wins_no_custody(self):
        db = _fresh("offwins")
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        env["MAEZ_LEDGER_COMMITS_PAUSED"] = "1"
        with patch.dict(os.environ, env, clear=True):
            ledger_owner.claim_ownership()
            out = ledger_owner.owner_write_turn(
                db, "user_message", "pre-birth", surface="cli", **_STAMP)
        self.assertIsNone(out)
        self.assertFalse(Path(spool.default_spool_root(db)).exists(),
                         "pause must never reopen pre-birth custody")


class ResumeExactlyOnceTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)

    def test_pause_resume_exactly_once(self):
        db = _fresh("resume")
        root = spool.default_spool_root(db)
        with patch.dict(os.environ, _PAUSED):
            ledger_owner.claim_ownership()
            for i in range(4):
                ledger_owner.owner_write_turn(
                    db, "user_message", f"held {i}", surface="telegram_text", **_STAMP)
            self.assertEqual(len(_turns(db)), 0)
        with patch.dict(os.environ, _ON):
            r1 = spool.drain_once(root, db)
            r2 = spool.drain_once(root, db)
        self.assertEqual(r1["acked"], 4)
        self.assertEqual(r2["acked"], 0, "second drain has nothing — UNIQUE holds")
        self.assertEqual(len(_turns(db)), 4)


if __name__ == "__main__":
    unittest.main()
