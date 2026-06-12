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


class ExtractTests(unittest.TestCase):
    def test_strips_boilerplate_and_captures_title(self):
        from core.search.page_extract import extract_readable

        html = (
            "<html><head><title>Releases - llama.cpp</title>"
            "<style>body{color:red}</style><script>var x=1;</script></head>"
            "<body><nav>Home | About</nav><header>Top</header>"
            "<p>b9601 was released on June 11.</p>"
            "<footer>(c) footer</footer><svg><path d='M0'/></svg></body></html>"
        )
        title, text = extract_readable(html, content_type="text/html")
        self.assertEqual(title, "Releases - llama.cpp")
        self.assertIn("b9601 was released", text)
        for noise in ("var x=1", "color:red", "Home | About", "(c) footer", "M0"):
            self.assertNotIn(noise, text)

    def test_plain_text_passthrough_bounded(self):
        from core.search.page_extract import extract_readable

        title, text = extract_readable("x" * 9000, content_type="text/plain")
        self.assertEqual(title, "")
        self.assertEqual(len(text), 6000)

    def test_html_output_bounded(self):
        from core.search.page_extract import extract_readable

        html = "<html><body><p>" + ("word " * 3000) + "</p></body></html>"
        _, text = extract_readable(html, content_type="text/html")
        self.assertLessEqual(len(text), 6000)

    def test_garbage_and_empty_fail_safe(self):
        from core.search.page_extract import extract_readable

        self.assertEqual(extract_readable("", content_type="text/html"), ("", ""))
        self.assertEqual(extract_readable("<<<>>>", content_type="text/html")[1], "")

    def test_extract_first_url(self):
        from core.search.page_extract import extract_first_url

        self.assertEqual(
            extract_first_url("check https://github.com/x/releases please"),
            "https://github.com/x/releases",
        )
        self.assertIsNone(extract_first_url("no links here"))
        self.assertIsNone(extract_first_url("ftp://nope.example/file"))


if __name__ == "__main__":
    unittest.main()
