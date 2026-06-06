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


if __name__ == "__main__":
    unittest.main()
