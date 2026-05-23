from __future__ import annotations

import unittest
from pathlib import Path

import yaml


class PrivacyEgressInventoryTests(unittest.TestCase):
    def test_network_migration_allowlist_has_required_fields(self):
        path = Path("docs/slices/privacy-egress-gate/network_migration_allowlist.yaml")
        self.assertTrue(path.exists(), "missing egress migration allow-list")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], "maez-egress-migration-allowlist-v1")
        entries = payload["entries"]
        self.assertGreaterEqual(len(entries), 4)
        required = {
            "path",
            "symbol",
            "destination",
            "surface",
            "category",
            "status",
            "owner_visible_rationale",
            "removal_target",
            "review_by",
            "surface_owner",
        }
        for entry in entries:
            self.assertTrue(required <= set(entry), entry)
            self.assertIn(entry["category"], {
                "runtime_external",
                "runtime_localhost",
                "dev_eval_only",
                "subprocess_mediated_external",
                "non_maez_tooling",
                "out_of_v1_scope_with_rationale",
            })
            self.assertIn(entry["status"], {
                "shadow_mode",
                "unmigrated",
                "proxy_shadow_provenanced",
                "proxy_shadow",
                "inventory_only",
                "deprecated",
            })
            self.assertNotEqual(entry["status"], "migrated")

    def test_direct_cloud_routes_are_not_unmigrated_after_closure(self):
        path = Path("docs/slices/privacy-egress-gate/network_migration_allowlist.yaml")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        entries = {
            (entry["path"], entry["symbol"]): entry
            for entry in payload["entries"]
        }

        for key in (
            ("skills/claude_router.py", "call_claude"),
        ):
            self.assertIn(key, entries)
            self.assertNotEqual(entries[key]["status"], "unmigrated")
            self.assertIn("proxy", entries[key]["removal_target"])

    def test_fast_backend_cloud_route_is_deprecated_after_retirement(self):
        path = Path("docs/slices/privacy-egress-gate/network_migration_allowlist.yaml")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        entries = {
            (entry["path"], entry["symbol"]): entry
            for entry in payload["entries"]
        }
        key = ("core/routing/fast_backend_cloud.py", "CloudBackend.generate")

        self.assertIn(key, entries)
        entry = entries[key]
        self.assertEqual(entry["status"], "deprecated")
        combined = (
            entry["owner_visible_rationale"]
            + " "
            + entry["removal_target"]
        ).lower()
        self.assertIn("fast-backend cloud retirement", combined)
        self.assertIn("2026-05-23", combined)


if __name__ == "__main__":
    unittest.main()
