import unittest


class SelfWebClaimProvenanceTest(unittest.TestCase):
    def test_self_web_claim_is_a_provenance_source(self):
        from memory.memory_manager import ProvenanceSource

        self.assertEqual(ProvenanceSource.SELF_WEB_CLAIM.value, "self_web_claim")

    def test_self_web_claim_defaults_to_untrusted(self):
        from memory.memory_manager import TrustTier, default_tier_for

        self.assertEqual(default_tier_for("self_web_claim"), TrustTier.UNTRUSTED)

    def test_self_web_claim_is_distinct_from_claude_tier_response(self):
        from memory.memory_manager import ProvenanceSource

        self.assertNotEqual(
            ProvenanceSource.SELF_WEB_CLAIM, ProvenanceSource.CLAUDE_TIER_RESPONSE
        )


if __name__ == "__main__":
    unittest.main()
