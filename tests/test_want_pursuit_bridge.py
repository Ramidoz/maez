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


class _FakeWants:
    def __init__(self, rows):
        self._rows = rows

    def active_wants(self, limit=None):
        return list(self._rows)


class _FakeCards:
    def __init__(self, open_want_ids=()):
        self._ids = list(open_want_ids)

    def list_open_by_action(self, action):
        class _C:
            def __init__(self, wid):
                self.params = {"want_id": wid}

        return [_C(w) for w in self._ids]


class SelectWantTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.w = wonderings.Wonderings(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def _want(self, wid, stmt="x"):
        return {"want_id": wid, "statement": stmt, "active_state": "active"}

    def test_no_active_wants_returns_none(self):
        got = wpb.select_want(
            _FakeWants([]),
            self.w,
            _FakeCards(),
            cooldown_s=3600,
            now=1000.0,
        )
        self.assertIsNone(got)

    def test_global_one_in_flight_blocks_all(self):
        self.w.add("pursuing", source="want:other")
        got = wpb.select_want(
            _FakeWants([self._want("a")]),
            self.w,
            _FakeCards(),
            cooldown_s=3600,
            now=1000.0,
        )
        self.assertIsNone(got)

    def test_want_with_open_proposal_card_is_excluded(self):
        got = wpb.select_want(
            _FakeWants([self._want("a")]),
            self.w,
            _FakeCards(open_want_ids=["a"]),
            cooldown_s=3600,
            now=1000.0,
        )
        self.assertIsNone(got)

    def test_least_recently_pursued_chosen_never_pursued_first(self):
        wid = self.w.add("old", source="want:a")
        self.w.resolve(wid, "done", resolved_at=10.0)
        got = wpb.select_want(
            _FakeWants([self._want("a"), self._want("b")]),
            self.w,
            _FakeCards(),
            cooldown_s=1.0,
            now=10000.0,
        )
        self.assertEqual(got["want_id"], "b")

    def test_cooldown_excludes_recently_pursued(self):
        wid = self.w.add("recent", source="want:a")
        self.w.resolve(wid, "done", resolved_at=9999.0)
        got = wpb.select_want(
            _FakeWants([self._want("a")]),
            self.w,
            _FakeCards(),
            cooldown_s=3600,
            now=10000.0,
        )
        self.assertIsNone(got)
