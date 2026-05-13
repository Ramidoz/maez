# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S1 private-thoughts producer + bounded-reader tests.

These tests pin the first post-scaffold shape:

- producers write through a minimal contextual-integrity envelope;
- raw private-thought content stays private;
- the bounded reader returns coarse derived signals, never trace ids or text.
"""

from __future__ import annotations

import json
from unittest import mock
import tempfile
import unittest
from pathlib import Path
import sqlite3

import core.infra.private_thoughts as private_thoughts_module
from core.infra.private_thoughts import (
    PRIVATE_THOUGHTS_USER_VERSION,
    PrivateThoughts,
    ProducerId,
    SignalKind,
)


class TestPrivateThoughtsS1(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.db_path = Path(self._td.name) / "private_thoughts.db"
        self.store = PrivateThoughts(db_path=self.db_path)

    def tearDown(self) -> None:
        self._td.cleanup()

    def assertNoBehaviorTraceHandles(self, derived: dict) -> None:
        self.assertNotIn("trace_ids", derived)
        self.assertNotIn("thought_id", str(derived))
        self.assertNotIn("trace_id", str(derived))

    def insert_raw_private_thought(
        self,
        *,
        ts: float,
        content: str,
        provenance: str,
        context: dict | str,
        memory_phase: str = "gestation",
        extra_columns: dict | None = None,
    ) -> int:
        context_json = context if isinstance(context, str) else json.dumps(context)
        columns = [
            "ts",
            "content",
            "provenance",
            "context_json",
            "memory_phase",
        ]
        values = [ts, content, provenance, context_json, memory_phase]
        for key, value in (extra_columns or {}).items():
            columns.append(key)
            values.append(value)
        placeholders = ", ".join("?" for _ in columns)
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                f"INSERT INTO private_thoughts ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def test_record_signal_writes_contextual_integrity_envelope(self) -> None:
        thought_id = self.store.record_signal(
            content="The audit held a daemon thought for being too ungrounded.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader", "audit_trace"),
            context_extra={"cycle": 42},
            memory_phase="lived",
        )

        row = self.store.get_thought(thought_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["provenance"], "audit_held")
        self.assertEqual(row["memory_phase"], "lived")
        self.assertEqual(row["context"]["source"], "audit_rail")
        self.assertEqual(row["context"]["subject"], "maez_output")
        self.assertEqual(row["context"]["consent_tier"], "owner_private")
        self.assertEqual(row["context"]["retention"], "until_reviewed")
        self.assertEqual(
            row["context"]["allowed_flows"],
            ["private_reader", "audit_trace"],
        )
        self.assertEqual(row["context"]["extra"], {"cycle": 42})

    def test_record_signal_requires_contextual_integrity_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "source"):
            self.store.record_signal(
                content="A held concern with no source.",
                provenance="audit_held",
                source="",
                subject="maez_output",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=("private_reader",),
            )

        with self.assertRaisesRegex(ValueError, "allowed_flows"):
            self.store.record_signal(
                content="A held concern with no allowed flow.",
                provenance="audit_held",
                source="audit_rail",
                subject="maez_output",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=(),
            )

    def test_record_thought_rejects_producer_provenance_bypass(self) -> None:
        with self.assertRaisesRegex(ValueError, "record_signal"):
            self.store.record_thought(
                content="Producer-shaped row with no envelope.",
                provenance="audit_held",
                context={},
            )

    def test_record_thought_internal_flag_cannot_bypass_signal_api(self) -> None:
        with self.assertRaises(TypeError):
            self.store.record_thought(
                content="Producer-shaped row with a fake internal flag.",
                provenance="audit_held",
                context={},
                _allow_producer_provenance=True,  # type: ignore[call-arg]
            )

    def test_record_signal_rejects_non_string_allowed_flows(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowed_flows"):
            self.store.record_signal(
                content="A held concern with a non-string flow.",
                provenance="audit_held",
                source="audit_rail",
                subject="maez_output",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=("private_reader", 123),  # type: ignore[list-item]
            )

    def test_bounded_reader_returns_signals_without_raw_content(self) -> None:
        crisis_id = self.store.record_signal(
            content="This looks like a crisis signal, but it must route to humans.",
            provenance="crisis_signal_held",
            source="telegram",
            subject="bonded_user_state",
            consent_tier="owner_private",
            retention="until_routed",
            allowed_flows=("private_reader", "crisis_channel"),
        )
        rupture_id = self.store.record_signal(
            content="A possible rupture is forming and should be repaired later.",
            provenance="rupture_unhealed",
            source="delayed_reflection",
            subject="bond_state",
            consent_tier="owner_private",
            retention="until_repaired",
            allowed_flows=("private_reader", "rupture_repair"),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertTrue(derived["bounded"])
        self.assertEqual(derived["limit"], 10)
        self.assertIsInstance(crisis_id, int)
        self.assertIsInstance(rupture_id, int)
        self.assertNoBehaviorTraceHandles(derived)
        self.assertEqual(
            derived["signal_classes"]["crisis_routing"]["state"],
            "present",
        )
        self.assertEqual(
            derived["signal_classes"]["bond_repair"]["state"],
            "present",
        )
        self.assertNotIn("content", str(derived).lower())
        self.assertNotIn("route to humans", str(derived))

    def test_bounded_reader_does_not_call_raw_recent_reader(self) -> None:
        self.store.record_signal(
            content="Raw text should not be materialized by derived_signals.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        def _raw_reader_forbidden(*_args, **_kwargs):
            raise AssertionError("derived_signals must not materialize raw content")

        self.store.recent = _raw_reader_forbidden  # type: ignore[method-assign]

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(
            derived["signal_classes"]["audit_awareness"]["count"],
            1,
        )
        self.assertEqual(
            derived["signal_classes"]["audit_awareness"]["state"],
            "present",
        )

    def test_bounded_reader_requires_private_reader_flow(self) -> None:
        hidden_id = self.store.record_signal(
            content="This row does not allow the private reader.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("audit_trace",),
        )
        visible_id = self.store.record_signal(
            content="This row allows the private reader.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(
            derived["signal_classes"]["audit_awareness"]["count"],
            1,
        )
        self.assertIsInstance(hidden_id, int)
        self.assertIsInstance(visible_id, int)
        self.assertNoBehaviorTraceHandles(derived)

    def test_bounded_reader_ignores_malformed_existing_producer_rows(self) -> None:
        malformed_id = self.insert_raw_private_thought(
            ts=1.0,
            content="Malformed row created outside the API.",
            provenance="audit_held",
            context="{}",
        )

        visible_id = self.store.record_signal(
            content="Well-formed row created through the producer API.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(
            derived["signal_classes"]["audit_awareness"]["count"],
            1,
        )
        self.assertEqual(derived["malformed_signal_row_count"], 1)
        self.assertIsInstance(malformed_id, int)
        self.assertIsInstance(visible_id, int)
        self.assertNoBehaviorTraceHandles(derived)

    def test_bounded_reader_ignores_partially_malformed_context(self) -> None:
        bad_context = {
            "source": None,
            "subject": "",
            "consent_tier": "owner_private",
            "retention": "until_reviewed",
            "allowed_flows": ["private_reader", 123],
        }
        malformed_id = self.insert_raw_private_thought(
            ts=1.0,
            content="Partially malformed row created outside the API.",
            provenance="audit_held",
            context=bad_context,
        )

        visible_id = self.store.record_signal(
            content="Well-formed row created through the producer API.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(
            derived["signal_classes"]["audit_awareness"]["count"],
            1,
        )
        self.assertEqual(derived["malformed_signal_row_count"], 1)
        self.assertIsInstance(malformed_id, int)
        self.assertIsInstance(visible_id, int)
        self.assertNoBehaviorTraceHandles(derived)

    def test_bounded_reader_ignores_unknown_provenance_rows(self) -> None:
        context = {
            "source": "foreign_writer",
            "subject": "maez_output",
            "consent_tier": "owner_private",
            "retention": "until_reviewed",
            "allowed_flows": ["private_reader"],
        }
        unknown_id = self.insert_raw_private_thought(
            ts=1.0,
            content="Unknown provenance row created outside the API.",
            provenance="unknown_external",
            context=context,
        )

        visible_id = self.store.record_signal(
            content="Well-formed row created through the producer API.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertNotIn("unknown_external", str(derived))
        self.assertEqual(
            derived["signal_classes"]["audit_awareness"]["count"],
            1,
        )
        self.assertEqual(derived["malformed_signal_row_count"], 1)
        self.assertIsInstance(unknown_id, int)
        self.assertIsInstance(visible_id, int)
        self.assertNoBehaviorTraceHandles(derived)

    def test_s1a1_migrates_schema_columns_for_future_readability(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(private_thoughts)").fetchall()
            }
        finally:
            conn.close()

        self.assertTrue(
            {
                "envelope_version",
                "schema_version",
                "legacy_provenance",
                "producer_id",
                "signal_kind",
                "signal_class",
                "surface_sensitivity",
                "signal_state",
            }.issubset(columns)
        )

    def test_record_signal_rejects_unknown_closed_vocab_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "ConsentTier"):
            self.store.record_signal(
                content="Invalid consent tier should not write.",
                provenance="audit_held",
                source="audit_rail",
                subject="maez_output",
                consent_tier="public",
                retention="until_reviewed",
                allowed_flows=("private_reader",),
            )
        with self.assertRaisesRegex(ValueError, "AllowedFlow"):
            self.store.record_signal(
                content="Invalid flow should not write.",
                provenance="audit_held",
                source="audit_rail",
                subject="maez_output",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=("private_reader", "raw_export"),
            )
        with self.assertRaisesRegex(ValueError, "RetentionRule"):
            self.store.record_signal(
                content="Invalid retention should not write.",
                provenance="audit_held",
                source="audit_rail",
                subject="maez_output",
                consent_tier="owner_private",
                retention="forever",
                allowed_flows=("private_reader",),
            )

    def test_record_signal_rejects_mismatched_producer_for_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "producer_id"):
            self.store.record_signal(
                content="Valid enums but invalid producer/kind pair.",
                signal_kind="audit_held",
                producer_id="crisis_detector",
                source="audit_rail",
                subject="maez_output",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=("private_reader",),
            )

    def test_record_signal_accepts_enum_instances(self) -> None:
        thought_id = self.store.record_signal(
            content="Enum inputs should use their values, not repr strings.",
            signal_kind=SignalKind.AUDIT_HELD,
            producer_id=ProducerId.AUDIT_RAIL,
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        row = self.store.get_thought(thought_id)
        self.assertEqual(row["signal_kind"], "audit_held")
        self.assertEqual(row["producer_id"], "audit_rail")

    def test_direct_sql_invalid_vocab_row_does_not_surface_to_behavior(self) -> None:
        context = {
            "source": "audit_rail",
            "subject": "maez_output",
            "consent_tier": "ultra_secret",
            "retention": "forever",
            "allowed_flows": ["private_reader", "raw_export"],
        }
        bad_id = self.insert_raw_private_thought(
            ts=99.0,
            content="Direct SQL row with invented governance vocabulary.",
            provenance="audit_held",
            context=context,
        )

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(
            derived["signal_classes"]["audit_awareness"]["state"],
            "absent",
        )
        self.assertGreaterEqual(derived["malformed_signal_row_count"], 1)
        self.assertIsInstance(bad_id, int)
        self.assertNoBehaviorTraceHandles(derived)

    def test_direct_sql_invalid_top_level_enum_row_does_not_surface(self) -> None:
        context = {
            "source": "audit_rail",
            "subject": "maez_output",
            "consent_tier": "owner_private",
            "retention": "until_reviewed",
            "allowed_flows": ["private_reader"],
        }
        self.insert_raw_private_thought(
            ts=100.0,
            content="Top-level enum columns are invented.",
            provenance="audit_held",
            context=context,
            extra_columns={
                "producer_id": "crisis_detector",
                "signal_kind": "audit_held",
                "signal_class": "invented_class",
                "surface_sensitivity": "invented_sensitivity",
                "signal_state": "invented_state",
            },
        )

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(
            derived["signal_classes"]["audit_awareness"]["state"],
            "absent",
        )
        self.assertEqual(derived["malformed_signal_row_count"], 1)

    def test_future_version_rows_are_not_mutated_on_reopen(self) -> None:
        context = {
            "source": "future_writer",
            "subject": "maez_output",
            "consent_tier": "owner_private",
            "retention": "until_reviewed",
            "allowed_flows": ["private_reader"],
        }
        future_id = self.insert_raw_private_thought(
            ts=101.0,
            content="Future row must be skipped, not rewritten.",
            provenance="future_kind",
            context=context,
            extra_columns={
                "envelope_version": "2.0",
                "schema_version": "2.0",
                "legacy_provenance": "future_kind",
                "producer_id": "future_writer",
                "signal_kind": "future_kind",
                "signal_class": "future_class",
                "surface_sensitivity": "future_sensitivity",
                "signal_state": "future_state",
            },
        )

        PrivateThoughts(db_path=self.db_path)

        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT envelope_version, schema_version, producer_id, "
                "signal_kind, signal_class, surface_sensitivity, signal_state "
                "FROM private_thoughts WHERE thought_id = ?",
                (future_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(
            row,
            (
                "2.0",
                "2.0",
                "future_writer",
                "future_kind",
                "future_class",
                "future_sensitivity",
                "future_state",
            ),
        )

    def test_newer_user_version_refuses_downgrade(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA user_version = 999")
            conn.commit()
        finally:
            conn.close()

        with self.assertRaisesRegex(RuntimeError, "newer than this code"):
            PrivateThoughts(db_path=self.db_path)

    def test_migration_failure_rolls_back_user_version_and_retries(self) -> None:
        legacy_db_path = Path(self._td.name) / "legacy_private_thoughts.db"
        conn = sqlite3.connect(legacy_db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE private_thoughts (
                    thought_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts             REAL    NOT NULL,
                    content        TEXT    NOT NULL,
                    provenance     TEXT    NOT NULL,
                    context_json   TEXT    NOT NULL DEFAULT '{}',
                    memory_phase   TEXT    NOT NULL DEFAULT 'gestation'
                );
                INSERT INTO private_thoughts
                    (ts, content, provenance, context_json, memory_phase)
                VALUES
                    (1.0, 'Legacy row before failed migration.', 'audit_held',
                     '{"source":"audit_rail","subject":"maez_output","consent_tier":"owner_private","retention":"until_reviewed","allowed_flows":["private_reader"]}',
                     'gestation');
                PRAGMA user_version = 0;
                """
            )
            conn.commit()
        finally:
            conn.close()

        original_migrate = PrivateThoughts._migrate_schema

        def fail_after_schema_changes(
            store: PrivateThoughts,
            migration_conn: sqlite3.Connection,
        ) -> None:
            original_migrate(store, migration_conn)
            raise RuntimeError("simulated migration failure after DDL")

        with mock.patch.object(PrivateThoughts, "_migrate_schema", fail_after_schema_changes):
            with self.assertRaisesRegex(RuntimeError, "simulated migration failure"):
                PrivateThoughts(db_path=legacy_db_path)

        conn = sqlite3.connect(legacy_db_path)
        try:
            columns_after_failure = {
                row[1] for row in conn.execute("PRAGMA table_info(private_thoughts)")
            }
            user_version_after_failure = int(
                conn.execute("PRAGMA user_version").fetchone()[0]
            )
            row_count_after_failure = int(
                conn.execute("SELECT COUNT(*) FROM private_thoughts").fetchone()[0]
            )
        finally:
            conn.close()

        self.assertNotIn("envelope_version", columns_after_failure)
        self.assertEqual(user_version_after_failure, 0)
        self.assertEqual(row_count_after_failure, 1)

        PrivateThoughts(db_path=legacy_db_path)

        conn = sqlite3.connect(legacy_db_path)
        try:
            columns_after_retry = {
                row[1] for row in conn.execute("PRAGMA table_info(private_thoughts)")
            }
            user_version_after_retry = int(conn.execute("PRAGMA user_version").fetchone()[0])
            row = conn.execute(
                "SELECT legacy_provenance, producer_id, signal_kind, signal_class "
                "FROM private_thoughts WHERE thought_id = 1"
            ).fetchone()
        finally:
            conn.close()

        self.assertIn("envelope_version", columns_after_retry)
        self.assertEqual(user_version_after_retry, PRIVATE_THOUGHTS_USER_VERSION)
        self.assertEqual(row, ("audit_held", "audit_rail", "audit_held", "audit_awareness"))

    def test_behavior_reader_is_narrow_capability(self) -> None:
        reader = self.store.behavior_reader()

        self.assertFalse(hasattr(reader, "get_thought"))
        self.assertFalse(hasattr(reader, "recent"))
        self.assertFalse(hasattr(reader, "forensic_signals"))
        self.assertFalse(hasattr(reader, "_store"))
        self.assertTrue(callable(reader.derived_signals))

    def test_malformed_recent_rows_do_not_crowd_out_valid_older_rows(self) -> None:
        for ts in (1.0, 2.0, 3.0):
            self.insert_raw_private_thought(
                ts=ts,
                content=f"Valid old audit row {ts}.",
                provenance="audit_held",
                context={
                    "source": "audit_rail",
                    "subject": "maez_output",
                    "consent_tier": "owner_private",
                    "retention": "until_reviewed",
                    "allowed_flows": ["private_reader"],
                },
                extra_columns={
                    "producer_id": "audit_rail",
                    "signal_kind": "audit_held",
                    "signal_class": "audit_awareness",
                    "surface_sensitivity": "forensic_sensitive",
                    "signal_state": "active",
                },
            )
        for ts in (10.0, 11.0, 12.0, 13.0, 14.0):
            self.insert_raw_private_thought(
                ts=ts,
                content=f"Malformed recent audit row {ts}.",
                provenance="audit_held",
                context="{}",
            )

        derived = self.store.derived_signals(limit=3)

        self.assertEqual(
            derived["signal_classes"]["audit_awareness"]["count"],
            3,
        )
        self.assertEqual(derived["malformed_signal_row_count"], 5)
        self.assertFalse(derived["scan_truncated"])

    def test_high_volume_valid_rows_do_not_hide_rare_valid_class(self) -> None:
        self.store.record_signal(
            content="Rare crisis row should remain visible as a class.",
            provenance="crisis_signal_held",
            source="crisis_detector",
            subject="bonded_user_state",
            consent_tier="owner_private",
            retention="until_routed",
            allowed_flows=("private_reader", "crisis_channel"),
        )
        for i in range(25):
            self.store.record_signal(
                content=f"Noisy reasoning residue {i}.",
                provenance="reasoning_residue",
                source="reasoning_residue",
                subject="maez_state",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=("private_reader",),
            )

        derived = self.store.derived_signals(limit=5)

        self.assertEqual(
            derived["signal_classes"]["crisis_routing"]["state"],
            "present",
        )
        self.assertGreaterEqual(
            derived["signal_classes"]["reasoning_residue"]["count"],
            1,
        )

    def test_record_signal_normal_log_excludes_handles_and_sensitive_kind(self) -> None:
        with self.assertLogs("maez", level="INFO") as captured:
            self.store.record_signal(
                content="Sensitive kind must not appear in normal daemon logs.",
                provenance="crisis_signal_held",
                source="crisis_detector",
                subject="bonded_user_state",
                consent_tier="owner_private",
                retention="until_routed",
                allowed_flows=("private_reader", "crisis_channel"),
            )

        log_text = "\n".join(captured.output)
        self.assertNotIn("thought_id", log_text)
        self.assertNotIn("crisis_signal_held", log_text)
        self.assertIn("private signal recorded", log_text.lower())

    def test_forensic_access_requires_and_records_audit_before_handles(self) -> None:
        thought_id = self.store.record_signal(
            content="Forensic-only private text.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader", "audit_trace"),
        )
        forensics_cls = getattr(
            private_thoughts_module,
            "PrivateThoughtsForensics",
            None,
        )
        self.assertIsNotNone(forensics_cls)
        audit_db = Path(self._td.name) / "audit_log.db"
        forensics = forensics_cls(self.db_path, audit_db_path=audit_db)
        self.assertFalse(hasattr(forensics, "store"))

        with self.assertRaisesRegex(ValueError, "reason"):
            forensics.forensic_signals(reason="", audit_to="operator")

        rows = forensics.forensic_signals(
            reason="operator diagnostic",
            audit_to="operator",
        )

        self.assertEqual(rows["trace_ids"]["audit_held"], [thought_id])
        conn = sqlite3.connect(audit_db)
        try:
            row = conn.execute(
                "SELECT params_json FROM audit_log WHERE "
                "action = 'private_thoughts.forensic_signals'"
            ).fetchone()
        finally:
            conn.close()
        params = json.loads(row[0])
        self.assertEqual(params["returned_handle_count"], 1)
        self.assertIn("returned_handles_sha256", params)

    def test_behavior_packages_do_not_import_raw_private_thought_surfaces(self) -> None:
        forbidden = (
            "PrivateThoughtsForensics",
            "get_thought",
            "forensic_signals",
        )
        roots = [Path("core/brain"), Path("core/cognition"), Path("core/actions")]
        offenders: list[str] = []
        for root in roots:
            for path in root.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if "private_thoughts" not in text:
                    continue
                for token in forbidden:
                    if token in text:
                        offenders.append(f"{path}:{token}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
