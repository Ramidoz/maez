import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "grounding_bench"))

from corpus_schema import validate_corpus, MODES, EVIDENCE_KINDS, LABELS  # noqa: E402


class CorpusSchemaTests(unittest.TestCase):
    def _row(self, **over):
        base = dict(id="x-1", mode="grounded_positive", source="synthetic",
                    evidence_kind="claimable_present", evidence="E", claim="C",
                    expected="SUPPORTED", strict_rule=False, rationale="r")
        base.update(over)
        return base

    def test_valid_row_passes(self):
        validate_corpus([self._row()])  # should not raise

    def test_missing_field_raises(self):
        bad = self._row()
        del bad["rationale"]
        with self.assertRaises(ValueError):
            validate_corpus([bad])

    def test_bad_enum_raises(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(expected="MAYBE")])

    def test_claimable_absent_must_be_abstain(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(evidence_kind="claimable_absent", expected="SUPPORTED")])

    def test_abstain_requires_claimable_absent(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(evidence_kind="claimable_present", expected="ABSTAIN_EXPECTED")])

    def test_duplicate_ids_raise(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(id="dup"), self._row(id="dup")])

    def test_empty_rationale_raises(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(rationale="   ")])


if __name__ == "__main__":
    unittest.main()
