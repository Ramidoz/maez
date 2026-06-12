from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from core.cognition.intake_faculty import FakeIntakeBackend, IntakeRead
from core.cognition import intake_shadow as shadow
from core.search.search_commitment import OfferReceipt


class _Controller:
    def __init__(self, offer=None, awaiting_card=False):
        self.offer = offer
        self.awaiting_card = awaiting_card
        self.mutated = False

    def get_search_offer(self, channel, chat_id):
        return self.offer

    def has_awaiting_card(self, channel, chat_id):
        return self.awaiting_card

    def consume_offer_approval(self, *args, **kwargs):
        self.mutated = True
        raise AssertionError("shadow must not consume offers")


class TelemetryTests(unittest.TestCase):
    def test_content_light_default_excludes_owner_text(self):
        read = IntakeRead(
            turn_kind="commitment_response",
            stance="yes",
            boundary_signal="none",
            needs="search",
            referent_kind="pending_offer",
            confidence=0.9,
            rationale="Owner said proceed to the search.",
        )

        rec = shadow.build_telemetry(
            message="Proceed with the llama.cpp search",
            context_turns=["Rohit: private prior text", "Maez: private reply"],
            pending_offer={
                "action_type": "web_search",
                "stakes": "low_read",
                "egress_class": "sovereign_local_search",
                "offered_query": "llama.cpp release",
            },
            faculty_read=read,
            gate_verdicts={"is_clear_yes": "false"},
            status="ok",
            latency_s=0.012,
            debug=False,
        )

        blob = json.dumps(rec)
        self.assertIn("turn_hash", rec)
        self.assertIn("context_hash", rec)
        self.assertNotIn("Proceed", blob)
        self.assertNotIn("private prior text", blob)
        self.assertNotIn("llama.cpp release", blob)
        self.assertNotIn("Owner said", blob)

    def test_debug_can_include_bounded_snippets(self):
        read = IntakeRead(
            turn_kind="ordinary",
            stance="n_a",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=0.8,
            rationale="debug rationale",
        )

        rec = shadow.build_telemetry(
            message="hello there",
            context_turns=[],
            pending_offer=None,
            faculty_read=read,
            gate_verdicts={},
            status="ok",
            latency_s=0.0,
            debug=True,
        )

        self.assertEqual(rec["turn_excerpt"], "hello there")
        self.assertEqual(rec["faculty_read"]["rationale"], "debug rationale")

    def test_gate_snapshot_is_read_only(self):
        offer = OfferReceipt(
            action_type="web_search",
            stakes="low_read",
            offered_query="x",
            created_ts=1.0,
            ttl_seconds=300.0,
            ttl_turns=3,
            requires_confirmation=True,
            confirmation_mode="clear_yes_ok",
            executor="searxng",
            egress_class="sovereign_local_search",
        )
        ctrl = _Controller(offer=offer)

        verdicts = shadow.gate_verdicts(
            "proceed",
            controller=ctrl,
            channel="telegram_text",
            chat_id="c",
        )

        self.assertEqual(verdicts["is_clear_yes"], "false")
        self.assertIn(verdicts["hard_want"], {"true", "false"})
        self.assertIn(verdicts["continuity"], {"true", "false", "unavailable"})
        self.assertIn("continuity_kind", verdicts)
        self.assertFalse(ctrl.mutated)
        self.assertIs(ctrl.get_search_offer("telegram_text", "c"), offer)

    def test_pending_offer_snapshot_hashes_query(self):
        offer = OfferReceipt(
            action_type="web_search",
            stakes="low_read",
            offered_query="private query text",
            created_ts=1.0,
            ttl_seconds=300.0,
            ttl_turns=3,
            requires_confirmation=True,
            confirmation_mode="clear_yes_ok",
            executor="searxng",
            egress_class="sovereign_local_search",
        )

        snap = shadow.offer_snapshot(offer)

        self.assertEqual(snap["action_type"], "web_search")
        self.assertEqual(snap["stakes"], "low_read")
        self.assertEqual(snap["egress_class"], "sovereign_local_search")
        self.assertIn("offered_query_hash", snap)
        self.assertNotIn("private query text", json.dumps(snap))

    def test_build_telemetry_sanitizes_raw_pending_offer_dict(self):
        read = IntakeRead(
            turn_kind="ordinary",
            stance="n_a",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=0.8,
        )

        rec = shadow.build_telemetry(
            message="hello",
            context_turns=[],
            pending_offer={
                "action_type": "web_search",
                "stakes": "low_read",
                "executor": "searxng",
                "egress_class": "sovereign_local_search",
                "offered_query": "private raw query",
            },
            faculty_read=read,
            gate_verdicts={},
            status="ok",
            latency_s=0.0,
            debug=False,
        )

        blob = json.dumps(rec)
        self.assertIn("offered_query_hash", blob)
        self.assertNotIn("private raw query", blob)


class _Memory:
    def __init__(self, turns=None, raises=None):
        self.turns = turns if turns is not None else [
            {"content": "Rohit: prior\nMaez: reply"},
            {"content": "Rohit: second\nMaez: reply"},
        ]
        self.raises = raises

    def get_telegram_exchanges(self, limit=6):
        if self.raises:
            raise self.raises
        return self.turns[:limit]


