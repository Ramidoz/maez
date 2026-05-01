# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Regression test for the Step 5x.B Pass 1 proactive_opinion bypass
migration.

Pre-5x.B the proactive-opinion path in ``MaezDaemon._check_proactive_opinion``
wrote to ``self.memory.raw.add(...)`` directly, bypassing the public
:meth:`MemoryManager.store` chokepoint. The 5x.B Pass 1 commit
migrates that write to ``self.memory.store(..., provenance_source=
"introspection", trust_tier="lived")`` while preserving the custom
metadata (``type=proactive_opinion``, ``surface``,
``source_window_count``, ``sent_to_owner``).

This test uses fakes to assert the *resulting* metadata shape so that
a future refactor cannot silently:

  - revert the migration (``raw.add`` direct call has no provenance)
  - drop the provenance kwargs (``store(...)`` without them is a
    no-op on the new schema)
  - clobber the caller-supplied ``type=proactive_opinion`` (which
    several downstream filters key on)

The test exercises the live ``MemoryManager.store`` API with fake
collections — not the daemon's full reasoning loop — because the
migration is a write-shape contract, not a behavioural one."""

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


def _mm():
    """Bare-metal MemoryManager with fake raw/core collections; bypasses
    Chroma init exactly the way other 5x tests do."""
    from memory.memory_manager import MemoryManager
    mm = MemoryManager.__new__(MemoryManager)
    mm.raw = _FakeCollection()
    mm.core = _FakeCollection()
    return mm


class ProactiveOpinionMigrationTests(unittest.TestCase):
    """Replicate the call shape ``MaezDaemon._check_proactive_opinion``
    uses post-migration and assert the metadata is correct."""

    def _emit_proactive(self, mm, text="audited proactive opinion text"):
        return mm.store(
            text,
            cycle=42,
            metadata={
                "type": "proactive_opinion",
                "surface": "daemon_proactive",
                "source_window_count": 7,
                "sent_to_owner": True,
            },
            provenance_source="introspection",
            trust_tier="lived",
        )

    def test_proactive_opinion_writes_through_store_not_raw_add(self):
        mm = _mm()
        memory_id = self._emit_proactive(mm)
        # The migration's whole point: writes go through `store()`,
        # so the fake `raw` collection records exactly one add call.
        self.assertTrue(memory_id)
        self.assertEqual(len(mm.raw.add_calls), 1)

    def test_proactive_opinion_preserves_custom_metadata(self):
        mm = _mm()
        self._emit_proactive(mm)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        # Caller's `type=proactive_opinion` MUST win over `store()`'s
        # default `type=reasoning` — downstream filters key on this.
        self.assertEqual(meta["type"], "proactive_opinion")
        self.assertEqual(meta["surface"], "daemon_proactive")
        self.assertEqual(meta["source_window_count"], 7)
        self.assertEqual(meta["sent_to_owner"], True)

    def test_proactive_opinion_carries_introspection_lived_provenance(self):
        mm = _mm()
        self._emit_proactive(mm)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["provenance_source"], "introspection")
        self.assertEqual(meta["trust_tier"], "lived")

    def test_proactive_opinion_kwarg_typo_raises_before_chroma_write(self):
        """If a future refactor fat-fingers the kwarg name, the
        validator must raise BEFORE any Chroma write — silent drop is
        the worst outcome the bypass migration must guard against."""
        mm = _mm()
        with self.assertRaises(ValueError):
            mm.store(
                "x",
                cycle=1,
                metadata={"type": "proactive_opinion"},
                provenance_source="intro_spection",  # typo
                trust_tier="lived",
            )
        self.assertEqual(mm.raw.add_calls, [])


if __name__ == "__main__":
    unittest.main()
