#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Rohit Ananthan

import unittest

from skills.web_search import needs_web_search


class LiveDataSearchTriggers(unittest.TestCase):
    def test_currency_questions_need_live_search(self):
        for text in (
            "What's Rs.2,00,000 in USD?",
            "What is the current INR to USD exchange rate?",
            "Convert ₹200000 to dollars today",
            "What is 300 euros in usd?",
            "What is €300 in dollars?",
            "Convert 20 pounds to yen",
        ):
            with self.subTest(text=text):
                self.assertTrue(needs_web_search(text))


if __name__ == "__main__":
    unittest.main()
