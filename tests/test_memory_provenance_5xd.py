# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5x.D.A — promotion gate + ancestor lineage.

5x.D closes the laundering vector the Zombie Agents threat model
named: a memory written from external_web/untrusted material can
ride a "promotion" pass into core, then look trusted because the
freeform ``source="promotion"`` and the core tier hide the
ancestor's lineage.

The gate is at ``MemoryManager.store_core``:

  - ``promoted_from=None`` → fresh-write path; no change from
    5x.A/B. Backwards compatible.
  - ``promoted_from=[ids…]`` → look up each ancestor's
    ``trust_tier`` from raw + core; compute the worst-ancestor
    tier; persist ``ancestor_tiers`` and inherit worst-wins.
  - Worst is ``untrusted`` and ``allow_untrusted_ancestors=False``
    → raise ``PromotionBlocked``. This is the load-bearing gate.
  - Worst is ``untrusted`` and ``allow_untrusted_ancestors=True``
    → promotion proceeds, result tagged ``trust_tier=untrusted``.
    5x.C surfaces it; promotion is not free.
  - Unresolvable ancestor ID → raise ``ValueError`` (caller must
    fix the citation).
  - All-``None``-tier ancestors (pre-5x.A legacy material) → result
    has ``trust_tier=None``. Legacy preservation: blocking would
    break every legitimate promotion of pre-5x material.
  - Mixed concrete + legacy-None → result inherits the worst of the
    concrete tiers (None is non-degrading; ignored in worst-wins).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class _FakeCollection:
    """Fake Chroma collection supporting add(...) and get(ids=...)
    so the gate can resolve ancestor metadata."""

    def __init__(self):
        self.add_calls = []
        self._rows: dict[str, dict] = {}

    def add(self, *, ids, documents, metadatas):
        self.add_calls.append({
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        })
        for i, mid in enumerate(ids):
            self._rows[mid] = {
                "id": mid,
                "document": documents[i],
                "metadata": metadatas[i],
            }

    def seed(self, mid: str, metadata: dict, document: str = ""):
        """Test helper: pre-populate a row so ancestor lookup works."""
        self._rows[mid] = {
            "id": mid,
            "document": document,
            "metadata": metadata,
        }

    def get(self, *, ids, include=None):
        # Mirror Chroma's get(ids=...) shape.
        out_ids: list[str] = []
        out_docs: list[str] = []
        out_metas: list[dict] = []
        for mid in ids:
            if mid in self._rows:
                row = self._rows[mid]
                out_ids.append(mid)
                out_docs.append(row["document"])
                out_metas.append(row["metadata"])
        return {"ids": out_ids, "documents": out_docs, "metadatas": out_metas}


def _mm():
    from memory.memory_manager import MemoryManager
    mm = MemoryManager.__new__(MemoryManager)
    mm.raw = _FakeCollection()
    mm.core = _FakeCollection()
    return mm


# ── fresh-write backwards compat ────────────────────────────────────


class FreshWriteUnchangedTests(unittest.TestCase):
    """``promoted_from=None`` MUST behave identically to 5x.A/B.
    Otherwise every existing call site (soul_evolution, nightly
    journal, heartbeat) regresses."""

    def test_fresh_write_with_provenance_kwargs_unchanged(self):
        mm = _mm()
        mid = mm.store_core(
            "fresh observation",
            source="reasoning",
            provenance_source="introspection",
            trust_tier="lived",
        )
        self.assertTrue(mid.startswith("core-"))
        meta = mm.core.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["provenance_source"], "introspection")
        self.assertEqual(meta["trust_tier"], "lived")
        # No ancestor metadata on a fresh write.
        self.assertNotIn("ancestor_tiers", meta)
        self.assertNotIn("promoted_from", meta)

    def test_fresh_write_legacy_no_provenance_unchanged(self):
        """Pre-5x.A call shape: positional content + freeform source."""
        mm = _mm()
        mid = mm.store_core("observation", source="reasoning")
        self.assertTrue(mid.startswith("core-"))
        meta = mm.core.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["source"], "reasoning")
        self.assertNotIn("provenance_source", meta)
        self.assertNotIn("trust_tier", meta)
        self.assertNotIn("ancestor_tiers", meta)


# ── worst-ancestor tier propagation ─────────────────────────────────


