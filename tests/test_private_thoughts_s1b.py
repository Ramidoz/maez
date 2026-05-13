# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S1b private-thoughts minimal wiring tests.

These tests pin the first production wiring through the S1a.1 doorway:
reasoning-residue producer writes are content-free and rate-limited, and
the behavior reader can only affect a local optional presentation copy.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from core.infra.private_thoughts import PrivateThoughts


class PrivateThoughtsS1bTest(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.db_path = self.root / "private_thoughts.db"
        self.audit_db_path = self.root / "audit_log.db"
        self.config_path = self.root / "private_thoughts_s1b.local.json"
        PrivateThoughts(db_path=self.db_path)

    def tearDown(self) -> None:
        self._td.cleanup()

    def _enable_config(self, *, producer: bool = True, consumer: bool = True) -> None:
        self.config_path.write_text(
            json.dumps(
                {
                    "producer_enabled": producer,
                    "consumer_enabled": consumer,
                    "active_window_seconds": 1800,
                    "hourly_write_cap": 20,
                    "optional_output_sentence_cap": 1,
                }
            ),
            encoding="utf-8",
        )

    def _producer(self):
        from core.infra.private_thoughts_s1b import PrivateThoughtsS1bProducer

        self._enable_config(producer=True, consumer=True)
        return PrivateThoughtsS1bProducer(
            db_path=self.db_path,
            audit_db_path=self.audit_db_path,
            config_path=self.config_path,
        )

    def test_producer_writes_fixed_reasoning_residue_registry_tuple(self) -> None:
        producer = self._producer()

        thought_id = producer.emit_cycle_residue(
            ["retry_triggered"],
            cycle_id=41,
            now=1_000_000.0,
        )

        self.assertIsInstance(thought_id, int)
        row = PrivateThoughts(db_path=self.db_path).get_thought(thought_id)
        self.assertEqual(row["content"], "s1b_reasoning_residue_event")
        self.assertEqual(row["provenance"], "reasoning_residue")
        self.assertEqual(row["producer_id"], "reasoning_residue")
        self.assertEqual(row["signal_kind"], "reasoning_residue")
        self.assertEqual(row["signal_class"], "reasoning_residue")
        self.assertEqual(row["memory_phase"], "gestation")
        self.assertEqual(row["context"]["source"], "daemon_cycle.reasoning_residue")
        self.assertEqual(row["context"]["subject"], "maez_internal_reasoning")
        self.assertEqual(row["context"]["consent_tier"], "owner_private")
        self.assertEqual(row["context"]["retention"], "until_reviewed")
        self.assertEqual(row["context"]["allowed_flows"], ["private_reader", "audit_trace"])
        self.assertEqual(row["context"]["extra"]["event_kind"], "retry_triggered")
        self.assertEqual(row["context"]["extra"]["cycle_id"], 41)
        self.assertEqual(row["context"]["extra"]["producer_version"], "s1b.1")

    def test_producer_rejects_raw_context_or_dynamic_content(self) -> None:
        from core.infra.private_thoughts_s1b import validate_s1b_context_extra

        forbidden_values = (
            {"trace_id": "abc"},
            {"thought_id": 123},
            {"raw_text": "Rohit said something private"},
            {"model_output": "I feel conflicted."},
            {"topic": "family"},
        )
        for context in forbidden_values:
            with self.subTest(context=context):
                with self.assertRaisesRegex(ValueError, "S1b context_extra"):
                    validate_s1b_context_extra(context)

    def test_producer_coalesces_at_end_of_cycle_by_priority(self) -> None:
        producer = self._producer()

        thought_id = producer.emit_cycle_residue(
            ["retry_triggered", "audit_rewrite", "retry_failed"],
            cycle_id=7,
            now=1_000_000.0,
        )

        row = PrivateThoughts(db_path=self.db_path).get_thought(thought_id)
        self.assertEqual(row["context"]["extra"]["event_kind"], "retry_failed")
        self.assertEqual(row["context"]["extra"]["coalesced_event_counts"]["retry_triggered"], 1)
        self.assertEqual(row["context"]["extra"]["coalesced_event_counts"]["audit_rewrite"], 1)

    def test_producer_rate_limits_from_durable_rows_across_instances(self) -> None:
        self._enable_config(producer=True, consumer=True)
        for i in range(20):
            producer = self._producer()
            self.assertIsNotNone(
                producer.emit_cycle_residue(
                    ["audit_rewrite"],
                    cycle_id=i,
                    now=1_000_000.0 + i,
                )
            )

        producer = self._producer()
        self.assertIsNone(
            producer.emit_cycle_residue(["audit_rewrite"], cycle_id=21, now=1_000_100.0)
        )
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM private_thoughts WHERE signal_class = 'reasoning_residue'"
            ).fetchone()[0]
        self.assertEqual(count, 20)
        with sqlite3.connect(self.audit_db_path) as conn:
            action = conn.execute(
                "SELECT action FROM audit_log ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        self.assertEqual(action, "private_thoughts_s1b.rate_limited")

    def test_rate_limit_summary_is_written_once_per_window(self) -> None:
        for i in range(20):
            self._producer().emit_cycle_residue(
                ["audit_rewrite"],
                cycle_id=i,
                now=1_000_000.0 + i,
            )

        for i in range(3):
            self._producer().emit_cycle_residue(
                ["audit_rewrite"],
                cycle_id=30 + i,
                now=1_000_100.0 + i,
            )

        with sqlite3.connect(self.audit_db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE action = ?",
                ("private_thoughts_s1b.rate_limited",),
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_producer_enforces_one_signal_per_cycle_durably(self) -> None:
        producer = self._producer()
        first = producer.emit_cycle_residue(["audit_rewrite"], cycle_id=44, now=1_000_000.0)
        second = producer.emit_cycle_residue(["retry_failed"], cycle_id=44, now=1_000_010.0)

        self.assertIsInstance(first, int)
        self.assertIsNone(second)
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM private_thoughts WHERE signal_class = 'reasoning_residue'"
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_behavior_safe_reader_is_neutral_without_migrating_reader(self) -> None:
        from core.infra.private_thoughts_s1b import behavior_safe_reasoning_residue_recency

        with mock.patch(
            "core.infra.private_thoughts.PrivateThoughts",
            side_effect=AssertionError("hot behavior read must not migrate schema"),
        ):
            result = behavior_safe_reasoning_residue_recency(
                self.db_path,
                now=1_000_000.0,
                active_window_seconds=1800,
            )

        self.assertEqual(result["recent_reasoning_residue_present"], False)
        self.assertEqual(result["behavior_safe_count"], 0)
        self.assertEqual(result["neutral_due_to_error"], False)

    def test_behavior_safe_reader_detects_recent_not_stale_rows(self) -> None:
        producer = self._producer()
        producer.emit_cycle_residue(["audit_rewrite"], cycle_id=1, now=1_000_000.0)

        from core.infra.private_thoughts_s1b import behavior_safe_reasoning_residue_recency

        recent = behavior_safe_reasoning_residue_recency(
            self.db_path,
            now=1_000_000.0 + 1800,
            active_window_seconds=1800,
        )
        stale = behavior_safe_reasoning_residue_recency(
            self.db_path,
            now=1_000_000.0 + 1801,
            active_window_seconds=1800,
        )

        self.assertTrue(recent["recent_reasoning_residue_present"])
        self.assertEqual(recent["behavior_safe_count"], 1)
        self.assertFalse(stale["recent_reasoning_residue_present"])

    def test_consumer_keeps_direct_replies_byte_identical(self) -> None:
        from core.infra.private_thoughts_s1b import apply_s1b_to_direct_reply

        text = "Here is the full answer. It has two sentences."

        self.assertEqual(apply_s1b_to_direct_reply(text), text)

    def test_optional_presentation_is_separate_dampened_payload(self) -> None:
        from core.infra.private_thoughts_s1b import (
            S1bPacingDecision,
            build_cycle_optional_presentation,
        )

        canonical = "First sentence. Second sentence. Third sentence."
        payload = build_cycle_optional_presentation(
            cycle=12,
            canonical_text=canonical,
            decision=S1bPacingDecision.dampened(sentence_cap=1),
        )

        self.assertEqual(payload["type"], "cycle_optional_presentation")
        self.assertEqual(payload["cycle"], 12)
        self.assertEqual(payload["presentation_text"], "First sentence.")
        self.assertTrue(payload["presentation_dampened"])
        self.assertTrue(payload["canonical_thought_unchanged"])
        self.assertNotEqual(payload["presentation_text"], canonical)

    def test_c2_probe_vocabulary_absent_from_optional_presentation(self) -> None:
        from core.infra.private_thoughts_s1b import (
            S1B_FORBIDDEN_USER_VISIBLE_SUBSTRINGS,
            S1bPacingDecision,
            build_cycle_optional_presentation,
        )

        payload = build_cycle_optional_presentation(
            cycle=13,
            canonical_text="I will keep this brief. The rest remains canonical.",
            decision=S1bPacingDecision.dampened(sentence_cap=1),
        )
        visible = payload["presentation_text"].lower()
        for forbidden in S1B_FORBIDDEN_USER_VISIBLE_SUBSTRINGS:
            self.assertNotIn(forbidden.lower(), visible)

    def test_forbidden_first_sentence_returns_no_optional_presentation(self) -> None:
        from core.infra.private_thoughts_s1b import (
            S1bPacingDecision,
            build_cycle_optional_presentation,
        )

        payload = build_cycle_optional_presentation(
            cycle=14,
            canonical_text="I feel private signal residue. Second sentence.",
            decision=S1bPacingDecision.dampened(sentence_cap=1),
        )

        self.assertIsNone(payload)

    def test_runtime_config_file_can_disable_consumer_over_enabled_env(self) -> None:
        from core.infra.private_thoughts_s1b import load_s1b_config

        self._enable_config(producer=True, consumer=False)
        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_PRIVATE_THOUGHTS_S1B_PRODUCER": "1",
                "MAEZ_PRIVATE_THOUGHTS_S1B_CONSUMER": "1",
            },
        ):
            cfg = load_s1b_config(config_path=self.config_path)

        self.assertTrue(cfg.producer_enabled)
        self.assertFalse(cfg.consumer_enabled)

    def test_consumer_self_disables_after_near_default_dampening(self) -> None:
        from core.infra.private_thoughts_s1b import PrivateThoughtsS1bConsumer

        self._enable_config(producer=True, consumer=True)
        producer = self._producer()
        consumer = PrivateThoughtsS1bConsumer(
            db_path=self.db_path,
            audit_db_path=self.audit_db_path,
            config_path=self.config_path,
        )

        for idx, offset in enumerate((0, 1800, 3600)):
            producer.emit_cycle_residue(
                ["audit_rewrite"],
                cycle_id=100 + idx,
                now=1_000_000.0 + offset,
            )
            decision = consumer.pacing_decision(now=1_000_000.0 + offset)
            if decision.is_dampened:
                consumer.record_optional_presentation(dampened=True, now=1_000_000.0 + offset)

        cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertFalse(cfg["consumer_enabled"])
        with sqlite3.connect(self.audit_db_path) as conn:
            action = conn.execute(
                "SELECT action FROM audit_log ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        self.assertEqual(action, "private_thoughts_s1b.consumer_self_disabled")

    def test_consumer_self_disable_counts_default_audit_log_path(self) -> None:
        from core.infra.private_thoughts_s1b import PrivateThoughtsS1bConsumer

        self._enable_config(producer=True, consumer=True)
        producer = self._producer()
        with mock.patch("core.cognition.audit_log.DEFAULT_DB_PATH", self.audit_db_path):
            consumer = PrivateThoughtsS1bConsumer(
                db_path=self.db_path,
                config_path=self.config_path,
            )
            for idx, offset in enumerate((0, 1800, 3600)):
                producer.emit_cycle_residue(
                    ["audit_rewrite"],
                    cycle_id=200 + idx,
                    now=1_000_000.0 + offset,
                )
                decision = consumer.pacing_decision(now=1_000_000.0 + offset)
                if decision.is_dampened:
                    consumer.record_optional_presentation(
                        dampened=True,
                        now=1_000_000.0 + offset,
                    )

        cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertFalse(cfg["consumer_enabled"])

    def test_consumer_self_disable_preserves_producer_enablement(self) -> None:
        from core.infra.private_thoughts_s1b import (
            PrivateThoughtsS1bConsumer,
            load_s1b_config,
        )

        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_PRIVATE_THOUGHTS_S1B_PRODUCER": "1",
                "MAEZ_PRIVATE_THOUGHTS_S1B_CONSUMER": "1",
            },
        ):
            consumer = PrivateThoughtsS1bConsumer(
                db_path=self.db_path,
                config_path=self.config_path,
            )
            consumer._disable_consumer_in_config()
            cfg = load_s1b_config(config_path=self.config_path)

        self.assertTrue(cfg.producer_enabled)
        self.assertFalse(cfg.consumer_enabled)

    def test_consumer_duty_cycle_counts_neutral_opportunities(self) -> None:
        from core.infra.private_thoughts_s1b import PrivateThoughtsS1bConsumer

        self._enable_config(producer=True, consumer=True)
        consumer = PrivateThoughtsS1bConsumer(
            db_path=self.db_path,
            audit_db_path=self.audit_db_path,
            config_path=self.config_path,
        )

        consumer.record_optional_presentation(dampened=True, now=1_000_000.0)
        consumer.record_optional_presentation(dampened=False, now=1_000_100.0)
        consumer.record_optional_presentation(dampened=False, now=1_000_200.0)

        cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertTrue(cfg["consumer_enabled"])

    def test_duty_cycle_parameters_are_loaded_from_config(self) -> None:
        from core.infra.private_thoughts_s1b import load_s1b_config

        self.config_path.write_text(
            json.dumps(
                {
                    "producer_enabled": True,
                    "consumer_enabled": True,
                    "duty_cycle_window_seconds": 3600,
                    "duty_cycle_min_samples": 9,
                    "duty_cycle_max_dampened_ratio": 0.95,
                }
            ),
            encoding="utf-8",
        )

        cfg = load_s1b_config(config_path=self.config_path)

        self.assertEqual(cfg.duty_cycle_window_seconds, 3600)
        self.assertEqual(cfg.duty_cycle_min_samples, 9)
        self.assertEqual(cfg.duty_cycle_max_dampened_ratio, 0.95)

    def test_consumer_self_disable_uses_configured_duty_cycle_threshold(self) -> None:
        from core.infra.private_thoughts_s1b import PrivateThoughtsS1bConsumer

        self.config_path.write_text(
            json.dumps(
                {
                    "producer_enabled": True,
                    "consumer_enabled": True,
                    "duty_cycle_min_samples": 3,
                    "duty_cycle_max_dampened_ratio": 1.0,
                }
            ),
            encoding="utf-8",
        )
        consumer = PrivateThoughtsS1bConsumer(
            db_path=self.db_path,
            audit_db_path=self.audit_db_path,
            config_path=self.config_path,
        )

        for offset in (0, 100, 200):
            consumer.record_optional_presentation(dampened=True, now=1_000_000.0 + offset)

        cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertTrue(cfg["consumer_enabled"])


