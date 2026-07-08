# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Regression guards for 2026-05-04 T1 schema-level races.

T1.1: pending-card supersession must be atomic. The old code did
SELECT open cards -> expire each via a separate public transition ->
INSERT new card. Two concurrent creators could both see no open card
and both insert OPEN rows for one chat.

T1.5: subscription_proxy budget check must serialize per adapter.
The old code checked hourly/daily caps, awaited the external adapter,
then recorded the call. Two concurrent requests could both pass the
cap check before either recorded usage.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import sqlite3
import tempfile
import threading
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException


class PendingCardsSupersessionRaceGuard(unittest.TestCase):
    def test_create_card_does_not_expire_via_public_transition_loop(self):
        """Atomic supersession must happen in the same SQLite write
        transaction as INSERT. Calling ``self.expire`` after a SELECT
        opens the TOCTOU window this test exists to keep closed."""
        from core.decision.pending_cards import PendingCardStore

        src = textwrap.dedent(inspect.getsource(PendingCardStore.create_card))
        self.assertNotIn(
            "self.expire(",
            src,
            "create_card must supersede existing cards with an in-transaction "
            "UPDATE, not a SELECT + public expire() loop",
        )
        self.assertIn(
            "BEGIN IMMEDIATE",
            src,
            "create_card must acquire a SQLite write transaction before "
            "superseding + inserting",
        )

    def test_two_same_chat_creates_leave_one_open_card(self):
        from core.decision.pending_cards import CardStatus, PendingCardStore
        from tests._helpers.concurrent import run_two_threads

        with tempfile.TemporaryDirectory() as td:
            store = PendingCardStore(db_path=Path(td) / "cards.db")

            def make_card(n: int):
                return store.create_card(
                    action="run_shell",
                    params={"cmd": f"echo {n}"},
                    reason=f"proposal {n}",
                    plain_english=f"proposal {n}",
                    chat_id="chat-1",
                    user_id="owner",
                )

            a, b = run_two_threads(
                lambda: make_card(1),
                lambda: make_card(2),
                timeout=5.0,
            )

            self.assertTrue(a.ok, a.exception)
            self.assertTrue(b.ok, b.exception)
            with sqlite3.connect(Path(td) / "cards.db") as con:
                rows = con.execute(
                    "SELECT request_id, status FROM pending_cards "
                    "WHERE chat_id = ?",
                    ("chat-1",),
                ).fetchall()
            open_rows = [
                rid for rid, status in rows
                if status == CardStatus.OPEN.value
            ]
            self.assertEqual(
                len(open_rows), 1,
                f"expected one active card after same-chat race, got {rows!r}",
            )


class PendingCardsTransitionCasRaceGuard(unittest.TestCase):
    def test_two_concurrent_terminal_transitions_leave_one_winner(self):
        from core.decision import pending_cards as cards_mod
        from core.decision.pending_cards import CardStatus, CardStoreError, PendingCardStore
        from tests._helpers.concurrent import run_two_threads

        original_connect = cards_mod.sqlite3.connect
        update_barrier = threading.Barrier(2)

        class BarrierConnection:
            def __init__(self, inner):
                self._inner = inner

            @property
            def row_factory(self):
                return self._inner.row_factory

            @row_factory.setter
            def row_factory(self, value):
                self._inner.row_factory = value

            def __enter__(self):
                self._inner.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._inner.__exit__(exc_type, exc, tb)

            def close(self):
                return self._inner.close()

            def execute(self, sql, parameters=()):
                normalized = " ".join(str(sql).split()).upper()
                if normalized.startswith("UPDATE PENDING_CARDS SET"):
                    update_barrier.wait(timeout=5.0)
                return self._inner.execute(sql, parameters)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def connect_with_update_barrier(*args, **kwargs):
            return BarrierConnection(original_connect(*args, **kwargs))

        with tempfile.TemporaryDirectory() as td:
            store = PendingCardStore(Path(td) / "cards.db")
            card = store.create_card(
                action="quote_stock",
                params={"ticker": "MAEZ"},
                reason="race guard",
                proposed_action_summary="Look up the MAEZ quote.",
            )

            with mock.patch.object(cards_mod.sqlite3, "connect", side_effect=connect_with_update_barrier):
                deny_result, expire_result = run_two_threads(
                    lambda: store.deny(card.request_id, user_id="owner", via="cockpit"),
                    lambda: store.expire(card.request_id, "abandoned"),
                    timeout=5.0,
                )

            results = (deny_result, expire_result)
            successes = [r.return_value for r in results if r.ok]
            failures = [r.exception for r in results if not r.ok]
            final = store.get(card.request_id)

        self.assertEqual(
            len(successes),
            1,
            f"exactly one transition should win; got successes={successes!r} failures={failures!r}",
        )
        self.assertEqual(len(failures), 1, failures)
        self.assertIsInstance(failures[0], CardStoreError)
        self.assertIsNotNone(final)
        self.assertEqual(final.status, successes[0].status)
        self.assertIn(final.status, {CardStatus.DENIED.value, CardStatus.EXPIRED.value})


class SubscriptionProxyBudgetRaceGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(
            os.environ,
            {
                "MAEZ_SUBSCRIPTION_PROXY_DB": str(self._db_path),
                "MAEZ_FAKE_HOURLY_CAP": "1",
                "MAEZ_FAKE_DAILY_CAP": "1",
            },
        )
        self._env.start()
        from core.subscription_proxy import server as _srv

        importlib.reload(_srv)
        self.srv = _srv

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def test_two_concurrent_requests_do_not_both_spend_cap_one(self):
        from core.subscription_proxy.adapters.base import CallResult

        class SlowFakeAdapter:
            name = "fake"

            def __init__(self):
                self.calls = 0

            def handles_model(self, model: str) -> bool:
                return model == "fake-model"

            def health(self) -> dict:
                return {"adapter": self.name}

            async def call(self, *, prompt, system_prompt=None, model=""):
                self.calls += 1
                # Long enough for the second request to reach the
                # budget gate if the gate is not serialized.
                await asyncio.sleep(0.05)
                return CallResult(
                    reply=f"ok-{self.calls}",
                    model_used=model,
                    input_toks=1,
                    output_toks=1,
                )

        class FakeRequest:
            headers = {"x-maez-caller": "race-test"}

            async def json(self):
                return {
                    "model": "fake-model",
                    "messages": [{"role": "user", "content": "hi"}],
                }

        adapter = SlowFakeAdapter()
        self.srv.ADAPTERS = [adapter]
        self.srv.DEFAULT_CAPS["fake"] = {"hourly": 1, "daily": 1}

        async def run_pair():
            return await asyncio.gather(
                self.srv.chat_completions(FakeRequest()),
                self.srv.chat_completions(FakeRequest()),
                return_exceptions=True,
            )

        results = asyncio.run(run_pair())
        successes = [
            r for r in results
            if not isinstance(r, BaseException)
        ]
        throttles = [
            r for r in results
            if isinstance(r, HTTPException) and r.status_code == 429
        ]

        self.assertEqual(len(successes), 1, results)
        self.assertEqual(len(throttles), 1, results)
        self.assertEqual(
            adapter.calls, 1,
            "second request must be stopped at budget gate before adapter.call",
        )
        with sqlite3.connect(self._db_path) as con:
            ok_rows = con.execute(
                "SELECT COUNT(*) FROM calls WHERE adapter = 'fake' "
                "AND status = 'ok'",
            ).fetchone()[0]
        self.assertEqual(ok_rows, 1)


if __name__ == "__main__":
    unittest.main()
