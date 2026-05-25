from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from core.evolution.wonderings import Wonderings


class CuriosityWonderingsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "wonderings.db"
        self.store = Wonderings(db_path=self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def test_wondering_drive_metadata_schema_fk_index_enforced(self):
        with closing(self._connect()) as con:
            columns = {
                row["name"]: row
                for row in con.execute(
                    "PRAGMA table_info(wondering_drive_metadata)"
                ).fetchall()
            }
            self.assertEqual(
                {
                    "wondering_id",
                    "bond_id",
                    "encounter_source",
                    "encounter_ref_digest",
                    "priority_class",
                    "salience",
                    "autonomy_lane_hints",
                    "subject_kind",
                    "third_party_consent_allows_external_research",
                    "produced_via_subjective_duration_depth",
                    "resolution_marker_type",
                    "resolution_marker_utc",
                    "transition_reason",
                    "created_at",
                },
                set(columns),
            )
            self.assertTrue(columns["bond_id"]["notnull"])
            self.assertTrue(columns["encounter_source"]["notnull"])
            self.assertTrue(columns["encounter_ref_digest"]["notnull"])
            self.assertTrue(columns["subject_kind"]["notnull"])
            self.assertEqual(columns["resolution_marker_utc"]["type"].upper(), "REAL")

            fks = con.execute(
                "PRAGMA foreign_key_list(wondering_drive_metadata)"
            ).fetchall()
            self.assertTrue(
                any(row["table"] == "wonderings" and row["to"] == "id" for row in fks)
            )

            indexes = {
                row["name"]
                for row in con.execute(
                    "PRAGMA index_list(wondering_drive_metadata)"
                ).fetchall()
            }
            self.assertIn("idx_wondering_drive_metadata_bond", indexes)

            with self.assertRaises(sqlite3.IntegrityError):
                con.execute(
                    """
                    INSERT INTO wondering_drive_metadata (
                        wondering_id, bond_id, encounter_source,
                        encounter_ref_digest, priority_class, salience,
                        autonomy_lane_hints, subject_kind,
                        third_party_consent_allows_external_research,
                        produced_via_subjective_duration_depth, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        999_999,
                        "private_owner",
                        "wondering_generated",
                        "hmac-sha256:" + "0" * 64,
                        "owner_bond",
                        0.5,
                        "[]",
                        "public_topic",
                        0,
                        0,
                        1.0,
                    ),
                )

    def test_add_keeps_legacy_default_and_accepts_real_bond_keyword(self):
        legacy_id = self.store.add("legacy question", source="test")
        bonded_id = self.store.add(
            "bonded question",
            source="test",
            bond_id="private_owner",
        )

        with closing(self._connect()) as con:
            legacy = con.execute(
                "SELECT bond_id FROM wonderings WHERE id = ?",
                (legacy_id,),
            ).fetchone()
            bonded = con.execute(
                "SELECT bond_id FROM wonderings WHERE id = ?",
                (bonded_id,),
            ).fetchone()

        self.assertEqual(legacy["bond_id"], "_LEGACY")
        self.assertEqual(bonded["bond_id"], "private_owner")

    def test_legacy_row_refused_at_single_row_drive_projector(self):
        from core.evolution.drive_driven_curiosity import (
            LegacyWonderingProjectionRefused,
            project_curiosity_object,
        )

        legacy_id = self.store.add("legacy question", source="test")

        with self.assertRaises(LegacyWonderingProjectionRefused):
            project_curiosity_object(self.store, legacy_id)

    def test_legacy_rows_skipped_not_raised_in_collection_drive_readers(self):
        from core.evolution.drive_driven_curiosity import (
            list_drive_curiosity_objects,
            record_wondering_drive_metadata,
        )

        legacy_id = self.store.add("legacy question", source="test")
        bonded_id = self.store.add(
            "bonded question",
            source="test",
            bond_id="private_owner",
        )
        record_wondering_drive_metadata(
            self.store,
            wondering_id=legacy_id,
            bond_id="_LEGACY",
            encounter_source="wondering_generated",
            encounter_ref_digest="hmac-sha256:" + "1" * 64,
            priority_class="owner_bond",
            salience=0.2,
            subject_kind="public_topic",
        )
        record_wondering_drive_metadata(
            self.store,
            wondering_id=bonded_id,
            bond_id="private_owner",
            encounter_source="wondering_generated",
            encounter_ref_digest="hmac-sha256:" + "2" * 64,
            priority_class="owner_bond",
            salience=0.8,
            subject_kind="public_topic",
        )

        objects = list_drive_curiosity_objects(self.store, bond_id="private_owner")

        self.assertEqual([obj.wondering_id for obj in objects], [bonded_id])
        self.assertEqual(self.store.list_open(limit=10)[0]["id"], legacy_id)

    def test_wondering_resolution_writes_resolved_at_and_sidecar_marker(self):
        from core.evolution.drive_driven_curiosity import (
            record_wondering_drive_metadata,
            resolve_curiosity_object,
        )

        wondering_id = self.store.add(
            "bonded question",
            source="test",
            bond_id="private_owner",
        )
        record_wondering_drive_metadata(
            self.store,
            wondering_id=wondering_id,
            bond_id="private_owner",
            encounter_source="wondering_generated",
            encounter_ref_digest="hmac-sha256:" + "3" * 64,
            priority_class="owner_bond",
            salience=0.8,
            subject_kind="public_topic",
        )

        resolve_curiosity_object(
            self.store,
            wondering_id=wondering_id,
            conclusion="answered",
            resolution_marker_type="explicit_self_resolved",
            resolution_marker_utc=1779710400.0,
        )

        row = self.store.get(wondering_id)
        self.assertEqual(row["status"], "resolved")
        self.assertIsNotNone(row["resolved_at"])

        with closing(self._connect()) as con:
            sidecar = con.execute(
                """
                SELECT resolution_marker_type, resolution_marker_utc
                FROM wondering_drive_metadata
                WHERE wondering_id = ?
                """,
                (wondering_id,),
            ).fetchone()

        self.assertEqual(sidecar["resolution_marker_type"], "explicit_self_resolved")
        self.assertAlmostEqual(sidecar["resolution_marker_utc"], 1779710400.0)

    def test_sidecar_refuses_mismatched_parent_bond_and_duplicate_write(self):
        from core.evolution.drive_driven_curiosity import (
            SidecarBondMismatchRefused,
            SidecarDuplicateWriteRefused,
            record_wondering_drive_metadata,
        )

        wondering_id = self.store.add(
            "bonded question",
            source="test",
            bond_id="private_owner",
        )

        with self.assertRaises(SidecarBondMismatchRefused):
            record_wondering_drive_metadata(
                self.store,
                wondering_id=wondering_id,
                bond_id="other_bond",
                encounter_source="wondering_generated",
                encounter_ref_digest="hmac-sha256:" + "4" * 64,
                priority_class="owner_bond",
                salience=0.4,
                subject_kind="public_topic",
            )

        record_wondering_drive_metadata(
            self.store,
            wondering_id=wondering_id,
            bond_id="private_owner",
            encounter_source="wondering_generated",
            encounter_ref_digest="hmac-sha256:" + "5" * 64,
            priority_class="owner_bond",
            salience=0.4,
            subject_kind="public_topic",
        )

        with self.assertRaises(SidecarDuplicateWriteRefused):
            record_wondering_drive_metadata(
                self.store,
                wondering_id=wondering_id,
                bond_id="private_owner",
                encounter_source="explicit_owner_flag",
                encounter_ref_digest="hmac-sha256:" + "6" * 64,
                priority_class="owner_bond",
                salience=0.9,
                subject_kind="public_topic",
            )


if __name__ == "__main__":
    unittest.main()
