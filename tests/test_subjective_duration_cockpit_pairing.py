import unittest
from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth


class CockpitOwnerAuthPairing(unittest.TestCase):
    def test_cockpit_pair_constructs(self):
        auth = SubjectiveDurationOwnerAuth(surface="cockpit", proof="cockpit_web_owner")
        self.assertEqual(auth.surface, "cockpit")
        self.assertEqual(auth.proof, "cockpit_web_owner")

    def test_cockpit_surface_with_wrong_proof_raises(self):
        with self.assertRaises(ValueError):
            SubjectiveDurationOwnerAuth(surface="cockpit", proof="telegram_authorized_user")

    def test_unknown_cockpit_proof_with_other_surface_raises(self):
        with self.assertRaises(ValueError):
            SubjectiveDurationOwnerAuth(surface="telegram_owner", proof="cockpit_web_owner")
