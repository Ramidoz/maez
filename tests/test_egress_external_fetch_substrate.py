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


class ExternalFetchRegistryTests(unittest.TestCase):
    def test_v1_registry_mapping_and_reserved_class_guard(self):
        from core.egress.external_fetch import build_fetch_registry

        registry = build_fetch_registry()

        self.assertEqual(registry.require_fetch_type("web_search").threat_model_class, "public_lookup")
        self.assertEqual(registry.require_fetch_type("search_rss").result_origin_class, "tool_result_public")
        self.assertEqual(registry.require_fetch_type("fetch_url").threat_model_class, "unknown_url_fetch")
        self.assertEqual(registry.require_fetch_type("fetch_url").result_origin_class, "unclassified")
        self.assertEqual(registry.require_fetch_type("currency_lookup").result_origin_class, "tool_result_public")
        self.assertEqual(registry.require_fetch_type("stock_lookup").result_origin_class, "tool_result_public")
        self.assertEqual(registry.reserved_instance_count(), 0)

        with self.assertRaises(ValueError):
            registry.register_fetch_type(
                "future_banking_api",
                threat_model_class="owner_private_api",
                result_origin_class="unclassified",
            )
        with self.assertRaises(ValueError):
            registry.register_fetch_type(
                "future_banking_api",
                threat_model_class="owner_private_api",
                result_origin_class="unclassified",
                spec_extension_acknowledged=True,
            )

        registry.register_fetch_type(
            "future_banking_api",
            threat_model_class="owner_private_api",
            result_origin_class="unclassified",
            spec_extension_acknowledged="docs/slices/example/spec.md@deadbeef",
        )
        entry = registry.require_fetch_type("future_banking_api")
        self.assertEqual(entry.spec_extension_acknowledged, "docs/slices/example/spec.md@deadbeef")


class ExternalFetchPreflightTests(unittest.TestCase):
    def test_preflight_refuses_forbidden_destinations_before_network(self):
        from core.egress.external_fetch import fetch_text

        def fail_opener(*_args, **_kwargs):
            raise AssertionError("HTTP opened before preflight refusal")

        cases = [
            ("http://127.0.0.1:8000", "preflight_refused_loopback"),
            ("http://localhost:8000", "preflight_refused_loopback"),
            ("http://[::1]:8000", "preflight_refused_loopback"),
            ("http://[::]:8000", "preflight_refused_loopback"),
            ("http://0.0.0.7", "preflight_refused_loopback"),
            ("http://10.0.0.1", "preflight_refused_private_range"),
            ("http://172.16.0.1", "preflight_refused_private_range"),
            ("http://192.168.1.1", "preflight_refused_private_range"),
            ("http://100.64.0.1", "preflight_refused_reserved_range"),
            ("http://255.255.255.255", "preflight_refused_reserved_range"),
            ("http://169.254.169.254", "preflight_refused_link_local"),
            ("http://[fe80::1]", "preflight_refused_link_local"),
            ("http://[fc00::1]", "preflight_refused_reserved_range"),
            ("http://[::ffff:127.0.0.1]", "preflight_refused_ipv4_mapped_ipv6"),
            ("ftp://example.com/file", "preflight_refused_scheme"),
            ("https://user:pass@example.com/", "preflight_refused_credentials"),
        ]
        for url, refusal_kind in cases:
            with self.subTest(url=url):
                result = fetch_text(
                    fetch_type="web_search",
                    url=url,
                    caller="test.preflight",
                    opener=fail_opener,
                    resolver=lambda _host: ["93.184.216.34"],
                )
                self.assertFalse(result.ok)
                self.assertEqual(result.decision, "block")
                self.assertEqual(result.preflight_status, "refused")
                self.assertEqual(result.preflight_refusal_kind, refusal_kind)
                self.assertIn(refusal_kind, result.reason_codes)

    def test_dns_multi_answer_and_rebinding_refuse_before_network(self):
        from core.egress.external_fetch import fetch_text

        def fail_opener(*_args, **_kwargs):
            raise AssertionError("HTTP opened before DNS refusal")

        mixed = fetch_text(
            fetch_type="web_search",
            url="https://mixed.example/search",
            caller="test.dns",
            opener=fail_opener,
            resolver=lambda _host: ["93.184.216.34", "127.0.0.1"],
        )
        self.assertFalse(mixed.ok)
        self.assertEqual(mixed.preflight_refusal_kind, "preflight_refused_dns_resolution")

        calls = []

        def rebinding_resolver(_host: str):
            calls.append(len(calls))
            if len(calls) == 1:
                return ["93.184.216.34"]
            return ["169.254.169.254"]

        rebound = fetch_text(
            fetch_type="web_search",
            url="https://rebind.example/search",
            caller="test.dns",
            opener=fail_opener,
            resolver=rebinding_resolver,
        )
        self.assertFalse(rebound.ok)
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(rebound.preflight_refusal_kind, "preflight_refused_dns_resolution")

    def test_redirect_target_is_preflighted_before_following(self):
        from core.egress.external_fetch import fetch_text

        opened = []

        class _RedirectResponse(_FakeResponse):
            def __init__(self, body: bytes):
                super().__init__(body, status=302)

            def getheader(self, name: str, default=None):
                return "http://127.0.0.1/metadata" if name.lower() == "location" else default

        def opener(request, **_kwargs):
            opened.append(request.full_url)
            return _RedirectResponse(b"")

        result = fetch_text(
            fetch_type="web_search",
            url="https://example.com/start",
            caller="test.redirect",
            opener=opener,
            resolver=lambda _host: ["93.184.216.34"],
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.preflight_refusal_kind, "preflight_refused_redirect_target")
        self.assertEqual(opened, ["https://example.com/start"])

    def test_non_get_and_unbounded_timeout_refuse_before_network(self):
        from core.egress.external_fetch import fetch_text

        def fail_opener(*_args, **_kwargs):
            raise AssertionError("HTTP opened for refused request")

        post = fetch_text(
            fetch_type="web_search",
            url="https://example.com/search",
            method="POST",
            caller="test.method",
            opener=fail_opener,
            resolver=lambda _host: ["93.184.216.34"],
        )
        self.assertFalse(post.ok)
        self.assertEqual(post.reason_codes, ("method_not_allowed",))

        for timeout in (None, 0, -1):
            with self.subTest(timeout=timeout):
                result = fetch_text(
                    fetch_type="web_search",
                    url="https://example.com/search",
                    caller="test.timeout",
                    timeout_s=timeout,
                    opener=fail_opener,
                    resolver=lambda _host: ["93.184.216.34"],
                )
                self.assertFalse(result.ok)
                self.assertEqual(result.reason_codes, ("invalid_timeout",))


