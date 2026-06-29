from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock

from core.body.desktop_presence_state import (
    DesktopPresenceState,
    sample_desktop_presence,
)

_NOW = datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)


class DesktopPresenceStateTests(unittest.TestCase):
    def test_default_disabled_does_not_sample(self):
        called = {"window": False, "avail": False}

        def _avail():
            called["avail"] = True
            return ("available", "")

        def _win():
            called["window"] = True
            return {"class": "firefox", "title": "secret"}

        state = sample_desktop_presence(
            {}, now=_NOW, availability_fn=_avail, active_window_fn=_win
        )
        self.assertEqual(state.sensor_state, "disabled")
        self.assertIsNone(state.app_class)
        self.assertFalse(called["avail"], "disabled must not probe availability")
        self.assertFalse(called["window"], "disabled must not read the window")

    def test_available_is_app_class_only_no_title(self):
        state = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
            availability_fn=lambda: ("available", ""),
            active_window_fn=lambda: {
                "class": "firefox",
                "title": "Re: confidential salary discussion - Gmail",
            },
        )
        self.assertEqual(state.sensor_state, "available")
        self.assertEqual(state.app_class, "firefox")
        health = state.to_health(now=_NOW)
        blob = repr(state) + repr(health)
        self.assertNotIn("confidential", blob)
        self.assertNotIn("Gmail", blob)
        self.assertNotIn("salary", blob)

    def test_honest_availability_matrix_never_fabricates(self):
        for reason in ("tools_missing", "wayland", "session_unreachable"):
            state = sample_desktop_presence(
                {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
                availability_fn=lambda r=reason: ("unavailable", r),
                active_window_fn=lambda: {"class": "firefox", "title": "x"},
            )
            self.assertEqual(state.sensor_state, "unavailable")
            self.assertEqual(state.reason, reason)
            self.assertIsNone(state.app_class, "blind must never carry an app class")

    def test_wayland_availability_uses_gdbus_not_xdotool(self):
        from core.body import desktop_presence_state as dps

        def has_binary(name: str) -> bool:
            return name == "gdbus"

        with mock.patch.dict(
            "os.environ",
            {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"},
            clear=True,
        ), mock.patch.object(dps.body_capabilities, "has_binary", has_binary):
            self.assertEqual(dps._desktop_availability(), ("available", ""))

    def test_wayland_availability_reports_tools_missing_without_gdbus(self):
        from core.body import desktop_presence_state as dps

        with mock.patch.dict(
            "os.environ",
            {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"},
            clear=True,
        ), mock.patch.object(dps.body_capabilities, "has_binary", return_value=False):
            self.assertEqual(dps._desktop_availability(), ("unavailable", "tools_missing"))

    def test_x11_availability_still_requires_xdotool_and_session(self):
        from core.body import desktop_presence_state as dps

        with mock.patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True), \
            mock.patch.object(dps.body_capabilities, "has_binary", return_value=True), \
            mock.patch.object(
                dps.body_capabilities, "desktop_session_reachable", return_value=True
            ):
            self.assertEqual(dps._desktop_availability(), ("available", ""))

    def test_reachable_but_no_active_window_is_blind_not_fabricated(self):
        state = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
            availability_fn=lambda: ("available", ""),
            active_window_fn=lambda: None,
        )
        self.assertEqual(state.sensor_state, "unavailable")
        self.assertEqual(state.reason, "no_active_window")
        self.assertIsNone(state.app_class)

    def test_blind_beats_stale(self):
        avail = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
            availability_fn=lambda: ("available", ""),
            active_window_fn=lambda: {"class": "code", "title": "x"},
        )
        self.assertEqual(avail.app_class, "code")
        blind = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
            availability_fn=lambda: ("unavailable", "session_unreachable"),
            active_window_fn=lambda: {"class": "code", "title": "x"},
        )
        self.assertEqual(blind.sensor_state, "unavailable")
        self.assertIsNone(blind.app_class)

    def test_invariant_app_class_only_when_available(self):
        with self.assertRaises(ValueError):
            DesktopPresenceState(sensor_state="unavailable", app_class="firefox")


if __name__ == "__main__":
    unittest.main()
