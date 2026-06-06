import unittest
from unittest import mock

import skills.screen_perception as sp


class SessionTypeTests(unittest.TestCase):
    def _env(self, **kw):
        base = {
            "XDG_SESSION_TYPE": "",
            "XDG_CURRENT_DESKTOP": "",
            "WAYLAND_DISPLAY": "",
            "DISPLAY": "",
        }
        base.update(kw)
        return base

    def test_x11(self):
        with mock.patch.dict(
            sp.os.environ,
            self._env(XDG_SESSION_TYPE="x11", DISPLAY=":0"),
            clear=True,
        ):
            self.assertEqual(sp._session_type(), "x11")

    def test_wayland_gnome(self):
        with mock.patch.dict(
            sp.os.environ,
            self._env(
                XDG_SESSION_TYPE="wayland",
                XDG_CURRENT_DESKTOP="ubuntu:GNOME",
                WAYLAND_DISPLAY="wayland-0",
            ),
            clear=True,
        ):
            self.assertEqual(sp._session_type(), "wayland-gnome")

    def test_wayland_wlroots(self):
        with mock.patch.dict(
            sp.os.environ,
            self._env(
                XDG_SESSION_TYPE="wayland",
                XDG_CURRENT_DESKTOP="sway",
                WAYLAND_DISPLAY="wayland-1",
            ),
            clear=True,
        ):
            self.assertEqual(sp._session_type(), "wayland-wlroots")

    def test_unknown(self):
        with mock.patch.dict(sp.os.environ, self._env(), clear=True):
            self.assertEqual(sp._session_type(), "unknown")


if __name__ == "__main__":
    unittest.main()
