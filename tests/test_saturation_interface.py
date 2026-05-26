from __future__ import annotations

import ast
import tempfile
import unittest
from datetime import UTC
from pathlib import Path
from unittest.mock import patch

from core.evolution.wonderings import Wonderings


def sample_saturation_for_test(*, bond_id, store, temperament_snapshot):
    from core.evolution.drive_driven_curiosity import compute_saturation

    return compute_saturation(
        bond_id=bond_id,
        store=store,
        temperament_snapshot=temperament_snapshot,
    )


class SaturationInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = Wonderings(db_path=Path(self.tmpdir.name) / "wonderings.db")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _add_object(
        self,
        *,
        bond_id: str = "firstborn",
        priority_class: str = "owner_bond",
        salience: float = 0.5,
        question: str = "what is still open?",
    ) -> int:
        from core.evolution.drive_driven_curiosity import (
            SubjectKind,
            record_wondering_drive_metadata,
        )

        wondering_id = self.store.add(question, source="manual", bond_id=bond_id)
        record_wondering_drive_metadata(
            self.store,
            wondering_id=wondering_id,
            bond_id=bond_id,
            encounter_source="wondering_generated",
            encounter_ref_digest="hmac-sha256:" + "1" * 64,
            priority_class=priority_class,
            salience=salience,
            subject_kind=SubjectKind.PUBLIC_TOPIC,
        )
        return wondering_id

    def test_continuous_press_formula(self):
        from core.evolution.drive_driven_curiosity import resolve_curiosity_object

        self._add_object(priority_class="owner_bond", salience=0.8)
        self._add_object(priority_class="world_knowledge", salience=0.5)
        resolved_id = self._add_object(priority_class="self_growth", salience=0.9)
        resolve_curiosity_object(
            self.store,
            wondering_id=resolved_id,
            conclusion="answered",
            resolution_marker_type="explicit_self_resolved",
            resolution_marker_utc=1779710400.0,
        )

        register = sample_saturation_for_test(
            bond_id="firstborn",
            store=self.store,
            temperament_snapshot={"awareness": 5.0, "persistence": 5.0},
        )

        self.assertEqual(register.bond_id, "firstborn")
        self.assertEqual(register.open_object_count, 2)
        self.assertAlmostEqual(register.total_salience, 1.3)
        self.assertAlmostEqual(register.weighted_salience, 0.8 + (0.5 * 0.4))
        self.assertAlmostEqual(register.carrying_capacity, 10.0)
        self.assertAlmostEqual(register.press, 1.0 / 10.0)
        self.assertEqual(register.sampled_utc.tzinfo, UTC)

    def test_temperament_modulates_carrying_capacity(self):
        from core.evolution.drive_driven_curiosity import (
            PressBand,
            classify_press,
            compute_carrying_capacity,
        )

        self.assertAlmostEqual(
            compute_carrying_capacity({"awareness": 5.0, "persistence": 5.0}),
            10.0,
        )
        self.assertAlmostEqual(
            compute_carrying_capacity({"awareness": 8.0, "persistence": 2.5}),
            8.0,
        )
        self.assertAlmostEqual(
            compute_carrying_capacity({"awareness": None, "persistence": None}),
            10.0,
        )
        self.assertAlmostEqual(
            compute_carrying_capacity({"awareness": 0.0, "persistence": 5.0}),
            0.0,
        )
        self.assertIs(classify_press(0.29), PressBand.LIGHT)
        self.assertIs(classify_press(0.3), PressBand.PRESS)
        self.assertIs(classify_press(0.7), PressBand.HEAVY)
        self.assertIs(classify_press(1.2), PressBand.OVERLOADED)

    def test_compute_saturation_consumer_allowlist(self):
        allowed = {
            Path("core/evolution/dream_state.py"),
            Path("core/evolution/wonderings.py"),
            Path("core/evolution/private_thoughts.py"),
            Path("core/evolution/drive_driven_curiosity.py"),
        }
        allowed_test_prefix = "tests/test_saturation_"
        violations: list[str] = []

        for path in [*Path("core").rglob("*.py"), *Path("daemon").rglob("*.py")]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports_name = False
            calls_name = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module == "core.evolution.drive_driven_curiosity":
                        imports_name = any(
                            alias.name == "compute_saturation" for alias in node.names
                        )
                elif isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "compute_saturation":
                        calls_name = True
                    elif (
                        isinstance(func, ast.Attribute)
                        and func.attr == "compute_saturation"
                    ):
                        calls_name = True
            if (imports_name or calls_name) and path not in allowed:
                violations.append(str(path))

        for path in Path("tests").glob("test_*.py"):
            if path.as_posix().startswith(allowed_test_prefix):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module == "core.evolution.drive_driven_curiosity":
                        if any(alias.name == "compute_saturation" for alias in node.names):
                            violations.append(str(path))
                elif isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "compute_saturation":
                        violations.append(str(path))
                    elif (
                        isinstance(func, ast.Attribute)
                        and func.attr == "compute_saturation"
                    ):
                        violations.append(str(path))

        subjective_duration_source = Path("core/evolution/subjective_duration.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("compute_saturation", subjective_duration_source)
        self.assertEqual(violations, [])

    def test_snapshot_temperament_cross_bond_emits_default_diagnostic_before_raise(self):
        from core.evolution.drive_driven_curiosity import snapshot_temperament_for_bond
        from core.policies.exceptions import CrossBondAccessError

        events: list[dict] = []

        class FakeDiagnosticSink:
            accepts_raw_diagnostic_fields = True

            def __call__(self, event):
                events.append(dict(event))

        with patch(
            "core.evolution.drive_driven_curiosity.identity.user_profile_id",
            return_value="authorized-bond",
        ), patch(
            "core.evolution.drive_driven_curiosity.DriveCuriosityDiagnosticSink",
            return_value=FakeDiagnosticSink(),
        ):
            with self.assertRaises(CrossBondAccessError):
                snapshot_temperament_for_bond("other-bond")

        self.assertEqual(events[0]["event_type"], "CROSS_BOND_ACCESS_REFUSED")
        self.assertEqual(events[0]["surface"], "snapshot_temperament_for_bond")


if __name__ == "__main__":
    unittest.main()
