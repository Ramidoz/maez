import importlib.util
import types
import unittest
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "repo_green_receipt.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("repo_green_receipt", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeCase:
    def __init__(self, label: str):
        self.label = label

    def __str__(self) -> str:
        return self.label


class RepoGreenReceiptFloorTests(unittest.TestCase):
    def test_known_full_discovery_floor_has_no_unexpected_reds(self):
        rg = _load_module()
        result = types.SimpleNamespace(
            testsRun=8349,
            failures=[(_FakeCase(rg.KNOWN_MEMORY_INTEGRITY_DRIFT_CASES[0]), "tb")],
            errors=[(_FakeCase(rg.KNOWN_ASSET_CONFOUND_CASES[0]), "tb")],
        )

        receipt = rg._build_receipt(
            result,
            commit="head",
            started_at="2026-07-07T00:00:00+00:00",
            finished_at="2026-07-07T00:01:00+00:00",
            worktree_clean=True,
        )

        self.assertEqual(receipt["failures"], 1)
        self.assertEqual(receipt["errors"], 1)
        self.assertEqual(receipt["unexpected_failures"], 0)
        self.assertEqual(receipt["unexpected_errors"], 0)
        self.assertEqual(receipt["known_floor_count"], 2)
        self.assertEqual(receipt["floor_buckets"]["memory_integrity_drift"], 1)
        self.assertEqual(receipt["floor_buckets"]["asset_confounded_full_discovery"], 1)
        self.assertIn("known full-discovery reds", receipt["floor_note"])
        self.assertIn("unexpected=0", receipt["floor_note"])

    def test_unexpected_failure_is_not_absorbed_into_floor(self):
        rg = _load_module()
        result = types.SimpleNamespace(
            testsRun=1,
            failures=[(_FakeCase("test_new_red (test_new_module.NewTest.test_new_red)"), "tb")],
            errors=[],
        )

        receipt = rg._build_receipt(
            result,
            commit="head",
            started_at="2026-07-07T00:00:00+00:00",
            finished_at="2026-07-07T00:01:00+00:00",
            worktree_clean=True,
        )

        self.assertEqual(receipt["unexpected_failures"], 1)
        self.assertEqual(receipt["unexpected_errors"], 0)
        self.assertEqual(receipt["known_floor_count"], 0)
        self.assertEqual(
            receipt["unexpected_reds"],
            ["FAIL: test_new_red (test_new_module.NewTest.test_new_red)"],
        )
        self.assertIn("unexpected=1", receipt["floor_note"])


if __name__ == "__main__":
    unittest.main()
