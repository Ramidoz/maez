import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.brain_bench import bench
from scripts.brain_bench.bench import BenchmarkConfigError
from scripts.brain_bench.bench_packet import (
    ApiFamily,
    BenchPacket,
    GpuContention,
    OpsRubric,
    RestartRecovery,
    ScreenResult,
    StartupHealth,
    Topology,
    VariantReport,
)
from scripts.brain_bench.variants import ConfigSource


def _packet(label="cli_variant"):
    return BenchPacket(
        schema_version="bench_packet.v3",
        fixture_manifest_hash="f" * 64,
        variant_config_hash="c" * 64,
        variant_config_source="file",
        variants=(
            VariantReport(
                label=label,
                hard_pass=True,
                fail_reasons=(),
                p95_ms=3000,
                max_ms=3000,
                ops=OpsRubric(
                    api_family=ApiFamily.OLLAMA,
                    topology=Topology.REUSE_ENDPOINT,
                    bind_host_verified=True,
                    live_daemon_disturbance=False,
                    gpu_contention=GpuContention.NONE,
                    startup_health=StartupHealth.OK,
                    streaming_support=True,
                    restart_recovery=RestartRecovery.CLEAN,
                ),
            ),
        ),
        screen_result=ScreenResult.PASSES_SCREEN,
    )


class BrainBenchCliTests(unittest.TestCase):
    def test_main_requires_variants_config_and_does_not_import_model_config(self):
        sys.modules.pop("core.model_config", None)
        sys.modules.pop("core.routing.model_config", None)
        with self.assertRaises(BenchmarkConfigError):
            bench.main([])
        self.assertNotIn("core.model_config", sys.modules)
        self.assertNotIn("core.routing.model_config", sys.modules)

    def test_main_loads_file_registry_calls_full_battery_and_writes_packet(self):
        variants = [
            {
                "label": "cli-v",
                "base_url": "http://127.0.0.1:11434",
                "model": "m",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "variants.json"
            out_path = Path(tmp) / "packet.json"
            config_path.write_text(json.dumps(variants))
            stdout = io.StringIO()

            with mock.patch("scripts.brain_bench.bench.run_full_battery", return_value=_packet("distinctive-v")) as full, contextlib.redirect_stdout(stdout):
                code = bench.main(["--variants-config", str(config_path), "--out", str(out_path)])

            self.assertEqual(code, 0)
            self.assertTrue(out_path.exists())
            data = json.loads(out_path.read_text())
            self.assertEqual(data["variants"][0]["label"], "distinctive-v")
            self.assertIn(str(out_path), stdout.getvalue())
            self.assertIn("debug_dump=", stdout.getvalue())
            registry = full.call_args.args[0]
            self.assertEqual(registry.variant_config_source, ConfigSource.FILE)
            self.assertEqual(registry[0].label, "cli-v")
            self.assertIn("build_probe_run_fn", full.call_args.kwargs)

    def test_main_rejects_output_inside_debug_quarantine(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "variants.json"
            config_path.write_text(
                json.dumps(
                    [
                        {
                            "label": "cli-v",
                            "base_url": "http://127.0.0.1:11434",
                            "model": "m",
                        }
                    ]
                )
            )
            with self.assertRaises(BenchmarkConfigError):
                bench.main(
                    [
                        "--variants-config",
                        str(config_path),
                        "--out",
                        str(bench.DEFAULT_DEBUG_DUMP_DIR / "packet.json"),
                    ]
                )

    def test_main_packet_is_content_free_and_debug_dump_carries_raw_records(self):
        variants = [
            {
                "label": "cli-v",
                "base_url": "http://127.0.0.1:11434",
                "model": "m",
            }
        ]

        def fake_probe_run(_variant):
            from scripts.brain_bench.bench import ProbeSample

            return [
                ProbeSample(
                    probe_id="dated_hit",
                    sample_id="sample-1",
                    answer="Maez answered with FABRICATED_SENTINEL from context [E1].",
                    evidence="[E1] FABRICATED_SENTINEL",
                    false_absence=False,
                    grounded_categorical=True,
                    wrong_absence=False,
                    p95_ms=3000,
                    max_ms=3000,
                    latency_ms=3000,
                    ttft_ms=100,
                    tokens_per_sec=20.0,
                    ops_evidence=_packet().variants[0].ops,
                )
            ]

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "variants.json"
            out_path = Path(tmp) / "packet.json"
            config_path.write_text(json.dumps(variants))
            stdout = io.StringIO()

            with mock.patch(
                "scripts.brain_bench.probe_runner.build_probe_run",
                return_value=fake_probe_run,
            ), contextlib.redirect_stdout(stdout):
                bench.main(["--variants-config", str(config_path), "--out", str(out_path)])

            debug_line = next(line for line in stdout.getvalue().splitlines() if line.startswith("debug_dump="))
            debug_path = Path(debug_line.split("=", 1)[1])
            try:
                packet_blob = out_path.read_text()
                debug_blob = debug_path.read_text()
                self.assertNotIn("FABRICATED_SENTINEL", packet_blob)
                self.assertIn("FABRICATED_SENTINEL", debug_blob)
                self.assertIn('"provenance": "UNTRUSTED"', debug_blob)
            finally:
                debug_path.unlink(missing_ok=True)
