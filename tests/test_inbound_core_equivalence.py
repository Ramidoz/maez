# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Equivalence harness for the SLICE 0 inbound-core extraction.

THE HARD GATE. This proves byte-identity between:
  - flag OFF (MAEZ_INBOUND_CORE_V2 unset): MaezMessageHandler.__call__'s
    untouched inline body, and
  - flag ON  (MAEZ_INBOUND_CORE_V2="1"):  daemon.inbound_core.run_inbound_turn
    driven via the adapter's injected descriptor.

Strategy: a FakeDaemon + FakeEvent + fake dependencies that RECORD every
dependency interaction into a single shared call-trace list. We drive the SAME
event through __call__ TWICE — once flag-off, once flag-on — and assert the
recorded call-trace AND the return value are IDENTICAL. That trace-equality
across the two flag states IS the byte-identity proof.

NO real brain / LLM / daemon: every heavyweight dependency
(run_brain_loop, observe_turn, handle_message, the pipeline, memory) is a fake
that records its inputs. The shared executor is patched to run callables
inline on the current loop so the recorded order is deterministic.
"""

from __future__ import annotations

import asyncio
import os
import unittest
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional
from unittest import mock

import skills.surface.maez_adapter as adapter_mod
import daemon.inbound_core as core_mod
from skills.surface.maez_adapter import MaezMessageHandler
from skills.surface.platform_base import MessageType


# --------------------------------------------------------------------------
# Fake event / source
# --------------------------------------------------------------------------
@dataclass
class FakeSource:
    chat_id: str = "chat-1"
    user_id: Optional[str] = None  # None => __call__ keeps the "rohit" literal


@dataclass
class FakeEvent:
    text: str
    message_type: MessageType = MessageType.TEXT
    source: Optional[FakeSource] = field(default_factory=FakeSource)
    channel_prompt: Any = None
    photo_analysis_text: Any = None
    reply_to_message_id: Optional[str] = None


# --------------------------------------------------------------------------
# Fake pipeline / card store
# --------------------------------------------------------------------------
class FakeCardStore:
    def __init__(self, trace: list, open_cards):
        self._trace = trace
        self._open_cards = open_cards

    def get_open_for_channel(self, channel, *, chat_id):
        self._trace.append(("card_store.get_open_for_channel", channel, chat_id))
        return list(self._open_cards)


@dataclass
class FakeReplyResult:
    dialog_reply_text: Optional[str] = None


class FakePipe:
    def __init__(self, trace: list, open_cards, reply_result):
        self._trace = trace
        self.card_store = FakeCardStore(trace, open_cards)
        self._reply_result = reply_result

    def handle_reply(self, *, text, user_id, chat_id, reply_to_message_id, channel):
        self._trace.append(
            ("pipe.handle_reply", text, user_id, chat_id, reply_to_message_id, channel)
        )
        return self._reply_result


class FakeLegacyTelegram:
    def __init__(self, trace: list, pipe):
        self._trace = trace
        self._pipe = pipe
        self._controller = "fake-controller"

    def _get_pipeline(self):
        self._trace.append(("get_pipeline",))
        return self._pipe


# --------------------------------------------------------------------------
# Fake memory
# --------------------------------------------------------------------------
class FakeMemory:
    def __init__(self, trace: list, exchanges):
        self._trace = trace
        self._exchanges = exchanges

    def get_telegram_exchanges(self, *, limit):
        self._trace.append(("get_telegram_exchanges", limit))
        return list(self._exchanges)


# --------------------------------------------------------------------------
# Fake daemon
# --------------------------------------------------------------------------
class FakeDaemon:
    def __init__(self, trace: list, *, pipe=None, memory=None, reply="final reply"):
        self._trace = trace
        self.actions = "fake-action-engine"
        self.telegram = FakeLegacyTelegram(trace, pipe) if pipe is not None else None
        self.memory = memory
        self.private_thoughts = None
        self._reply = reply
        # transport-closure capture points (no real surface)
        self._surface_v2_adapter = None
        self._surface_v2_loop = None

    def _mark_m1_s4_policy(self, policy):
        self._trace.append(("_mark_m1_s4_policy", policy))

    def handle_message(self, text, surface, **kwargs):
        # Record the full kwarg surface — chat_id, transcript, tool_calls,
        # recall_items, subjective_duration_owner_auth presence, etc.
        self._trace.append(
            (
                "handle_message",
                text,
                surface,
                kwargs.get("transcript"),
                kwargs.get("context_note"),
                kwargs.get("photo_analysis"),
                tuple(c for c in (kwargs.get("chat_history") or [])) if kwargs.get("chat_history") is not None else None,
                kwargs.get("chat_id"),
                kwargs.get("tool_calls"),
                tuple(kwargs.get("recall_items") or ()),
                # auth object identity isn't stable; record only whether present
                kwargs.get("subjective_duration_owner_auth") is not None,
                # send_intermediate is the adapter's progress-receipt closure
                callable(kwargs.get("send_intermediate")),
            )
        )
        return self._reply


# --------------------------------------------------------------------------
# Fake brain-loop structured result
# --------------------------------------------------------------------------
@dataclass
class FakeBrainResult:
    transcript: str = "jarvis transcript"
    tool_calls: list = field(default_factory=lambda: [{"tool": "noop"}])
    recall_items: tuple = ()


# --------------------------------------------------------------------------
# Inline executor (deterministic ordering, no thread)
# --------------------------------------------------------------------------
class _InlineExecutor:
    def submit(self, fn, *args, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError


def _make_inline_run_in_executor(loop):
    # We don't patch loop.run_in_executor itself; instead we patch
    # get_shared_executor to return a sentinel and rely on the real
    # loop.run_in_executor(None-like) — but to stay fully synchronous and
    # avoid threads we instead monkeypatch loop.run_in_executor.
    orig = loop.run_in_executor

    async def _inline(executor, fn, *args):
        return fn(*args)

    return _inline, orig


# --------------------------------------------------------------------------
# observe_turn fake (records enter/exit + output)
# --------------------------------------------------------------------------
class _FakeTurn:
    def __init__(self, trace):
        self._trace = trace

    def update(self, **kwargs):
        self._trace.append(("turn.update", kwargs.get("output")))


def _make_observe_turn(trace):
    @contextmanager
    def _observe_turn(label, *, input=None, metadata=None):
        trace.append(("observe_turn.enter", label, tuple(sorted((input or {}).items())), tuple(sorted((metadata or {}).items()))))
        try:
            yield _FakeTurn(trace)
        finally:
            trace.append(("observe_turn.exit", label))

    return _observe_turn


def _make_run_brain_loop(trace, result):
    def _run_brain_loop(text, **kwargs):
        trace.append(
            (
                "run_brain_loop",
                text,
                kwargs.get("user_id"),
                kwargs.get("chat_id"),
                kwargs.get("surface"),
                callable(kwargs.get("send_intermediate")),
                tuple(c for c in (kwargs.get("chat_history") or [])) if kwargs.get("chat_history") is not None else None,
                kwargs.get("return_structured"),
            )
        )
        return result

    return _run_brain_loop


# --------------------------------------------------------------------------
# Harness driver
# --------------------------------------------------------------------------
class InboundCoreEquivalenceTests(unittest.TestCase):
    def _drive(
        self,
        *,
        flag_on: bool,
        event: FakeEvent,
        open_cards=(),
        reply_result=None,
        exchanges=(),
        brain_result=None,
        proposal_reply=None,
        search_reply=None,
        surface_parity=True,
        with_pipe=True,
        with_memory=True,
        handle_reply_result=None,
    ):
        trace: list = []

        pipe = (
            FakePipe(trace, open_cards, reply_result if reply_result is not None else handle_reply_result)
            if with_pipe
            else None
        )
        memory = FakeMemory(trace, exchanges) if with_memory else None
        daemon = FakeDaemon(trace, pipe=pipe, memory=memory)
        handler = MaezMessageHandler(daemon)

        # Record proposal / search-commitment interceptor invocations and let
        # the test choose whether they "hit" (early-return) or fall through.
        async def _fake_proposal(*, text, chat_id, pipe, user_id):
            trace.append(("try_proposal_intent", text, chat_id, user_id))
            return proposal_reply

        async def _fake_search(*, text, chat_id):
            trace.append(("try_search_commitment_intent", text, chat_id))
            # The producer's contract is a TYPED result carrying its
            # provenance shape (twenty-third round), not a bare str —
            # both flag paths unwrap `.text`, so a str double would
            # test a contract the producer no longer has.
            if search_reply is None:
                return None
            from core.ledger.recorder import OrganProvenance, ProducedReply

            return ProducedReply(search_reply, OrganProvenance.CANNED)

        # The descriptor wires self._try_* — patch the bound methods so BOTH
        # flag paths (flag-off calls them as self.method; flag-on calls them as
        # injected callables resolved from self.method) record identically.
        handler._try_surface_parity_proposal_intent = _fake_proposal  # type: ignore
        handler._try_search_commitment_intent = _fake_search  # type: ignore

        loop = asyncio.new_event_loop()
        inline_run, _orig = _make_inline_run_in_executor(loop)

        brain = brain_result if brain_result is not None else FakeBrainResult()
        observe = _make_observe_turn(trace)
        rbl = _make_run_brain_loop(trace, brain)

        env = {}
        if flag_on:
            env["MAEZ_INBOUND_CORE_V2"] = "1"
        else:
            env.pop("MAEZ_INBOUND_CORE_V2", None)

        # Build a fake core.brain_loop module exposing run_brain_loop +
        # strip_tool_call_leaks (used by the card-reply dialog path).
        fake_brain_mod = mock.MagicMock()
        fake_brain_mod.run_brain_loop = rbl
        fake_brain_mod.strip_tool_call_leaks = lambda s: s

        fake_obs_mod = mock.MagicMock()
        fake_obs_mod.observe_turn = observe

        with mock.patch.dict(os.environ, env, clear=False):
            if not flag_on:
                os.environ.pop("MAEZ_INBOUND_CORE_V2", None)
            with mock.patch.object(loop, "run_in_executor", inline_run), \
                 mock.patch.object(adapter_mod, "surface_parity_enabled", lambda: surface_parity), \
                 mock.patch.object(core_mod, "surface_parity_enabled", lambda: surface_parity), \
                 mock.patch.object(adapter_mod, "get_shared_executor", lambda: None), \
                 mock.patch.object(core_mod, "get_shared_executor", lambda: None), \
                 mock.patch.dict("sys.modules", {"core.brain_loop": fake_brain_mod, "core.observability": fake_obs_mod}):
                result = loop.run_until_complete(handler(event))

        loop.close()
        return result, trace

    def _assert_equivalent(self, **kwargs):
        off_result, off_trace = self._drive(flag_on=False, **kwargs)
        on_result, on_trace = self._drive(flag_on=True, **kwargs)
        self.assertEqual(off_result, on_result, "return value differs between flag states")
        self.assertEqual(off_trace, on_trace, "call-trace differs between flag states")
        return off_result, off_trace

    # ---- (a) plain owner text (full synthesis path) ----
    def test_a_plain_owner_text_full_synthesis(self):
        result, trace = self._assert_equivalent(event=FakeEvent(text="hello maez"))
        self.assertEqual(result, "final reply")
        kinds = [t[0] for t in trace]
        self.assertIn("run_brain_loop", kinds)
        self.assertIn("handle_message", kinds)
        self.assertIn("observe_turn.enter", kinds)

    # ---- (b) open card + "yes" => card-reply interceptor ----
    def test_b_open_card_yes_card_reply_interceptor(self):
        # Pipeline fully handles it: dialog_reply_text None => __call__ returns None.
        result, trace = self._assert_equivalent(
            event=FakeEvent(text="yes"),
            open_cards=("card-1",),
            handle_reply_result=FakeReplyResult(dialog_reply_text=None),
        )
        self.assertIsNone(result)
        kinds = [t[0] for t in trace]
        self.assertIn("pipe.handle_reply", kinds)
        # Card path returns before brain_loop / handle_message.
        self.assertNotIn("run_brain_loop", kinds)
        self.assertNotIn("handle_message", kinds)

    def test_b2_open_card_with_dialog_continuation(self):
        result, trace = self._assert_equivalent(
            event=FakeEvent(text="yes"),
            open_cards=("card-1",),
            handle_reply_result=FakeReplyResult(dialog_reply_text="mid-dialog text"),
        )
        self.assertEqual(result, "mid-dialog text")

    # ---- (c) proposal-intent hit ----
    def test_c_proposal_intent_hit(self):
        result, trace = self._assert_equivalent(
            event=FakeEvent(text="yes to #22"),
            proposal_reply="proposal handled",
        )
        self.assertEqual(result, "proposal handled")
        kinds = [t[0] for t in trace]
        self.assertIn("try_proposal_intent", kinds)
        self.assertNotIn("handle_message", kinds)

    # ---- (d) search-commitment hit ----
    def test_d_search_commitment_hit(self):
        result, trace = self._assert_equivalent(
            event=FakeEvent(text="search for X"),
            search_reply="search offered",
        )
        self.assertEqual(result, "search offered")
        kinds = [t[0] for t in trace]
        self.assertIn("try_search_commitment_intent", kinds)
        self.assertNotIn("handle_message", kinds)

    # ---- (e) photo turn => brain_loop skipped ----
    def test_e_photo_turn_brain_loop_skipped(self):
        event = FakeEvent(
            text="what is this",
            message_type=MessageType.PHOTO,
            channel_prompt="Local Maez vision analysis: a cat",
            photo_analysis_text="a cat",
        )
        result, trace = self._assert_equivalent(event=event)
        self.assertEqual(result, "final reply")
        kinds = [t[0] for t in trace]
        self.assertNotIn("run_brain_loop", kinds)  # has_local_photo_context => skipped
        self.assertIn("handle_message", kinds)

    # ---- (f) empty text => both return None ----
    def test_f_empty_text_returns_none(self):
        result, trace = self._assert_equivalent(event=FakeEvent(text="   "))
        self.assertIsNone(result)
        self.assertEqual(trace, [])

    # ---- (h) no-pipe equivalence: D20 must fire un-gated on Telegram ----
    def test_h_no_pipe_equivalence(self):
        # When _get_pipeline raises (pipe is None) the Telegram body still fires
        # the D20 capability-gap detector (the inline body gates ONLY on
        # surface_parity, never on pipe). FIX 2 makes the core byte-identical:
        # gate_d20_on_pipe defaults False, so flag-on == flag-off even with no
        # pipe. The trace records the D20 enqueue via get_shared_executor; the
        # inline-executor harness runs _fire_gap_detector, which imports the real
        # capability_gap_detector. With pending_card_store=None it self-skips, so
        # no card is created — but the enqueue path itself must match.
        result, trace = self._assert_equivalent(
            event=FakeEvent(text="hello maez"),
            with_pipe=False,
        )
        self.assertEqual(result, "final reply")
        kinds = [t[0] for t in trace]
        # No pipe -> no card_store probe, no handle_reply, but synthesis still runs.
        self.assertNotIn("card_store.get_open_for_channel", kinds)
        self.assertNotIn("pipe.handle_reply", kinds)
        self.assertIn("handle_message", kinds)

    # ---- (i) no-memory equivalence: chat_history kwarg identical ----
    def test_i_no_memory(self):
        # When daemon.memory is None the chat_history fetch is skipped and
        # handle_message receives chat_history=None. Flag-on must match flag-off.
        result, trace = self._assert_equivalent(
            event=FakeEvent(text="hello maez"),
            with_memory=False,
        )
        self.assertEqual(result, "final reply")
        kinds = [t[0] for t in trace]
        self.assertNotIn("get_telegram_exchanges", kinds)
        # handle_message tuple index 6 is the chat_history snapshot (None here).
        hm = [t for t in trace if t[0] == "handle_message"][0]
        self.assertIsNone(hm[6], "chat_history kwarg must be None across flag states")

    # ---- extra: resolved user_id (src.user_id set) still byte-identical ----
    def test_g_resolved_user_id_split_preserved(self):
        # When src.user_id is set, D20 + proposal use the resolved id while
        # handle_reply / observe metadata / run_brain_loop keep "rohit".
        event = FakeEvent(text="hello", source=FakeSource(chat_id="c9", user_id="rohit-alt"))
        result, trace = self._assert_equivalent(event=event)
        self.assertEqual(result, "final reply")
        # proposal intent saw the resolved id...
        prop = [t for t in trace if t[0] == "try_proposal_intent"][0]
        self.assertEqual(prop[3], "rohit-alt")
        # ...but run_brain_loop kept the literal "rohit" (index 2 = user_id;
        # tuple is (kind, text, user_id, chat_id, surface, ...)).
        rbl = [t for t in trace if t[0] == "run_brain_loop"][0]
        self.assertEqual(rbl[2], "rohit")
        # handle_message also kept the literal "rohit" via observe_turn metadata
        # path; verify the observe_turn metadata carries the literal too.
        obs = [t for t in trace if t[0] == "observe_turn.enter"][0]
        self.assertIn(("user_id", "rohit"), obs[3])


class InboundCoreFlagParserTests(unittest.TestCase):
    def test_unset_is_off(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_INBOUND_CORE_V2", None)
            self.assertFalse(core_mod.inbound_core_v2_enabled())

    def test_zero_is_off(self):
        with mock.patch.dict(os.environ, {"MAEZ_INBOUND_CORE_V2": "0"}):
            self.assertFalse(core_mod.inbound_core_v2_enabled())

    def test_false_no_off_are_off(self):
        for val in ("false", "no", "off", "", "  ", "maybe"):
            with mock.patch.dict(os.environ, {"MAEZ_INBOUND_CORE_V2": val}):
                self.assertFalse(core_mod.inbound_core_v2_enabled(), val)

    def test_truthy_values_are_on(self):
        for val in ("1", "true", "yes", "on", "TRUE", "On", " 1 "):
            with mock.patch.dict(os.environ, {"MAEZ_INBOUND_CORE_V2": val}):
                self.assertTrue(core_mod.inbound_core_v2_enabled(), val)


if __name__ == "__main__":
    unittest.main()
