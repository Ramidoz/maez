from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path


class DriveCuriosityDiagnosticSchemaTests(unittest.TestCase):
    def test_row_shape_uniform(self):
        from core.policies.diagnostics import (
            CuriosityDiagnosticEventType,
            DriveCuriosityDiagnosticSink,
            DIAGNOSTIC_SCHEMA_VERSION,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sink = DriveCuriosityDiagnosticSink(
                log_path=root / "logs" / "drive_driven_curiosity_diagnostics.jsonl",
                master_key_path=root / "memory" / "drive_curiosity_master.key",
            )

            sink.emit(
                event_type=CuriosityDiagnosticEventType.SUPPRESSION_EVENT,
                bond_id="firstborn",
                occurred_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
                suppression_kind="SIGNAL_GATED",
                reason="quiet_hours",
                raw_seed_text="raw text must not survive",
            )
            sink.emit(
                event_type=CuriosityDiagnosticEventType.SUBJECT_BOUNDARY_REFUSED,
                bond_id="firstborn",
                occurred_utc=datetime(2026, 5, 26, 12, 1, tzinfo=UTC),
                subject_ref="named-third-party",
                refusal_kind="named_third_party",
            )

            rows = [
                json.loads(line)
                for line in sink.log_path.read_text(encoding="utf-8").splitlines()
            ]

        event_rows = [
            row
            for row in rows
            if row["event_type"]
            != CuriosityDiagnosticEventType.MASTER_KEY_INITIALIZED.value
        ]
        self.assertEqual(len(event_rows), 2)
        self.assertEqual({tuple(row.keys()) for row in event_rows}, {tuple(event_rows[0].keys())})
        self.assertTrue(
            all(row["schema_version"] == DIAGNOSTIC_SCHEMA_VERSION for row in event_rows)
        )
        self.assertTrue(all(row["bond_digest"].startswith("hmac-sha256:") for row in event_rows))
        self.assertTrue(all(row["raw_seed_text"] is None for row in event_rows))
        self.assertNotIn("raw text must not survive", json.dumps(event_rows, sort_keys=True))

    def test_digests_are_hmac_shaped_and_raw_seed_text_is_never_logged(self):
        from core.policies.diagnostics import (
            CuriosityDiagnosticEventType,
            DriveCuriosityDiagnosticSink,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sink = DriveCuriosityDiagnosticSink(
                log_path=root / "logs" / "drive_driven_curiosity_diagnostics.jsonl",
                master_key_path=root / "memory" / "drive_curiosity_master.key",
            )

            sink.emit(
                event_type=CuriosityDiagnosticEventType.QUERY_SANITIZATION,
                bond_id="firstborn",
                occurred_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
                seed_text="private seed phrase",
                object_id="object-123",
            )

            row = json.loads(sink.log_path.read_text(encoding="utf-8").splitlines()[-1])

        for key in ("bond_digest", "seed_text_digest", "object_id_digest"):
            digest = row[key]
            self.assertRegex(digest, r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertIsNone(row["seed_text"])
        self.assertIsNone(row["raw_seed_text"])
        self.assertNotIn("private seed phrase", json.dumps(row, sort_keys=True))

    def test_daemon_owner_interrupting_gate_uses_unified_diagnostic_stream(self):
        daemon_source = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")
        pursuit_index = daemon_source.index("_pursuit_decision")
        gate_index = daemon_source.index("evaluate_extraction_gate", pursuit_index)

        self.assertIn("DriveCuriosityDiagnosticSink", daemon_source[pursuit_index:gate_index])
        self.assertIn("emit_diagnostic_best_effort", daemon_source[pursuit_index:gate_index])

    def test_best_effort_diagnostic_emit_swallow_failures(self):
        from core.policies.diagnostics import emit_diagnostic_best_effort

        warnings: list[str] = []

        class BrokenSink:
            def __call__(self, event: dict) -> None:
                raise RuntimeError(f"boom: {event['event_type']}")

        class CapturingLogger:
            def warning(self, message: str, *args) -> None:
                warnings.append(message % args)

        result = emit_diagnostic_best_effort(
            BrokenSink(),
            {"event_type": "SUPPRESSION_EVENT"},
            logger=CapturingLogger(),
        )

        self.assertFalse(result)
        self.assertEqual(len(warnings), 1)
        self.assertIn("drive curiosity diagnostic stream write failed", warnings[0])

    def test_first_boot_master_key_creation_is_race_safe(self):
        from core.policies.diagnostics import ensure_master_key

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            key_path = root / "memory" / "drive_curiosity_master.key"
            log_path = root / "logs" / "drive_driven_curiosity_diagnostics.jsonl"

            with ThreadPoolExecutor(max_workers=8) as pool:
                keys = list(
                    pool.map(
                        lambda _: ensure_master_key(
                            master_key_path=key_path,
                            diagnostic_log_path=log_path,
                        ),
                        range(8),
                    )
                )
            rows = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual({key for key in keys}, {keys[0]})
        self.assertEqual({len(key) for key in keys}, {32})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "master_key_initialized")

    def test_current_drive_layer_diagnostic_event_types_are_closed_vocabulary(self):
        from core.policies.diagnostics import DriveCuriosityDiagnosticSink

        drive_source = Path("core/evolution/drive_driven_curiosity.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("MEANINGFUL_EXCHANGE_CLASSIFIED", drive_source)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sink = DriveCuriosityDiagnosticSink(
                log_path=root / "logs" / "drive_driven_curiosity_diagnostics.jsonl",
                master_key_path=root / "memory" / "drive_curiosity_master.key",
            )

            sink(
                {
                    "event_type": "SATURATION_SAMPLE",
                    "bond_id": "firstborn",
                    "reason": "owner_bond_saturation",
                }
            )
            sink(
                {
                    "event_type": "TEMPERAMENT_WRITE_CLAMPED",
                    "bond_id": "firstborn",
                    "parameter": "curiosity",
                    "proposed_delta": 0.3,
                    "delta_applied": 0.2,
                }
            )
            rows = [
                json.loads(line)
                for line in sink.log_path.read_text(encoding="utf-8").splitlines()
            ]

        event_types = [row["event_type"] for row in rows]
        self.assertIn("saturation_sample", event_types)
        self.assertIn("temperament_write_clamped", event_types)
        saturation = next(row for row in rows if row["event_type"] == "saturation_sample")
        self.assertRegex(saturation["bond_digest"], r"^hmac-sha256:[0-9a-f]{64}$")

    def test_maintenance_proposal_events_use_unified_schema_and_hmac_proposal_id(self):
        from core.policies.diagnostics import (
            CuriosityDiagnosticEventType,
            DriveCuriosityDiagnosticSink,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sink = DriveCuriosityDiagnosticSink(
                log_path=root / "logs" / "drive_driven_curiosity_diagnostics.jsonl",
                master_key_path=root / "memory" / "drive_curiosity_master.key",
            )

            sink.emit(
                event_type=CuriosityDiagnosticEventType.MAINTENANCE_PROPOSAL_EMITTED,
                bond_id="firstborn",
                occurred_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
                proposal_id="proposal-1",
                proposal_scope_class="ranking_refinement",
                proposal_status="proposed",
            )
            row = json.loads(sink.log_path.read_text(encoding="utf-8").splitlines()[-1])

        self.assertEqual(row["event_type"], "maintenance_proposal_emitted")
        self.assertRegex(row["bond_digest"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(row["proposal_id_digest"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertEqual(row["proposal_scope_class"], "ranking_refinement")
        self.assertEqual(row["proposal_status"], "proposed")
        self.assertNotIn("proposal-1", json.dumps(row, sort_keys=True))

    def test_bond_isolation_refusals_feed_hmac_rows_to_unified_sink(self):
        from core.egress.fetch_for_curiosity import ProvenancedQuery, fetch_for_curiosity
        from core.evolution import drive_driven_curiosity as curiosity
        from core.evolution.subjective_duration import ProducerRef
        from core.policies.diagnostics import (
            DriveCuriosityDiagnosticSink,
            hmac_digest_for_bond,
        )
        from core.policies.exceptions import CrossBondAccessError, SubjectBoundaryRefused
        from core.policies.third_party_subject_gate import SubjectKind

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            key_path = root / "memory" / "drive_curiosity_master.key"
            sink = DriveCuriosityDiagnosticSink(
                log_path=root / "logs" / "drive_driven_curiosity_diagnostics.jsonl",
                master_key_path=key_path,
            )
            curiosity.clear_encounter_producers_for_tests()
            self.addCleanup(curiosity.clear_encounter_producers_for_tests)
            curiosity.register_encounter_producer(
                source=curiosity.EncounterSource.WONDERING_GENERATED,
                evidence_pointer_kind="wonderings.id",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY,
                create_curiosity_object=lambda seed: {
                    "wondering_id": 1,
                    "bond_id": "private_owner",
                    "question": "what should Maez learn here?",
                    "encounter_source": "wondering_generated",
                    "priority_class": "owner_bond",
                    "salience": 0.7,
                    "subject_kind": None,
                    "subject_ref": "person:unconsented",
                    **seed,
                },
            )
            entry = curiosity.get_registered_producer(
                curiosity.EncounterSource.WONDERING_GENERATED
            )

            with self.assertRaises(curiosity.SubjectKindRefused):
                entry.create({"diagnostic_sink": sink})
            with self.assertRaises(SubjectBoundaryRefused):
                fetch_for_curiosity(
                    bond_id="private_owner",
                    query=ProvenancedQuery(
                        bond_id="private_owner",
                        query_text="find a named third party",
                        subject_kind=SubjectKind.NAMED_THIRD_PARTY,
                        subject_ref="person:unconsented",
                    ),
                    diagnostic_sink=sink,
                )
            with self.assertRaises(CrossBondAccessError):
                fetch_for_curiosity(
                    bond_id="private_owner",
                    query=ProvenancedQuery(
                        bond_id="other_bond",
                        query_text="weather in chicago",
                        subject_kind=SubjectKind.PUBLIC_TOPIC,
                    ),
                    diagnostic_sink=sink,
                )
            rows = [
                json.loads(line)
                for line in sink.log_path.read_text(encoding="utf-8").splitlines()
            ]
            master_key = key_path.read_bytes()

        by_type = {row["event_type"]: row for row in rows}
        for event_type in (
            "subject_kind_refused",
            "subject_boundary_refused",
            "cross_bond_access_refused",
        ):
            self.assertIn(event_type, by_type)
        self.assertRegex(by_type["subject_kind_refused"]["bond_digest"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(by_type["subject_kind_refused"]["subject_ref_digest"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(by_type["subject_boundary_refused"]["bond_digest"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(by_type["subject_boundary_refused"]["subject_ref_digest"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(by_type["cross_bond_access_refused"]["requested_bond_digest"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(by_type["cross_bond_access_refused"]["query_bond_digest"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertEqual(
            by_type["cross_bond_access_refused"]["requested_bond_digest"],
            hmac_digest_for_bond(
                master_key=master_key,
                bond_id="private_owner",
                value="private_owner",
            ),
        )
        self.assertEqual(
            by_type["cross_bond_access_refused"]["query_bond_digest"],
            hmac_digest_for_bond(
                master_key=master_key,
                bond_id="other_bond",
                value="other_bond",
            ),
        )
        self.assertNotEqual(
            by_type["cross_bond_access_refused"]["requested_bond_digest"],
            hmac_digest_for_bond(
                master_key=master_key,
                bond_id="_diagnostic",
                value="private_owner",
            ),
        )
        self.assertNotIn("private_owner", json.dumps(rows, sort_keys=True))
        self.assertNotIn("other_bond", json.dumps(rows, sort_keys=True))
        self.assertNotIn("person:unconsented", json.dumps(rows, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
