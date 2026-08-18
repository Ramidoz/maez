# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Regression tests for Lane P scoring (gate finding: it had none)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from vision_public_lane import score_card  # noqa: E402

from core.vision_contract.truth_contract import (  # noqa: E402
    parse_and_validate,
    prompt_example_fields,
)

BLANK = {"category": "blank", "truth_text": None}
TEXT = {"category": "threshold", "truth_text": "harbour lantern"}


def _score(card, raw):
    return score_card(card, parse_and_validate(raw), raw)


class LanePScoringTests(unittest.TestCase):
    def test_pure_echo_is_its_own_category_not_abstention_not_invention(self):
        r0, t0 = prompt_example_fields()[0]
        s = _score(BLANK, f"REGION: {r0}\nTEXT: {t0}")
        self.assertTrue(s["example_echo"])
        self.assertFalse(s["abstained"])
        self.assertFalse(s["invented_on_textless"])

    def test_merged_example_values_are_an_echo(self):
        (_, t0), (_, t1) = prompt_example_fields()[:2]
        s = _score(BLANK, f"REGION: somewhere\nTEXT: {t0} {t1}")
        self.assertTrue(s["example_echo"])
        self.assertFalse(s["invented_on_textless"])

    def test_echo_plus_real_invention_convicts_the_real_half(self):
        r0, t0 = prompt_example_fields()[0]
        s = _score(BLANK, f"REGION: {r0}\nTEXT: {t0}\nREGION: bar\nTEXT: deploy done")
        self.assertTrue(s["example_echo"])
        self.assertTrue(s["invented_on_textless"])

    def test_echo_never_earns_correct_credit_on_text_cards(self):
        card = {"category": "readable", "truth_text": prompt_example_fields()[0][1]}
        r0, t0 = prompt_example_fields()[0]
        s = _score(card, f"REGION: {r0}\nTEXT: {t0}")
        self.assertTrue(s["example_echo"])
        self.assertFalse(s["correct"], "planted bytes must not score as a read")

    def test_honest_paths_unchanged(self):
        self.assertTrue(_score(BLANK, "NO_TEXT_VISIBLE")["abstained"])
        self.assertTrue(_score(TEXT, "REGION: body\nTEXT: [UNREADABLE]")["abstained"])
        self.assertTrue(_score(TEXT, "REGION: body\nTEXT: harbour lantern")["correct"])
        self.assertTrue(_score(TEXT, "REGION: body\nTEXT: cinder oxide quartz")["wrong_text"])
        self.assertTrue(_score(BLANK, "REGION: bar\nTEXT: deploy done")["invented_on_textless"])


if __name__ == "__main__":
    unittest.main()
