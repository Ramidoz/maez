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
            lines, segs, _ = FC._render_evidence_lines_contained(
                [_web_item("hi"), _mem_item("m")], render_version="v1", nonce="abcd", contain_enabled=False)
        self.assertEqual(segs, 0)
        self.assertNotIn("<<EXT:", "\n".join(lines))
        self.assertEqual(lines, FC._render_evidence_lines([_web_item("hi"), _mem_item("m")], render_version="v1"))

    def test_flag_on_wraps_web_only_and_counts_v1_repeat(self):
        lines, segs, _ = FC._render_evidence_lines_contained(
            [_web_item("hi"), _mem_item("m")], render_version="v1", nonce="abcd", contain_enabled=True)
        joined = "\n".join(lines)
        self.assertEqual(segs, 2)  # top web item rendered twice (main + repeat)
        self.assertEqual(joined.count("<<EXT:abcd>>"), 2)
        self.assertEqual(joined.count("<</EXT:abcd>>"), 2)
        self.assertIn("source=web_context", joined)
        self.assertIn("digest=dig1", joined)
        self.assertNotIn("<<EXT:abcd>> m", joined)  # memory item not wrapped

    def test_v2_no_repeat_single_segment(self):
        lines, segs, _ = FC._render_evidence_lines_contained(
            [_web_item("hi")], render_version="v2", nonce="abcd", contain_enabled=True)
        self.assertEqual(segs, 1)
        self.assertEqual("\n".join(lines).count("<<EXT:abcd>>"), 1)


class FocusedContainmentWebDigestsTest(unittest.TestCase):
    def test_helper_returns_web_digests_regardless_of_position(self):
        # memory FIRST, web SECOND -> the returned web digests come from the WEB item, not items[0]
        lines, segs, web_digests = FC._render_evidence_lines_contained(
            [_mem_item("m"), _web_item("hi")], render_version="v2",
            nonce="abcd", contain_enabled=True)
        self.assertEqual(segs, 1)
        self.assertEqual(web_digests, ["dig1"])  # _web_item uses durable_id="dig1"; _mem_item uses "dig2"
        self.assertNotIn("dig2", web_digests)

    def test_v1_repeat_web_digests_count(self):
        # top item is web -> wrapped twice -> two render entries, same durable_id
        lines, segs, web_digests = FC._render_evidence_lines_contained(
            [_web_item("hi"), _mem_item("m")], render_version="v1",
            nonce="abcd", contain_enabled=True)
        self.assertEqual(segs, 2)
        self.assertEqual(web_digests, ["dig1", "dig1"])


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

    def test_receipt_digest_identifies_web_item_not_first_item(self):
        # memory_evidence (priority=1) ranks before web_context (priority=2), so E1 is memory,
        # E2+ are web. The emitted receipt digest must identify the web item's hash, not memory's.
        # We patch emit_receipt to capture the dict instead of logging.
        from core.routing import web_containment as _wc
        captured: list[dict] = []
        mem_transcript = "[memory evidence]\nsome recalled fact about the user"
        web_text = "breaking news headline from the web"
        with (
            mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}),
            mock.patch.object(_wc, "emit_receipt", side_effect=captured.append),
        ):
            ws = FC.assemble_working_set(
                transcript=mem_transcript,
                web_context=web_text,
                owner_question="news?",
            )
        self.assertIsNotNone(ws, "working set must be produced")
        self.assertEqual(len(captured), 1, "exactly one receipt must be emitted")
        receipt = captured[0]
        # The digest in the receipt must be derived from the web item's durable_id
        # (a content-hash of web_text), NOT from the memory item's durable_id.
        from core.routing.focused_cognition import _content_hash
        web_hash = _content_hash(web_text)
        mem_hash = _content_hash("some recalled fact about the user")
        self.assertIn(web_hash, receipt["digest"],
                      "receipt digest must identify the contained web segment")
        self.assertNotIn(mem_hash, receipt["digest"],
                         "receipt digest must NOT be the memory item's hash")
