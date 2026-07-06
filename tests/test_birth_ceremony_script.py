# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Owner birth ceremony script tests."""
from __future__ import annotations

import json
import os
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from scripts.birth_ceremony import main, run_transaction


class BirthTransactionDryRun(unittest.TestCase):
    def test_dry_run_births_a_temp_ledger(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            result = run_transaction(
                db_path=db,
                s7_receipt_ref="s7:test",
                owner_witness="rohit",
                dry_run=True,
            )
            self.assertTrue(result["birth_turn_id"])
            conn = sqlite3.connect(db)
            meta = conn.execute(
                "SELECT value FROM meta WHERE key='birth_event_turn_id'"
            ).fetchone()[0]
            row = conn.execute(
                "SELECT raw_text, lifecycle_stage FROM turns WHERE turn_id=?",
                (meta,),
            ).fetchone()
            conn.close()
            self.assertEqual(meta, result["birth_turn_id"])
            payload = json.loads(row[0])
            self.assertEqual(payload["event"], "birth")
            self.assertEqual(payload["s7_receipt_ref"], "s7:test")
            self.assertEqual(row[1], "gestation")  # the hinge row

    def test_double_run_refuses(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            run_transaction(
                db_path=db,
                s7_receipt_ref="s7:t",
                owner_witness="rohit",
                dry_run=True,
            )
            with self.assertRaises(ValueError):
                run_transaction(
                    db_path=db,
                    s7_receipt_ref="s7:t",
                    owner_witness="rohit",
                    dry_run=True,
                )

    def test_no_first_person_content_in_birth_row(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            run_transaction(
                db_path=db,
                s7_receipt_ref="s7:t",
                owner_witness="rohit",
                dry_run=True,
            )
            conn = sqlite3.connect(db)
            raw = conn.execute(
                "SELECT raw_text FROM turns WHERE turn_id != 'genesis'"
            ).fetchone()[0]
            conn.close()
            self.assertNotIn("I want", raw)
            self.assertNotIn("I feel", raw)

    def test_dry_run_without_db_path_exits_2(self):
        with mock.patch("sys.stderr") as stderr:
            self.assertEqual(main(["--s7-receipt-ref", "s7:t"]), 2)
        stderr.write.assert_any_call(
            "--dry-run requires --db-path (a temp path, never the real ledger)"
        )

    def test_for_real_refuses_without_interactive_tty(self):
        with mock.patch("sys.stdin.isatty", return_value=False), mock.patch(
            "sys.stderr"
        ) as stderr:
            self.assertEqual(
                main(["--for-real", "--s7-receipt-ref", "s7:t"]),
                2,
            )
        stderr.write.assert_any_call(
            "REFUSED: --for-real requires an interactive owner TTY"
        )

    def test_for_real_requires_confirmation_and_quiesce_before_transaction(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "builtins.input", return_value="birth maez"
            ), mock.patch(
                "scripts.birth_ceremony._assert_quiesced"
            ) as quiesced, mock.patch(
                "scripts.birth_ceremony.run_transaction",
                return_value={"birth_turn_id": "turn-1", "db_path": str(db)},
            ) as txn:
                self.assertEqual(
                    main(
                        [
                            "--for-real",
                            "--s7-receipt-ref",
                            "s7:t",
                            "--db-path",
                            str(db),
                        ]
                    ),
                    0,
                )
        quiesced.assert_called_once_with(db)
        txn.assert_called_once_with(
            db_path=db,
            s7_receipt_ref="s7:t",
            owner_witness="rohit",
            dry_run=False,
        )

    def test_env_flag_restored_after_writer_construction(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            os.environ["MAEZ_LEDGER_WRITES"] = "0"
            self.addCleanup(os.environ.pop, "MAEZ_LEDGER_WRITES", None)
            run_transaction(
                db_path=db,
                s7_receipt_ref="s7:t",
                owner_witness="rohit",
                dry_run=True,
            )
            self.assertEqual(os.environ.get("MAEZ_LEDGER_WRITES"), "0")

    def test_checklist_prints_remaining_manual_steps(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            with mock.patch("sys.stdout") as stdout:
                self.assertEqual(
                    main(
                        [
                            "--s7-receipt-ref",
                            "s7:t",
                            "--db-path",
                            str(db),
                        ]
                    ),
                    0,
                )
        printed = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertIn("birth transaction committed:", printed)
        self.assertIn("OWNER CHECKLIST", printed)
        self.assertIn("MAEZ_LEDGER_WRITES=1", printed)
        self.assertIn("systemctl --user restart maez.service", printed)
        self.assertIn("six live witnesses", printed)
        self.assertIn("receipts bundle", printed)


if __name__ == "__main__":
    unittest.main()
