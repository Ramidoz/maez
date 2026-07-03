# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for A1 Scar Tissue's pure core.

The core invariant is receipt-grade, neutral correction memory:
pre-validate before any mint, mint a consequence row when needed, validate
the combined receipt set, then append scar evidence without mutating history.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ScarValidationTests(unittest.TestCase):
    def test_no_receipt_raises(self):
        from core.learning.scar_tissue import ScarEvent, validate_scar

        event = ScarEvent(
            scar_class="dream_rejected",
            surface="telegram",
            context="proposal 7",
            correction="rejected: too grand",
            receipt_refs=[],
            dedup_key="dream:7",
        )

        with self.assertRaises(ValueError):
            validate_scar(event)

    def test_invalid_class_raises_before_any_consequence_write(self):
        from core.learning.scar_tissue import ScarEvent, record_scar

        for bad_class in ("tool_failure", "made_up_class"):
            event = ScarEvent(
                scar_class=bad_class,
                surface="daemon",
                context="x",
                correction="y",
                receipt_refs=[],
                dedup_key=f"k:{bad_class}",
            )
            with mock.patch("core.learning.consequence_memory.record_event") as rec:
                with self.assertRaises(ValueError):
                    record_scar(
                        event,
                        episode_store=mock.Mock(),
                        sidecar=mock.Mock(),
                    )
                rec.assert_not_called()

    def test_redo_scar_succeeds_via_minted_consequence_receipt(self):
        from core.learning.scar_tissue import ScarEvent, ScarSidecar, record_scar
        from core.memory.episodes import EpisodeStore

        event = ScarEvent(
            scar_class="claim_receipt_redo",
            surface="daemon",
            context="action=web_search outcome=floor",
            correction="claim lacked receipt; reply held to facts",
            receipt_refs=[],
            dedup_key="redo:web_search:p1",
        )
        with tempfile.TemporaryDirectory() as td:
            episodes = EpisodeStore(str(Path(td) / "episodes.db"))
            sidecar = ScarSidecar(Path(td) / "scars.db")
            with mock.patch(
                "core.learning.consequence_memory.record_event",
                return_value=42,
            ) as rec:
                result = record_scar(
                    event,
                    episode_store=episodes,
                    sidecar=sidecar,
                    now_iso="2026-07-02T12:00:00+00:00",
                )

            rec.assert_called_once()
            self.assertTrue(result["new_episode"])
            self.assertEqual(result["consequence_id"], 42)
            episode = episodes.get(result["episode_id"])
            self.assertIsNotNone(episode)
            self.assertIn("consequence:42", episode["source_memory_ids"])
            self.assertEqual(episode["source_kind"], "scar")
            self.assertEqual(episode["authorship"], "scar_detector")
            self.assertEqual(episode["memory_voice"], "external_to_maez")
            self.assertEqual(episode["importance"], 4)

    def test_redo_scar_without_external_receipts_raises_if_mint_fails(self):
        from core.learning.scar_tissue import ScarEvent, record_scar

        event = ScarEvent(
            scar_class="claim_receipt_redo",
            surface="daemon",
            context="action=web_search",
            correction="held to facts",
            receipt_refs=[],
            dedup_key="redo:web_search:p1",
        )
        with mock.patch(
            "core.learning.consequence_memory.record_event",
            return_value=None,
        ):
            with self.assertRaises(ValueError):
                record_scar(
                    event,
                    episode_store=mock.Mock(),
                    sidecar=mock.Mock(),
                )

    def test_tool_failure_is_not_scar_grade(self):
        from core.learning.scar_tissue import SCAR_CLASSES

        self.assertNotIn("tool_failure", SCAR_CLASSES)
        for scar_class in (
            "fabrication_catch",
            "claim_receipt_redo",
            "dream_rejected",
            "veto_proven_wrong",
            "card_rejected",
        ):
            self.assertIn(scar_class, SCAR_CLASSES)

    def test_scaffold_text_is_neutral(self):
        from core.learning.scar_tissue import CORRECTION_MARKER, compose_scar_text

        text = compose_scar_text(
            scar_class="card_rejected",
            surface="decision_pipeline",
            context="action=run_shell cmd='rm -rf tmp'",
            correction=CORRECTION_MARKER,
            receipt_refs=["consequence:42", "card:abc"],
            occurred_at="2026-07-02T12:00:00Z",
        )
        scaffold = text.replace(CORRECTION_MARKER, "")
        for banned in (
            "mistake",
            "never ",
            "should not",
            "avoid ",
            "failed to",
            "sorry",
            "apolog",
            "shame",
            "must not",
        ):
            self.assertNotIn(banned, scaffold.lower())
        self.assertIn("consequence:42", text)

    def test_verbatim_correction_with_hot_words_still_composes_and_is_labeled(self):
        from core.learning.scar_tissue import compose_scar_text

        text = compose_scar_text(
            scar_class="dream_rejected",
            surface="telegram",
            context="proposal 7",
            correction="never do this again, you failed to check",
            receipt_refs=["consequence:9", "dream:7"],
            occurred_at="2026-07-02T12:00:00Z",
        )

        self.assertIn("never do this again, you failed to check", text)
        self.assertIn('The correction: "', text)


