# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Admission spool — the council-ruled transport for NON-OWNER surfaces.

Web and the CLI never touch SQLite: they publish one immutable envelope
per submission into their own spool dir (temp write → fsync → atomic
rename → dir fsync; filename = client-minted submission_id = the schema
UNIQUE key). The daemon owner drains: dependency-aware
(parent-before-child via parent_submission_id), commit under the UNIQUE
constraint, ack by chain-bound receipt + rename to acked/, refusals to
refused/ quarantine. Crash anywhere → redrive resolves by DB membership
(idempotent commit-by-identity), never duplicates, never silently drops.

Authority is structurally inexpressible: an envelope naming
birth_anchor / meta_marker_keys / lifecycle_stage / submission overrides
is refused at the admission door — the file is never trusted.

Grok seat overturn (2026-08-24): in-daemon producers do NOT ride this;
they stay on owner_write_turn.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DIR = tempfile.mkdtemp(prefix="maez_test_spool_")

from core.ledger import migrate, spool  # noqa: E402
from core.ledger import owner as ledger_owner  # noqa: E402

_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


def _fresh(name: str) -> tuple[str, str]:
    base = Path(_TEST_DIR) / f"{name}_{os.urandom(4).hex()}"
    base.mkdir()
    db = str(base / "ledger.db")
    migrate.run(db)
    return db, str(base / "spool")


def _turns(db: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM turns WHERE chain_position > 0"
            " ORDER BY chain_position"
        ).fetchall()
    finally:
        conn.close()


class SpoolTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()

    def tearDown(self):
        ledger_owner._reset_for_tests()

    # ------------------------------------------------------------ enqueue

    def test_enqueue_publishes_one_complete_envelope(self):
        db, root = _fresh("enq")
        sid = spool.enqueue(
            root, producer="web", turn_kind="user_message",
            raw_text="hello from web", kwargs={"surface": "web_owner", **_STAMP},
        )
        pending = list((Path(root) / "web" / "pending").iterdir())
        self.assertEqual(len(pending), 1, "exactly one file, no temp residue")
        self.assertEqual(pending[0].name, f"{sid}.json")
        env = json.loads(pending[0].read_text())
        self.assertEqual(env["submission_id"], sid)
        self.assertEqual(env["raw_text"], "hello from web")
        self.assertIn("submitted_at", env)
        self.assertIn("payload_digest", env)

    # -------------------------------------------------------------- drain

    def test_drain_commits_acks_with_chain_bound_receipt(self):
        db, root = _fresh("drain")
        sid = spool.enqueue(
            root, producer="web", turn_kind="user_message",
            raw_text="a life event", kwargs={"surface": "web_owner", **_STAMP},
        )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            report = spool.drain_once(root, db)
        self.assertEqual(report["acked"], 1)
        rows = _turns(db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["submission_id"], sid)
        self.assertEqual(rows[0]["raw_text"], "a life event")
        acked_dir = Path(root) / "web" / "acked"
        self.assertTrue((acked_dir / f"{sid}.json").exists())
        receipt = json.loads((acked_dir / f"{sid}.receipt.json").read_text())
        self.assertEqual(receipt["turn_id"], rows[0]["turn_id"])
        self.assertEqual(receipt["chain_position"], rows[0]["chain_position"])
        self.assertEqual(receipt["chain_hash"], rows[0]["chain_hash"])
        self.assertEqual(
            list((Path(root) / "web" / "pending").iterdir()), [],
            "pending must be empty after ack",
        )

    def test_redrive_after_crash_is_idempotent(self):
        db, root = _fresh("redrive")
        sid = spool.enqueue(
            root, producer="cli", turn_kind="user_message",
            raw_text="once only", kwargs={"surface": "cli", **_STAMP},
        )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            spool.drain_once(root, db)
            # Simulate a crash between COMMIT and ack: the envelope is
            # back in pending/ as if the rename never happened.
            acked = Path(root) / "cli" / "acked" / f"{sid}.json"
            pending = Path(root) / "cli" / "pending" / f"{sid}.json"
            pending.write_text(acked.read_text())
            report = spool.drain_once(root, db)
        self.assertEqual(report["acked"], 1, "redrive resolves, not errors")
        self.assertEqual(len(_turns(db)), 1, "and never duplicates the row")

    def test_parent_before_child_even_when_enqueued_backwards(self):
        db, root = _fresh("deps")
        child_sid = spool.enqueue(
            root, producer="web", turn_kind="user_message",
            raw_text="child turn", kwargs={"surface": "web_owner", **_STAMP},
            parent_submission_id="PLACEHOLDER",
        )
        parent_sid = spool.enqueue(
            root, producer="web", turn_kind="user_message",
            raw_text="parent turn", kwargs={"surface": "web_owner", **_STAMP},
        )
        # Rewrite the child's parent pointer to the real parent id (the
        # test enqueued child first to prove order independence).
        child_path = Path(root) / "web" / "pending" / f"{child_sid}.json"
        env = json.loads(child_path.read_text())
        env["parent_submission_id"] = parent_sid
        child_path.write_text(json.dumps(env))
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            report = spool.drain_once(root, db)
        self.assertEqual(report["acked"], 2)
        rows = _turns(db)
        by_sid = {r["submission_id"]: r for r in rows}
        self.assertEqual(
            by_sid[child_sid]["parent_turn_id"],
            by_sid[parent_sid]["turn_id"],
            "the child must commit AFTER its parent and reference its "
            "real turn_id — conversation edges are life, not drain "
            "artifacts",
        )
        self.assertLess(
            by_sid[parent_sid]["chain_position"],
            by_sid[child_sid]["chain_position"],
        )

    def test_orphan_child_stays_pending(self):
        db, root = _fresh("orphan")
        sid = spool.enqueue(
            root, producer="web", turn_kind="user_message",
            raw_text="orphan", kwargs={"surface": "web_owner", **_STAMP},
            parent_submission_id="never-arrives",
        )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            report = spool.drain_once(root, db)
        self.assertEqual(report["acked"], 0)
        self.assertEqual(report["deferred"], 1)
        self.assertTrue(
            (Path(root) / "web" / "pending" / f"{sid}.json").exists(),
            "an orphan is deferred loudly, never dropped and never "
            "committed with a fabricated parent",
        )

    # ----------------------------------------------------------- refusals

    def test_authority_fields_are_refused_at_the_door(self):
        db, root = _fresh("authority")
        sid = spool.enqueue(
            root, producer="web", turn_kind="system_event",
            raw_text="sneaky birth",
            kwargs={"surface": "web_owner", "birth_anchor": True, **_STAMP},
        )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            report = spool.drain_once(root, db)
        self.assertEqual(report["refused"], 1)
        self.assertEqual(len(_turns(db)), 0)
        refused = Path(root) / "web" / "refused" / f"{sid}.json"
        self.assertTrue(refused.exists())
        err = json.loads(
            (refused.parent / f"{sid}.error.json").read_text()
        )
        self.assertIn("authority", err["error"].lower())

    def test_invalid_payload_is_quarantined_not_retried(self):
        db, root = _fresh("invalid")
        sid = spool.enqueue(
            root, producer="web", turn_kind="model_reply",
            raw_text="missing required fields",
            kwargs={"surface": "web_owner",
                    "taint_labels": ["self_generated"],
                    "privacy_access": "public"},
        )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            report = spool.drain_once(root, db)
            second = spool.drain_once(root, db)
        self.assertEqual(report["refused"], 1)
        self.assertEqual(second["refused"], 0, "quarantine is terminal")
        self.assertTrue(
            (Path(root) / "web" / "refused" / f"{sid}.json").exists()
        )

    def test_unparseable_file_is_quarantined(self):
        db, root = _fresh("garbage")
        pending = Path(root) / "web" / "pending"
        pending.mkdir(parents=True)
        (pending / "not-json.json").write_text("{torn")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            report = spool.drain_once(root, db)
        self.assertEqual(report["refused"], 1)
        self.assertFalse((pending / "not-json.json").exists())

    # ------------------------------------------------------------ dormancy

    def test_drain_with_writes_disabled_is_a_no_op(self):
        db, root = _fresh("dormant")
        sid = spool.enqueue(
            root, producer="web", turn_kind="user_message",
            raw_text="waits for birth", kwargs={"surface": "web_owner", **_STAMP},
        )
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        with patch.dict(os.environ, env, clear=True):
            report = spool.drain_once(root, db)
        self.assertEqual(report, {"acked": 0, "refused": 0, "deferred": 0,
                                  "skipped_disabled": True})
        self.assertTrue(
            (Path(root) / "web" / "pending" / f"{sid}.json").exists(),
            "dormant drain must move nothing",
        )
        self.assertEqual(len(_turns(db)), 0)


class DrainerLoopTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()

    def tearDown(self):
        ledger_owner._reset_for_tests()

    def test_run_drainer_drains_and_stops(self):
        import threading
        import time as _time

        db, root = _fresh("loop")
        sid = spool.enqueue(
            root, producer="web", turn_kind="user_message",
            raw_text="looped", kwargs={"surface": "web_owner", **_STAMP},
        )
        stop = threading.Event()
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            t = threading.Thread(
                target=spool.run_drainer, args=(root, db, stop, 0.05),
            )
            t.start()
            deadline = _time.monotonic() + 10
            try:
                while _time.monotonic() < deadline:
                    if (Path(root) / "web" / "acked" / f"{sid}.json").exists():
                        break
                    _time.sleep(0.02)
            finally:
                stop.set()
                t.join(timeout=10)
        self.assertFalse(t.is_alive())
        self.assertEqual(len(_turns(db)), 1)

    def test_spool_status_reports_pending(self):
        db, root = _fresh("status")
        spool.enqueue(
            root, producer="cli", turn_kind="user_message",
            raw_text="waiting", kwargs={"surface": "cli", **_STAMP},
        )
        status = spool.spool_status(root)
        self.assertEqual(status["pending_total"], 1)
        self.assertEqual(status["producers"]["cli"]["pending"], 1)
        self.assertIsNotNone(status["oldest_pending_ts"])


if __name__ == "__main__":
    unittest.main()
