from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from core.consent.spine import ConsentIntent, ConsentSpineStore, OwnerUtterance


@dataclass(frozen=True)
class _Card:
    request_id: str
    action: str = "run_shell"
    proposed_action_summary: str = "proposed action"
    created_at: float = 1000.0


def _utterance(text: str, *, at: str = "2026-07-08T00:00:00Z", fresh: bool = True):
    return OwnerUtterance(
        surface_kind="telegram",
        surface_identity="111:222",
        text=text,
        fresh=fresh,
        reply_to_ref=None,
        at=at,
    )


class ConsentSpineStateMachineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "consent.sqlite3"

    def tearDown(self):
        self.tmp.cleanup()

    def test_approve_intent_surfaces_then_fresh_echo_moves_to_resolving(self):
        store = ConsentSpineStore(self.db_path, token_generator=lambda: "ABCD")
        card = _Card("card-1", action="backup_key")

        surfaced = store.handle_turn(
            binding_id="bind_owner",
            utterance=_utterance("approve the backup key"),
            intent=ConsentIntent(kind="approve", card_hint=None, confidence=0.91),
            open_cards=[card],
            now=1000.0,
        )

        self.assertEqual(surfaced.state, "CARD_SURFACED")
        self.assertEqual(surfaced.card_id, "card-1")
        self.assertEqual(surfaced.echo_token, "ABCD")

        resolving = store.handle_turn(
            binding_id="bind_owner",
            utterance=_utterance("approve ABCD"),
            intent=ConsentIntent(kind="approve", card_hint="ABCD", confidence=0.93),
            open_cards=[card],
            now=1010.0,
        )

        self.assertEqual(resolving.state, "RESOLVING")
        self.assertEqual(resolving.card_id, "card-1")
        self.assertEqual(resolving.decision, "approve")

    def test_standing_pre_consent_primes_then_lazy_surfaces_when_card_exists(self):
        store = ConsentSpineStore(self.db_path, token_generator=lambda: "PRME")

        primed = store.handle_turn(
            binding_id="bind_owner",
            utterance=_utterance("if a backup key card appears, approve it"),
            intent=ConsentIntent(kind="standing_pre_consent", card_hint="backup key", confidence=0.84),
            open_cards=[],
            now=2000.0,
        )
        self.assertEqual(primed.state, "PRIMED")

        surfaced = store.handle_turn(
            binding_id="bind_owner",
            utterance=_utterance("hey"),
            intent=ConsentIntent(kind="none", card_hint=None, confidence=0.0),
            open_cards=[_Card("card-2", action="backup_key")],
            now=2010.0,
        )
        self.assertEqual(surfaced.state, "CARD_SURFACED")
        self.assertEqual(surfaced.echo_token, "PRME")

    def test_expired_surfacing_never_resolves(self):
        store = ConsentSpineStore(self.db_path, token_generator=lambda: "OLD1")
        card = _Card("card-1")
        store.handle_turn(
            binding_id="bind_owner",
            utterance=_utterance("approve this"),
            intent=ConsentIntent(kind="approve", card_hint=None, confidence=0.9),
            open_cards=[card],
            now=3000.0,
        )

        expired = store.handle_turn(
            binding_id="bind_owner",
            utterance=_utterance("OLD1"),
            intent=ConsentIntent(kind="approve", card_hint="OLD1", confidence=0.9),
            open_cards=[card],
            now=3601.0,
        )

        self.assertEqual(expired.refusal_code, "echo_expired")
        self.assertNotEqual(expired.state, "RESOLVING")

    def test_expired_surfacing_returns_to_idle_for_later_resurface(self):
        tokens = iter(["OLD1", "NEW1"])
        store = ConsentSpineStore(self.db_path, token_generator=lambda: next(tokens))
        card = _Card("card-1")
        store.handle_turn(
            binding_id="bind_owner",
            utterance=_utterance("approve this"),
            intent=ConsentIntent(kind="approve", card_hint=None, confidence=0.9),
            open_cards=[card],
            now=3000.0,
        )

        resurfaced = store.handle_turn(
            binding_id="bind_owner",
            utterance=_utterance("approve this"),
            intent=ConsentIntent(kind="approve", card_hint=None, confidence=0.9),
            open_cards=[card],
            now=3601.0,
        )

        self.assertEqual(resurfaced.state, "CARD_SURFACED")
        self.assertEqual(resurfaced.echo_token, "NEW1")

    def test_ambiguity_with_multiple_open_cards_never_resolves(self):
        store = ConsentSpineStore(self.db_path, token_generator=lambda: "AMB1")

        result = store.handle_turn(
            binding_id="bind_owner",
            utterance=_utterance("approve it"),
            intent=ConsentIntent(kind="approve", card_hint=None, confidence=0.88),
            open_cards=[_Card("card-1"), _Card("card-2")],
            now=4000.0,
        )

        self.assertEqual(result.refusal_code, "echo_ambiguous")
        self.assertNotEqual(result.state, "RESOLVING")

    def test_token_collision_regenerates_inside_unique_active_index(self):
        tokens = iter(["DUP1", "DUP1", "UNIQ"])
        store = ConsentSpineStore(self.db_path, token_generator=lambda: next(tokens))

        first = store.surface_card(
            binding_id="bind_a",
            card_id="card-a",
            decision="approve",
            now=5000.0,
        )
        second = store.surface_card(
            binding_id="bind_b",
            card_id="card-b",
            decision="deny",
            now=5001.0,
        )

        self.assertEqual(first.echo_token, "DUP1")
        self.assertEqual(second.echo_token, "UNIQ")


if __name__ == "__main__":
    unittest.main()
