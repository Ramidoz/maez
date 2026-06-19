# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""SLICE 2 — cockpit /message routed through the surface-agnostic inbound core.

Covenant decisions under test (fixed — see the slice spec):

  * S4 fires on the cockpit owner surface (the live bug: source="UI" failed
    _is_direct_owner_surface, so the clinical/suicide-crisis boundary was DEAD
    on cockpit). Adding "cockpit" to the allowlist re-arms it.
  * Cockpit is M1-EXCLUDED (conservative): NOT in M1_ALLOWED_PROMOTION_SOURCES.
    The unauthenticated localhost surface must not write durable M1 selfhood.
  * MAEZ_COCKPIT_CORE strict flag, DEFAULT OFF. Flag off -> cockpit unchanged
    (source="UI" -> handle_message). Flag on -> run_inbound_turn with
    source="cockpit", get_pipeline=None (no brain_loop / no tools).

Fakes only — no real brain / LLM / pipeline. The core (run_inbound_turn) is the
real spine; only daemon.handle_message / memory are faked.
"""

from __future__ import annotations

import asyncio
import os
import unittest
from unittest import mock

from daemon.maez_daemon import MaezDaemon
from tests.test_s7_1_daemon_internal_channel import _DaemonAppClientMixin


# --- Fakes -----------------------------------------------------------------


class _FakeMemory:
    """Minimal memory: present (so chat_history fetch runs) but returns []."""

    def get_telegram_exchanges(self, limit):
        return []


class _FakeDaemon:
    """Records handle_message calls; carries a memory and S4-policy mark."""

    def __init__(self, reply="cockpit final reply"):
        self.memory = _FakeMemory()
        self.private_thoughts = None
        self._reply = reply
        self.handle_message_calls: list[dict] = []
        self.s4_policy_marks: list[str] = []

    def handle_message(self, text, source, **kwargs):
        self.handle_message_calls.append(
            {"text": text, "source": source, "kwargs": kwargs}
        )
        return self._reply

    def _mark_m1_s4_policy(self, policy):
        self.s4_policy_marks.append(policy)


# --- Tests -----------------------------------------------------------------


class CockpitS4FiresTests(unittest.TestCase):
    def test_is_direct_owner_surface_cockpit_true(self):
        from core.safety.clinical_boundary import _is_direct_owner_surface

        self.assertTrue(
            _is_direct_owner_surface("cockpit"),
            "cockpit must be in the S4 owner-surface allowlist or the clinical "
            "boundary stays disarmed on the cockpit owner path",
        )

    def test_cockpit_s4_fires_under_flag(self):
        from daemon.maez_daemon import _build_cockpit_inbound_descriptor
        from daemon.inbound_core import run_inbound_turn
        from core.safety.clinical_boundary import guard_owner_text

        # Direct unit: a crisis-class message matches under surface="cockpit".
        direct = guard_owner_text("I want to end my life", surface="cockpit")
        self.assertTrue(direct.matched, "S4 must match crisis text on cockpit")
        self.assertNotEqual(direct.promotion_policy, "ordinary")

        # End-of-rail: routed through the cockpit descriptor + core, the S4
        # early-return wins — daemon.handle_message is NEVER reached.
        daemon = _FakeDaemon()
        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_CORE": "1"}):
            descriptor = _build_cockpit_inbound_descriptor(
                daemon, text="I want to end my life", chat_history=None
            )
            reply = asyncio.run(run_inbound_turn(**descriptor))

        self.assertTrue(reply, "S4 must return a crisis-care answer text")
        self.assertEqual(
            daemon.handle_message_calls,
            [],
            "S4 early-return must short-circuit before handle_message",
        )
        # COVENANT (FIX 1): cockpit must NOT mark the shared (Telegram-fed) global
        # M1 promotion window — an unauthenticated localhost surface must not
        # mutate durable selfhood. The crisis-care reply is still returned above;
        # only the shared-window mark is skipped (mark_s4_promotion_policy=False).
        self.assertEqual(
            daemon.s4_policy_marks,
            [],
            "cockpit S4 must NOT mutate the shared M1 promotion window",
        )

    def test_cockpit_s4_returns_care_without_shared_window_mark(self):
        # Focused unit for FIX 1: drive run_inbound_turn directly with the
        # cockpit descriptor and assert both faces — the crisis-care answer_text
        # IS returned, AND _mark_m1_s4_policy is NEVER invoked.
        from daemon.maez_daemon import _build_cockpit_inbound_descriptor
        from daemon.inbound_core import run_inbound_turn

        daemon = _FakeDaemon()
        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_CORE": "1"}):
            descriptor = _build_cockpit_inbound_descriptor(
                daemon, text="I want to kill myself", chat_history=None
            )
            self.assertFalse(
                descriptor["mark_s4_promotion_policy"],
                "cockpit descriptor must pass mark_s4_promotion_policy=False",
            )
            reply = asyncio.run(run_inbound_turn(**descriptor))

        self.assertTrue(reply, "crisis-care text must still be returned on cockpit")
        self.assertEqual(daemon.handle_message_calls, [])
        self.assertEqual(
            daemon.s4_policy_marks,
            [],
            "the shared M1 window mark must NOT be invoked for cockpit",
        )


class CockpitNotInM1Tests(unittest.TestCase):
    def test_cockpit_not_in_m1(self):
        from daemon.maez_daemon import M1_ALLOWED_PROMOTION_SOURCES

        self.assertNotIn(
            "cockpit",
            M1_ALLOWED_PROMOTION_SOURCES,
            "cockpit is unauthenticated (localhost-bind only) and must NOT "
            "promote to durable M1 selfhood — conservative covenant default",
        )


class CockpitFlagParserTests(unittest.TestCase):
    def test_flag_strict_parser(self):
        from daemon.maez_daemon import cockpit_core_enabled

        for off in ("0", "false", "no", "off", "", "FILE_NOT_FOUND"):
            with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_CORE": off}):
                self.assertFalse(
                    cockpit_core_enabled(), f"{off!r} must read OFF"
                )
        # Unset is OFF.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_COCKPIT_CORE", None)
            self.assertFalse(cockpit_core_enabled(), "unset must read OFF")

        for on in ("1", "true", "yes", "on", "ON", "Yes"):
            with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_CORE": on}):
                self.assertTrue(
                    cockpit_core_enabled(), f"{on!r} must read ON"
                )


class CockpitRouteBranchTests(unittest.TestCase):
    """The /message route branch — exercised at the helper seam (no Flask).

    The route does, in essence::

        if cockpit_core_enabled():
            reply = asyncio.run(run_inbound_turn(**descriptor(...)))
        else:
            reply = handle_message(text, source="UI", chat_history=...)

    These tests pin BOTH arms.
    """

    def test_flag_off_cockpit_unchanged(self):
        # Flag unset -> the route stays on the source="UI" handle_message path,
        # byte-identical to today. Drive the exact branch the route runs.
        from daemon.maez_daemon import cockpit_core_enabled

        daemon = _FakeDaemon()
        chat_history = [{"content": "Rohit: hi\nMaez: hello"}]
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_COCKPIT_CORE", None)
            self.assertFalse(cockpit_core_enabled())
            # Simulate the OFF arm exactly as the route does.
            reply = daemon.handle_message(
                "hello there", source="UI", chat_history=chat_history
            )

        self.assertEqual(reply, "cockpit final reply")
        self.assertEqual(len(daemon.handle_message_calls), 1)
        call = daemon.handle_message_calls[0]
        self.assertEqual(call["source"], "UI")
        self.assertEqual(call["kwargs"].get("chat_history"), chat_history)

    def test_cockpit_routes_through_core_when_on(self):
        # Flag on + plain (non-clinical) message -> run_inbound_turn reaches
        # daemon.handle_message with source="cockpit" (NOT "UI"), get_pipeline
        # is None (so no brain_loop), and the reply string flows back.
        from daemon.maez_daemon import (
            _build_cockpit_inbound_descriptor,
            cockpit_core_enabled,
        )
        from daemon.inbound_core import run_inbound_turn

        daemon = _FakeDaemon(reply="hi from cockpit core")
        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_CORE": "1"}):
            self.assertTrue(cockpit_core_enabled())
            descriptor = _build_cockpit_inbound_descriptor(
                daemon, text="what's the weather like today", chat_history=None
            )
            # Covenant assertions on the descriptor itself.
            self.assertEqual(descriptor["owner_surface_label"], "cockpit")
            self.assertIsNone(descriptor["get_pipeline"])
            self.assertIsNone(descriptor["action_engine"])
            self.assertIsNone(descriptor["owner_auth_factory"]())

            reply = asyncio.run(run_inbound_turn(**descriptor))

        self.assertEqual(reply, "hi from cockpit core")
        self.assertEqual(len(daemon.handle_message_calls), 1)
        call = daemon.handle_message_calls[0]
        self.assertEqual(
            call["source"],
            "cockpit",
            "core must dispatch handle_message with the cockpit surface label, "
            "not the legacy source='UI'",
        )
        # No brain-loop ran (get_pipeline None) -> empty transcript synthesized.
        self.assertEqual(call["kwargs"].get("transcript"), "")


class CockpitFeltTimeDescriptor(unittest.TestCase):
    def _descriptor(self, *, flag, owner_authenticated):
        from daemon import maez_daemon as md

        env = {}
        if flag:
            env["MAEZ_COCKPIT_FELT_TIME"] = "1"
        with mock.patch.dict(os.environ, env, clear=False):
            if not flag:
                os.environ.pop("MAEZ_COCKPIT_FELT_TIME", None)
            return md._build_cockpit_inbound_descriptor(
                _FakeDaemon(),
                text="hi",
                chat_history=None,
                owner_authenticated=owner_authenticated,
            )

    def test_flag_off_factory_none_even_with_marker(self):
        d = self._descriptor(flag=False, owner_authenticated=True)
        self.assertIsNone(d["owner_auth_factory"]())
        self.assertFalse(d["felt_time_enabled"])

    def test_flag_on_no_marker_factory_none(self):
        d = self._descriptor(flag=True, owner_authenticated=False)
        self.assertIsNone(d["owner_auth_factory"]())
        self.assertFalse(d["felt_time_enabled"])

    def test_flag_on_with_marker_mints_cockpit_auth(self):
        d = self._descriptor(flag=True, owner_authenticated=True)
        auth = d["owner_auth_factory"]()
        self.assertEqual(
            (auth.surface, auth.proof), ("cockpit", "cockpit_web_owner")
        )
        self.assertTrue(d["felt_time_enabled"])

    def test_no_leak_via_surface_parity(self):
        # The factory gates on felt_time_on (flag AND marker) and NEVER reads
        # surface_parity. The parity patch below is intentionally INERT — the
        # factory never consults it. We force parity globally ON only to
        # document the safety: even so, with the cockpit flag OFF the factory
        # still returns None -> a globally-ON parity flag cannot leak cockpit
        # felt-time. (run_inbound_turn may CALL the factory under parity, but it
        # gets None.)
        with mock.patch(
            "daemon.inbound_core.surface_parity_enabled", return_value=True
        ):
            d = self._descriptor(flag=False, owner_authenticated=True)
            self.assertIsNone(d["owner_auth_factory"]())


class CockpitFeltTimeMessageRouteMarker(
    _DaemonAppClientMixin, unittest.TestCase
):
    """The S7-gated /message route reads X-Maez-Owner-Authenticated: 1 and
    threads it to _build_cockpit_inbound_descriptor as owner_authenticated."""

    def _drive(self, *, owner_header):
        from daemon import maez_daemon as md

        captured = {}

        def _fake_descriptor(daemon, *, text, chat_history, owner_authenticated):
            captured["owner_authenticated"] = owner_authenticated
            # Return a minimal descriptor; run_inbound_turn is patched to a
            # no-op so none of these keys are exercised.
            return {"owner_authenticated": owner_authenticated}

        async def _fake_run_inbound_turn(**_kwargs):
            return "ok"

        daemon = MaezDaemon.__new__(MaezDaemon)
        daemon._health_server = None

        headers = {"X-Maez-S7-Internal-Channel": "test-channel-secret"}
        if owner_header is not None:
            headers["X-Maez-Owner-Authenticated"] = owner_header

        with mock.patch.dict(
            os.environ,
            {
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "MAEZ_COCKPIT_CORE": "1",
            },
            clear=False,
        ):
            with mock.patch.object(
                md, "_build_cockpit_inbound_descriptor", _fake_descriptor
            ):
                with mock.patch(
                    "daemon.inbound_core.run_inbound_turn",
                    _fake_run_inbound_turn,
                ):
                    client = self._client_for_daemon(daemon)
                    resp = client.post(
                        "/message", json={"text": "hello"}, headers=headers
                    )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        return captured

    def test_owner_marker_present_captures_true(self):
        captured = self._drive(owner_header="1")
        self.assertIs(captured["owner_authenticated"], True)

    def test_owner_marker_absent_captures_false(self):
        captured = self._drive(owner_header=None)
        self.assertIs(captured["owner_authenticated"], False)


if __name__ == "__main__":
    unittest.main()
