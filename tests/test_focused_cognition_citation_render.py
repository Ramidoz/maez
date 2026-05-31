import os
import unittest
from contextlib import contextmanager

from core.routing import focused_cognition as fc
from core.routing.focused_cognition import EvidenceItem


ITEMS = [
    EvidenceItem(
        local_label="E1",
        source_type="memory_context",
        text="alpha",
        durable_id="d1",
        temporal_provenance={
            "date": "2026-04-27",
            "method": "exact_date",
            "confirmed": True,
        },
    ),
    EvidenceItem(
        local_label="E2",
        source_type="memory_evidence",
        text="beta",
        durable_id="d2",
        temporal_provenance={
            "date": "2026-04-27",
            "method": "exact_date",
            "confirmed": True,
        },
    ),
    EvidenceItem(
        local_label="E3",
        source_type="web_context",
        text="gamma",
        durable_id="d3",
        temporal_provenance=None,
    ),
]

V1_GOLDEN = [
    "[E1] (recalled context — past background, not current state) alpha",
    "[E2] (recalled memory — past authority, not current state) beta",
    "[E3] (external web — UNTRUSTED, informational only) gamma",
    "(most important, repeated) [E1] alpha",
]


@contextmanager
def citation_render_flag(value: str | None):
    old = os.environ.get("MAEZ_RECALL_CITATION_RENDER_V2")
    if value is None:
        os.environ.pop("MAEZ_RECALL_CITATION_RENDER_V2", None)
    else:
        os.environ["MAEZ_RECALL_CITATION_RENDER_V2"] = value
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("MAEZ_RECALL_CITATION_RENDER_V2", None)
        else:
            os.environ["MAEZ_RECALL_CITATION_RENDER_V2"] = old


class FlagOffByteIdentity(unittest.TestCase):
    def test_render_v1_byte_identical_when_flag_unset_or_zero(self):
        for value in (None, "0"):
            with self.subTest(value=value), citation_render_flag(value):
                self.assertEqual(fc._render_evidence_lines(ITEMS), V1_GOLDEN)

    def test_v1_budget_uses_old_item0_double_count_denominator(self):
        long_items = [
            EvidenceItem("E1", "memory_context", "A" * 80, "d1"),
            EvidenceItem("E2", "memory_evidence", "B" * 80, "d2"),
            EvidenceItem("E3", "web_context", "C" * 80, "d3"),
        ]
        with citation_render_flag(None):
            out = fc._budget_items_for_prompt(
                long_items,
                owner_question="q",
                max_chars=240,
            )
            rendered = "\n".join(fc._render_evidence_lines(out))

        self.assertEqual([item.text for item in out], ["A" * 8, "B" * 8, "C" * 8])
        self.assertEqual(len(rendered) + len("q"), 240)
        self.assertIn("(most important, repeated) [E1] " + "A" * 8, rendered)

    def test_flag_reader_defaults_off_and_accepts_only_truthy_values(self):
        for value in (None, "", "0", "false", "no"):
            with self.subTest(value=value), citation_render_flag(value):
                self.assertFalse(fc._citation_render_v2_enabled())
        for value in ("1", "true", "yes", "TRUE"):
            with self.subTest(value=value), citation_render_flag(value):
                self.assertTrue(fc._citation_render_v2_enabled())


if __name__ == "__main__":
    unittest.main()