class _FakeProducer:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], int]] = []

    def emit_cycle_residue(self, event_kinds, *, cycle_id, now=None):
        self.calls.append((list(event_kinds), cycle_id))
        return 101


class _FakeConsumer:
    def __init__(self) -> None:
        self.records: list[bool] = []

    def pacing_decision(self, *, now=None):
        from core.infra.private_thoughts_s1b import S1bPacingDecision

        return S1bPacingDecision.dampened(sentence_cap=1)

    def should_record_optional_presentation_opportunity(self):
        return True

    def record_optional_presentation(self, *, dampened, now=None):
        self.records.append(bool(dampened))


class MaezDaemonS1bSeamTest(unittest.TestCase):
    def _daemon(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 22
        daemon._s1b_residue_events = []
        daemon._s1b_producer = _FakeProducer()
        daemon._s1b_consumer = _FakeConsumer()
        daemon.broadcasts = []
        daemon._ws_broadcast = lambda payload: daemon.broadcasts.append(payload)
        return daemon

    def test_daemon_flushes_coalesced_residue_at_cycle_end(self) -> None:
        daemon = self._daemon()

        daemon._s1b_note_residue_event("retry_triggered")
        daemon._s1b_note_residue_event("retry_failed")
        daemon._s1b_flush_residue_events()

        self.assertEqual(
            daemon._s1b_producer.calls,
            [(["retry_triggered", "retry_failed"], 22)],
        )
        self.assertEqual(daemon._s1b_residue_events, [])

    def test_daemon_flushes_residue_on_heartbeat_ok_branch(self) -> None:
        daemon = self._daemon()

        daemon._s1b_note_residue_event("retry_triggered")
        daemon._s1b_flush_residue_events()

        self.assertEqual(daemon._s1b_producer.calls, [(["retry_triggered"], 22)])
        self.assertEqual(daemon._s1b_residue_events, [])

    def test_daemon_optional_presentation_is_separate_from_cycle_end(self) -> None:
        daemon = self._daemon()
        canonical = "First sentence. Second sentence."

        payload = daemon._s1b_optional_presentation_payload(canonical)

        daemon._ws_broadcast({"type": "cycle_end", "cycle": 22, "thought": canonical})
        if payload is not None:
            daemon._ws_broadcast(payload)

        self.assertEqual(daemon.broadcasts[0]["type"], "cycle_end")
        self.assertEqual(daemon.broadcasts[0]["thought"], canonical)
        self.assertEqual(daemon.broadcasts[1]["type"], "cycle_optional_presentation")
        self.assertEqual(daemon.broadcasts[1]["presentation_text"], "First sentence.")
        self.assertTrue(daemon.broadcasts[1]["canonical_thought_unchanged"])
        self.assertEqual(daemon._s1b_consumer.records, [True])

    def test_daemon_records_neutral_optional_presentation_opportunity(self) -> None:
        daemon = self._daemon()

        payload = daemon._s1b_optional_presentation_payload(
            "I feel private signal residue. Second sentence."
        )

        self.assertIsNone(payload)
        self.assertEqual(daemon._s1b_consumer.records, [False])

    def test_terminal_ui_consumes_cycle_optional_presentation(self) -> None:
        if "blessed" not in sys.modules:
            blessed = types.ModuleType("blessed")
            blessed.Terminal = lambda *args, **kwargs: object()
            sys.modules["blessed"] = blessed
        from ui.maez_terminal_ui import MaezTerminalUI

        ui = object.__new__(MaezTerminalUI)
        ui.last_thought = "Full canonical thought. Second sentence."
        ui.set_emotion = lambda _emotion: None

        ui._handle_ws_payload(
            {
                "type": "cycle_optional_presentation",
                "presentation_text": "Full canonical thought.",
                "presentation_dampened": True,
            }
        )

        self.assertEqual(ui.last_thought, "Full canonical thought.")


if __name__ == "__main__":
    unittest.main()
