# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Surface wiring — web and the CLI ride the admission spool.

Council rulings 2026-08-24 (four seats): non-owner surfaces never open
the ledger. Their user_message and model_reply writes become durable
spool envelopes (``spool.enqueue``); the daemon owner drains. Parent
linkage moves to ``parent_submission_id`` — the synchronous
``parent_turn_id`` threading (wait for a turn_id, hand it to the reply)
dies with this slice, because the reply path must never block on the
ledger. In-daemon producers (Telegram, handle_message) do NOT ride the
spool (Grok overturn): their persist path stays owner_write_turn with
synchronous parent_turn_id.

Dormancy is exact: with MAEZ_LEDGER_WRITES unset the surface helpers
leave NO trace — no spool file, no directory, no SQLite open. Pre-birth
conversations must not pile into the spool and drain into the ledger at
birth as pre-birth life (birth-gated activation).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DIR = tempfile.mkdtemp(prefix="maez_test_surface_spool_")
_REPO = Path("/home/rohit/maez")

from core.ledger import migrate, spool  # noqa: E402
from core.ledger import model_reply_persistence as mrp  # noqa: E402
from core.ledger import owner as ledger_owner  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


def _fresh(name: str) -> str:
    """A migrated ledger in its own memory-dir; spool root sits beside it."""
    base = Path(_TEST_DIR) / f"{name}_{os.urandom(4).hex()}"
    base.mkdir()
    db = str(base / "ledger.db")
    migrate.run(db)
    return db


def _spool_root(db: str) -> Path:
    return Path(db).parent / "ledger_spool"


def _turns(db: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM turns WHERE chain_position > 0"
            " ORDER BY chain_position"
        ).fetchall()
    finally:
        conn.close()


def _read(rel: str) -> str:
    return (_REPO / rel).read_text()


def _method_body(src: str, name: str) -> str:
    start = src.find(f"def {name}")
    if start == -1:
        raise AssertionError(f"{name} not found")
    match = re.search(r"\n    def ", src[start + 20:])
    end = start + 20 + match.start() if match else len(src)
    return src[start:end]


_REPLY_ARGS = dict(
    raw_text="Maez answers after audit",
    surface="web_owner",
    model_id="test-model",
    prompt_material={"messages": ["owner asks"]},
    soul_material="test soul",
    evidence_envelope={"claimable": [], "forbidden": []},
    audit_verdict={"verdict": "post_audit"},
)


class SpoolRootTests(unittest.TestCase):
    def test_default_spool_root_sits_beside_the_ledger(self):
        self.assertEqual(
            spool.default_spool_root("/some/memory/ledger.db"),
            "/some/memory/ledger_spool",
            "units only write under memory/ — the spool lives beside the db",
        )


class SubmitUserMessageTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()

    def tearDown(self):
        ledger_owner._reset_for_tests()

    def test_enabled_nonowner_enqueues_and_never_touches_the_ledger(self):
        db = _fresh("usermsg")
        before = Path(db).stat().st_mtime_ns
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            sid = mrp.submit_user_message(db, "hello", surface="web_owner")
        self.assertIsNotNone(sid)
        env_path = _spool_root(db) / "web_owner" / "pending" / f"{sid}.json"
        self.assertTrue(env_path.exists())
        env = json.loads(env_path.read_text())
        self.assertEqual(env["turn_kind"], "user_message")
        self.assertEqual(env["raw_text"], "hello")
        self.assertEqual(env["kwargs"]["surface"], "web_owner")
        self.assertEqual(env["kwargs"]["taint_labels"], ["owner_utterance"])
        self.assertEqual(env["kwargs"]["privacy_access"], "public")
        self.assertEqual(len(_turns(db)), 0, "no direct ledger write")
        self.assertEqual(
            Path(db).stat().st_mtime_ns, before,
            "the surface must not open the ledger for writing",
        )

    def test_flag_dormant_leaves_no_filesystem_trace(self):
        db = _fresh("dormant")
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        with patch.dict(os.environ, env, clear=True):
            sid = mrp.submit_user_message(db, "pre-birth", surface="cli")
        self.assertIsNone(sid)
        self.assertFalse(
            _spool_root(db).exists(),
            "flag-dormant means NO spool residue — pre-birth turns must not "
            "pile up and drain into the ledger at birth",
        )

    def test_never_raises_on_unwritable_spool(self):
        db = _fresh("unwritable")
        root = _spool_root(db)
        root.mkdir()
        os.chmod(root, 0o500)
        try:
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                sid = mrp.submit_user_message(db, "hi", surface="web_owner")
        finally:
            os.chmod(root, 0o700)
        self.assertIsNone(sid, "reply path must survive spool I/O failure")


class PersistModelReplyNonOwnerTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()

    def tearDown(self):
        ledger_owner._reset_for_tests()

    def test_nonowner_enqueues_reply_with_parent_submission_id(self):
        db = _fresh("reply")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            parent_sid = mrp.submit_user_message(
                db, "owner asks", surface="web_owner",
            )
            tid = mrp.persist_model_reply(
                db_path=db,
                parent_submission_id=parent_sid,
                **_REPLY_ARGS,
            )
        self.assertIsNone(tid, "non-owner path returns no turn_id — the "
                               "commit happens at drain, not at the surface")
        pending = _spool_root(db) / "web_owner" / "pending"
        envs = {
            p.name: json.loads(p.read_text())
            for p in pending.iterdir() if not p.name.startswith(".tmp-")
        }
        replies = [e for e in envs.values() if e["turn_kind"] == "model_reply"]
        self.assertEqual(len(replies), 1)
        reply = replies[0]
        self.assertEqual(reply["parent_submission_id"], parent_sid)
        self.assertEqual(reply["kwargs"]["surface"], "web_owner")
        self.assertIn("prompt_hash", reply["kwargs"])
        self.assertIn("soul_hash", reply["kwargs"])
        self.assertIn("audit_verdict", reply["kwargs"])
        self.assertNotIn(
            "parent_turn_id", reply["kwargs"],
            "parent linkage is parent_submission_id only — a turn_id in the "
            "envelope would be refused at the admission door",
        )
        self.assertNotIn("meta_marker_keys", reply["kwargs"])
        self.assertEqual(len(_turns(db)), 0, "no direct write, no marker")

    def test_nonowner_path_never_opens_sqlite(self):
        """db need not even exist: the spool is pure filesystem custody."""
        base = Path(_TEST_DIR) / f"nodb_{os.urandom(4).hex()}"
        base.mkdir()
        db = str(base / "ledger.db")  # never created — 0-byte unborn world
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            mrp.persist_model_reply(
                db_path=db, parent_submission_id=None, **_REPLY_ARGS,
            )
        self.assertFalse(Path(db).exists(),
                         "the non-owner path must not create the ledger")
        pending = _spool_root(db) / "web_owner" / "pending"
        self.assertEqual(
            len([p for p in pending.iterdir()
                 if not p.name.startswith(".tmp-")]), 1,
        )

    def test_flag_dormant_reply_leaves_no_trace(self):
        db = _fresh("replydormant")
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        with patch.dict(os.environ, env, clear=True):
            tid = mrp.persist_model_reply(
                db_path=db, parent_submission_id=None, **_REPLY_ARGS,
            )
        self.assertIsNone(tid)
        self.assertFalse(_spool_root(db).exists())
        self.assertEqual(len(_turns(db)), 0)

    def test_owner_path_still_writes_direct_with_no_spool(self):
        """Grok overturn guard: in-owner producers do NOT ride the spool."""
        db = _fresh("ownerdirect")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            parent = mrp.write_user_message_for_test(
                db, "owner asks", surface="telegram_text",
            )
            tid = mrp.persist_model_reply(
                db_path=db,
                parent_turn_id=parent,
                **{**_REPLY_ARGS, "surface": "telegram_text"},
            )
        self.assertIsNotNone(tid)
        rows = [r for r in _turns(db) if r["turn_kind"] == "model_reply"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["parent_turn_id"], parent)
        self.assertFalse(
            _spool_root(db).exists(),
            "an owner write must not leave spool residue",
        )


