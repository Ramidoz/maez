# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the singleton-failure cluster
(T1.3 + T1.4 + T1.9) from the 2026-05-04 15-agent audit.

T1.3 — conversation_controller._card_store() silent fail-open
  Audit found: a transient pipeline_getter failure is logged at
  DEBUG and returns None. Every honesty-guard caller (7 sites)
  treats None as 'no pending card' → fail-OPEN. The user's pending
  card context gets steamrolled when the pipeline lookup is sick.

T1.4 — lived_recall entity-expansion silent swallow
  Audit found: ix.list_mentions() failures are silently absorbed
  (`except Exception: mentions = []`). Entity-index DB corruption
  produces an empty section with zero observability — looks
  identical to "no relevant entities".

T1.9 — surface v2 asyncio shutdown race
  Audit found: maez_daemon.stop() schedules the surface-v2 loop
  to stop via call_soon_threadsafe but never joins the thread.
  Connections / aiohttp / uvicorn cleanup races SIGKILL.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── T1.3 — _card_store() silent fail-open ────────────────────────────


class T1_3_CardStoreSilentFailOpen(unittest.TestCase):
    """REGRESSION GUARDS for T1.3: _card_store() must surface
    pipeline_getter failures (WARNING + counter), and the honesty-
    guard caller has_awaiting_card() must fail CLOSED — return True
    so the guard backs off — when a recent failure is on record."""

    def _ctrl(self, getter=None):
        from core.brain.conversation_controller import ConversationController
        return ConversationController(
            memory=None, pipeline=None, daemon=None,
            pipeline_getter=getter,
        )

    def test_card_store_logs_warning_and_increments_counter(self):
        def bad_getter():
            raise RuntimeError("simulated pipeline failure")

        ctrl = self._ctrl(getter=bad_getter)

        with self.assertLogs("maez", level="WARNING") as cm:
            result = ctrl._card_store()

        self.assertIsNone(result)
        self.assertEqual(
            ctrl._card_store_failures, 1,
            "_card_store_failures counter must increment on getter failure",
        )
        self.assertIsNotNone(
            ctrl._card_store_last_failure_ts,
            "_card_store_last_failure_ts must be set on failure",
        )
        self.assertTrue(
            any("pipeline_getter raised" in msg for msg in cm.output),
            f"WARNING log must mention pipeline_getter; got {cm.output}",
        )

    def test_has_awaiting_card_fails_closed_after_recent_failure(self):
        """When _card_store has failed in the last 30s, has_awaiting_card
        must return True (fail-CLOSED) so the honesty guard backs off
        rather than steamrolling whatever pending-card context the user
        already cued."""
        def bad_getter():
            raise RuntimeError("simulated")

        ctrl = self._ctrl(getter=bad_getter)
        # Trigger one failure
        ctrl._card_store()
        self.assertTrue(
            ctrl.has_awaiting_card("ch", "u"),
            "has_awaiting_card must return True after a recent "
            "pipeline_getter failure (fail-CLOSED for honesty guard)",
        )

    def test_has_awaiting_card_returns_false_when_no_pipeline_ever(self):
        """When there's no pipeline_getter (no failure, just absent),
        has_awaiting_card returns False — preserves the original
        contract for the 'controller-only / no pipeline' case."""
        ctrl = self._ctrl(getter=None)
        self.assertFalse(
            ctrl.has_awaiting_card("ch", "u"),
            "has_awaiting_card must return False when no pipeline_getter "
            "is configured at all (no failure on record)",
        )

    def test_has_awaiting_card_fails_closed_only_within_window(self):
        """Stale failures (>30s ago) should NOT keep poisoning the
        honesty guard. Old failure timestamps return to fail-OPEN
        (False) so the guard can resume normal operation."""
        ctrl = self._ctrl(getter=None)
        # Synthesize an old failure
        ctrl._card_store_failures = 1
        ctrl._card_store_last_failure_ts = 0.0  # epoch — definitely stale
        self.assertFalse(
            ctrl.has_awaiting_card("ch", "u"),
            "stale (>30s) failure must not keep has_awaiting_card "
            "fail-closed forever",
        )


# ── T1.4 — entity-expansion silent swallow ───────────────────────────


class T1_4_EntityExpansionSilentSwallow(unittest.TestCase):
    """REGRESSION GUARD for T1.4: lived_recall entity-expansion must
    log a WARNING and increment a failure counter when
    ix.list_mentions() raises, instead of silently producing an
    empty section that looks identical to 'no relevant entities'."""

    def test_list_mentions_failure_logs_warning_and_increments_counter(self):
        from core.memory import lived_recall as lr

        class _BoomIx:
            def list_mentions(self, _entity_id):
                raise RuntimeError("simulated DB corruption")

        class _Match:
            entity_id = "e1"
            canonical_name = "Foo"
            confidence = 0.9

        class _Exp:
            matched_entities = [_Match()]

        before = lr._entity_expansion_failures["count"]
        with self.assertLogs("core.memory.lived_recall", level="WARNING") as cm:
            out = lr._format_entity_expansion_section(_Exp(), _BoomIx())
        after = lr._entity_expansion_failures["count"]

        self.assertGreater(
            after, before,
            "_entity_expansion_failures counter must increment on "
            "list_mentions failure",
        )
        self.assertTrue(
            any("list_mentions" in msg for msg in cm.output),
            f"WARNING must mention list_mentions; got {cm.output}",
        )
        # Output is allowed to be the section header + the entity line
        # with "(no sessions)" — what we DON'T want is a crash or a
        # silently-empty section that swallows the visibility hint.
        self.assertIsInstance(out, str)


# ── T1.9 — surface v2 shutdown race ──────────────────────────────────


class T1_9_SurfaceV2ShutdownJoin(unittest.TestCase):
    """REGRESSION GUARD for T1.9: maez_daemon.stop()'s surface_v2
    block must join self._surface_v2_thread after scheduling
    _loop.stop, otherwise connections leak before SIGKILL.

    Source-level pin — exercising daemon.stop() from a unit test
    requires booting the daemon, which is impractical. The pin
    catches refactors that drop the join; behavioral coverage
    happens via real shutdowns in the field."""

    def test_surface_v2_block_calls_thread_join(self):
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        # Locate the surface_v2 stop block. Bounded by the next
        # `self.public_bot.stop()` line which immediately follows.
        try:
            start = src.index('if getattr(self, "_surface_v2_loop"')
        except ValueError:
            self.fail(
                "could not locate surface_v2 stop block by anchor "
                "`if getattr(self, \"_surface_v2_loop\"` — refactor "
                "must update this regression guard"
            )
        end = src.index("self.public_bot.stop()", start)
        block = src[start:end]

        self.assertIn(
            "_loop.call_soon_threadsafe(_loop.stop)", block,
            "surface_v2 stop block must still schedule _loop.stop",
        )
        self.assertIn(
            "_surface_v2_thread", block,
            "surface_v2 stop block must reference _surface_v2_thread "
            "to join it after scheduling stop",
        )
        self.assertIn(
            ".join(", block,
            "surface_v2 stop block must call thread.join() after "
            "scheduling _loop.stop — without it, connections leak",
        )


if __name__ == "__main__":
    unittest.main()
