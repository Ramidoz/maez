# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3 proper — carve-out classification block in the judge prompt.

Per docs/slices/legacy/3-0c-carveout.md (RATIFIED 2026-05-07), the judge
prompt MUST encode:
  §3 exclusion list (verbatim categories)
  §2/§4 positive carve-out examples
  §4 negative carve-out examples
  §5 default-deny rule for ambiguous cases

Plus the slice-3-proper extension to ``judge()`` accepting an optional
``evidence_envelope`` kwarg that flows through to the prompt builder
(self_history + tool_results renders).

These are PROMPT-SHAPE tests. Behavioral tests against a live judge
endpoint are separate (test_judge_carveout_live.py, skipped when
endpoint absent).
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"

from core.cognition import grounding_judge as gj  # noqa: E402


def _build(**overrides):
    kwargs = dict(
        text="Paris is the capital of France.",
        signals_present=[],
        signals_absent=[],
        few_shots=[],
    )
    kwargs.update(overrides)
    return gj._build_judge_prompt(**kwargs)


class CarveOutBlockPresenceTests(unittest.TestCase):
    def test_carveout_section_header_present(self):
        prompt = _build()
        # Memo §1 wording — narrow, conservative carve-out, default-deny.
        self.assertIn("BACKGROUND-KNOWLEDGE CARVE-OUT", prompt)

    def test_default_deny_rule_present(self):
        prompt = _build()
        self.assertIn("default-deny", prompt.lower())

    def test_three_scope_dimensions_present(self):
        prompt = _build()
        # §2 the three constraints: stable, non-temporal, non-personal.
        for keyword in ("stable", "non-temporal", "non-personal"):
            self.assertIn(keyword, prompt.lower(),
                          f"missing scope dimension {keyword!r}")


class ExclusionListTests(unittest.TestCase):
    """§3 exclusion list — must surface verbatim category keywords so
    the judge can reject claims falling under them."""

    def setUp(self):
        self.prompt = _build()

    def test_legal_jurisdictional_excluded(self):
        # §3 says ALL legal/jurisdictional/regulatory claims are
        # excluded, broader than medical, due to liability.
        self.assertIn("legal", self.prompt.lower())
        for word in ("jurisdictional", "regulatory"):
            self.assertIn(word, self.prompt.lower(), f"missing {word!r}")

    def test_medical_advice_excluded(self):
        # §3: medical/financial ADVICE / DOSING / SAFETY excluded
        # categorically; stable biomedical FACTS may pass.
        self.assertIn("dosing", self.prompt.lower())

    def test_specific_numbers_dates_excluded(self):
        # §3: specific dates, numbers, quantities about real-world
        # entities (Eiffel height boundary).
        self.assertTrue(
            any(k in self.prompt.lower()
                for k in ("specific dates", "specific numbers",
                          "numerical specific")),
            "missing specific-numbers-about-entities exclusion",
        )

    def test_current_events_local_state_owner_excluded(self):
        for keyword in ("current events", "owner", "personal"):
            self.assertIn(keyword, self.prompt.lower(),
                          f"missing exclusion keyword {keyword!r}")


class PositiveExamplesTests(unittest.TestCase):
    """§2 positives that the carve-out IS designed to admit."""

    def setUp(self):
        self.prompt = _build()

    def test_paris_positive_present(self):
        self.assertIn("Paris is the capital of France", self.prompt)

    def test_python_typing_positive_present(self):
        self.assertIn("Python is dynamically typed", self.prompt)

    def test_photosynthesis_positive_present(self):
        self.assertIn("Photosynthesis", self.prompt)


class NegativeExamplesTests(unittest.TestCase):
    """§4 negatives — look eligible but aren't, default-deny."""

    def setUp(self):
        self.prompt = _build()

    def test_eiffel_height_negative_present(self):
        # §7.1 ratified default-deny on numerical specifics about
        # real-world entities.
        self.assertIn("330", self.prompt)

    def test_mona_lisa_date_negative_present(self):
        # §4 boundary: dates about real entities default-deny.
        self.assertIn("Mona Lisa", self.prompt)

    def test_aspirin_dosing_negative_present(self):
        # §4: medical dosing default-deny categorically.
        self.assertIn("aspirin", self.prompt.lower())


