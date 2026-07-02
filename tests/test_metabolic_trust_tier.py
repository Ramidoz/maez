import unittest

from memory.memory_manager import (
    TrustTier,
    _partition_consolidation_input,
    _provenance_metadata,
    _TRUST_TIER_ORDER,
)


class SelfObservedTierTests(unittest.TestCase):
    def test_self_observed_is_a_valid_tier(self):
        self.assertEqual(TrustTier("self_observed"), TrustTier.SELF_OBSERVED)

    def test_introspection_default_maps_to_self_observed(self):
        meta = _provenance_metadata("introspection", None)
        self.assertEqual(meta["trust_tier"], "self_observed")
        self.assertEqual(meta["provenance_source"], "introspection")

    def test_order_between_untrusted_and_observed(self):
        order = list(_TRUST_TIER_ORDER)
        self.assertIn("self_observed", order)
        self.assertGreater(order.index("self_observed"), order.index("untrusted"))
        self.assertLess(order.index("self_observed"), order.index("observed"))

    def test_explicit_self_observed_write_does_not_raise(self):
        meta = _provenance_metadata("introspection", "self_observed")
        self.assertEqual(meta["trust_tier"], "self_observed")

    def test_consolidation_filter_keeps_self_observed_drops_untrusted(self):
        items = [
            {"id": "a", "content": "x", "metadata": {"trust_tier": "self_observed"}},
            {"id": "b", "content": "y", "metadata": {"trust_tier": "untrusted"}},
        ]
        _kept, kept_ids, filtered_n, _labels = _partition_consolidation_input(items)
        self.assertEqual(kept_ids, ["a"])
        self.assertEqual(filtered_n, 1)
