from __future__ import annotations

import unittest
from types import SimpleNamespace


class _FakeCardStore:
    def __init__(self):
        self.cards = []

    @property
    def last_created(self):
        return self.cards[-1]

    def create_card(self, **kwargs):
        card = SimpleNamespace(
            request_id=f"card-{len(self.cards) + 1}",
            status="open",
            action=kwargs["action"],
            params=kwargs["params"],
            audit_decision=None,
            lane=str((kwargs.get("classification") or {}).get("lane") or ""),
            audit_reasoning=kwargs.get("reason") or "",
            audit_concerns=[],
            state_fields=kwargs.get("state_fields"),
            state_hash="hash",
        )
        self.cards.append(card)
        return card


class _FakeDream:
    def __init__(self, pending):
        self.pending = pending

    def get_proposal(self, prop_id):
        row = self.pending.get(prop_id)
        if row is None:
            return None
        return {"id": prop_id, **row}

    def proposal_fingerprint(self, prop_id):
        row = self.pending.get(prop_id)
        if row is None:
            return {"proposal_id": prop_id, "status": "absent"}
        return {
            "proposal_id": prop_id,
            "proposal_type": row.get("proposal_type") or row.get("kind") or "append",
            "status": row.get("status") or "pending",
            "content_hash": f"h-{prop_id}",
        }


class _FakeDeps:
    def __init__(self, *, pending):
        self.dream = _FakeDream(pending)
        self.card_store = _FakeCardStore()
        self._open_by_proposal = {}
        self.opened = []

    def open_dialog_for_proposal(self, prop_id):
        card_request_id = self._open_by_proposal.get(prop_id)
        if card_request_id is None:
            return None
        card = next(c for c in self.card_store.cards if c.request_id == card_request_id)
        return SimpleNamespace(card_request_id=card.request_id, action=card.action)

    def open_dialog_for_card(self, card):
        self.opened.append(card.request_id)

    def remember_open_dialog(self, prop_id, card_request_id, action):
        self._open_by_proposal[prop_id] = card_request_id

    def dialog_opened_for(self, card_request_id):
        return card_request_id in self.opened

    def s7_request_envelope_hash_for_card(self, card):
        return f"envelope-hash:{card.request_id}"


def _fake_bridge_deps(*, pending):
    return _FakeDeps(pending=pending)


class SeedDialogTest(unittest.TestCase):
    def test_seeds_lane3_card_with_freshness_and_opens_dialog(self):
        from skills.surface.s7_ceremony_bridge import seed_soul_proposal_dialog

        deps = _fake_bridge_deps(
            pending={7: {"proposal_type": "append", "insight": "note text", "status": "pending"}}
        )

        result = seed_soul_proposal_dialog(prop_id=7, deps=deps)

        card = deps.card_store.last_created
        self.assertEqual(card.action, "write_soul_note")
        self.assertIn("note text", card.params["note"])
        self.assertEqual(card.params["_proposal_id"], 7)
        self.assertIn("_proposal_fingerprint", card.params)
        self.assertTrue(card.audit_decision == "ESCALATE" or str(card.lane) == "3")
        self.assertTrue(deps.dialog_opened_for(card.request_id))
        self.assertEqual(result.card_request_id, card.request_id)
        self.assertEqual(result.action, "write_soul_note")

    def test_idempotent_per_open_proposal(self):
        from skills.surface.s7_ceremony_bridge import seed_soul_proposal_dialog

        deps = _fake_bridge_deps(
            pending={7: {"proposal_type": "append", "insight": "x", "status": "pending"}}
        )

        first = seed_soul_proposal_dialog(prop_id=7, deps=deps)
        second = seed_soul_proposal_dialog(prop_id=7, deps=deps)

        self.assertEqual(first.card_request_id, second.card_request_id)
        self.assertEqual(len(deps.card_store.cards), 1)

    def test_edit_proposal_seeds_edit_soul_section(self):
        from skills.surface.s7_ceremony_bridge import seed_soul_proposal_dialog

        deps = _fake_bridge_deps(
            pending={
                9: {
                    "proposal_type": "section_replace",
                    "target_section": "Values",
                    "proposed_new_body": "body",
                    "insight": "because",
                    "status": "pending",
                }
            }
        )

        seed_soul_proposal_dialog(prop_id=9, deps=deps)

        card = deps.card_store.last_created
        self.assertEqual(card.action, "edit_soul_section")
        self.assertEqual(card.params["target_name"], "Values")
        self.assertEqual(card.params["new_body"], "body")
        self.assertEqual(card.params["rationale"], "because")
        self.assertNotIn("target", card.params)

    def test_non_pending_proposal_does_not_seed(self):
        from skills.surface.s7_ceremony_bridge import seed_soul_proposal_dialog

        deps = _fake_bridge_deps(
            pending={7: {"proposal_type": "append", "insight": "x", "status": "rejected"}}
        )

        self.assertIsNone(seed_soul_proposal_dialog(prop_id=7, deps=deps))
        self.assertEqual(deps.card_store.cards, [])
