# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 4c.5a — owner-private model_reply persistence.

This slice is autobiographical continuity turning on: owner-private
assistant replies begin landing in the append-only ledger as model_reply
rows, after audit and before user-facing storage/return. Public surfaces
must stay outside the owner ledger.
"""
from __future__ import annotations

import json
import importlib
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ["MAEZ_TEST_MODE"] = "1"
_REPO = Path("/home/rohit/maez")
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_model_reply_persistence_")


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _read(rel: str) -> str:
    return (_REPO / rel).read_text()


def _method_body(src: str, name: str) -> str:
    start = src.find(f"def {name}")
    if start == -1:
        raise AssertionError(f"{name} not found")
    match = re.search(r"\n    def ", src[start + 20:])
    end = start + 20 + match.start() if match else len(src)
    return src[start:end]


def _fresh_db(name: str) -> str:
    from core.ledger import migrate

    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


class ModelReplyPersistenceHelperTests(unittest.TestCase):
    def test_helper_writes_discontinuity_marker_once_and_parented_reply(self):
        try:
            mod = importlib.import_module("core.ledger.model_reply_persistence")
        except ModuleNotFoundError:
            self.fail(
                "core.ledger.model_reply_persistence must provide the shared "
                "owner-private model_reply persistence helper"
            )
        persist_model_reply = mod.persist_model_reply

        db = _fresh_db("helper")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            parent = mod.write_user_message_for_test(
                db, "owner asks", surface="telegram_text",
            )
            reply1 = persist_model_reply(
                db_path=db,
                raw_text="Maez answers after audit",
                surface="telegram_text",
                parent_turn_id=parent,
                model_id="test-model",
                prompt_material={"messages": ["owner asks"]},
                soul_material="test soul",
                evidence_envelope={"claimable": [], "forbidden": []},
                audit_verdict={"verdict": "post_audit"},
            )
            reply2 = persist_model_reply(
                db_path=db,
                raw_text="Maez answers again",
                surface="telegram_text",
                parent_turn_id=parent,
                model_id="test-model",
                prompt_material={"messages": ["owner asks again"]},
                soul_material="test soul",
                evidence_envelope={"claimable": [], "forbidden": []},
                audit_verdict={"verdict": "post_audit"},
            )

        self.assertIsNotNone(reply1)
        self.assertIsNotNone(reply2)
        conn = sqlite3.connect(db)
        try:
            rows = conn.execute(
                "SELECT turn_kind, raw_text, surface, parent_turn_id "
                "FROM turns WHERE turn_kind IN ('system_event', 'model_reply') "
                "ORDER BY timestamp ASC"
            ).fetchall()
        finally:
            conn.close()

        markers = [
            r for r in rows
            if r[0] == "system_event"
            and "model_reply_persistence_introduced" in r[1]
        ]
        replies = [r for r in rows if r[0] == "model_reply"]
        self.assertEqual(len(markers), 1)
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[0][2], "telegram_text")
        self.assertEqual(replies[0][3], parent)

        marker_payload = json.loads(markers[0][1])
        self.assertIn("autobiographical continuity turning on",
                      marker_payload["plain_english"])

    def test_helper_skips_model_reply_when_evidence_envelope_unavailable(self):
        mod = importlib.import_module("core.ledger.model_reply_persistence")
        db = _fresh_db("no_envelope")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = mod.persist_model_reply(
                db_path=db,
                raw_text="reply without envelope",
                surface="telegram_text",
                parent_turn_id=None,
                model_id="test-model",
                prompt_material={"messages": []},
                soul_material="test soul",
                evidence_envelope=None,
                audit_verdict={"verdict": "post_audit"},
            )
        self.assertIsNone(tid)
        conn = sqlite3.connect(db)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM turns WHERE turn_kind='model_reply'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 0)

    def test_helper_canonicalizes_audit_verdict_shape(self):
        mod = importlib.import_module("core.ledger.model_reply_persistence")
        if not hasattr(mod, "build_model_reply_audit_verdict"):
            self.fail(
                "model_reply persistence must expose a shared audit verdict "
                "builder so surface metadata does not fork by caller"
            )

        verdict = mod.build_model_reply_audit_verdict(
            surface="cli",
            audit_ran=True,
            changed_output=False,
            surface_meta={"mode": "noop"},
        )

        self.assertEqual(
            set(verdict),
            {
                "verdict",
                "audit_ran",
                "changed_output",
                "surface",
                "event",
                "surface_meta",
            },
        )
        self.assertEqual(verdict["event"], "autobiographical_continuity_turning_on")
        self.assertEqual(verdict["surface_meta"], {"mode": "noop"})


class DaemonModelReplyPersistenceWiringTests(unittest.TestCase):
    def test_handle_message_persists_model_reply_after_audit_before_memory_store(self):
        body = _method_body(_read("daemon/maez_daemon.py"), "handle_message")
        audit_idx = body.find("reply = audit_assistant_text(")
        persist_idx = body.find("persist_model_reply(")
        store_idx = body.find("self.memory.store_telegram(")

        self.assertGreater(audit_idx, 0)
        self.assertGreater(persist_idx, audit_idx)
        self.assertGreater(store_idx, persist_idx)

        window = body[persist_idx:persist_idx + 700]
        self.assertIn('if getattr(_trace.audit, "ran", False):',
                      body[persist_idx - 250:persist_idx])
        self.assertIn("parent_turn_id=_user_msg_turn_id", window)
        self.assertIn("surface=source", window)
        self.assertIn("evidence_envelope=_evidence_envelope", window)
        self.assertIn('"autobiographical_continuity_turning_on"', window)
        self.assertIn("build_model_reply_audit_verdict", window)

    def test_outer_fail_open_uses_warn_once_not_debug(self):
        body = _method_body(_read("daemon/maez_daemon.py"), "handle_message")
        persist_idx = body.find("persist_model_reply(")
        self.assertGreater(persist_idx, 0)
        after = body[persist_idx:persist_idx + 1200]

        self.assertIn("warn_model_reply_persistence_skip", after)
        self.assertNotIn("logger.debug", after)


class WebModelReplyPersistenceWiringTests(unittest.TestCase):
    def test_owner_bridge_persists_model_reply_and_public_path_does_not(self):
        body = _method_body(_read("skills/web_interface.py"), "chat")
        audit_idx = body.find("reply = audit_assistant_text(")
        persist_idx = body.find("persist_model_reply(")
        store_idx = body.find("memory.store_telegram(")

        self.assertGreater(audit_idx, 0)
        self.assertGreater(persist_idx, audit_idx)
        self.assertGreater(store_idx, persist_idx)

        persist_window = body[persist_idx:persist_idx + 850]
        self.assertIn("if owner_bridge:", body[audit_idx:persist_idx])
        self.assertIn('surface="web_owner"', persist_window)
        self.assertIn("parent_turn_id=_owner_user_msg_turn_id", persist_window)
        self.assertIn("evidence_envelope=_evidence_envelope", persist_window)
        self.assertIn("build_model_reply_audit_verdict", persist_window)

        public_window = body[body.find("else:"):persist_idx]
        self.assertNotIn("persist_model_reply(", public_window)

    def test_outer_fail_open_uses_warn_once_not_debug(self):
        body = _method_body(_read("skills/web_interface.py"), "chat")
        persist_idx = body.find("persist_model_reply(")
        self.assertGreater(persist_idx, 0)
        after = body[persist_idx:persist_idx + 1200]

        self.assertIn("warn_model_reply_persistence_skip", after)
        self.assertNotIn("logger.debug", after)


class CliModelReplyPersistenceWiringTests(unittest.TestCase):
    def test_cli_persists_model_reply_after_audit_before_trajectory_log(self):
        body = _method_body(_read("cli/maez_chat.py"), "_handle_chat")
        audit_idx = body.find("_sc_result = _sc_audit(")
        persist_idx = body.find("persist_model_reply(")
        trajectory_idx = body.find("claude_router.log_trajectory(")

        self.assertGreater(audit_idx, 0)
        self.assertGreater(persist_idx, audit_idx)
        self.assertGreater(trajectory_idx, persist_idx)

        window = body[persist_idx - 250:persist_idx + 850]
        self.assertIn('surface="cli"', window)
        self.assertIn("parent_turn_id=_cli_user_msg_turn_id", window)
        self.assertIn("evidence_envelope=_evidence_envelope", window)
        self.assertIn("final_reply", window)
        self.assertIn("if _cli_ledger_db_path and _cli_audit_ran:", window)
        self.assertIn("build_model_reply_audit_verdict", window)

    def test_outer_fail_open_uses_warn_once_not_pass(self):
        body = _method_body(_read("cli/maez_chat.py"), "_handle_chat")
        persist_idx = body.find("persist_model_reply(")
        trajectory_idx = body.find("claude_router.log_trajectory(")
        self.assertGreater(persist_idx, 0)
        self.assertGreater(trajectory_idx, persist_idx)
        after = body[persist_idx:trajectory_idx]

        self.assertIn("warn_model_reply_persistence_skip", after)
        self.assertNotIn("pass", after)

    def test_cli_does_not_persist_interrupted_or_audit_failed_reply(self):
        body = _method_body(_read("cli/maez_chat.py"), "_handle_chat")
        interrupted_idx = body.find("if self._stop_stream.is_set():")
        audit_flag_idx = body.find("_cli_audit_ran = True")
        persist_idx = body.find("persist_model_reply(")

        self.assertGreater(interrupted_idx, 0)
        self.assertGreater(audit_flag_idx, interrupted_idx)
        self.assertGreater(persist_idx, audit_flag_idx)
        self.assertIn("if _cli_ledger_db_path and _cli_audit_ran:",
                      body[persist_idx - 250:persist_idx])


class WebModelReplyAuditBoundaryTests(unittest.TestCase):
    def test_web_owner_persistence_requires_successful_audit(self):
        body = _method_body(_read("skills/web_interface.py"), "chat")
        audit_idx = body.find("reply = audit_assistant_text(")
        persist_idx = body.find("persist_model_reply(")

        self.assertGreater(audit_idx, 0)
        self.assertGreater(persist_idx, audit_idx)
        self.assertIn("_web_audit_ran = True", body[audit_idx:persist_idx])
        self.assertIn("if owner_bridge and _web_audit_ran:",
                      body[persist_idx - 500:persist_idx])


class TelegramVoiceModelReplyPersistenceTests(unittest.TestCase):
    def test_owner_private_telegram_persists_model_reply_after_audit_before_store(self):
        body = _method_body(_read("skills/telegram_voice.py"), "_process_message")
        audit_idx = body.find("_audit_telegram_reply_with_status(")
        persist_idx = body.find("persist_model_reply(")
        store_idx = body.find("self.memory.store_telegram(", persist_idx)

        self.assertGreater(audit_idx, 0)
        self.assertGreater(persist_idx, audit_idx)
        self.assertGreater(store_idx, persist_idx)

        window = body[persist_idx - 350:persist_idx + 900]
        self.assertIn('if _telegram_ledger_db_path and _telegram_audit_ran:', window)
        self.assertIn('surface="telegram_text"', window)
        self.assertIn("parent_turn_id=_telegram_user_msg_turn_id", window)
        self.assertIn("evidence_envelope=_evidence_envelope", window)
        self.assertIn("build_model_reply_audit_verdict", window)

    def test_telegram_uses_single_surface_label_for_audit_envelope_and_ledger(self):
        body = _method_body(_read("skills/telegram_voice.py"), "_process_message")
        persist_idx = body.find("persist_model_reply(")
        self.assertGreater(persist_idx, 0)
        persistence_window = body[persist_idx - 700:persist_idx + 1000]

        self.assertIn('_default_signals("telegram_text")', body)
        self.assertIn('surface="telegram_text"', persistence_window)
        self.assertIn('"surface": "telegram_text"', persistence_window)
        self.assertNotIn('"telegram_surface"', persistence_window)

    def test_outer_fail_open_uses_warn_once_not_debug(self):
        body = _method_body(_read("skills/telegram_voice.py"), "_process_message")
        persist_idx = body.find("persist_model_reply(")
        store_idx = body.find("self.memory.store_telegram(", persist_idx)
        self.assertGreater(persist_idx, 0)
        self.assertGreater(store_idx, persist_idx)
        after = body[persist_idx:store_idx]

        self.assertIn("warn_model_reply_persistence_skip", after)
        self.assertNotIn("logger.debug", after)


class MemoryProjectionRulesModelReplyScopeTests(unittest.TestCase):
    def test_rulebook_documents_autobiographical_reply_persistence_scope(self):
        doc = _read("docs/governance/MEMORY_PROJECTION_RULES.md")

        self.assertIn("Autobiographical Reply Persistence Scope", doc)
        self.assertIn("main owner-response paths", doc)
        self.assertIn("Excluded speech paths", doc)
        self.assertIn("reflection", doc)
        self.assertIn("proposal", doc)
        self.assertIn("dream", doc)
        self.assertIn("not silently promoted", doc)

    def test_persistence_fail_open_is_warn_once(self):
        src = _read("core/ledger/model_reply_persistence.py")
        warn_src = _read("core/ledger/model_reply_persistence_warning.py")
        self.assertIn("_warn_once", src)
        self.assertIn("_LOGGER.warning", warn_src)
        self.assertIn("warn_model_reply_persistence_skip", src)


if __name__ == "__main__":
    unittest.main()