class SurfaceConversationDrainTests(unittest.TestCase):
    """The full admission shape: surface enqueues both turns, the owner
    drains, and the conversation edge (reply → user turn) is real."""

    def setUp(self):
        ledger_owner._reset_for_tests()

    def tearDown(self):
        ledger_owner._reset_for_tests()

    def test_user_message_then_reply_drain_parent_before_child(self):
        db = _fresh("conversation")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            parent_sid = mrp.submit_user_message(
                db, "owner asks", surface="web_owner",
            )
            mrp.persist_model_reply(
                db_path=db, parent_submission_id=parent_sid, **_REPLY_ARGS,
            )
            ledger_owner.claim_ownership()
            report = spool.drain_once(str(_spool_root(db)), db)
        self.assertEqual(report["acked"], 2)
        rows = _turns(db)
        by_kind = {r["turn_kind"]: r for r in rows}
        self.assertEqual(
            by_kind["model_reply"]["parent_turn_id"],
            by_kind["user_message"]["turn_id"],
            "the drained conversation edge must be real, not a drain artifact",
        )
        self.assertEqual(by_kind["user_message"]["submission_id"], parent_sid)


class WebWiringTests(unittest.TestCase):
    """The web chat handler must ride the spool, not try_write_turn."""

    def test_web_user_message_enqueues_instead_of_direct_write(self):
        body = _method_body(_read("skills/web_interface.py"), "chat")
        self.assertNotIn(
            "try_write_turn", body,
            "web is a non-owner surface: its ledger writes go through the "
            "admission spool, never a direct writer",
        )
        self.assertIn("submit_user_message(", body)
        self.assertIn('surface="web_owner"', body)

    def test_web_reply_links_by_parent_submission_id(self):
        body = _method_body(_read("skills/web_interface.py"), "chat")
        persist_idx = body.find("persist_model_reply(")
        self.assertGreater(persist_idx, 0)
        window = body[persist_idx:persist_idx + 900]
        self.assertIn(
            "parent_submission_id=_owner_user_msg_submission_id", window,
        )
        self.assertNotIn(
            "parent_turn_id", body,
            "synchronous parent_turn_id threading dies with this slice",
        )


class CliWiringTests(unittest.TestCase):
    """The CLI is a non-owner surface too — same shape as web."""

    def test_cli_user_message_enqueues_instead_of_direct_write(self):
        body = _method_body(_read("cli/maez_chat.py"), "_handle_chat")
        self.assertNotIn("try_write_turn", body)
        self.assertIn("submit_user_message(", body)

    def test_cli_reply_links_by_parent_submission_id(self):
        body = _method_body(_read("cli/maez_chat.py"), "_handle_chat")
        persist_idx = body.find("persist_model_reply(")
        self.assertGreater(persist_idx, 0)
        window = body[persist_idx:persist_idx + 900]
        self.assertIn(
            "parent_submission_id=_cli_user_msg_submission_id", window,
        )
        self.assertNotIn("parent_turn_id", body)


class FailedClaimUnclaimsTests(unittest.TestCase):
    """Codex validation CRITICAL #1: claim_ownership set the PID marker
    BEFORE constructing the latch-holding writer; on eager failure the
    daemon catches and continues, leaving this_process_is_owner() true
    while another process holds the latch — so replies take the
    owner-direct branch and dead-letter instead of spooling."""

    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)

    def test_failed_eager_claim_does_not_leave_owner_marker(self):
        import fcntl

        db = _fresh("claimfail")
        fd = os.open(f"{os.path.abspath(db)}.ownerlock",
                     os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                with self.assertRaises(Exception):
                    ledger_owner.claim_ownership(db)
                self.assertFalse(
                    ledger_owner.this_process_is_owner(),
                    "a failed latch claim must not leave this process "
                    "believing it is the owner — surfaces would route "
                    "owner-direct and dead-letter instead of spooling",
                )
        finally:
            os.close(fd)


class InDaemonProducersUnchangedTests(unittest.TestCase):
    """Grok overturn: the daemon and in-daemon Telegram keep synchronous
    owner writes — routing them through the spool is structurally wrong
    (a second durability domain inside the process that holds the latch)."""

    def test_daemon_handle_message_keeps_parent_turn_id(self):
        body = _method_body(_read("daemon/maez_daemon.py"), "handle_message")
        self.assertIn("parent_turn_id=_user_msg_turn_id", body)

    def test_telegram_voice_keeps_parent_turn_id(self):
        body = _method_body(_read("skills/telegram_voice.py"),
                            "_process_message")
        self.assertIn("parent_turn_id=_telegram_user_msg_turn_id", body)


if __name__ == "__main__":
    unittest.main()
