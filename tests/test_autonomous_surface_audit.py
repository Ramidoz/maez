# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Autonomous surface audit regressions — 2026-04-24.

After two voice regressions in 24h (nightly `_write_readme` template
overwrite + `Welcome back the owner` greeting), the 2026-04-24
audit (docs/audits/2026-04-24/autonomous_surface_audit.md) found two
more autonomous paths emitting LLM output to Telegram without the
audit stack: `_send_morning_briefing` (F1) and
`DreamState.run_dream_cycle` (F2).

These tests lock in the fix via source inspection. The behavioral
path would need to mock the LLM, Telegram client, file IO, and
system perception — more mocking code than the guard protects.
The regression we're blocking is exactly at the source-literal
level: "this path must call `audit_assistant_text` before Telegram
transport."
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class MorningBriefingAuditedBeforeSend(unittest.TestCase):
    """F1 — `_send_morning_briefing` must route the LLM output
    through `audit_assistant_text` before Telegram transport."""

    def _source(self):
        from daemon.maez_daemon import MaezDaemon
        return inspect.getsource(MaezDaemon._send_morning_briefing)

    def test_calls_audit_assistant_text(self):
        src = self._source()
        self.assertIn("audit_assistant_text", src,
            "morning briefing no longer routes through the audit "
            "stack — see 2026-04-24 audit F1.",
        )

    def test_audit_runs_before_send(self):
        src = self._source()
        audit_pos = src.find("audit_assistant_text")
        send_pos = src.find("_send_telegram_notice")
        self.assertGreater(audit_pos, 0, "audit_assistant_text not found")
        self.assertGreater(send_pos, 0, "_send_telegram_notice not found")
        self.assertLess(audit_pos, send_pos,
            "audit_assistant_text call must appear before "
            "Telegram transport in source — reverse order means "
            "raw LLM output reaches the owner first.",
        )

    def test_briefing_path_not_hardcoded(self):
        src = self._source()
        self.assertNotIn('"/home/rohit/maez/memory/last_briefing.txt"', src,
            "morning_briefing stamp path is hardcoded to dev install — "
            "breaks CI and non-dev installs. Use BASE_DIR / core.paths.",
        )

    def test_prompt_does_not_carry_owner_role_label(self):
        src = self._source()
        # The old prompt had `"You are sending the owner his morning
        # briefing."` — role label + gendered pronoun. The new prompt
        # interpolates `display_name()`.
        self.assertNotIn("sending the owner his", src,
            "morning_briefing prompt still uses 'the owner his' role "
            "label. Use display_name() instead.",
        )

    def test_briefing_stored_in_memory(self):
        src = self._source()
        self.assertIn("store_telegram", src,
            "morning_briefing not stored in telegram memory — "
            "chat_history threading (commit cc462c5) can't surface "
            "the briefing as a prior assistant turn when the owner "
            "replies. Continuity hole.",
        )


class DreamInsightAuditedBeforeSend(unittest.TestCase):
    """F2 — `DreamState.run_dream_cycle`'s insight must route through
    `audit_assistant_text` before Telegram transport."""

    def _source(self):
        from core.evolution.dream_state import DreamState
        return inspect.getsource(DreamState.run_dream_cycle)

    def test_calls_audit_assistant_text(self):
        src = self._source()
        self.assertIn("audit_assistant_text", src,
            "dream insight no longer routes through the audit stack "
            "— see 2026-04-24 audit F2.",
        )

    def test_audit_runs_before_send(self):
        src = self._source()
        # Locate the LAST occurrence of audit_assistant_text (the call
        # site, not the import) and the first Telegram transport call
        # after it. The audit must appear before the send.
        audit_pos = src.rfind("audit_assistant_text(")
        send_pos = src.find("_send_telegram_notice")
        self.assertGreater(audit_pos, 0, "audit_assistant_text() call not found")
        self.assertGreater(send_pos, 0, "_send_telegram_notice not found")
        self.assertLess(audit_pos, send_pos,
            "audit_assistant_text call must appear before "
            "Telegram transport in source — see F2 rationale.",
        )


class TrainingProposalAuditedBeforeSend(unittest.TestCase):
    """F3 — training proposals are mostly deterministic, but they are
    autonomous Telegram output and should use the same output guard."""

    def _source(self):
        from core.evolution.dream_state import DreamState
        return inspect.getsource(DreamState.store_training_proposal)

    def test_calls_audit_assistant_text(self):
        src = self._source()
        self.assertIn("audit_assistant_text", src,
            "training proposal Telegram output no longer routes "
            "through the audit stack — see 2026-04-24 audit F3.",
        )

    def test_audit_runs_before_send(self):
        src = self._source()
        audit_pos = src.rfind("audit_assistant_text(")
        send_pos = src.find("_send_telegram_notice")
        self.assertGreater(audit_pos, 0, "audit_assistant_text() call not found")
        self.assertGreater(send_pos, 0, "_send_telegram_notice not found")
        self.assertLess(audit_pos, send_pos,
            "training proposal audit must appear before Telegram send.",
        )


class GitHubCommitMessageAudited(unittest.TestCase):
    """F5 — public GitHub commit messages generated by the model must
    be audited before they become public repo metadata."""

    def _source(self):
        from skills.github_publish import GitHubPublisher
        return inspect.getsource(GitHubPublisher._generate_commit_message)

    def test_calls_audit_assistant_text(self):
        src = self._source()
        self.assertIn("audit_assistant_text", src,
            "GitHub commit-message generation no longer routes "
            "through the audit stack — see 2026-04-24 audit F5.",
        )

    def test_commit_message_normalized_after_audit(self):
        src = self._source()
        audit_pos = src.rfind("audit_assistant_text(")
        normalize_pos = src.find('" ".join(msg.split())')
        self.assertGreater(audit_pos, 0, "audit_assistant_text() call not found")
        self.assertGreater(normalize_pos, 0, "post-audit normalization not found")
        self.assertLess(audit_pos, normalize_pos,
            "commit message should be audited before final one-line "
            "normalization/truncation.",
        )


if __name__ == "__main__":
    unittest.main()
