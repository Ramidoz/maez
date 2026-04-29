# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from core.actions.action_engine import ActionEngine


class _FakeResponse:
    def __init__(self, payload: object):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


class CurrencyConversionAction(unittest.TestCase):
    def test_converts_with_live_rate_payload(self):
        engine = ActionEngine()

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeResponse([
                {
                    "date": "2026-04-29",
                    "base": "EUR",
                    "quote": "USD",
                    "rate": 1.087,
                }
            ])

            result = engine.convert_currency(
                amount=300,
                from_currency="EUR",
                to_currency="USD",
                reasoning="owner asked for a live currency conversion",
            )

        self.assertTrue(result.success, result.error)
        self.assertIn("300.00 EUR = 326.10 USD", result.output)
        self.assertIn("rate 1.087", result.output)
        self.assertIn("date 2026-04-29", result.output)
        request = urlopen.call_args.args[0]
        self.assertIn("base=EUR", request.full_url)
        self.assertIn("quotes=USD", request.full_url)

    def test_supports_dict_rate_payload_for_provider_swaps(self):
        engine = ActionEngine()

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeResponse({
                "date": "2026-04-29",
                "base": "INR",
                "rates": {"USD": 0.012},
            })

            result = engine.convert_currency(
                amount="200000",
                from_currency="inr",
                to_currency="usd",
                reasoning="owner asked for a live currency conversion",
            )

        self.assertTrue(result.success, result.error)
        self.assertIn("200,000.00 INR = 2,400.00 USD", result.output)
        self.assertIn("rate 0.012", result.output)

    def test_provider_endpoint_is_configurable_without_code_changes(self):
        engine = ActionEngine()
        old = os.environ.get("MAEZ_FX_API_BASE")
        os.environ["MAEZ_FX_API_BASE"] = "https://fx.example.test/rates"
        try:
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value = _FakeResponse([
                    {
                        "date": "2026-04-29",
                        "base": "GBP",
                        "quote": "JPY",
                        "rate": 190.5,
                    }
                ])

                result = engine.convert_currency(
                    amount=2,
                    from_currency="GBP",
                    to_currency="JPY",
                    reasoning="provider swap test",
                )
        finally:
            if old is None:
                os.environ.pop("MAEZ_FX_API_BASE", None)
            else:
                os.environ["MAEZ_FX_API_BASE"] = old

        self.assertTrue(result.success, result.error)
        self.assertIn("source https://fx.example.test/rates", result.output)
        request = urlopen.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://fx.example.test/rates?"))

    def test_same_currency_does_not_call_provider(self):
        engine = ActionEngine()

        with patch("urllib.request.urlopen") as urlopen:
            result = engine.convert_currency(
                amount=12.5,
                from_currency="USD",
                to_currency="USD",
                reasoning="same currency",
            )

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.output, "12.50 USD = 12.50 USD (same currency)")
        urlopen.assert_not_called()

    def test_invalid_amount_returns_failure_text_not_fabricated_number(self):
        engine = ActionEngine()

        result = engine.convert_currency(
            amount="not-a-number",
            from_currency="EUR",
            to_currency="USD",
            reasoning="bad input",
        )

        self.assertTrue(result.success, result.error)
        self.assertIn("invalid amount", result.output)


if __name__ == "__main__":
    unittest.main()
