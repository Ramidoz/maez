from __future__ import annotations

import unittest


def _candidate(source_type: str, text: str, *, salience: int = 10, durable_id: str = ""):
    from core.cognition.cycle_packet import CycleEvidenceCandidate

    return CycleEvidenceCandidate(
        source_type=source_type,
        text=text,
        durable_id=durable_id or f"id-{source_type}-{abs(hash(text))}",
        salience=salience,
    )


def _est_tokens(items) -> int:
    return sum(max(1, len(getattr(item, "text", "")) // 4) for item in items)


class CycleVocabTest(unittest.TestCase):
    def test_cycle_source_types_have_distinct_authority_labels(self):
        from core.routing.focused_cognition import _authority_label

        for source_type in (
            "action_outcome",
            "signal_absence",
            "open_loop",
            "builder_event",
            "quality_signal",
        ):
            label = _authority_label(source_type)
            self.assertNotEqual(
                label,
                "unverified",
                f"{source_type} missing an authority label",
            )

        self.assertIn("absence", _authority_label("signal_absence").lower())


class CyclePacketSelectorTest(unittest.TestCase):
    def test_packet_respects_token_budget(self):
        from core.cognition.cycle_packet import select_cycle_evidence

        candidates = [
            _candidate("memory_context", f"memory item {idx} " + ("x" * 500))
            for idx in range(80)
        ]
        items = select_cycle_evidence(candidates, budget_tokens=3000)

        self.assertLessEqual(_est_tokens(items), 3000)

    def test_no_single_source_crowds_out_others(self):
        from core.cognition.cycle_packet import select_cycle_evidence

        candidates = [
            _candidate("memory_context", f"memory item {idx} " + ("m" * 900))
            for idx in range(80)
        ]
        candidates.extend(
            [
                _candidate("action_outcome", "wmctrl failed after three retries", salience=100),
                _candidate(
                    "signal_absence",
                    "screen observation unavailable; do not infer user activity",
                    salience=100,
                ),
                _candidate("open_loop", "unresolved want: inspect recall latency", salience=90),
            ]
        )

        items = select_cycle_evidence(candidates, budget_tokens=3000)
        kinds = {item.source_type for item in items}

        self.assertIn("action_outcome", kinds)
        self.assertIn("signal_absence", kinds)
        self.assertIn("open_loop", kinds)

    def test_signal_absence_survives_selection_under_tight_budget(self):
        from core.cognition.cycle_packet import select_cycle_evidence

        candidates = [
            _candidate("memory_context", "large memory " + ("m" * 1800), salience=50),
            _candidate(
                "signal_absence",
                "screen observation unavailable; do not fabricate what Rohit is doing",
                salience=20,
            ),
            _candidate("quality_signal", "recent cycle was too vague", salience=40),
        ]

        items = select_cycle_evidence(candidates, budget_tokens=500)

        self.assertTrue(
            any(item.source_type == "signal_absence" for item in items),
            "absence rail dropped under tight budget — fabrication risk",
        )

    def test_errs_toward_inclusion_when_salience_uncertain(self):
        from core.cognition.cycle_packet import select_cycle_evidence

        candidates = [
            _candidate("open_loop", "uncertain but unresolved wondering", salience=0),
            _candidate("quality_signal", "uncertain quality nudge", salience=0),
        ]

        items = select_cycle_evidence(candidates, budget_tokens=300)

        self.assertEqual({item.source_type for item in items}, {"open_loop", "quality_signal"})

    def test_items_are_evidence_not_summaries(self):
        from core.cognition.cycle_packet import build_cycle_packet, select_cycle_evidence

        candidates = [
            _candidate(
                "signal_absence",
                "screen observation unavailable; do not infer user activity",
                salience=100,
            ),
            _candidate("action_outcome", "last tool call failed with exit code 1", salience=90),
        ]
        items = select_cycle_evidence(candidates, budget_tokens=3000)
        working_set = build_cycle_packet(items)

        for item in items:
            self.assertTrue(item.source_type)
            self.assertTrue(item.durable_id)
        self.assertIn("[E1]", working_set.ordered_evidence_text)
        self.assertIn("signal_absence", working_set.ordered_evidence_text)
        self.assertNotIn("summary:", working_set.ordered_evidence_text.lower())

    def test_reflection_instruction_allows_honest_silence(self):
        from core.cognition.cycle_packet import CYCLE_REFLECTION_INSTRUCTION

        lowered = CYCLE_REFLECTION_INSTRUCTION.lower()

        self.assertIn("evidence", lowered)
        self.assertIn("signal_absence", lowered)
        self.assertTrue("nothing" in lowered or "say so" in lowered)
        self.assertNotIn("always produce", lowered)
