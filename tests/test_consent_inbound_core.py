from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

import daemon.inbound_core as core_mod
from core.consent.bindings import BindingRegistry, ConsentBindingPaths
from core.consent.resolution import ConsentResolutionPaths
from core.consent.spine import ConsentSpineStore
from tests.test_inbound_core_equivalence import (
    FakeBrainResult,
    FakeDaemon,
    _make_inline_run_in_executor,
    _make_observe_turn,
    _make_run_brain_loop,
)


@dataclass(frozen=True)
class _Card:
    request_id: str
    action: str = "note"
    proposed_action_summary: str = "write a note"
    created_at: float = 1000.0
    status: str = "open"


class CountingCardStore:
    def __init__(self, trace, initial_cards=()):
        self.trace = trace
        self.cards = list(initial_cards)
        self.calls = 0

    def get_open_for_channel(self, channel, *, chat_id):
        self.calls += 1
        self.trace.append(("card_store.get_open_for_channel", channel, chat_id, self.calls))
        if self.calls == 1:
            return list(self.cards)
        return [*self.cards, _Card("mid-turn-card")]

    def get(self, request_id):
        for card in self.cards:
            if card.request_id == request_id:
                return card
        return None


class CountingPipe:
    def __init__(self, trace, card_store):
        self._trace = trace
        self.card_store = card_store

    def handle_reply(self, **kwargs):
        self._trace.append(("pipe.handle_reply", kwargs))
        return None


async def _noop_proposal(**kwargs):
    return None


async def _noop_search(**kwargs):
    return None


