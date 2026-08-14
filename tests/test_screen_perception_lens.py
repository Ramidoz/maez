import subprocess
import tempfile
import unittest
import json
import os
from unittest import mock

from PIL import Image

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

    def test_title_only_window_is_excluded_as_class_unavailable(self):
        reason = sp.active_window_preflight_reason(
            {"class": "", "title": "ordinary document"}
        )

        self.assertEqual(reason, "class_unavailable")

    def test_supplied_snapshot_uses_authority_without_rereading_window(self):
        snapshot = {"class": "Code", "title": "plan.md"}
        with mock.patch(
            "core.memory.ambient.active_window_for_preflight",
            side_effect=AssertionError("supplied snapshot must not be re-read"),
        ):
            reason = sp.active_window_preflight_reason(snapshot)

        self.assertIsNone(reason)

    def test_oversized_title_or_class_is_excluded_before_matching(self):
        self.assertEqual(
            sp.active_window_preflight_reason(
                {"class": "Code", "title": "x" * 1025}
            ),
            "window_schema_invalid",
        )
        self.assertEqual(
            sp.active_window_preflight_reason(
                {"class": "x" * 257, "title": "ordinary"}
            ),
            "class_unavailable",
        )

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

    def test_curtain_stops_entire_capture_loop_before_any_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            curtain = os.path.join(tmpdir, "curtain")
            with open(curtain, "w", encoding="utf-8"):
                pass
            screencast = mock.Mock(return_value=False)
            def would_capture(path):
                with open(path, "wb") as handle:
                    handle.write(b"captured despite curtain")
                return True

            gnome_dbus = mock.Mock(side_effect=would_capture)
            portal = mock.Mock(return_value=True)
            candidates = [
                {"name": "screencast", "fn": screencast},
                {"name": "gnome-shell-dbus", "fn": gnome_dbus},
                {"name": "portal", "fn": portal},
            ]
            with mock.patch.dict(
                os.environ,
                {"MAEZ_SCREEN_CURTAIN_FILE": curtain},
                clear=False,
            ), mock.patch.object(sp, "_capture_candidates", return_value=candidates):
                result = sp._capture_screenshot()

        self.assertIsNone(result)
        screencast.assert_not_called()
        gnome_dbus.assert_not_called()
        portal.assert_not_called()

    def test_curtain_drawn_between_candidates_stops_all_fallbacks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            curtain = os.path.join(tmpdir, "curtain")

            def screencast_observes_new_curtain(_path):
                with open(curtain, "w", encoding="utf-8"):
                    pass
                return False

            screencast = mock.Mock(side_effect=screencast_observes_new_curtain)
            def fallback_would_capture(path):
                with open(path, "wb") as handle:
                    handle.write(b"fallback captured after curtain")
                return True

            gnome_dbus = mock.Mock(side_effect=fallback_would_capture)
            portal = mock.Mock(return_value=True)
            candidates = [
                {"name": "screencast", "fn": screencast},
                {"name": "gnome-shell-dbus", "fn": gnome_dbus},
                {"name": "portal", "fn": portal},
            ]
            with mock.patch.dict(
                os.environ,
                {"MAEZ_SCREEN_CURTAIN_FILE": curtain},
                clear=False,
            ), mock.patch.object(sp, "_capture_candidates", return_value=candidates):
                result = sp._capture_screenshot()

        self.assertIsNone(result)
        screencast.assert_called_once()
        gnome_dbus.assert_not_called()
        portal.assert_not_called()

    def test_curtain_drawn_during_success_discards_captured_bytes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            curtain = os.path.join(tmpdir, "curtain")

            def captures_while_curtain_closes(path):
                with open(path, "wb") as handle:
                    handle.write(b"captured while curtain closed")
                with open(curtain, "w", encoding="utf-8"):
                    pass
                return True

            candidate = mock.Mock(side_effect=captures_while_curtain_closes)
            with mock.patch.dict(
                os.environ,
                {"MAEZ_SCREEN_CURTAIN_FILE": curtain},
                clear=False,
            ), mock.patch.object(
                sp,
                "_capture_candidates",
                return_value=[{"name": "successful", "fn": candidate}],
            ):
                result = sp._capture_screenshot()

        self.assertIsNone(result)
        candidate.assert_called_once()

    def test_curtain_drawn_during_encoding_blocks_every_return_path(self):
        def write_raw(path):
            with open(path, "wb") as handle:
                handle.write(b"raw bytes")
            return True

        def write_png(path):
            Image.new("RGB", (2, 2), color=(1, 2, 3)).save(path, format="PNG")
            return True

        for writer in (write_raw, write_png):
            with self.subTest(writer=writer.__name__), mock.patch.object(
                sp,
                "screen_privacy_state",
                side_effect=[None, None, None, "curtain_drawn"],
            ) as privacy, mock.patch.object(
                sp,
                "_capture_candidates",
                return_value=[{"name": writer.__name__, "fn": writer}],
            ):
                result = sp._capture_screenshot()

            self.assertIsNone(result)
            self.assertEqual(privacy.call_count, 4)


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
