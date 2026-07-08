# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""TDD tests for core.ledger.writer flag-parsing + per-kind validation.

Pins:
  1. MAEZ_LEDGER_WRITES env-flag parsing (strict, default-off, with
     warning on unrecognized non-empty non-falsy values).
  2. Per-kind NOT-NULL contract (docs/ledger/envelope-schema.md §4.2),
     enforced BEFORE the SQL INSERT (not as a DB error).
  3. Per-kind forbidden-field contract.
  4. Atomicity: validation failure → no row inserted, no meta change.
  5. Disabled writer is a silent no-op even on otherwise-invalid
     payloads.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_writer_val_")

from core.ledger import migrate as ledger_migrate  # noqa: E402
from core.ledger import writer as writer_mod  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


LOGGER_NAME = "core.ledger.writer"


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    ledger_migrate.run(str(path))
    return str(path)


def _count_turns(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    finally:
        conn.close()


def _get_meta(db_path: str, key: str) -> str | None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _scrub_env() -> dict:
    env = dict(os.environ)
    env.pop("MAEZ_LEDGER_WRITES", None)
    return env


# Per-kind valid kwargs (the structured-types canonical API).
def _stamp_for_kind(kind: str) -> dict:
    labels_by_kind = {
        "user_message": ["owner_utterance"],
        "model_reply": ["self_generated"],
        "tool_call": ["self_generated"],
        "tool_result": ["tool_output"],
        "daemon_cycle": ["self_generated"],
        "approval_decision": ["owner_utterance"],
        "self_mod_dialog_step": ["owner_utterance", "self_generated"],
        "peer_message_in": ["third_party"],
        "peer_message_out": ["self_generated"],
        "system_event": ["self_generated"],
    }
    return {"taint_labels": labels_by_kind[kind], "privacy_access": "public"}


def _valid_kwargs(kind: str) -> dict:
    common = {"surface": "test", **_stamp_for_kind(kind)}
    if kind == "user_message":
        return {**common, "raw_text": "hi"}
    if kind == "model_reply":
        return {**common, "raw_text": "reply",
                "model_id": "qwen36-27b",
                "prompt_hash": "p" * 64, "soul_hash": "s" * 64,
                "evidence_envelope": {"claimable": []},
                "audit_verdict": {"verdict": "grounded"}}
    if kind == "tool_call":
        return {**common, "raw_text": "run", "action_proposal": {"tool": "x"}}
    if kind == "tool_result":
        # parent_turn_id is required; supply a synthetic uuid (writer
        # doesn't enforce existence at insert — FK is documented but
        # not enforced at DB level since pragma may be off).
        return {**common, "raw_text": "out",
                "parent_turn_id": "11111111-1111-4111-8111-111111111111"}
    if kind == "daemon_cycle":
        return {**common, "raw_text": "thinking",
                "model_id": "qwen36-27b",
                "prompt_hash": "p" * 64, "soul_hash": "s" * 64,
                "evidence_envelope": {"claimable": []},
                "audit_verdict": {"verdict": "grounded"}}
    if kind == "approval_decision":
        return {**common, "raw_text": "approved",
                "audit_verdict": {"verdict": "approved"},
                "pending_card_id": 42}
    if kind == "self_mod_dialog_step":
        return {**common, "raw_text": "step",
                "audit_verdict": {"verdict": "clean"},
                "self_mod_dialog_id": 7}
    if kind == "peer_message_in":
        return {**common, "raw_text": "peer hi",
                "parent_turn_id": "11111111-1111-4111-8111-222222222222"}
    if kind == "peer_message_out":
        return {**common, "raw_text": "peer hi back",
                "evidence_envelope": {"claimable": []},
                "audit_verdict": {"verdict": "clean"}}
    if kind == "system_event":
        return {**common, "raw_text": '{"event":"x"}'}
    raise AssertionError(f"unknown kind: {kind}")


class FlagTests(unittest.TestCase):
    """MAEZ_LEDGER_WRITES parsing: strict, default-off, warn on garbage."""

    def setUp(self):
        self.db_path = _fresh_db("flag")

    def test_unset_is_disabled(self):
        with patch.dict(os.environ, _scrub_env(), clear=True):
            os.environ["MAEZ_TEST_MODE"] = "1"
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                self.assertFalse(w.is_enabled())
            finally:
                w.close()

    def test_empty_string_is_disabled(self):
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": ""}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                self.assertFalse(w.is_enabled())
            finally:
                w.close()

    def test_zero_is_disabled(self):
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "0"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                self.assertFalse(w.is_enabled())
            finally:
                w.close()

    def test_falsey_words_are_disabled(self):
        for v in ("false", "FALSE", "False", "no", "NO", "off"):
            with self.subTest(value=v):
                with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": v}):
                    w = writer_mod.LedgerWriter(self.db_path)
                    try:
                        self.assertFalse(w.is_enabled())
                    finally:
                        w.close()

    def test_one_is_enabled(self):
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                self.assertTrue(w.is_enabled())
            finally:
                w.close()

    def test_true_variants_are_enabled(self):
        for v in ("true", "TRUE", "True", "TrUe"):
            with self.subTest(value=v):
                with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": v}):
                    w = writer_mod.LedgerWriter(self.db_path)
                    try:
                        self.assertTrue(w.is_enabled())
                    finally:
                        w.close()

    def test_whitespace_stripped_for_enabled(self):
        for v in (" 1 ", "\t1\n", " true ", "  TRUE\t"):
            with self.subTest(value=v):
                with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": v}):
                    w = writer_mod.LedgerWriter(self.db_path)
                    try:
                        self.assertTrue(w.is_enabled())
                    finally:
                        w.close()

    def test_unrecognized_values_disabled_with_warning(self):
        for v in ("yes", "on", "enable", "TRUE_LIKE", "yep"):
            with self.subTest(value=v):
                with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": v}):
                    # De-fork: the unrecognized-value warning now comes from the
                    # shared core.ledger.writes_flag helper, not the writer logger.
                    with self.assertLogs("core.ledger.writes_flag", level="WARNING") as cm:
                        w = writer_mod.LedgerWriter(self.db_path)
                        try:
                            self.assertFalse(w.is_enabled())
                        finally:
                            w.close()
                    self.assertTrue(
                        any("MAEZ_LEDGER_WRITES" in line for line in cm.output),
                        f"warning must mention MAEZ_LEDGER_WRITES; got {cm.output!r}")

    def test_warning_emitted_once_per_instance(self):
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "yes"}):
            with self.assertLogs("core.ledger.writes_flag", level="WARNING") as cm:
                w = writer_mod.LedgerWriter(self.db_path)
                try:
                    for _ in range(5):
                        self.assertFalse(w.is_enabled())
                finally:
                    w.close()
            warning_records = [r for r in cm.records if r.levelno == logging.WARNING]
            self.assertEqual(len(warning_records), 1,
                f"warning must log exactly once per instance; got {len(warning_records)}")


