"""Decision 13 biography-average support for temperament history."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TemperamentBiographyAverage(unittest.TestCase):
    def _store(self):
        from core.evolution.temperament import Temperament

        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        return Temperament(Path(td.name) / "temperament.db")

    def test_biography_average_returns_none_without_history(self):
        store = self._store()

        self.assertIsNone(store.biography_average("warmth", as_of=1000.0))

    def test_biography_average_time_weights_history_until_as_of(self):
        store = self._store()

        with mock.patch("core.evolution.temperament.time.time", return_value=0.0):
            store.record_event(parameter="warmth", value=2.0)
        with mock.patch("core.evolution.temperament.time.time", return_value=10.0):
            store.record_event(parameter="warmth", value=6.0)

        # 2.0 for ten seconds, then 6.0 for ten seconds.
        self.assertEqual(store.biography_average("warmth", as_of=20.0), 4.0)

    def test_biography_average_ignores_events_after_as_of(self):
        store = self._store()

        with mock.patch("core.evolution.temperament.time.time", return_value=0.0):
            store.record_event(parameter="patience", value=1.0)
        with mock.patch("core.evolution.temperament.time.time", return_value=10.0):
            store.record_event(parameter="patience", value=9.0)
        with mock.patch("core.evolution.temperament.time.time", return_value=50.0):
            store.record_event(parameter="patience", value=3.0)

        self.assertEqual(store.biography_average("patience", as_of=20.0), 5.0)

    def test_biography_average_single_observation_returns_observed_value(self):
        store = self._store()

        with mock.patch("core.evolution.temperament.time.time", return_value=10.0):
            store.record_event(parameter="joy", value=7.5)

        self.assertEqual(store.biography_average("joy", as_of=30.0), 7.5)

    def test_biography_average_rejects_unknown_parameter(self):
        store = self._store()

        with self.assertRaisesRegex(ValueError, "unknown parameter"):
            store.biography_average("sparkle", as_of=30.0)


if __name__ == "__main__":
    unittest.main()
