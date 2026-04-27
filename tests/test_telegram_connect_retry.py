# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Telegram connect-retry regression test (2026-04-27 incident).

The owner's TelegramVoice surface failed to come up at boot when DNS
wasn't ready, retried 8 times with exponential backoff (~75 seconds
total), then gave up permanently. The daemon kept running for hours
with `surface v2 connect() returned False` while outgoing sends still
worked through a separate kept-alive loop — but incoming polling was
dead until manual restart.

The fix in skills/surface/telegram_adapter.py replaces the bounded
8-attempt loop with indefinite retry (capped backoff, periodic
heartbeat log). This regression test locks that invariant so the
cap can't quietly come back.

Source-level assertion (not behavioral) — mocking the full
python-telegram-bot Application chain is heavy, and the behavior
we're locking is structural: there must be no fixed cap on
connect-time network-error retries.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_ADAPTER = _REPO / "skills" / "surface" / "telegram_adapter.py"


class ConnectRetryIsIndefinite(unittest.TestCase):
    """The connect loop retries forever on transient network errors.
    A fixed cap (the prior `_max_connect = 8`) is the regression."""

    def setUp(self):
        self.src = _ADAPTER.read_text()

    def test_no_fixed_max_connect_constant(self):
        # The prior bug was `_max_connect = 8` followed by
        # `for _attempt in range(_max_connect):` and a raise on the
        # last attempt. None of those tokens may appear together.
        self.assertNotIn(
            "_max_connect = 8",
            self.src,
            "regression: bounded connect cap reintroduced — see "
            "tests/test_telegram_connect_retry.py for context",
        )

    def test_initialize_loop_uses_while_true(self):
        # The fix is a `while True:` loop around `_app.initialize()`.
        # We don't lock the exact text, only the structural shape:
        # the initialize call must live inside an unbounded loop.
        m = re.search(
            r"while True:\s*\n\s*try:\s*\n\s*await self\._app\.initialize\(\)",
            self.src,
        )
        self.assertIsNotNone(
            m,
            "connect() must call _app.initialize() inside a "
            "`while True:` retry loop — bounded retries leave the "
            "bot permanently dead on slow-boot DNS failure.",
        )

    def test_only_retries_on_transient_errors(self):
        # Auth / config errors must NOT be swept into the indefinite
        # loop. Only NetworkError / TimedOut / OSError are retried.
        # If a future change broadens the except clause, this test
        # forces a re-think.
        m = re.search(
            r"except\s*\(\s*NetworkError\s*,\s*TimedOut\s*,\s*OSError\s*\)",
            self.src,
        )
        self.assertIsNotNone(
            m,
            "connect() retry must catch ONLY transient network "
            "errors — auth/config errors should propagate, not "
            "infinite-loop the bot.",
        )

    def test_backoff_cap_at_60_seconds(self):
        # The backoff floor matters: too short = thrashing during a
        # real outage, too long = slow recovery once network returns.
        # 60s is the cap we settled on. Lock it loosely (looking for
        # the literal `60` in proximity to a backoff calculation).
        # If a future maintainer changes the cap, they must update
        # this test deliberately.
        # Find the connect-retry block and check it contains a 60s
        # cap on the wait value. Loose match (don't lock the exact
        # backoff formula) but strict that the literal 60 cap exists.
        connect_block = self.src[self.src.index("Start polling — retry initialize") :][:2000]
        self.assertRegex(
            connect_block,
            r"wait\s*=.*\b60\b",
            "connect() backoff must cap at 60s — this is the "
            "operational floor between thrashing and slow recovery.",
        )

    def test_heartbeat_logging_for_long_outages(self):
        # During a long outage, the journal must not go silent.
        # The fix logs every 10th attempt after the first 8.
        # Lock that the modulo guard exists somewhere near the
        # connect retry block.
        connect_block = self.src[self.src.index("Start polling — retry initialize") :][:2000]
        self.assertIn(
            "_attempt % 10 == 0",
            connect_block,
            "long outages must log a heartbeat every 10 attempts so "
            "the bot's still-trying state stays visible in journal.",
        )


if __name__ == "__main__":
    unittest.main()
