import inspect
import unittest
from types import SimpleNamespace

from scripts.brain_bench import latency_sweep


class LatencySweepTest(unittest.TestCase):
    def test_sweep_produces_attribution_rows(self):
        def stub_stream(*, variant, payload):
            yield {"content": "hello "}
            yield {"content": "world"}

        rows = latency_sweep.run_sweep(
            ws_item_counts=(1, 4, 7),
            output_modes=("short", "long"),
            variant=SimpleNamespace(
                model="stub",
                chat_kwargs={},
                draft_model=None,
            ),
            stream_factory=stub_stream,
        )
        self.assertTrue(rows)
        self.assertEqual(len(rows), 6)
        row = rows[0]
        expected_keys = {
            "ws_items",
            "input_tokens",
            "output_tokens",
            "ttft_ms",
            "total_ms",
            "tok_s",
        }
        self.assertEqual(set(row), expected_keys)
        self.assertTrue(all(isinstance(row[key], int | float) for key in expected_keys))
        self.assertFalse({"answer", "reply", "evidence", "question", "messages"} & set(row))

    def test_sweep_does_not_import_live_focused_path(self):
        source = inspect.getsource(latency_sweep)
        self.assertNotIn("core.routing.focused_cognition", source)
        self.assertNotIn("focused_synthesize", source)
        self.assertNotIn("assemble_working_set", source)
