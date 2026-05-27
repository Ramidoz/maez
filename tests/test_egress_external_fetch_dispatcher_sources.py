from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self, *_args):
        return self._body

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class DispatcherExternalFetchSourceTests(unittest.TestCase):
    def test_external_fetch_registry_has_live_reddit_public_lookup(self):
        from core.egress.external_fetch import build_fetch_registry

        entry = build_fetch_registry().require_fetch_type("live_reddit")

        self.assertEqual(entry.threat_model_class, "public_lookup")
        self.assertEqual(entry.result_origin_class, "tool_result_public")

    def test_external_fetch_registry_has_arxiv_public_lookup(self):
        from core.egress.external_fetch import build_fetch_registry

        entry = build_fetch_registry().require_fetch_type("arxiv")

        self.assertEqual(entry.threat_model_class, "public_lookup")
        self.assertEqual(entry.result_origin_class, "tool_result_public")

    def test_live_reddit_fetch_type_allows_public_lookup_diagnostics(self):
        self._assert_dispatcher_fetch_type_logs_public_lookup("live_reddit")

    def test_arxiv_fetch_type_allows_public_lookup_diagnostics(self):
        self._assert_dispatcher_fetch_type_logs_public_lookup("arxiv")

    def _assert_dispatcher_fetch_type_logs_public_lookup(self, fetch_type: str) -> None:
        from core.egress.external_fetch import fetch_text

        seen_headers = {}

        def opener(request, **_kwargs):
            seen_headers.update(dict(request.header_items()))
            return _FakeResponse(b"public dispatcher result")

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "external_fetch.jsonl"
            with mock.patch.dict(
                "os.environ",
                {
                    "MAEZ_EXTERNAL_FETCH_LOG": str(log_path),
                    "MAEZ_EGRESS_TELEMETRY_KEY": "test-key",
                },
                clear=False,
            ):
                result = fetch_text(
                    fetch_type=fetch_type,
                    url="https://example.com/search?q=secret+query",
                    caller="test.dispatcher_external_source",
                    opener=opener,
                    resolver=lambda _host: ["93.184.216.34"],
                    headers={
                        "Accept-Language": "en-US",
                        "Authorization": "Bearer top-secret",
                    },
                )

            rows = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertTrue(result.ok)
        self.assertEqual(result.decision, "allow")
        self.assertEqual(result.threat_model_class, "public_lookup")
        self.assertEqual(result.result_origin_class, "tool_result_public")
        self.assertEqual(result.reason_codes, ("public_lookup_allowed",))

        header_blob = "\n".join(f"{key}: {value}" for key, value in seen_headers.items())
        self.assertIn("MaezExternalFetch/1.0", header_blob)
        self.assertNotIn("Accept-Language", header_blob)
        self.assertNotIn("Authorization", header_blob)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["schema_version"], "external-fetch-diagnostic-v1")
        self.assertEqual(row["fetch_type"], fetch_type)
        self.assertEqual(row["threat_model_class"], "public_lookup")
        self.assertEqual(row["result_origin_class"], "tool_result_public")
        self.assertEqual(row["decision"], "allow")
        self.assertTrue(row["request_id"])
        self.assertTrue(row["url_digest"].startswith("hmac-sha256:"))
        self.assertTrue(row["query_digest"].startswith("hmac-sha256:"))
        serialized = json.dumps(row, sort_keys=True)
        self.assertNotIn("secret query", serialized)
        self.assertNotIn("q=secret", serialized)
        self.assertNotIn("Bearer top-secret", serialized)


if __name__ == "__main__":
    unittest.main()
