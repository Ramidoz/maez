import subprocess
import tempfile
import unittest
import json
import os
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
        with mock.patch("core.memory.ambient.active_window_for_preflight", return_value=None):
            self.assertTrue(sp._is_excluded_active_window())

    def test_known_safe_window_not_excluded(self):
        with mock.patch(
            "core.memory.ambient.active_window_for_preflight",
            return_value={"class": "Gnome-terminal", "title": "bash"},
        ):
            self.assertFalse(sp._is_excluded_active_window())

    def test_known_sensitive_window_excluded(self):
        with mock.patch(
            "core.memory.ambient.active_window_for_preflight",
            return_value={"class": "Bitwarden", "title": "Vault"},
        ):
            self.assertTrue(sp._is_excluded_active_window())

    def test_observe_excludes_before_capture_when_window_unreadable(self):
        with mock.patch.object(sp, "_is_enabled", return_value=True), \
             mock.patch.object(sp, "_is_paused", return_value=False), \
             mock.patch("core.memory.ambient.active_window_for_preflight", return_value=None), \
             mock.patch.object(sp, "_capture_screenshot") as cap, \
             mock.patch.object(sp, "_vision_endpoint_probe") as probe:
            obs = sp.observe()
        self.assertEqual(obs.state, "excluded")
        cap.assert_not_called()
        probe.assert_not_called()


class PreflightUsesTitleSurfaceTests(unittest.TestCase):
    def test_preflight_reads_title_bearing_surface(self):
        with mock.patch(
            "core.memory.ambient.active_window_for_preflight",
            return_value={"title": "Bank of X — Login", "class": "firefox"},
        ), \
             mock.patch("core.memory.ambient.active_window", return_value={"class": "firefox"}), \
             mock.patch.object(sp, "_exclusion_terms", return_value=("bank",)):
            self.assertTrue(sp._is_excluded_active_window())

    def test_preflight_none_excludes_even_if_public_surface_has_class(self):
        with mock.patch("core.memory.ambient.active_window_for_preflight", return_value=None), \
             mock.patch("core.memory.ambient.active_window", return_value={"class": "firefox"}):
            self.assertTrue(sp._is_excluded_active_window())


class ExclusionSetTests(unittest.TestCase):
    def test_sensitive_classes_and_titles_excluded(self):
        cases = [
            {"class": "Bitwarden", "title": "Vault"},
            {"class": "firefox", "title": "Online Banking — Chase"},
            {"class": "Signal", "title": "Alice"},
            {"class": "firefox", "title": "MyChart — Patient Portal"},
            {"class": "1Password", "title": ""},
            {"class": "firefox", "title": "Re: confidential salary — Gmail"},
            {"class": "Zoom", "title": "Weekly call"},
        ]
        for win in cases:
            with self.subTest(win=win), \
                 mock.patch("core.memory.ambient.active_window_for_preflight", return_value=win):
                self.assertTrue(sp._is_excluded_active_window(), win)

    def test_ordinary_windows_not_excluded(self):
        cases = (
            {"class": "Gnome-terminal", "title": "bash"},
            {"class": "Code", "title": "ambient.py"},
        )
        for win in cases:
            with self.subTest(win=win), \
                 mock.patch("core.memory.ambient.active_window_for_preflight", return_value=win):
                self.assertFalse(sp._is_excluded_active_window(), win)


class CaptureSelectionTests(unittest.TestCase):
    def test_x11_uses_x11_methods(self):
        with mock.patch.object(sp, "_session_type", return_value="x11"):
            names = [method["name"] for method in sp._capture_candidates()]
        self.assertIn("scrot", names)
        self.assertNotIn("gnome-shell-dbus", names)

    def test_gnome_wayland_prefers_noprompt_dbus_first(self):
        with mock.patch.object(sp, "_session_type", return_value="wayland-gnome"):
            names = [method["name"] for method in sp._capture_candidates()]
        self.assertEqual(names[0], "screencast")
        self.assertIn("gnome-shell-dbus", names)
        self.assertIn("portal", names)
        self.assertNotIn("scrot", names)

    def test_no_candidate_succeeds_returns_none(self):
        with mock.patch.object(sp, "_session_type", return_value="wayland-gnome"), \
             mock.patch.object(
                 sp,
                 "_capture_candidates",
                 return_value=[{"name": "x", "fn": lambda tmp: False}],
             ):
            self.assertIsNone(sp._capture_screenshot())


