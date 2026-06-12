from __future__ import annotations

import os
import unittest


class PageReadFlagTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_PAGE_READ_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_PAGE_READ_ENABLED", None))

    def test_default_off(self):
        from core.search.sense_flag import page_read_enabled

        self.assertFalse(page_read_enabled())

    def test_on_when_set(self):
        from core.search.sense_flag import page_read_enabled

        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        self.assertTrue(page_read_enabled())


if __name__ == "__main__":
    unittest.main()
