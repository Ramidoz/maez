import unittest

from core.evolution.brain_audition import seams


class Seams(unittest.TestCase):
    def test_candidate_source_is_inert_by_default(self):
        self.assertEqual(seams.candidate_source(), [])

    def test_advisor_consult_is_future_decide_egress_public_topic_shape(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            "decide_egress.*public-topic",
        ):
            seams.advisor_consult(candidate="gemma4-12b")

    def test_owner_proposal_is_future_surface(self):
        with self.assertRaisesRegex(NotImplementedError, "owner_proposal.*future seam"):
            seams.owner_proposal(report={"candidate": "gemma4-12b"})

    def test_swap_breath_is_owner_breath_and_never_autofires(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            "owner.*breath.*never auto-fired",
        ):
            seams.swap_breath(candidate="gemma4-12b")


if __name__ == "__main__":
    unittest.main()
