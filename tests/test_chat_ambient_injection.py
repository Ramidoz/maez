# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5r — chat-handler ambient injection wiring tests.

The signal pipeline (skills/iphone_ingest.py + core/memory/ambient.py)
already populates ambient state. wondering_cycle uses it. Until this
slice, the daemon's chat handler did NOT — Telegram messages went
out without knowing where the owner was, what app was active, or
their focus mode. This test pins that the wiring exists in the
right call site, gated by MAEZ_AMBIENT_BRIEF.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class TestChatHandlerInjectsAmbientBlock(unittest.TestCase):
    """The wiring is a few-liner inside daemon.maez_daemon. Rather
    than spin up the whole daemon (huge startup cost, would couple
    this test to ollama / chroma / surfaces), assert against the
    source so a future refactor that drops the import is caught."""

    def setUp(self):
        self.daemon_src = (
            _REPO / "daemon" / "maez_daemon.py"
        ).read_text()

    def test_ambient_prompt_block_is_imported_in_daemon(self):
        # Lazy import inside the chat path is fine; just verify the
        # symbol appears.
        self.assertIn(
            "from core.memory.ambient_format import ambient_prompt_block",
            self.daemon_src,
            "daemon must import ambient_prompt_block "
            "for the chat-path injection",
        )

    def test_env_gate_pattern_matches_lived_recall(self):
        self.assertIn(
            'os.environ.get("MAEZ_AMBIENT_BRIEF", "1") != "0"',
            self.daemon_src,
            "ambient injection must be gated by MAEZ_AMBIENT_BRIEF "
            "(default on; '0' disables) — same pattern as "
            "MAEZ_LIVED_RECALL for operator-symmetric control",
        )

    def test_injection_appends_to_messages_as_system_role(self):
        # Look for the append pattern in the right vicinity.
        self.assertIn('"role": "system"', self.daemon_src)
        # Two role-system appends: one for lived_brief, one for
        # ambient. Confirm at least the ambient one exists with
        # the ambient block content variable.
        self.assertIn("_ambient_block", self.daemon_src)


class TestAmbientPromptBlockProducesUsefulOutput(unittest.TestCase):
    """Sanity check: the function the daemon now calls actually
    returns something the model can use. This exercises the ambient
    pipeline end-to-end (signals reader + weather + active-window
    poll + format) but tolerates partial failure — any individual
    pull may degrade silently in the production environment."""

    def test_block_renders_without_raising(self):
        from core.memory.ambient_format import ambient_prompt_block
        out = ambient_prompt_block()
        # Output may be empty if every pull failed (offline + no
        # signals + no DISPLAY), but the call itself must not raise.
        self.assertIsInstance(out, str)


if __name__ == "__main__":
    unittest.main()