class ExternalFetchRuntimeTests(unittest.TestCase):
    def test_successful_fetch_sets_fixed_user_agent_and_logs_non_reconstructive_row(self):
        from core.egress.external_fetch import fetch_text

        raw_url = "https://example.com/search?q=secret+query"
        raw_body = b"secret response body"
        seen_headers = {}

        def opener(request, **_kwargs):
            seen_headers.update(dict(request.header_items()))
            return _FakeResponse(raw_body)

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
                    fetch_type="web_search",
                    url=raw_url,
                    caller="test.runtime",
                    opener=opener,
                    resolver=lambda _host: ["93.184.216.34"],
                    headers={
                        "Accept-Language": "en-US",
                        "Authorization": "Bearer top-secret",
                    },
                )

            self.assertTrue(result.ok)
            self.assertEqual(result.result_origin_class, "tool_result_public")
            self.assertEqual(result.text, raw_body.decode())
            header_blob = "\n".join(f"{k}: {v}" for k, v in seen_headers.items())
            self.assertIn("MaezExternalFetch/1.0", header_blob)
            self.assertNotIn("Accept-Language", header_blob)
            self.assertNotIn("Authorization", header_blob)

            rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["schema_version"], "external-fetch-diagnostic-v1")
            self.assertEqual(row["fetch_type"], "web_search")
            self.assertEqual(row["threat_model_class"], "public_lookup")
            self.assertEqual(row["result_origin_class"], "tool_result_public")
            self.assertEqual(row["decision"], "allow")
            self.assertTrue(row["url_digest"].startswith("hmac-sha256:"))
            self.assertTrue(row["query_digest"].startswith("hmac-sha256:"))
            self.assertTrue(row["response_digest"].startswith("hmac-sha256:"))
            serialized = json.dumps(row, sort_keys=True)
            self.assertNotIn("secret query", serialized)
            self.assertNotIn("q=secret", serialized)
            self.assertNotIn("secret response body", serialized)
            self.assertNotIn("Bearer top-secret", serialized)

    def test_unknown_url_shadow_allows_but_records_would_block_reason(self):
        from core.egress.external_fetch import fetch_text

        result = fetch_text(
            fetch_type="fetch_url",
            url="https://example.com/readme",
            caller="test.fetch_url",
            opener=lambda *_args, **_kwargs: _FakeResponse(b"public page"),
            resolver=lambda _host: ["93.184.216.34"],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.decision, "would_block")
        self.assertEqual(result.result_origin_class, "unclassified")
        self.assertIn("would_block_unknown_url_fetch", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
