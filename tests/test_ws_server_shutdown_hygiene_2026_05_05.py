# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for ws-server shutdown hygiene
(T1.9 second-instance fix).

Yesterday's T1.9 fix (commit 5c3c677) made the surface-v2 stop
block cooperative-only — removed `_loop.call_soon_threadsafe
(_loop.stop)` because surface-v2's `_run` had a
`while self.running:` cooperative path. Codex's deploy
verification of dce9fa5 today caught the SECOND instance:
`_run_ws_server` has the same shutdown traceback shape, but
with a different structure — its serve() does
`await asyncio.Future()` (forever-await), so cooperative
shutdown isn't an option there. The `_ws_loop.call_soon_
threadsafe(_loop.stop)` in stop() is doing real work.

This commit applies the OTHER hygiene shape: catch the
expected RuntimeError("Event loop stopped before Future
completed") inside `_run_ws_server` and recognize it as
the shutdown shape during `not self.running`. Real RuntimeError
during operation still surfaces as ERROR. Same shape as the
'expected during shutdown' pattern documented in the surface_v2
hygiene fix's commit message as the alternative path.

Contract enforced:
  - `_run_ws_server` wraps run_until_complete(serve()) in
    a try/except RuntimeError block.
  - Inside the except, the function gates on self.running:
    if False (we're shutting down), log at INFO/DEBUG and
    return cleanly. If True (real bug), re-raise or log at
    ERROR.
  - The stop() block STILL calls _ws_loop.call_soon_threadsafe
    (_loop.stop) — unlike surface_v2, the WS path needs this
    to break out of the forever-await.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class WsServerCatchesShutdownRuntimeError(unittest.TestCase):
    """REGRESSION GUARD: _run_ws_server catches the expected
    RuntimeError on event-loop stop and exits cleanly during
    shutdown, instead of producing the noisy traceback that
    Codex caught on the dce9fa5 deploy."""

    def test_run_ws_server_wraps_run_until_complete_in_try(self):
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        # Locate _run_ws_server's body
        start = src.index("def _run_ws_server(self):")
        # Bound by the next def at the same indent
        end_match = src.find("\n    def ", start + 1)
        body = src[start: end_match if end_match > start else len(src)]

        self.assertIn(
            "run_until_complete(serve())", body,
            "_run_ws_server must still call run_until_complete; "
            "the fix is to wrap it in try/except, not remove it",
        )
        self.assertIn(
            "try:", body,
            "_run_ws_server must wrap run_until_complete in try/except "
            "to recognize the shutdown RuntimeError as expected",
        )
        self.assertIn(
            "RuntimeError", body,
            "_run_ws_server must catch RuntimeError "
            "(the 'Event loop stopped before Future completed' shape "
            "produced when stop() calls _loop.stop)",
        )

    def test_run_ws_server_distinguishes_shutdown_from_real_error(self):
        """When self.running is False (we're shutting down), the
        RuntimeError is expected and should NOT propagate as a
        traceback. When self.running is True, a real bug must
        still surface."""
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        start = src.index("def _run_ws_server(self):")
        end_match = src.find("\n    def ", start + 1)
        body = src[start: end_match if end_match > start else len(src)]
        self.assertIn(
            "self.running", body,
            "_run_ws_server must gate the RuntimeError handling on "
            "self.running so a real loop-crash during operation is "
            "still surfaced (not silently swallowed as 'expected "
            "shutdown')",
        )

    def test_stop_block_keeps_loop_stop_for_ws(self):
        """Unlike surface_v2 (which had a cooperative `while
        self.running:` path), the WS server does
        `await asyncio.Future()` forever — it CANNOT exit
        cooperatively. So the stop() block MUST still call
        _ws_loop.call_soon_threadsafe(_loop.stop)."""
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        # Find the WebSocket stop block
        start = src.index("if self._ws_loop is not None")
        end = src.index("\n        try:", start + 1)
        block = src[start:end]
        self.assertIn(
            "call_soon_threadsafe", block,
            "WebSocket stop block must still schedule _loop.stop "
            "— the WS server's forever-await has no cooperative "
            "exit path",
        )
        self.assertIn(
            "_ws_loop.stop", block,
            "stop() must reference _ws_loop.stop in the threadsafe "
            "schedule",
        )


if __name__ == "__main__":
    unittest.main()
