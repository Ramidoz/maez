import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution import want_pursuit_bridge as wpb
from core.evolution import wonderings


class TemplateAndTrailTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.w = wonderings.Wonderings(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_template_question_is_deterministic_and_bounded(self):
        q = wpb.template_question("I want the daemon logs to stay quiet at night")
        self.assertEqual(
            q,
            "What bounded, read-only investigation would advance this want: "
            "I want the daemon logs to stay quiet at night?",
        )

    def test_source_for_and_want_id_from(self):
        self.assertEqual(wpb.source_for("abc123"), "want:abc123")
        self.assertEqual(wpb.want_id_from_source("want:abc123"), "abc123")
        self.assertIsNone(wpb.want_id_from_source("manual"))

    def test_want_pursuit_trail_returns_source_linked(self):
        self.w.add("q1", source="want:abc")
        self.w.add("other", source="manual")
        trail = wpb.want_pursuit_trail(self.w, "abc")
        self.assertEqual([t["question"] for t in trail], ["q1"])