class RequiredFieldsTests(unittest.TestCase):
    """One test per (kind, required-field) pair from §4.2."""

    def setUp(self):
        self.db_path = _fresh_db("required")

    def _expect_validation_error(self, kind: str, kwargs: dict, missing_field: str):
        before = _count_turns(self.db_path)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                with self.assertRaises(ValueError) as ctx:
                    raw_text = kwargs.pop("raw_text", None)
                    w.write_turn(kind, raw_text, **kwargs)
            finally:
                w.close()
        msg = str(ctx.exception)
        self.assertIn(kind, msg, f"error must name kind; got {msg!r}")
        self.assertIn(missing_field, msg,
            f"error must name missing field {missing_field!r}; got {msg!r}")
        self.assertEqual(_count_turns(self.db_path), before,
            "validation failure must not insert a row")

    # user_message
    def test_user_message_missing_raw_text(self):
        kw = _valid_kwargs("user_message"); kw["raw_text"] = None
        self._expect_validation_error("user_message", kw, "raw_text")

    # model_reply
    def test_model_reply_missing_raw_text(self):
        kw = _valid_kwargs("model_reply"); kw["raw_text"] = None
        self._expect_validation_error("model_reply", kw, "raw_text")

    def test_model_reply_missing_model_id(self):
        kw = _valid_kwargs("model_reply"); kw["model_id"] = None
        self._expect_validation_error("model_reply", kw, "model_id")

    def test_model_reply_missing_prompt_hash(self):
        kw = _valid_kwargs("model_reply"); kw["prompt_hash"] = None
        self._expect_validation_error("model_reply", kw, "prompt_hash")

    def test_model_reply_missing_soul_hash(self):
        kw = _valid_kwargs("model_reply"); kw["soul_hash"] = None
        self._expect_validation_error("model_reply", kw, "soul_hash")

    def test_model_reply_missing_evidence_envelope(self):
        kw = _valid_kwargs("model_reply"); kw["evidence_envelope"] = None
        self._expect_validation_error("model_reply", kw, "evidence_envelope")

    def test_model_reply_missing_audit_verdict(self):
        kw = _valid_kwargs("model_reply"); kw["audit_verdict"] = None
        self._expect_validation_error("model_reply", kw, "audit_verdict")

    # tool_call
    def test_tool_call_missing_action_proposal(self):
        kw = _valid_kwargs("tool_call"); kw["action_proposal"] = None
        self._expect_validation_error("tool_call", kw, "action_proposal")

    # tool_result
    def test_tool_result_missing_parent_turn_id(self):
        kw = _valid_kwargs("tool_result"); kw["parent_turn_id"] = None
        self._expect_validation_error("tool_result", kw, "parent_turn_id")

    # daemon_cycle (same shape as model_reply for all-required)
    def test_daemon_cycle_missing_model_id(self):
        kw = _valid_kwargs("daemon_cycle"); kw["model_id"] = None
        self._expect_validation_error("daemon_cycle", kw, "model_id")

    def test_daemon_cycle_missing_evidence_envelope(self):
        kw = _valid_kwargs("daemon_cycle"); kw["evidence_envelope"] = None
        self._expect_validation_error("daemon_cycle", kw, "evidence_envelope")

    # approval_decision
    def test_approval_decision_missing_audit_verdict(self):
        kw = _valid_kwargs("approval_decision"); kw["audit_verdict"] = None
        self._expect_validation_error("approval_decision", kw, "audit_verdict")

    def test_approval_decision_missing_pending_card_id(self):
        kw = _valid_kwargs("approval_decision"); kw["pending_card_id"] = None
        self._expect_validation_error("approval_decision", kw, "pending_card_id")

    # self_mod_dialog_step
    def test_self_mod_dialog_step_missing_dialog_id(self):
        kw = _valid_kwargs("self_mod_dialog_step"); kw["self_mod_dialog_id"] = None
        self._expect_validation_error("self_mod_dialog_step", kw, "self_mod_dialog_id")

    # peer_message_in: parent_turn_id is NOT required per §12 sign-off
    # ratification 2026-05-06 (parent lives in the OTHER Maez's ledger,
    # not ours). Verify the writer accepts a peer_message_in without it.
    def test_peer_message_in_without_parent_turn_id_succeeds(self):
        kw = _valid_kwargs("peer_message_in")
        kw["parent_turn_id"] = None
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                raw_text = kw.pop("raw_text", None)
                # Must NOT raise — parent_turn_id is optional for
                # peer_message_in per §12 ratification.
                tid = w.write_turn("peer_message_in", raw_text, **kw)
                self.assertIsNotNone(tid,
                    "peer_message_in must succeed without parent_turn_id "
                    "per §12 sign-off (parent lives in peer's ledger)")
            finally:
                w.close()

    # peer_message_out
    def test_peer_message_out_missing_evidence_envelope(self):
        kw = _valid_kwargs("peer_message_out"); kw["evidence_envelope"] = None
        self._expect_validation_error("peer_message_out", kw, "evidence_envelope")

    def test_peer_message_out_missing_audit_verdict(self):
        kw = _valid_kwargs("peer_message_out"); kw["audit_verdict"] = None
        self._expect_validation_error("peer_message_out", kw, "audit_verdict")

    # system_event
    def test_system_event_missing_raw_text(self):
        kw = _valid_kwargs("system_event"); kw["raw_text"] = None
        self._expect_validation_error("system_event", kw, "raw_text")


