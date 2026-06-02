from __future__ import annotations

import unittest


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

