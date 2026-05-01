# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5x.E — daily consolidation lineage.

After 5x.D.B1 the explicit promotion path is gated. Daily
consolidation is the next-largest laundering surface: every night
``consolidate_daily`` distills N raw rows into a single daily
summary that lands in core's prompt block forever. Without
ancestor lineage, a single reddit post in the day's raw stream
gets summarised into the daily entry and looks trusted thereafter.

Design call (filter, not fail):

  - Untrusted raw rows are EXCLUDED from the consolidation input
    before the LLM ever sees them. The consolidation proceeds on
    the surviving rows.
  - Failing the consolidation on first untrusted row would force
    owner intervention every time reddit ingests; filtering keeps
    nightly continuity AND keeps untrusted text out of derived
    memory.
  - The daily entry's metadata persists ancestor lineage:
    ``ancestor_tiers`` (comma-joined; only includes rows that fed
    in), ``promoted_from`` (their IDs), ``filtered_untrusted_count``
    (visibility), worst-wins ``trust_tier`` from survivors.
  - If filtering empties the input (every raw row was untrusted),
    no daily entry is written — falls through the existing
    "no memories since last consolidation" path.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── _partition_consolidation_input helper ───────────────────────────


class PartitionConsolidationInputTests(unittest.TestCase):
    """Pure-function helper. Splits raw rows into (kept, untrusted_
    count, ancestor_tier_labels) based on each row's trust_tier."""

    def _partition(self, items):
        from memory.memory_manager import _partition_consolidation_input
        return _partition_consolidation_input(items)

    def test_all_lived_rows_pass_through_unchanged(self):
        items = [
            {"id": "raw-1", "content": "a", "metadata": {
                "trust_tier": "lived",
                "provenance_source": "user_utterance",
            }},
            {"id": "raw-2", "content": "b", "metadata": {
                "trust_tier": "lived",
                "provenance_source": "introspection",
            }},
        ]
        kept, kept_ids, filtered_n, tiers = self._partition(items)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept_ids, ["raw-1", "raw-2"])
        self.assertEqual(filtered_n, 0)
        self.assertEqual(tiers, ["lived", "lived"])

    def test_untrusted_rows_are_filtered_out(self):
        items = [
            {"id": "raw-1", "content": "a", "metadata": {
                "trust_tier": "lived",
                "provenance_source": "user_utterance",
            }},
            {"id": "raw-evil", "content": "reddit poison", "metadata": {
                "trust_tier": "untrusted",
                "provenance_source": "external_web",
            }},
            {"id": "raw-3", "content": "c", "metadata": {
                "trust_tier": "observed",
                "provenance_source": "tool_observation",
            }},
        ]
        kept, kept_ids, filtered_n, tiers = self._partition(items)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept_ids, ["raw-1", "raw-3"])
        self.assertEqual(filtered_n, 1)
        self.assertEqual(tiers, ["lived", "observed"])
        # The untrusted content NEVER reaches the kept set.
        for row in kept:
            self.assertNotIn("reddit poison", row["content"])

    def test_legacy_rows_pass_through_as_unknown(self):
        items = [
            {"id": "raw-old", "content": "pre-5x", "metadata": {}},
            {"id": "raw-old2", "content": "also pre-5x", "metadata": {
                "timestamp": "2026-04-01"
            }},
        ]
        kept, kept_ids, filtered_n, tiers = self._partition(items)
        self.assertEqual(len(kept), 2)
        self.assertEqual(filtered_n, 0)
        self.assertEqual(tiers, ["unknown", "unknown"])

    def test_empty_input_returns_empty(self):
        kept, kept_ids, filtered_n, tiers = self._partition([])
        self.assertEqual(kept, [])
        self.assertEqual(kept_ids, [])
        self.assertEqual(filtered_n, 0)
        self.assertEqual(tiers, [])

    def test_all_untrusted_input_returns_empty_kept(self):
        """Edge case: every raw row was untrusted. Kept set empty;
        consolidate_daily falls through its existing 'no memories'
        path and writes no daily entry."""
        items = [
            {"id": "raw-evil1", "content": "reddit", "metadata": {
                "trust_tier": "untrusted",
            }},
            {"id": "raw-evil2", "content": "more reddit", "metadata": {
                "trust_tier": "untrusted",
            }},
        ]
        kept, kept_ids, filtered_n, tiers = self._partition(items)
        self.assertEqual(kept, [])
        self.assertEqual(kept_ids, [])
        self.assertEqual(filtered_n, 2)
        self.assertEqual(tiers, [])


