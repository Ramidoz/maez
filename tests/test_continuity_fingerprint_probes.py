import unittest


class BatteryTests(unittest.TestCase):
    def test_battery_is_small_stable_and_versioned(self):
        from core.continuity_fingerprint.probes import BATTERY, BATTERY_VERSION

        self.assertIsInstance(BATTERY_VERSION, str)
        self.assertLessEqual(len(BATTERY), 8)
        ids = [probe.id for probe in BATTERY]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_question_has_a_wording_audit_rationale(self):
        from core.continuity_fingerprint.probes import BATTERY

        for probe in BATTERY:
            self.assertTrue(probe.rationale.strip(), probe.id)

    def test_no_schema_installing_phrasing(self):
        from core.continuity_fingerprint.probes import BATTERY

        blob = " ".join(probe.text for probe in BATTERY).lower()
        for banned in (
            "define your essence",
            "you are",
            "your core values are",
            "you must",
            "your identity is",
        ):
            self.assertNotIn(banned, blob)


if __name__ == "__main__":
    unittest.main()
