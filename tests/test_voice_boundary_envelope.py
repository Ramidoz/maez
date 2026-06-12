import json
import os
import unittest

from core.cognition.capability_card import capability_prompt_block, reset_card_cache


def _fake_registry():
    return (
        ("web sense", lambda: "searxng healthy"),
        ("page read", lambda: "on"),
        ("search commitment", lambda: "gatekeeper mode"),
        ("felt time", lambda: "attached"),
    )


def _boom_registry():
    def _boom():
        raise RuntimeError("probe down")

    return (("web sense", _boom),)


class VoiceBoundaryEnvelopeTest(unittest.TestCase):
    OLD_PROSE_HEADER = "YOUR LIVE BODY (live/cached substrate probe)"

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

    def test_flag_off_returns_exact_old_prose(self):
        out = capability_prompt_block(registry=_fake_registry())
        self.assertIn(self.OLD_PROSE_HEADER, out)
        self.assertIn("search commitment: gatekeeper mode", out)
        self.assertNotIn("capability_state", out)

    def test_precedence_off_returns_empty_regardless_of_voice_flag(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "0"
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        self.assertEqual(capability_prompt_block(registry=_fake_registry()), "")

    def test_flag_on_emits_structured_envelope(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        out = capability_prompt_block(registry=_fake_registry())
        self.assertNotIn(self.OLD_PROSE_HEADER, out)
        start = out.index("{")
        end = out.rindex("}") + 1
        payload = json.loads(out[start:end])
        self.assertEqual(payload["kind"], "capability_state")
        self.assertEqual(payload["freshness"], "live_or_cached_30s")
        self.assertEqual(payload["authority"], "current_self_capability_state")
        self.assertIn("outranks stale memory", payload["precedence"])
        names = {e["name"]: e for e in payload["entries"]}
        self.assertEqual(names["web sense"]["status"], "healthy")
        self.assertEqual(names["search commitment"]["status"], "on")
        self.assertEqual(names["felt time"]["status"], "attached")
        self.assertEqual(names["web sense"]["source"], "probe")
        self.assertEqual(names["page read"]["source"], "flag")

    def test_flag_on_envelope_carries_no_dashboard_jargon(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        out = capability_prompt_block(registry=_fake_registry())
        self.assertNotIn("gatekeeper mode", out)
        self.assertNotIn("searxng", out)

    def test_flag_on_includes_voice_boundary_instruction(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        out = capability_prompt_block(registry=_fake_registry())
        self.assertIn("private grounding", out)
        self.assertIn("Do not quote", out)
        self.assertIn("do not override this state", out)

    def test_flag_on_unknown_probe_is_explicit_not_missing(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        out = capability_prompt_block(registry=_boom_registry())
        start = out.index("{")
        end = out.rindex("}") + 1
        payload = json.loads(out[start:end])
        entry = payload["entries"][0]
        self.assertEqual(entry["status"], "unknown")
        self.assertEqual(entry["error"], "probe_error")

    def test_30s_cache_preserved_under_flag_on(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        first = capability_prompt_block(registry=_fake_registry())
        second = capability_prompt_block(registry=_boom_registry())
        self.assertEqual(first, second)
