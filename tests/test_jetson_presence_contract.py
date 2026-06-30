# tests/test_jetson_presence_contract.py
import unittest
from core.body.jetson_presence import JetsonPresenceReading, parse_label


class ParseLabelTests(unittest.TestCase):
    def _valid(self) -> dict:
        return {
            "owner_present": "present",
            "confidence": "high",
            "sensor_state": "available",
            "ts": "2026-06-29T19:00:00+00:00",
            "schema_version": "jetson_presence.v0",
        }

    def test_valid_label_parses(self):
        r = parse_label(self._valid())
        self.assertIsInstance(r, JetsonPresenceReading)
        self.assertEqual(r.owner_present, "present")
        self.assertEqual(r.confidence, "high")
        self.assertEqual(r.sensor_state, "available")
        self.assertEqual(r.observed_at, "2026-06-29T19:00:00+00:00")

    def test_bad_owner_present_enum_rejected(self):
        bad = self._valid() | {"owner_present": "maybe"}
        self.assertIsNone(parse_label(bad))

    def test_bad_sensor_state_enum_rejected(self):
        bad = self._valid() | {"sensor_state": "stale"}  # host-derived only, not wire-valid
        self.assertIsNone(parse_label(bad))

    def test_missing_field_rejected(self):
        bad = self._valid()
        del bad["confidence"]
        self.assertIsNone(parse_label(bad))

    def test_wrong_schema_version_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"schema_version": "jetson_presence.v9"}))

    def test_non_dict_rejected(self):
        self.assertIsNone(parse_label(None))
        self.assertIsNone(parse_label("present"))

    # Cross-field consistency: present/absent require sensor_state == available.
    def test_present_with_error_sensor_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"owner_present": "present", "sensor_state": "error"}))

    def test_absent_with_curtained_sensor_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"owner_present": "absent", "sensor_state": "curtained"}))

    def test_present_with_unenrolled_sensor_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"owner_present": "present", "sensor_state": "unenrolled"}))

    def test_present_with_unavailable_sensor_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"owner_present": "present", "sensor_state": "unavailable"}))

    def test_unknown_with_curtained_sensor_allowed(self):
        r = parse_label(self._valid() | {"owner_present": "unknown", "sensor_state": "curtained"})
        self.assertIsNotNone(r)
        self.assertEqual((r.owner_present, r.sensor_state), ("unknown", "curtained"))

    def test_present_with_available_sensor_allowed(self):
        r = parse_label(self._valid() | {"owner_present": "present", "sensor_state": "available"})
        self.assertIsNotNone(r)


if __name__ == "__main__":
    unittest.main()
