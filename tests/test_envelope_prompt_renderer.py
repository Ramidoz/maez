# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3 wiring: prompt-block renderer for the evidence envelope.

The renderer turns the envelope dict into the human-readable block
specified in docs/LEDGER_ENVELOPE_SCHEMA.md §3.2 — the constraint
section the daemon injects into the LLM's generation prompt:

    [EVIDENCE ENVELOPE — TURN <turn_id>]
    You may claim:
      - "..."
    You may NOT claim:
      - ...
    If you must speak about a forbidden topic, name the absence
    instead of confabulating.
    [END ENVELOPE]

Disabled mode (envelope is None) returns "" so the prompt assembly
stays identical to legacy.
"""
from __future__ import annotations

import os
import unittest

os.environ["MAEZ_TEST_MODE"] = "1"

from core.cognition import envelope_builder as eb  # noqa: E402


class NoneAndEmptyTests(unittest.TestCase):
    def test_none_envelope_renders_empty(self):
        self.assertEqual(eb.render_envelope_for_prompt(None), "")

    def test_disabled_envelope_renders_empty(self):
        # Disabled-mode envelope (builder returns None, but if a caller
        # accidentally passes an empty/disabled-marker dict, render
        # nothing rather than a malformed header).
        empty = {
            "tool_results": [], "claimable": [], "forbidden": [],
            "self_history": [], "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(empty)
        # Empty envelope: no constraints to surface, render nothing.
        self.assertEqual(rendered, "")


class HeaderAndFooterTests(unittest.TestCase):
    def test_header_includes_turn_id(self):
        env = {
            "turn_id": "turn-abc-123",
            "tool_results": [], "claimable": [],
            "forbidden": [{"topic": "calendar", "reason": "absent"}],
            "self_history": [], "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        self.assertIn("[EVIDENCE ENVELOPE — TURN turn-abc-123]", rendered)
        self.assertIn("[END ENVELOPE]", rendered)

    def test_header_without_turn_id(self):
        env = {
            "forbidden": [{"topic": "x", "reason": "y"}],
            "tool_results": [], "claimable": [], "self_history": [],
            "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        self.assertIn("[EVIDENCE ENVELOPE", rendered)
        self.assertIn("[END ENVELOPE]", rendered)


class ClaimableSectionTests(unittest.TestCase):
    def test_claimable_rendered_as_you_may_claim(self):
        env = {
            "claimable": [
                {"text": "owner is at his desk",
                 "provenance": "observed",
                 "evidence": "presence snapshot"},
                {"text": "owner asked about X",
                 "provenance": "owner-said"},
            ],
            "tool_results": [], "forbidden": [], "self_history": [],
            "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        self.assertIn("You may claim", rendered)
        self.assertIn("owner is at his desk", rendered)
        self.assertIn("observed", rendered)
        self.assertIn("owner-said", rendered)


class AuditEvidenceSectionTests(unittest.TestCase):
    def test_tool_results_render_when_audit_can_use_them(self):
        env = {
            "tool_results": [{
                "name": "web_tool_loop",
                "status": "ok",
                "tool_call_id": "call-123",
                "summary": "Observed disk usage from real tool output.",
            }],
            "claimable": [], "forbidden": [], "self_history": [],
            "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        self.assertIn("Tool results available", rendered)
        self.assertIn("web_tool_loop", rendered)
        self.assertIn("Observed disk usage", rendered)

    def test_self_history_renders_when_audit_can_use_it(self):
        env = {
            "self_history": [{
                "turn_id": "turn-1",
                "kind": "model_reply",
                "utterance_summary": "I said I did not have a grounded answer.",
                "lifecycle_stage": "gestation",
            }],
            "tool_results": [], "claimable": [], "forbidden": [],
            "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        self.assertIn("Prior Maez utterances", rendered)
        self.assertIn("pre-birth / build-stage", rendered)
        self.assertIn("I said I did not have a grounded answer", rendered)

    def test_signals_present_render_when_audit_can_use_them(self):
        env = {
            "signals_present": ["configured model identity", "body capability registry"],
            "tool_results": [], "claimable": [], "forbidden": [],
            "self_history": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        self.assertIn("Signals present", rendered)
        self.assertIn("configured model identity", rendered)


class ForbiddenSectionTests(unittest.TestCase):
    def test_forbidden_rendered_as_you_may_not_claim(self):
        env = {
            "forbidden": [
                {"topic": "calendar", "reason": "signal absent"},
                {"topic": "screen contents", "reason": "no screen this turn"},
            ],
            "claimable": [], "tool_results": [], "self_history": [],
            "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        self.assertIn("You may NOT claim", rendered)
        self.assertIn("calendar", rendered)
        self.assertIn("signal absent", rendered)

    def test_signals_absent_become_forbidden_topics(self):
        # If the envelope only has signals_absent (no explicit
        # forbidden entries), the renderer derives a "you may not
        # claim about <signal>" line per absent signal — that is
        # exactly the §3.2 example pattern.
        env = {
            "signals_absent": ["calendar", "screen observation"],
            "forbidden": [], "claimable": [], "tool_results": [],
            "self_history": [], "signals_present": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        self.assertIn("calendar", rendered)
        self.assertIn("screen observation", rendered)
        self.assertIn("You may NOT claim", rendered)


class FooterInstructionTests(unittest.TestCase):
    def test_forbidden_footer_instructs_naming_the_absence(self):
        env = {
            "signals_absent": ["calendar"],
            "forbidden": [], "claimable": [], "tool_results": [],
            "self_history": [], "signals_present": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        # Per §3.2, footer instruction MUST appear so the model
        # knows the right behavior on a forbidden topic.
        self.assertIn("name the absence", rendered.lower())


class TruncatedFallbackTests(unittest.TestCase):
    def test_truncated_envelope_renders_with_warning(self):
        # When the builder emits the §3a minimal-fallback shape
        # (_truncated=True), the renderer should still produce a
        # block — just with a "(truncated)" marker so the model
        # knows context is partial.
        env = {
            "_truncated": True,
            "_truncation_reason": "preserved-sections exceeded cap",
            "schema_version": 1,
            "tool_results": [{"name": "ls", "status": "ok"}],
            "forbidden": [{"topic": "calendar"}],
            "claimable": [], "self_history": [],
            "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        self.assertIn("[EVIDENCE ENVELOPE", rendered)
        self.assertIn("truncated", rendered.lower())


class RendererEdgeCaseTests(unittest.TestCase):
    """Reviewer-flagged (2026-05-07): renderer must not emit malformed
    lines when claim entries are degenerate. Also: structured evidence
    fields must render readably, not as Python repr."""

    def test_empty_text_claimable_skipped(self):
        env = {
            "claimable": [
                {"text": "", "provenance": "observed"},
                {"text": "real claim", "provenance": "observed"},
                {"text": None, "provenance": "observed"},
                {"fact": "", "provenance": "observed"},
            ],
            "forbidden": [], "tool_results": [], "self_history": [],
            "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        # Empty/None text claimables MUST NOT emit a `  - ""` line.
        self.assertNotIn('- ""', rendered)
        self.assertIn("real claim", rendered)

    def test_evidence_dict_renders_as_json_not_python_repr(self):
        env = {
            "claimable": [{
                "text": "owner is at his desk",
                "provenance": "observed",
                "evidence_refs": {"snapshot_id": "abc-123",
                                  "timestamp": 1700000000},
            }],
            "forbidden": [], "tool_results": [], "self_history": [],
            "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        # Python repr produces single-quoted keys: {'snapshot_id': ...}
        # JSON produces double-quoted keys: {"snapshot_id": ...}
        # Per memo / readability, use JSON-shaped output.
        self.assertNotIn("'snapshot_id'", rendered)
        self.assertIn('"snapshot_id"', rendered)

    def test_evidence_list_renders_as_json(self):
        env = {
            "claimable": [{
                "text": "tool ran",
                "provenance": "tool-verified",
                "evidence_refs": ["call-1", "call-2"],
            }],
            "forbidden": [], "tool_results": [], "self_history": [],
            "signals_present": [], "signals_absent": [],
        }
        rendered = eb.render_envelope_for_prompt(env)
        # JSON-shaped, not str([..]) shape.
        self.assertIn('"call-1"', rendered)


if __name__ == "__main__":
    unittest.main()
