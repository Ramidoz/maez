from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


class _FakeEpisodeStore:
    def __init__(self):
        self.add_calls = []

    def list_active(self):
        return [
            {
                "id": "ep-1",
                "title": "A careful slice landed",
                "summary": "Rohit and Maez held the line on witness-before-claim.",
                "source_kind": "core",
                "source_memory_ids": ["core-1"],
                "created_at": "2026-06-02T04:00:00+00:00",
            }
        ]

    def add(self, *args, **kwargs):
        self.add_calls.append((args, kwargs))
        raise AssertionError("dry-run reflection synthesis must not persist")


def _reflection_json(_prompt: str) -> str:
    return json.dumps(
        [
            {
                "reflection": "Rohit and Maez repeatedly require live witness before belief.",
                "evidence": ["core-1"],
            },
            {
                "reflection": "This one cites nothing and must be owner-visible as dropped.",
                "evidence": [],
            },
            {
                "reflection": "This one cites a fabricated id and must be dropped.",
                "evidence": ["made-up"],
            },
        ]
    )


def _reflection_json_with_metadata(prompt: str) -> str:
    raw = _reflection_json(prompt)
    _reflection_json_with_metadata.last_finish_reason = "stop"
    _reflection_json_with_metadata.max_tokens = 8192
    _reflection_json_with_metadata.last_raw_content = raw
    return raw