# ── consolidate_daily integration: lineage on the daily entry ───────


class _FakeRawCollection:
    """Fake supporting count + get(limit/offset) for consolidate_daily."""

    def __init__(self, rows: list[dict]):
        # Each row: {"id", "document", "metadata"}.
        self._rows = list(rows)

    def count(self):
        return len(self._rows)

    def get(self, *, limit=None, offset=None, ids=None, include=None):
        if ids is not None:
            wanted = set(ids)
            subset = [r for r in self._rows if r["id"] in wanted]
        else:
            subset = self._rows
            if offset:
                subset = subset[offset:]
            if limit is not None:
                subset = subset[:limit]
        return {
            "ids": [r["id"] for r in subset],
            "documents": [r["document"] for r in subset],
            "metadatas": [r["metadata"] for r in subset],
        }


class _FakeDailyCollection:
    def __init__(self):
        self.add_calls = []

    def add(self, *, ids, documents, metadatas):
        self.add_calls.append({
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        })


def _mm_with_consolidation_fakes(raw_rows, monkeypatch_summary="SUMMARY"):
    """Build a MemoryManager with fake raw + daily, monkey-patched
    so _consolidate_with_chunking returns a deterministic string and
    last-consolidation timestamp / mark_consolidated are no-ops."""
    from memory.memory_manager import MemoryManager
    import memory.memory_manager as _mm_mod

    mm = MemoryManager.__new__(MemoryManager)
    mm.raw = _FakeRawCollection(raw_rows)
    mm.daily = _FakeDailyCollection()
    # Avoid touching the scorer + consolidation-timestamp side files.
    mm._get_last_consolidation = lambda: __import__(
        "datetime"
    ).datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc)
    mm._save_last_consolidation = lambda: None
    # The scorer feedback loop tries to import core.memory_scoring; in
    # the fake path we skip it via monkey-patched mark_consolidated.
    mm.mark_consolidated = lambda ids: None

    # Replace the LLM call with a deterministic stub.
    _mm_mod._consolidate_with_chunking = lambda *, memory_texts, soul, logger_: monkeypatch_summary
    return mm, _mm_mod


