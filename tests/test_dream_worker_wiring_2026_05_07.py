# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for slice 1.3 dream-worker bounding wiring.

The bounded-worker primitive in core/health/bounded_worker.py has its
own unit tests (tests/test_bounded_worker.py). These tests pin the
PRODUCTION wiring in daemon/maez_daemon.py + core/evolution/dream_state.py
so a future refactor that bypasses the worker (or removes it entirely)
fails loudly here instead of silently regressing the thread-leak fix.

Specifically guarded:
  - MaezDaemon constructs ``self._dream_worker`` of type
    ``BoundedSingletonWorker``.
  - The dream-cycle spawn site uses ``self._dream_worker.submit(...)``,
    NOT a direct ``threading.Thread(... name="dream-cycle" ...)``.
  - ``MaezDaemon.stop()`` calls ``self._dream_worker.shutdown(...)``
    with a bounded timeout before the daemon exits.
  - ``dream_state.run_dream_cycle`` keeps the start-of-cycle
    ``self._last_dream_at = now`` cooldown claim. Slice 1.3's bounded
    worker is defense-in-depth; if the cooldown ever moves to the END
    of the cycle, the bounded worker becomes load-bearing for re-spawn
    safety. The cross-file coupling note must be present so this
    intent doesn't get lost in a refactor.

