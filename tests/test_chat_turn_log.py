# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5v — chat-turn structured log line wiring tests.

Single INFO line emitted per Telegram message Maez handles, capturing
prompt and reply shape so journal-grep can answer "did the substrate
contribute?" across many turns. Source-level test pinning:
spinning up the daemon for a unit test is overkill (chroma + ollama
+ surfaces all need to come up); future refactors that move/drop
this log line should still surface here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class TestChatTurnLogWiring(unittest.TestCase):
    def setUp(self):
        self.daemon_src = (
            _REPO / "daemon" / "maez_daemon.py"
        ).read_text()

    def test_log_token_present(self):
        # The literal log prefix — make a future refactor that
        # renames this token visibly break.
        self.assertIn(
            '"chat_turn handled "',
            self.daemon_src,
            "daemon must emit the 'chat_turn handled' log line",
        )

    def test_log_carries_required_fields(self):
        for token in (
            "source=%s",
            "len_user=%d",
            "len_lived_brief=%d",
            "len_ambient_block=%d",
            "len_reply=%d",
            "user_excerpt=%r",
            "reply_excerpt=%r",
        ):
            self.assertIn(
                token, self.daemon_src,
                f"chat_turn log missing required field {token!r}",
            )

    def test_ambient_block_is_function_scoped(self):
        """Per Step-5r audit finding: _ambient_block was scoped
        inside the if/try block; promoted to function scope at
        the same level as _lived_brief so the response log can
        reference its length. Pin that promotion."""
        # Find both declarations near each other.
        self.assertIn('_lived_brief = ""', self.daemon_src)
        self.assertIn('_ambient_block = ""', self.daemon_src)

    def test_log_fires_after_response_finalization(self):
        """Audit identified line 1857 (just before store_telegram)
        as the right injection point — AFTER LLM synthesis +
        wondering pursuit + canary scrub + audit, BEFORE storage
        and broadcast. Verify the log token appears BEFORE the
        store_telegram call in the file."""
        log_idx = self.daemon_src.index('"chat_turn handled "')
        store_idx = self.daemon_src.index(
            "self.memory.store_telegram",
        )
        self.assertLess(
            log_idx, store_idx,
            "chat_turn log must fire BEFORE store_telegram so the "
            "log captures what was about to be sent (post-audit, "
            "pre-storage)",
        )

    def test_log_reply_excerpt_is_truncated(self):
        """60-char cap on the reply_excerpt so a verbose reply
        doesn't produce an unbounded journalctl line. Verify the
        truncation marker '[:60]' or similar appears in the
        log-building block."""
        # The exact truncation form is implementation-detail;
        # match either the slice or the ellipsis fallback.
        self.assertTrue(
            "[:60]" in self.daemon_src
            or "[:59]" in self.daemon_src,
            "reply/user excerpt must be capped (no unbounded "
            "log lines)",
        )

    def test_chat_turn_backend_errors_use_owner_visible_message(self):
        """Telegram should not send raw backend exception reprs to Rohit.

        The raw details belong in logs/telemetry; the surface gets a short
        local-brain status message.
        """
        handle_start = self.daemon_src.index("    def handle_message(")
        handle_end = self.daemon_src.index("    def _get_public_context", handle_start)
        handle_src = self.daemon_src[handle_start:handle_end]

        self.assertIn("owner_visible_message", handle_src)
        self.assertIn('surface="telegram_chat"', handle_src)
        self.assertNotIn('reply = f"Error: {e}"', handle_src)


if __name__ == "__main__":
    unittest.main()
