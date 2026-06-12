from __future__ import annotations

import os
import unittest

from core.routing.evidence_state import (
    EvidenceState,
    build_evidence_precedence_directive,
    build_turn_final_context,
    turn_evidence_state,
)


class TurnEvidenceStateTests(unittest.TestCase):
    def test_detects_positive_markers(self):
        state = turn_evidence_state(
            transcript="[memory context] Recent Reddit substrate rows:\n- r/LocalLLaMA ...",
            web_context="",
        )
        self.assertTrue(state.evidence_present)
        self.assertIn("memory context", state.marker_labels)

    def test_negative_markers_not_evidence(self):
        state = turn_evidence_state(
            transcript="[no fresh evidence available: LIVE_REDDIT:EMPTY:NONE:FRESH_ATTEMPT_FAILED]",
            web_context="",
        )
        self.assertFalse(state.evidence_present)

    def test_legacy_web_results_present_vs_empty(self):
        present = turn_evidence_state(
            transcript="",
            web_context="[WEB SEARCH: 'x'] 3 results - 2026\n  1. Title\n     snippet",
        )
        self.assertTrue(present.evidence_present)
        self.assertIn("web search results", present.marker_labels)

        empty = turn_evidence_state(
            transcript="",
            web_context="[WEB SEARCH: 'x'] No results found.",
        )
        self.assertFalse(empty.evidence_present)

    def test_excludes_background(self):
        state = turn_evidence_state(
            transcript="some lived recall and ambient context, no markers",
            web_context="",
        )
        self.assertFalse(state.evidence_present)

    def test_directive_names_markers_and_forbids_blocked_claim(self):
        state = turn_evidence_state(
            transcript="[fresh evidence] LIVE_REDDIT: recent posts",
            web_context="",
        )
        directive = build_evidence_precedence_directive(state)
        self.assertIn("EVIDENCE PRESENT THIS TURN", directive)
        self.assertIn("fresh evidence", directive)
        self.assertTrue(
            directive.rstrip().endswith("the evidence above contradicts that.")
        )

    def test_build_turn_final_context_dispatcher_and_legacy(self):
        directive = "DIRECTIVE"
        self.assertEqual(
            build_turn_final_context("TRANSCRIPT_CTX", directive),
            "TRANSCRIPT_CTX\n\nDIRECTIVE",
        )
        self.assertEqual(build_turn_final_context("", directive), "DIRECTIVE")
        self.assertEqual(
            build_turn_final_context("TRANSCRIPT_CTX", ""),
            "TRANSCRIPT_CTX",
        )


class DirectiveExtensionTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", None))

    def _state(self):
        return EvidenceState(
            evidence_present=True,
            marker_labels=("memory evidence", "fresh evidence"),
            source_hint=("memory", "web"),
            descriptions=("", ""),
        )

    def test_flag_off_directive_string_identical(self):
        base = build_evidence_precedence_directive(self._state())
        self.assertIn("EVIDENCE PRESENT THIS TURN.", base)
        self.assertIn("You may NOT claim the relevant source is blocked", base)
        self.assertNotIn("CONTEXTUALIZE", base)

    def test_flag_on_appends_the_precedence_rule(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        text = build_evidence_precedence_directive(self._state())
        self.assertIn("Recalled memories may CONTEXTUALIZE the fresh evidence", text)
        self.assertIn("re-read the evidence text itself", text)
        self.assertIn("You may NOT claim the relevant source is blocked", text)

    def test_flag_on_extension_is_appended_last(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        text = build_evidence_precedence_directive(self._state())
        self.assertGreater(
            text.index("Recalled memories may CONTEXTUALIZE"),
            text.index("You may NOT claim"),
        )


if __name__ == "__main__":
    unittest.main()
