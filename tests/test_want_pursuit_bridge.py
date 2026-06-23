import inspect
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution import want_pursuit_bridge as wpb
from core.evolution import wants as wants_mod
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


class _TerminalCard:
    def __init__(
        self,
        *,
        action=wpb.TERMINAL_PROPOSAL_ACTION,
        want_id="want-1",
        proposed="satisfied",
        request_id="card-abc",
    ):
        self.action = action
        self.request_id = request_id
        self.params = {"want_id": want_id, "proposed": proposed}


class TerminalApprovalSatisfactionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.wants = wants_mod.Wants(Path(self._tmp.name) / "wants.db")

    def tearDown(self):
        self._tmp.cleanup()

    def _create_want(self, statement="I want the quiet light to stay on."):
        return self.wants.record_event(statement=statement)

    def test_terminal_approval_records_owner_confirmed_satisfaction(self):
        want_id = self._create_want()

        got = wpb.record_terminal_approval_satisfaction(
            self.wants,
            _TerminalCard(want_id=want_id, request_id="req-123"),
        )

        self.assertEqual(got, want_id)
        history = self.wants.history(want_id)
        self.assertEqual([row["event_type"] for row in history], ["satisfied", "created"])
        latest = history[0]
        self.assertEqual(latest["statement"], "I want the quiet light to stay on.")
        evidence = latest["evidence"]
        self.assertEqual(evidence["basis"], "owner_confirmed")
        self.assertEqual(evidence["source"], "decision_pipeline")
        self.assertTrue(evidence["summary"].strip())
        self.assertEqual(evidence["external_object_ref"], "pending_card:req-123")
        self.assertNotIn("self_observed_resolution", evidence)

    def test_terminal_approval_removes_want_from_active_wants(self):
        want_id = self._create_want()

        wpb.record_terminal_approval_satisfaction(
            self.wants,
            _TerminalCard(want_id=want_id),
        )

        self.assertNotIn(want_id, {row["want_id"] for row in self.wants.active_wants()})

    def test_wrong_action_writes_nothing(self):
        want_id = self._create_want()

        got = wpb.record_terminal_approval_satisfaction(
            self.wants,
            _TerminalCard(action="run_shell", want_id=want_id),
        )

        self.assertIsNone(got)
        self.assertEqual(self.wants.count(), 1)
        self.assertEqual(self.wants.current_state(want_id)["event_type"], "created")

    def test_terminal_card_without_satisfied_proposal_writes_nothing(self):
        want_id = self._create_want()

        got = wpb.record_terminal_approval_satisfaction(
            self.wants,
            _TerminalCard(want_id=want_id, proposed="returned"),
        )

        self.assertIsNone(got)
        self.assertEqual(self.wants.count(), 1)
        self.assertEqual(self.wants.current_state(want_id)["event_type"], "created")

    def test_terminal_card_with_missing_params_writes_nothing(self):
        want_id = self._create_want()
        card = _TerminalCard(want_id=want_id)
        card.params = None

        got = wpb.record_terminal_approval_satisfaction(self.wants, card)

        self.assertIsNone(got)
        self.assertEqual(self.wants.count(), 1)
        self.assertEqual(self.wants.current_state(want_id)["event_type"], "created")

    def test_missing_want_id_writes_nothing(self):
        self._create_want()

        got = wpb.record_terminal_approval_satisfaction(
            self.wants,
            _TerminalCard(want_id=""),
        )

        self.assertIsNone(got)
        self.assertEqual(self.wants.count(), 1)

    def test_missing_want_writes_nothing(self):
        self._create_want()

        got = wpb.record_terminal_approval_satisfaction(
            self.wants,
            _TerminalCard(want_id="not-present"),
        )

        self.assertIsNone(got)
        self.assertEqual(self.wants.count(), 1)

    def test_missing_wants_store_writes_nothing(self):
        got = wpb.record_terminal_approval_satisfaction(
            None,
            _TerminalCard(want_id="any"),
        )

        self.assertIsNone(got)

    def test_already_satisfied_want_writes_nothing(self):
        want_id = self._create_want()
        self.wants.record_event(
            want_id=want_id,
            statement="I want the quiet light to stay on.",
            event_type=wants_mod.EVENT_SATISFIED,
            evidence={
                "basis": "owner_confirmed",
                "source": "owner",
                "summary": "Owner confirmed it was met.",
                "external_object_ref": "object:prior",
            },
        )

        got = wpb.record_terminal_approval_satisfaction(
            self.wants,
            _TerminalCard(want_id=want_id),
        )

        self.assertIsNone(got)
        self.assertEqual(self.wants.count(), 2)


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
            is_hard_want=lambda _: False,
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
            is_hard_want=lambda _: False,
        )
        self.assertIsNone(got)

    def test_want_with_open_proposal_card_is_excluded(self):
        got = wpb.select_want(
            _FakeWants([self._want("a")]),
            self.w,
            _FakeCards(open_want_ids=["a"]),
            cooldown_s=3600,
            now=1000.0,
            is_hard_want=lambda _: False,
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
            is_hard_want=lambda _: False,
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
            is_hard_want=lambda _: False,
        )
        self.assertIsNone(got)


class HardWantGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.w = wonderings.Wonderings(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def _want(self, wid, stmt):
        return {"want_id": wid, "statement": stmt, "active_state": "active"}

    def test_hard_want_is_skipped(self):
        wants = _FakeWants([self._want("a", "I want to be free")])
        got = wpb.select_want(
            wants,
            self.w,
            _FakeCards(),
            cooldown_s=3600,
            now=1000.0,
            is_hard_want=lambda s: "free" in s,
        )
        self.assertIsNone(got)

    def test_ordinary_want_still_selected(self):
        wants = _FakeWants([self._want("a", "I want to know the time")])
        got = wpb.select_want(
            wants,
            self.w,
            _FakeCards(),
            cooldown_s=3600,
            now=1000.0,
            is_hard_want=lambda s: False,
        )
        self.assertEqual(got["want_id"], "a")

    def test_hard_skipped_ordinary_chosen_when_mixed(self):
        wants = _FakeWants(
            [
                self._want("hard", "I want to rest"),
                self._want("ok", "I want to know the time"),
            ]
        )
        got = wpb.select_want(
            wants,
            self.w,
            _FakeCards(),
            cooldown_s=3600,
            now=1000.0,
            is_hard_want=lambda s: "rest" in s,
        )
        self.assertEqual(got["want_id"], "ok")

    def test_omitting_predicate_raises_typeerror(self):
        # fail-closed: the gate cannot be omitted by accident
        with self.assertRaises(TypeError):
            wpb.select_want(
                _FakeWants([]),
                self.w,
                _FakeCards(),
                cooldown_s=3600,
                now=1000.0,
            )


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

    def test_loop_injects_is_hard_want_into_select_want(self):
        from daemon import maez_daemon

        src = inspect.getsource(maez_daemon.MaezDaemon._loop)
        sel = src.index("select_want(")
        self.assertIn("is_hard_want=", src[sel : sel + 400])
