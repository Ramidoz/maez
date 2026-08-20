"""Held-now Phase 1, commit A: scope stamps + the coalesced reader.

Design: docs/superpowers/specs/2026-08-20-held-now-repair-phase1-design.md
(pass 6, gate-approved). These tests cover C4's write side and C5's
reader, including the gate-pinned orphan-starvation case.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.eval.longmemeval import IsolatedMemoryHarness


def _ts(minutes: int) -> str:
    base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    return (base + timedelta(minutes=minutes)).isoformat()


def _add_raw(mm, row_id, content, **meta):
    full = {"type": "telegram_exchange", "timestamp": meta.pop("timestamp")}
    full.update(meta)
    mm.raw.add(ids=[row_id], documents=[content], metadatas=[full])


class StoreStampTests(unittest.TestCase):
    def test_store_telegram_stamps_scope_when_given(self):
        with IsolatedMemoryHarness() as h:
            mid = h.mm.store_telegram(
                "the owner (telegram_surface): hi\nMaez: hello",
                origin_surface="telegram_surface",
                chat_id="12345",
            )
            row = h.mm.raw.get(ids=[mid], include=["metadatas"])
            meta = row["metadatas"][0]
            self.assertEqual(meta["origin_surface"], "telegram_surface")
            self.assertEqual(meta["chat_id"], "12345")

    def test_store_telegram_without_scope_stamps_nothing(self):
        # Legacy callers keep producing legacy rows: no empty-string
        # stamps that would defeat wildcard matching.
        with IsolatedMemoryHarness() as h:
            mid = h.mm.store_telegram(
                "the owner (telegram_surface): hi\nMaez: hello",
            )
            meta = h.mm.raw.get(ids=[mid], include=["metadatas"])["metadatas"][0]
            self.assertNotIn("origin_surface", meta)
            self.assertNotIn("chat_id", meta)


class CoalescedReaderTests(unittest.TestCase):
    def test_scope_filter_excludes_other_surfaces_keeps_legacy(self):
        with IsolatedMemoryHarness() as h:
            _add_raw(h.mm, "a", "the owner (telegram_surface): one\nMaez: r1",
                     timestamp=_ts(0), origin_surface="telegram_surface",
                     chat_id="c1")
            _add_raw(h.mm, "b", "the owner (web_owner): two\nMaez: r2",
                     timestamp=_ts(1), origin_surface="web_owner",
                     chat_id="web_owner")
            _add_raw(h.mm, "c", "the owner (telegram): legacy\nMaez: r3",
                     timestamp=_ts(2))  # unstamped legacy row
            got = h.mm.get_telegram_exchanges_coalesced(
                origin_surface="telegram_surface", chat_id="c1"
            )
            ids = [g["id"] for g in got]
            self.assertIn("a", ids)
            self.assertNotIn("b", ids)  # other surface excluded
            self.assertIn("c", ids)     # legacy wildcard matches

    def test_split_pair_coalesces_into_one_logical_exchange(self):
        with IsolatedMemoryHarness() as h:
            _add_raw(h.mm, "o1", "the owner (telegram_surface): what is X?",
                     timestamp=_ts(0), turn_link_id="L1",
                     provenance_source="user_utterance", trust_tier="lived")
            _add_raw(h.mm, "r1", "Maez: X is a thing I read on the web.",
                     timestamp=_ts(0), turn_link_id="L1",
                     provenance_source="self_web_claim", trust_tier="untrusted")
            got = h.mm.get_telegram_exchanges_coalesced()
            self.assertEqual(len(got), 1)
            row = got[0]
            self.assertIn("what is X?", row["content"])
            self.assertIn("\nMaez: X is a thing", row["content"])
            # worst-half governs
            self.assertEqual(row["metadata"]["trust_tier"], "untrusted")
            self.assertEqual(
                row["metadata"]["provenance_source_reply"], "self_web_claim"
            )

    def test_coalesced_pair_consumes_one_window_slot(self):
        with IsolatedMemoryHarness() as h:
            # oldest: split pair; then two plain exchanges; window of 3
            _add_raw(h.mm, "o1", "the owner (t): q1", timestamp=_ts(0),
                     turn_link_id="L1")
            _add_raw(h.mm, "r1", "Maez: a1", timestamp=_ts(0),
                     turn_link_id="L1")
            _add_raw(h.mm, "p2", "the owner (t): q2\nMaez: a2",
                     timestamp=_ts(1))
            _add_raw(h.mm, "p3", "the owner (t): q3\nMaez: a3",
                     timestamp=_ts(2))
            got = h.mm.get_telegram_exchanges_coalesced(limit=3)
            self.assertEqual(len(got), 3)  # split pair = ONE slot
            self.assertIn("q1", got[0]["content"])

    def test_orphan_half_skipped_with_warning_and_no_starvation(self):
        # Gate-pinned case: >N newest orphan rows ahead of N intact
        # exchanges must still yield N logical exchanges.
        with IsolatedMemoryHarness() as h:
            for i in range(3):
                _add_raw(h.mm, f"intact{i}",
                         f"the owner (t): q{i}\nMaez: a{i}",
                         timestamp=_ts(i))
            for i in range(4):  # 4 orphan owner-halves, newest
                _add_raw(h.mm, f"orph{i}", f"the owner (t): lost{i}",
                         timestamp=_ts(10 + i), turn_link_id=f"OL{i}")
            with self.assertLogs(level="WARNING") as logs:
                got = h.mm.get_telegram_exchanges_coalesced(limit=3)
            self.assertEqual(len(got), 3)
            self.assertTrue(all("Maez:" in g["content"] for g in got))
            self.assertTrue(
                any("held_now_orphan_row" in line for line in logs.output)
            )

    def test_original_reader_untouched_by_split_rows(self):
        # The 8 legacy callers keep exact legacy semantics: split rows
        # remain two raw rows there.
        with IsolatedMemoryHarness() as h:
            _add_raw(h.mm, "o1", "the owner (t): q1", timestamp=_ts(0),
                     turn_link_id="L1")
            _add_raw(h.mm, "r1", "Maez: a1", timestamp=_ts(0),
                     turn_link_id="L1")
            legacy = h.mm.get_telegram_exchanges()
            self.assertEqual(len(legacy), 2)


if __name__ == "__main__":
    unittest.main()