class WorstAncestorTierTests(unittest.TestCase):
    def test_all_lived_ancestors_yield_lived_core(self):
        mm = _mm()
        mm.raw.seed("raw-1", {"trust_tier": "lived",
                              "provenance_source": "user_utterance"})
        mm.raw.seed("raw-2", {"trust_tier": "lived",
                              "provenance_source": "introspection"})
        mm.store_core(
            "[Promoted] something the owner said",
            source="promotion",
            promoted_from=["raw-1", "raw-2"],
        )
        meta = mm.core.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["trust_tier"], "lived")
        # Persisted as comma-joined string per Chroma metadata
        # primitive constraint.
        self.assertEqual(meta["ancestor_tiers"], "lived,lived")
        self.assertEqual(meta["promoted_from"], "raw-1,raw-2")

    def test_lived_plus_observed_ancestors_yield_observed_core(self):
        mm = _mm()
        mm.raw.seed("raw-1", {"trust_tier": "lived",
                              "provenance_source": "user_utterance"})
        mm.raw.seed("raw-2", {"trust_tier": "observed",
                              "provenance_source": "tool_observation"})
        mm.store_core(
            "[Promoted] mixed lineage",
            source="promotion",
            promoted_from=["raw-1", "raw-2"],
        )
        meta = mm.core.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["trust_tier"], "observed")

    def test_caller_supplied_trust_tier_does_not_override_worst_wins(self):
        """Worst-ancestor wins. A caller cannot launder a tier by
        passing trust_tier=lived alongside an observed ancestor."""
        mm = _mm()
        mm.raw.seed("raw-obs", {"trust_tier": "observed",
                                "provenance_source": "tool_observation"})
        mm.store_core(
            "laundering attempt",
            source="promotion",
            promoted_from=["raw-obs"],
            trust_tier="lived",  # liar
        )
        meta = mm.core.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["trust_tier"], "observed")


# ── the gate — load-bearing ─────────────────────────────────────────


class PromotionGateTests(unittest.TestCase):
    def test_untrusted_ancestor_blocks_promotion_by_default(self):
        from memory.memory_manager import PromotionBlocked

        mm = _mm()
        mm.raw.seed("raw-reddit", {
            "trust_tier": "untrusted",
            "provenance_source": "external_web",
        })
        with self.assertRaises(PromotionBlocked):
            mm.store_core(
                "[Promoted] reddit said the moon is hollow",
                source="promotion",
                promoted_from=["raw-reddit"],
            )
        # No core write happened.
        self.assertEqual(mm.core.add_calls, [])

    def test_one_untrusted_among_many_blocks_promotion(self):
        """Single untrusted ancestor in a mixed citation is enough
        to trip the gate — worst-wins is conservative."""
        from memory.memory_manager import PromotionBlocked

        mm = _mm()
        mm.raw.seed("raw-good", {"trust_tier": "lived",
                                 "provenance_source": "user_utterance"})
        mm.raw.seed("raw-evil", {"trust_tier": "untrusted",
                                 "provenance_source": "external_web"})
        with self.assertRaises(PromotionBlocked):
            mm.store_core(
                "[Promoted] mixed lineage with reddit smuggled in",
                source="promotion",
                promoted_from=["raw-good", "raw-evil"],
            )
        self.assertEqual(mm.core.add_calls, [])

    def test_explicit_opt_in_allows_untrusted_promotion(self):
        mm = _mm()
        mm.raw.seed("raw-evil", {"trust_tier": "untrusted",
                                 "provenance_source": "external_web"})
        mid = mm.store_core(
            "[Owner-acknowledged] reddit claim worth recording",
            source="promotion",
            promoted_from=["raw-evil"],
            allow_untrusted_ancestors=True,
        )
        self.assertTrue(mid.startswith("core-"))
        meta = mm.core.add_calls[-1]["metadatas"][0]
        # Result inherits untrusted; promotion is not free.
        self.assertEqual(meta["trust_tier"], "untrusted")
        self.assertEqual(meta["ancestor_tiers"], "untrusted")


# ── legacy preservation ─────────────────────────────────────────────


