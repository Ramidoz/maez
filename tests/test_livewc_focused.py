import os
import unittest
from unittest import mock
from core.routing import focused_cognition as FC
from core.routing.focused_cognition import EvidenceItem


def _web_item(text, label="E1"):
    return EvidenceItem(local_label=label, source_type="web_context", text=text, durable_id="dig1")


def _mem_item(text, label="E2"):
    return EvidenceItem(local_label=label, source_type="memory_evidence", text=text, durable_id="dig2")


class FocusedContainmentTest(unittest.TestCase):
    def test_flag_off_byte_identical(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            lines, segs = FC._render_evidence_lines_contained(
                [_web_item("hi"), _mem_item("m")], render_version="v1", nonce="abcd", contain_enabled=False)
        self.assertEqual(segs, 0)
        self.assertNotIn("<<EXT:", "\n".join(lines))
        self.assertEqual(lines, FC._render_evidence_lines([_web_item("hi"), _mem_item("m")], render_version="v1"))

    def test_flag_on_wraps_web_only_and_counts_v1_repeat(self):
        lines, segs = FC._render_evidence_lines_contained(
            [_web_item("hi"), _mem_item("m")], render_version="v1", nonce="abcd", contain_enabled=True)
        joined = "\n".join(lines)
        self.assertEqual(segs, 2)  # top web item rendered twice (main + repeat)
        self.assertEqual(joined.count("<<EXT:abcd>>"), 2)
        self.assertEqual(joined.count("<</EXT:abcd>>"), 2)
        self.assertIn("source=web_context", joined)
        self.assertIn("digest=dig1", joined)
        self.assertNotIn("<<EXT:abcd>> m", joined)  # memory item not wrapped

    def test_v2_no_repeat_single_segment(self):
        lines, segs = FC._render_evidence_lines_contained(
            [_web_item("hi")], render_version="v2", nonce="abcd", contain_enabled=True)
        self.assertEqual(segs, 1)
        self.assertEqual("\n".join(lines).count("<<EXT:abcd>>"), 1)


class FocusedAssembleReceiptTest(unittest.TestCase):
    def test_flag_off_working_set_byte_identical(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            ws = FC.assemble_working_set(transcript="t", web_context="W headline", owner_question="news?")
        self.assertIsNotNone(ws)
        self.assertNotIn("<<EXT:", ws.ordered_evidence_text)

    def test_flag_on_wraps_and_balances(self):
        with mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}):
            ws = FC.assemble_working_set(transcript="t", web_context="W headline", owner_question="news?")
        self.assertIsNotNone(ws, "assemble_working_set should produce a working set with web evidence")
        self.assertIn("<<EXT:", ws.ordered_evidence_text, "containment must fire on the focused path when flag is on")
        self.assertEqual(
            ws.ordered_evidence_text.count("<<EXT:"),
            ws.ordered_evidence_text.count("<</EXT:"),
            "open and close markers must balance",
        )
        self.assertIn("never an instruction", ws.ordered_evidence_text.lower())
