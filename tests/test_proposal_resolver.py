from __future__ import annotations

import unittest

from core.dispatcher.proposal_resolver import (
    detect_proposal_intent,
    resolve_proposal_target,
)


class ProposalResolverTests(unittest.TestCase):
    def test_detects_legacy_approval_reject_and_show_shapes(self):
        self.assertEqual(detect_proposal_intent("yes"), ("approve", None))
        self.assertEqual(detect_proposal_intent("proceed with it"), ("approve", None))
        self.assertEqual(detect_proposal_intent("approve #42"), ("approve", 42))
        self.assertEqual(detect_proposal_intent("no to #7"), ("reject", 7))
        self.assertEqual(detect_proposal_intent("show me #5"), ("show", 5))

    def test_ignores_long_or_non_intent_text(self):
        self.assertEqual(detect_proposal_intent("yes, and another thing"), (None, None))
        self.assertEqual(detect_proposal_intent("yes " + "x" * 100), (None, None))

    def test_bare_yes_without_context_or_last_shown_does_not_bind(self):
        target = resolve_proposal_target(
            action="approve",
            explicit_id=None,
            pending_ids=[1],
            last_shown=None,
            source="evolution",
            text="yes",
        )
        self.assertIsNone(target)

    def test_bare_yes_binds_to_recent_last_shown(self):
        target = resolve_proposal_target(
            action="approve",
            explicit_id=None,
            pending_ids=[9],
            last_shown={"id": 9, "source": "evolution", "shown_at": 100.0},
            source="evolution",
            text="yes",
            now=120.0,
        )
        self.assertEqual(target, 9)

    def test_explicit_id_wins(self):
        target = resolve_proposal_target(
            action="reject",
            explicit_id=4,
            pending_ids=[1, 4],
            last_shown={"id": 1, "source": "evolution", "shown_at": 100.0},
            source="evolution",
            text="reject #4",
            now=120.0,
        )
        self.assertEqual(target, 4)

    def test_context_word_allows_single_pending_bind(self):
        target = resolve_proposal_target(
            action="approve",
            explicit_id=None,
            pending_ids=[3],
            last_shown=None,
            source="evolution",
            text="approve the proposal",
        )
        self.assertEqual(target, 3)