class ConsolidateDailyLineageTests(unittest.TestCase):
    def setUp(self):
        # Snapshot the real _consolidate_with_chunking so each test
        # restores it (other suites may rely on the import).
        import memory.memory_manager as _mm_mod
        self._real_consolidate = _mm_mod._consolidate_with_chunking

    def tearDown(self):
        import memory.memory_manager as _mm_mod
        _mm_mod._consolidate_with_chunking = self._real_consolidate

    def _row(self, mid, content, **meta_extra):
        # Use a recent timestamp so consolidate_daily's cutoff includes
        # this row regardless of which expansion branch fires.
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        return {
            "id": mid,
            "document": content,
            "metadata": {
                "timestamp": ts,
                "cycle": 1,
                "type": "reasoning",
                **meta_extra,
            },
        }

    def test_consolidation_with_only_lived_rows_writes_lived_daily(self):
        rows = [
            self._row("r1", "a", trust_tier="lived",
                      provenance_source="user_utterance"),
            self._row("r2", "b", trust_tier="lived",
                      provenance_source="introspection"),
        ]
        mm, _ = _mm_with_consolidation_fakes(rows)
        cid = mm.consolidate_daily()
        self.assertIsNotNone(cid)
        meta = mm.daily.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["trust_tier"], "lived")
        self.assertEqual(meta["ancestor_tiers"], "lived,lived")
        self.assertEqual(meta["promoted_from"], "r1,r2")
        self.assertEqual(meta["filtered_untrusted_count"], 0)
        # Curatorial act → introspection.
        self.assertEqual(meta["provenance_source"], "introspection")

    def test_consolidation_filters_untrusted_and_records_count(self):
        rows = [
            self._row("r-good", "a", trust_tier="lived",
                      provenance_source="user_utterance"),
            self._row("r-evil", "REDDIT_POISON_TEXT",
                      trust_tier="untrusted",
                      provenance_source="external_web"),
            self._row("r-tool", "c", trust_tier="observed",
                      provenance_source="tool_observation"),
        ]
        mm, mm_mod = _mm_with_consolidation_fakes(rows)
        # Sentinel: capture the memory_texts passed to the LLM so we
        # can prove the untrusted content never reached it.
        captured = {}

        def _capture(*, memory_texts, soul, logger_):
            captured["memory_texts"] = list(memory_texts)
            return "SUMMARY"

        mm_mod._consolidate_with_chunking = _capture
        mm.consolidate_daily()
        joined_input = "\n".join(captured["memory_texts"])
        self.assertNotIn("REDDIT_POISON_TEXT", joined_input)

        meta = mm.daily.add_calls[-1]["metadatas"][0]
        # Worst-wins of survivors: lived + observed → observed.
        self.assertEqual(meta["trust_tier"], "observed")
        self.assertEqual(meta["ancestor_tiers"], "lived,observed")
        self.assertEqual(meta["promoted_from"], "r-good,r-tool")
        self.assertEqual(meta["filtered_untrusted_count"], 1)
        # raw_count reflects the rows that ACTUALLY fed in (post-filter)
        # so downstream observability matches reality.
        self.assertEqual(meta["raw_count"], 2)

    def test_consolidation_with_all_untrusted_writes_no_daily(self):
        rows = [
            self._row("r-evil1", "reddit a", trust_tier="untrusted",
                      provenance_source="external_web"),
            self._row("r-evil2", "reddit b", trust_tier="untrusted",
                      provenance_source="external_web"),
        ]
        mm, _ = _mm_with_consolidation_fakes(rows)
        cid = mm.consolidate_daily()
        # Filter empties input → no daily entry written.
        self.assertIsNone(cid)
        self.assertEqual(mm.daily.add_calls, [])

    def test_consolidation_caps_promoted_from_string_with_remainder_sentinel(self):
        """M3 from 5x.E review: high-volume days (e.g. 500 raw rows)
        would produce a 20kb+ comma-joined ID string in metadata that
        gets re-serialized on every daily-query. Cap inline IDs and
        record total via promoted_from_count so an operator still
        sees the truth. Truth-of-lineage stays on the raw rows
        themselves; each survivor's metadata is unchanged."""
        rows = [
            self._row(f"r{i}", f"row {i}", trust_tier="lived",
                      provenance_source="introspection")
            for i in range(75)
        ]
        mm, _ = _mm_with_consolidation_fakes(rows)
        mm.consolidate_daily()
        meta = mm.daily.add_calls[-1]["metadatas"][0]
        # Cap is 50 inline IDs + ",+25" remainder sentinel.
        self.assertEqual(meta["promoted_from_count"], 75)
        self.assertTrue(meta["promoted_from"].endswith(",+25"))
        # Inline portion contains exactly 50 IDs.
        inline_ids = meta["promoted_from"].rsplit(",+", 1)[0].split(",")
        self.assertEqual(len(inline_ids), 50)
        self.assertEqual(inline_ids[0], "r0")
        self.assertEqual(inline_ids[-1], "r49")

    def test_consolidation_under_cap_omits_remainder_sentinel(self):
        """Below the cap, promoted_from is the plain comma-joined list;
        no `+N` sentinel suffix should appear."""
        rows = [
            self._row(f"r{i}", f"row {i}", trust_tier="lived",
                      provenance_source="introspection")
            for i in range(5)
        ]
        mm, _ = _mm_with_consolidation_fakes(rows)
        mm.consolidate_daily()
        meta = mm.daily.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["promoted_from"], "r0,r1,r2,r3,r4")
        self.assertEqual(meta["promoted_from_count"], 5)
        self.assertNotIn("+", meta["promoted_from"])

    def test_consolidation_with_all_legacy_writes_daily_with_no_tier(self):
        rows = [
            self._row("r-old1", "pre-5x a"),
            self._row("r-old2", "pre-5x b"),
        ]
        mm, _ = _mm_with_consolidation_fakes(rows)
        cid = mm.consolidate_daily()
        self.assertIsNotNone(cid)
        meta = mm.daily.add_calls[-1]["metadatas"][0]
        # Legacy preservation: no trust_tier, no provenance_source.
        self.assertNotIn("trust_tier", meta)
        self.assertNotIn("provenance_source", meta)
        # Lineage trail still lands so a future reader can see this
        # WAS a derived consolidation.
        self.assertEqual(meta["ancestor_tiers"], "unknown,unknown")
        self.assertEqual(meta["promoted_from"], "r-old1,r-old2")
        self.assertEqual(meta["filtered_untrusted_count"], 0)


if __name__ == "__main__":
    unittest.main()
