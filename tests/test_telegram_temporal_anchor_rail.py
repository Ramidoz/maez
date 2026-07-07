from __future__ import annotations

import unittest
from unittest import mock


class TelegramTemporalAnchorRailTests(unittest.TestCase):
    def test_flag_off_preserves_prompt_context_byte_identically(self):
        from core.cognition.temporal_anchor import anchor_prompt_context

        memory_block = "[RECALLED MEMORY]\nYesterday's meeting was still pending."
        with mock.patch.dict(
            "os.environ",
            {"MAEZ_TEMPORAL_ANCHOR_SHADOW": "0", "MAEZ_TEMPORAL_ANCHOR_ENFORCE": "0"},
            clear=False,
        ):
            anchored = anchor_prompt_context(
                memory_block,
                elapsed_seconds=9 * 3600,
            )

        self.assertEqual(memory_block, anchored)
        self.assertEqual(memory_block.encode("utf-8"), anchored.encode("utf-8"))

    def test_shadow_logs_without_changing_prompt_context(self):
        from core.cognition import temporal_anchor

        memory_block = "[RECALLED MEMORY]\nYesterday's meeting was still pending."
        with mock.patch.dict(
            "os.environ",
            {"MAEZ_TEMPORAL_ANCHOR_SHADOW": "1", "MAEZ_TEMPORAL_ANCHOR_ENFORCE": "0"},
            clear=False,
        ), mock.patch.object(temporal_anchor.logger, "info") as info:
            anchored = temporal_anchor.anchor_prompt_context(
                memory_block,
                elapsed_seconds=9 * 3600,
            )

        self.assertEqual(memory_block, anchored)
        info.assert_called_once()
        self.assertIn("temporal_anchor_shadow", info.call_args.args[0])

    def test_enforce_over_three_hours_marks_memory_as_past_with_elapsed_hours(self):
        from core.cognition.temporal_anchor import anchor_prompt_context

        memory_block = "[RECALLED MEMORY]\nYesterday's meeting was still pending."
        with mock.patch.dict(
            "os.environ",
            {"MAEZ_TEMPORAL_ANCHOR_SHADOW": "0", "MAEZ_TEMPORAL_ANCHOR_ENFORCE": "1"},
            clear=False,
        ):
            anchored = anchor_prompt_context(
                memory_block,
                elapsed_seconds=(9 * 3600) + 90,
            )

        self.assertIn("[previous conversation, 9 hours ago - not current]", anchored)
        self.assertIn(memory_block, anchored)

    def test_enforce_under_three_hours_leaves_prompt_context_unchanged(self):
        from core.cognition.temporal_anchor import anchor_prompt_context

        memory_block = "[RECALLED MEMORY]\nEarlier thread context."
        with mock.patch.dict(
            "os.environ",
            {"MAEZ_TEMPORAL_ANCHOR_SHADOW": "0", "MAEZ_TEMPORAL_ANCHOR_ENFORCE": "1"},
            clear=False,
        ):
            anchored = anchor_prompt_context(
                memory_block,
                elapsed_seconds=(2 * 3600) + 59,
            )

        self.assertEqual(memory_block, anchored)


if __name__ == "__main__":
    unittest.main()