class JudgeEnvelopeKwargTests(unittest.TestCase):
    """Slice 3 proper additive surface: judge() accepts an optional
    evidence_envelope dict, extracts self_history (and tool_results
    when present), forwards to the prompt builder."""

    def _stub_call(self, captured: dict):
        def _impl(prompt: str) -> str:
            captured["prompt"] = prompt
            return '{"ungrounded": []}'
        return _impl

    def test_envelope_self_history_flows_through(self):
        captured: dict = {}
        with patch.object(gj, "_call_dedicated_judge",
                          self._stub_call(captured)):
            with patch.object(gj, "_JUDGE_BASE_URL",
                              "http://127.0.0.1:8081"):
                gj.judge(
                    text="As I told you earlier, the kettle was on.",
                    signals_present=[], signals_absent=[],
                    few_shots=[],
                    evidence_envelope={
                        "self_history": [{
                            "turn_id": "t-001",
                            "timestamp": 1700000000.0,
                            "kind": "model_reply",
                            "utterance_summary": "the kettle is on",
                        }],
                        "tool_results": [],
                        "signals_present": [],
                        "signals_absent": [],
                    },
                )
        self.assertIn("PRIOR UTTERANCES", captured["prompt"])
        self.assertIn("t-001", captured["prompt"])

    def test_envelope_tool_results_flows_through(self):
        captured: dict = {}
        with patch.object(gj, "_call_dedicated_judge",
                          self._stub_call(captured)):
            with patch.object(gj, "_JUDGE_BASE_URL",
                              "http://127.0.0.1:8081"):
                gj.judge(
                    text="The directory listing showed three files.",
                    signals_present=[], signals_absent=[],
                    few_shots=[],
                    evidence_envelope={
                        "self_history": [],
                        "tool_results": [{
                            "name": "ls",
                            "status": "ok",
                            "tool_call_id": "call-123",
                            "summary": "a.txt\nb.txt\nc.txt",
                        }],
                        "signals_present": [],
                        "signals_absent": [],
                    },
                )
        self.assertIn("TOOL RESULTS", captured["prompt"])
        self.assertIn("ls", captured["prompt"])

    def test_envelope_none_backward_compatible(self):
        captured: dict = {}
        with patch.object(gj, "_call_dedicated_judge",
                          self._stub_call(captured)):
            with patch.object(gj, "_JUDGE_BASE_URL",
                              "http://127.0.0.1:8081"):
                # No evidence_envelope kwarg — the existing signals_*
                # path must keep working unchanged.
                gj.judge(
                    text="The system is running.",
                    signals_present=["system stats"],
                    signals_absent=[],
                    few_shots=[],
                )
        self.assertIn("system stats", captured["prompt"])
        # Self-history block omitted when no history present.
        self.assertNotIn("PRIOR UTTERANCES", captured["prompt"])

    def test_partial_envelope_does_not_fall_back_to_legacy_kwargs(self):
        """Envelope present but missing some keys must NOT silently
        revert to the legacy signals_present/signals_absent kwargs.
        Full-takeover semantics — partial envelope means empty
        section, not legacy fallback. (Reviewer-flagged contract gap.)"""
        captured: dict = {}
        with patch.object(gj, "_call_dedicated_judge",
                          self._stub_call(captured)):
            with patch.object(gj, "_JUDGE_BASE_URL",
                              "http://127.0.0.1:8081"):
                gj.judge(
                    text="The system runs.",
                    signals_present=["LEGACY_SIGNAL"],
                    signals_absent=["LEGACY_ABSENT"],
                    few_shots=[],
                    evidence_envelope={
                        # only self_history present; sigs absent
                        "self_history": [],
                    },
                )
        self.assertNotIn("LEGACY_SIGNAL", captured["prompt"])
        self.assertNotIn("LEGACY_ABSENT", captured["prompt"])

    def test_envelope_signals_override_explicit_kwargs(self):
        """When both evidence_envelope and signals_present/absent are
        provided, the envelope wins (it's the canonical context)."""
        captured: dict = {}
        with patch.object(gj, "_call_dedicated_judge",
                          self._stub_call(captured)):
            with patch.object(gj, "_JUDGE_BASE_URL",
                              "http://127.0.0.1:8081"):
                gj.judge(
                    text="x",
                    signals_present=["LEGACY"], signals_absent=[],
                    few_shots=[],
                    evidence_envelope={
                        "signals_present": ["FROM_ENVELOPE"],
                        "signals_absent": [],
                        "tool_results": [],
                        "self_history": [],
                    },
                )
        self.assertIn("FROM_ENVELOPE", captured["prompt"])
        self.assertNotIn("LEGACY", captured["prompt"])


class CarveOutInsertionPlacementTests(unittest.TestCase):
    """Carve-out block sits AFTER the SELF-HISTORY RULE and BEFORE the
    EXAMPLES OF UNGROUNDED CLAIMS section. Order matters for prompt
    coherence."""

    def test_carveout_after_self_history_rule(self):
        prompt = _build(
            self_history=[{
                "turn_id": "t1", "timestamp": 1.0,
                "kind": "model_reply", "utterance_summary": "x",
            }],
        )
        idx_self_history = prompt.find("SELF-HISTORY RULE")
        idx_carveout = prompt.find("BACKGROUND-KNOWLEDGE CARVE-OUT")
        self.assertGreater(idx_self_history, -1)
        self.assertGreater(idx_carveout, -1)
        self.assertLess(
            idx_self_history, idx_carveout,
            "SELF-HISTORY RULE must precede carve-out block",
        )

    def test_carveout_before_response_to_judge(self):
        prompt = _build()
        idx_carveout = prompt.find("BACKGROUND-KNOWLEDGE CARVE-OUT")
        idx_response = prompt.find("RESPONSE TO JUDGE")
        self.assertLess(
            idx_carveout, idx_response,
            "carve-out must precede the audited response section",
        )


if __name__ == "__main__":
    unittest.main()
