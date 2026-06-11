import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.decision.pending_cards import PendingCardStore
from core.evolution import wonderings


class ListBySourceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = wonderings.Wonderings(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_list_by_source_returns_only_matching_source(self):
        a = self.store.add("q1", source="want:abc")
        self.store.add("q2", source="manual")
        c = self.store.add("q3", source="want:abc")
        ids = sorted(r["id"] for r in self.store.list_by_source("want:abc"))
        self.assertEqual(ids, sorted([a, c]))

    def test_list_by_source_empty_when_none_match(self):
        self.store.add("q", source="manual")
        self.assertEqual(self.store.list_by_source("want:zzz"), [])


class ListOpenByActionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = PendingCardStore(Path(self._tmp.name) / "cards.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_list_open_by_action_filters_by_action_and_open_status(self):
        self.store.create_card(action="want_terminal_proposal", params={"want_id": "a"})
        self.store.create_card(action="run_command", params={"cmd": "ls"})
        out = self.store.list_open_by_action("want_terminal_proposal")
        self.assertEqual([c.params.get("want_id") for c in out], ["a"])

    def test_list_open_by_action_empty_when_none(self):
        self.assertEqual(self.store.list_open_by_action("want_terminal_proposal"), [])
