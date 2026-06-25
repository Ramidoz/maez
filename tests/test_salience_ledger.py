from __future__ import annotations

import unittest

from core.cognition.salience_ledger import LEDGER_VERSION, derive_outcome


def _hb(
    *,
    note_chars: int = 0,
    stored: bool = False,
    skip_reason: str = "heartbeat_ok_or_rejected",
) -> dict:
    return {"note_chars": note_chars, "stored": stored, "skip_reason": skip_reason}


class DeriveOutcomeTest(unittest.TestCase):
    def test_unmoved_is_neutral_across_window(self) -> None:
        out = derive_outcome([_hb(), _hb()])

        self.assertEqual(LEDGER_VERSION, "salience_ledger.v0")
        self.assertTrue(out["unmoved"])
        self.assertFalse(out["thought_formed"])
        self.assertFalse(out["non_duplicate_stored"])
        self.assertEqual(out["repetition_signal"], "not_applicable")

    def test_non_duplicate_stored(self) -> None:
        out = derive_outcome(
            [_hb(), _hb(note_chars=80, stored=True, skip_reason="none")]
        )

        self.assertTrue(out["thought_formed"])
        self.assertTrue(out["non_duplicate_stored"])
        self.assertFalse(out["unmoved"])

    def test_candidate_formed_but_duplicate_rejected(self) -> None:
        out = derive_outcome(
            [
                _hb(note_chars=80, stored=False, skip_reason="duplicate_recent_output"),
                _hb(),
            ]
        )

        self.assertTrue(out["thought_formed"])
        self.assertFalse(out["non_duplicate_stored"])
        self.assertEqual(out["repetition_signal"], "duplicate")
        self.assertFalse(out["unmoved"])

    def test_window_takes_best_across_N_and_N1(self) -> None:
        out = derive_outcome(
            [_hb(), _hb(note_chars=50, stored=True, skip_reason="none")]
        )

        self.assertTrue(out["non_duplicate_stored"])

    def test_derive_outcome_only_consumes_idle_loop_fields(self) -> None:
        poisoned = {
            "note_chars": 0,
            "stored": False,
            "skip_reason": "heartbeat_ok_or_rejected",
            "owner_replied": True,
            "open_loop_resolved": True,
            "fixation_score": 99,
            "contradiction_receipt": True,
        }

        out = derive_outcome([poisoned, poisoned])

        self.assertTrue(out["unmoved"])


if __name__ == "__main__":
    unittest.main()