class ScarSidecarTests(unittest.TestCase):
    def _sidecar(self, td: str):
        from core.learning.scar_tissue import ScarSidecar

        return ScarSidecar(Path(td) / "scars.db")

    def test_first_occurrence_needs_episode(self):
        with tempfile.TemporaryDirectory() as td:
            sidecar = self._sidecar(td)

            self.assertIsNone(sidecar.active_episode("fab:tok1"))
            sidecar.register(
                "fab:tok1",
                episode_id="ep-1",
                receipt_ref="fabrication:9",
                occurred_at="2026-07-02T12:00:00+00:00",
            )

            self.assertEqual(sidecar.active_episode("fab:tok1"), "ep-1")

    def test_repeat_appends_evidence_without_new_episode(self):
        with tempfile.TemporaryDirectory() as td:
            sidecar = self._sidecar(td)
            sidecar.register(
                "fab:tok1",
                episode_id="ep-1",
                receipt_ref="fabrication:9",
                occurred_at="2026-07-02T12:00:00+00:00",
            )
            sidecar.append_evidence(
                "fab:tok1",
                receipt_ref="fabrication:10",
                occurred_at="2026-07-02T12:30:00+00:00",
            )

            row = sidecar.get("fab:tok1")
            self.assertEqual(row["active_episode_id"], "ep-1")
            self.assertEqual(row["occurrence_count"], 2)
            self.assertIn("fabrication:10", row["receipt_refs"])

    def test_supersede_updates_active_pointer_preserving_history(self):
        with tempfile.TemporaryDirectory() as td:
            sidecar = self._sidecar(td)
            sidecar.register(
                "fab:tok1",
                episode_id="ep-1",
                receipt_ref="r1",
                occurred_at="2026-07-02T12:00:00+00:00",
            )
            sidecar.supersede_active("fab:tok1", new_episode_id="ep-2")

            row = sidecar.get("fab:tok1")
            self.assertEqual(row["active_episode_id"], "ep-2")
            self.assertIn("ep-1", row["prior_episode_ids"])

    def test_record_scar_repeated_key_appends_evidence_without_episode(self):
        from core.learning.scar_tissue import ScarEvent, ScarSidecar, record_scar
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            episodes = EpisodeStore(str(Path(td) / "episodes.db"))
            sidecar = ScarSidecar(Path(td) / "scars.db")
            event = ScarEvent(
                scar_class="fabrication_catch",
                surface="daemon",
                context="claim about system state",
                correction="judge removed unsupported claim",
                receipt_refs=["fabrication:7"],
                dedup_key="fabrication:claim-about-system",
            )
            with mock.patch(
                "core.learning.consequence_memory.record_event",
                side_effect=[101, 102],
            ):
                first = record_scar(
                    event,
                    episode_store=episodes,
                    sidecar=sidecar,
                    now_iso="2026-07-02T12:00:00+00:00",
                )
                second = record_scar(
                    ScarEvent(
                        scar_class=event.scar_class,
                        surface=event.surface,
                        context=event.context,
                        correction=event.correction,
                        receipt_refs=["fabrication:8"],
                        dedup_key=event.dedup_key,
                    ),
                    episode_store=episodes,
                    sidecar=sidecar,
                    now_iso="2026-07-02T12:30:00+00:00",
                )

            self.assertTrue(first["new_episode"])
            self.assertFalse(second["new_episode"])
            self.assertEqual(first["episode_id"], second["episode_id"])
            active = episodes.list_active()
            self.assertEqual(len(active), 1)
            row = sidecar.get(event.dedup_key)
            self.assertEqual(row["occurrence_count"], 2)
            self.assertIn("fabrication:8", row["receipt_refs"])
            self.assertIn("consequence:102", row["receipt_refs"])


if __name__ == "__main__":
    unittest.main()
