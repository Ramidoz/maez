from __future__ import annotations

import os
import unittest
from unittest import mock

from core.policies.third_party_subject_gate import SubjectKind
from core.search.searxng_client import FakeSearchBackend


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
