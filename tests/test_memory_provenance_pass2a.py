# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5x.B Pass 2a — external/system ingress provenance.

Pass 2a tags two confirmed call sites:

  - skills/reddit_skill.py    -> external_web / untrusted
  - scripts/backup/restore_writer.py -> system / covenant

These tests assert the resulting metadata shape on the
``MemoryManager`` write side. Behavioural recall is unchanged in
5x.B; surfacing/gating arrive in 5x.C and 5x.D."""

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
    from memory.memory_manager import MemoryManager
    mm = MemoryManager.__new__(MemoryManager)
    mm.raw = _FakeCollection()
    mm.core = _FakeCollection()
    return mm


# ── reddit_skill: external_web / untrusted ──────────────────────────


class RedditSkillProvenanceTests(unittest.TestCase):
    """The reddit ingest path is the canonical external_web write
    site. The Zombie Agents threat model treats this as the source
    most likely to carry adversarial content."""

    def _emit_reddit_post(self, mm, post_id="abc123"):
        # Mirror the live call shape at skills/reddit_skill.py:176
        # post-Pass-2a: provenance kwargs added on top of the
        # existing freeform `source=reddit/r/...` metadata.
        return mm.store(
            "reddit post body",
            cycle=99,
            metadata={
                "type": "reddit_post",
                "source": "reddit/r/LocalLLaMA",
                "reddit_post_id": post_id,
                "reddit_subreddit": "LocalLLaMA",
                "reddit_score": 42,
                "reddit_comments": 7,
                "reddit_flair": "Discussion",
            },
            provenance_source="external_web",
            trust_tier="untrusted",
        )

    def test_reddit_post_carries_external_untrusted_provenance(self):
        mm = _mm()
        self._emit_reddit_post(mm)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["provenance_source"], "external_web")
        self.assertEqual(meta["trust_tier"], "untrusted")

    def test_reddit_post_preserves_existing_freeform_source(self):
        """The existing freeform ``source=reddit/r/...`` field MUST
        coexist with the new ``provenance_source`` enum. They are not
        the same field; conflating them would silently break the
        per-subreddit topic routing this metadata supports today."""
        mm = _mm()
        self._emit_reddit_post(mm)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["source"], "reddit/r/LocalLLaMA")
        self.assertEqual(meta["type"], "reddit_post")
        self.assertEqual(meta["reddit_post_id"], "abc123")
        self.assertEqual(meta["reddit_subreddit"], "LocalLLaMA")


# ── restore_writer: system / covenant ───────────────────────────────


class RestoreWriterProvenanceTests(unittest.TestCase):
    """The restore-writer path emits the coma core-memory after a
    hardware-failure restore. Tagged system/covenant because the
    body is schema-derived from canonical timestamps; this is
    exactly the trust gradient covenant exists for."""

    def test_hardware_failure_restore_writes_system_covenant(self):
        from scripts.backup.restore_writer import write_restoration_record

        captured = []

        class FakeMM:
            # Pass 2a contract: the production restore_writer adds
            # provenance kwargs to its store_core call. Test mocks
            # MUST accept them so the TypeError fallback path in the
            # production code does not silently drop provenance.
            def store_core(self, content, source=None, *,
                           provenance_source=None, trust_tier=None):
                captured.append({
                    "content": content,
                    "source": source,
                    "provenance_source": provenance_source,
                    "trust_tier": trust_tier,
                })
                return "core-fake-id"

        write_restoration_record(
            mm=FakeMM(),
            snapshot_timestamp="2026-04-30T06-00-00",
            restore_timestamp="2026-04-30T10-15-00",
            reason="hardware-failure",
        )
        self.assertEqual(len(captured), 1)
        rec = captured[0]
        self.assertEqual(rec["provenance_source"], "system")
        self.assertEqual(rec["trust_tier"], "covenant")
        # Existing freeform source field MUST still carry the
        # restoration_event_<ts> tag — Pass 2a does not overload it.
        self.assertTrue(rec["source"].startswith("restoration_event_"))

    def test_legacy_mm_falls_through_chain_with_warning(self):
        """A legacy FakeMM that rejects the provenance kwargs must
        still result in a successful core memory write through the
        outer TypeError fallback. Guards against future refactors
        that break the chain order — the production system path
        must keep restore-writing even with old mocks."""
        from scripts.backup.restore_writer import write_restoration_record

        captured = []

        class LegacyFakeMM:
            # Predates Pass 2a — does NOT accept provenance kwargs.
            def store_core(self, content, source=None):
                captured.append({"content": content, "source": source})
                return "core-legacy-id"

        with self.assertLogs(
            "scripts.backup.restore_writer",
            level="WARNING",
        ) as log_ctx:
            result = write_restoration_record(
                mm=LegacyFakeMM(),
                snapshot_timestamp="2026-04-30T06-00-00",
                restore_timestamp="2026-04-30T10-15-00",
                reason="hardware-failure",
            )
        self.assertEqual(result["core_memory_id"], "core-legacy-id")
        self.assertEqual(len(captured), 1)
        # The covenant tag did NOT land on this row (legacy mock); the
        # warning must surface so an operator can notice.
        self.assertTrue(any(
            "rejected provenance kwargs" in m for m in log_ctx.output
        ))


class RestoreWriterFallbackChainTests(unittest.TestCase):
    def test_oldest_mm_falls_through_to_positional_call(self):
        """An ancient FakeMM that doesn't accept ``source=`` either
        must still complete the write through the inner-most fallback,
        with a SECOND warning so the double-degrade is visible."""
        from scripts.backup.restore_writer import write_restoration_record

        captured = []

        class AncientFakeMM:
            def store_core(self, content):
                captured.append(content)
                return "core-ancient-id"

        with self.assertLogs(
            "scripts.backup.restore_writer",
            level="WARNING",
        ) as log_ctx:
            result = write_restoration_record(
                mm=AncientFakeMM(),
                snapshot_timestamp="2026-04-30T06-00-00",
                restore_timestamp="2026-04-30T10-15-00",
                reason="hardware-failure",
            )
        self.assertEqual(result["core_memory_id"], "core-ancient-id")
        self.assertEqual(len(captured), 1)
        # Both warnings must have fired (provenance + source dropped).
        joined = "\n".join(log_ctx.output)
        self.assertIn("rejected provenance kwargs", joined)
        self.assertIn("rejected source kwarg", joined)


if __name__ == "__main__":
    unittest.main()
