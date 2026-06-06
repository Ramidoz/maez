from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

import skills.screen_perception as sp
from skills.screen_perception import ScreenObservation


class ScreenObservationShapeTests(unittest.TestCase):
    def _obs(self, **kw):
        base = dict(
            activity="",
            application="",
            detail="",
            focus_level="",
            raw_response="",
            timestamp=0.0,
            success=False,
        )
        base.update(kw)
        return ScreenObservation(**base)

    def test_new_fields_default(self):
        o = self._obs(state="ok", success=True, activity="coding")
        self.assertFalse(o.third_party_content_present)
        self.assertEqual(o.egress_origin_class, "owner_screen_context")

    def test_paused_and_excluded_are_honest_blind(self):
        for state in ("paused", "excluded"):
            with self.subTest(state=state):
                o = self._obs(state=state, detail="SHOULD_NOT_APPEAR")
                ctx = o.format_for_context()
                self.assertNotIn("SHOULD_NOT_APPEAR", ctx)


class PausePrimitiveTests(unittest.TestCase):
    def test_paused_skips_capture_probe_vision(self):
        tmp = tempfile.mkdtemp()
        pause = os.path.join(tmp, "paused")
        open(pause, "w").close()

        with mock.patch.dict(
            os.environ,
            {"MAEZ_SCREEN_PERCEPTION": "1", "MAEZ_SCREEN_PAUSE_FILE": pause},
            clear=False,
        ), mock.patch.object(sp, "_capture_screenshot") as cap, mock.patch.object(
            sp, "_vision_endpoint_probe"
        ) as probe, mock.patch.object(sp.requests, "post") as post:
            obs = sp.observe()

        self.assertEqual(obs.state, "paused")
        cap.assert_not_called()
        probe.assert_not_called()
        post.assert_not_called()


class PreflightExclusionTests(unittest.TestCase):
    def test_excluded_app_is_never_looked_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            pause = os.path.join(tmp, "absent")
            with mock.patch.dict(
                os.environ,
                {"MAEZ_SCREEN_PERCEPTION": "1", "MAEZ_SCREEN_PAUSE_FILE": pause},
                clear=False,
            ), mock.patch(
                "core.memory.ambient.active_window",
                return_value={"class": "KeePassXC", "title": "vault"},
            ), mock.patch.object(sp, "_vision_endpoint_probe") as probe, mock.patch.object(
                sp, "_capture_screenshot"
            ) as cap, mock.patch.object(sp.requests, "post") as post:
                obs = sp.observe()

        self.assertEqual(obs.state, "excluded")
        probe.assert_not_called()
        cap.assert_not_called()
        post.assert_not_called()

    def test_non_excluded_app_proceeds_to_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            pause = os.path.join(tmp, "absent")
            with mock.patch.dict(
                os.environ,
                {"MAEZ_SCREEN_PERCEPTION": "1", "MAEZ_SCREEN_PAUSE_FILE": pause},
                clear=False,
            ), mock.patch(
                "core.memory.ambient.active_window",
                return_value={"class": "code", "title": "plan.md"},
            ), mock.patch.object(sp, "_vision_endpoint_probe", return_value=False) as probe:
                obs = sp.observe()

        probe.assert_called_once()
        self.assertEqual(obs.state, "unavailable")


class ThirdPartyMinimizationTests(unittest.TestCase):
    def test_vision_prompt_requests_third_party_flag(self):
        self.assertIn("THIRD_PARTY:", sp.VISION_PROMPT)

    def test_parse_vision_response_carries_third_party_field(self):
        parsed = sp._parse_vision_response(
            "ACTIVITY: reading\n"
            "APPLICATION: mail\n"
            "DETAIL: inbox\n"
            "FOCUS_LEVEL: browsing\n"
            "THIRD_PARTY: yes\n"
        )
        self.assertEqual(parsed["third_party"], "yes")

    def test_third_party_detail_is_minimized(self):
        parsed = {
            "activity": "reading email",
            "application": "thunderbird",
            "detail": "Email from Jane Doe about the lawsuit settlement",
            "focus_level": "browsing",
            "third_party": "yes",
        }
        obs = sp._apply_screen_governance(parsed, timestamp=0.0, raw="r")
        self.assertTrue(obs.third_party_content_present)
        self.assertEqual(obs.egress_origin_class, "third_party_private_context")
        self.assertNotIn("Jane", obs.detail)
        self.assertNotIn("lawsuit", obs.detail)
        self.assertNotIn("Jane", obs.format_for_context())

    def test_uncertain_or_missing_is_third_party(self):
        parsed = {
            "activity": "x",
            "application": "unknown",
            "detail": "d",
            "focus_level": "x",
            "third_party": "",
        }
        self.assertTrue(sp._looks_third_party(parsed))
        self.assertTrue(sp._looks_third_party({**parsed, "third_party": "unsure"}))
        self.assertTrue(
            sp._looks_third_party({**parsed, "application": "Signal", "third_party": "no"})
        )

    def test_owner_only_keeps_detail(self):
        parsed = {
            "activity": "coding",
            "application": "code",
            "detail": "editing plan.md",
            "focus_level": "deep_work",
            "third_party": "no",
        }
        obs = sp._apply_screen_governance(parsed, timestamp=0.0, raw="r")
        self.assertFalse(obs.third_party_content_present)
        self.assertEqual(obs.egress_origin_class, "owner_screen_context")
        self.assertIn("plan.md", obs.detail)


if __name__ == "__main__":
    unittest.main()