class ReflectionDryRunScriptTest(unittest.TestCase):
    def test_dry_run_captures_candidates_and_drops_to_local_artifact(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            ReflectionReport,
            run_synthesis_pass,
            write_reflection_dry_run_artifact,
        )

        store = _FakeEpisodeStore()
        report = ReflectionReport(dry_run=True, started_at="2026-06-02T04:00:00+00:00")

        run_synthesis_pass(
            episode_store=store,
            llm_call=_reflection_json_with_metadata,
            max_reflections=3,
            report=report,
            dry_run=True,
        )

        self.assertEqual(store.add_calls, [])
        self.assertEqual(report.reflections_attempted, 1)
        self.assertEqual(report.reflections_added, 0)
        self.assertEqual(
            report.reflection_candidates,
            [
                {
                    "text": "Rohit and Maez repeatedly require live witness before belief.",
                    "source_memory_ids": ["core-1"],
                }
            ],
        )
        self.assertEqual(
            {drop["reason"] for drop in report.reflection_drops},
            {"missing_evidence", "fabricated_evidence"},
        )
        self.assertEqual(report.finish_reason, "stop")
        self.assertEqual(report.max_tokens, 8192)
        self.assertTrue(report.valid_witness)

        with tempfile.TemporaryDirectory() as tmp:
            path = write_reflection_dry_run_artifact(
                report,
                artifact_dir=Path(tmp),
                timestamp_slug="fixed",
            )
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(path.name, "fixed.jsonl")
        self.assertEqual(rows[0]["kind"], "run")
        self.assertEqual(rows[0]["finish_reason"], "stop")
        self.assertEqual(rows[0]["max_tokens"], 8192)
        self.assertFalse(rows[0]["truncated"])
        self.assertTrue(rows[0]["valid_witness"])
        self.assertIn("live witness", rows[0]["raw_model_content"])
        self.assertEqual(rows[1]["kind"], "candidate")
        self.assertEqual(rows[1]["source_memory_ids"], ["core-1"])
        self.assertIn("live witness", rows[1]["text"])
        self.assertEqual({row["kind"] for row in rows[2:]}, {"drop"})

    def test_artifact_marks_truncated_run_as_invalid_witness_not_no_candidates(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            ReflectionReport,
            write_reflection_dry_run_artifact,
        )

        report = ReflectionReport(
            dry_run=True,
            started_at="2026-06-02T04:00:00+00:00",
            finish_reason="length",
            max_tokens=8192,
            raw_model_content="private truncated reasoning tail",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = write_reflection_dry_run_artifact(
                report,
                artifact_dir=Path(tmp),
                timestamp_slug="truncated",
            )
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(rows[0]["kind"], "run")
        self.assertEqual(rows[0]["finish_reason"], "length")
        self.assertTrue(rows[0]["truncated"])
        self.assertFalse(rows[0]["valid_witness"])
        self.assertEqual(rows[0]["reason"], "truncated")
        self.assertIn("private truncated reasoning tail", rows[0]["raw_model_content"])
        self.assertEqual(rows[1]["kind"], "summary")
        self.assertEqual(rows[1]["reason"], "truncated")
        self.assertNotEqual(rows[1]["reason"], "no_candidates")

    def test_artifact_marks_no_llm_call_as_no_input_not_no_candidates(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            ReflectionReport,
            write_reflection_dry_run_artifact,
        )

        report = ReflectionReport(
            dry_run=True,
            started_at="2026-06-02T04:00:00+00:00",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = write_reflection_dry_run_artifact(
                report,
                artifact_dir=Path(tmp),
                timestamp_slug="no-input",
            )
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(rows[0]["kind"], "run")
        self.assertEqual(rows[0]["finish_reason"], "")
        self.assertFalse(rows[0]["valid_witness"])
        self.assertEqual(rows[0]["reason"], "no_input")
        self.assertEqual(rows[1]["kind"], "summary")
        self.assertEqual(rows[1]["reason"], "no_input")
        self.assertNotEqual(rows[1]["reason"], "no_candidates")


class ReflectionDryRunDaemonHookTest(unittest.TestCase):
    def test_flag_off_is_noop(self):
        from daemon.maez_daemon import _run_reflection_synthesis_nightly

        with mock.patch.dict(os.environ, {}, clear=True):
            summary = _run_reflection_synthesis_nightly(
                SimpleNamespace(lived_episodes=_FakeEpisodeStore()),
                llm_call=_reflection_json,
            )

        self.assertEqual(summary, {"status": "disabled", "reason": "flag_off"})

    def test_flag_on_write_off_writes_local_artifact_and_content_free_summary(self):
        from daemon.maez_daemon import _run_reflection_synthesis_nightly

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ,
            {
                "MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
                "MAEZ_REFLECTION_SYNTHESIS_WRITE": "0",
            },
            clear=True,
        ):
            summary = _run_reflection_synthesis_nightly(
                SimpleNamespace(lived_episodes=_FakeEpisodeStore()),
                llm_call=_reflection_json_with_metadata,
                artifact_dir=Path(tmp),
            )
            artifact_path = Path(str(summary["artifact_path"]))
            rows = [
                json.loads(line)
                for line in artifact_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        encoded_summary = json.dumps(summary, sort_keys=True)
        self.assertNotIn("live witness before belief", encoded_summary)
        self.assertNotIn("cites nothing", encoded_summary)
        self.assertEqual(summary["status"], "dry_run")
        self.assertEqual(summary["candidates_count"], 1)
        self.assertEqual(summary["drops_count"], 2)
        self.assertEqual(summary["finish_reason"], "stop")
        self.assertEqual(summary["max_tokens"], 8192)
        self.assertEqual(rows[0]["kind"], "run")
        self.assertEqual(rows[1]["kind"], "candidate")
        self.assertIn("live witness before belief", rows[1]["text"])

    def test_summary_marks_truncation_as_invalid_witness_without_content_leak(self):
        from daemon.maez_daemon import _reflection_synthesis_summary
        from scripts.memory_reflection.nightly_lived_memory import ReflectionReport

        report = ReflectionReport(
            dry_run=True,
            finish_reason="length",
            max_tokens=8192,
            raw_model_content="private truncated reasoning tail",
        )

        summary = _reflection_synthesis_summary(
            status="dry_run",
            reason="write_flag_off",
            report=report,
        )

        self.assertEqual(summary["status"], "invalid_witness")
        self.assertEqual(summary["reason"], "truncated")
        self.assertEqual(summary["finish_reason"], "length")
        self.assertEqual(summary["max_tokens"], 8192)
        self.assertTrue(summary["truncated"])
        self.assertNotIn(
            "private truncated reasoning tail",
            json.dumps(summary, sort_keys=True),
        )

    def test_summary_allows_no_candidates_only_for_stop_finish_reason(self):
        from daemon.maez_daemon import _reflection_synthesis_summary
        from scripts.memory_reflection.nightly_lived_memory import ReflectionReport

        report = ReflectionReport(dry_run=True, finish_reason="stop", max_tokens=8192)

        summary = _reflection_synthesis_summary(
            status="dry_run",
            reason="write_flag_off",
            report=report,
        )

        self.assertEqual(summary["status"], "dry_run")
        self.assertEqual(summary["reason"], "write_flag_off")
        self.assertEqual(summary["finish_reason"], "stop")
        self.assertFalse(summary["truncated"])

    def test_flag_on_timeout_writes_invalid_witness_artifact_and_summary(self):
        from daemon.maez_daemon import _run_reflection_synthesis_nightly

        def timeout_llm(_prompt: str) -> str:
            timeout_llm.last_finish_reason = "llm_timeout"
            timeout_llm.max_tokens = 8192
            timeout_llm.last_raw_content = ""
            return ""

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ,
            {
                "MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
                "MAEZ_REFLECTION_SYNTHESIS_WRITE": "0",
            },
            clear=True,
        ):
            summary = _run_reflection_synthesis_nightly(
                SimpleNamespace(lived_episodes=_FakeEpisodeStore()),
                llm_call=timeout_llm,
                artifact_dir=Path(tmp),
            )
            rows = [
                json.loads(line)
                for line in Path(str(summary["artifact_path"]))
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]

        self.assertEqual(summary["status"], "invalid_witness")
        self.assertEqual(summary["reason"], "llm_timeout")
        self.assertEqual(summary["finish_reason"], "llm_timeout")
        self.assertEqual(summary["max_tokens"], 8192)
        self.assertFalse(summary["truncated"])
        self.assertEqual(rows[0]["kind"], "run")
        self.assertEqual(rows[0]["reason"], "llm_timeout")
        self.assertEqual(rows[1]["kind"], "summary")
        self.assertEqual(rows[1]["reason"], "llm_timeout")

    def test_synthesis_failure_emits_content_free_telemetry(self):
        from daemon import maez_daemon
        from daemon.maez_daemon import _run_reflection_synthesis_nightly

        records = []

        def boom(**_kwargs):
            raise RuntimeError("private reflection text must not leak")

        class _Logger:
            def info(self, fmt, payload):
                records.append(fmt % payload)

            def warning(self, fmt, *args):
                records.append(fmt % args if args else fmt)

            def debug(self, *_args, **_kwargs):
                pass

        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
                "MAEZ_REFLECTION_SYNTHESIS_WRITE": "0",
            },
            clear=True,
        ), mock.patch(
            "scripts.memory_reflection.nightly_lived_memory.run_synthesis_pass",
            boom,
        ), mock.patch.object(maez_daemon, "logger", _Logger()):
            summary = _run_reflection_synthesis_nightly(
                SimpleNamespace(lived_episodes=_FakeEpisodeStore()),
                llm_call=_reflection_json,
            )

        self.assertEqual(summary["status"], "error")
        self.assertEqual(summary["reason"], "synthesis_failed")
        encoded_summary = json.dumps(summary, sort_keys=True)
        self.assertNotIn("private reflection text", encoded_summary)

        telemetry = [
            record for record in records if record.startswith("consolidation_telemetry")
        ]
        self.assertEqual(len(telemetry), 1)
        payload = json.loads(telemetry[0].split("summary=", 1)[1])
        self.assertEqual(payload["organ"], "reflection")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["reason"], "synthesis_failed")
        self.assertNotIn("private reflection text", telemetry[0])


if __name__ == "__main__":
    unittest.main()
