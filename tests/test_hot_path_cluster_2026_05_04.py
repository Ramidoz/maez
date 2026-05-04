# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the hot-path cluster (T1.8 + T1.11 + T1.12)
from the 2026-05-04 15-agent audit.

T1.8 — propose_tests --write covenant violation
  Audit found: the CLI's --write branch writes generated test code
  straight to disk without any diff review. Self-dev covenant
  requires diff-then-approve.

T1.11 — gap-detector hook misses interceptor success paths
  Audit found: the D20 Stage-1 gap-sense fires inside the
  try/finally that wraps `_process_message`. Every interceptor
  early-return (offer-binding, card-reply, proposal, dream-proposal,
  web-search) skips that finally — D20 is blind to those messages.

T1.12 — interrupt-queue race in `_handle_message`
  Audit found: `self._generating = True` is set BEFORE
  `self._interrupt_queue = asyncio.Queue()`. Even though pure
  asyncio shouldn't preempt the gap, the TOCTOU window is real if
  any future await is ever introduced.

Tests are source-level where the runtime test would require booting
the daemon / Telegram polling thread / live Claude tier.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── T1.8 — propose_tests --write covenant gate ───────────────────────


class T1_8_ProposeTestsWriteCovenantGate(unittest.TestCase):
    """REGRESSION GUARD for T1.8: the `propose_tests --write` CLI
    branch must not write test code to disk without an explicit
    diff-reviewed acknowledgment flag."""

    def test_write_branch_requires_review_flag(self):
        path = REPO / "core" / "self_dev" / "__init__.py"
        src = path.read_text()
        # Locate the --write branch in the propose_tests CLI handler.
        # It begins with `if args.write:` and ends with `return 0` of
        # that branch.
        try:
            start = src.index("if args.write:")
        except ValueError:
            self.fail(
                "could not locate `if args.write:` in propose_tests CLI "
                "— refactor must update this regression guard"
            )
        # Take ~80 lines of slack to capture the branch body.
        end = start + 4000
        block = src[start:end]
        # The covenant gate flag — exact name pinned so a refactor
        # that drops it lights this test up.
        self.assertIn(
            "i_have_reviewed_the_diff",
            block,
            "propose_tests --write branch must check for an "
            "`--i-have-reviewed-the-diff` co-flag before writing "
            "to disk; without it the self-dev covenant is bypassed",
        )

    def test_write_argparse_declares_review_flag(self):
        """The argparse layer must declare the
        --i-have-reviewed-the-diff flag so the CLI accepts it."""
        path = REPO / "core" / "self_dev" / "__init__.py"
        src = path.read_text()
        self.assertIn(
            "--i-have-reviewed-the-diff",
            src,
            "argparse must register --i-have-reviewed-the-diff so "
            "the CLI accepts the covenant-gate co-flag",
        )


# ── T1.11 — gap-detector early hook ──────────────────────────────────


class T1_11_GapDetectorEarlyHook(unittest.TestCase):
    """REGRESSION GUARD for T1.11: a gap-sense fire-and-forget
    must occur EARLY in _handle_message — before the first
    interceptor runs — so messages handled by interceptors
    (offer-binding, card-reply, proposal, dream-proposal, web-
    search) are still seen by D20."""

    def test_handle_message_fires_gap_sense_before_interceptors(self):
        path = REPO / "skills" / "telegram_voice.py"
        src = path.read_text()
        # Locate the _handle_message body.
        m = re.search(
            r"async def _handle_message\(self, update: Update, "
            r"context: ContextTypes\.DEFAULT_TYPE\):",
            src,
        )
        self.assertIsNotNone(
            m, "could not locate _handle_message definition"
        )
        body_start = m.end()
        # The body extends until the next async def at column 4.
        next_def = re.search(
            r"\n    async def ", src[body_start:],
        )
        self.assertIsNotNone(
            next_def, "could not bound _handle_message body"
        )
        body = src[body_start: body_start + next_def.start()]

        # Find the offsets of:
        #  - the FIRST `maybe_fire_capability_proposal` reference
        #  - the FIRST `_try_*_intent` interceptor call
        gap_match = re.search(
            r"maybe_fire_capability_proposal", body,
        )
        intent_match = re.search(r"self\._try_\w+_intent\(", body)

        self.assertIsNotNone(
            gap_match,
            "_handle_message must reference "
            "maybe_fire_capability_proposal at least once",
        )
        self.assertIsNotNone(
            intent_match,
            "_handle_message must reference at least one "
            "self._try_*_intent call",
        )
        self.assertLess(
            gap_match.start(), intent_match.start(),
            "FIRST maybe_fire_capability_proposal must appear "
            "BEFORE the first self._try_*_intent call so "
            "interceptor early-returns don't skip gap-sense",
        )


# ── T1.12 — interrupt-queue init order ───────────────────────────────


class T1_12_InterruptQueueInitOrder(unittest.TestCase):
    """REGRESSION GUARD for T1.12: in `_handle_message`, the
    `self._interrupt_queue = asyncio.Queue()` assignment must come
    BEFORE `self._generating = True` so there is no window where
    _generating is True with a stale / None interrupt queue."""

    def test_queue_init_precedes_generating_flag(self):
        path = REPO / "skills" / "telegram_voice.py"
        src = path.read_text()
        m = re.search(
            r"async def _handle_message\(self, update: Update, "
            r"context: ContextTypes\.DEFAULT_TYPE\):",
            src,
        )
        self.assertIsNotNone(m)
        body_start = m.end()
        next_def = re.search(
            r"\n    async def ", src[body_start:],
        )
        body = src[body_start: body_start + next_def.start()]

        # Find the FIRST `self._generating = True` and the FIRST
        # `self._interrupt_queue = asyncio.Queue()` after the
        # `if self._generating:` short-circuit branch.
        gen_true = re.search(
            r"^\s+self\._generating = True\s*$",
            body, re.MULTILINE,
        )
        queue_init = re.search(
            r"^\s+self\._interrupt_queue = asyncio\.Queue\(\)\s*$",
            body, re.MULTILINE,
        )

        self.assertIsNotNone(
            gen_true,
            "_handle_message must contain `self._generating = True`",
        )
        self.assertIsNotNone(
            queue_init,
            "_handle_message must initialize "
            "`self._interrupt_queue = asyncio.Queue()`",
        )
        self.assertLess(
            queue_init.start(), gen_true.start(),
            "queue init must come BEFORE generating-flag flip "
            "(T1.12 audit) — otherwise there is a window where "
            "a concurrent message sees _generating=True with a "
            "stale / None _interrupt_queue",
        )


if __name__ == "__main__":
    unittest.main()
