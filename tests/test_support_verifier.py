import unittest

from core.cognition.support_verifier import (
    SUPPORTED,
    UNAVAILABLE,
    UNSUPPORTED,
    FakeSupportVerifier,
    SupportVerifier,
)


class FakeSupportVerifierTests(unittest.TestCase):
    def test_interface_is_abstract(self):
        with self.assertRaises(TypeError):
            SupportVerifier()

    def test_scripted_verdict(self):
        v = FakeSupportVerifier(scripted={"the sky is green": (UNSUPPORTED, 0.1)})
        label, score, latency = v.support("ev", "the sky is green", 0.25)
        self.assertEqual(label, UNSUPPORTED)
        self.assertEqual(score, 0.1)
        self.assertGreaterEqual(latency, 0.0)

    def test_default_verdict(self):
        v = FakeSupportVerifier(default=(SUPPORTED, 0.99))
        self.assertEqual(v.support("ev", "anything", 0.25)[0], SUPPORTED)

    def test_records_calls(self):
        v = FakeSupportVerifier()
        v.support("ev1", "claim1", 0.25)
        self.assertEqual(v.calls, [("ev1", "claim1")])

    def test_can_raise(self):
        v = FakeSupportVerifier(raises=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            v.support("ev", "claim", 0.25)


if __name__ == "__main__":
    unittest.main()
