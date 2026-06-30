import unittest
import tests._jetson_edge_path  # noqa: F401  (path side-effect)
from jetson_presence import labels


class LabelRuleTests(unittest.TestCase):
    def test_available_is_unknown_low(self):
        lab = labels.build_label("available", "2026-06-30T12:00:00+00:00")
        self.assertEqual(lab["owner_present"], "unknown")
        self.assertEqual(lab["confidence"], "low")
        self.assertEqual(lab["sensor_state"], "available")
        self.assertEqual(lab["ts"], "2026-06-30T12:00:00+00:00")
        self.assertEqual(lab["schema_version"], "jetson_presence.v0")

    def test_curtained_and_unavailable_still_unknown_low(self):
        for state in ("curtained", "unavailable", "error"):
            lab = labels.build_label(state, "t")
            self.assertEqual(lab["owner_present"], "unknown")
            self.assertEqual(lab["confidence"], "low")
            self.assertEqual(lab["sensor_state"], state)

    def test_b0_never_emits_present_or_absent(self):
        for state in ("available", "curtained", "unavailable", "error", "unenrolled"):
            self.assertEqual(labels.build_label(state, "t")["owner_present"], "unknown")

    def test_rejects_unknown_sensor_state(self):
        with self.assertRaises(ValueError):
            labels.build_label("teleporting", "t")

    def test_exact_five_keys(self):
        self.assertEqual(
            set(labels.build_label("available", "t").keys()),
            {"owner_present", "confidence", "sensor_state", "ts", "schema_version"},
        )


class ContractDriftTests(unittest.TestCase):
    def test_schema_version_matches_host(self):
        from core.body import jetson_presence as host

        self.assertEqual(labels.SCHEMA_VERSION, host.SCHEMA_VERSION)

    def test_sensor_states_match_host_wire_enum(self):
        from core.body import jetson_presence as host

        self.assertEqual(labels.SENSOR_STATES, host._SENSOR_STATE_WIRE)

    def test_label_keys_match_host_allowed_keys(self):
        from core.body import jetson_presence as host

        self.assertEqual(set(labels.build_label("available", "t").keys()), host._ALLOWED_KEYS)

    def test_fixed_owner_present_and_confidence_are_host_valid(self):
        from core.body import jetson_presence as host

        self.assertIn(labels.FIXED_OWNER_PRESENT, host._OWNER_PRESENT)
        self.assertIn(labels.FIXED_CONFIDENCE, host._CONFIDENCE)


if __name__ == "__main__":
    unittest.main()
