# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5x.D.B1 — action_engine promotion uses ancestor lineage.

The promotion gate landed in ``MemoryManager.store_core`` in 5x.D.A,
but it only protects production once callers pass ``promoted_from``.
This slice wires the explicit raw-memory promotion action, the one
action-engine path that already has a concrete source ID.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class _FakeRaw:
    def __init__(self, docs_by_id):
        self.docs_by_id = dict(docs_by_id)

    def get(self, *, ids, include=None):
        docs = []
        for mid in ids:
            if mid in self.docs_by_id:
                docs.append(self.docs_by_id[mid])
        return {"documents": docs}


class _FakeMemory:
    def __init__(self, docs_by_id=None, *, block=False):
        self.raw = _FakeRaw(docs_by_id or {})
        self.block = block
        self.store_core_calls = []

    def store_core(self, content, source="reasoning", *,
                   provenance_source=None, trust_tier=None,
                   promoted_from=None,
                   allow_untrusted_ancestors=False):
        # Tightened to mirror the live MemoryManager.store_core
        # signature exactly: a future required-kwarg drift in
        # production surfaces here as a TypeError rather than a
        # silent permissive pass-through. Captured kwargs are stored
        # under their real names so test assertions key on the
        # production-facing API.
        self.store_core_calls.append({
            "content": content,
            "source": source,
            "provenance_source": provenance_source,
            "trust_tier": trust_tier,
            "promoted_from": promoted_from,
            "allow_untrusted_ancestors": allow_untrusted_ancestors,
        })
        if self.block:
            from memory.memory_manager import PromotionBlocked

            raise PromotionBlocked("untrusted ancestor blocked")
        return "core-promoted"


class ActionEnginePromotionProvenanceTests(unittest.TestCase):
    def test_promote_to_core_passes_promoted_from_memory_id(self):
        from core.actions.action_engine import ActionEngine

        mem = _FakeMemory({"raw-safe": "owner said continuity matters"})
        engine = ActionEngine(memory=mem)

        out = engine._do_promote_to_core_memory("raw-safe", "important")

        self.assertEqual(out, "Promoted to core: core-promoted")
        self.assertEqual(len(mem.store_core_calls), 1)
        call = mem.store_core_calls[0]
        self.assertEqual(call["source"], "promotion")
        self.assertEqual(call["promoted_from"], ["raw-safe"])
        # Safety contract: the action surface must NOT silently opt in
        # to untrusted-ancestor promotion. The default (False) is the
        # only acceptable value here until an explicit override
        # primitive lands.
        self.assertFalse(call["allow_untrusted_ancestors"])

    def test_promote_to_core_missing_memory_does_not_write_core(self):
        from core.actions.action_engine import ActionEngine

        mem = _FakeMemory({})
        engine = ActionEngine(memory=mem)

        out = engine._do_promote_to_core_memory("raw-missing", "important")

        self.assertIn("not found", out)
        self.assertEqual(mem.store_core_calls, [])

    def test_untrusted_ancestor_block_surfaces_as_failed_action(self):
        from core.actions.action_engine import ActionEngine

        mem = _FakeMemory({"raw-evil": "external claim"}, block=True)
        engine = ActionEngine(memory=mem)

        result = engine.promote_to_core_memory("raw-evil", "seems useful")

        self.assertFalse(result.success)
        self.assertIn("untrusted ancestor blocked", result.error)
        self.assertEqual(mem.store_core_calls[0]["promoted_from"], ["raw-evil"])
        # Symmetry with the happy-path safety check: a future "let's
        # silence this gate temporarily" edit could pass
        # allow_untrusted_ancestors=True and this test would otherwise
        # still pass (because the fake raises unconditionally on
        # block=True). Lock the contract: the wiring must NEVER
        # opt-in.
        self.assertFalse(
            mem.store_core_calls[0]["allow_untrusted_ancestors"]
        )
