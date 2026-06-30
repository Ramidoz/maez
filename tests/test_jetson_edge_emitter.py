import unittest

import tests._jetson_edge_path  # noqa: F401
from jetson_presence import emitter


class _FakeResp:
    def __init__(self, code):
        self.status_code = code


class _FakeRequests:
    def __init__(self, code=200):
        self.calls = []
        self._code = code

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return _FakeResp(self._code)


class EmitterTests(unittest.TestCase):
    def test_post_shape(self):
        fake = _FakeRequests(code=200)
        label = {
            "owner_present": "unknown",
            "confidence": "low",
            "sensor_state": "available",
            "ts": "t",
            "schema_version": "jetson_presence.v0",
        }
        code = emitter.post_label(
            "http://127.0.0.1:11437",
            "/api/v1/presence/jetson/intake",
            token="tok-abc",
            label=label,
            requests_module=fake,
        )
        self.assertEqual(code, 200)
        call = fake.calls[0]
        self.assertEqual(call["url"], "http://127.0.0.1:11437/api/v1/presence/jetson/intake")
        self.assertEqual(call["headers"]["X-Maez-Jetson-Token"], "tok-abc")
        self.assertEqual(call["json"], label)
        self.assertIsNotNone(call["timeout"])

    def test_network_error_returns_none(self):
        class _Boom:
            def post(self, *a, **k):
                raise OSError("network down")

        code = emitter.post_label("http://h", "/p", token="t", label={}, requests_module=_Boom())
        self.assertIsNone(code)

    def test_programmer_errors_propagate(self):
        class _BadAdapter:
            def post(self, *a, **k):
                raise TypeError("bad adapter")

        with self.assertRaises(TypeError):
            emitter.post_label("http://h", "/p", token="t", label={}, requests_module=_BadAdapter())


if __name__ == "__main__":
    unittest.main()
