# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Hook tests for A1 Scar Tissue.

These tests keep the integration seams small and explicit: surfaces detect
corrections, then call the scar core only when MAEZ_SCAR_TISSUE is enabled.
Failures in scar writing must never break the original host path.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _dream_state(testcase: unittest.TestCase):
    from core.evolution.dream_state import DreamState

    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    return DreamState(
        memory=None,
        telegram=None,
        action_engine=None,
        db_path=str(Path(tmp.name) / "dream.db"),
    )


class DreamScarHookTests(unittest.TestCase):
    def test_default_hook_none_preserves_rejection(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")

        ok, message = dream.reject_proposal(prop_id, reason="not this")

        self.assertTrue(ok, message)
        self.assertEqual(dream.get_proposal(prop_id)["status"], "rejected")
        self.assertIsNone(dream.scar_hook)

    def test_hook_fires_once_on_successful_rejection_only(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")
        hook = mock.Mock()
        dream.scar_hook = hook

        ok, _ = dream.reject_proposal(prop_id, reason="too grand")
        self.assertTrue(ok)
        hook.assert_called_once_with(prop_id=prop_id, reason="too grand")

        ok, _ = dream.reject_proposal(prop_id, reason="again")
        self.assertFalse(ok)
        hook.assert_called_once()

        ok, _ = dream.reject_proposal(999999, reason="missing")
        self.assertFalse(ok)
        hook.assert_called_once()

    def test_raising_hook_does_not_break_rejection(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")
        dream.scar_hook = mock.Mock(side_effect=RuntimeError("scar db down"))

        ok, message = dream.reject_proposal(prop_id, reason="too grand")

        self.assertTrue(ok, message)
        self.assertEqual(dream.get_proposal(prop_id)["status"], "rejected")


class DaemonScarHelperTests(unittest.TestCase):
    def _daemon_stub(self):
        daemon = SimpleNamespace()
        daemon.lived_episodes = mock.Mock()
        daemon._scar_sidecar = mock.Mock()
        return daemon

    def test_record_scar_event_flag_off_is_noop(self):
        from core.learning.scar_tissue import ScarEvent
        from daemon.maez_daemon import MaezDaemon

        daemon = self._daemon_stub()
        event = ScarEvent(
            scar_class="dream_rejected",
            surface="dream",
            context="proposal 7",
            correction="rejected",
            receipt_refs=["dream:7"],
            dedup_key="dream:7",
        )
        with (
            mock.patch.dict(os.environ, {"MAEZ_SCAR_TISSUE": "0"}, clear=False),
            mock.patch("core.learning.scar_tissue.record_scar") as record_scar,
        ):
            result = MaezDaemon._record_scar_event(daemon, event)

        self.assertFalse(result)
        record_scar.assert_not_called()

    def test_record_scar_event_flag_on_calls_core_and_fails_safe(self):
        from core.learning.scar_tissue import ScarEvent
        from daemon.maez_daemon import MaezDaemon

        daemon = self._daemon_stub()
        event = ScarEvent(
            scar_class="veto_proven_wrong",
            surface="daemon",
            context="veto event v1",
            correction="veto was likely wrong",
            receipt_refs=["veto:v1"],
            dedup_key="veto:v1",
        )
        with (
            mock.patch.dict(os.environ, {"MAEZ_SCAR_TISSUE": "1"}, clear=False),
            mock.patch(
                "core.learning.scar_tissue.record_scar",
                side_effect=[{"episode_id": "ep-1"}, RuntimeError("down")],
            ) as record_scar,
        ):
            self.assertTrue(MaezDaemon._record_scar_event(daemon, event))
            self.assertFalse(MaezDaemon._record_scar_event(daemon, event))

        self.assertEqual(record_scar.call_count, 2)

    def test_fabrication_helper_uses_receipt_ids_and_skips_mismatches(self):
        from core.safety.self_claim_audit import AuditResult, Flag
        from daemon.maez_daemon import MaezDaemon

        daemon = SimpleNamespace(_record_scar_event=mock.Mock(return_value=True))
        clean = AuditResult(
            text="x",
            mode="action_claim_mismatch",
            fabrication_receipt_ids=None,
        )
        MaezDaemon._record_fabrication_scars_from_audit_result(
            daemon,
            clean,
            surface="telegram",
        )
        daemon._record_scar_event.assert_not_called()

        flagged = AuditResult(
            text="safe",
            rewritten=True,
            mode="sentence",
            flags=[
                Flag(
                    kind="judge",
                    span=(0, 10),
                    text="bad claim",
                    reason="no receipt",
                )
            ],
            fabrication_receipt_ids=[9],
        )
        MaezDaemon._record_fabrication_scars_from_audit_result(
            daemon,
            flagged,
            surface="telegram",
        )
        daemon._record_scar_event.assert_called_once()
        event = daemon._record_scar_event.call_args.args[0]
        self.assertEqual(event.scar_class, "fabrication_catch")
        self.assertIn("fabrication:9", event.receipt_refs)
        self.assertTrue(event.dedup_key.startswith("fabrication:"))

    def test_fabrication_helper_deduplicates_by_claim_text_not_receipt_id(self):
        from core.safety.self_claim_audit import AuditResult, Flag
        from daemon.maez_daemon import MaezDaemon

        daemon = SimpleNamespace(_record_scar_event=mock.Mock(return_value=True))
        for receipt_id in (9, 10):
            flagged = AuditResult(
                text="safe",
                rewritten=True,
                mode="sentence",
                flags=[
                    Flag(
                        kind="judge",
                        span=(0, 10),
                        text="same unsupported claim",
                        reason="no receipt",
                    )
                ],
                fabrication_receipt_ids=[receipt_id],
            )
            MaezDaemon._record_fabrication_scars_from_audit_result(
                daemon,
                flagged,
                surface="telegram",
            )

        first = daemon._record_scar_event.call_args_list[0].args[0]
        second = daemon._record_scar_event.call_args_list[1].args[0]
        self.assertEqual(first.dedup_key, second.dedup_key)
        self.assertEqual(first.receipt_refs, ["fabrication:9"])
        self.assertEqual(second.receipt_refs, ["fabrication:10"])

    def test_claim_redo_helper_records_minted_receipt_class(self):
        from core.safety.self_claim_audit import ActionClaimMismatch
        from daemon.maez_daemon import MaezDaemon

        daemon = SimpleNamespace(_record_scar_event=mock.Mock(return_value=True))
        mismatch = ActionClaimMismatch(
            action_type="web_search",
            pattern_id="search_initiating",
            claim_text="Initiating live search",
            receipt_present=False,
            tense_class="present_progressive",
            reason="no receipt",
        )

        MaezDaemon._record_claim_receipt_redo_scar(
            daemon,
            mismatch,
            surface="telegram",
            outcome="floor",
        )

        event = daemon._record_scar_event.call_args.args[0]
        self.assertEqual(event.scar_class, "claim_receipt_redo")
        self.assertEqual(event.receipt_refs, [])
        self.assertEqual(event.dedup_key, "redo:web_search:search_initiating")

    def test_dream_and_veto_helpers_build_receipt_refs(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = SimpleNamespace(_record_scar_event=mock.Mock(return_value=True))

        MaezDaemon._record_dream_rejection_scar(daemon, prop_id=7, reason="too broad")
        MaezDaemon._record_veto_proven_wrong_scar(daemon, event_id="veto-1")

        dream_event = daemon._record_scar_event.call_args_list[0].args[0]
        veto_event = daemon._record_scar_event.call_args_list[1].args[0]
        self.assertEqual(dream_event.scar_class, "dream_rejected")
        self.assertIn("dream:7", dream_event.receipt_refs)
        self.assertEqual(veto_event.scar_class, "veto_proven_wrong")
        self.assertIn("veto:veto-1", veto_event.receipt_refs)


class CardScarHookTests(unittest.TestCase):
    def _pipeline(self, *, scar_hook=None):
        from core.decision.decision_pipeline import DecisionPipeline

        card = SimpleNamespace(
            request_id="card-1",
            action="run_shell",
            params={"cmd": "apt install imaginary"},
            audit_request_id="audit-1",
        )
        card_store = mock.Mock()
        card_store.deny.return_value = card
        return DecisionPipeline(
            action_engine=mock.Mock(),
            card_store=card_store,
            audit_log=mock.Mock(),
            renderer=None,
            scar_hook=scar_hook,
        ), card_store

    def test_card_rejected_flag_off_keeps_single_consequence_write_no_scar(self):
        pipeline, card_store = self._pipeline(scar_hook=mock.Mock())
        cls = SimpleNamespace(source="telegram", reasoning="no")
        with (
            mock.patch.dict(os.environ, {"MAEZ_SCAR_TISSUE": "0"}, clear=False),
            mock.patch("core.consequence_memory.record_event", return_value=55) as rec,
            mock.patch("core.inner_residue.record"),
        ):
            result = pipeline._on_deny(
                card_store.deny.return_value,
                cls,
                user_id="rohit",
            )

        self.assertEqual(result.message, "Card denied.")
        rec.assert_called_once()
        pipeline.scar_hook.assert_not_called()

    def test_card_rejected_flag_on_calls_scar_hook_with_existing_consequence_id(self):
        scar_hook = mock.Mock()
        pipeline, card_store = self._pipeline(scar_hook=scar_hook)
        cls = SimpleNamespace(source="telegram", reasoning="too risky")
        with (
            mock.patch.dict(os.environ, {"MAEZ_SCAR_TISSUE": "1"}, clear=False),
            mock.patch("core.consequence_memory.record_event", return_value=55),
            mock.patch("core.inner_residue.record"),
        ):
            pipeline._on_deny(card_store.deny.return_value, cls, user_id="rohit")

        scar_hook.assert_called_once()
        kwargs = scar_hook.call_args.kwargs
        self.assertEqual(kwargs["consequence_id"], 55)
        event = kwargs["event"]
        self.assertEqual(event.scar_class, "card_rejected")
        self.assertEqual(event.receipt_refs, ["card:card-1"])
        self.assertEqual(event.dedup_key, "card:card-1")

    def test_card_rejected_uses_house_strict_flag_parser(self):
        scar_hook = mock.Mock()
        pipeline, card_store = self._pipeline(scar_hook=scar_hook)
        cls = SimpleNamespace(source="telegram", reasoning="too risky")
        with (
            mock.patch.dict(os.environ, {"MAEZ_SCAR_TISSUE": "yes"}, clear=False),
            mock.patch("core.consequence_memory.record_event", return_value=55),
            mock.patch("core.inner_residue.record"),
        ):
            pipeline._on_deny(card_store.deny.return_value, cls, user_id="rohit")

        scar_hook.assert_called_once()

    def test_card_rejected_scar_hook_exception_does_not_break_deny(self):
        pipeline, card_store = self._pipeline(
            scar_hook=mock.Mock(side_effect=RuntimeError("scar unavailable"))
        )
        cls = SimpleNamespace(source="telegram", reasoning="no")
        with (
            mock.patch.dict(os.environ, {"MAEZ_SCAR_TISSUE": "1"}, clear=False),
            mock.patch("core.consequence_memory.record_event", return_value=55),
            mock.patch("core.inner_residue.record"),
        ):
            result = pipeline._on_deny(
                card_store.deny.return_value,
                cls,
                user_id="rohit",
            )

        self.assertEqual(result.message, "Card denied.")


if __name__ == "__main__":
    unittest.main()
