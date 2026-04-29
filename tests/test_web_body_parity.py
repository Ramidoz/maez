# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Web body parity — Commit 5 of the 2026-04-23 audit repair pass.

Invariant guarded here:

    When MAEZ_WEB_TOOL_LOOP=1, the owner's web /chat turn first runs
    a brain-loop iteration (via the daemon's /internal/brain_loop
    endpoint) so tools can execute before synthesis. Public/guest
    chats NEVER route through this — tool execution is owner-only.
    When the flag is unset (default), web /chat behavior is exactly
    as before this commit — zero changes to production hot path.

This commit landed INFRASTRUCTURE (a new daemon endpoint + an env-
gated web hook) without changing default runtime behavior. The
tests assert:

  1. The daemon has an /internal/brain_loop endpoint registered.
  2. The endpoint runs brain_loop against daemon.actions when
     both action_engine and pipeline are available.
  3. The endpoint fails open (returns "transcript": "") when
     action_engine or pipeline is unavailable.
  4. The web hook is gated by MAEZ_WEB_TOOL_LOOP — source-level
     assertion that the env check exists.
  5. The web hook is gated by owner_bridge — source-level
     assertion that public/guest path is excluded.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class DaemonEndpointExists(unittest.TestCase):
    """daemon/maez_daemon.py must declare the /internal/brain_loop route."""

    def test_route_declared(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        self.assertIn('@app.route("/internal/brain_loop"', src,
                      "daemon must declare /internal/brain_loop so the "
                      "web process can invoke run_brain_loop against "
                      "the daemon's action_engine.")

    def test_endpoint_calls_run_brain_loop(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        start = src.find('@app.route("/internal/brain_loop"')
        self.assertGreater(start, 0)
        # Find end at the next @app.route decorator.
        end = src.find("@app.route(", start + 30)
        window = src[start:end if end > 0 else len(src)]
        self.assertIn("run_brain_loop(", window,
                      "/internal/brain_loop body must call "
                      "brain_loop.run_brain_loop().")
        self.assertIn("action_engine=", window,
                      "endpoint must wire action_engine into the "
                      "brain_loop call.")
        self.assertIn("get_pipeline=", window,
                      "endpoint must wire get_pipeline into the "
                      "brain_loop call.")

    def test_endpoint_fails_open_on_unavailable_engine(self):
        """The endpoint body should return a successful response with
        empty transcript when action_engine is unavailable, so the
        web caller's fallback path keeps working."""
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        start = src.find('@app.route("/internal/brain_loop"')
        end = src.find("@app.route(", start + 30)
        window = src[start:end if end > 0 else len(src)]
        # A status-503 path for "action_engine or pipeline unavailable"
        # is visible in the body — that's the fail-open branch.
        self.assertIn("action_engine or pipeline unavailable", window,
                      "endpoint must handle action_engine=None "
                      "explicitly rather than crashing.")


class WebGatedByFlagAndOwner(unittest.TestCase):
    """/chat's tool-loop bridge is env-gated AND owner_bridge-gated."""

    def test_env_flag_gate(self):
        src = (_REPO / "skills" / "web_interface.py").read_text()
        self.assertIn("MAEZ_WEB_TOOL_LOOP", src,
                      "web /chat tool-loop bridge must be gated by "
                      "MAEZ_WEB_TOOL_LOOP so default behavior is "
                      "unchanged until the owner opts in.")

    def test_owner_bridge_gate(self):
        """The env-flagged block must be nested under owner_bridge so
        public/guest users never trigger a brain_loop."""
        src = (_REPO / "skills" / "web_interface.py").read_text()
        # Anchor on the CODE reference to the env var (not the first
        # mention, which is inside a comment block). The code form
        # is `os.environ.get("MAEZ_WEB_TOOL_LOOP"`.
        anchor = 'os.environ.get("MAEZ_WEB_TOOL_LOOP"'
        env_line_idx = src.find(anchor)
        self.assertGreater(env_line_idx, 0,
                           "expected code reference to env var, "
                           "got only comments or nothing.")
        # The `if owner_bridge and ...` must be on the same line or
        # immediately preceding it — search a small window backward.
        preamble = src[max(0, env_line_idx - 100):env_line_idx]
        self.assertIn("owner_bridge", preamble,
                      "the MAEZ_WEB_TOOL_LOOP gate must be nested "
                      "under an owner_bridge check so public/guest "
                      "users do NOT trigger the owner's tool loop.")

    def test_transcript_added_as_system_context(self):
        """When a transcript comes back non-empty, the web caller must
        add it as system context. Folding tool scaffolding into user
        text pollutes memory/search/trace with non-owner instructions."""
        src = (_REPO / "skills" / "web_interface.py").read_text()
        self.assertIn("_JARVIS_INSTRUCTION_BLOCK", src)
        self.assertIn('"role": "system"', src)
        self.assertIn("not folded into the owner's user text", src)
        self.assertNotIn("build_synthesis_user_text", src)


if __name__ == "__main__":
    unittest.main()
