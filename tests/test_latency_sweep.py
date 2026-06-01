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
        for key in (
            "ws_items",
            "input_tokens",
            "output_tokens",
            "ttft_ms",
            "total_ms",
            "tok_s",
        ):
            self.assertIn(key, row)

