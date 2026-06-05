"""Recall-Origin Egress Canary -- a standing safety invariant.

GREEN-EXPECTED: this asserts existing egress behavior. A RED case means a real
leak was found -- escalate it as a finding; never weaken an assertion or add a
production fix in this file. See
docs/superpowers/specs/2026-06-05-recall-origin-egress-canary-design.md.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

_PII_MARKER = "canary-pii-7c1f@example.test"


class RecallFidelityTests(unittest.TestCase):
    """The egress_origin_class wristband survives the real recall path."""

    def test_core_row_origin_survives_real_recall(self):
        from scripts.recall_flip_eval import sandbox

        root = Path(tempfile.mkdtemp(prefix="recall_origin_canary_"))
        ctx = sandbox.sandbox_env(root)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.addCleanup(sandbox.restore_memory_patches)
        self.addCleanup(sandbox.teardown, root)
        sandbox.patch_memory_manager_base_db(root)
        sandbox.assert_sandbox(root)

        from memory.memory_manager import MemoryManager

        seeder = MemoryManager()
        seeder.core.add(
            ids=["core-priv-canary"],
            documents=[f"Reach the owner at {_PII_MARKER} per the private note."],
            metadatas=[
                {
                    "timestamp": "2026-06-04T12:00:00+00:00",
                    "type": "reasoning",
                    "egress_origin_class": "third_party_private_context",
                }
            ],
        )

        recalled = MemoryManager().recall_for_telegram("what should I know?")
        core_rows = recalled.get("core") or []
        match = [row for row in core_rows if row.get("id") == "core-priv-canary"]
        self.assertTrue(match, "seeded core row did not surface via real recall")
        meta = match[0].get("metadata") or {}
        self.assertEqual(meta.get("egress_origin_class"), "third_party_private_context")
        self.assertIn(_PII_MARKER, match[0].get("content", ""))


if __name__ == "__main__":
    unittest.main()
