import inspect
import os
import unittest

import daemon.maez_daemon as maez_daemon
from core.cognition.capability_card import reset_card_cache
from core.routing import focused_cognition


class VoiceBoundaryBothPathsTest(unittest.TestCase):
    def setUp(self):
        reset_card_cache()
        self._saved = {
            k: os.environ.get(k)
            for k in ("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", "MAEZ_VOICE_BOUNDARY_ENABLED")
        }
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        os.environ.pop("MAEZ_VOICE_BOUNDARY_ENABLED", None)

    def tearDown(self):
        reset_card_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_focused_path_uses_envelope_when_voice_boundary_on(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()

        card = focused_cognition._focused_capability_card()

        self.assertIn("capability_state", card)
        self.assertIn("private grounding", card)
        self.assertIn("Do not quote", card)
        self.assertNotIn("YOUR LIVE BODY", card)

    def test_focused_path_uses_old_prose_when_voice_boundary_off(self):
        card = focused_cognition._focused_capability_card()

        self.assertIn("YOUR LIVE BODY (live/cached substrate probe)", card)
        self.assertNotIn("capability_state", card)

    def test_daemon_and_focused_paths_share_one_renderer(self):
        daemon_src = inspect.getsource(maez_daemon.MaezDaemon.handle_message)
        focused_src = inspect.getsource(focused_cognition._focused_capability_card)

        self.assertIn("capability_prompt_block", daemon_src)
        self.assertIn("capability_prompt_block", focused_src)


if __name__ == "__main__":
    unittest.main()
