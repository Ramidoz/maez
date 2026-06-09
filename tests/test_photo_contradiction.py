import unittest

from core.routing.photo_contradiction import (
    extract_photo_claims,
    normalize_claim_text,
)


class PhotoClaimExtraction(unittest.TestCase):
    def test_extracts_direct_perceptual_sentences(self):
        reply = (
            "The screenshot title says WWDC 2026 [E1]. "
            "The chart lists Q4_0 as 2.9 GB [E1]. "
            "This matters for what we are building."
        )
        claims = extract_photo_claims(reply)
        self.assertEqual(
            [c.text for c in claims],
            [
                "The screenshot title says WWDC 2026.",
                "The chart lists Q4_0 as 2.9 GB.",
            ],
        )
        self.assertTrue(all(c.direct_perceptual for c in claims))
        self.assertEqual([c.claim_id for c in claims], ["C1", "C2"])
        self.assertEqual([c.evidence_label for c in claims], ["E1", "E1"])

    def test_excludes_interpretive_advice_and_project_meaning(self):
        reply = (
            "This matters for Maez's roadmap [E1]. "
            "You may want to test it later. "
            "I would treat this as promising."
        )
        self.assertEqual(extract_photo_claims(reply), [])

    def test_claims_are_draft_bound_no_generated_paraphrase(self):
        reply = "The image shows a Reddit screenshot [E1]."
        claims = extract_photo_claims(reply)
        self.assertEqual(
            [c.text for c in claims],
            ["The image shows a Reddit screenshot."],
        )
        normalized_reply = normalize_claim_text(reply)
        self.assertIn(normalize_claim_text(claims[0].text), normalized_reply)

    def test_mixed_claim_keeps_sentence_or_skips_never_invents_smaller_claim(self):
        reply = "The image shows WWDC 2026, which is a developer conference [E1]."
        claims = extract_photo_claims(reply)
        self.assertEqual(len(claims), 1)
        self.assertEqual(
            claims[0].text,
            "The image shows WWDC 2026, which is a developer conference.",
        )
        self.assertNotIn("The image shows WWDC 2026.", [c.text for c in claims])

    def test_ambiguous_sentence_is_omitted_not_false_demoted(self):
        reply = "It seems important and probably relates to the current work [E1]."
        self.assertEqual(extract_photo_claims(reply), [])

    def test_bare_non_photo_verbs_are_omitted(self):
        reply = (
            "The presenter says WWDC 2026 is next week [E1]. "
            "The article lists three possible launch dates [E1]."
        )
        self.assertEqual(extract_photo_claims(reply), [])

    def test_claim_cap_truncates_to_first_five(self):
        reply = " ".join(
            f"The screenshot lists item {i} [E1]." for i in range(1, 8)
        )
        claims = extract_photo_claims(reply, limit=5)
        self.assertEqual(len(claims), 5)
        self.assertEqual(claims[-1].text, "The screenshot lists item 5.")

    def test_nonpositive_claim_cap_returns_no_claims(self):
        reply = "The screenshot lists item 1 [E1]."
        self.assertEqual(extract_photo_claims(reply, limit=0), [])
        self.assertEqual(extract_photo_claims(reply, limit=-1), [])

    def test_normalize_removes_citation_without_space_before_punctuation(self):
        self.assertEqual(
            normalize_claim_text("The screenshot title says WWDC 2026 [E1]."),
            "The screenshot title says WWDC 2026.",
        )


if __name__ == "__main__":
    unittest.main()
