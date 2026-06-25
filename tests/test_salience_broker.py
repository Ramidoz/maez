from __future__ import annotations

import unittest

from core.cognition.salience_broker import (
    STRATEGY,
    WATCHED_KEYS,
    broker_receipt,
    fact_signatures,
    propose_changes,
)


class SalienceBrokerTest(unittest.TestCase):
    def _facts(self, **over):
        base = {
            "time_facts": {"owner_contact_gap_s": 30},
            "body_state": {"watchdog": "ok"},
            "open_loops": {"open_loop_count": 0},
            "recent_private_thoughts": (),
        }
        base.update(over)
        return base

    def test_cold_start_proposes_nothing(self) -> None:
        current = fact_signatures(self._facts())

        self.assertEqual(propose_changes(current, None), [])

    def test_changed_fact_is_proposed_as_observation(self) -> None:
        baseline = fact_signatures(self._facts(time_facts={"owner_contact_gap_s": 30}))
        current = fact_signatures(self._facts(time_facts={"owner_contact_gap_s": 999}))

        proposals = propose_changes(current, baseline)

        self.assertEqual(
            [(proposal.fact_key, proposal.change_kind) for proposal in proposals],
            [("time_facts", "changed")],
        )
        self.assertTrue(all(proposal.strategy == STRATEGY for proposal in proposals))

    def test_thought_appearing_and_clearing(self) -> None:
        empty = fact_signatures(self._facts(recent_private_thoughts=()))
        present = fact_signatures(self._facts(recent_private_thoughts=("a note",)))

        self.assertEqual(
            [(proposal.fact_key, proposal.change_kind) for proposal in propose_changes(present, empty)],
            [("recent_private_thoughts", "appeared")],
        )
        self.assertEqual(
            [(proposal.fact_key, proposal.change_kind) for proposal in propose_changes(empty, present)],
            [("recent_private_thoughts", "cleared")],
        )

    def test_unchanged_window_proposes_nothing(self) -> None:
        signatures = fact_signatures(self._facts())

        self.assertEqual(propose_changes(signatures, signatures), [])

    def test_signatures_are_content_light(self) -> None:
        signatures = fact_signatures(self._facts(recent_private_thoughts=("SECRET THOUGHT",)))

        self.assertNotIn("SECRET", "".join(signatures.values()))

    def test_receipt_is_content_light_and_makes_no_importance_claim(self) -> None:
        baseline = fact_signatures(self._facts())
        current = fact_signatures(self._facts(body_state={"watchdog": "stale"}))

        receipt = broker_receipt(propose_changes(current, baseline), cold_start=False)
        blob = str(receipt).lower()

        for forbidden in (
            "importance",
            "important",
            "notable",
            "priority",
            "score",
            "secret",
            "should",
            "unusual",
            "urgent",
            "deserves",
            "matters",
        ):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(receipt["strategy"], STRATEGY)
        self.assertEqual(receipt["watched_keys"], list(WATCHED_KEYS))
        self.assertEqual(
            receipt["proposals"],
            [{"fact_key": "body_state", "change_kind": "changed"}],
        )
