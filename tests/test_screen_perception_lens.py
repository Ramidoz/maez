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


class PreflightFailSafeTests(unittest.TestCase):
    def test_undetermined_window_is_excluded(self):
        with mock.patch("core.memory.ambient.active_window", return_value=None):
            self.assertTrue(sp._is_excluded_active_window())

    def test_known_safe_window_not_excluded(self):
        with mock.patch(
            "core.memory.ambient.active_window",
            return_value={"class": "Gnome-terminal", "title": "bash"},
        ):
            self.assertFalse(sp._is_excluded_active_window())

    def test_known_sensitive_window_excluded(self):
        with mock.patch(
            "core.memory.ambient.active_window",
            return_value={"class": "Bitwarden", "title": "Vault"},
        ):
            self.assertTrue(sp._is_excluded_active_window())

    def test_observe_excludes_before_capture_when_window_unreadable(self):
        with mock.patch.object(sp, "_is_enabled", return_value=True), \
             mock.patch.object(sp, "_is_paused", return_value=False), \
             mock.patch("core.memory.ambient.active_window", return_value=None), \
             mock.patch.object(sp, "_capture_screenshot") as cap, \
             mock.patch.object(sp, "_vision_endpoint_probe") as probe:
            obs = sp.observe()
        self.assertEqual(obs.state, "excluded")
        cap.assert_not_called()
        probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
