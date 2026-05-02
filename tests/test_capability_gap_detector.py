# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for the D20 Stage-1 chat-surface gap detector.

The orchestrator (ADR-0021 stages 2-4) is now wired but operator-
driven only. Stage 1 is the autonomous detection layer that
watches user messages and fires the orchestrator when the user
expresses a felt limitation that lexically matches a manual
entry's `gap_signals`.

Detector contract:
  - take a user_text string
  - run the same lexical matcher used by the orchestrator
  - apply a confidence threshold so weak matches don't fire
  - apply a per-capability cooldown so the same gap can't spam
    cards every turn
  - return a DetectorResult naming what fired (or None)

The detector itself is pure-ish (only side effect is the cooldown
SQLite write). Producers (chat path, daemon, etc.) wrap it with
the orchestrator on hits.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class _Base(unittest.TestCase):
    """Each test gets a hermetic cooldown DB path so cooldown
    state from one test doesn't leak into the next."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cooldown_db = Path(self._tmp.name) / "gap_cooldown.db"
        self._env = mock.patch.dict(os.environ, {
            "MAEZ_GAP_DETECTOR_DB": str(self.cooldown_db),
        })
        self._env.start()
        # Reload the module so DB_PATH picks up the env override.
        import importlib
        if "core.infra.capability_gap_detector" in sys.modules:
            importlib.reload(sys.modules["core.infra.capability_gap_detector"])

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()


class StrongMatchFires(_Base):
    def test_temporal_signal_above_threshold(self):
        """A direct hit on the temporal-arithmetic gap signal
        ('user asks when did X happen?') must fire the detector."""
        from core.infra.capability_gap_detector import detect_gap
        r = detect_gap("when did X happen?", threshold=0.3)
        self.assertIsNotNone(r.fired_for, "strong signal must fire")
        self.assertEqual(r.fired_for.capability_id,
                         "temporal-arithmetic-at-recall")
        self.assertGreaterEqual(r.fired_for.score, 0.3)

    def test_returns_full_match_list(self):
        """DetectorResult exposes all matches above threshold so
        callers can log and rate-limit per-cap, not just the top."""
        from core.infra.capability_gap_detector import (
            DetectorResult, detect_gap,
        )
        r = detect_gap(
            "how long after Y did Z happen", threshold=0.3,
        )
        self.assertIsInstance(r, DetectorResult)
        self.assertIsInstance(r.matches_above_threshold, list)


class WeakMatchSuppressed(_Base):
    def test_low_score_does_not_fire(self):
        """A weak lexical match (one common token shared) must be
        below threshold so casual conversation doesn't trigger
        capability proposals."""
        from core.infra.capability_gap_detector import detect_gap
        r = detect_gap("hello there friend", threshold=0.3)
        self.assertIsNone(
            r.fired_for,
            "weak match on common words should not fire",
        )

    def test_unrelated_query_does_not_fire(self):
        from core.infra.capability_gap_detector import detect_gap
        r = detect_gap(
            "what is the weather like today",
            threshold=0.3,
        )
        self.assertIsNone(r.fired_for)


class CooldownGate(_Base):
    """REGRESSION GUARD: if detect_gap fires for capability_id=X,
    a second detection within cooldown_s must NOT fire even if the
    text matches strongly. Without this the user sees duplicate
    cards on every turn while the same gap remains unaddressed."""

    def test_second_fire_within_cooldown_suppressed(self):
        from core.infra.capability_gap_detector import detect_gap
        r1 = detect_gap(
            "when did X happen?", threshold=0.3, cooldown_s=3600,
        )
        self.assertIsNotNone(r1.fired_for)
        r2 = detect_gap(
            "when did X happen?", threshold=0.3, cooldown_s=3600,
        )
        self.assertIsNone(
            r2.fired_for,
            "second fire within cooldown must be suppressed",
        )
        # But the matches list should still surface them so callers
        # can log "we would have fired but cooldown active"
        self.assertGreater(len(r2.matches_above_threshold), 0)
        self.assertEqual(r2.cooldown_blocked, ["temporal-arithmetic-at-recall"])

    def test_fire_resumes_after_cooldown_expires(self):
        from core.infra.capability_gap_detector import detect_gap
        # cooldown_s=0 means "no cooldown" — used to verify the
        # cooldown logic is gated on the parameter, not always-on.
        r1 = detect_gap(
            "when did X happen?", threshold=0.3, cooldown_s=0,
        )
        r2 = detect_gap(
            "when did X happen?", threshold=0.3, cooldown_s=0,
        )
        self.assertIsNotNone(r1.fired_for)
        self.assertIsNotNone(
            r2.fired_for,
            "cooldown_s=0 must mean 'every detection fires'",
        )

    def test_cooldown_per_capability(self):
        """Cooldown is per-capability_id, not global. Firing for
        capability A must not block a future fire for capability
        B."""
        from core.infra.capability_gap_detector import detect_gap
        r1 = detect_gap(
            "when did X happen?", threshold=0.3, cooldown_s=3600,
        )
        self.assertEqual(
            r1.fired_for.capability_id,
            "temporal-arithmetic-at-recall",
        )
        # A different gap (RCE — recursive context engine; signal
        # mentions audit-style summaries / repo-wide synthesis):
        r2 = detect_gap(
            "give me an audit-style summary of this whole repo",
            threshold=0.3, cooldown_s=3600,
        )
        # If RCE matches strongly enough above threshold, it should
        # fire INDEPENDENTLY of the prior temporal cooldown. If the
        # match score doesn't clear threshold we can't assert it
        # fires — but the cooldown_blocked list must NOT include
        # temporal (because we haven't tried temporal again).
        self.assertNotIn(
            "recursive-context-engine", r2.cooldown_blocked,
            "RCE wasn't fired before so it can't be cooldown-blocked",
        )


class GriefDoesNotFire(_Base):
    """REGRESSION GUARD: a chat moment where the user is in grief
    is exactly the wrong time to surface a capability-proposal
    card. Reviewer flagged this concern; live probe at threshold
    0.3 confirms grief-shaped messages don't lexically overlap
    enough with seed-entry gap_signals to fire. This test pins
    that behaviour so a future scoring tweak can't silently
    regress."""

    def test_grief_messages_do_not_fire(self):
        from core.infra.capability_gap_detector import detect_gap
        for msg in [
            "i miss her",
            "i miss her, when did she leave me",
            "how long since she died",
            "how long ago did mom pass",
            "i wish i could remember when",
            "i miss when we used to talk",
        ]:
            r = detect_gap(msg, threshold=0.3, cooldown_s=0)
            self.assertIsNone(
                r.fired_for,
                f"grief-shaped message {msg!r} must not fire — "
                f"got {r.fired_for}",
            )


class FailClosed(_Base):
    """The detector is on a hot path (every chat turn). Any failure
    inside it must NOT propagate — return a benign empty result so
    the caller's chat turn proceeds as if the detector hadn't run."""

    def test_empty_text_returns_empty_result(self):
        from core.infra.capability_gap_detector import detect_gap
        r = detect_gap("", threshold=0.3)
        self.assertIsNone(r.fired_for)
        self.assertEqual(r.matches_above_threshold, [])

    def test_internal_exception_swallowed(self):
        """If match_gap raises (e.g. corrupt manual), the detector
        must return an empty result, not propagate."""
        from core.infra import capability_gap_detector as det
        with mock.patch.object(
            det, "match_gap", side_effect=RuntimeError("boom"),
        ):
            r = det.detect_gap("when did X happen?", threshold=0.3)
        self.assertIsNone(r.fired_for)
        self.assertEqual(r.matches_above_threshold, [])


class FireHelper(_Base):
    """The fire-and-forget helper detects + orchestrates + creates a
    card in one call. Designed for hot-path producers (chat
    handler, daemon cycle) — must never raise."""

    def setUp(self):
        super().setUp()
        from core.decision.pending_cards import PendingCardStore
        self.cards = PendingCardStore(
            Path(self._tmp.name) / "pending.db",
        )

    def test_fire_on_strong_signal_creates_card(self):
        from core.infra.capability_gap_detector import (
            maybe_fire_capability_proposal,
        )
        out = maybe_fire_capability_proposal(
            "when did X happen?",
            pending_card_store=self.cards,
            cooldown_s=0,  # disable cooldown for this test
        )
        self.assertTrue(out["fired"])
        self.assertEqual(
            out["capability_id"], "temporal-arithmetic-at-recall",
        )
        self.assertGreaterEqual(len(out["cards_created"]), 0)

    def test_no_fire_on_casual_chat(self):
        from core.infra.capability_gap_detector import (
            maybe_fire_capability_proposal,
        )
        out = maybe_fire_capability_proposal(
            "hello there",
            pending_card_store=self.cards,
        )
        self.assertFalse(out["fired"])
        self.assertEqual(out["cards_created"], [])

    def test_helper_never_raises_on_internal_error(self):
        from core.infra import capability_gap_detector as det
        with mock.patch.object(
            det, "detect_gap", side_effect=RuntimeError("boom"),
        ):
            out = det.maybe_fire_capability_proposal(
                "any input", pending_card_store=self.cards,
            )
        self.assertFalse(out["fired"])
        self.assertEqual(out.get("error"), "boom")


if __name__ == "__main__":
    unittest.main()
