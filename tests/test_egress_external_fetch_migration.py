from __future__ import annotations

import unittest
from unittest import mock


class _FetchResult:
    def __init__(self, text: str, *, ok: bool = True):
        self.text = text
        self.ok = ok
        self.decision = "allow" if ok else "block"
        self.reason_codes = ("test",)
        self.status_code = 200 if ok else None
        self.result_origin_class = "tool_result_public"


class ExternalFetchMigrationTests(unittest.TestCase):
    def setUp(self):
        from skills import web_search

        web_search._cache.clear()

    def test_web_search_search_uses_external_fetch_for_instant_and_html_paths(self):
        from skills import web_search

        instant = _FetchResult("{}")
        html = _FetchResult(
            '<a class="result__snippet">A useful snippet</a>'
            '<a class="result__a">A useful title</a>'
            '<span class="result__url">example.com/page</span>'
        )
        with mock.patch("core.egress.external_fetch.fetch_text", side_effect=[instant, html]) as fetch:
            result = web_search.search("maez external fetch", max_results=1)

        self.assertTrue(result["success"])
        self.assertEqual(result["results"][0]["title"], "A useful title")
        self.assertEqual([call.kwargs["fetch_type"] for call in fetch.call_args_list], ["web_search", "web_search"])
        self.assertTrue(all(call.kwargs["caller"].startswith("skills.web_search.") for call in fetch.call_args_list))

    def test_search_rss_uses_search_rss_fetch_type(self):
        from skills import web_search

        rss = _FetchResult(
            b"""<?xml version='1.0'?>
            <rss><channel><item><title>Headline</title><description>Story</description>
            <link>https://example.com/story</link><pubDate>today</pubDate></item></channel></rss>""".decode()
        )
        with mock.patch("core.egress.external_fetch.fetch_text", return_value=rss) as fetch:
            result = web_search.search_rss("general", max_results=1)

        self.assertTrue(result["success"])
        self.assertEqual(result["results"][0]["title"], "Headline")
        self.assertEqual(fetch.call_args.kwargs["fetch_type"], "search_rss")
        self.assertEqual(fetch.call_args.kwargs["caller"], "skills.web_search.search_rss")

    def test_action_engine_live_data_methods_use_external_fetch_types(self):
        from core.actions.action_engine import ActionEngine

        engine = ActionEngine()
        responses = [
            _FetchResult("<html><body><p>Fetched page text</p></body></html>"),
            _FetchResult('{"amount":1,"base":"USD","date":"2026-05-24","rates":{"INR":83.25}}'),
            _FetchResult("Symbol,Date,Time,Open,High,Low,Close,Volume\nAAPL.US,2026-05-24,10:00,1,2,1,199.50,1000\n"),
        ]

        with mock.patch("core.egress.external_fetch.fetch_text", side_effect=responses) as fetch:
            fetched = engine._do_fetch_url("https://example.com/page", max_chars=100)
            converted = engine._do_convert_currency(amount=2, from_currency="USD", to_currency="INR")
            quoted = engine._do_quote_stock(symbol="AAPL")

        self.assertIn("Fetched page text", fetched)
        self.assertIn("166.50 INR", converted)
        self.assertIn("AAPL.US = 199.50 USD", quoted)
        self.assertEqual(
            [call.kwargs["fetch_type"] for call in fetch.call_args_list],
            ["fetch_url", "currency_lookup", "stock_lookup"],
        )


if __name__ == "__main__":
    unittest.main()
