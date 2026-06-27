import unittest
import sqlite3
import tempfile
from pathlib import Path

from core.cognition.salience_ledger import (
    SalienceLedger,
    make_pulse_id,
    new_run_id,
)


class PulseIdentityTest(unittest.TestCase):
    def test_namespacing_two_runs_cannot_collide(self):
        a = new_run_id(now_ms=1000, pid=100)
        b = new_run_id(now_ms=2000, pid=200)

        self.assertNotEqual(a, b)
        ids_a = {make_pulse_id(a, s) for s in range(1, 51)}
        ids_b = {make_pulse_id(b, s) for s in range(1, 51)}

        self.assertEqual(len(ids_a), 50)
        self.assertEqual(ids_a & ids_b, set())

    def test_same_second_different_pid_is_distinct(self):
        self.assertNotEqual(
            new_run_id(now_ms=1000, pid=100),
            new_run_id(now_ms=1000, pid=200),
        )

    def test_within_run_stable_prefix_monotonic_seq(self):
        run = new_run_id(now_ms=1234, pid=42)

        self.assertEqual(make_pulse_id(run, 1), f"{run}.seq1")
        self.assertEqual(make_pulse_id(run, 7), f"{run}.seq7")
        self.assertTrue(make_pulse_id(run, 1).startswith(run))
        self.assertTrue(make_pulse_id(run, 2).startswith(run))

    def test_run_id_shape(self):
        self.assertEqual(new_run_id(now_ms=1000, pid=100), "r1000_100")

    def test_proposal_hash_binds_full_pulse_id(self):
        from core.cognition.salience_ledger import make_proposal_hash

        run_a = new_run_id(now_ms=1000, pid=100)
        run_b = new_run_id(now_ms=2000, pid=200)
        fields = {
            "strategy": "changed_since_last",
            "arm": "proposed",
            "fact_key": "f",
            "change_kind": "changed",
        }

        h_a = make_proposal_hash(pulse_id=make_pulse_id(run_a, 1), **fields)
        h_b = make_proposal_hash(pulse_id=make_pulse_id(run_b, 1), **fields)

        self.assertNotEqual(h_a, h_b)
        self.assertEqual(
            h_a,
            make_proposal_hash(pulse_id=make_pulse_id(run_a, 1), **fields),
        )
        self.assertNotEqual(h_a, make_proposal_hash(pulse_id="seq1", **fields))


class PulseLedgerNoCollisionTest(unittest.TestCase):
    def _seed(self, ledger: SalienceLedger, pulse_id: str) -> None:
        ledger.record(
            pulse_id=pulse_id,
            strategy="changed_since_last",
            arm="proposed",
            fact_key="f",
            change_kind="changed",
            proposal_hash="h",
            outcome={
                "thought_formed": False,
                "non_duplicate_stored": False,
                "repetition_signal": "not_applicable",
                "unmoved": True,
            },
        )

    def test_two_runs_write_distinct_pulse_ids(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = SalienceLedger(Path(d) / "s.db")
            run_a = new_run_id(now_ms=1000, pid=100)
            run_b = new_run_id(now_ms=2000, pid=200)

            for seq in range(1, 6):
                self._seed(ledger, make_pulse_id(run_a, seq))
            for seq in range(1, 6):
                self._seed(ledger, make_pulse_id(run_b, seq))

            conn = sqlite3.connect(Path(d) / "s.db")
            try:
                distinct = conn.execute(
                    "SELECT COUNT(DISTINCT pulse_id) FROM salience_ledger"
                ).fetchone()[0]
                total = conn.execute(
                    "SELECT COUNT(*) FROM salience_ledger"
                ).fetchone()[0]
            finally:
                conn.close()

            self.assertEqual(total, 10)
            self.assertEqual(distinct, 10)

    def test_gate_report_handles_legacy_and_new_rows(self):
        from core.cognition.salience_gate import gate_report

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.db"
            ledger = SalienceLedger(path)

            self._seed(ledger, "seq1")
            self._seed(ledger, make_pulse_id(new_run_id(now_ms=1000, pid=100), 1))

            report = gate_report(ledger_path=path)

            self.assertIsInstance(report, dict)


if __name__ == "__main__":
    unittest.main()