class ConsentInboundCoreTests(unittest.TestCase):
    def _run_core(
        self,
        *,
        env,
        raw_platform_metadata=None,
        open_cards=(),
        brain_result=None,
        registry=None,
        spine_store=None,
        approve_channel=None,
        resolution_paths=None,
    ):
        trace = []
        card_store = CountingCardStore(trace, open_cards)
        pipe = CountingPipe(trace, card_store)
        daemon = FakeDaemon(trace, pipe=pipe, memory=None, reply="final reply")
        loop = asyncio.new_event_loop()
        inline_run, _ = _make_inline_run_in_executor(loop)
        observe = _make_observe_turn(trace)
        rbl = _make_run_brain_loop(trace, brain_result or FakeBrainResult())
        fake_brain_mod = mock.MagicMock()
        fake_brain_mod.run_brain_loop = rbl
        fake_obs_mod = mock.MagicMock()
        fake_obs_mod.observe_turn = observe

        with mock.patch.dict(os.environ, env, clear=False):
            if "MAEZ_CONVERSATIONAL_CONSENT_ENABLED" not in env:
                os.environ.pop("MAEZ_CONVERSATIONAL_CONSENT_ENABLED", None)
            with mock.patch.object(loop, "run_in_executor", inline_run), \
                 mock.patch.object(core_mod, "surface_parity_enabled", lambda: False), \
                 mock.patch.object(core_mod, "get_shared_executor", lambda: None), \
                 mock.patch.dict("sys.modules", {"core.brain_loop": fake_brain_mod, "core.observability": fake_obs_mod}):
                result = loop.run_until_complete(
                    core_mod.run_inbound_turn(
                        daemon=daemon,
                        text="approve ABCD",
                        chat_id="222",
                        resolved_user_id="111",
                        reply_to_message_id=None,
                        context_note=None,
                        photo_analysis=None,
                        is_photo_turn=False,
                        owner_surface_label="telegram_owner",
                        user_id="rohit",
                        channel="telegram_text",
                        owner_auth_factory=lambda: None,
                        observe_turn_label="telegram_turn",
                        chat_history_turns=3,
                        action_engine="actions",
                        get_pipeline=lambda: pipe,
                        chat_history_provider=lambda limit: [],
                        try_proposal_intent=_noop_proposal,
                        try_search_commitment_intent=_noop_search,
                        search_commitment_controller=lambda: None,
                        audit_surface_reply=lambda text, surface: text,
                        clean_exchange=lambda text: text,
                        send_intermediate=lambda text: None,
                        send_progress_receipt=lambda *args, **kwargs: None,
                        raw_platform_metadata=raw_platform_metadata,
                        consent_binding_registry=registry,
                        consent_spine_store=spine_store,
                        consent_approve_channel=approve_channel,
                        consent_resolution_paths=resolution_paths,
                    )
                )
        loop.close()
        return result, trace, card_store

    def test_flag_off_takes_no_top_of_turn_snapshot_and_keeps_legacy_timing(self):
        result, trace, card_store = self._run_core(
            env={"MAEZ_CONVERSATIONAL_CONSENT_ENABLED": "0"},
            raw_platform_metadata={"from_user": {"id": "111"}, "chat": {"id": "222"}},
            open_cards=[],
        )

        self.assertEqual(result, "final reply")
        self.assertEqual(card_store.calls, 1)
        self.assertNotIn("consent.snapshot", [row[0] for row in trace])

    def test_unbound_turn_takes_no_snapshot_even_when_flag_on(self):
        with tempfile.TemporaryDirectory() as td:
            registry = BindingRegistry(
                ConsentBindingPaths(
                    db_path=Path(td) / "bindings.sqlite3",
                    receipt_log=Path(td) / "bindings.jsonl",
                )
            )
            result, trace, card_store = self._run_core(
                env={"MAEZ_CONVERSATIONAL_CONSENT_ENABLED": "1"},
                raw_platform_metadata={"from_user": {"id": "111"}, "chat": {"id": "222"}},
                open_cards=[],
                registry=registry,
            )

        self.assertEqual(result, "final reply")
        self.assertEqual(card_store.calls, 1)
        self.assertNotIn("consent.snapshot", [row[0] for row in trace])

    def test_unbound_default_path_does_not_create_consent_db(self):
        with tempfile.TemporaryDirectory() as td:
            result, trace, card_store = self._run_core(
                env={
                    "MAEZ_CONVERSATIONAL_CONSENT_ENABLED": "1",
                    "MAEZ_DATA": td,
                },
                raw_platform_metadata={"from_user": {"id": "111"}, "chat": {"id": "222"}},
                open_cards=[],
                registry=None,
                spine_store=None,
            )
            self.assertEqual(result, "final reply")
            self.assertEqual(card_store.calls, 1)
            self.assertFalse((Path(td) / "memory" / "consent").exists())
            self.assertNotIn("consent.snapshot", [row[0] for row in trace])

    def test_bound_flag_on_turn_uses_single_authoritative_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = BindingRegistry(
                ConsentBindingPaths(
                    db_path=root / "bindings.sqlite3",
                    receipt_log=root / "bindings.jsonl",
                )
            )
            registry.enroll("telegram", "111:222", enrolled_via="cli")
            spine = ConsentSpineStore(root / "spine.sqlite3", token_generator=lambda: "SNAP")

            result, trace, card_store = self._run_core(
                env={"MAEZ_CONVERSATIONAL_CONSENT_ENABLED": "1"},
                raw_platform_metadata={"from_user": {"id": "111"}, "chat": {"id": "222"}},
                open_cards=[],
                registry=registry,
                spine_store=spine,
            )

        self.assertEqual(result, "final reply")
        self.assertEqual(card_store.calls, 1)
        self.assertIn("consent.snapshot", [row[0] for row in trace])
        self.assertNotIn("pipe.handle_reply", [row[0] for row in trace])

    def test_active_flow_suppresses_legacy_resolver_and_brain_sees_turn(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = BindingRegistry(
                ConsentBindingPaths(
                    db_path=root / "bindings.sqlite3",
                    receipt_log=root / "bindings.jsonl",
                )
            )
            binding = registry.enroll("telegram", "111:222", enrolled_via="cli")
            spine = ConsentSpineStore(root / "spine.sqlite3", token_generator=lambda: "ABCD")
            spine.surface_card(
                binding_id=binding.binding_id,
                card_id="card-1",
                decision="approve",
                now=1000.0,
            )

            result, trace, _ = self._run_core(
                env={"MAEZ_CONVERSATIONAL_CONSENT_ENABLED": "1"},
                raw_platform_metadata={"from_user": {"id": "111"}, "chat": {"id": "222"}},
                open_cards=[_Card("card-1")],
                registry=registry,
                spine_store=spine,
            )

        kinds = [row[0] for row in trace]
        self.assertEqual(result, "final reply")
        self.assertNotIn("pipe.handle_reply", kinds)
        self.assertIn("run_brain_loop", kinds)

    def test_senderless_raw_metadata_is_unverifiable_and_never_constructs_utterance(self):
        refusal = core_mod.extract_owner_utterance_from_raw_metadata(
            surface_label="telegram_owner",
            text="approve it",
            reply_to_message_id=None,
            raw_platform_metadata={"chat": {"id": "222"}},
            binding_registry=None,
        )

        self.assertEqual(refusal.refusal_code, "surface_identity_unverifiable")
        self.assertIsNone(refusal.utterance)

    def test_brain_failure_during_suppressed_turn_returns_intent_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = BindingRegistry(
                ConsentBindingPaths(
                    db_path=root / "bindings.sqlite3",
                    receipt_log=root / "bindings.jsonl",
                )
            )
            binding = registry.enroll("telegram", "111:222", enrolled_via="cli")
            spine = ConsentSpineStore(root / "spine.sqlite3", token_generator=lambda: "ABCD")
            spine.surface_card(binding_id=binding.binding_id, card_id="card-1", decision="approve")

            class RaisingBrain:
                pass

            trace = []
            card_store = CountingCardStore(trace, [_Card("card-1")])
            pipe = CountingPipe(trace, card_store)
            daemon = FakeDaemon(trace, pipe=pipe, memory=None, reply="final reply")
            loop = asyncio.new_event_loop()
            inline_run, _ = _make_inline_run_in_executor(loop)
            fake_brain_mod = mock.MagicMock()

            def _raise(*args, **kwargs):
                trace.append(("run_brain_loop", "raised"))
                raise RuntimeError("brain down")

            fake_brain_mod.run_brain_loop = _raise
            fake_obs_mod = mock.MagicMock()
            fake_obs_mod.observe_turn = _make_observe_turn(trace)
            with mock.patch.dict(os.environ, {"MAEZ_CONVERSATIONAL_CONSENT_ENABLED": "1"}), \
                 mock.patch.object(loop, "run_in_executor", inline_run), \
                 mock.patch.object(core_mod, "surface_parity_enabled", lambda: False), \
                 mock.patch.object(core_mod, "get_shared_executor", lambda: None), \
                 mock.patch.dict("sys.modules", {"core.brain_loop": fake_brain_mod, "core.observability": fake_obs_mod}):
                result = loop.run_until_complete(
                    core_mod.run_inbound_turn(
                        daemon=daemon,
                        text="approve ABCD",
                        chat_id="222",
                        resolved_user_id="111",
                        reply_to_message_id=None,
                        context_note=None,
                        photo_analysis=None,
                        is_photo_turn=False,
                        owner_surface_label="telegram_owner",
                        user_id="rohit",
                        channel="telegram_text",
                        owner_auth_factory=lambda: None,
                        observe_turn_label="telegram_turn",
                        chat_history_turns=3,
                        action_engine="actions",
                        get_pipeline=lambda: pipe,
                        chat_history_provider=lambda limit: [],
                        try_proposal_intent=_noop_proposal,
                        try_search_commitment_intent=_noop_search,
                        search_commitment_controller=lambda: None,
                        audit_surface_reply=lambda text, surface: text,
                        clean_exchange=lambda text: text,
                        send_intermediate=lambda text: None,
                        send_progress_receipt=lambda *args, **kwargs: None,
                        raw_platform_metadata={"from_user": {"id": "111"}, "chat": {"id": "222"}},
                        consent_binding_registry=registry,
                        consent_spine_store=spine,
                    )
                )
            loop.close()

        self.assertEqual(result, "intent_unavailable")
        self.assertNotIn("pipe.handle_reply", [row[0] for row in trace])

    def test_refused_receipt_does_not_mark_flow_resolved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = BindingRegistry(
                ConsentBindingPaths(
                    db_path=root / "bindings.sqlite3",
                    receipt_log=root / "bindings.jsonl",
                )
            )
            binding = registry.enroll("telegram", "111:222", enrolled_via="cli")
            spine = ConsentSpineStore(root / "spine.sqlite3", token_generator=lambda: "ABCD")
            spine.surface_card(binding_id=binding.binding_id, card_id="card-1", decision="approve")

            brain = FakeBrainResult()
            brain.consent_intent = __import__(
                "core.consent.spine",
                fromlist=["ConsentIntent"],
            ).ConsentIntent(kind="approve", card_hint="ABCD", confidence=0.95)
            result, trace, _ = self._run_core(
                env={"MAEZ_CONVERSATIONAL_CONSENT_ENABLED": "1"},
                raw_platform_metadata={"from_user": {"id": "111"}, "chat": {"id": "222"}},
                open_cards=[_Card("card-1")],
                brain_result=brain,
                registry=registry,
                spine_store=spine,
                approve_channel=lambda *_: {
                    "ok": False,
                    "http_status": 403,
                    "error": "s7_authorization_required",
                    "status": "blocked",
                },
                resolution_paths=ConsentResolutionPaths(
                    receipt_log=root / "consent_receipts.jsonl"
                ),
            )
            self.assertEqual(result, "final reply")
            self.assertNotEqual(spine.active_flow_state(binding.binding_id), "RESOLVED")
            self.assertIn(("consent.receipt", "refused", "s7_ceremony_required"), trace)


class ConsentBrainLoopResultTests(unittest.TestCase):
    def test_brain_loop_result_has_additive_consent_intent_default_none(self):
        from core.brain.brain_loop import BrainLoopResult

        result = BrainLoopResult(transcript="x")
        self.assertIsNone(result.consent_intent)
        self.assertEqual(result.transcript, "x")


class ConsentAdapterBoundaryTests(unittest.TestCase):
    def test_maez_adapter_has_no_consent_imports(self):
        # Amendment A1 permits exactly ONE consent-adjacent element in the
        # adapter: the raw_platform_metadata pass-through in the descriptor.
        # The adapter must still never import consent machinery.
        text = Path("/home/rohit/maez/skills/surface/maez_adapter.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("core.consent", text)
        self.assertNotIn("ConsentIntent", text)

    def test_descriptor_passes_raw_platform_metadata(self):
        """Amendment A1: the live-path descriptor carries event.raw_message
        verbatim as raw_platform_metadata so raw-identity extraction can run
        server-side. Flag-off inertness is inbound_core's (already tested);
        this pins the adapter seam itself."""
        import asyncio
        from types import SimpleNamespace

        from skills.surface.maez_adapter import MaezMessageHandler

        daemon = SimpleNamespace(memory=None, actions=None, telegram=None)
        handler = MaezMessageHandler(daemon)
        raw = SimpleNamespace(
            from_user=SimpleNamespace(id=111),
            chat=SimpleNamespace(id=222),
            forward_origin=None,
        )
        event = SimpleNamespace(
            text="approve it",
            source=SimpleNamespace(chat_id="222", user_id="111"),
            message_type=None,
            channel_prompt=None,
            photo_analysis_text=None,
            reply_to_message_id=None,
            raw_message=raw,
        )
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            descriptor = handler._build_inbound_descriptor(event)
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        self.assertIn("raw_platform_metadata", descriptor)
        self.assertIs(descriptor["raw_platform_metadata"], raw)


if __name__ == "__main__":
    unittest.main()
