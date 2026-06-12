from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from core.cognition import evidence_precedence_shadow as eps


class _Env(unittest.TestCase):
    def setUp(self):
        for k in (
            "MAEZ_EVIDENCE_PRECEDENCE_ENABLED",
            "MAEZ_EVIDENCE_PRECEDENCE_DEBUG",
        ):
            os.environ.pop(k, None)
            self.addCleanup(lambda k=k: os.environ.pop(k, None))
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.ledger = Path(td.name) / "eps.jsonl"

    def _rows(self):
        if not self.ledger.exists():
            return []
        return [json.loads(x) for x in self.ledger.read_text().splitlines()]


class DetectorTests(_Env):
    def setUp(self):
        super().setUp()
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"

    def test_each_absence_verb_flags_with_fresh_citation(self):
        for verb_text in (
            "the tag is truncated in [E1]",
            "the version is missing from [E1]",
            "it was cut off in [E1]",
            "that detail is not in [E1]",
            "the data doesn't contain it [E1]",
            "[E1] lacks the version string",
            "it is absent from [E1]",
        ):
            with self.subTest(verb_text=verb_text):
                n_before = len(self._rows())
                eps.observe_marked_draft(
                    verb_text,
                    surface="telegram_surface",
                    fresh_indices=(1,),
                    web_present=True,
                    ledger_path=self.ledger,
                )
                self.assertEqual(len(self._rows()), n_before + 1)

    def test_no_marker_no_flag(self):
        eps.observe_marked_draft(
            "the version seems to be missing entirely",
            surface="t",
            fresh_indices=(1,),
            web_present=True,
            ledger_path=self.ledger,
        )
        self.assertEqual(self._rows(), [])

    def test_multi_sentence_only_the_absence_sentence_flags(self):
        draft = "The page loaded fine [E1]. The tag is truncated in [E1]. Good day."
        eps.observe_marked_draft(
            draft,
            surface="t",
            fresh_indices=(1,),
            web_present=True,
            ledger_path=self.ledger,
        )
        rows = self._rows()
        self.assertEqual(len(rows), 1)

    def test_row_is_content_light_with_mode(self):
        eps.observe_marked_draft(
            "secret detail is missing from [E2]",
            surface="t",
            fresh_indices=(2,),
            web_present=True,
            ledger_path=self.ledger,
        )
        row = self._rows()[0]
        self.assertIn(row["fresh_index_mode"], ("proof", "fallback_all_cited"))
        self.assertIn("sentence_hash", row)
        self.assertNotIn("secret detail", json.dumps(row))

    def test_debug_adds_snippet(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_DEBUG"] = "1"
        eps.observe_marked_draft(
            "x is missing from [E1]",
            surface="t",
            fresh_indices=(1,),
            web_present=True,
            ledger_path=self.ledger,
        )
        self.assertIn("sentence_excerpt", self._rows()[0])

    def test_flag_off_writes_nothing(self):
        os.environ.pop("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", None)
        eps.observe_marked_draft(
            "x is missing from [E1]",
            surface="t",
            fresh_indices=(1,),
            web_present=True,
            ledger_path=self.ledger,
        )
        self.assertEqual(self._rows(), [])

    def test_never_raises(self):
        eps.observe_marked_draft(
            None,
            surface="t",
            fresh_indices=None,
            web_present=True,
            ledger_path=Path("/nonexistent/x.jsonl"),
        )


class FallbackPathIndexTests(_Env):
    def setUp(self):
        super().setUp()
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"

    def test_any_cited_index_flags_by_design_with_visible_bias(self):
        eps.observe_marked_draft(
            "we hit this wall before, it was missing [E5]",
            surface="t",
            fresh_indices=None,
            web_present=True,
            ledger_path=self.ledger,
        )
        row = self._rows()[0]
        self.assertEqual(row["fresh_index_mode"], "fallback_all_cited")

    def test_non_web_turn_does_not_flag(self):
        eps.observe_marked_draft(
            "it was missing [E5]",
            surface="t",
            fresh_indices=None,
            web_present=False,
            ledger_path=self.ledger,
        )
        self.assertEqual(self._rows(), [])


if __name__ == "__main__":
    unittest.main()
