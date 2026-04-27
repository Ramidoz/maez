# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Premise-acceptance audit tests (2026-04-27 incident).

The named bug:

  Owner:  "I was approving the cleanup suggestion you gave"
  Maez:   accepts premise → issues `journalctl --vacuum / apt clean`

Root cause: self_claim_audit guards Maez's *own* claims; it does not
verify premises Maez *accepts from the user*. premise_audit closes
that gap by detecting user-side claims about past Maez actions and
checking them against the proposal store + audit log. When no match
exists, the synthesis prompt gets a flag instructing Maez to ask
for clarification rather than silently proceed.

Tests cover:

- Detection: each pattern fires on its target shape.
- Non-premise text returns None.
- Phrase extraction is bounded and trimmed.
- Verification: zero token overlap → unverified.
- Verification: real overlap with seeded card → verified.
- Public entry point returns prompt flag iff unverified.
- Empty / malformed inputs handled gracefully (never raise).
- Real owner-incident regression: cleanup-suggestion premise is
  flagged when no cleanup card exists.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── DB fixture helpers ──────────────────────────────────────────────


def _make_cards_db():
    """Empty pending_cards.db with the production schema."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute(
        """
        CREATE TABLE pending_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL UNIQUE,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            status TEXT NOT NULL,
            action TEXT,
            params_json TEXT,
            reason TEXT,
            plain_english TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    return tmp.name


def _make_audit_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL UNIQUE,
            ts REAL NOT NULL,
            action TEXT NOT NULL,
            params_json TEXT,
            summary TEXT,
            reasoning TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    return tmp.name


def _seed_card(path, *, plain_english, action="run_shell", params=""):
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO pending_cards "
        "(request_id, created_at, updated_at, status, action, "
        " params_json, reason, plain_english) "
        "VALUES (?, ?, ?, 'open', ?, ?, '', ?)",
        ("req-" + str(hash(plain_english))[:8], 0.0, 0.0, action, params, plain_english),
    )
    conn.commit()
    conn.close()


# ── detection ───────────────────────────────────────────────────────


class DetectionFiresOnEachPattern(unittest.TestCase):
    def test_approval_recall_pattern(self):
        from core.safety.premise_audit import detect_premise

        flag = detect_premise("I was approving the cleanup suggestion you gave")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.pattern, "approval_recall")
        self.assertIn("cleanup", flag.phrase.lower())

    def test_proposal_recall_pattern(self):
        from core.safety.premise_audit import detect_premise

        flag = detect_premise("Let's proceed with the patch you proposed earlier")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.pattern, "proposal_recall")
        self.assertIn("patch", flag.phrase.lower())

    def test_statement_recall_pattern(self):
        from core.safety.premise_audit import detect_premise

        flag = detect_premise("You said the GPU was at 95C earlier.")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.pattern, "statement_recall")

    def test_temporal_recall_pattern(self):
        from core.safety.premise_audit import detect_premise

        flag = detect_premise("Yesterday you mentioned the disk fixation problem.")
        self.assertIsNotNone(flag)
        # Either statement_recall OR temporal_recall — the message
        # contains both shapes; first pattern wins. We just lock
        # that *some* premise pattern fires.
        self.assertIn(
            flag.pattern,
            {"statement_recall", "temporal_recall"},
        )


class DoesNotFireOnNonPremiseText(unittest.TestCase):
    def test_plain_question(self):
        from core.safety.premise_audit import detect_premise

        self.assertIsNone(detect_premise("What's the GPU temp?"))

    def test_command(self):
        from core.safety.premise_audit import detect_premise

        self.assertIsNone(detect_premise("ls -la"))

    def test_empty(self):
        from core.safety.premise_audit import detect_premise

        self.assertIsNone(detect_premise(""))
        self.assertIsNone(detect_premise(None))

    def test_first_person_without_recall(self):
        from core.safety.premise_audit import detect_premise

        # "I want to" by itself isn't a premise about past Maez action.
        self.assertIsNone(detect_premise("I want to upgrade the kernel"))


