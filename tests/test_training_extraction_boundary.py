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


class VoiceQualityFilterTests(unittest.TestCase):
    """2026-04-28 — voice-LoRA quality filters (date, fabrication,
    per-source cap). These prevent training on pre-grounding-fix turns
    that contain fluently-confabulated narrations the audit pipeline
    has since flagged as a class."""

    def test_ts_after_empty_passes(self):
        # No timestamp → can't filter; keep (fail-open).
        self.assertTrue(extract._ts_after("", "2026-04-23"))

    def test_ts_after_iso_pre_drops(self):
        self.assertFalse(
            extract._ts_after("2026-04-19T12:00:00+00:00", "2026-04-23")
        )

    def test_ts_after_iso_post_passes(self):
        self.assertTrue(
            extract._ts_after("2026-04-25T12:00:00+00:00", "2026-04-23")
        )

    def test_ts_after_unix_float_pre_drops(self):
        # 2025-04-18 unix → pre-fix
        self.assertFalse(extract._ts_after("1745000000", "2026-04-23"))

    def test_ts_after_unix_float_post_passes(self):
        # 2026-04-28 unix → post-fix
        self.assertTrue(extract._ts_after("1777354719.13", "2026-04-23"))

    def test_ts_after_garbage_passes(self):
        # Unparseable → keep (fail-open).
        self.assertTrue(extract._ts_after("not a date", "2026-04-23"))

    def test_fabrication_flagged_substring_match(self):
        flagged = {extract._norm("the disk has been trending upward for weeks")}
        self.assertTrue(
            extract.is_fabrication_flagged(
                "The disk has been trending upward for weeks.",
                flagged,
            )
        )

    def test_fabrication_flagged_unrelated_passes(self):
        flagged = {extract._norm("specific fabricated text")}
        self.assertFalse(
            extract.is_fabrication_flagged("Hello, what's up?", flagged)
        )

    def test_fabrication_flagged_empty_set_passes_everything(self):
        # No fabrication log → no filtering.
        self.assertFalse(extract.is_fabrication_flagged("anything", set()))


if __name__ == "__main__":
    unittest.main()
