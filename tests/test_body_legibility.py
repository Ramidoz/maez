import json
import os
import unittest
from unittest import mock


class AffordanceTests(unittest.TestCase):
    def test_web_sense_affordance_is_state_aware(self):
        from core.cognition.capability_card import _affordance

        self.assertEqual(
            _affordance("web sense", "healthy"),
            "can retrieve current external information",
        )
        self.assertNotIn("can retrieve", _affordance("web sense", "degraded") or "")
        self.assertNotIn("can retrieve", _affordance("web sense", "unknown") or "")
        self.assertIsNotNone(_affordance("web sense", "degraded"))

    def test_affordance_is_generic_no_examples(self):
        from core.cognition.capability_card import _affordance

        text = (_affordance("web sense", "healthy") or "").lower()
        for banned in ("weather", "stock", "news", "sports", "forecast"):
            self.assertNotIn(banned, text)

    def test_unknown_sense_has_no_affordance(self):
        from core.cognition.capability_card import _affordance

        self.assertIsNone(_affordance("felt time", "attached"))

    def test_flag_helper_strict(self):
        from core.cognition.capability_card import body_legibility_enabled

        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "1"}):
            self.assertTrue(body_legibility_enabled())
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "0"}):
            self.assertFalse(body_legibility_enabled())


def _extract_payload(envelope_text: str) -> dict:
    start = envelope_text.index("{")
    end = envelope_text.rindex("}") + 1
    return json.loads(envelope_text[start:end])


class CardModeTests(unittest.TestCase):
    def setUp(self):
        from core.cognition.capability_card import reset_card_cache

        reset_card_cache()
        self.addCleanup(reset_card_cache)

    def _reg(self, raw):
        return [("web sense", lambda: raw)]

    def test_structured_envelope_affordance_is_a_parsed_field(self):
        from core.cognition.capability_card import _build_capability_envelope

        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "1"}):
            payload = _extract_payload(
                _build_capability_envelope(self._reg("searxng healthy"))
            )
        entry = next(e for e in payload["entries"] if e["name"] == "web sense")
        self.assertEqual(
            entry["affordance"], "can retrieve current external information"
        )

    def test_flag_off_envelope_byte_identical(self):
        from core.cognition.capability_card import _build_capability_envelope

        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "0"}):
            payload = _extract_payload(
                _build_capability_envelope(self._reg("searxng healthy"))
            )
        entry = next(e for e in payload["entries"] if e["name"] == "web sense")
        self.assertNotIn("affordance", entry)

    def test_prose_mode_canonicalizes_raw_before_affordance(self):
        from core.cognition.capability_card import capability_prompt_block

        with mock.patch.dict(
            os.environ,
            {"MAEZ_BODY_LEGIBILITY": "1", "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1"},
        ):
            with mock.patch(
                "core.cognition.capability_card.voice_boundary_enabled",
                return_value=False,
            ):
                healthy = capability_prompt_block(self._reg("searxng healthy"))
                from core.cognition.capability_card import reset_card_cache

                reset_card_cache()
                degraded = capability_prompt_block(self._reg("searxng degraded"))
        self.assertIn("searxng healthy", healthy)
        self.assertIn("— can retrieve current external information", healthy)
        self.assertIn("searxng degraded", degraded)
        self.assertIn("retrieval currently degraded", degraded)
        self.assertNotIn("can retrieve", degraded)

    def test_prose_probe_error_unknown_does_not_overclaim(self):
        from core.cognition.capability_card import capability_prompt_block

        def _boom():
            raise RuntimeError("probe down")

        with mock.patch.dict(
            os.environ,
            {"MAEZ_BODY_LEGIBILITY": "1", "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1"},
        ):
            with mock.patch(
                "core.cognition.capability_card.voice_boundary_enabled",
                return_value=False,
            ):
                out = capability_prompt_block([("web sense", _boom)])
        self.assertIn("unknown (probe error)", out)
        self.assertNotIn("can retrieve", out)


if __name__ == "__main__":
    unittest.main()
