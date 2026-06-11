import unittest
from unittest import mock

from core.cognition.support_verifier import (
    HttpSupportVerifier,
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


class HttpSupportVerifierTests(unittest.TestCase):
    def _resp(self, payload):
        r = mock.Mock()
        r.json.return_value = payload
        r.raise_for_status.return_value = None
        return r

    def test_supported(self):
        v = HttpSupportVerifier(url="http://127.0.0.1:8083")
        with mock.patch(
            "core.cognition.support_verifier.httpx.post",
            return_value=self._resp({"verdict": "SUPPORTED", "score": 0.9}),
        ) as p:
            label, score, _ = v.support("ev", "claim", 0.25)
        self.assertEqual(label, SUPPORTED)
        self.assertEqual(score, 0.9)
        self.assertEqual(p.call_args.kwargs["timeout"], 0.25)

    def test_unsupported(self):
        v = HttpSupportVerifier()
        with mock.patch(
            "core.cognition.support_verifier.httpx.post",
            return_value=self._resp({"verdict": "UNSUPPORTED", "score": 0.2}),
        ):
            self.assertEqual(v.support("ev", "claim", 0.25)[0], UNSUPPORTED)

    def test_transport_error_returns_unavailable(self):
        v = HttpSupportVerifier()
        with mock.patch(
            "core.cognition.support_verifier.httpx.post",
            side_effect=Exception("connection refused"),
        ):
            label, score, _ = v.support("ev", "claim", 0.25)
        self.assertEqual(label, UNAVAILABLE)
        self.assertIsNone(score)

    def test_never_raises(self):
        v = HttpSupportVerifier()
        with mock.patch(
            "core.cognition.support_verifier.httpx.post",
            side_effect=Exception("boom"),
        ):
            try:
                v.support("ev", "claim", 0.25)
            except Exception:  # noqa: BLE001
                self.fail("HttpSupportVerifier.support must never raise")


if __name__ == "__main__":
    unittest.main()
