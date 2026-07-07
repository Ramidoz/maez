import unittest
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.governance.operator_user_boundary import build_birth_readiness_projection


def _cond(key, state, detail="d"):
    return {
        "key": key,
        "title": key.replace("_", " "),
        "state": state,
        "detail": detail,
        "checked_at": "2026-07-05T00:00:00Z",
    }


class BirthReadinessProjectionTests(unittest.TestCase):
    def test_all_green_overall_green(self):
        p = build_birth_readiness_projection(
            generated_at="2026-07-05T00:00:00Z",
            conditions=[_cond("ledger_init", "green"), _cond("flag_state", "green")],
        )
        self.assertEqual(p["route"], "/operator/birth_readiness")
        self.assertEqual(p["overall"], "green")
        self.assertEqual(len(p["conditions"]), 2)

    def test_any_red_overall_red(self):
        p = build_birth_readiness_projection(
            generated_at="2026-07-05T00:00:00Z",
            conditions=[_cond("ledger_init", "green"), _cond("dream_witness", "red")],
        )
        self.assertEqual(p["overall"], "red")

    def test_invalid_state_refused(self):
        with self.assertRaises(ValueError):
            build_birth_readiness_projection(
                generated_at="2026-07-05T00:00:00Z",
                conditions=[_cond("x", "yellow")],
            )

    def test_content_light_no_free_fields(self):
        with self.assertRaises(ValueError):
            build_birth_readiness_projection(
                generated_at="2026-07-05T00:00:00Z",
                conditions=[{**_cond("x", "green"), "thought_body": "leak"}],
            )


class BirthReadinessRepoGreenReceiptTests(unittest.TestCase):
    def test_receipt_missing_is_red(self):
        with tempfile.TemporaryDirectory() as td:
            receipt_path = Path(td) / "repo_green_receipt.json"
            projection = self._projection(receipt_path=receipt_path)

        condition = self._condition(projection, "repo_green")
        self.assertEqual(condition["state"], "red")
        self.assertIn("receipt stale/missing", condition["detail"])

    def test_receipt_wrong_commit_is_red(self):
        with tempfile.TemporaryDirectory() as td:
            receipt_path = Path(td) / "repo_green_receipt.json"
            self._write_receipt(receipt_path, commit="not-head", finished_at=datetime.now(timezone.utc))

            projection = self._projection(receipt_path=receipt_path, current_head="head-sha")

        condition = self._condition(projection, "repo_green")
        self.assertEqual(condition["state"], "red")
        self.assertIn("receipt stale/missing", condition["detail"])

    def test_receipt_stale_is_red(self):
        with tempfile.TemporaryDirectory() as td:
            receipt_path = Path(td) / "repo_green_receipt.json"
            finished_at = datetime.now(timezone.utc) - timedelta(hours=25)
            self._write_receipt(receipt_path, commit="head-sha", finished_at=finished_at)

            projection = self._projection(receipt_path=receipt_path, current_head="head-sha")

        condition = self._condition(projection, "repo_green")
        self.assertEqual(condition["state"], "red")
        self.assertIn("receipt stale/missing", condition["detail"])

    def test_receipt_fresh_head_under_floor_is_green(self):
        with tempfile.TemporaryDirectory() as td:
            receipt_path = Path(td) / "repo_green_receipt.json"
            self._write_receipt(
                receipt_path,
                commit="head-sha",
                finished_at=datetime.now(timezone.utc),
                failures=3,
                floor_note="known memory_integrity drifts",
            )

            projection = self._projection(receipt_path=receipt_path, current_head="head-sha")

        condition = self._condition(projection, "repo_green")
        self.assertEqual(condition["state"], "green")
        self.assertIn("known memory_integrity drifts", condition["detail"])

    def test_receipt_dirty_worktree_is_red(self):
        with tempfile.TemporaryDirectory() as td:
            receipt_path = Path(td) / "repo_green_receipt.json"
            self._write_receipt(
                receipt_path,
                commit="head-sha",
                finished_at=datetime.now(timezone.utc),
                worktree_clean=False,
            )

            projection = self._projection(receipt_path=receipt_path, current_head="head-sha")

        condition = self._condition(projection, "repo_green")
        self.assertEqual(condition["state"], "red")
        self.assertIn("receipt stale/missing", condition["detail"])

    @staticmethod
    def _condition(projection, key):
        return {condition["key"]: condition for condition in projection["conditions"]}[key]

    @staticmethod
    def _write_receipt(
        path: Path,
        *,
        commit: str,
        finished_at: datetime,
        failures: int = 0,
        errors: int = 0,
        ran: int = 8000,
        floor_note: str = "known memory_integrity drifts",
        worktree_clean: bool = True,
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "commit": commit,
                    "started_at": finished_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "ran": ran,
                    "failures": failures,
                    "errors": errors,
                    "floor_note": floor_note,
                    "worktree_clean": worktree_clean,
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _projection(*, receipt_path: Path, current_head: str = "head-sha"):
        from daemon import maez_daemon
        from daemon.maez_daemon import MaezDaemon

        class ReceiptStore:
            def count(self):
                return 0

        daemon = MaezDaemon.__new__(MaezDaemon)
        daemon.boot_time = "9999-01-01T00:00:00+00:00"
        with (
            patch.object(maez_daemon, "REPO_GREEN_RECEIPT_PATH", receipt_path),
            patch.object(maez_daemon, "_current_git_head", return_value=current_head),
            patch("core.infra.unseal_receipts.UnsealReceipts", return_value=ReceiptStore()),
        ):
            return daemon._birth_readiness()


if __name__ == "__main__":
    unittest.main()
