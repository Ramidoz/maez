import json
from pathlib import Path
import unittest


MANIFEST_PATH = Path("scripts/backup/backup_state_manifest.json")


class ManifestCoverageTest(unittest.TestCase):
    def _manifest(self):
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_welfare_stores_are_required_welfare(self):
        manifest = self._manifest()
        by_path = {entry["path"]: entry for entry in manifest["entries"]}
        for path in (
            "memory/salience_ledger.db",
            "memory/subjective_duration.db",
            "memory/routing_observation.db",
            "memory/veto_ledger.db",
        ):
            self.assertIn(path, by_path, f"{path} not in manifest")
            self.assertEqual(
                by_path[path].get("class"),
                "required_welfare",
                f"{path} not required_welfare",
            )
            self.assertTrue(by_path[path].get("required"), f"{path} not required")

    def test_private_thoughts_stays_protected_as_required_welfare(self):
        manifest = self._manifest()
        by_path = {entry["path"]: entry for entry in manifest["entries"]}
        self.assertIn("memory/private_thoughts.db", by_path)
        self.assertEqual(
            by_path["memory/private_thoughts.db"].get("class"),
            "required_welfare",
        )

    def test_fresh_moment_receipts_are_welfare_protected_when_present(self):
        manifest = self._manifest()
        by_path = {entry["path"]: entry for entry in manifest["entries"]}
        path = "memory/fresh_moment_receipts.db"
        self.assertIn(path, by_path, f"{path} not in manifest")
        self.assertEqual(by_path[path].get("class"), "required_welfare")
        self.assertFalse(
            by_path[path].get("required"),
            "fresh moment receipts are absent until the first real receipt; "
            "backup must protect them when present without failing before then",
        )

    def test_skips_have_written_reasons(self):
        manifest = self._manifest()
        skips = manifest.get("intentionally_skipped", [])
        self.assertGreaterEqual(len(skips), 1)
        for skipped in skips:
            self.assertTrue(skipped.get("path"), f"skip missing path: {skipped}")
            self.assertTrue(skipped.get("reason"), f"skip missing reason: {skipped}")
            self.assertEqual(skipped.get("class"), "ephemeral_skip")

    def test_every_entry_has_a_valid_class(self):
        manifest = self._manifest()
        valid = {"required_continuity", "required_welfare", "optional_observability"}
        for entry in manifest["entries"]:
            self.assertIn(
                entry.get("class"),
                valid,
                f"entry missing/invalid class: {entry['path']}",
            )

    def test_backup_inventory_still_loads_manifest(self):
        from scripts.backup.inventory import load_default_manifest

        manifest = load_default_manifest()
        self.assertTrue(manifest.get("entries"))
