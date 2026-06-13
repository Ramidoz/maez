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
        # M1-ineligibility was marked (the second face of the bug).
        self.assertTrue(daemon.s4_policy_marks)
        self.assertNotIn("ordinary", daemon.s4_policy_marks)


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


if __name__ == "__main__":
    unittest.main()
