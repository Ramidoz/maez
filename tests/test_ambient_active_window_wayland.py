import unittest
from unittest import mock

import core.memory.ambient as ambient


class WaylandActiveWindowTests(unittest.TestCase):
    def test_wayland_no_route_returns_none(self):
        with mock.patch.object(ambient, "_session_is_wayland", return_value=True), \
             mock.patch.object(ambient, "_wayland_active_window", return_value=None):
            self.assertIsNone(ambient.active_window())

    def test_wayland_route_present_returns_window(self):
        window = {"class": "firefox", "title": "x"}
        with mock.patch.object(ambient, "_session_is_wayland", return_value=True), \
             mock.patch.object(ambient, "_wayland_active_window", return_value=window):
            self.assertEqual(ambient.active_window(), window)


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


if __name__ == "__main__":
    unittest.main()
