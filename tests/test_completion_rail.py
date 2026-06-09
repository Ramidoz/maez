import unittest

from core.safety.self_claim_audit import check_completion_claims
from tests.test_judge_coverage_corpus import load_corpus


class CompletionRail(unittest.TestCase):
    def test_corpus_precision_and_recall(self):
        for r in load_corpus():
            if not r["stratum"].startswith("completion_"):
                continue
            flags = check_completion_claims(
                r["text"],
                grounded_by_tool=r["grounded_by_tool"],
            )
            flagged = bool(flags)
            self.assertEqual(
                flagged,
                r["expect"] == "flag",
                f"{r['id']} ({r['note']}): expected {r['expect']}, "
                f"got {'flag' if flagged else 'clean'} on {r['text']!r}",
            )

    def test_both_conditions_required(self):
        self.assertEqual(
            check_completion_claims("The manifest was updated.", grounded_by_tool=False),
            [],
        )
        self.assertEqual(
            check_completion_claims("I considered the manifest.", grounded_by_tool=False),
            [],
        )


if __name__ == "__main__":
    unittest.main()