class ForbiddenFieldsTests(unittest.TestCase):
    """Per-kind forbidden non-null contract."""

    def setUp(self):
        self.db_path = _fresh_db("forbidden")

    def _expect_validation_error(self, kind: str, kwargs: dict, forbidden_field: str):
        before = _count_turns(self.db_path)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                with self.assertRaises(ValueError) as ctx:
                    raw_text = kwargs.pop("raw_text", None)
                    w.write_turn(kind, raw_text, **kwargs)
            finally:
                w.close()
        msg = str(ctx.exception)
        self.assertIn(kind, msg, f"error must name kind; got {msg!r}")
        self.assertIn(forbidden_field, msg,
            f"error must name forbidden field {forbidden_field!r}; got {msg!r}")
        self.assertEqual(_count_turns(self.db_path), before)

    # user_message: forbid model_id, prompt_hash, audit_verdict
    def test_user_message_with_model_id(self):
        kw = _valid_kwargs("user_message"); kw["model_id"] = "qwen"
        self._expect_validation_error("user_message", kw, "model_id")

    def test_user_message_with_prompt_hash(self):
        kw = _valid_kwargs("user_message"); kw["prompt_hash"] = "p" * 64
        self._expect_validation_error("user_message", kw, "prompt_hash")

    def test_user_message_with_audit_verdict(self):
        kw = _valid_kwargs("user_message"); kw["audit_verdict"] = {"v": "x"}
        self._expect_validation_error("user_message", kw, "audit_verdict")

    # tool_call: forbid model_id
    def test_tool_call_with_model_id(self):
        kw = _valid_kwargs("tool_call"); kw["model_id"] = "qwen"
        self._expect_validation_error("tool_call", kw, "model_id")

    # tool_result: forbid model_id, evidence_envelope
    def test_tool_result_with_model_id(self):
        kw = _valid_kwargs("tool_result"); kw["model_id"] = "qwen"
        self._expect_validation_error("tool_result", kw, "model_id")

    def test_tool_result_with_evidence_envelope(self):
        kw = _valid_kwargs("tool_result"); kw["evidence_envelope"] = {"x": []}
        self._expect_validation_error("tool_result", kw, "evidence_envelope")

    # approval_decision: forbid model_id
    def test_approval_decision_with_model_id(self):
        kw = _valid_kwargs("approval_decision"); kw["model_id"] = "qwen"
        self._expect_validation_error("approval_decision", kw, "model_id")

    # system_event: forbid model_id, prompt_hash
    def test_system_event_with_model_id(self):
        kw = _valid_kwargs("system_event"); kw["model_id"] = "qwen"
        self._expect_validation_error("system_event", kw, "model_id")

    def test_system_event_with_prompt_hash(self):
        kw = _valid_kwargs("system_event"); kw["prompt_hash"] = "p" * 64
        self._expect_validation_error("system_event", kw, "prompt_hash")


