from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.consent.bindings import BindingRegistry, ConsentBindingPaths
from core.consent.resolution import ConsentResolutionPaths, ConsentResolutionRequest, resolve_consent_decision
from core.consent.spine import ConsentIntent, ConsentSpineStore, OwnerUtterance
from core.pending_cards import PendingCardStore


def _utterance(*, fresh: bool = True, identity: str = "111:222") -> OwnerUtterance:
    return OwnerUtterance(
        surface_kind="telegram",
        surface_identity=identity,
        text="approve ABCD",
        fresh=fresh,
        reply_to_ref=None,
        at="2026-07-08T00:00:00Z",
    )


class ConsentResolutionRailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.binding_paths = ConsentBindingPaths(
            db_path=root / "memory" / "consent" / "owner_surface_bindings.sqlite3",
            receipt_log=root / "logs" / "consent_binding_receipts.jsonl",
        )
        self.resolution_paths = ConsentResolutionPaths(
            receipt_log=root / "logs" / "consent_receipts.jsonl",
        )
        self.registry = BindingRegistry(self.binding_paths)
        self.binding = self.registry.enroll("telegram", "111:222", enrolled_via="cli")
        self.store = PendingCardStore(root / "memory" / "pending_cards.db")
        self.card = self.store.create_card(
            action="note",
            params={"text": "hello"},
            proposed_action_summary="write a note",
            channel="telegram_text",
            chat_id="222",
            user_id="111",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _request(self, **overrides):
        data = {
            "utterance": _utterance(),
            "intent": ConsentIntent(kind="approve", card_hint="ABCD", confidence=0.9),
            "binding_id": self.binding.binding_id,
            "card_id": self.card.request_id,
            "decision": "approve",
        }
        data.update(overrides)
        return ConsentResolutionRequest(**data)

    def _receipt_rows(self):
        if not self.resolution_paths.receipt_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.resolution_paths.receipt_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_every_refusal_code_has_a_reachable_rail(self):
        cases = []

        cases.append(("consent_flag_off", {"flag_enabled": False}, {}))
        cases.append(("surface_identity_unverifiable", {}, {"identity_verified": False}))

        other_registry = BindingRegistry(
            ConsentBindingPaths(
                db_path=Path(self.tmp.name) / "other" / "bindings.sqlite3",
                receipt_log=Path(self.tmp.name) / "other" / "bindings.jsonl",
            )
        )
        cases.append(("surface_not_bound", {"binding_registry": other_registry}, {}))
        cases.append(("card_not_found", {}, {"card_id": "missing"}))

        denied = self.store.deny(
            self.card.request_id,
            user_id="111",
            via="test",
            notes="already denied",
        )
        cases.append(("card_not_awaiting", {}, {"card_id": denied.request_id}))

        fresh_card = self.store.create_card(
            action="note",
            params={},
            proposed_action_summary="write another note",
            channel="telegram_text",
            chat_id="333",
            user_id="111",
        )
        cases.extend(
            [
                ("echo_expired", {}, {"card_id": fresh_card.request_id, "echo_status": "expired"}),
                ("echo_ambiguous", {}, {"card_id": fresh_card.request_id, "echo_status": "ambiguous"}),
                ("utterance_not_fresh", {}, {"card_id": fresh_card.request_id, "utterance": _utterance(fresh=False)}),
                ("intent_unavailable", {}, {"card_id": fresh_card.request_id, "intent": None}),
                (
                    "approval_channel_unavailable",
                    {"approve_channel": None},
                    {"card_id": fresh_card.request_id},
                ),
            ]
        )

        for expected, kw_overrides, request_overrides in cases:
            with self.subTest(expected):
                request = self._request(**request_overrides)
                receipt = resolve_consent_decision(
                    request,
                    card_store=self.store,
                    binding_registry=kw_overrides.get("binding_registry", self.registry),
                    paths=self.resolution_paths,
                    flag_enabled=kw_overrides.get("flag_enabled", True),
                    approve_channel=kw_overrides.get("approve_channel", lambda *_: {"ok": False, "http_status": 500}),
                )
                self.assertEqual(receipt["reason"], expected)
                self.assertFalse(receipt["ok"])

    def test_approve_success_requires_upstream_ok_and_post_resolution_reread(self):
        def approve_channel(request_id, payload):
            with sqlite3.connect(self.store.db_path) as conn:
                conn.execute(
                    "UPDATE pending_cards SET status = ?, updated_at = ? WHERE request_id = ?",
                    ("done", 1001.0, request_id),
                )
            return {"ok": True, "http_status": 200, "status": "done"}

        receipt = resolve_consent_decision(
            self._request(),
            card_store=self.store,
            binding_registry=self.registry,
            paths=self.resolution_paths,
            flag_enabled=True,
            approve_channel=approve_channel,
        )

        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["outcome"], "resolved")
        self.assertEqual(receipt["final_card_status"], "done")

    def test_upstream_403_s7_guarded_is_honest_ceremony_refusal(self):
        receipt = resolve_consent_decision(
            self._request(),
            card_store=self.store,
            binding_registry=self.registry,
            paths=self.resolution_paths,
            flag_enabled=True,
            approve_channel=lambda *_: {
                "ok": False,
                "http_status": 403,
                "error": "s7_authorization_required",
                "status": "blocked",
            },
        )

        self.assertFalse(receipt["ok"])
        self.assertEqual(receipt["reason"], "s7_ceremony_required")
        self.assertEqual(receipt["outcome"], "refused")
        self.assertEqual(receipt["final_card_status"], "open")

    def test_upstream_refused_and_unconfirmed_are_not_resolved(self):
        refused = resolve_consent_decision(
            self._request(),
            card_store=self.store,
            binding_registry=self.registry,
            paths=self.resolution_paths,
            flag_enabled=True,
            approve_channel=lambda *_: {"ok": False, "http_status": 403, "error": "no"},
        )
        self.assertEqual(refused["reason"], "upstream_refused")

        unconfirmed_card = self.store.create_card(
            action="note",
            params={},
            proposed_action_summary="write unconfirmed note",
            channel="telegram_text",
            chat_id="444",
            user_id="111",
        )
        unconfirmed = resolve_consent_decision(
            self._request(card_id=unconfirmed_card.request_id),
            card_store=self.store,
            binding_registry=self.registry,
            paths=self.resolution_paths,
            flag_enabled=True,
            approve_channel=lambda *_: {"ok": True, "http_status": 200, "status": "done"},
        )
        self.assertEqual(unconfirmed["reason"], "upstream_unconfirmed")
        self.assertEqual(unconfirmed["outcome"], "unconfirmed")

    def test_deny_routes_through_pending_card_store(self):
        receipt = resolve_consent_decision(
            self._request(
                intent=ConsentIntent(kind="deny", card_hint="ABCD", confidence=0.9),
                decision="deny",
            ),
            card_store=self.store,
            binding_registry=self.registry,
            paths=self.resolution_paths,
            flag_enabled=True,
            approve_channel=None,
        )

        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["final_card_status"], "denied")
        self.assertEqual(self.store.get(self.card.request_id).resolved_via, "conversational_consent")

    def test_canonical_2026_07_07_incident_fixture(self):
        root = Path(self.tmp.name)
        spine = ConsentSpineStore(root / "memory" / "consent" / "flow.sqlite3", token_generator=lambda: "S7K1")
        spine.handle_turn(
            binding_id=self.binding.binding_id,
            utterance=OwnerUtterance(
                surface_kind="telegram",
                surface_identity="111:222",
                text="I'm adding a backup key, if anything approve it.",
                fresh=True,
                reply_to_ref=None,
                at="2026-07-07T21:00:00Z",
            ),
            intent=ConsentIntent(kind="standing_pre_consent", card_hint="backup key", confidence=0.92),
            open_cards=[],
            now=1000.0,
        )
        backup_card = self.store.create_card(
            action="s7_add_backup_key",
            params={"credential": "fixture"},
            proposed_action_summary="add a backup key",
            channel="telegram_text",
            chat_id="222",
            user_id="111",
        )
        surfaced = spine.handle_turn(
            binding_id=self.binding.binding_id,
            utterance=_utterance(),
            intent=ConsentIntent(kind="none", card_hint=None, confidence=0.0),
            open_cards=[backup_card],
            now=1010.0,
        )
        self.assertEqual(surfaced.echo_token, "S7K1")

        resolving = spine.handle_turn(
            binding_id=self.binding.binding_id,
            utterance=OwnerUtterance(
                surface_kind="telegram",
                surface_identity="111:222",
                text="approve S7K1",
                fresh=True,
                reply_to_ref=None,
                at="2026-07-07T21:01:00Z",
            ),
            intent=ConsentIntent(kind="approve", card_hint="S7K1", confidence=0.95),
            open_cards=[backup_card],
            now=1020.0,
        )
        self.assertEqual(resolving.state, "RESOLVING")

        receipt = resolve_consent_decision(
            self._request(card_id=backup_card.request_id),
            card_store=self.store,
            binding_registry=self.registry,
            paths=self.resolution_paths,
            flag_enabled=True,
            approve_channel=lambda *_: {
                "ok": False,
                "http_status": 403,
                "error": "s7_authorization_required",
                "status": "blocked",
            },
        )
        self.assertEqual(receipt["reason"], "s7_ceremony_required")
        self.assertEqual(self.store.get(backup_card.request_id).status, "open")
        self.assertEqual(self._receipt_rows()[-1]["reason"], "s7_ceremony_required")


if __name__ == "__main__":
    unittest.main()
