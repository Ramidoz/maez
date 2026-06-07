import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import model_refresh


class PacketTests(unittest.TestCase):
    def test_candidate_packet_required_fields_and_content_free(self):
        packet = model_refresh.build_packet(
            candidate="qwen3vl-4b",
            runtime_path="/home/rohit/llama.cpp-release/llama-deadbeef/llama-server",
            runtime_version="llama.cpp build deadbeef",
            model_repo="Qwen/Qwen3-VL-4B-Instruct-GGUF",
            model_files=["Qwen3VL-4B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"],
            license="apache-2.0",
            quantization="Q4_K_M+Q8_0-mmproj",
            service_port=8082,
            load_status="not_started",
            vram_before_mib=3975,
            vram_after_load_mib=None,
            vram_after_image_mib=None,
            smoke_status="not_run",
            benchmark_status="not_run",
            latency_ms=None,
            decision="candidate",
            rollback="stop llama-vision.service; leave llama-server.service and llama-judge.service unchanged",
        )

        required = {
            "candidate",
            "runtime_path",
            "runtime_version",
            "model_repo",
            "model_files",
            "license",
            "quantization",
            "service_port",
            "load_status",
            "vram_before_mib",
            "vram_after_load_mib",
            "vram_after_image_mib",
            "smoke_status",
            "benchmark_status",
            "latency_ms",
            "decision",
            "rollback",
        }
        self.assertEqual(required, set(packet))
        encoded = json.dumps(packet)
        self.assertNotIn("restore_token", encoded)
        self.assertNotIn("data:image", encoded)
        self.assertNotIn("screen content", encoded.lower())

    def test_invalid_decision_rejected(self):
        with self.assertRaises(ValueError):
            model_refresh.build_packet(
                candidate="bad",
                runtime_path="/tmp/llama-server",
                runtime_version="x",
                model_repo="repo",
                model_files=[],
                license="unknown",
                quantization="q4",
                service_port=8082,
                load_status="not_started",
                vram_before_mib=1,
                vram_after_load_mib=None,
                vram_after_image_mib=None,
                smoke_status="not_run",
                benchmark_status="not_run",
                latency_ms=None,
                decision="ship_it_anyway",
                rollback="rollback",
            )

    def test_write_packet_uses_logs_model_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = {"candidate": "qwen3vl-4b", "decision": "candidate"}
            out = model_refresh.write_packet(packet, root=Path(tmp), timestamp="20260606T120000")
            self.assertEqual(
                Path(tmp) / "logs" / "model_refresh" / "20260606T120000-qwen3vl-4b.json", out
            )
            self.assertTrue(out.exists())
            self.assertEqual(packet, json.loads(out.read_text()))

    def test_write_packet_rejects_unsafe_explicit_timestamp(self):
        unsafe_timestamps = [
            "",
            "../escape",
            "..\\escape",
            "../../escape",
            "/tmp/escape",
            "C:\\tmp\\escape",
            "20260606T120000:escape",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            packet = {"candidate": "qwen3vl-4b", "decision": "candidate"}
            for timestamp in unsafe_timestamps:
                with self.subTest(timestamp=timestamp):
                    with self.assertRaises(ValueError):
                        model_refresh.write_packet(packet, root=Path(tmp), timestamp=timestamp)


class RuntimeDiscoveryTests(unittest.TestCase):
    def test_parse_llama_help_detects_mmproj_and_mtp(self):
        help_text = """
        --mmproj FILE
        --mmproj-offload
        --spec-type none,draft,eagle3,mtp,ngram-simple
        """
        support = model_refresh.parse_llama_help(help_text)
        self.assertTrue(support["mmproj"])
        self.assertTrue(support["mmproj_offload"])
        self.assertTrue(support["mtp"])

    def test_parse_llama_help_reports_missing_mtp_without_crash(self):
        help_text = "--mmproj FILE\n--spec-type none,draft,eagle3,ngram-simple\n"
        support = model_refresh.parse_llama_help(help_text)
        self.assertTrue(support["mmproj"])
        self.assertFalse(support["mtp"])

    def test_parse_llama_help_ignores_mtp_outside_spec_type_line(self):
        help_text = """
        --mmproj FILE
        --spec-type none,draft,eagle3,ngram-simple
        example: mtp draft models are configured elsewhere
        """
        support = model_refresh.parse_llama_help(help_text)
        self.assertTrue(support["mmproj"])
        self.assertFalse(support["mtp"])

    def test_parse_nvidia_smi_csv(self):
        row = "NVIDIA GeForce RTX 4090, 24564 MiB, 20053 MiB, 3975 MiB"
        parsed = model_refresh.parse_nvidia_smi_csv(row)
        self.assertEqual(24564, parsed["total_mib"])
        self.assertEqual(20053, parsed["used_mib"])
        self.assertEqual(3975, parsed["free_mib"])

    def test_parse_nvidia_smi_csv_rejects_malformed_rows(self):
        malformed_rows = [
            "NVIDIA GeForce RTX 4090, 24564 MiB, 20053 MiB",
            "NVIDIA GeForce RTX 4090, 24564, 20053 MiB, 3975 MiB",
            "NVIDIA GeForce RTX 4090, -24564 MiB, 20053 MiB, 3975 MiB",
            "NVIDIA GeForce RTX 4090, 24564 MiB trailing, 20053 MiB, 3975 MiB",
        ]
        for row in malformed_rows:
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    model_refresh.parse_nvidia_smi_csv(row)

    def test_verify_model_alias_from_models_response(self):
        response = {"data": [{"id": "maez-vision", "aliases": ["maez-vision"]}]}
        self.assertTrue(model_refresh.response_has_model_alias(response, "maez-vision"))
        self.assertFalse(model_refresh.response_has_model_alias(response, "qwen2.5-vl-3b"))

    def test_cli_nvidia_smi_row_prints_parsed_json(self):
        stdout = io.StringIO()
        argv = [
            "model_refresh.py",
            "--nvidia-smi-row",
            "NVIDIA GeForce RTX 4090, 24564 MiB, 20053 MiB, 3975 MiB",
        ]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            self.assertEqual(0, model_refresh.main())
        self.assertEqual(
            {"free_mib": 3975, "total_mib": 24564, "used_mib": 20053},
            json.loads(stdout.getvalue()),
        )

    def test_cli_llama_server_prints_help_support_json(self):
        stdout = io.StringIO()
        argv = ["model_refresh.py", "--llama-server", "/tmp/llama-server"]
        completed = mock.Mock(stdout="--mmproj FILE\n--mmproj-offload\n--spec-type mtp\n")
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch("scripts.model_refresh.subprocess.run", return_value=completed) as run,
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(0, model_refresh.main())
        run.assert_called_once_with(
            ["/tmp/llama-server", "--help"],
            text=True,
            stdout=model_refresh.subprocess.PIPE,
            stderr=model_refresh.subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(
            {"mmproj": True, "mmproj_offload": True, "mtp": True},
            json.loads(stdout.getvalue()),
        )


class VisionServiceTemplateTests(unittest.TestCase):
    def test_render_vision_service_uses_8082_and_does_not_touch_judge(self):
        text = model_refresh.render_vision_service(
            runtime="/home/rohit/llama.cpp-release/llama-deadbeef/llama-server",
            model="/home/rohit/maez/models/llamacpp/vision/Qwen3VL-4B-Instruct-Q4_K_M.gguf",
            mmproj="/home/rohit/maez/models/llamacpp/vision/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf",
            alias="maez-vision",
            port=8082,
            ctx_size=4096,
        )
        self.assertIn("Description=llama.cpp vision server", text)
        self.assertIn("--port 8082", text)
        self.assertIn("--alias maez-vision", text)
        self.assertIn(
            "--mmproj /home/rohit/maez/models/llamacpp/vision/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf",
            text,
        )
        self.assertNotIn("--port 8081", text)
        self.assertNotIn("llama-judge", text)

    def test_render_vision_service_rejects_judge_and_main_ports(self):
        for port in (8080, 8081):
            with self.subTest(port=port):
                with self.assertRaises(ValueError):
                    model_refresh.render_vision_service(
                        runtime="/bin/llama-server",
                        model="/models/v.gguf",
                        mmproj="/models/mmproj.gguf",
                        alias="maez-vision",
                        port=port,
                        ctx_size=4096,
                    )

    def test_cli_render_vision_service_prints_template(self):
        stdout = io.StringIO()
        argv = [
            "model_refresh.py",
            "--render-vision-service",
            "--runtime",
            "/bin/llama-server",
            "--model-path",
            "/models/v.gguf",
            "--mmproj-path",
            "/models/mmproj.gguf",
            "--alias",
            "maez-vision",
            "--port",
            "8082",
            "--ctx-size",
            "4096",
        ]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            self.assertEqual(0, model_refresh.main())
        text = stdout.getvalue()
        self.assertIn("ExecStart=/bin/llama-server", text)
        self.assertIn("-m /models/v.gguf", text)
        self.assertIn("--mmproj /models/mmproj.gguf", text)
        self.assertIn("--alias maez-vision", text)
        self.assertIn("--port 8082", text)
        self.assertIn("--ctx-size 4096", text)


if __name__ == "__main__":
    unittest.main()
