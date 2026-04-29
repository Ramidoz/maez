# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.actions.action_engine import ActionEngine


class _FakeResponse:
    def __init__(self, text: str):
        self._body = text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return self._body


class StockQuoteAction(unittest.TestCase):
    def test_quotes_stock_from_structured_csv(self):
        engine = ActionEngine()
        csv = (
            "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
            "SRXH.US,2026-04-29,18:03:11,0.117,0.1189,0.1107,0.1135,13640200\n"
        )

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeResponse(csv)
            result = engine.quote_stock(
                symbol="SRXH",
                reasoning="owner asked for the current stock price",
            )

        self.assertTrue(result.success, result.error)
        self.assertIn("SRXH.US = 0.1135 USD", result.output)
        self.assertIn("as of 2026-04-29 18:03:11", result.output)
        self.assertIn("volume 13640200", result.output)
        request = urlopen.call_args.args[0]
        self.assertIn("s=srxh.us", request.full_url)

    def test_provider_template_is_configurable_without_code_changes(self):
        engine = ActionEngine()
        old = os.environ.get("MAEZ_STOCK_QUOTE_URL_TEMPLATE")
        os.environ["MAEZ_STOCK_QUOTE_URL_TEMPLATE"] = (
            "https://quotes.example.test/current?symbol={symbol}"
        )
        try:
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value = _FakeResponse(
                    "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
                    "AAPL.US,2026-04-29,18:03:11,200,201,199,200.5,100\n"
                )
                result = engine.quote_stock(
                    symbol="AAPL",
                    reasoning="provider template test",
                )
        finally:
            if old is None:
                os.environ.pop("MAEZ_STOCK_QUOTE_URL_TEMPLATE", None)
            else:
                os.environ["MAEZ_STOCK_QUOTE_URL_TEMPLATE"] = old

        self.assertTrue(result.success, result.error)
        self.assertIn("AAPL.US = 200.5 USD", result.output)
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://quotes.example.test/current?symbol=aapl.us",
        )

    def test_invalid_symbol_does_not_hit_provider(self):
        engine = ActionEngine()

        with patch("urllib.request.urlopen") as urlopen:
            result = engine.quote_stock(
                symbol="SRXH; rm -rf /",
                reasoning="bad symbol",
            )

        self.assertTrue(result.success, result.error)
        self.assertIn("invalid stock symbol", result.output)
        urlopen.assert_not_called()

    def test_no_price_returns_error_text_not_fake_quote(self):
        engine = ActionEngine()

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeResponse(
                "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
                "NOPE.US,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n"
            )
            result = engine.quote_stock(
                symbol="NOPE",
                reasoning="missing quote",
            )

        self.assertTrue(result.success, result.error)
        self.assertIn("stock quote error: no current price", result.output)


if __name__ == "__main__":
    unittest.main()