Style mirrors tests/test_t1_9_shutdown_hygiene_2026_05_05.py — read the
source as text and assert specific substrings, no daemon construction.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class DaemonDreamWorkerWiringTests(unittest.TestCase):
    """Pin the slice 1.3 production wiring. If any of these fail, the
    dream-cycle thread-leak fix has regressed."""

    @classmethod
    def setUpClass(cls):
        cls.daemon_src = (REPO / "daemon" / "maez_daemon.py").read_text()
        cls.dream_src = (
            REPO / "core" / "evolution" / "dream_state.py"
        ).read_text()

    # ── construction ──────────────────────────────────────────────────

    def test_bounded_worker_is_imported(self):
        self.assertIn(
            "from core.health.bounded_worker import BoundedSingletonWorker",
            self.daemon_src,
            "daemon must import BoundedSingletonWorker — slice 1.3 wiring",
        )

    def test_dream_worker_attribute_is_constructed(self):
        # Match conservative: any call shape constructing the worker
        # against the dream-cycle name.
        self.assertIn(
            'self._dream_worker = BoundedSingletonWorker(name="dream-cycle")',
            self.daemon_src,
            "daemon.__init__ must construct self._dream_worker as a "
            "BoundedSingletonWorker named 'dream-cycle'",
        )

    # ── spawn site uses the worker ────────────────────────────────────

    def test_dream_spawn_uses_submit(self):
        self.assertIn(
            "self._dream_worker.submit(_run_dream_bg)",
            self.daemon_src,
            "the dream-cycle spawn site must go through "
            "self._dream_worker.submit(...) — direct Thread.start() "
            "would re-introduce the slice 1.3 thread leak",
        )

    def test_no_direct_thread_start_for_dream_cycle(self):
        """Look for the historical leak shape: a threading.Thread
        targeting _run_dream_bg directly. The bounded worker spawns
        threads internally with the worker's own naming scheme
        (f"{name}-{id(self):x}"), so a direct ``threading.Thread(
        target=_run_dream_bg, ...)`` in the daemon module is a
        regression.

        ``name="dream-cycle"`` is permitted ONLY in the
        BoundedSingletonWorker construction — that is the worker's
        identity, not a direct Thread name.
        """
        # Most precise indicator: a direct threading.Thread targeting
        # _run_dream_bg. Either at import-time or as a multi-line
        # constructor call.
        self.assertNotIn(
            "threading.Thread(target=_run_dream_bg",
            self.daemon_src,
            "direct threading.Thread(target=_run_dream_bg, ...) must "
            "not appear; submit() through the worker is the only path",
        )
        # Multi-line variant defensively too — the original code used
        # a multi-line keyword-call form.
        self.assertNotIn(
            "threading.Thread(\n                        target=_run_dream_bg",
            self.daemon_src,
            "multi-line threading.Thread(target=_run_dream_bg, ...) must "
            "not reappear",
        )
        # Sanity: the only occurrence of name="dream-cycle" should be
        # in the BoundedSingletonWorker construction. If it appears
        # anywhere else (e.g., a direct Thread), that's a regression.
        occurrences = self.daemon_src.count('name="dream-cycle"')
        self.assertEqual(
            occurrences, 1,
            f'expected exactly 1 occurrence of name="dream-cycle" '
            f'(in BoundedSingletonWorker construction); got {occurrences}',
        )
        # And that one occurrence must be on the BoundedSingletonWorker
        # line, not on a Thread() call.
        self.assertIn(
            'BoundedSingletonWorker(name="dream-cycle")',
            self.daemon_src,
            'the lone name="dream-cycle" must be on the '
            'BoundedSingletonWorker construction line',
        )

    # ── shutdown wiring ───────────────────────────────────────────────

    def test_stop_calls_dream_worker_shutdown(self):
        self.assertIn(
            "self._dream_worker.shutdown(timeout=5.0)",
            self.daemon_src,
            "MaezDaemon.stop() must call self._dream_worker.shutdown("
            "timeout=...) so an in-flight dream cycle gets a bounded "
            "window to finish writing to memory.db before exit",
        )

    def test_stop_uses_shutdown_not_join(self):
        # join() is wait-only and leaves the worker reusable; shutdown
        # is the one-way close. stop() must use shutdown to prevent a
        # stale loop-tail caller from re-spawning post-stop.
        self.assertNotIn(
            "self._dream_worker.join(",
            self.daemon_src,
            "stop() must use self._dream_worker.shutdown(...), not "
            "join(...). join leaves the worker reusable; only shutdown "
            "blocks post-stop submits.",
        )

    # ── cooldown coupling note in dream_state.py ──────────────────────

    def test_dream_state_keeps_start_of_cycle_cooldown(self):
        """The cooldown gate's correctness depends on _last_dream_at
        being set at the START of run_dream_cycle, not at the end.
        If that ever moves, the bounded worker becomes the only re-
        spawn safety — and the cross-file note must remain to flag
        that coupling for the next refactor.

        Position is verified, not just existence: within
        ``run_dream_cycle``, the FIRST ``self._last_dream_at = now``
        must appear BEFORE the first real-work call (the recent_raw
        memory fetch). 'Exists somewhere' is not a position guard;
        an end-of-function assignment would still pass that.

        Note: dream_state.py legitimately has a SECOND
        ``self._last_dream_at = now`` later in the cycle that extends
        the cooldown after a successful proposal lands. That's
        intentional and not what this test guards. The guard scope is
        the FIRST assignment within the function bounds.
        """
        # Locate the function bounds: from `def run_dream_cycle` to
        # the next `\n    def ` (next method on the class).
        func_start = self.dream_src.index("def run_dream_cycle(self")
        # Look for the next method definition after our function start.
        next_def = self.dream_src.find("\n    def ", func_start + 1)
        self.assertGreater(
            next_def, func_start,
            "could not locate end of run_dream_cycle (no following "
            "method definition); test needs to be re-anchored if the "
            "file structure changed",
        )
        body = self.dream_src[func_start:next_def]

        # The assignment must exist within the function.
        self.assertIn(
            "self._last_dream_at = now",
            body,
            "run_dream_cycle must update _last_dream_at to claim the "
            "cooldown slot",
        )
        # ...AND the FIRST occurrence in the function must appear
        # before the first real-work call.
        # `self.memory.recent_raw(` is the first I/O call inside
        # run_dream_cycle; if the assignment lands after it, the
        # cooldown is set too late.
        assignment_idx = body.index("self._last_dream_at = now")
        work_idx = body.index("self.memory.recent_raw(")
        self.assertLess(
            assignment_idx, work_idx,
            "first self._last_dream_at = now in run_dream_cycle must "
            "appear BEFORE the first real-work call "
            "(self.memory.recent_raw). End-of-function placement would "
            "let a long cycle re-spawn before the cooldown is claimed "
            "— exactly the bug slice 1.3 guards. "
            f"Saw assignment at body offset {assignment_idx}, "
            f"work at body offset {work_idx}.",
        )

        # The slice 1.3 coupling comment must remain so a future
        # refactor doesn't silently move the cooldown update without
        # also touching the daemon's bounded worker spawn site.
        self.assertIn(
            "Slice 1.3 cross-file coupling",
            body,
            "the slice 1.3 cross-file coupling note must remain in "
            "dream_state.run_dream_cycle so a future refactor doesn't "
            "silently break re-spawn safety",
        )


if __name__ == "__main__":
    unittest.main()
