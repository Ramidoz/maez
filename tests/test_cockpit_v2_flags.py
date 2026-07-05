import tempfile
import unittest
from pathlib import Path


class CockpitV2FlagRegistryTests(unittest.TestCase):
    def test_unknown_flag_write_is_refused(self):
        from core.cockpit.flags import write_policy_for_flag

        policy = write_policy_for_flag("MAEZ_UNREVIEWED_NEW_FLAG", "1", registry={})

        self.assertFalse(policy["direct_write_allowed"])
        self.assertEqual(policy["reason"], "unknown_flag")
        self.assertEqual(policy["tier"], "unclassified")

    def test_process_file_divergence_is_warning_with_both_values_visible(self):
        from core.cockpit.flags import compare_file_process_flags

        comparison = compare_file_process_flags(
            file_env={
                "MAEZ_BODY_LEGIBILITY": "1",
                "MAEZ_COCKPIT_V2": "0",
                "MAEZ_MATCHED": "1",
            },
            process_env={
                "MAEZ_BODY_LEGIBILITY": "0",
                "MAEZ_PROCESS_ONLY": "1",
                "MAEZ_MATCHED": "1",
            },
        )
        by_name = {row["name"]: row for row in comparison}

        self.assertEqual(by_name["MAEZ_BODY_LEGIBILITY"]["sync_state"], "mismatch")
        self.assertEqual(by_name["MAEZ_BODY_LEGIBILITY"]["severity"], "warning")
        self.assertEqual(by_name["MAEZ_BODY_LEGIBILITY"]["file_value"], "1")
        self.assertEqual(by_name["MAEZ_BODY_LEGIBILITY"]["process_value"], "0")
        self.assertEqual(by_name["MAEZ_COCKPIT_V2"]["sync_state"], "file_only")
        self.assertEqual(by_name["MAEZ_COCKPIT_V2"]["process_value"], None)
        self.assertEqual(by_name["MAEZ_PROCESS_ONLY"]["sync_state"], "process_only")
        self.assertEqual(by_name["MAEZ_PROCESS_ONLY"]["file_value"], None)
        self.assertEqual(by_name["MAEZ_MATCHED"]["sync_state"], "in_sync")
        self.assertEqual(by_name["MAEZ_MATCHED"]["severity"], "ok")

    def test_sensitive_env_values_are_redacted_but_divergence_stays_visible(self):
        from core.cockpit.flags import compare_file_process_flags

        comparison = compare_file_process_flags(
            file_env={"MAEZ_TELEGRAM_TOKEN": "file-token"},
            process_env={"MAEZ_TELEGRAM_TOKEN": "process-token"},
        )

        row = comparison[0]
        self.assertEqual(row["name"], "MAEZ_TELEGRAM_TOKEN")
        self.assertEqual(row["sync_state"], "mismatch")
        self.assertEqual(row["severity"], "warning")
        self.assertEqual(row["file_value"], "[redacted]")
        self.assertEqual(row["process_value"], "[redacted]")

    def test_t3_action_has_no_direct_write_endpoint(self):
        from core.cockpit.flags import FlagRegistryEntry, write_policy_for_flag

        registry = {
            "S7_CEREMONY": FlagRegistryEntry(
                name="S7_CEREMONY",
                label="S7 ceremony",
                tier="T3",
                description="Human-gated self-shaping ceremony.",
                witness_recipe="Complete the existing S7 ceremony route.",
                revert_line="No direct env revert; follow the ceremony rollback path.",
                owner_review_status="pending_owner_review",
            )
        }

        policy = write_policy_for_flag("S7_CEREMONY", "1", registry=registry)

        self.assertFalse(policy["direct_write_allowed"])
        self.assertEqual(policy["reason"], "ceremony_only")
        self.assertEqual(policy["tier"], "T3")
        self.assertIsNone(policy["direct_write_endpoint"])

    def test_owner_pinned_birth_and_s7_switches_are_ceremony_only(self):
        from core.cockpit.flags import write_policy_for_flag

        for name in ("MAEZ_LEDGER_WRITES", "S7_LIVE_WEBAUTHN_CEREMONY"):
            with self.subTest(name=name):
                policy = write_policy_for_flag(name, "1")
                self.assertFalse(policy["direct_write_allowed"])
                self.assertEqual(policy["reason"], "ceremony_only")
                self.assertEqual(policy["tier"], "T3")
                self.assertIsNone(policy["direct_write_endpoint"])

    def test_owner_review_unlocks_safe_t1_policy(self):
        from core.cockpit.flags import write_policy_for_flag

        policy = write_policy_for_flag("MAEZ_BODY_LEGIBILITY", "1")

        self.assertTrue(policy["direct_write_allowed"])
        self.assertEqual(policy["reason"], "ok")
        self.assertEqual(policy["tier"], "T1")
        self.assertEqual(
            policy["direct_write_endpoint"],
            "/api/v2/cockpit/flags/MAEZ_BODY_LEGIBILITY",
        )

    def test_registry_entries_include_witness_recipe_and_revert_line(self):
        from core.cockpit.flags import default_registry

        entry = default_registry()["MAEZ_COCKPIT_V2"]

        self.assertEqual(entry.owner_review_status, "owner_reviewed")
        self.assertIn("MAEZ_COCKPIT_V2", entry.witness_recipe)
        self.assertIn("MAEZ_COCKPIT_V2", entry.revert_line)
        self.assertIn("restart", entry.witness_recipe.lower())

    def test_discovery_combines_code_env_file_and_process_sources(self):
        from core.cockpit.flags import discover_observed_flags

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            code_root = root / "code"
            env_root = root / "env"
            code_root.mkdir()
            env_root.mkdir()
            (code_root / "module.py").write_text(
                'strict_env_flag("MAEZ_CODE_ONLY")\n', encoding="utf-8"
            )
            env_file = env_root / "model.env"
            env_file.write_text(
                "# comment\nMAEZ_FILE_ONLY=1\nexport MAEZ_SHARED=0\n",
                encoding="utf-8",
            )

            observed = discover_observed_flags(
                code_roots=[code_root],
                env_files=[env_file],
                process_envs=[{"MAEZ_PROCESS_ONLY": "1", "MAEZ_SHARED": "1"}],
            )
            by_name = {row["name"]: row for row in observed}

        self.assertEqual(by_name["MAEZ_CODE_ONLY"]["sources"], ["code"])
        self.assertEqual(by_name["MAEZ_FILE_ONLY"]["sources"], ["env_file"])
        self.assertEqual(by_name["MAEZ_PROCESS_ONLY"]["sources"], ["process_env"])
        self.assertEqual(
            by_name["MAEZ_SHARED"]["sources"], ["env_file", "process_env"]
        )

    def test_owner_tier_artifact_exists_and_marks_review_gate(self):
        artifact = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "proof"
            / "2026-07-04-cockpit-flag-tier-table.md"
        )

        text = artifact.read_text(encoding="utf-8")

        self.assertIn("Owner-reviewed tier table", text)
        self.assertIn("Task 5 may use this table", text)
        self.assertIn("Unknown/unclassified flags are not writable", text)
        self.assertIn("MAEZ_LEDGER_WRITES", text)
        self.assertIn("S7_LIVE_WEBAUTHN_CEREMONY", text)
        self.assertIn("T3", text)


if __name__ == "__main__":
    unittest.main()
