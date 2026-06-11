import unittest
from unittest import mock

from core.search.searxng_client import (
    SearchBackend, FakeSearchBackend, SearxngBackend, HEALTHY, DEGRADED, DOWN,
)


class FakeBackendTests(unittest.TestCase):
    def test_interface_is_abstract(self):
        with self.assertRaises(TypeError):
            SearchBackend()

    def test_returns_scripted_results_and_records_query(self):
        b = FakeSearchBackend(results=[{"title": "T", "url": "U", "content": "C"}])
        out = b.search("llama.cpp")
        self.assertEqual(out[0]["title"], "T")
        self.assertEqual(b.searched, ["llama.cpp"])

    def test_health_is_scriptable(self):
        self.assertEqual(FakeSearchBackend(health="degraded").health(), "degraded")

    def test_search_can_raise(self):
        with self.assertRaises(RuntimeError):
            FakeSearchBackend(raises=RuntimeError("boom")).search("q")


class SearxngBackendTests(unittest.TestCase):
    def _resp(self, payload, status=200):
        r = mock.Mock()
        r.status_code = status
        r.json.return_value = payload
        r.raise_for_status.return_value = None
        return r

    def test_search_normalizes_results(self):
        b = SearxngBackend()
        payload = {"results": [{"title": "T", "url": "U", "content": "C", "engine": "brave"}]}
        with mock.patch("core.search.searxng_client.httpx.get", return_value=self._resp(payload)):
            out = b.search("llama.cpp", max_results=8)
        self.assertEqual(out, [{"title": "T", "url": "U", "content": "C"}])

    def test_health_healthy_when_results(self):
        b = SearxngBackend()
        with mock.patch("core.search.searxng_client.httpx.get",
                        return_value=self._resp({"results": [{"title": "x"}], "unresponsive_engines": []})):
            self.assertEqual(b.health(), HEALTHY)

    def test_health_degraded_when_no_results(self):
        b = SearxngBackend()
        with mock.patch("core.search.searxng_client.httpx.get",
                        return_value=self._resp({"results": [], "unresponsive_engines": [["x", "captcha"]]})):
            self.assertEqual(b.health(), DEGRADED)

    def test_health_down_on_transport_error(self):
        b = SearxngBackend()
        with mock.patch("core.search.searxng_client.httpx.get", side_effect=Exception("refused")):
            self.assertEqual(b.health(), DOWN)


if __name__ == "__main__":
    unittest.main()