# ── verification ────────────────────────────────────────────────────


class VerifyAgainstEmptyDBs(unittest.TestCase):
    """With no cards and no audit entries, every premise is unverified."""

    def test_zero_match_count_marks_unverified(self):
        from core.safety.premise_audit import (
            detect_premise,
            verify_premise,
        )

        cards = _make_cards_db()
        audit = _make_audit_db()
        try:
            flag = detect_premise("I was approving the cleanup suggestion you gave")
            self.assertIsNotNone(flag)
            verify_premise(
                flag,
                cards_db_path=cards,
                audit_db_path=audit,
            )
            self.assertEqual(flag.match_count, 0)
            self.assertEqual(flag.verdict, "unverified")
        finally:
            Path(cards).unlink(missing_ok=True)
            Path(audit).unlink(missing_ok=True)


class VerifyWithMatchingCard(unittest.TestCase):
    def test_seeded_card_marks_premise_verified(self):
        from core.safety.premise_audit import (
            detect_premise,
            verify_premise,
        )

        cards = _make_cards_db()
        audit = _make_audit_db()
        try:
            _seed_card(
                cards,
                plain_english=("Clean up cache and logs to free disk space"),
                action="run_shell",
                params='{"command": "apt clean"}',
            )
            flag = detect_premise("I was approving the cleanup suggestion you gave")
            verify_premise(
                flag,
                cards_db_path=cards,
                audit_db_path=audit,
            )
            self.assertGreater(flag.match_count, 0)
            self.assertEqual(flag.verdict, "verified")
        finally:
            Path(cards).unlink(missing_ok=True)
            Path(audit).unlink(missing_ok=True)


class VerifyWithMatchingAudit(unittest.TestCase):
    def test_seeded_audit_marks_premise_verified(self):
        from core.safety.premise_audit import (
            detect_premise,
            verify_premise,
        )

        cards = _make_cards_db()
        audit = _make_audit_db()
        try:
            conn = sqlite3.connect(audit)
            conn.execute(
                "INSERT INTO audit_log "
                "(request_id, ts, action, params_json, summary, reasoning) "
                "VALUES ('req-1', 0.0, 'run_shell', '{}', "
                "'Proposed kernel upgrade for security patch', '')",
            )
            conn.commit()
            conn.close()
            flag = detect_premise("I want to approve the kernel upgrade")
            verify_premise(
                flag,
                cards_db_path=cards,
                audit_db_path=audit,
            )
            self.assertGreater(flag.match_count, 0)
            self.assertEqual(flag.verdict, "verified")
        finally:
            Path(cards).unlink(missing_ok=True)
            Path(audit).unlink(missing_ok=True)


# ── prompt-flag generation ──────────────────────────────────────────


class PromptFlagFormat(unittest.TestCase):
    def test_unverified_yields_clarify_instruction(self):
        from core.safety.premise_audit import (
            PremiseFlag,
            format_prompt_flag,
        )

        msg = format_prompt_flag(
            PremiseFlag(
                pattern="approval_recall",
                phrase="the cleanup suggestion you gave",
                match_count=0,
                verdict="unverified",
            )
        )
        self.assertIn("USER PREMISE FLAG", msg)
        self.assertIn("clarify", msg.lower())
        self.assertIn("cleanup suggestion", msg)
        # Must not phrase as a refusal — Maez retains agency.
        self.assertNotIn("refuse", msg.lower())
        self.assertNotIn("blocked", msg.lower())

    def test_verified_yields_empty_string(self):
        from core.safety.premise_audit import (
            PremiseFlag,
            format_prompt_flag,
        )

        self.assertEqual(
            format_prompt_flag(
                PremiseFlag(
                    pattern="approval_recall",
                    phrase="anything",
                    match_count=3,
                    verdict="verified",
                )
            ),
            "",
        )


# ── public entry point ──────────────────────────────────────────────


