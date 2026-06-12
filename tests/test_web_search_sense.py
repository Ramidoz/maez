from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.dispatcher.external_sources import _latest_diagnostic_id_after
from core.egress import external_fetch
from core.policies.third_party_subject_gate import SubjectKind
from core.search.searxng_client import FakeSearchBackend, SearxngBackend


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self, *_args):
        return self._body

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _Env(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None))
        # search() caches results module-globally; isolate every test.
        import skills.web_search as ws

        ws._cache.clear()
        self.addCleanup(ws._cache.clear)


class SenseFlagTests(_Env):
    def test_flag_off_never_touches_searxng(self):
        import skills.web_search as ws

        with mock.patch.object(
            ws,
            "_sense_backend",
            side_effect=AssertionError("flag off must not build a backend"),
        ):
            with mock.patch.object(
                ws,
                "_ddg_search",
                return_value={
                    "query": "q",
                    "success": True,
                    "results": [],
                    "source": "duckduckgo",
                },
            ) as ddg:
                out = ws.search("q")
        self.assertEqual(out["source"], "duckduckgo")
        ddg.assert_called_once()

    def test_flag_on_routes_to_searxng_contract_shape(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws

        fake = FakeSearchBackend(
            results=[{"title": "T", "url": "U", "content": "C"}]
        )
        with mock.patch.object(ws, "_sense_backend", return_value=fake):
            out = ws.search("llama.cpp release", max_results=3)
        self.assertTrue(out["success"])
        self.assertEqual(out["source"], "searxng")
        self.assertEqual(
            out["results"][0], {"title": "T", "url": "U", "snippet": "C"}
        )
        self.assertEqual(fake.searched, ["llama.cpp release"])

    def test_searxng_sense_path_records_dispatcher_visible_egress_diagnostic(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "external_fetch.jsonl"
            os.environ["MAEZ_EXTERNAL_FETCH_LOG"] = str(log_path)
            self.addCleanup(lambda: os.environ.pop("MAEZ_EXTERNAL_FETCH_LOG", None))
            start_offset = log_path.stat().st_size if log_path.exists() else 0

            def opener(_req, timeout=None):
                return _FakeResponse(
                    {
                        "results": [
                            {"title": "T", "url": "https://example.com/t", "content": "C"}
                        ]
                    }
                )

            backend = SearxngBackend(
                base_url="http://127.0.0.1:8888",
                opener=opener,
                resolver=lambda _host: ["127.0.0.1"],
            )
            with mock.patch.object(ws, "_sense_backend", return_value=backend):
                out = ws.search("llama.cpp release", max_results=3)

            self.assertTrue(out["success"])
            diagnostic_id = _latest_diagnostic_id_after(
                log_path=external_fetch._diagnostic_path(),
                start_offset=start_offset,
                caller_prefix="skills.web_search.",
            )
            self.assertTrue(diagnostic_id)

    def test_flag_on_empty_results_is_honest_failure(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws

        with mock.patch.object(
            ws, "_sense_backend", return_value=FakeSearchBackend(results=[])
        ):
            out = ws.search("nothing")
        self.assertFalse(out["success"])
        self.assertEqual(out["results"], [])

    def test_flag_on_backend_exception_is_honest_failure(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws

        with mock.patch.object(
            ws,
            "_sense_backend",
            return_value=FakeSearchBackend(raises=RuntimeError("down")),
        ):
            out = ws.search("boom")
        self.assertFalse(out["success"])


class PreEgressRefusalTests(_Env):
    def test_named_third_party_refused_before_any_backend_call(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws

        fake = FakeSearchBackend()
        with mock.patch.object(ws, "_sense_backend", return_value=fake):
            out = ws.search(
                "John Smith my coworker",
                subject_kind=SubjectKind.NAMED_THIRD_PARTY,
            )
        self.assertFalse(out["success"])
        self.assertEqual(out.get("refused"), "subject_boundary")
        self.assertEqual(fake.searched, [])  # ZERO egress

    def test_unknown_subject_refused(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws

        fake = FakeSearchBackend()
        with mock.patch.object(ws, "_sense_backend", return_value=fake):
            out = ws.search("???", subject_kind=SubjectKind.UNKNOWN)
        self.assertEqual(out.get("refused"), "subject_boundary")
        self.assertEqual(fake.searched, [])

    def test_default_subject_kind_is_public_topic_and_allowed(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws

        fake = FakeSearchBackend(
            results=[{"title": "t", "url": "u", "content": "c"}]
        )
        with mock.patch.object(ws, "_sense_backend", return_value=fake):
            out = ws.search("latest llama.cpp")
        self.assertTrue(out["success"])


if __name__ == "__main__":
    unittest.main()
