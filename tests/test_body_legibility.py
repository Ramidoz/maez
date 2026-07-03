import ast
import inspect
import json
import os
import textwrap
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


def _routing_offenders(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    offenders: list[str] = []
    forbidden_calls = {
        "ambient_context",
        "call_tool",
        "current_weather",
        "dispatch_tool",
        "run_search",
        "search",
        "search_web",
        "web_search",
    }
    forbidden_import_roots = ("core.search",)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                name = fn.id
            elif isinstance(fn, ast.Attribute):
                name = fn.attr
            else:
                continue
            if name in forbidden_calls:
                offenders.append(f"call:{name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(forbidden_import_roots):
                offenders.append(f"import:{module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(forbidden_import_roots):
                    offenders.append(f"import:{alias.name}")
    return offenders


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

    def test_flag_off_envelope_matches_unset(self):
        from core.cognition.capability_card import _build_capability_envelope

        with mock.patch.dict(os.environ, {}, clear=True):
            unset = _build_capability_envelope(self._reg("searxng healthy"))
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "0"}, clear=True):
            off = _build_capability_envelope(self._reg("searxng healthy"))
        self.assertEqual(off, unset)

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

    def test_flag_off_prose_matches_unset(self):
        from core.cognition.capability_card import capability_prompt_block, reset_card_cache

        with mock.patch.dict(
            os.environ,
            {"MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1"},
            clear=True,
        ):
            with mock.patch(
                "core.cognition.capability_card.voice_boundary_enabled",
                return_value=False,
            ):
                unset = capability_prompt_block(self._reg("searxng healthy"))
        reset_card_cache()
        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "1",
                "MAEZ_BODY_LEGIBILITY": "0",
            },
            clear=True,
        ):
            with mock.patch(
                "core.cognition.capability_card.voice_boundary_enabled",
                return_value=False,
            ):
                off = capability_prompt_block(self._reg("searxng healthy"))
        self.assertEqual(off, unset)


class AmbientHonestyTests(unittest.TestCase):
    def _fmt(self, ctx):
        from core.memory import ambient_format

        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "1"}):
            return ambient_format._format(ctx)

    def test_attempted_and_failed_renders_unavailable(self):
        out = self._fmt({"weather": None, "coords_source": "phone"})
        self.assertIn("weather sense temporarily down", out.lower())
        self.assertIn("phone", out)
        for banned in ("°c", "error", "urlopen", "hostname", "traceback"):
            self.assertNotIn(banned, out.lower())

    def test_absent_key_stays_silent(self):
        out = self._fmt({"coords_source": "phone"})
        self.assertNotIn("weather", out.lower())

    def test_success_unchanged(self):
        out = self._fmt(
            {
                "weather": {
                    "temp_c": 21,
                    "conditions": "clear",
                    "coords": {"source": "phone"},
                }
            }
        )
        self.assertIn("21", out)
        self.assertNotIn("unavailable", out.lower())

    def test_flag_off_failed_pull_stays_silent(self):
        from core.memory import ambient_format

        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "0"}):
            out = ambient_format._format({"weather": None, "coords_source": "phone"})
        self.assertNotIn("unavailable", out.lower())

    def test_flag_off_failed_pull_matches_unset(self):
        from core.memory import ambient_format

        ctx = {"weather": None, "coords_source": "phone"}
        with mock.patch.dict(os.environ, {}, clear=True):
            unset = ambient_format._format(ctx)
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "0"}, clear=True):
            off = ambient_format._format(ctx)
        self.assertEqual(off, unset)


class NoRoutingChangeTests(unittest.TestCase):
    def test_routing_scanner_trips_on_synthetic_invocations(self):
        synthetic = """
        def changed(ctx):
            from core.search.searxng_client import SearxngBackend
            current_weather()
            web_search("weather")
        """
        self.assertEqual(
            _routing_offenders(synthetic),
            [
                "import:core.search.searxng_client",
                "call:current_weather",
                "call:web_search",
            ],
        )

    def test_changed_functions_add_no_routing_or_tool_invocation(self):
        from core.cognition import capability_card
        from core.memory import ambient_format

        functions = (
            capability_card._affordance,
            capability_card._build_capability_envelope,
            capability_card.capability_prompt_block,
            ambient_format._format,
        )
        offenders: list[str] = []
        for fn in functions:
            for offender in _routing_offenders(inspect.getsource(fn)):
                offenders.append(f"{fn.__name__}:{offender}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
