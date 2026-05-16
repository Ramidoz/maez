# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""RED-first tests for M1 lived-episode promotion.

These tests pin Decision 25 / ADR 0030 before production code exists:
promote biography, do not widen recall; structural summaries only; source-ID
provenance; default-disabled rollout.
"""

from __future__ import annotations

import tempfile
import unittest
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.memory.episodes import EpisodeStore
from core.memory.m1_lived_episode_promotion import (
    M1Config,
    M1LivedEpisodePromoter,
    M1PromotionStore,
    PendingWindow,
    biography_staleness_health,
    build_structural_summary,
    marker_is_owner_authored,
    reset_m1_observability_counters_for_tests,
)


class M1PromotionTestCase(unittest.TestCase):
    def setUp(self):
        reset_m1_observability_counters_for_tests()
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        self.episodes = EpisodeStore(str(root / "lived_episodes.db"))
        self.sidecar = M1PromotionStore(str(root / "m1_sidecar.db"))
        self.now = datetime(2026, 5, 14, 18, 30, tzinfo=timezone.utc)
        self.promoter = M1LivedEpisodePromoter(
            episode_store=self.episodes,
            promotion_store=self.sidecar,
            config=M1Config(enabled=True, max_promotions_per_day=10),
            now_fn=lambda: self.now,
        )

    def tearDown(self):
        self._td.cleanup()
        reset_m1_observability_counters_for_tests()


class MarkerDetectionTests(unittest.TestCase):
    def test_marker_must_be_owner_authored_non_negated_non_quoted(self):
        self.assertTrue(marker_is_owner_authored("remember this"))
        self.assertTrue(marker_is_owner_authored("This matters. Save this."))

        self.assertFalse(marker_is_owner_authored("don't remember this"))
        self.assertFalse(marker_is_owner_authored("he said remember this"))
        self.assertFalse(marker_is_owner_authored("Anna said remember this"))
        self.assertFalse(marker_is_owner_authored("my mom told me save this"))
        self.assertFalse(marker_is_owner_authored("Bob asked me to remember this"))
        self.assertFalse(marker_is_owner_authored("I'm quoting 'save this'"))


class StructuralSummaryTests(unittest.TestCase):
    def test_structural_summary_contains_no_raw_transcript_text(self):
        summary = build_structural_summary(
            pair_count=2,
            start_at="2026-05-14T18:00:00+00:00",
            end_at="2026-05-14T18:12:00+00:00",
            trigger="explicit_marker",
            reason="explicit_marker",
        )

        self.assertIn("Bonded Telegram exchange.", summary)
        self.assertIn("2 audited owner/Maez pairs", summary)
        self.assertIn("Participants: Rohit, Maez.", summary)
        self.assertNotIn("remember this", summary)
        self.assertNotIn("Rohit said", summary)
        self.assertNotIn("Maez replied", summary)

    def test_structural_summary_resolves_owner_name_from_identity(self):
        from core import identity

        with patch.dict(os.environ, {"MAEZ_OWNER_NAME": "Alex"}, clear=False):
            identity.reload()
            summary = build_structural_summary(
                pair_count=1,
                start_at="2026-05-14T18:00:00+00:00",
                end_at="2026-05-14T18:00:00+00:00",
                trigger="explicit_marker",
                reason="explicit_marker",
            )
        identity.reload()

        self.assertIn("Participants: Alex, Maez.", summary)
        self.assertNotIn("Participants: Rohit, Maez.", summary)


class PromotionBehaviorTests(M1PromotionTestCase):
    def test_default_config_is_disabled(self):
        self.assertFalse(M1Config().enabled)

    def test_explicit_marker_promotes_structural_episode(self):
        outcome = self.promoter.consider_audited_exchange(
            owner_text="Remember this: today we proved M1 safely.",
            maez_reply="I hear you. I will keep the shape honest.",
            raw_memory_id="raw-1",
            occurred_at="2026-05-14T18:00:00+00:00",
        )

        self.assertTrue(outcome.promoted)
        self.assertIsNotNone(outcome.episode_id)
        ep = self.episodes.get(outcome.episode_id or "")
        self.assertEqual(ep["source_kind"], "telegram_exchange")
        self.assertEqual(ep["participants"], ["Rohit", "Maez"])
        self.assertEqual(ep["source_memory_ids"], ["raw-1"])
        self.assertEqual(ep["authorship"], "bonded_dialogue")
        self.assertEqual(ep["memory_voice"], "mixed_owner_maez")
        self.assertIn("Bonded Telegram exchange.", ep["summary"])
        self.assertNotIn("today we proved", ep["summary"])
        self.assertNotIn("I hear you", ep["summary"])

    def test_promoted_episode_uses_identity_display_name_not_hardcoded_owner(self):
        from core import identity

        with patch.dict(os.environ, {"MAEZ_OWNER_NAME": "Alex"}, clear=False):
            identity.reload()
            outcome = self.promoter.consider_audited_exchange(
                owner_text="remember this",
                maez_reply="Okay.",
                raw_memory_id="raw-identity",
                occurred_at="2026-05-14T18:00:00+00:00",
            )
        identity.reload()

        self.assertTrue(outcome.promoted)
        ep = self.episodes.get(outcome.episode_id or "")
        self.assertEqual(ep["title"], "Bonded conversation with Alex")
        self.assertEqual(ep["participants"], ["Alex", "Maez"])
        self.assertIn("Participants: Alex, Maez.", ep["summary"])

    def test_explicit_marker_promotes_current_exchange_not_prior_pending_turns(self):
        self.promoter.consider_audited_exchange(
            owner_text="ordinary setup",
            maez_reply="Okay.",
            raw_memory_id="raw-prior",
            occurred_at="2026-05-14T17:55:00+00:00",
        )

        outcome = self.promoter.consider_audited_exchange(
            owner_text="remember this",
            maez_reply="Okay.",
            raw_memory_id="raw-current",
            occurred_at="2026-05-14T18:00:00+00:00",
        )

        self.assertTrue(outcome.promoted)
        ep = self.episodes.get(outcome.episode_id or "")
        self.assertEqual(ep["source_memory_ids"], ["raw-current"])

    def test_disabled_promoter_records_no_episode(self):
        promoter = M1LivedEpisodePromoter(
            episode_store=self.episodes,
            promotion_store=self.sidecar,
            config=M1Config(enabled=False),
            now_fn=lambda: self.now,
        )
        outcome = promoter.consider_audited_exchange(
            owner_text="remember this",
            maez_reply="Okay.",
            raw_memory_id="raw-disabled",
            occurred_at="2026-05-14T18:00:00+00:00",
        )

        self.assertFalse(outcome.promoted)
        self.assertEqual(outcome.skipped_reason, "disabled")
        self.assertEqual(self.episodes.list_active(), [])

    def test_ordinary_boundary_without_eligibility_does_not_promote(self):
        for idx in range(4):
            outcome = self.promoter.consider_audited_exchange(
                owner_text=f"ordinary note {idx}",
                maez_reply="Okay.",
                raw_memory_id=f"raw-ordinary-{idx}",
                occurred_at=f"2026-05-14T18:0{idx}:00+00:00",
            )

        self.assertFalse(outcome.promoted)
        self.assertEqual(outcome.skipped_reason, "not_eligible")
        self.assertEqual(self.episodes.list_active(), [])

    def test_salient_owner_affect_window_promotes_at_turn_boundary(self):
        texts = [
            "I feel much better compared to last week.",
            "That relief matters to me.",
            "This is a normal follow-up.",
            "One more bounded turn.",
        ]
        for idx, text in enumerate(texts):
            outcome = self.promoter.consider_audited_exchange(
                owner_text=text,
                maez_reply="I hear you.",
                raw_memory_id=f"raw-affect-{idx}",
                occurred_at=f"2026-05-14T18:1{idx}:00+00:00",
            )

        self.assertTrue(outcome.promoted)
        ep = self.episodes.get(outcome.episode_id or "")
        self.assertEqual(
            ep["source_memory_ids"],
            [
                "raw-affect-0",
                "raw-affect-1",
                "raw-affect-2",
                "raw-affect-3",
            ],
        )
        self.assertNotIn("much better", ep["summary"])

    def test_pending_window_survives_restart_with_ids_only(self):
        self.promoter.consider_audited_exchange(
            owner_text="I feel steadier today.",
            maez_reply="I hear that.",
            raw_memory_id="raw-pending",
            occurred_at="2026-05-14T18:00:00+00:00",
        )

        reopened = M1PromotionStore(str(Path(self._td.name) / "m1_sidecar.db"))
        pending = reopened.load_pending_window()
        self.assertEqual(pending.source_memory_ids, ["raw-pending"])
        self.assertEqual(pending.pair_count, 1)
        self.assertNotIn("steadier", repr(pending))

    def test_duplicate_and_partial_overlap_are_deterministic(self):
        first = self.promoter.consider_audited_exchange(
            owner_text="remember this",
            maez_reply="Okay.",
            raw_memory_id="raw-dup-1",
            occurred_at="2026-05-14T18:00:00+00:00",
        )
        self.assertTrue(first.promoted)

        replay = self.promoter.promote_window(
            source_memory_ids=["raw-dup-1"],
            first_owner_at="2026-05-14T18:00:00+00:00",
            last_owner_at="2026-05-14T18:00:00+00:00",
            pair_count=1,
            trigger="explicit_marker",
            reason="explicit_marker",
        )
        self.assertFalse(replay.promoted)
        self.assertEqual(replay.skipped_reason, "duplicate_source")

        partial = self.promoter.promote_window(
            source_memory_ids=["raw-dup-1", "raw-dup-2"],
            first_owner_at="2026-05-14T18:00:00+00:00",
            last_owner_at="2026-05-14T18:05:00+00:00",
            pair_count=2,
            trigger="explicit_marker",
            reason="explicit_marker",
        )
        self.assertFalse(partial.promoted)
        self.assertEqual(partial.skipped_reason, "partial_overlap")

    def test_sidecar_reconstructs_idempotency_from_existing_lived_episodes(self):
        self.episodes.add(
            title="Bonded conversation with Rohit",
            summary="Bonded Telegram exchange. 1 audited owner/Maez pair at t.",
            participants=["Rohit", "Maez"],
            source_memory_ids=["raw-restored"],
            source_kind="telegram_exchange",
            occurred_at="2026-05-14T18:00:00+00:00",
            authorship="bonded_dialogue",
            memory_voice="mixed_owner_maez",
        )
        fresh_sidecar = M1PromotionStore(str(Path(self._td.name) / "fresh_sidecar.db"))
        promoter = M1LivedEpisodePromoter(
            episode_store=self.episodes,
            promotion_store=fresh_sidecar,
            config=M1Config(enabled=True),
            now_fn=lambda: self.now,
        )

        replay = promoter.promote_window(
            source_memory_ids=["raw-restored"],
            first_owner_at="2026-05-14T18:00:00+00:00",
            last_owner_at="2026-05-14T18:00:00+00:00",
            pair_count=1,
            trigger="explicit_marker",
            reason="explicit_marker",
        )

        self.assertFalse(replay.promoted)
        self.assertEqual(replay.skipped_reason, "duplicate_source")

    def test_promotion_provenance_envelope_is_inspectable(self):
        outcome = self.promoter.consider_audited_exchange(
            owner_text="remember this",
            maez_reply="Okay.",
            raw_memory_id="raw-prov",
            occurred_at="2026-05-14T18:00:00+00:00",
        )

        provenance = self.sidecar.get_provenance(outcome.episode_id or "")

        self.assertEqual(provenance["producer_version"], "m1.v1")
        self.assertEqual(provenance["promotion_trigger"], "explicit_marker")
        self.assertEqual(provenance["promotion_reason"], "explicit_marker")
        self.assertEqual(provenance["consent_posture"], "bonded_user_dialogue")
        self.assertEqual(provenance["source_id_count"], 1)
        self.assertIn("promoted_at", provenance)
        self.assertIn("window_start", provenance)
        self.assertIn("window_end", provenance)

    def test_pending_window_rejects_unknown_eligibility_reason(self):
        with self.assertRaises(ValueError):
            PendingWindow(
                window_id="bad-window",
                source_memory_ids=["raw-bad"],
                first_owner_at="2026-05-14T18:00:00+00:00",
                last_owner_at="2026-05-14T18:00:00+00:00",
                pair_count=1,
                eligibility_reasons=["made_up_reason"],
            )

    def test_promote_window_rejects_unknown_promotion_reason(self):
        with self.assertRaises(ValueError):
            self.promoter.promote_window(
                source_memory_ids=["raw-bad-reason"],
                first_owner_at="2026-05-14T18:00:00+00:00",
                last_owner_at="2026-05-14T18:00:00+00:00",
                pair_count=1,
                trigger="explicit_marker",
                reason="made_up_reason",
            )
        self.assertEqual(
            self.promoter.status_health()["invalid_eligibility_reason_rejected_count"],
            1,
        )

    def test_status_health_reports_owner_identity_fallback_count(self):
        import core.identity

        with patch.object(core.identity, "display_name", return_value=""):
            outcome = self.promoter.consider_audited_exchange(
                owner_text="remember this",
                maez_reply="Okay.",
                raw_memory_id="raw-fallback-owner",
                occurred_at="2026-05-14T18:00:00+00:00",
            )

        self.assertTrue(outcome.promoted)
        health = self.promoter.status_health()
        self.assertEqual(health["identity_fallback_count"], 1)

    def test_daily_promotion_cap_limits_new_episodes(self):
        promoter = M1LivedEpisodePromoter(
            episode_store=self.episodes,
            promotion_store=self.sidecar,
            config=M1Config(enabled=True, max_promotions_per_day=1),
            now_fn=lambda: self.now,
        )

        first = promoter.consider_audited_exchange(
            owner_text="remember this",
            maez_reply="Okay.",
            raw_memory_id="raw-cap-1",
            occurred_at="2026-05-14T18:00:00+00:00",
        )
        second = promoter.consider_audited_exchange(
            owner_text="remember this",
            maez_reply="Okay.",
            raw_memory_id="raw-cap-2",
            occurred_at="2026-05-14T18:05:00+00:00",
        )

        self.assertTrue(first.promoted)
        self.assertFalse(second.promoted)
        self.assertEqual(second.skipped_reason, "rate_limited")
        self.assertEqual(len(self.episodes.list_active()), 1)
        pending = self.sidecar.load_pending_window()
        self.assertEqual(pending.promotion_state, "deferred_rate_limited")
        self.assertEqual(pending.source_memory_ids, ["raw-cap-2"])

    def test_daily_promotion_cap_resets_at_owner_local_midnight(self):
        utc_now = datetime(2026, 5, 15, 5, 30, tzinfo=timezone.utc)
        promoter = M1LivedEpisodePromoter(
            episode_store=self.episodes,
            promotion_store=self.sidecar,
            config=M1Config(enabled=True, max_promotions_per_day=1),
            now_fn=lambda: utc_now,
        )
        self.sidecar.mark_promoted(
            source_memory_ids=["raw-local-offset"],
            episode_id="episode-local-offset",
            window_id="prior-window",
            promoted_at="2026-05-14T23:30:00-05:00",
            provenance={},
        )

        with patch(
            "core.memory.m1_lived_episode_promotion._identity.timezone",
            return_value="America/Chicago",
        ):
            outcome = promoter.consider_audited_exchange(
                owner_text="remember this",
                maez_reply="Okay.",
                raw_memory_id="raw-cap-local",
                occurred_at="2026-05-15T05:30:00+00:00",
            )

        self.assertTrue(outcome.promoted)

    def test_silence_flush_promotes_eligible_window_without_new_owner_message(self):
        self.promoter.consider_audited_exchange(
            owner_text="I feel like this is getting real.",
            maez_reply="I hear that.",
            raw_memory_id="raw-silence",
            occurred_at="2026-05-14T18:00:00+00:00",
        )
        self.now = self.now + timedelta(seconds=901)

        outcomes = self.promoter.flush_due_windows()

        self.assertEqual(len(outcomes), 1)
        self.assertTrue(outcomes[0].promoted)
        self.assertEqual(
            self.episodes.get(outcomes[0].episode_id or "")["source_memory_ids"],
            ["raw-silence"],
        )

    def test_s4_marker_skips_entire_pending_window(self):
        self.promoter.consider_audited_exchange(
            owner_text="plain setup turn",
            maez_reply="I am here.",
            raw_memory_id="raw-before-s4",
            occurred_at="2026-05-14T18:00:00+00:00",
        )

        outcome = self.promoter.mark_current_window_s4_policy("m1_ineligible_clinical_boundary")
        self.assertFalse(outcome.promoted)
        self.assertEqual(outcome.skipped_reason, "s4_clinical_boundary")

        self.promoter.consider_audited_exchange(
            owner_text="I promise we will come back to the ordinary part.",
            maez_reply="I hear the commitment.",
            raw_memory_id="raw-after-s4",
            occurred_at="2026-05-14T18:01:00+00:00",
        )
        self.now = self.now + timedelta(seconds=901)

        outcomes = self.promoter.flush_due_windows()

        self.assertEqual(outcomes[0].skipped_reason, "s4_clinical_boundary")
        self.assertEqual(self.episodes.list_active(), [])

    def test_s4_marker_uses_closed_policy_values_and_content_free_skip_reason(self):
        outcome = self.promoter.mark_current_window_s4_policy("m1_ineligible_crisis_candidate")

        self.assertFalse(outcome.promoted)
        self.assertEqual(outcome.skipped_reason, "s4_crisis_candidate")
        window = self.sidecar.load_pending_window()
        self.assertEqual(window.s4_skip_reasons, ["s4_crisis_candidate"])
        self.assertNotIn("crisis", repr(window.source_memory_ids))
        self.assertNotIn("symptom", repr(window))

    def test_m1_rejects_invalid_s4_policy_with_content_free_counter(self):
        with self.assertRaises(ValueError):
            self.promoter.mark_current_window_s4_policy("symptom_fear")  # type: ignore[arg-type]

        self.assertEqual(
            self.promoter.status_health()["invalid_s4_skip_reason_rejected_count"],
            1,
        )


class StalenessHealthTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = EpisodeStore(str(Path(self._td.name) / "lived_episodes.db"))
        self.now = datetime(2026, 5, 14, 18, 30, tzinfo=timezone.utc)

    def tearDown(self):
        self._td.cleanup()

    def test_empty_biography_reports_empty(self):
        health = biography_staleness_health(self.store, now=self.now)

        self.assertEqual(health["active_count"], 0)
        self.assertEqual(health["staleness_status"], "empty")

    def test_ok_warn_alarm_thresholds(self):
        newest = self.now - timedelta(hours=1)
        self.store.add(
            title="recent",
            summary="s",
            participants=["Rohit", "Maez"],
            source_memory_ids=["raw-recent"],
            source_kind="telegram_exchange",
            occurred_at=newest.isoformat(),
        )
        self.assertEqual(
            biography_staleness_health(self.store, now=self.now)["staleness_status"],
            "ok",
        )

        self.assertEqual(
            biography_staleness_health(
                self.store,
                now=newest + timedelta(hours=49),
            )["staleness_status"],
            "warn",
        )
        self.assertEqual(
            biography_staleness_health(
                self.store,
                now=newest + timedelta(hours=169),
            )["staleness_status"],
            "alarm",
        )


class BackupManifestTests(unittest.TestCase):
    def test_m1_sidecar_is_in_decision_22_backup_manifest(self):
        manifest = json.loads(Path("scripts/backup/backup_state_manifest.json").read_text())
        paths = {entry["path"] for entry in manifest["entries"]}

        self.assertIn("memory/m1_lived_episode_promotion.db", paths)
