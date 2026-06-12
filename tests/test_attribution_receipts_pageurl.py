import unittest

from core.routing.attribution_render import stash_turn_evidence, pop_turn_evidence


class _Sum:
    def __init__(self, source):
        self.source = source


class _Turn:
    def __init__(self, summaries):
        self.source_summaries = summaries


class PageUrlReceiptTest(unittest.TestCase):
    def test_page_read_url_added_even_when_absent_from_evidence_text(self):
        # G2: a page-read's URL often does NOT appear in the page body text, so
        # extract_source_urls returns nothing; the read URL must be unioned in.
        turn = _Turn([_Sum("FETCH_URL")])
        stash_turn_evidence(
            "c1",
            rendered_turn=turn,
            evidence_texts=["page body with no link in it"],
            observation=None,
            extra_source_urls=["https://example.com/page"],
        )
        rec = pop_turn_evidence("c1")
        self.assertIn("https://example.com/page", rec["sources"])
        self.assertTrue(rec["web_present"])

    def test_extra_urls_deduped_against_text_urls(self):
        turn = _Turn([_Sum("FETCH_URL")])
        stash_turn_evidence(
            "c2",
            rendered_turn=turn,
            evidence_texts=["see https://example.com/page for more"],
            observation=None,
            extra_source_urls=["https://example.com/page"],
        )
        rec = pop_turn_evidence("c2")
        self.assertEqual(rec["sources"].count("https://example.com/page"), 1)

    def test_no_extra_urls_keeps_today_behavior(self):
        turn = _Turn([_Sum("WEB_SEARCH")])
        stash_turn_evidence(
            "c3",
            rendered_turn=turn,
            evidence_texts=["body http://found.com/x here"],
            observation=None,
        )
        rec = pop_turn_evidence("c3")
        self.assertIn("http://found.com/x", rec["sources"])