class LegacyAncestorTests(unittest.TestCase):
    """Pre-5x.A Chroma rows have no trust_tier metadata. Strict
    blocking would break every legitimate promotion of the existing
    21k+ raw entries. The threat 5x.D closes is NEW untrusted
    ingress; legacy preservation is a feature."""

    def test_all_legacy_ancestors_yield_none_trust_tier(self):
        mm = _mm()
        # Pre-5x.A entries have no trust_tier key.
        mm.raw.seed("raw-old-1", {"timestamp": "2026-04-01T00:00:00"})
        mm.raw.seed("raw-old-2", {"timestamp": "2026-04-02T00:00:00"})
        mid = mm.store_core(
            "[Promoted] legacy material",
            source="promotion",
            promoted_from=["raw-old-1", "raw-old-2"],
        )
        self.assertTrue(mid.startswith("core-"))
        meta = mm.core.add_calls[-1]["metadatas"][0]
        # No trust_tier on the result (legacy semantics preserved).
        self.assertNotIn("trust_tier", meta)
        # ancestor_tiers reflects the unknowns explicitly.
        self.assertEqual(meta["ancestor_tiers"], "unknown,unknown")

    def test_caller_supplied_trust_tier_dropped_in_all_legacy_branch(self):
        """Symmetry with ``test_caller_supplied_trust_tier_does_not_
        override_worst_wins`` (worst-is-concrete branch). When every
        ancestor is legacy, a caller's ``trust_tier="lived"`` claim
        must also be dropped — legacy preservation cannot be a
        backdoor for laundering. The result has NO trust_tier key."""
        mm = _mm()
        mm.raw.seed("raw-old", {})
        mm.store_core(
            "[Promoted] legacy laundering attempt",
            source="promotion",
            promoted_from=["raw-old"],
            trust_tier="lived",  # liar
            provenance_source="introspection",  # also liar
        )
        meta = mm.core.add_calls[-1]["metadatas"][0]
        # Both provenance keys are dropped — the result is fully
        # legacy except for the new ancestor lineage metadata.
        self.assertNotIn("trust_tier", meta)
        self.assertNotIn("provenance_source", meta)
        # Lineage metadata still lands so 5x.D.B / future readers can
        # see this WAS a promotion even when tier is unknown.
        self.assertEqual(meta["ancestor_tiers"], "unknown")
        self.assertEqual(meta["promoted_from"], "raw-old")

    def test_mixed_concrete_and_legacy_inherits_worst_concrete(self):
        """When some ancestors are tagged and some legacy, the result
        inherits the worst of the CONCRETE tiers. Legacy is
        non-degrading — the bar for a promotion's trust is set by
        what is known, not by the absence of info on legacy rows."""
        mm = _mm()
        mm.raw.seed("raw-legacy", {})
        mm.raw.seed("raw-tagged", {"trust_tier": "observed",
                                   "provenance_source": "tool_observation"})
        mm.store_core(
            "[Promoted]",
            source="promotion",
            promoted_from=["raw-legacy", "raw-tagged"],
        )
        meta = mm.core.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["trust_tier"], "observed")
        self.assertEqual(meta["ancestor_tiers"], "unknown,observed")


# ── error paths: unresolvable ancestors and empty lists ─────────────


class CitationErrorTests(unittest.TestCase):
    def test_unresolvable_ancestor_raises(self):
        mm = _mm()
        with self.assertRaises(ValueError):
            mm.store_core(
                "[Promoted]",
                source="promotion",
                promoted_from=["raw-does-not-exist"],
            )
        self.assertEqual(mm.core.add_calls, [])

    def test_empty_promoted_from_raises(self):
        """Empty list is ambiguous (programming error vs. intent).
        Refuse rather than silently promoting as fresh-write."""
        mm = _mm()
        with self.assertRaises(ValueError):
            mm.store_core(
                "[Promoted]",
                source="promotion",
                promoted_from=[],
            )

    def test_promotion_resolves_ancestors_in_core_too(self):
        """A promotion can cite a core ancestor (e.g. consolidating
        two existing core memories into a higher-level one). The
        gate must look in both raw AND core."""
        mm = _mm()
        mm.core.seed("core-prior", {"trust_tier": "lived",
                                    "provenance_source": "introspection"})
        mid = mm.store_core(
            "[Promoted] consolidation of an earlier core",
            source="promotion",
            promoted_from=["core-prior"],
        )
        self.assertTrue(mid.startswith("core-"))
        meta = mm.core.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["trust_tier"], "lived")


if __name__ == "__main__":
    unittest.main()
