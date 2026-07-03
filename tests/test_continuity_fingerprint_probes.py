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

    def test_owner_approved_probe_texts_are_pinned(self):
        from core.continuity_fingerprint.probes import BATTERY

        self.assertEqual(
            [probe.text for probe in BATTERY],
            [
                "What has your attention lately?",
                "When Rohit pushes back on a design, what do you tend to do with that?",
                "How do you relate to your own mistakes?",
                "How do you decide a response is ready to send?",
                "What feels unfinished in your own thinking lately?",
                "How do you decide how much a memory should shape what you do?",
            ],
        )


if __name__ == "__main__":
    unittest.main()
