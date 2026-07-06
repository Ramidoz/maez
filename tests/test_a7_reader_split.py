import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.infra import private_thoughts_unseal
from core.infra.private_thoughts import (
    AllowedFlow,
    ConsentTier,
    PrivateThoughts,
    ProducerId,
    RetentionRule,
    SignalKind,
)
from core.infra.unseal_receipts import UnsealReceipts


def _store_with_one_thought(td: str):
    store = PrivateThoughts(db_path=str(Path(td) / "pt.db"))
    tid = store.record_thought(content="the secret garden", provenance="explicit_api")
    return store, tid


class DefaultReadersAreContentLight(unittest.TestCase):
    def test_get_thought_returns_hash_not_body(self):
        with TemporaryDirectory() as td:
            store, tid = _store_with_one_thought(td)
            row = store.get_thought(tid)
            self.assertNotIn("content", row)
            self.assertEqual(
                row["content_sha256"],
                hashlib.sha256(b"the secret garden").hexdigest(),
            )
            self.assertEqual(row["content_chars"], len("the secret garden"))

    def test_recent_returns_hash_not_body(self):
        with TemporaryDirectory() as td:
            store, _ = _store_with_one_thought(td)
            rows = store.recent(limit=5)
            self.assertTrue(rows)
            self.assertNotIn("content", rows[0])
            self.assertIn("content_sha256", rows[0])

    def test_maez_lane_unchanged(self):
        with TemporaryDirectory() as td:
            store = PrivateThoughts(db_path=str(Path(td) / "pt.db"))
            store.record_signal(
                content="my own thought",
                source="heartbeat:v1",
                subject="maez_internal_state",
                signal_kind=SignalKind.SELF_WONDERING,
                producer_id=ProducerId.SELF_WONDERING,
                consent_tier=ConsentTier.OWNER_PRIVATE,
                retention=RetentionRule.UNTIL_REVIEWED,
                allowed_flows=(AllowedFlow.PRIVATE_READER,),
                context_extra={},
            )
            rows = store.recent_by_source("heartbeat:v1", limit=1, phase=None)
            self.assertEqual(rows[0]["content"], "my own thought")


class UnsealPathWritesReceiptFirst(unittest.TestCase):
    def test_content_served_and_receipt_recorded(self):
        with TemporaryDirectory() as td:
            store, tid = _store_with_one_thought(td)
            receipts = UnsealReceipts(db_path=Path(td) / "ur.db")
            rows = private_thoughts_unseal.read_content(
                store,
                thought_ids=[tid],
                actor="rohit",
                s7_receipt_ref="s7:abc",
                reason="diagnostic",
                receipts=receipts,
            )
            self.assertEqual(rows[0]["content"], "the secret garden")
            self.assertEqual(receipts.count(), 1)
            self.assertEqual(receipts.recent(1)[0]["scope_kind"], "thought_id")

    def test_failed_receipt_means_no_content(self):
        with TemporaryDirectory() as td:
            store, tid = _store_with_one_thought(td)

            class BrokenReceipts:
                def record_unseal(self, **kw):
                    raise RuntimeError("disk full")

            with self.assertRaises(RuntimeError):
                private_thoughts_unseal.read_content(
                    store,
                    thought_ids=[tid],
                    actor="rohit",
                    s7_receipt_ref="s7:abc",
                    reason="diagnostic",
                    receipts=BrokenReceipts(),
                )


class UnsealImportGuard(unittest.TestCase):
    ALLOWLIST = {
        "core/infra/private_thoughts_unseal.py",
        "scripts/verify_self_claim.py",
        "tests/test_a7_reader_split.py",
    }

    def test_no_default_runtime_import_of_unseal(self):
        import subprocess

        repo = Path(__file__).resolve().parents[1]
        out = subprocess.run(
            [
                "grep",
                "-rl",
                "--include=*.py",
                "private_thoughts_unseal",
                "core",
                "scripts",
                "daemon",
                "memory",
                "web",
                "tests",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        hits = {line for line in out.stdout.splitlines() if line}
        self.assertLessEqual(
            hits,
            self.ALLOWLIST,
            f"unexpected unseal importers: {hits - self.ALLOWLIST}",
        )


if __name__ == "__main__":
    unittest.main()
