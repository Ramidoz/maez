from __future__ import annotations

import pathlib
import sqlite3
import tempfile
import unittest
from unittest import mock

from core.cognition.salience_ledger import (
    LEDGER_VERSION,
    SalienceLedger,
    WITHHOLD_EVERY,
    assign_arm,
    derive_outcome,
    salience_ledger_db_path,
)


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
        self.assertEqual(out["repetition_signal"], "not_applicable")
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
            "output_chars": 9000,
            "owner_replied": True,
            "open_loop_resolved": True,
            "fixation_score": 99,
            "contradiction_receipt": True,
        }

        out = derive_outcome([poisoned, poisoned])

        self.assertEqual(
            out,
            {
                "thought_formed": False,
                "non_duplicate_stored": False,
                "repetition_signal": "not_applicable",
                "unmoved": True,
            },
        )


class AssignArmTest(unittest.TestCase):
    def test_no_change_is_control_none_with_sentinel(self) -> None:
        arm, rows = assign_arm([], pulse_signature="anything")

        self.assertEqual(WITHHOLD_EVERY, 5)
        self.assertEqual(arm, "control_none")
        self.assertEqual(
            list(rows),
            [{"fact_key": "none", "change_kind": "none"}],
        )

    def test_change_preserves_fact_identity(self) -> None:
        proposals = [{"fact_key": "time_facts", "change_kind": "changed"}]

        arm, rows = assign_arm(proposals, pulse_signature="sig-not-withheld")

        self.assertIn(arm, ("proposed", "control_withheld"))
        self.assertEqual(list(rows), proposals)

    def test_withheld_is_deterministic_and_keeps_fact_identity(self) -> None:
        proposals = [{"fact_key": "body_state", "change_kind": "changed"}]

        first_arm, first_rows = assign_arm(proposals, pulse_signature="sig-X")
        second_arm, second_rows = assign_arm(proposals, pulse_signature="sig-X")

        self.assertEqual(first_arm, second_arm)
        self.assertEqual(list(first_rows), list(second_rows))
        if first_arm == "control_withheld":
            self.assertEqual(first_rows[0]["fact_key"], "body_state")

    def test_no_randomness_imported(self) -> None:
        import inspect
        import core.cognition.salience_ledger as module

        source = inspect.getsource(module)
        self.assertNotIn("import random", source)
        self.assertNotIn("Math.random", source)


class SalienceLedgerStoreTest(unittest.TestCase):
    def _ledger(self) -> SalienceLedger:
        return SalienceLedger(pathlib.Path(tempfile.mkdtemp()) / "ledger.db")

    def test_row_binds_to_concrete_proposal(self) -> None:
        ledger = self._ledger()
        outcome = derive_outcome(
            [{"note_chars": 80, "stored": True, "skip_reason": "none"}]
        )

        ledger.record(
            pulse_id="p1",
            strategy="changed_since_last",
            arm="proposed",
            fact_key="time_facts",
            change_kind="changed",
            proposal_hash="abc123",
            outcome=outcome,
        )

        rows = ledger.recent(limit=5)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(
            (row["pulse_id"], row["strategy"], row["fact_key"], row["change_kind"]),
            ("p1", "changed_since_last", "time_facts", "changed"),
        )
        self.assertEqual(row["proposal_hash"], "abc123")
        self.assertTrue(row["non_duplicate_stored"])

    def test_fresh_schema_has_arm_column(self) -> None:
        ledger = self._ledger()

        self.assertIn("arm", ledger.column_names())

    def test_record_persists_arm(self) -> None:
        ledger = self._ledger()
        outcome = derive_outcome(
            [{"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok"}]
        )

        ledger.record(
            pulse_id="p1",
            strategy="changed_since_last",
            arm="control_none",
            fact_key="none",
            change_kind="none",
            proposal_hash="abc",
            outcome=outcome,
        )

        self.assertEqual(ledger.recent(1)[0]["arm"], "control_none")

    def test_existing_rows_migrate_to_proposed(self) -> None:
        path = pathlib.Path(tempfile.mkdtemp()) / "old.db"
        conn = sqlite3.connect(path)
        try:
            conn.execute(
                """CREATE TABLE salience_ledger (
                    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pulse_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    change_kind TEXT NOT NULL,
                    proposal_hash TEXT NOT NULL,
                    thought_formed INTEGER NOT NULL,
                    non_duplicate_stored INTEGER NOT NULL,
                    repetition_signal TEXT NOT NULL,
                    unmoved INTEGER NOT NULL,
                    schema_version TEXT NOT NULL
                )"""
            )
            conn.execute(
                """INSERT INTO salience_ledger (
                    pulse_id, strategy, fact_key, change_kind, proposal_hash,
                    thought_formed, non_duplicate_stored, repetition_signal,
                    unmoved, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "seq2",
                    "changed_since_last",
                    "time_facts",
                    "changed",
                    "h",
                    0,
                    0,
                    "not_applicable",
                    1,
                    "salience_ledger.v0",
                ),
            )
            conn.commit()
        finally:
            conn.close()

        ledger = SalienceLedger(path)
        row = ledger.recent(1)[0]

        self.assertEqual(row["arm"], "proposed")

    def test_store_is_content_light(self) -> None:
        ledger = self._ledger()
        outcome = derive_outcome(
            [
                {
                    "note_chars": 0,
                    "stored": False,
                    "skip_reason": "heartbeat_ok_or_rejected",
                }
            ]
        )

        ledger.record(
            pulse_id="p2",
            strategy="changed_since_last",
            arm="proposed",
            fact_key="recent_private_thoughts",
            change_kind="appeared",
            proposal_hash="deadbeef",
            outcome=outcome,
        )

        cols = ledger.column_names()
        for forbidden in (
            "content",
            "thought",
            "prompt",
            "raw_text",
            "fact_value",
            "owner_reaction",
            "open_loop_resolution",
            "fixation_score",
            "contradiction_receipt",
        ):
            self.assertNotIn(forbidden, cols)

    def test_db_path_helper_honors_env_without_initializing_store(self) -> None:
        path = pathlib.Path(tempfile.mkdtemp()) / "custom-salience.db"

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_LEDGER_PATH": str(path)}, clear=False
        ):
            self.assertEqual(salience_ledger_db_path(), path)

        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