class GnomeShellCaptureTests(unittest.TestCase):
    def test_dbus_success_writes_file(self):
        def fake_run(cmd, **kw):
            path = cmd[-1]
            with open(path, "wb") as f:
                f.write(b"\x89PNG")
            return mock.Mock(returncode=0, stdout=f"(true, '{path}')")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/x.png"
            with mock.patch("subprocess.run", side_effect=fake_run):
                self.assertTrue(sp._capture_gnome_shell_dbus(path))

    def test_dbus_rejected_returns_false(self):
        with mock.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "gdbus"),
        ):
            self.assertFalse(sp._capture_gnome_shell_dbus("/tmp/x.png"))


class TempCleanupTests(unittest.TestCase):
    def test_capture_removes_temp_on_success(self):
        created = {}
        real_mktemp = sp.tempfile.mktemp

        def tracking_mktemp(*args, **kwargs):
            path = real_mktemp(*args, **kwargs)
            created["path"] = path
            return path

        def write_png(tmp):
            with open(tmp, "wb") as f:
                f.write(b"\x89PNG")
            return True

        with mock.patch.object(sp.tempfile, "mktemp", side_effect=tracking_mktemp), \
             mock.patch.object(
                 sp,
                 "_capture_candidates",
                 return_value=[{"name": "fake", "fn": write_png}],
             ):
            sp._capture_screenshot()

        self.assertFalse(sp.os.path.exists(created["path"]), "temp not cleaned up")

    def test_capture_removes_temp_on_failure_after_write(self):
        created = {}
        real_mktemp = sp.tempfile.mktemp

        def tracking_mktemp(*args, **kwargs):
            path = real_mktemp(*args, **kwargs)
            created["path"] = path
            return path

        def write_then_fail(tmp):
            with open(tmp, "wb") as f:
                f.write(b"partial")
            return False

        with mock.patch.object(sp.tempfile, "mktemp", side_effect=tracking_mktemp), \
             mock.patch.object(
                 sp,
                 "_capture_candidates",
                 return_value=[{"name": "fake", "fn": write_then_fail}],
             ):
            self.assertIsNone(sp._capture_screenshot())

        self.assertFalse(sp.os.path.exists(created["path"]), "temp not cleaned up")


class ScreencastCandidateTests(unittest.TestCase):
    def test_screencast_first_on_wayland_gnome(self):
        with mock.patch.object(sp, "_session_type", return_value="wayland-gnome"):
            names = [c["name"] for c in sp._capture_candidates()]
        self.assertEqual(names[0], "screencast")

    def test_helper_ok_writes_dest_and_unlinks_helper_temp(self):
        helper_tmp = tempfile.mktemp(prefix="maez-screencast-", suffix=".png")
        with open(helper_tmp, "wb") as f:
            f.write(b"\x89PNG-fake")
        dest = tempfile.mktemp(suffix=".png")
        fake = json.dumps(
            {
                "status": "ok",
                "temp_path": helper_tmp,
                "bytes": 9,
                "duration_ms": 5,
                "error_class": "",
            }
        )
        with mock.patch.object(
            sp.subprocess,
            "run",
            return_value=mock.Mock(returncode=0, stdout=fake),
        ):
            ok = sp._capture_via_screencast(dest)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(dest))
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), b"\x89PNG-fake")
        self.assertFalse(os.path.exists(helper_tmp))
        os.unlink(dest)

    def test_foreign_path_rejected(self):
        fake = json.dumps(
            {
                "status": "ok",
                "temp_path": "/etc/passwd",
                "bytes": 9,
                "duration_ms": 1,
                "error_class": "",
            }
        )
        with mock.patch.object(
            sp.subprocess,
            "run",
            return_value=mock.Mock(returncode=0, stdout=fake),
        ):
            ok = sp._capture_via_screencast("/tmp/dest.png")
        self.assertFalse(ok)

    def test_non_ok_status_returns_false(self):
        for status in ("needs_grant", "curtain_drawn", "capture_failed"):
            fake = json.dumps(
                {
                    "status": status,
                    "temp_path": None,
                    "bytes": 0,
                    "duration_ms": 0,
                    "error_class": "portal",
                }
            )
            with mock.patch.object(
                sp.subprocess,
                "run",
                return_value=mock.Mock(returncode=0, stdout=fake),
            ):
                self.assertFalse(sp._capture_via_screencast("/tmp/dest.png"))


if __name__ == "__main__":
    unittest.main()