class IntakeShadowQueueTests(unittest.TestCase):
    def _path(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        return Path(td.name) / "intake_shadow.jsonl"

    def test_full_queue_returns_enqueue_failed_without_raising(self):
        path = self._path()
        sh = shadow.IntakeShadow(FakeIntakeBackend(), path, maxsize=1)

        self.assertEqual(sh.enqueue({"message": "one"}), "enqueued")
        self.assertEqual(sh.enqueue({"message": "two"}), "enqueue_failed")

        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(rows[-1]["status"], "enqueue_failed")

    def test_worker_writes_content_light_record(self):
        path = self._path()
        backend = FakeIntakeBackend(default=IntakeRead(
            turn_kind="commitment_response",
            stance="yes",
            boundary_signal="none",
            needs="search",
            referent_kind="pending_offer",
            confidence=0.9,
            rationale="private rationale",
        ))
        sh = shadow.IntakeShadow(backend, path, maxsize=4, debug=False)
        sh.start()
        self.addCleanup(sh.stop)

        self.assertEqual(sh.enqueue({
            "message": "Proceed with private topic",
            "surface": "telegram_surface",
            "chat_id": "c",
            "context_provider": lambda: ["Rohit: private prior"],
            "pending_offer": None,
            "gate_verdicts": {"is_clear_yes": "false"},
        }), "enqueued")

        deadline = time.time() + 2.0
        while time.time() < deadline and not path.exists():
            time.sleep(0.02)

        rows = [json.loads(line) for line in path.read_text().splitlines()]
        blob = json.dumps(rows[-1])
        self.assertEqual(rows[-1]["status"], "ok")
        self.assertNotIn("Proceed", blob)
        self.assertNotIn("private prior", blob)
        self.assertNotIn("private rationale", blob)

    def test_busy_backend_drops_sample_as_judge_busy(self):
        path = self._path()
        sh = shadow.IntakeShadow(FakeIntakeBackend(busy=True), path, maxsize=4)
        sh.start()
        self.addCleanup(sh.stop)

        sh.enqueue({
            "message": "anything",
            "surface": "telegram_surface",
            "chat_id": "c",
            "context_provider": lambda: [],
            "pending_offer": None,
            "gate_verdicts": {},
        })

        deadline = time.time() + 2.0
        while time.time() < deadline and not path.exists():
            time.sleep(0.02)

        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(rows[-1]["status"], "judge_busy")

    def test_rotation_keeps_file_bounded(self):
        path = self._path()
        sh = shadow.IntakeShadow(FakeIntakeBackend(), path, maxsize=4, rotate_bytes=120, rotate_keep=2)

        for idx in range(8):
            sh._emit({"status": "ok", "idx": idx, "payload": "x" * 100})

        files = sorted(path.parent.glob("intake_shadow.jsonl*"))
        self.assertLessEqual(len(files), 3)  # active + 2 rotated


class HookTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_INTAKE_FACULTY_SHADOW", None)
        os.environ.pop("MAEZ_INTAKE_FACULTY_DEBUG", None)
        shadow.reset_shadow_singleton()
        self.addCleanup(shadow.reset_shadow_singleton)
        self.addCleanup(lambda: os.environ.pop("MAEZ_INTAKE_FACULTY_SHADOW", None))
        self.addCleanup(lambda: os.environ.pop("MAEZ_INTAKE_FACULTY_DEBUG", None))

    def test_flag_off_returns_disabled_and_builds_nothing(self):
        result = shadow.observe_owner_turn(
            "proceed",
            surface="telegram_surface",
            chat_id="c",
            controller=_Controller(),
            memory=_Memory(),
        )

        self.assertEqual(result, "disabled")

    def test_flag_on_enqueues_without_fetching_context_on_live_path(self):
        os.environ["MAEZ_INTAKE_FACULTY_SHADOW"] = "1"
        path = Path(tempfile.mkdtemp()) / "intake_shadow.jsonl"
        sh = shadow.IntakeShadow(FakeIntakeBackend(), path, maxsize=4)
        shadow.set_shadow_singleton(sh)
        memory = _Memory(raises=AssertionError("context fetch should happen in worker, not enqueue"))

        result = shadow.observe_owner_turn(
            "proceed",
            surface="telegram_surface",
            chat_id="c",
            controller=_Controller(),
            memory=memory,
        )

        self.assertEqual(result, "enqueued")

    def test_context_provider_fetches_six_turns_when_worker_runs(self):
        os.environ["MAEZ_INTAKE_FACULTY_SHADOW"] = "1"
        path = Path(tempfile.mkdtemp()) / "intake_shadow.jsonl"
        backend = FakeIntakeBackend()
        sh = shadow.IntakeShadow(backend, path, maxsize=4)
        sh.start()
        self.addCleanup(sh.stop)
        shadow.set_shadow_singleton(sh)

        shadow.observe_owner_turn(
            "proceed",
            surface="telegram_surface",
            chat_id="c",
            controller=_Controller(),
            memory=_Memory(turns=[{"content": f"turn-{i}"} for i in range(8)]),
        )

        deadline = time.time() + 2.0
        while time.time() < deadline and not backend.calls:
            time.sleep(0.02)

        self.assertEqual(len(backend.calls[0][1]["turns"]), 6)
