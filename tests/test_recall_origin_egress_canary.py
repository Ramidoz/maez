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


def _mm():
    from memory.memory_manager import MemoryManager

    return MemoryManager.__new__(MemoryManager)


def _raw_row(row_id: str, content: str, *, egress_origin_class: str | None = None):
    meta = {
        "cycle": 7,
        "timestamp": "2026-06-04T12:00:00+00:00",
        "type": "reasoning",
    }
    if egress_origin_class:
        meta["egress_origin_class"] = egress_origin_class
    return {"id": row_id, "content": content, "metadata": meta, "distance": 0.123}


class LocalRenderFidelityTests(unittest.TestCase):
    def test_local_render_keeps_full_content(self):
        # COVENANT: local-first means the local render is full-fidelity; refusal
        # lives at the cloud door, never here. This asserts we do NOT lobotomize.
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-priv",
                    f"email {_PII_MARKER}",
                    egress_origin_class="third_party_private_context",
                )
            ],
        }
        rendered = _mm().format_for_prompt(recalled)
        self.assertIn(_PII_MARKER, rendered)

    def test_provenanced_render_carries_origin_span(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-priv",
                    f"email {_PII_MARKER}",
                    egress_origin_class="third_party_private_context",
                )
            ],
        }
        provenanced = _mm().format_for_prompt_provenanced(recalled)
        priv = [
            span
            for span in provenanced.spans
            if span.origin_class == "third_party_private_context"
        ]
        self.assertTrue(priv, "private-origin span missing from provenanced render")
        self.assertTrue(all(span.redaction_allowed for span in priv))
        self.assertIn(_PII_MARKER, provenanced.text)


if __name__ == "__main__":
    unittest.main()
