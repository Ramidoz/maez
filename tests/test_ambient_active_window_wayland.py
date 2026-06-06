import unittest
from unittest import mock

import core.memory.ambient as ambient
import core.memory.ambient_format as ambient_format


class WaylandActiveWindowTests(unittest.TestCase):
    def test_wayland_no_route_returns_none(self):
        with mock.patch.object(ambient, "_session_is_wayland", return_value=True), \
             mock.patch.object(ambient, "_wayland_active_window", return_value=None):
            self.assertIsNone(ambient.active_window())

    def test_wayland_route_present_returns_class_only_window(self):
        window = {"class": "firefox", "title": "x"}
        with mock.patch.object(ambient, "_session_is_wayland", return_value=True), \
             mock.patch.object(ambient, "_wayland_active_window", return_value=window):
            self.assertEqual(ambient.active_window(), {"class": "firefox"})
            self.assertEqual(ambient.active_window_for_preflight(), window)


class ParseFocusedWindowTests(unittest.TestCase):
    def test_tuple_wrapped_json_string_discards_action_fields(self):
        out = ambient._parse_focused_window_dbus(
            '(\'{"title": "Doc", "wm_class": "Code", "moveable": true, '
            '"resizeable": true, "canclose": true, "unknown": "drop"}\',)'
        )

        self.assertEqual(out, {"title": "Doc", "class": "Code"})

    def test_raw_json_object(self):
        out = ambient._parse_focused_window_dbus('{"title": "T", "class": "firefox"}')

        self.assertEqual(out, {"title": "T", "class": "firefox"})

    def test_optional_pid_and_id_survive(self):
        out = ambient._parse_focused_window_dbus(
            '{"title": "T", "wm_class": "Code", "pid": 123, "id": "abc"}'
        )

        self.assertEqual(out, {"title": "T", "class": "Code", "pid": 123, "id": "abc"})

    def test_empty_or_malformed_is_none(self):
        for raw in ("", "()", "{}", "(\'{}\',)", "garbage", "(\'not json\',)"):
            with self.subTest(raw=raw):
                self.assertIsNone(ambient._parse_focused_window_dbus(raw))


class WaylandRouteTests(unittest.TestCase):
    def test_calls_focused_window_interface(self):
        captured = {}

        def fake_check_output(cmd, **_kwargs):
            captured["cmd"] = cmd
            return '(\'{"title":"T","wm_class":"firefox"}\',)'

        with mock.patch.object(ambient.shutil, "which", return_value="/usr/bin/gdbus"), \
             mock.patch.object(ambient.subprocess, "check_output", side_effect=fake_check_output):
            out = ambient._wayland_active_window()

        self.assertEqual(out, {"title": "T", "class": "firefox"})
        self.assertIn("/org/gnome/shell/extensions/FocusedWindow", captured["cmd"])
        self.assertIn("org.gnome.shell.extensions.FocusedWindow.Get", captured["cmd"])


class SurfaceSplitTests(unittest.TestCase):
    def test_active_window_is_class_only(self):
        with mock.patch.object(
            ambient, "_raw_active_window", return_value={"title": "secret doc", "class": "Code"}
        ):
            out = ambient.active_window()

        self.assertEqual(out, {"class": "Code"})
        self.assertNotIn("title", out)

    def test_preflight_surface_keeps_title(self):
        with mock.patch.object(
            ambient, "_raw_active_window", return_value={"title": "secret doc", "class": "Code"}
        ):
            out = ambient.active_window_for_preflight()

        self.assertEqual(out, {"title": "secret doc", "class": "Code"})

    def test_both_none_when_raw_none(self):
        with mock.patch.object(ambient, "_raw_active_window", return_value=None):
            self.assertIsNone(ambient.active_window())
            self.assertIsNone(ambient.active_window_for_preflight())


class TitleLeakRegressionTests(unittest.TestCase):
    def test_confidential_title_never_renders_in_ambient(self):
        rendered = ambient_format._format(
            {
                "now": "2026-06-06T00:00:00+00:00",
                "active_window": {"title": "Re: confidential salary — Gmail", "class": "firefox"},
                "signals_latest": {},
            }
        )
        self.assertIn("Active desktop window: firefox", rendered)
        for leak in ("confidential", "salary", "Gmail"):
            self.assertNotIn(leak, rendered)


if __name__ == "__main__":
    unittest.main()