class AuditUserPremiseEndToEnd(unittest.TestCase):
    def test_unverified_returns_flag_string(self):
        from core.safety.premise_audit import audit_user_premise

        cards = _make_cards_db()
        audit = _make_audit_db()
        try:
            out = audit_user_premise(
                "I was approving the cleanup suggestion you gave",
                cards_db_path=cards,
                audit_db_path=audit,
            )
            self.assertIsNotNone(out)
            self.assertIn("USER PREMISE FLAG", out)
        finally:
            Path(cards).unlink(missing_ok=True)
            Path(audit).unlink(missing_ok=True)

    def test_verified_returns_none(self):
        from core.safety.premise_audit import audit_user_premise

        cards = _make_cards_db()
        audit = _make_audit_db()
        try:
            _seed_card(
                cards,
                plain_english="Cleanup cache and logs",
                params='{"command": "apt clean && journalctl --vacuum"}',
            )
            out = audit_user_premise(
                "I was approving the cleanup suggestion you gave",
                cards_db_path=cards,
                audit_db_path=audit,
            )
            self.assertIsNone(out)
        finally:
            Path(cards).unlink(missing_ok=True)
            Path(audit).unlink(missing_ok=True)

    def test_non_premise_returns_none(self):
        from core.safety.premise_audit import audit_user_premise

        out = audit_user_premise("What time is it?")
        self.assertIsNone(out)

    def test_missing_dbs_handled_gracefully(self):
        from core.safety.premise_audit import audit_user_premise

        out = audit_user_premise(
            "I was approving the cleanup suggestion you gave",
            cards_db_path="/nonexistent/cards.db",
            audit_db_path="/nonexistent/audit.db",
        )
        # No DBs → 0 matches → unverified → flag returned. Critical
        # invariant: never raise on missing DBs.
        self.assertIsNotNone(out)
        self.assertIn("USER PREMISE FLAG", out)

    def test_owner_incident_regression(self):
        """Lock the actual 2026-04-26 21:37 owner exchange shape."""
        from core.safety.premise_audit import audit_user_premise

        cards = _make_cards_db()
        audit = _make_audit_db()
        try:
            # The card store is empty — Maez had no actual cleanup
            # proposal stored. The premise must be flagged.
            out = audit_user_premise(
                "I was approving the cleanup suggestion you gave",
                cards_db_path=cards,
                audit_db_path=audit,
            )
            self.assertIsNotNone(out)
            self.assertIn("clarify", out.lower())
        finally:
            Path(cards).unlink(missing_ok=True)
            Path(audit).unlink(missing_ok=True)


class HandleMessageWiresInPremiseAudit(unittest.TestCase):
    """Source-level assertion: handle_message must call
    audit_user_premise and inject the flag into the synthesis
    messages immediately before the user turn. Mocking the full
    handle_message call path is heavy (memory + action_engine +
    ollama + audit + perception); the structural shape is what
    matters and source assertion is the right granularity."""

    def setUp(self):
        self.src = (_REPO / "daemon" / "maez_daemon.py").read_text()

    def test_handle_message_imports_audit_user_premise(self):
        self.assertIn(
            "from core.safety.premise_audit import audit_user_premise",
            self.src,
        )

    def test_handle_message_calls_audit_and_assigns_flag(self):
        self.assertIn(
            "_premise_flag = audit_user_premise(text)",
            self.src,
        )

    def test_premise_flag_injected_as_system_message(self):
        # The flag must land in `messages` as a system-role entry
        # immediately before the user turn, so the model treats it
        # as a directive about *this* message.
        self.assertRegex(
            self.src,
            r"if\s+_premise_flag:\s*\n\s*messages\.append\("
            r'\{"role":\s*"system",\s*"content":\s*_premise_flag\}\)',
        )

    def test_audit_failure_is_silent(self):
        # The premise audit is advisory — its failure must NOT
        # abort the synthesis path.
        self.assertRegex(
            self.src,
            r"except\s+Exception\s+as\s+_premise_exc:"
            r'\s*\n\s*logger\.debug\("premise audit skipped: ',
        )


if __name__ == "__main__":
    unittest.main()
