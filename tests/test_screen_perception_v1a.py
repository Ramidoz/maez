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


if __name__ == "__main__":
    unittest.main()
