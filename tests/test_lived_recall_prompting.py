# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 6 wiring tests (ADR 0019).

Locks the contract for injecting the lived-recall brief into
``handle_message``'s synthesis prompt. Source-level assertions —
mocking the full handle_message pipeline (memory + action_engine +
ollama + audit + perception) is heavy, and the structural shape is
what matters: the brief must land as a system message between
chat_history and premise_flag, gated by a feature flag, and a
build-time exception must not break the synthesis path.

Tests cover:

- daemon imports build_lived_recall_brief.
- daemon constructs EpisodeStore + RelationshipGraph at __init__.
- handle_message builds the brief from user text + lived stores.
- handle_message gates injection on MAEZ_LIVED_RECALL env (default
  enabled, "0" disables).
- Empty brief is not injected (no system message added when no
  signal — avoids polluting prompt with empty headers).
- Brief injection lands BETWEEN chat_history threading and
  premise_flag (matches the ADR 0019 prompt-ordering rule:
  "after current memory block, before final answer generation").
- Build-time exception is caught silently (synthesis must continue).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DAEMON_SRC = (_REPO / "daemon" / "maez_daemon.py").read_text()


class DaemonImportsLivedRecall(unittest.TestCase):
    def test_imports_build_lived_recall_brief(self):
        self.assertIn(
            "from core.memory.lived_recall import build_lived_recall_brief",
            _DAEMON_SRC,
            "Phase 6 wiring requires importing the planner.",
        )

    def test_imports_lived_stores(self):
        self.assertIn("from core.memory.episodes import EpisodeStore", _DAEMON_SRC)
        self.assertIn(
            "from core.memory.relationship_graph import RelationshipGraph",
            _DAEMON_SRC,
        )


class DaemonConstructsLivedStoresAtInit(unittest.TestCase):
    """The stores must be constructed once at daemon init and reused
    across handle_message calls — not re-opened on every request."""

    def test_episode_store_attribute_assigned(self):
        self.assertRegex(
            _DAEMON_SRC,
            r"self\.lived_episodes\s*=\s*EpisodeStore\(",
            "daemon must assign self.lived_episodes at init",
        )

    def test_relationship_graph_attribute_assigned(self):
        self.assertRegex(
            _DAEMON_SRC,
            r"self\.lived_graph\s*=\s*RelationshipGraph\(",
            "daemon must assign self.lived_graph at init",
        )


class HandleMessageBuildsBriefFromUserText(unittest.TestCase):
    def test_brief_built_from_text_arg(self):
        # The query passed to build_lived_recall_brief must be the
        # user's `text` (the message they just sent), not some other
        # variable. Lock the call shape.
        self.assertRegex(
            _DAEMON_SRC,
            r"build_lived_recall_brief\(\s*text\s*,",
            "lived recall brief query must be the user's text",
        )

    def test_brief_passed_lived_stores(self):
        self.assertRegex(
            _DAEMON_SRC,
            r"episode_store\s*=\s*self\.lived_episodes",
        )
        self.assertRegex(
            _DAEMON_SRC,
            r"graph\s*=\s*self\.lived_graph",
        )


class FeatureFlagGatesInjection(unittest.TestCase):
    """MAEZ_LIVED_RECALL env knob — default enabled, '0' disables.
    Fast rollback path if the wiring degrades chat quality in lived
    use."""

    def test_env_var_check_present(self):
        self.assertIn("MAEZ_LIVED_RECALL", _DAEMON_SRC)

    def test_default_enabled(self):
        # Default: missing env or any value other than "0" → enabled.
        # The check should look like `os.environ.get("MAEZ_LIVED_RECALL", "1") != "0"`
        # or equivalent — the structural invariant is "default enabled".
        self.assertRegex(
            _DAEMON_SRC,
            r'os\.environ\.get\("MAEZ_LIVED_RECALL"[^)]*\)\s*!=\s*"0"',
            "MAEZ_LIVED_RECALL must default enabled (default not '0')",
        )


class EmptyBriefIsNotInjected(unittest.TestCase):
    """An empty brief means no relevant data — must not be appended
    as a system message (would pollute the prompt with an empty
    header for no signal)."""

    def test_brief_truthy_check_before_append(self):
        # The injection must be guarded by `if _lived_brief:` (or
        # similar truthy check) so an empty brief is skipped.
        self.assertRegex(
            _DAEMON_SRC,
            r"if\s+_lived_brief\s*:",
            "empty lived brief must be skipped before append",
        )


class InjectionPlacementBetweenHistoryAndPremise(unittest.TestCase):
    """The plan: lived recall lands AFTER Chroma recall (already
    inside sys_prompt) AND chat_history threading, BEFORE premise_flag
    and user turn. Lock the structural shape via order in the source."""

    def test_lived_brief_append_before_premise_flag_append(self):
        # In the source, the `if _lived_brief: messages.append(...)`
        # block must appear before the `if _premise_flag: messages.append(...)`
        # block. Order matters for prompt construction.
        m_lived = _DAEMON_SRC.find('"role": "system", "content": _lived_brief')
        m_premise = _DAEMON_SRC.find('"role": "system", "content": _premise_flag')
        m_user = _DAEMON_SRC.find('messages.append({"role": "user", "content": prompt})')
        self.assertGreater(m_lived, 0, "lived_brief append not found")
        self.assertGreater(m_premise, 0, "premise_flag append not found (regression?)")
        self.assertGreater(m_user, 0, "user-turn append not found (regression?)")
        self.assertLess(m_lived, m_premise, "lived_brief must come before premise_flag")
        self.assertLess(m_premise, m_user, "premise_flag must come before user turn")


class FailureIsSilent(unittest.TestCase):
    """Build-time exception in the planner must not break synthesis.
    The wiring must wrap the brief build in try/except and fall
    back to empty (no injection)."""

    def test_brief_build_in_try_except(self):
        # Find the build call and verify it's inside a try block.
        # Conservative check: a `try:` precedes the build call within
        # ~200 chars, and an `except` follows within ~400 chars.
        idx = _DAEMON_SRC.find("build_lived_recall_brief(")
        self.assertGreater(idx, 0)
        before = _DAEMON_SRC[max(0, idx - 200):idx]
        after = _DAEMON_SRC[idx:idx + 400]
        self.assertIn(
            "try:",
            before,
            "build_lived_recall_brief must be inside a try: block",
        )
        self.assertRegex(
            after,
            r"except\s+Exception",
            "build_lived_recall_brief must catch Exception (silent fail-open)",
        )


if __name__ == "__main__":
    unittest.main()
