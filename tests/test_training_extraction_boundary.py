# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.

import unittest
from unittest import mock

import training.extract_training_pairs as extract


def _named_iter(name):
    def _inner():
        if False:
            yield None

    _inner.__name__ = name
    return _inner


class TrainingExtractionBoundaryTests(unittest.TestCase):
    def test_reasoning_cycles_are_excluded_by_default(self):
        with (
            mock.patch.object(extract, "iter_chromadb_pairs", _named_iter("chromadb")),
            mock.patch.object(extract, "iter_fast_log_pairs", _named_iter("fast")),
            mock.patch.object(extract, "iter_reasoning_pairs", _named_iter("reasoning")),
            mock.patch.object(extract, "iter_soul_qa_pairs", _named_iter("soul")),
            mock.patch.object(extract, "iter_evolution_pairs", _named_iter("evolution")),
            mock.patch.object(extract, "iter_continuity_pairs", _named_iter("continuity")),
        ):
            sources = extract.iter_training_sources()

        self.assertEqual(
            [src.__name__ for src in sources],
            ["chromadb", "fast", "soul", "evolution", "continuity"],
        )

    def test_reasoning_cycles_are_explicit_opt_in(self):
        with (
            mock.patch.object(extract, "iter_chromadb_pairs", _named_iter("chromadb")),
            mock.patch.object(extract, "iter_fast_log_pairs", _named_iter("fast")),
            mock.patch.object(extract, "iter_reasoning_pairs", _named_iter("reasoning")),
            mock.patch.object(extract, "iter_soul_qa_pairs", _named_iter("soul")),
            mock.patch.object(extract, "iter_evolution_pairs", _named_iter("evolution")),
            mock.patch.object(extract, "iter_continuity_pairs", _named_iter("continuity")),
        ):
            sources = extract.iter_training_sources(include_reasoning_cycles=True)

        self.assertEqual(
            [src.__name__ for src in sources],
            ["chromadb", "fast", "reasoning", "soul", "evolution", "continuity"],
        )


if __name__ == "__main__":
    unittest.main()
