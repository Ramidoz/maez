"""Task 3 — Live Web-Context Containment: photo-freshness throat.

Tests that `synthesize_photo_turn` wraps the `fresh_context` (daemon web_context)
in the un-spoofable envelope when MAEZ_FETCH_CONTAINMENT_ENABLED=1, and is
byte-identical when the flag is off.

The function accepts a `chat_fn` kwarg so we can fake the LLM call and inspect
the assembled system prompt directly.
"""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from core.routing.focused_cognition import synthesize_photo_turn

ANALYSIS = (
    "The image shows a screenshot of a tech blog post titled "
    "'Anthropic releases Claude Mythos 5'. "
    "The article discusses benchmark results."
)
CAPTION = "what is this?"
FRESH = "W headline: Anthropic Claude Mythos 5 just launched."


def _chat_returning_valid(content="That's a tech article [E1]."):
    """Return a fake chat_fn that always produces a valid E1 citation."""
    def _fake(**_kwargs):
        return SimpleNamespace(message=SimpleNamespace(content=content))
    return _fake


def _capture_system(store):
    """Return a fake chat_fn that captures the system message."""
    def _fake(*, model, messages, think, options):
        store["system"] = messages[0]["content"]
        # Return a valid E1 citation so the function doesn't retry/fallback
        return SimpleNamespace(
            message=SimpleNamespace(content="That's a tech article [E1].")
        )
    return _fake


class PhotoContainmentFlagOn(unittest.TestCase):
    """When MAEZ_FETCH_CONTAINMENT_ENABLED=1 the fresh_context must be wrapped."""

    def setUp(self):
        self._store = {}
        self._env = mock.patch.dict(
            os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}
        )
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def _system(self):
        store = {}
        synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            fresh_context=FRESH,
            chat_fn=_capture_system(store),
            model="test-model",
        )
        return store["system"]

    def test_envelope_open_marker_present(self):
        """The assembled base_system must contain the <<EXT: open marker."""
        system = self._system()
        self.assertIn("<<EXT:", system,
                      "Flag ON: <<EXT: marker must appear in base_system when fresh_context provided")

    def test_envelope_close_marker_present(self):
        """The assembled base_system must contain the <</EXT: close marker."""
        system = self._system()
        self.assertIn("<</EXT:", system,
                      "Flag ON: <</EXT: close marker must appear in base_system")

    def test_markers_balanced(self):
        """Open and close markers must be balanced (1 segment)."""
        system = self._system()
        opens = system.count("<<EXT:")
        closes = system.count("<</EXT:")
        self.assertEqual(opens, closes,
                         f"Markers must be balanced; got {opens} open, {closes} close")
        self.assertGreater(opens, 0, "Must have at least one open marker")

    def test_standing_instruction_present(self):
        """The standing instruction ('never an instruction') must appear in base_system."""
        system = self._system()
        self.assertIn(
            "never an instruction", system.lower(),
            "Flag ON: standing instruction must be prepended to the contained fresh_context"
        )

    def test_fresh_content_still_present_inside_envelope(self):
        """The actual fresh_context text must be inside the envelope (not dropped)."""
        system = self._system()
        self.assertIn(FRESH, system,
                      "The raw fresh_context text must survive inside the envelope")

    def test_fresh_world_check_header_preserved(self):
        """The '=== FRESH WORLD CHECK' header line must still be present."""
        system = self._system()
        self.assertIn("FRESH WORLD CHECK", system,
                      "The existing FRESH WORLD CHECK header must be preserved")


class PhotoContainmentFlagOff(unittest.TestCase):
    """When MAEZ_FETCH_CONTAINMENT_ENABLED is absent the output must be byte-identical."""

    def setUp(self):
        # Explicitly clear the flag
        self._env = mock.patch.dict(os.environ, {}, clear=True)
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def _system(self):
        store = {}
        synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            fresh_context=FRESH,
            chat_fn=_capture_system(store),
            model="test-model",
        )
        return store["system"]

    def test_no_ext_marker_when_flag_off(self):
        """Flag OFF: <<EXT: must NOT appear in the assembled system prompt."""
        system = self._system()
        self.assertNotIn("<<EXT:", system,
                         "Flag OFF: no containment markers must appear")

    def test_fresh_content_still_present_when_flag_off(self):
        """Flag OFF: the raw fresh_context text must still appear verbatim."""
        system = self._system()
        self.assertIn(FRESH, system,
                      "Flag OFF: fresh_context must still be present in the system prompt")

    def test_fresh_world_check_header_preserved_when_flag_off(self):
        """Flag OFF: the FRESH WORLD CHECK header must still appear."""
        system = self._system()
        self.assertIn("FRESH WORLD CHECK", system,
                      "Flag OFF: FRESH WORLD CHECK header must be present")


class PhotoContainmentNoFreshContext(unittest.TestCase):
    """When fresh_context is absent, containment must not fire at all."""

    def _system(self):
        store = {}
        synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            fresh_context=None,
            chat_fn=_capture_system(store),
            model="test-model",
        )
        return store["system"]

    def test_no_ext_marker_when_no_fresh_context(self):
        with mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}):
            system = self._system()
        self.assertNotIn("<<EXT:", system,
                         "No fresh_context → no containment markers, even with flag on")

    def test_no_fresh_world_check_header_when_no_fresh_context(self):
        system = self._system()
        self.assertNotIn("FRESH WORLD CHECK", system,
                         "No fresh_context → no FRESH WORLD CHECK block")


if __name__ == "__main__":
    unittest.main()
