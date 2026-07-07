import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from memory.memory_manager import ProvenanceSource


class _FakeMemory:
    def __init__(self):
        self.stored = []
        self.lookups = []

    def body_row_id_by_source_ref(self, source_ref, *, egress_origin_class):
        self.lookups.append((source_ref, egress_origin_class))
        return None

    def store(
        self,
        content,
        cycle,
        snapshot=None,
        metadata=None,
        *,
        provenance_source=None,
        trust_tier=None,
        egress_origin_class=None,
    ):
        self.stored.append({
            "content": content,
            "cycle": cycle,
            "snapshot": snapshot,
            "metadata": dict(metadata or {}),
            "provenance_source": provenance_source,
            "trust_tier": trust_tier,
            "egress_origin_class": egress_origin_class,
        })
        return f"body-{len(self.stored)}"


class ConnectorLaneTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_CONNECTOR_LANE", None)
        os.environ.pop("MAEZ_CONNECTOR_LANE_SHADOW", None)
        from core.intake_bus import connector_lane

        connector_lane.reset_connector_lane_dedupe_for_tests()

    def test_unknown_signal_kind_is_refused_content_free(self):
        from core.intake_bus.connector_lane import admit_connector_fact

        memory = _FakeMemory()
        decision = admit_connector_fact(
            {"kind": "calendar", "data": {"title": "legacy tunnel"}},
            memory=memory,
        )

        self.assertEqual(decision.status, "refused")
        self.assertEqual(decision.reason, "unknown_signal_kind")
        self.assertEqual(memory.stored, [])

    def test_near_identical_consecutive_signals_are_deduped_per_kind(self):
        from core.intake_bus.connector_lane import admit_connector_fact

        memory = _FakeMemory()
        first = admit_connector_fact(
            {"kind": "arrive_home", "data": {}, "timestamp": "2026-07-07T10:00:00Z"},
            memory=memory,
        )
        second = admit_connector_fact(
            {"kind": "arrive_home", "data": {}, "timestamp": "2026-07-07T10:00:05Z"},
            memory=memory,
        )

        self.assertEqual(first.status, "admitted")
        self.assertEqual(second.status, "deduped")
        self.assertEqual(second.reason, "near_identical_consecutive_signal")
        self.assertEqual(len(memory.stored), 1)

    def test_owner_account_context_taint_is_applied_to_admitted_facts(self):
        from core.intake_bus.connector_lane import admit_connector_fact

        memory = _FakeMemory()
        decision = admit_connector_fact(
            {"kind": "manual_note", "data": {"text": "remember the blue notebook"}},
            memory=memory,
        )

        self.assertEqual(decision.status, "admitted")
        self.assertEqual(memory.stored[0]["egress_origin_class"], "owner_account_context")
        self.assertEqual(memory.stored[0]["provenance_source"], ProvenanceSource.TOOL_OBSERVATION)
        self.assertEqual(memory.stored[0]["metadata"]["owner_account_context"], "true")

    def test_shadow_observation_does_not_consume_enforced_admission(self):
        from core.intake_bus.connector_lane import admit_connector_fact

        memory = _FakeMemory()
        shadow = admit_connector_fact(
            {"kind": "manual_note", "data": {"text": "shadow then enforce"}},
            memory=None,
            shadow=True,
        )
        enforced = admit_connector_fact(
            {"kind": "manual_note", "data": {"text": "shadow then enforce"}},
            memory=memory,
        )

        self.assertEqual(shadow.status, "would_admit")
        self.assertEqual(enforced.status, "admitted")
        self.assertEqual(len(memory.stored), 1)

    def test_failed_admission_does_not_consume_dedupe_slot(self):
        from core.intake_bus.connector_lane import admit_connector_fact

        class BrokenMemory(_FakeMemory):
            def body_row_id_by_source_ref(self, source_ref, *, egress_origin_class):
                raise RuntimeError("backend down")

        signal = {"kind": "manual_note", "data": {"text": "retry me"}}
        with self.assertRaises(RuntimeError):
            admit_connector_fact(signal, memory=BrokenMemory())

        memory = _FakeMemory()
        retry = admit_connector_fact(signal, memory=memory)

        self.assertEqual(retry.status, "admitted")
        self.assertEqual(len(memory.stored), 1)

    def test_importing_connector_lane_creates_no_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.dict(
                os.environ,
                {
                    "MAEZ_HOME": str(root),
                    "MAEZ_DATA": str(root),
                    "MAEZ_CONFIG": str(root / "config"),
                },
                clear=False,
            ):
                import core.intake_bus.connector_lane as connector_lane

                importlib.reload(connector_lane)
                created = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))

        self.assertEqual(created, [])


class IPhoneConnectorLaneFlagTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_CONNECTOR_LANE", None)
        os.environ.pop("MAEZ_CONNECTOR_LANE_SHADOW", None)
        os.environ["MAEZ_IPHONE_INGEST_TOKEN"] = "test-token"
        import skills.iphone_ingest as iphone_ingest

        iphone_ingest.SIGNALS_DIR = Path(tempfile.mkdtemp()) / "signals"

    def tearDown(self):
        os.environ.pop("MAEZ_CONNECTOR_LANE", None)
        os.environ.pop("MAEZ_CONNECTOR_LANE_SHADOW", None)

    def test_flag_off_path_matches_existing_response_and_signal_write(self):
        import skills.iphone_ingest as iphone_ingest

        payload = {"kind": "manual_note", "data": {"text": "same old path"}}
        before = iphone_ingest.ingest(payload, "test-token")
        signal_file = next(iphone_ingest.SIGNALS_DIR.glob("*.jsonl"))
        before_lines = signal_file.read_text(encoding="utf-8").splitlines()

        with mock.patch("core.intake_bus.connector_lane.admit_connector_fact") as admit:
            after = iphone_ingest.ingest(payload, "test-token")

        after_lines = signal_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(before, ({"ok": True, "kind": "manual_note"}, 200))
        self.assertEqual(after, before)
        self.assertEqual(len(after_lines), len(before_lines) + 1)
        self.assertEqual(
            [
                {k: v for k, v in json.loads(line).items() if k != "timestamp"}
                for line in after_lines
            ],
            [
                {"kind": "manual_note", "data": {"text": "same old path"}, "source": "ios_shortcuts"},
                {"kind": "manual_note", "data": {"text": "same old path"}, "source": "ios_shortcuts"},
            ],
        )
        admit.assert_not_called()

    def test_shadow_flag_logs_would_admit_without_memory_write(self):
        import skills.iphone_ingest as iphone_ingest

        with mock.patch.dict(os.environ, {"MAEZ_CONNECTOR_LANE_SHADOW": "1"}, clear=False), mock.patch(
            "skills.iphone_ingest.logger"
        ) as logger, mock.patch("core.intake_bus.connector_lane.admit_connector_fact") as admit:
            response = iphone_ingest.ingest(
                {"kind": "manual_note", "data": {"text": "shadow only"}},
                "test-token",
            )

        self.assertEqual(response, ({"ok": True, "kind": "manual_note"}, 200))
        admit.assert_called_once()
        self.assertIsNone(admit.call_args.kwargs["memory"])
        self.assertTrue(admit.call_args.kwargs["shadow"])
        logger.info.assert_any_call(
            "connector lane shadow: status=%s reason=%s kind=%s",
            admit.return_value.status,
            admit.return_value.reason,
            "manual_note",
        )


if __name__ == "__main__":
    unittest.main()
