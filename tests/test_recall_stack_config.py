import unittest

from core.routing.recall_stack_config import RecallMode, resolve_recall_stack


class ResolveRecallStackTest(unittest.TestCase):
    def test_bundle_on_yields_triad_regardless_of_raw(self):
        raw_cases = (
            {},
            {"MAEZ_DISPATCHER_ENABLED": "1"},
            {
                "MAEZ_DISPATCHER_ENABLED": "1",
                "MAEZ_FOCUSED_COGNITION_ENABLED": "1",
                "MAEZ_LIVING_RECALL_ENABLED": "1",
            },
        )
        for raw in raw_cases:
            cfg = resolve_recall_stack(
                env={"MAEZ_RECALL_TRIAD_ENABLED": "1", **raw}
            )
            self.assertIs(cfg.mode, RecallMode.TRIAD)
            self.assertEqual(cfg.reason, "bundle_enabled")
            self.assertTrue(cfg.triad_on)
            self.assertTrue(cfg.carrier_available)

    def test_all_off_is_legacy_off(self):
        cfg = resolve_recall_stack(env={})
        self.assertIs(cfg.mode, RecallMode.LEGACY)
        self.assertEqual(cfg.reason, "off")
        self.assertFalse(cfg.triad_on)
        self.assertFalse(cfg.carrier_available)

    def test_raw_flags_without_bundle_are_inert_legacy_with_named_reason(self):
        cases = {
            ("MAEZ_DISPATCHER_ENABLED",):
                "legacy_raw_flags_ignored:MAEZ_DISPATCHER_ENABLED",
            ("MAEZ_FOCUSED_COGNITION_ENABLED",):
                "legacy_raw_flags_ignored:MAEZ_FOCUSED_COGNITION_ENABLED",
            ("MAEZ_LIVING_RECALL_ENABLED",):
                "legacy_raw_flags_ignored:MAEZ_LIVING_RECALL_ENABLED",
            ("MAEZ_DISPATCHER_ENABLED", "MAEZ_FOCUSED_COGNITION_ENABLED"):
                "legacy_raw_flags_ignored:MAEZ_DISPATCHER_ENABLED,"
                "MAEZ_FOCUSED_COGNITION_ENABLED",
            ("MAEZ_DISPATCHER_ENABLED", "MAEZ_LIVING_RECALL_ENABLED"):
                "legacy_raw_flags_ignored:MAEZ_DISPATCHER_ENABLED,"
                "MAEZ_LIVING_RECALL_ENABLED",
            ("MAEZ_FOCUSED_COGNITION_ENABLED", "MAEZ_LIVING_RECALL_ENABLED"):
                "legacy_raw_flags_ignored:MAEZ_FOCUSED_COGNITION_ENABLED,"
                "MAEZ_LIVING_RECALL_ENABLED",
            (
                "MAEZ_DISPATCHER_ENABLED",
                "MAEZ_FOCUSED_COGNITION_ENABLED",
                "MAEZ_LIVING_RECALL_ENABLED",
            ):
                "legacy_raw_flags_ignored:MAEZ_DISPATCHER_ENABLED,"
                "MAEZ_FOCUSED_COGNITION_ENABLED,MAEZ_LIVING_RECALL_ENABLED",
        }
        for names, expected_reason in cases.items():
            env = {name: "1" for name in names}
            cfg = resolve_recall_stack(env=env)
            self.assertIs(cfg.mode, RecallMode.LEGACY)
            self.assertEqual(cfg.reason, expected_reason)
            self.assertFalse(cfg.triad_on)

    def test_truthiness_is_tolerant_for_bundle(self):
        for value in ("1", " 1", "TRUE", "true", "Yes", "  yes "):
            cfg = resolve_recall_stack(env={"MAEZ_RECALL_TRIAD_ENABLED": value})
            self.assertIs(cfg.mode, RecallMode.TRIAD, value)

    def test_falsey_bundle_values_do_not_enable(self):
        for value in ("0", "", "no", "false", "off"):
            cfg = resolve_recall_stack(env={"MAEZ_RECALL_TRIAD_ENABLED": value})
            self.assertIs(cfg.mode, RecallMode.LEGACY, value)

    def test_carrier_available_tracks_triad_on_in_every_branch(self):
        for env in (
            {},
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
            {"MAEZ_DISPATCHER_ENABLED": "1"},
        ):
            cfg = resolve_recall_stack(env=env)
            self.assertEqual(cfg.carrier_available, cfg.triad_on)


if __name__ == "__main__":
    unittest.main()
