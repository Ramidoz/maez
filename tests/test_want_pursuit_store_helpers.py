import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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
