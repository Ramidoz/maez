# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5x.A — memory provenance schema/API contract.

This slice is intentionally metadata-only. It adds optional
``provenance_source`` and ``trust_tier`` write-through without changing
recall behavior for legacy/unmigrated memories.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class _FakeCollection:
    def __init__(self):
        self.add_calls = []

    def add(self, *, ids, documents, metadatas):
        self.add_calls.append({
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        })


def _mm_with_fakes():
    from memory.memory_manager import MemoryManager

    mm = MemoryManager.__new__(MemoryManager)
    mm.raw = _FakeCollection()
    mm.core = _FakeCollection()
    return mm


class ProvenanceWriteApiTests(unittest.TestCase):
    def test_store_accepts_provenance_kwargs(self):
        from memory.memory_manager import ProvenanceSource, TrustTier

        mm = _mm_with_fakes()
        mid = mm.store(
            "owner said the bridge matters",
            cycle=7,
            provenance_source=ProvenanceSource.USER_UTTERANCE,
            trust_tier=TrustTier.LIVED,
        )

        self.assertTrue(mid)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["provenance_source"], "user_utterance")
        self.assertEqual(meta["trust_tier"], "lived")

    def test_store_telegram_accepts_provenance_kwargs(self):
        mm = _mm_with_fakes()
        mid = mm.store_telegram(
            "the owner: hi\nMaez: here",
            provenance_source="user_utterance",
            trust_tier="lived",
        )

        self.assertTrue(mid)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["type"], "telegram_exchange")
        self.assertEqual(meta["provenance_source"], "user_utterance")
        self.assertEqual(meta["trust_tier"], "lived")

    def test_store_core_accepts_provenance_kwargs_alongside_existing_source(self):
        mm = _mm_with_fakes()
        mid = mm.store_core(
            "A restore coma entry belongs in core memory.",
            source="restore_writer",
            provenance_source="system",
            trust_tier="covenant",
        )

        self.assertTrue(mid.startswith("core-"))
        meta = mm.core.add_calls[-1]["metadatas"][0]
        # Existing freeform source field is preserved; Step 5x must not
        # overload it with the provenance enum.
        self.assertEqual(meta["source"], "restore_writer")
        self.assertEqual(meta["provenance_source"], "system")
        self.assertEqual(meta["trust_tier"], "covenant")

    def test_store_derives_default_tier_from_provenance_source(self):
        mm = _mm_with_fakes()
        mm.store(
            "Claude tier said something that must not be laundered.",
            cycle=9,
            provenance_source="claude_tier_response",
        )

        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["provenance_source"], "claude_tier_response")
        self.assertEqual(meta["trust_tier"], "untrusted")

    def test_store_accepts_egress_origin_class(self):
        mm = _mm_with_fakes()
        mid = mm.store(
            "owner-account memory canary",
            cycle=11,
            egress_origin_class="owner_account_context",
        )

        self.assertTrue(mid)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["egress_origin_class"], "owner_account_context")

    def test_store_telegram_accepts_egress_origin_class(self):
        mm = _mm_with_fakes()
        mid = mm.store_telegram(
            "owner account exchange canary",
            egress_origin_class="owner_account_context",
        )

        self.assertTrue(mid)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["egress_origin_class"], "owner_account_context")

    def test_store_core_accepts_egress_origin_class(self):
        mm = _mm_with_fakes()
        mid = mm.store_core(
            "owner-account-derived core canary",
            egress_origin_class="owner_account_context",
        )

        self.assertTrue(mid.startswith("core-"))
        meta = mm.core.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["egress_origin_class"], "owner_account_context")

    def test_unmigrated_entries_have_no_provenance_and_prompt_is_unchanged(self):
        from memory.memory_manager import MemoryManager

        mm = MemoryManager.__new__(MemoryManager)
        recalled = {
            "core": [{"id": "core-a", "content": "continuity matters", "metadata": {}}],
            "daily": [],
            "raw": [],
        }
        out = mm.format_for_prompt(recalled)

        self.assertIn("continuity matters", out)
        self.assertNotIn("provenance_source", out)
        self.assertNotIn("trust_tier", out)
        self.assertNotIn("untrusted", out)

    def test_invalid_provenance_source_raises(self):
        mm = _mm_with_fakes()
        with self.assertRaises(ValueError):
            mm.store("bad source", cycle=1, provenance_source="claudeish")
        self.assertEqual(mm.raw.add_calls, [])

    def test_invalid_trust_tier_raises(self):
        mm = _mm_with_fakes()
        with self.assertRaises(ValueError):
            mm.store("bad tier", cycle=1, trust_tier="probably_fine")
        self.assertEqual(mm.raw.add_calls, [])

    def test_invalid_egress_origin_class_raises_before_write(self):
        mm = _mm_with_fakes()
        with self.assertRaises(ValueError):
            mm.store(
                "bad egress origin",
                cycle=1,
                egress_origin_class="owner_account_contex",
            )
        self.assertEqual(mm.raw.add_calls, [])


class DefaultTierTests(unittest.TestCase):
    def test_default_tier_for_helper(self):
        from memory.memory_manager import (
            ProvenanceSource,
            TrustTier,
            default_tier_for,
        )

        self.assertEqual(
            default_tier_for(ProvenanceSource.INTROSPECTION),
            TrustTier.SELF_OBSERVED,
        )
        self.assertEqual(default_tier_for("user_utterance"), TrustTier.LIVED)
        self.assertEqual(default_tier_for("tool_observation"), TrustTier.OBSERVED)
        self.assertEqual(default_tier_for("external_web"), TrustTier.UNTRUSTED)
        self.assertEqual(
            default_tier_for("claude_tier_response"),
            TrustTier.UNTRUSTED,
        )
        self.assertEqual(default_tier_for("system"), TrustTier.COVENANT)

    def test_default_tier_rejects_unknown_source(self):
        from memory.memory_manager import default_tier_for

        with self.assertRaises(ValueError):
            default_tier_for("friend_of_a_friend")
