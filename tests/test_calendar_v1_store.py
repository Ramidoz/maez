"""Calendar v1 noncanonical store contract.

Decision 28 / ADR 0033 keeps Calendar outside Maez's body until a reviewed
flow admits derived facts. The local store is pre-body staging: minimized,
versioned, content-free in telemetry, and tombstone-survivable.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class CalendarV1StoreTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.db_path = Path(self._td.name) / "calendar_v1.db"

    def test_store_creates_required_tables_with_schema_version_columns(self):
        from core.information_limb.calendar_store import CalendarStore

        store = CalendarStore(self.db_path)
        store.initialize()

        with closing(sqlite3.connect(self.db_path)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            expected = {
                "calendar_provider_mirror",
                "calendar_read_model",
                "calendar_sync_state",
                "calendar_tombstone_sidecar",
                "calendar_audit_events",
                "calendar_policy_versions",
            }
            self.assertTrue(expected.issubset(tables))
            for table in expected:
                columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                self.assertIn("calendar_store_schema_version", columns, table)

    def test_schema_mismatch_blocks_startup(self):
        from core.information_limb.calendar_store import CalendarStore, CalendarStoreError

        store = CalendarStore(self.db_path)
        store.initialize()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE calendar_policy_versions SET calendar_store_schema_version=?",
                ("999",),
            )
            conn.commit()

        with self.assertRaisesRegex(CalendarStoreError, "schema"):
            store.validate_schema()

    def test_provider_mirror_rejects_forbidden_raw_calendar_fields(self):
        from core.information_limb.calendar_store import CalendarStore, CalendarStoreError

        store = CalendarStore(self.db_path)
        store.initialize()

        with self.assertRaisesRegex(CalendarStoreError, "forbidden"):
            store.upsert_provider_mirror(
                source_instance_id="primary",
                external_event_id_hash="evt_hash",
                source_revision_hash="rev_hash",
                provider_updated_at="2026-05-15T12:00:00Z",
                facts={
                    "safe_title_token": "[calendar event]",
                    "description": "raw description must never land here",
                },
            )

    def test_safe_title_and_location_tokens_cannot_carry_raw_text(self):
        from core.information_limb.calendar_store import CalendarStore, CalendarStoreError

        store = CalendarStore(self.db_path)
        store.initialize()

        with self.assertRaisesRegex(CalendarStoreError, "safe token"):
            store.upsert_provider_mirror(
                source_instance_id="primary",
                external_event_id_hash="evt_hash",
                source_revision_hash="rev_hash",
                provider_updated_at="2026-05-15T12:00:00Z",
                facts={"safe_title_token": "Coffee with Sarah re: her divorce"},
            )

    def test_tombstone_survives_provider_mirror_delete(self):
        from core.information_limb.calendar_store import CalendarStore

        store = CalendarStore(self.db_path)
        store.initialize()
        store.upsert_provider_mirror(
            source_instance_id="primary",
            external_event_id_hash="evt_hash",
            source_revision_hash="rev_hash",
            provider_updated_at="2026-05-15T12:00:00Z",
            facts={"safe_title_token": "[calendar event]"},
        )

        store.tombstone_provider_record(
            source_instance_id="primary",
            external_event_id_hash="evt_hash",
            source_revision_hash="rev_hash",
            source_deleted_at="2026-05-15T12:05:00Z",
            deletion_observed_at="2026-05-15T12:06:00Z",
        )
        store.delete_provider_mirror(
            source_instance_id="primary",
            external_event_id_hash="evt_hash",
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            mirror_count = conn.execute("SELECT COUNT(*) FROM calendar_provider_mirror").fetchone()[
                0
            ]
            tombstone = conn.execute(
                "SELECT external_event_id_hash, record_state FROM calendar_tombstone_sidecar"
            ).fetchone()
        self.assertEqual(mirror_count, 0)
        self.assertEqual(tuple(tombstone), ("evt_hash", "tombstoned"))

    def test_health_snapshot_is_aggregate_only(self):
        from core.information_limb.calendar_store import CalendarStore

        store = CalendarStore(self.db_path)
        store.initialize()
        store.upsert_provider_mirror(
            source_instance_id="primary",
            external_event_id_hash="evt_hash",
            source_revision_hash="rev_hash",
            provider_updated_at="2026-05-15T12:00:00Z",
            facts={"safe_title_token": "[redacted calendar detail]"},
        )

        health = store.health_snapshot(mode="v1", auth_ready=False)

        self.assertEqual(health["event_count"], 1)
        self.assertEqual(health["connector_state"], "auth_unavailable")
        encoded = json.dumps(health, sort_keys=True)
        for forbidden in ("title", "attendee", "location", "description", "evt_hash", "rev_hash"):
            self.assertNotIn(forbidden, encoded)


if __name__ == "__main__":
    unittest.main()
