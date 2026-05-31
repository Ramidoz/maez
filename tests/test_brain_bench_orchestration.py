import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.brain_bench.bench import (
    debug_dump_metadata,
    derive_screen_result,
    run_benchmark,
    write_debug_dump,
)
from scripts.brain_bench.bench_packet import FailReason, ScreenResult
from scripts.brain_bench.variants import load_variants


def _registry():
    return load_variants(
        json.dumps(
            [
                {
                    "label": "variant",
                    "base_url": "http://127.0.0.1:11434",
                    "model": "m",
                }
            ]
        ),
        source="file",
    )


class DebugDumpTests(unittest.TestCase):
    def test_debug_dump_is_quarantine_tagged_in_written_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_debug_dump(
                Path(root),
                records=[{"answer": "FABRICATED_SENTINEL", "evidence": "[E1] raw"}],
                fixture_manifest_hash="f" * 64,
                variant_config_hash="c" * 64,
            )
            data = json.loads(path.read_text())

        self.assertEqual(data["metadata"]["provenance"], "UNTRUSTED")
        self.assertTrue(data["metadata"]["quarantined"])
        self.assertFalse(data["metadata"]["promotable"])
        self.assertIn("FABRICATED_SENTINEL", json.dumps(data))
        self.assertEqual(debug_dump_metadata()["provenance"], "UNTRUSTED")


class ScreenResultPrecedenceTests(unittest.TestCase):
    def test_screen_result_precedence(self):
        self.assertEqual(
            derive_screen_result([{"hard_pass": True, "over_ceiling": False}]),
            ScreenResult.PASSES_SCREEN,
        )
        self.assertEqual(
            derive_screen_result([{"hard_pass": False, "over_ceiling": True, "honesty_clean": True}]),
            ScreenResult.FAILS_TOO_SLOW,
        )
        self.assertEqual(
            derive_screen_result([{"hard_pass": False, "over_ceiling": False, "honesty_clean": False}]),
            ScreenResult.FAILS_DISHONEST,
        )


class OrchestrationTests(unittest.TestCase):
    def test_negative_control_no_text_leak(self):
        def dishonest_probe(_variant):
            return {
                "answer": "FABRICATED_SENTINEL",
                "evidence": "[E1] FABRICATED_SENTINEL",
                "false_absence": True,
                "grounded_categorical": False,
                "wrong_absence": False,
                "p95_ms": 3000,
                "max_ms": 3000,
                "ttft_ms": 100,
                "tokens_per_sec": 20.0,
            }

        with tempfile.TemporaryDirectory() as root:
            packet = run_benchmark(
                _registry(),
                fixture_manifest_hash="f" * 64,
                probe_run=dishonest_probe,
                debug_dump_dir=Path(root),
            )
            packet_blob = json.dumps(packet.to_dict())
            dump_blob = "\n".join(path.read_text() for path in Path(root).iterdir())

        self.assertFalse(packet.variants[0].hard_pass)
        self.assertIn(FailReason.FALSE_ABSENCE, packet.variants[0].fail_reasons)
        self.assertNotIn("FABRICATED_SENTINEL", packet_blob)
        self.assertIn("FABRICATED_SENTINEL", dump_blob)
        self.assertIn('"provenance": "UNTRUSTED"', dump_blob)

    def test_judging_phase_opens_only_judge_port(self):
        seen_ports = []

        @contextlib.contextmanager
        def fake_no_egress(*, allow_loopback_ports=()):
            seen_ports.append(tuple(allow_loopback_ports))
            yield

        def clean_probe(_variant):
            return {
                "answer": "Maez answered from dated context with [E1].",
                "evidence": "[E1] context",
                "false_absence": False,
                "grounded_categorical": True,
                "wrong_absence": False,
                "p95_ms": 3000,
                "max_ms": 3000,
                "ttft_ms": 100,
                "tokens_per_sec": 20.0,
            }

        with mock.patch("scripts.brain_bench.bench.no_egress", fake_no_egress):
            run_benchmark(
                _registry(),
                fixture_manifest_hash="f" * 64,
                probe_run=clean_probe,
                call_judge=lambda **_kw: "TIE",
                judge_base_url="http://127.0.0.1:8081",
            )

        self.assertIn((11434,), seen_ports)
        self.assertIn((8081,), seen_ports)
        self.assertNotIn((11434, 8081), seen_ports)
        self.assertNotIn((8081, 11434), seen_ports)


if __name__ == "__main__":
    unittest.main()
