from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.recall_flip_eval import sandbox
from scripts.legacy_recall_eval import harness


class _SandboxTestCase(unittest.TestCase):
    """Fresh hermetic sandbox per test, with patch restoration."""

    def _enter_sandbox(self):
        root = Path(tempfile.mkdtemp(prefix="legacy_recall_eval_"))
        ctx = sandbox.sandbox_env(root)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.addCleanup(sandbox.restore_memory_patches)
        self.addCleanup(sandbox.teardown, root)
        original_now = harness.patch_fixed_now()
        self.addCleanup(harness.restore_now, original_now)
        sandbox.patch_memory_manager_base_db(root)
        return root


class FidelityTests(_SandboxTestCase):
    def test_fidelity_passes_in_proper_sandbox(self):
        root = self._enter_sandbox()
        self.assertTrue(harness.prove_sandbox_fidelity(root, run_id="t-fidelity-ok"))

    def test_fidelity_aborts_when_tier_path_outside_sandbox(self):
        root = self._enter_sandbox()

        import memory.memory_manager as mm_mod

        mm_mod.BASE_DB = Path("/home/rohit/maez/memory/db")
        with self.assertRaises(harness.HarnessAbort):
            harness.prove_sandbox_fidelity(root, run_id="t-fidelity-tampered")


if __name__ == "__main__":
    unittest.main()
