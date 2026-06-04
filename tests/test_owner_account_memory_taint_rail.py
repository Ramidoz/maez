from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


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
    return {
        "id": row_id,
        "content": content,
        "metadata": meta,
        "distance": 0.123,
    }


class ProvenancedRecallRendererTests(unittest.TestCase):
    def test_provenanced_text_matches_existing_string_renderer(self):
        recalled = {
            "core": [{"id": "core-a", "content": "core continuity", "metadata": {}}],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                ),
                _raw_row("raw-ordinary", "ordinary memory"),
            ],
        }
        mm = _mm()

        text = mm.format_for_prompt(recalled, max_chars=8000)
        provenanced = mm.format_for_prompt_provenanced(recalled, max_chars=8000)

        self.assertEqual(provenanced.text, text)

    def test_owner_account_row_gets_owner_account_span(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                )
            ],
        }

        provenanced = _mm().format_for_prompt_provenanced(recalled)
        owner_spans = [
            span for span in provenanced.spans
            if "OWNER_ACCOUNT_MEMORY_CANARY" in span.text
        ]

        self.assertTrue(owner_spans)
        self.assertTrue(
            all(span.origin_class == "owner_account_context" for span in owner_spans)
        )
        self.assertTrue(all(not span.redaction_allowed for span in owner_spans))

    def test_mixed_recall_uses_per_row_spans(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                ),
                _raw_row("raw-ordinary", "ORDINARY_MEMORY_CANARY"),
            ],
        }

        provenanced = _mm().format_for_prompt_provenanced(recalled)
        owner_origins = {
            span.origin_class
            for span in provenanced.spans
            if "OWNER_ACCOUNT_MEMORY_CANARY" in span.text
        }
        ordinary_origins = {
            span.origin_class
            for span in provenanced.spans
            if "ORDINARY_MEMORY_CANARY" in span.text
        }

        self.assertEqual(owner_origins, {"owner_account_context"})
        self.assertEqual(ordinary_origins, {"memory"})
        self.assertIn("owner_account_context", {s.origin_class for s in provenanced.spans})
        self.assertIn("memory", {s.origin_class for s in provenanced.spans})

    def test_legacy_rows_have_no_owner_account_span(self):
        recalled = {
            "core": [{"id": "core-a", "content": "legacy core", "metadata": {}}],
            "daily": [],
            "raw": [_raw_row("raw-ordinary", "legacy raw")],
        }

        provenanced = _mm().format_for_prompt_provenanced(recalled)

        self.assertNotIn(
            "owner_account_context",
            {span.origin_class for span in provenanced.spans},
        )
        self.assertIn("memory", {span.origin_class for span in provenanced.spans})


if __name__ == "__main__":
    unittest.main()
