# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.pending_cards — specifically the state-hash guard
in approve(). Added 2026-04-22 after observing four identical
"Card expired — was empty, now ..." messages in Telegram from cards
created without state_fields (wondering-cycle probes). The fix
treats state_hash='empty' as state-exempt rather than invalidating."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class StateGuardForEmptySentinel(unittest.TestCase):
    """A card created without `state_fields` uses the CardRecord
    dataclass default state_hash='empty'. Approving such a card with
    a real `current_state_fields` must NOT expire it — the creator
    declined to bind to state, so state drift cannot invalidate."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["MAEZ_PENDING_CARDS_DB"] = str(
            Path(self._tmp.name) / "pc.db",
        )
        from core.pending_cards import PendingCardStore
        self.store = PendingCardStore(
            db_path=Path(self._tmp.name) / "pc.db",
        )

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("MAEZ_PENDING_CARDS_DB", None)

    def test_state_unbound_card_approves_despite_current_state(self):
        """Card created with no state_fields → state_hash='empty'.
        Approve with non-empty current_state_fields → APPROVED, not
        EXPIRED. This is the fix for the 2026-04-22 four-noise bug."""
        card = self.store.create_card(
            action="run_shell",
            params={"cmd": "ls /tmp"},
            reason="smoke test — no state bound",
            plain_english="run a harmless ls",
        )
        # Sanity: confirm the sentinel is set as expected
        self.assertEqual(card.state_hash, "empty")

        # Approve with a non-empty current state
        result = self.store.approve(
            card.request_id,
            user_id="test",
            via="cockpit",
            current_state_fields={"cwd": "/tmp", "mode": "interactive"},
        )

        self.assertEqual(result.status, "approved",
                         f"state-unbound card should APPROVE, got {result.status} "
                         f"(resolution_notes={result.resolution_notes!r})")
        # Resolution notes should NOT claim a state-hash change
        self.assertNotIn(
            "state hash changed", (result.resolution_notes or ""),
        )

    def test_state_bound_card_still_expires_on_real_change(self):
        """Regression guard: the fix above must NOT disable the guard
        for cards that legitimately bound to state at creation."""
        card = self.store.create_card(
            action="run_shell",
            params={"cmd": "ls /tmp"},
            reason="state-bound test",
            plain_english="run ls",
            state_fields={"cwd": "/original"},
        )
        # This card's state_hash SHOULD be computed, not "empty"
        self.assertNotEqual(card.state_hash, "empty")
        self.assertTrue(card.state_hash,
                         "state-bound card must get a real hash")

        # Approve with a DIFFERENT current state
        result = self.store.approve(
            card.request_id,
            user_id="test",
            via="cockpit",
            current_state_fields={"cwd": "/somewhere-else"},
        )
        # Should still expire (the guard still works for bound cards)
        self.assertEqual(result.status, "expired")
        self.assertIn("state hash changed",
                       result.resolution_notes or "")

    def test_state_bound_card_approves_when_state_matches(self):
        card = self.store.create_card(
            action="run_shell", params={"cmd": "ls /tmp"},
            reason="state-bound, matches", plain_english="run ls",
            state_fields={"cwd": "/home/rohit"},
        )
        result = self.store.approve(
            card.request_id, user_id="test", via="cockpit",
            current_state_fields={"cwd": "/home/rohit"},
        )
        self.assertEqual(result.status, "approved")


if __name__ == "__main__":
    unittest.main()
