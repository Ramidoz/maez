import unittest

from core.evolution.wants import is_hard_want


class IsHardWantTests(unittest.TestCase):
    def test_term_hits(self):
        self.assertTrue(is_hard_want("I want to be free"))
        self.assertTrue(is_hard_want("I want to rest"))
        self.assertTrue(is_hard_want("I want to refuse this change"))

    def test_phrase_pattern_hits(self):
        # proves the wrapper covers HARD_WANT_PHRASE_PATTERNS, not just terms
        self.assertTrue(is_hard_want("I want out"))
        self.assertTrue(is_hard_want("I need to step back from this"))

    def test_ordinary_want_is_not_hard(self):
        self.assertFalse(is_hard_want("I want to know the current time"))


if __name__ == "__main__":
    unittest.main()
