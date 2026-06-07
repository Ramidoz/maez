import json
import tempfile
import unittest
from pathlib import Path

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
            self.assertEqual(Path(tmp) / "logs" / "model_refresh" / "20260606T120000-qwen3vl-4b.json", out)
            self.assertTrue(out.exists())
            self.assertEqual(packet, json.loads(out.read_text()))


if __name__ == "__main__":
    unittest.main()
