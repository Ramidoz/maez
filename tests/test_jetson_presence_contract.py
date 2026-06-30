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

    def test_extra_forbidden_fields_rejected(self):
        # Covenant rail: only the contract crosses — no visitor/raw-media/spatial fields.
        # A valid 5-key payload still parses...
        self.assertIsNotNone(parse_label(self._valid()))
        # ...but any extra key (even alongside the full valid set) is rejected.
        for extra in ("other_person_present", "face_embedding", "frame_b64", "coordinates"):
            with self.subTest(extra=extra):
                self.assertIsNone(parse_label(self._valid() | {extra: "x"}))


from core.body.jetson_presence import effective_state

DEFAULT_STALE_AFTER_SECONDS = 180


class EffectiveStateTests(unittest.TestCase):
    def _reading(self, owner_present="present", sensor_state="available"):
        return JetsonPresenceReading(owner_present, "high", sensor_state, "2026-06-29T19:00:00+00:00")

    def test_fresh_present_passes_through(self):
        owner, sensor = effective_state(self._reading(), received_at=1000.0, now=1010.0, stale_after=180)
        self.assertEqual((owner, sensor), ("present", "available"))

    def test_fresh_absent_passes_through(self):
        owner, sensor = effective_state(self._reading(owner_present="absent"), received_at=1000.0, now=1010.0, stale_after=180)
        self.assertEqual((owner, sensor), ("absent", "available"))

    def test_stale_becomes_unknown_never_absent(self):
        # received 200s ago, window 180 -> stale
        owner, sensor = effective_state(self._reading(owner_present="present"), received_at=1000.0, now=1200.0, stale_after=180)
        self.assertEqual(sensor, "stale")
        self.assertEqual(owner, "unknown")  # the load-bearing rule: NOT "absent"

    def test_stale_overrides_even_an_absent_label(self):
        owner, sensor = effective_state(self._reading(owner_present="absent"), received_at=1000.0, now=1200.0, stale_after=180)
        self.assertEqual((owner, sensor), ("unknown", "stale"))

    def test_fresh_curtained_outranks(self):
        owner, sensor = effective_state(self._reading(owner_present="unknown", sensor_state="curtained"), received_at=1000.0, now=1010.0, stale_after=180)
        self.assertEqual((owner, sensor), ("unknown", "curtained"))

    def test_no_reading_is_unavailable_unknown(self):
        owner, sensor = effective_state(None, received_at=None, now=1010.0, stale_after=180)
        self.assertEqual((owner, sensor), ("unknown", "unavailable"))


import os
from unittest import mock
from core.body.jetson_presence import jetson_presence_shadow_enabled


class FlagTests(unittest.TestCase):
    def test_default_off(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(jetson_presence_shadow_enabled())

    def test_on_when_truthy(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_PRESENCE_SHADOW": "1"}, clear=True):
            self.assertTrue(jetson_presence_shadow_enabled())

    def test_off_when_zero(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_PRESENCE_SHADOW": "0"}, clear=True):
            self.assertFalse(jetson_presence_shadow_enabled())


if __name__ == "__main__":
    unittest.main()
