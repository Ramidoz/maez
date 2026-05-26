from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path


class DriveCuriosityBondScopingTests(unittest.TestCase):
    def test_per_bond_hmac_keys_distinct(self):
        from core.policies.diagnostics import hmac_digest_for_bond

        master_key = bytes(range(32))

        first = hmac_digest_for_bond(
            master_key=master_key,
            bond_id="firstborn",
            value="same-content",
        )
        second = hmac_digest_for_bond(
            master_key=master_key,
            bond_id="second-bond",
            value="same-content",
        )

        self.assertRegex(first, r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(second, r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertNotEqual(first, second)

    def test_master_key_auto_initialized_with_0600_perms(self):
        from core.policies.diagnostics import (
            CuriosityDiagnosticEventType,
            ensure_master_key,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            key_path = root / "memory" / "drive_curiosity_master.key"
            log_path = root / "logs" / "drive_driven_curiosity_diagnostics.jsonl"

            key = ensure_master_key(master_key_path=key_path, diagnostic_log_path=log_path)

            rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            key_size = key_path.stat().st_size
            key_mode = stat.S_IMODE(key_path.stat().st_mode)

        self.assertEqual(len(key), 32)
        self.assertEqual(key_size, 32)
        self.assertEqual(key_mode, 0o600)
        self.assertEqual(rows[0]["event_type"], CuriosityDiagnosticEventType.MASTER_KEY_INITIALIZED.value)
        self.assertIsNone(rows[0]["bond_digest"])

    def test_master_key_path_distinct_from_egress_telemetry_key(self):
        from core import paths

        drive_path = paths.drive_curiosity_master_key()
        egress_path = paths.memory_dir() / "egress_telemetry.key"

        self.assertNotEqual(drive_path, egress_path)
        self.assertEqual(drive_path.name, "drive_curiosity_master.key")

    def test_compute_saturation_bond_scoped(self):
        from core.evolution.drive_driven_curiosity import (
            SubjectKind,
            record_wondering_drive_metadata,
        )
        from core.evolution.wonderings import Wonderings
        from tests.test_saturation_interface import sample_saturation_for_test

        with tempfile.TemporaryDirectory() as td:
            store = Wonderings(db_path=Path(td) / "wonderings.db")
            firstborn_id = store.add(
                "firstborn open question",
                source="manual",
                bond_id="firstborn",
            )
            second_bond_id = store.add(
                "second bond open question",
                source="manual",
                bond_id="second-bond",
            )
            record_wondering_drive_metadata(
                store,
                wondering_id=firstborn_id,
                bond_id="firstborn",
                encounter_source="wondering_generated",
                encounter_ref_digest="hmac-sha256:" + "a" * 64,
                priority_class="owner_bond",
                salience=0.4,
                subject_kind=SubjectKind.PUBLIC_TOPIC,
            )
            record_wondering_drive_metadata(
                store,
                wondering_id=second_bond_id,
                bond_id="second-bond",
                encounter_source="wondering_generated",
                encounter_ref_digest="hmac-sha256:" + "b" * 64,
                priority_class="owner_bond",
                salience=1.0,
                subject_kind=SubjectKind.PUBLIC_TOPIC,
            )

            register = sample_saturation_for_test(
                bond_id="firstborn",
                store=store,
                temperament_snapshot={"awareness": 5.0, "persistence": 5.0},
            )

        self.assertEqual(register.open_object_count, 1)
        self.assertAlmostEqual(register.total_salience, 0.4)
        self.assertAlmostEqual(register.weighted_salience, 0.4)

    def test_compute_saturation_rechecks_parent_wondering_bond(self):
        from core.evolution.drive_driven_curiosity import (
            SubjectKind,
            record_wondering_drive_metadata,
        )
        from core.evolution.wonderings import Wonderings
        from tests.test_saturation_interface import sample_saturation_for_test

        with tempfile.TemporaryDirectory() as td:
            store = Wonderings(db_path=Path(td) / "wonderings.db")
            wondering_id = store.add(
                "parent belongs to the other bond",
                source="manual",
                bond_id="second-bond",
            )
            record_wondering_drive_metadata(
                store,
                wondering_id=wondering_id,
                bond_id="second-bond",
                encounter_source="wondering_generated",
                encounter_ref_digest="hmac-sha256:" + "c" * 64,
                priority_class="owner_bond",
                salience=1.0,
                subject_kind=SubjectKind.PUBLIC_TOPIC,
            )
            with store._lock, store._conn() as con:
                con.execute(
                    """
                    UPDATE wondering_drive_metadata
                       SET bond_id = ?
                     WHERE wondering_id = ?
                    """,
                    ("firstborn", wondering_id),
                )

            register = sample_saturation_for_test(
                bond_id="firstborn",
                store=store,
                temperament_snapshot={"awareness": 5.0, "persistence": 5.0},
            )

        self.assertEqual(register.open_object_count, 0)
        self.assertAlmostEqual(register.weighted_salience, 0.0)


if __name__ == "__main__":
    unittest.main()
