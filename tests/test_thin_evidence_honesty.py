import unittest
from unittest import mock


def _result(query, results, count=None):
    return {
        "success": bool(results),
        "results": results,
        "result_count": count if count is not None else len(results),
        "query": query,
        "timestamp": "2026-06-16",
    }


class ThinSignalRenderTest(unittest.TestCase):
    def _render(self, result, *, flag="1", include_quality=True):
        from skills import web_search

        with mock.patch.dict(
            "os.environ",
            {"MAEZ_THIN_EVIDENCE_HONESTY_ENABLED": flag},
            clear=False,
        ):
            return web_search.format_for_context(
                result, include_quality=include_quality
            )

    def test_thin_when_few_results(self):
        out = self._render(
            _result("q", [{"title": "T", "snippet": "x" * 100, "url": "u"}])
        )
        self.assertIn("quality=thin result_count=1", out.splitlines()[0])

    def test_thin_when_short_snippets(self):
        results = [{"title": "T", "snippet": "short", "url": "u"} for _ in range(3)]
        out = self._render(_result("q", results))
        self.assertIn("quality=thin", out.splitlines()[0])

    def test_adequate_when_enough(self):
        results = [{"title": "T", "snippet": "y" * 200, "url": "u"} for _ in range(3)]
        out = self._render(_result("q", results))
        self.assertIn(
            "quality=adequate result_count=3 snippet_chars=600",
            out.splitlines()[0],
        )

    def test_default_does_not_emit_quality_line(self):
        result = _result("q", [{"title": "T", "snippet": "x", "url": "u"}])
        out = self._render(result, include_quality=False)
        self.assertNotIn("quality=", out)
        self.assertTrue(out.startswith("[WEB SEARCH: 'q'] 1 results"))

    def test_flag_off_byte_identical_and_dict_unmutated(self):
        result = _result("q", [{"title": "T", "snippet": "x", "url": "u"}])
        out = self._render(result, flag="0", include_quality=True)
        self.assertNotIn("quality=", out)
        self.assertNotIn("result_quality", result)
        self.assertTrue(out.startswith("[WEB SEARCH: 'q'] 1 results"))


class ThinParseTest(unittest.TestCase):
    def test_anchored_quality_thin_line_sets_thin(self):
        from core.routing.evidence_state import turn_evidence_state

        web_context = (
            "[WEB SEARCH: 'q'] quality=thin result_count=1 snippet_chars=80\n"
            "[WEB SEARCH: 'q'] 1 results - t\n"
            "  1. T\n"
            "     s"
        )
        self.assertTrue(
            turn_evidence_state(transcript="", web_context=web_context).thin_evidence
        )

    def test_dispatcher_fresh_evidence_prefix_parses(self):
        from core.routing.evidence_state import turn_evidence_state

        transcript = (
            "[fresh evidence] [WEB SEARCH: 'q'] "
            "quality=thin result_count=2 snippet_chars=120"
        )
        self.assertTrue(
            turn_evidence_state(transcript=transcript, web_context="").thin_evidence
        )

    def test_adequate_line_not_thin(self):
        from core.routing.evidence_state import turn_evidence_state

        web_context = (
            "[WEB SEARCH: 'q'] quality=adequate result_count=3 snippet_chars=600"
        )
        self.assertFalse(
            turn_evidence_state(transcript="", web_context=web_context).thin_evidence
        )


class DaemonDirectiveTest(unittest.TestCase):
    def _state(self, thin):
        from core.routing.evidence_state import EvidenceState

        return EvidenceState(
            evidence_present=True,
            marker_labels=("web search results",),
            descriptions=("web summary",),
            thin_evidence=thin,
        )

    def test_thin_emits_hedge_and_suppresses_confidence_clause(self):
        from core.routing.evidence_state import build_evidence_precedence_directive

        out = build_evidence_precedence_directive(self._state(True))
        self.assertIn("THIN", out)
        self.assertIn("limited information", out)
        self.assertNotIn("You may NOT claim the relevant source", out)
        self.assertNotIn("refuse", out.lower())

    def test_adequate_keeps_normal_directive(self):
        from core.routing.evidence_state import build_evidence_precedence_directive

        out = build_evidence_precedence_directive(self._state(False))
        self.assertIn("You may NOT claim the relevant source", out)
        self.assertNotIn("THIN", out)

    def test_midline_page_text_does_not_spoof(self):
        from core.routing.evidence_state import turn_evidence_state

        web_context = (
            "[WEB SEARCH: 'q'] 1 results - t\n"
            "  1. Blog\n"
            "     our data quality=thin per the report"
        )
        self.assertFalse(
            turn_evidence_state(transcript="", web_context=web_context).thin_evidence
        )
