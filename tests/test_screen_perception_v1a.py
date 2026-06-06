from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
