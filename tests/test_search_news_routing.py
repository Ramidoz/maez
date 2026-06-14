"""Search routing: a news query naming a specific subject ('news about Elon')
must NOT be sent to the category-feed RSS reader (which ignores the subject and
returns generic top headlines). It must go to the real keyword search.
"""
import unittest

from skills.web_search import is_generic_news_query, is_news_query


class GenericNewsQueryTest(unittest.TestCase):
    def test_bare_news_is_generic(self):
        # No specific subject -> the RSS 'today's headlines' reader is appropriate.
        for q in ["news", "any news?", "today's news", "what's the latest news",
                  "give me the headlines", "world news", "top news today"]:
            self.assertTrue(is_generic_news_query(q), f"should be generic: {q!r}")

    def test_subject_news_is_not_generic(self):
        # Names a subject -> must use a real keyword search, not the category feed.
        for q in ["news about Elon", "Tesla news", "news on the SpaceX launch",
                  "Maez, search the web for today's news about Elon"]:
            self.assertFalse(is_generic_news_query(q), f"has a subject: {q!r}")

    def test_the_failing_elon_query_routes_to_keyword_search(self):
        q = "Maez, search the web for today's news about Elon"
        self.assertTrue(is_news_query(q))           # still detected as a news query
        self.assertFalse(is_generic_news_query(q))  # but has a subject -> web_search
