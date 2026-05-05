# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for T1.9 hygiene fix (Codex 2026-05-04 + 05).

The original T1.9 fix (commit 10220d9, morning of 2026-05-04) added
a thread.join(timeout=5.0) after `_loop.call_soon_threadsafe
(_loop.stop)` to bound the shutdown wait. Codex's R3.5+R4 deploy
verification (2026-05-04 evening) confirmed empirically that the
join doesn't actually prevent the surface-v2 traceback — the
`call_soon_threadsafe(_loop.stop)` interrupts the runner's
`await _asyncio.sleep(1.0)` mid-await, asyncio.run() raises
RuntimeError("Event loop stopped before Future completed"), the
runner's outer try/except logs it, and only THEN does the join sit
for an already-dead thread.

The cooperative shutdown signal `self.running = False` is set FIRST
(daemon stop() at line ~4340) — the runner's `while self.running:`
loop would exit naturally on the next sleep boundary (≤1s). The
explicit `_loop.stop()` is redundant and harmful: it produces the
traceback without giving the runner time to exit cleanly via
`await adapter.disconnect()`.

Contract enforced:
- daemon.stop()'s surface_v2 block must NOT call
  _loop.call_soon_threadsafe(_loop.stop). The cooperative
  `self.running = False` flag (set earlier in stop()) is the
  shutdown signal; the thread.join with timeout bounds the wait.
- The block must still call _surface_v2_thread.join(timeout=...)
  so SIGKILL doesn't race a still-running thread.
- A fallback comment notes the design: if the runner ever hangs
  past the join timeout, future-Maez can add a hard _loop.stop()
  with explicit RuntimeError suppression in the runner.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class T1_9_HygieneNoExternalLoopStop(unittest.TestCase):
    """REGRESSION GUARD: daemon.stop()'s surface_v2 block must not
    forcibly stop the runner's event loop — that's the source of
    the `Event loop stopped before Future completed` traceback.
    Cooperative shutdown via `self.running = False` is sufficient
    given the runner's structure."""

    def test_surface_v2_block_does_not_call_loop_stop(self):
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        # Locate the surface_v2 stop block. Bounded by the next
        # `self.public_bot.stop()` line.
        try:
            start = src.index('_thread = getattr(self, "_surface_v2_thread"')
        except ValueError:
            self.fail(
                "could not locate surface_v2 stop block by anchor "
                "`_thread = getattr(self, \"_surface_v2_thread\"` "
                "— refactor must update this regression guard"
            )
        end = src.index("self.public_bot.stop()", start)
        block = src[start:end]
        self.assertNotIn(
            "_loop.call_soon_threadsafe(_loop.stop)",
            block,
            "surface_v2 stop block must NOT forcibly stop the "
            "runner's event loop — that produces the "
            "`Event loop stopped before Future completed` "
            "traceback. Cooperative shutdown via `self.running "
            "= False` (set earlier in stop()) is sufficient.",
        )

    def test_surface_v2_block_still_joins_thread(self):
        """The thread.join (T1.9 morning fix) must remain — it's
        the bound on shutdown wait, distinct from the loop.stop
        problem we're now removing."""
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        start = src.index('_thread = getattr(self, "_surface_v2_thread"')
        end = src.index("self.public_bot.stop()", start)
        block = src[start:end]
        self.assertIn(
            "_surface_v2_thread", block,
            "stop block must still reference the thread to join it",
        )
        self.assertIn(
            ".join(", block,
            "stop block must still call thread.join() so SIGKILL "
            "doesn't race a still-running thread",
        )

    def test_self_running_false_set_before_surface_v2_block(self):
        """Source-pin: `self.running = False` must be assigned
        BEFORE the surface_v2 stop block runs, so the runner's
        while-loop can exit cooperatively while the join waits."""
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        running_match_idx = src.find("self.running = False")
        surface_v2_idx = src.index('_thread = getattr(self, "_surface_v2_thread"')
        self.assertGreaterEqual(
            running_match_idx, 0,
            "stop() must set `self.running = False` to signal the "
            "runner cooperatively",
        )
        self.assertLess(
            running_match_idx, surface_v2_idx,
            "self.running = False must precede the surface_v2 stop "
            "block so the runner sees the shutdown signal before "
            "the join begins waiting",
        )


if __name__ == "__main__":
    unittest.main()
