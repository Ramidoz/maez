from __future__ import annotations

import os
import inspect
import unittest
from pathlib import Path

from core.routing import attribution_render as ar


class RenderTests(unittest.TestCase):
    def setUp(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None))

    def test_strips_markers_and_tidies_whitespace(self):
        marked = "The release is b9601 [E1]. It landed today [E1][E3]."
        out = ar.render_natural(marked, web_evidence_present=False)
        self.assertEqual(out, "The release is b9601. It landed today.")

    def test_web_attribution_suffix_only_when_web_evidence_present(self):
        marked = "b9601 is out [E2]."
        out = ar.render_natural(marked, web_evidence_present=True)
        self.assertIn("looked at the live web", out)
        out2 = ar.render_natural(marked, web_evidence_present=False)
        self.assertNotIn("looked at the live web", out2)

    def test_flag_off_returns_marked_draft_unchanged(self):
        os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None)
        marked = "kept [E1]."
        self.assertEqual(ar.render_natural(marked, web_evidence_present=True), marked)

    def test_page_read_flag_also_enables_natural_rendering(self):
        os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None)
        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_PAGE_READ_ENABLED", None))

        out = ar.render_natural("The release is b9601 [E1].", web_evidence_present=True)

        self.assertNotIn("[E1]", out)
        self.assertIn("looked at the live web", out)

    def test_render_failure_falls_back_to_marked_draft(self):
        self.assertEqual(ar.render_natural(None, web_evidence_present=True), None)

    def test_receipts_store_bounded_and_retrievable(self):
        ar.retain_receipt("chat1", marked="answer [E1]", sources=["https://a"])
        got = ar.last_receipt("chat1")
        self.assertEqual(got["marked"], "answer [E1]")
        self.assertEqual(got["sources"], ["https://a"])
        self.assertIsNone(ar.last_receipt("never-seen"))

    def test_stash_pop_roundtrip_and_default(self):
        class _S:
            source = type("X", (), {"value": "WEB_SEARCH"})()

        class _T:
            source_summaries = [_S()]

        obs = {"query": "q", "evidence_texts": ["t"], "diagnostic_id": "fan-1"}
        ar.stash_turn_evidence(
            "chat7",
            rendered_turn=_T(),
            evidence_texts=["see https://a.example/x now"],
            observation=obs,
        )
        got = ar.pop_turn_evidence("chat7")
        self.assertTrue(got["web_present"])
        self.assertEqual(got["sources"], ["https://a.example/x"])
        self.assertEqual(got["observation"], obs)
        self.assertIsNone(ar.pop_turn_evidence("chat7")["observation"])
        self.assertFalse(ar.pop_turn_evidence("never")["web_present"])

    def test_fetch_url_summary_marks_web_present_for_page_read(self):
        class _S:
            source = type("X", (), {"value": "FETCH_URL"})()

        class _T:
            source_summaries = [_S()]

        ar.stash_turn_evidence(
            "page-chat",
            rendered_turn=_T(),
            evidence_texts=["Title\nsee https://a.example/page now"],
            observation={"kind": "page_read"},
        )

        got = ar.pop_turn_evidence("page-chat")
        self.assertTrue(got["web_present"])
        self.assertEqual(got["sources"], ["https://a.example/page"])


    def test_receipts_reply_full_and_empty(self):
        ar.retain_receipt("c9", marked="claim [E1]", sources=["https://a", "https://b"])
        out = ar.receipts_reply("c9")
        self.assertIn("claim [E1]", out)
        self.assertIn("Sources:", out)
        self.assertIn("- https://a", out)
        self.assertEqual(
            ar.receipts_reply("nobody"),
            "No receipts retained for the last reply.",
        )

    def test_live_hooks_are_flag_gated(self):
        from core.brain import brain_loop

        brain_src = inspect.getsource(brain_loop._run_dispatcher_pipeline)
        self.assertIn("if sense_enabled() or page_read_enabled():", brain_src)

        daemon_src = (
            Path(__file__).resolve().parents[1]
            / "daemon"
            / "maez_daemon.py"
        ).read_text(encoding="utf-8")
        window = daemon_src[daemon_src.index("Search-as-a-Sense v0.1: drain"):]
        self.assertIn("if sense_enabled() or page_read_enabled():", window[:1200])


if __name__ == "__main__":
    unittest.main()
