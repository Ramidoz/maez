import os
import unittest
from unittest import mock


_RECALL_FLAGS = (
    "MAEZ_RECALL_TRIAD_ENABLED",
    "MAEZ_DISPATCHER_ENABLED",
    "MAEZ_FOCUSED_COGNITION_ENABLED",
    "MAEZ_LIVING_RECALL_ENABLED",
)


def _clean_env(**values):
    env = {name: "" for name in _RECALL_FLAGS}
    env.update(values)
    return mock.patch.dict(os.environ, env, clear=False)


class DaemonWebGatePreservationTest(unittest.TestCase):
    def test_triad_on_with_nonempty_transcript_suppresses_legacy_web(self):
        import daemon.maez_daemon as md

        with _clean_env(MAEZ_RECALL_TRIAD_ENABLED="1"):
            self.assertFalse(md._daemon_parallel_web_search_enabled("some transcript"))

    def test_triad_on_with_empty_transcript_keeps_fallback(self):
        import daemon.maez_daemon as md

        with _clean_env(MAEZ_RECALL_TRIAD_ENABLED="1"):
            self.assertTrue(md._daemon_parallel_web_search_enabled(""))
            self.assertTrue(md._daemon_parallel_web_search_enabled("   "))

    def test_triad_off_keeps_legacy_web(self):
        import daemon.maez_daemon as md

        with _clean_env():
            self.assertTrue(md._daemon_parallel_web_search_enabled("some transcript"))

    def test_focused_enabled_tracks_bundle(self):
        import daemon.maez_daemon as md

        with _clean_env():
            self.assertFalse(md._focused_cognition_enabled())
        with _clean_env(MAEZ_RECALL_TRIAD_ENABLED="1"):
            self.assertTrue(md._focused_cognition_enabled())

    def test_raw_focused_flag_alone_is_inert(self):
        import daemon.maez_daemon as md

        with _clean_env(MAEZ_FOCUSED_COGNITION_ENABLED="1"):
            self.assertFalse(md._focused_cognition_enabled())


class TelegramVoiceGateTest(unittest.TestCase):
    def test_pipeline_a_web_search_disabled_when_triad_on(self):
        from skills import telegram_voice

        with _clean_env(MAEZ_RECALL_TRIAD_ENABLED="1"):
            self.assertFalse(telegram_voice._telegram_pipeline_a_web_search_enabled())

    def test_pipeline_a_web_search_enabled_when_triad_off(self):
        from skills import telegram_voice

        with _clean_env():
            self.assertTrue(telegram_voice._telegram_pipeline_a_web_search_enabled())

    def test_raw_dispatcher_flag_alone_does_not_disable_pipeline_a_web(self):
        from skills import telegram_voice

        with _clean_env(MAEZ_DISPATCHER_ENABLED="1"):
            self.assertTrue(telegram_voice._telegram_pipeline_a_web_search_enabled())


if __name__ == "__main__":
    unittest.main()
