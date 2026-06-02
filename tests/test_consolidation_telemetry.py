from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ConsolidationTelemetryShapeTest(unittest.TestCase):
    def test_summary_has_exact_content_free_field_set(self):
        from core.cognition.consolidation_telemetry import (
            CONSOLIDATION_TELEMETRY_FIELDS,
            consolidation_telemetry_summary,
        )

        summary = consolidation_telemetry_summary(
            organ="raw_daily",
            inputs_count=17,
            outputs_count=1,
            model="qwen36-27b",
            duration_ms=12.8,
            rails_blocked=3,
            status="success",
            reason="stored",
        )

        self.assertEqual(set(summary), CONSOLIDATION_TELEMETRY_FIELDS)
        self.assertEqual(summary["duration_ms"], 13)
        encoded = json.dumps(summary, sort_keys=True)
        self.assertNotIn("private reflection text", encoded)
        self.assertNotIn("raw memory content", encoded)

    def test_emit_writes_content_free_json_summary(self):
        from core.cognition.consolidation_telemetry import emit_consolidation_telemetry

        records = []

        class _Logger:
            def info(self, fmt, payload):
                records.append(fmt % payload)

        emit_consolidation_telemetry(
            _Logger(),
            organ="reflection",
            inputs_count=4,
            outputs_count=0,
            model="qwen36-27b",
            duration_ms=5,
            rails_blocked=2,
            status="dry_run",
            reason="write_flag_off",
        )

        self.assertEqual(len(records), 1)
        prefix, raw = records[0].split("summary=", 1)
        self.assertEqual(prefix, "consolidation_telemetry ")
        payload = json.loads(raw)
        self.assertEqual(payload["organ"], "reflection")
        self.assertNotIn("private reflection text", raw)


class ServedModelReportingTest(unittest.TestCase):
    def test_llamacpp_served_model_alias_reads_props_not_requested_label(self):
        from core.routing import llm_client

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"model_alias": "qwen36-27b", "model_path": "/models/qwen.gguf"}'

        with mock.patch.dict(
            "os.environ",
            {"MAEZ_LLM_BACKEND": "llamacpp", "MAEZ_PRIMARY_MODEL": "qwen36-27b"},
            clear=True,
        ), mock.patch("urllib.request.urlopen", return_value=_Resp()) as urlopen:
            model = llm_client.served_model_alias(default="gemma4:26b")

        self.assertEqual(model, "qwen36-27b")
        self.assertNotEqual(model, "gemma4:26b")
        self.assertIn("/props", urlopen.call_args.args[0])


class OrganTelemetryHookTest(unittest.TestCase):
    def test_daily_consolidation_telemetry_uses_exact_schema(self):
        from memory.memory_manager import _daily_consolidation_telemetry

        summary = _daily_consolidation_telemetry(
            inputs_count=12,
            outputs_count=1,
            model="qwen36-27b",
            duration_ms=33,
            rails_blocked=2,
            status="success",
            reason="stored",
        )

        self.assertEqual(summary["organ"], "raw_daily")
        self.assertEqual(summary["inputs_count"], 12)
        self.assertEqual(summary["rails_blocked"], 2)
        self.assertEqual(set(summary), {
            "organ",
            "inputs_count",
            "outputs_count",
            "model",
            "duration_ms",
            "rails_blocked",
            "status",
            "reason",
        })

    def test_dream_short_input_emits_content_free_telemetry(self):
        from core.evolution import dream_state

        class _Memory:
            def recent_raw(self, n):
                return {"documents": ["raw memory content"] * 3}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            dream_state.logger, "info"
        ) as info:
            dream = dream_state.DreamState(
                memory=_Memory(),
                telegram=None,
                action_engine=None,
                db_path=str(Path(tmp) / "dream.db"),
            )
            self.assertIsNone(dream.run_dream_cycle(force=True))

        records = [
            args[0] % args[1:]
            for args, _kwargs in info.call_args_list
            if args and str(args[0]).startswith("consolidation_telemetry")
        ]
        self.assertEqual(len(records), 1)
        payload = json.loads(records[0].split("summary=", 1)[1])
        self.assertEqual(payload["organ"], "dream")
        self.assertEqual(payload["inputs_count"], 3)
        self.assertEqual(payload["outputs_count"], 0)
        self.assertNotIn("raw memory content", records[0])

    def test_reflection_hook_summary_can_be_reemitted_as_consolidation_telemetry(self):
        from core.cognition.consolidation_telemetry import consolidation_telemetry_summary
        from daemon.maez_daemon import _reflection_consolidation_telemetry

        summary = _reflection_consolidation_telemetry(
            {
                "status": "dry_run",
                "reason": "write_flag_off",
                "candidates_count": 1,
                "drops_count": 2,
            },
            model="qwen36-27b",
            duration_ms=42,
        )

        self.assertEqual(set(summary), set(consolidation_telemetry_summary(
            organ="reflection",
            inputs_count=0,
            outputs_count=0,
            model="qwen36-27b",
            duration_ms=0,
            rails_blocked=0,
            status="dry_run",
            reason="x",
        )))
        self.assertEqual(summary["inputs_count"], 3)
        self.assertEqual(summary["outputs_count"], 1)
        self.assertEqual(summary["rails_blocked"], 2)


if __name__ == "__main__":
    unittest.main()