class DisabledWriterTests(unittest.TestCase):
    """Disabled writer is a silent no-op — never validates, never writes."""

    def setUp(self):
        self.db_path = _fresh_db("disabled")

    def test_disabled_returns_none_on_valid_payload(self):
        before = _count_turns(self.db_path)
        before_head = _get_meta(self.db_path, "last_chain_hash")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "0"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                kw = _valid_kwargs("user_message")
                result = w.write_turn("user_message", kw.pop("raw_text"), **kw)
            finally:
                w.close()
        self.assertIsNone(result)
        self.assertEqual(_count_turns(self.db_path), before)
        self.assertEqual(_get_meta(self.db_path, "last_chain_hash"), before_head)

    def test_disabled_silent_noop_on_invalid_payload(self):
        """Disabled means do-nothing — including not validating."""
        before = _count_turns(self.db_path)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "0"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                kw = _valid_kwargs("model_reply")
                kw["model_id"] = None  # would be invalid on enabled writer
                try:
                    result = w.write_turn("model_reply", kw.pop("raw_text"), **kw)
                except ValueError as e:
                    self.fail(f"disabled writer must not validate; got: {e}")
            finally:
                w.close()
        self.assertIsNone(result)
        self.assertEqual(_count_turns(self.db_path), before)


class TransactionAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.db_path = _fresh_db("atomicity")

    def test_validation_failure_no_state_change(self):
        before_count = _count_turns(self.db_path)
        before_head = _get_meta(self.db_path, "last_chain_hash")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                kw = _valid_kwargs("model_reply"); kw["model_id"] = None
                with self.assertRaises(ValueError):
                    w.write_turn("model_reply", kw.pop("raw_text"), **kw)
            finally:
                w.close()
        self.assertEqual(_count_turns(self.db_path), before_count)
        self.assertEqual(_get_meta(self.db_path, "last_chain_hash"), before_head)


if __name__ == "__main__":
    unittest.main()
