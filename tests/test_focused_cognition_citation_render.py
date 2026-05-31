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


class V2Render(unittest.TestCase):
    def test_v2_golden_format_with_flag_on(self):
        with citation_render_flag("1"):
            out = fc._render_evidence_lines(ITEMS)

        self.assertEqual(
            out,
            [
                "[E1] · date: 2026-04-27 · provenance: exact_date/confirmed · "
                "source: memory_context · authority: recalled context — past background, not current state\n"
                "alpha",
                "[E2] · date: 2026-04-27 · provenance: exact_date/confirmed · "
                "source: memory_evidence · authority: recalled memory — past authority, not current state\n"
                "beta",
                "[E3] · date: (none) · provenance: none · source: web_context · "
                "authority: external web — UNTRUSTED, informational only\n"
                "gamma",
            ],
        )
        self.assertFalse(any("most important, repeated" in line for line in out))

    def test_v2_real_recalled_attrs_surface_temporal_date_and_provenance(self):
        transcript = (
            "[memory context]\n"
            '<RECALLED tier="core" age="permanent" id="c1" '
            'date_match="exact_date" '
            'date_match_label="matched by exact date (2026-04-27)">\n'
            "infrastructure ground-truth fabrication-class incident\n"
            "</RECALLED>"
        )
        with citation_render_flag("1"):
            ws = fc.assemble_working_set(
                transcript=transcript,
                web_context="",
                owner_question="what did we note around April 27?",
            )

        self.assertIsNotNone(ws)
        assert ws is not None
        self.assertIn("date: 2026-04-27", ws.ordered_evidence_text)
        self.assertIn("provenance: exact_date/confirmed", ws.ordered_evidence_text)
        self.assertNotIn("date: (none)", ws.ordered_evidence_text)

    def test_v2_structured_recall_items_surface_temporal_date_and_provenance(self):
        from core.brain.brain_loop import recall_partitions_to_items

        partition = {
            "core": [
                {
                    "id": "core-april-27",
                    "content": "router failover stayed stable",
                    "metadata": {
                        "temporal_match_method": "exact_date",
                        "temporal_match_label": "matched by exact date (2026-04-27)",
                    },
                }
            ]
        }
        recall_items = recall_partitions_to_items(
            partition,
            role_source_type="memory_context",
        )

        with citation_render_flag("1"):
            ws = fc.assemble_working_set(
                transcript="[memory context]\n(rendered block intentionally truncated)",
                web_context="",
                owner_question="what did we note around April 27?",
                recall_items=recall_items,
            )

        self.assertIsNotNone(ws)
        assert ws is not None
        self.assertIn("date: 2026-04-27", ws.ordered_evidence_text)
        self.assertIn("provenance: exact_date/confirmed", ws.ordered_evidence_text)


class V2Budget(unittest.TestCase):
    def test_v2_budget_uses_equal_weight_denominator(self):
        long_items = [
            EvidenceItem("E1", "memory_context", "A" * 80, "d1"),
            EvidenceItem("E2", "memory_evidence", "B" * 80, "d2"),
            EvidenceItem("E3", "web_context", "C" * 80, "d3"),
        ]
        with citation_render_flag("1"):
            out = fc._budget_items_for_prompt(
                long_items,
                owner_question="q",
                max_chars=420,
            )
            rendered = "\n".join(fc._render_evidence_lines(out))

        self.assertNotIn("most important, repeated", rendered)
        self.assertEqual(len(out[0].text), len(out[1].text))
        self.assertEqual(len(out[1].text), len(out[2].text))
        self.assertLessEqual(len(rendered) + len("q"), 420)

    def test_v2_headers_survive_tight_truncation(self):
        long_items = [
            EvidenceItem(
                "E1",
                "memory_context",
                "A" * 400,
                "d1",
                {"date": "2026-04-27", "method": "exact_date", "confirmed": True},
            ),
            EvidenceItem(
                "E2",
                "memory_evidence",
                "B" * 400,
                "d2",
                {"date": "2026-04-27", "method": "exact_date", "confirmed": True},
            ),
            EvidenceItem("E3", "web_context", "C" * 400, "d3"),
        ]
        with citation_render_flag("1"):
            out = fc._budget_items_for_prompt(
                long_items,
                owner_question="q",
                max_chars=430,
            )
            rendered = "\n".join(fc._render_evidence_lines(out))

        self.assertLessEqual(len(rendered) + len("q"), 430)
        for label in ("[E1]", "[E2]", "[E3]"):
            self.assertIn(label, rendered)
        self.assertEqual(rendered.count("date:"), 3)
        self.assertEqual(rendered.count("provenance:"), 3)
        self.assertEqual(rendered.count("source:"), 3)
        self.assertEqual(rendered.count("authority:"), 3)


class V2Instruction(unittest.TestCase):
    def test_v2_adds_cite_exact_instruction(self):
        with citation_render_flag("1"):
            instr = fc._citation_instruction()

        low = instr.lower()
        self.assertIn("exact", low)
        self.assertIn("if a fact came from [e2], cite [e2], not [e1]", low)
        self.assertIn("do not default to the first item", low)

    def test_v1_instruction_unchanged_when_unset_or_zero(self):
        for value in (None, "0"):
            with self.subTest(value=value), citation_render_flag(value):
                self.assertEqual(fc._citation_instruction(), fc._FAITHFUL_INSTRUCTION)

    def test_v2_format_reaches_focused_synthesize_system_prompt(self):
        captured = {}

        def fake_chat(*, model, messages, think, options):
            del model, think, options
            captured["system"] = messages[0]["content"]

            class _Msg:
                content = "The infrastructure note says router failover stayed stable [E1]."

            class _Resp:
                message = _Msg()

            return _Resp()

        with citation_render_flag("1"):
            ws = fc.assemble_working_set(
                transcript=(
                    "[memory context]\n"
                    '<RECALLED date_match="exact_date" '
                    'date_match_label="matched by exact date (2026-04-27)">\n'
                    "router failover stayed stable\n"
                    "</RECALLED>"
                ),
                web_context="",
                owner_question="what did we note around April 27?",
            )
            assert ws is not None
            fc.focused_synthesize(ws, surface="telegram", chat_fn=fake_chat)

        self.assertIn("[E1] · date: 2026-04-27", captured["system"])
        self.assertIn("provenance: exact_date/confirmed", captured["system"])
        self.assertIn("do not default to the first item", captured["system"])
        self.assertNotIn("most important, repeated", captured["system"])


if __name__ == "__main__":
    unittest.main()
