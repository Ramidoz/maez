import unittest
from types import SimpleNamespace
from unittest import mock


class EnvelopeModeTests(unittest.TestCase):
    def test_self_card_mode_uses_assembled_card_without_time_line(self):
        from core.continuity_fingerprint import envelope

        with (
            mock.patch(
                "core.continuity_fingerprint.envelope._self_card_enabled",
                return_value=True,
            ),
            mock.patch(
                "core.continuity_fingerprint.envelope.assemble_self_card_from_paths",
                return_value=SimpleNamespace(
                    text="assembled persistent self-card",
                    receipt=lambda: {"line_sources": ("soul.base", "soul.local")},
                ),
            ) as assemble,
        ):
            env, snap = envelope.build_probe_envelope()

        self.assertTrue(snap["self_card_applied"])
        self.assertIn("assembled persistent self-card", env)
        assemble.assert_called_once()
        _, kwargs = assemble.call_args
        self.assertIsNone(kwargs["time_line_candidate"])
        self.assertFalse(kwargs["time_line_applied"])
        for banned in ("felt", "gpu", "capability_state", "=== EVIDENCE"):
            self.assertNotIn(banned.lower(), env.lower())

    def test_legacy_mode_uses_voice_card_text(self):
        from core.continuity_fingerprint import envelope
        from core.routing.focused_cognition import _VOICE_CARD_TEXT

        with mock.patch(
            "core.continuity_fingerprint.envelope._self_card_enabled",
            return_value=False,
        ):
            env, snap = envelope.build_probe_envelope()

        self.assertFalse(snap["self_card_applied"])
        self.assertIn(_VOICE_CARD_TEXT[:40], env)

    def test_snapshot_has_all_component_hashes(self):
        from core.continuity_fingerprint import envelope

        _, snap = envelope.build_probe_envelope()

        for key in (
            "base_model",
            "soul_base_hash",
            "soul_local_hash",
            "frame_text_hash",
            "policy_hash",
            "self_card_applied",
        ):
            self.assertIn(key, snap)

    def test_never_calls_voice_card(self):
        import inspect

        import core.continuity_fingerprint.envelope as envelope

        self.assertNotIn("_voice_card(", inspect.getsource(envelope))


if __name__ == "__main__":
    unittest.main()
