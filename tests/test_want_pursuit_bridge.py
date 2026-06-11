import inspect
import os
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


class _RecordingCards:
    def __init__(self):
        self.created = []

    def create_card(self, *, action, params, reason=None, plain_english=None, **kw):
        self.created.append(
            {
                "action": action,
                "params": params,
                "reason": reason,
                "plain_english": plain_english,
            }
        )

        class _R:
            request_id = "card-1"

        return _R()

    def list_open_by_action(self, action):
        return []


class SeedAndProposeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.w = wonderings.Wonderings(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_seed_work_order_adds_want_sourced_wondering(self):
        wid = wpb.seed_work_order(self.w, {"want_id": "abc", "statement": "stay honest"})
        row = self.w.get(wid)
        self.assertEqual(row["source"], "want:abc")
        self.assertIn("stay honest", row["question"])

    def test_resolved_want_wondering_creates_advisory_card(self):
        wid = self.w.add("q", source="want:abc")
        cards = _RecordingCards()
        rid = wpb.maybe_propose_terminal(
            {"wondering_id": wid, "action": "resolved", "text": "found the cause"},
            self.w,
            cards,
        )
        self.assertEqual(rid, "card-1")
        self.assertEqual(len(cards.created), 1)
        c = cards.created[0]
        self.assertEqual(c["action"], "want_terminal_proposal")
        self.assertEqual(c["params"]["want_id"], "abc")
        self.assertEqual(c["params"]["proposed"], "satisfied")
        self.assertEqual(c["params"]["conclusion"], "found the cause")
        self.assertEqual(c["params"]["wondering_id"], wid)

    def test_abandoned_want_wondering_proposes_nothing(self):
        wid = self.w.add("q", source="want:abc")
        cards = _RecordingCards()
        rid = wpb.maybe_propose_terminal(
            {"wondering_id": wid, "action": "abandoned", "text": "dead end"},
            self.w,
            cards,
        )
        self.assertIsNone(rid)
        self.assertEqual(cards.created, [])

    def test_resolved_non_want_wondering_proposes_nothing(self):
        wid = self.w.add("q", source="manual")
        cards = _RecordingCards()
        rid = wpb.maybe_propose_terminal(
            {"wondering_id": wid, "action": "resolved", "text": "x"},
            self.w,
            cards,
        )
        self.assertIsNone(rid)
        self.assertEqual(cards.created, [])

    def test_non_resolved_actions_propose_nothing(self):
        wid = self.w.add("q", source="want:abc")
        cards = _RecordingCards()
        for action in ("advanced", "card_queued", "no_probe", "safety_refused"):
            self.assertIsNone(
                wpb.maybe_propose_terminal(
                    {"wondering_id": wid, "action": action},
                    self.w,
                    cards,
                )
            )
        self.assertEqual(cards.created, [])

    def test_none_result_is_safe(self):
        self.assertIsNone(wpb.maybe_propose_terminal(None, self.w, _RecordingCards()))


class DaemonFlagAndWiringTests(unittest.TestCase):
    def test_flag_default_off(self):
        from daemon import maez_daemon

        old = os.environ.pop("MAEZ_WANT_PURSUIT_ENABLED", None)
        try:
            self.assertFalse(maez_daemon._want_pursuit_enabled())
            os.environ["MAEZ_WANT_PURSUIT_ENABLED"] = "1"
            self.assertTrue(maez_daemon._want_pursuit_enabled())
        finally:
            os.environ.pop("MAEZ_WANT_PURSUIT_ENABLED", None)
            if old is not None:
                os.environ["MAEZ_WANT_PURSUIT_ENABLED"] = old

    def test_loop_wires_bridge_after_advance_one_and_behind_flag(self):
        from daemon import maez_daemon

        src = inspect.getsource(maez_daemon.MaezDaemon._loop)
        advance_idx = src.index("advance_one(self")
        flag_idx = src.index("_want_pursuit_enabled(", advance_idx)
        backward_idx = src.index("maybe_propose_terminal", advance_idx)
        seed_idx = src.index("seed_work_order", advance_idx)
        self.assertLess(advance_idx, flag_idx)
        self.assertLess(flag_idx, backward_idx)
        self.assertLess(backward_idx, seed_idx)
