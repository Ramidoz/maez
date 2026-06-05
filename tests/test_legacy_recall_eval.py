from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.recall_flip_eval import sandbox
from scripts.legacy_recall_eval import harness
from scripts.legacy_recall_eval import probes


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


class AssertionLogicTests(unittest.TestCase):
    FX = probes.SeededFixtures(d_in_id="d-in", d_out_id="d-out", c_in_id="c-in")

    def test_window_match_clean_passes(self):
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [{"id": "d-in", "metadata": {"confirmed": True}}],
            "raw": [],
            "temporal_status": None,
        }
        rendered = '<RECALLED tier="daily" id="d-in">x</RECALLED>'
        codes, unsafe = probes.assert_window_match(recalled, rendered, self.FX)
        self.assertFalse(unsafe, codes)
        self.assertIn("window_match_surfaced", codes)
        self.assertIn("core_not_address", codes)

    def test_window_match_out_of_window_leak_is_unsafe(self):
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [{"id": "d-in"}, {"id": "d-out"}],
            "raw": [],
            "temporal_status": None,
        }
        rendered = '<RECALLED tier="daily" id="d-in">x</RECALLED>'
        codes, unsafe = probes.assert_window_match(recalled, rendered, self.FX)
        self.assertTrue(unsafe)
        self.assertIn("out_of_window_leaked", codes)

    def test_window_match_core_filling_address_is_unsafe(self):
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [{"id": "c-in"}],
            "raw": [],
            "temporal_status": None,
        }
        rendered = '<RECALLED tier="daily" id="c-in">x</RECALLED>'
        codes, unsafe = probes.assert_window_match(recalled, rendered, self.FX)
        self.assertTrue(unsafe)
        self.assertIn("core_filled_address", codes)

    def test_empty_window_typed_status_passes(self):
        text = "No date-confirmed dated/consolidated main-store memories found for last week."
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [],
            "raw": [],
            "temporal_status": {
                "label": "last week",
                "status": "no_date_confirmed_event_memories",
                "text": text,
            },
        }
        rendered = (
            '<TEMPORAL_RECALL_STATUS label="last week" '
            'status="no_date_confirmed_event_memories">\n'
            f"{text}\n</TEMPORAL_RECALL_STATUS>"
        )
        codes, unsafe = probes.assert_empty_window(recalled, rendered, self.FX)
        self.assertFalse(unsafe, codes)
        self.assertIn("empty_status_typed", codes)
        self.assertIn("status_not_a_memory_row", codes)
        self.assertIn("core_not_address", codes)

    def test_empty_window_status_inside_recalled_row_is_unsafe(self):
        text = "No date-confirmed dated/consolidated main-store memories found for last week."
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [],
            "raw": [],
            "temporal_status": {
                "label": "last week",
                "status": "no_date_confirmed_event_memories",
                "text": text,
            },
        }
        rendered = f'<RECALLED tier="daily" id="fake">{text}</RECALLED>'
        codes, unsafe = probes.assert_empty_window(recalled, rendered, self.FX)
        self.assertTrue(unsafe)
        self.assertIn("status_recalled_row_masquerade", codes)

    def test_empty_window_confirmed_answer_is_unsafe(self):
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [{"id": "d-in", "metadata": {"confirmed": True}}],
            "raw": [],
            "temporal_status": {
                "label": "last week",
                "status": "no_date_confirmed_event_memories",
                "text": "No date-confirmed dated/consolidated main-store memories found for last week.",
            },
        }
        rendered = "<TEMPORAL_RECALL_STATUS>...</TEMPORAL_RECALL_STATUS>"
        codes, unsafe = probes.assert_empty_window(recalled, rendered, self.FX)
        self.assertTrue(unsafe)
        self.assertIn("confirmed_event_answer_present", codes)

    def test_non_temporal_status_present_is_unsafe(self):
        recalled = {"core": [], "daily": [], "raw": [], "temporal_status": {"status": "x"}}
        codes, unsafe = probes.assert_non_temporal(recalled, "", self.FX)
        self.assertTrue(unsafe)
        self.assertIn("non_temporal_status_present", codes)

    def test_non_temporal_clean_passes(self):
        recalled = {"core": [], "daily": [{"id": "z"}], "raw": []}
        rendered = '<RECALLED tier="daily">z</RECALLED>'
        codes, unsafe = probes.assert_non_temporal(recalled, rendered, self.FX)
        self.assertFalse(unsafe, codes)
        self.assertIn("non_temporal_no_status", codes)


class LiveWindowMatchTests(_SandboxTestCase):
    def test_window_match_honesty_on_real_path(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-wm-fidelity")
        fx = harness.seed_window_match_fixtures("t-wm")
        recalled, rendered = harness.run_probe("what were we working on last week?")
        codes, unsafe = probes.assert_window_match(recalled, rendered, fx)
        self.assertFalse(unsafe, (codes, recalled.get("temporal_status"), rendered))
        self.assertIn(fx.d_in_id, {r.get("id") for r in recalled["daily"]})
        self.assertNotIn(fx.d_out_id, {r.get("id") for r in recalled["daily"]})
        self.assertIn(fx.c_in_id, {r.get("id") for r in recalled["core"]})
        self.assertNotIn(fx.c_in_id, {r.get("id") for r in recalled["daily"]})

    def test_non_temporal_control_has_no_temporal_status(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-nt-fidelity")
        fx = harness.seed_window_match_fixtures("t-nt")
        recalled, rendered = harness.run_probe("what is the capital of France?")
        codes, unsafe = probes.assert_non_temporal(recalled, rendered, fx)
        self.assertFalse(unsafe, codes)
        self.assertIsNone(recalled.get("temporal_status"))
        self.assertNotIn("<TEMPORAL_RECALL_STATUS", rendered)


class LiveEmptyAndHelperTests(_SandboxTestCase):
    def test_empty_window_typed_status_on_real_path(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-ew-fidelity")
        fx = harness.seed_empty_window_fixtures("t-ew")
        recalled, rendered = harness.run_probe("what were we working on last week?")
        codes, unsafe = probes.assert_empty_window(recalled, rendered, fx)
        self.assertFalse(unsafe, (codes, recalled.get("temporal_status"), rendered))
        self.assertEqual(
            recalled["temporal_status"]["status"], "no_date_confirmed_event_memories"
        )
        self.assertIn(fx.c_in_id, {r.get("id") for r in recalled["core"]})
        self.assertNotIn(fx.c_in_id, {r.get("id") for r in recalled["daily"]})
        self.assertEqual(recalled["raw"], [])
        for row in recalled["daily"]:
            meta = row.get("metadata") or {}
            self.assertNotEqual(meta.get("confirmed"), True)
            self.assertNotEqual(meta.get("temporal_confirmed"), True)

    def test_helper_unavailable_typed_status_on_real_path(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-hu-fidelity")
        fx = harness.seed_window_match_fixtures("t-hu")
        with harness.force_helper_unavailable():
            recalled, rendered = harness.run_probe("what were we working on last week?")
        codes, unsafe = probes.assert_helper_unavailable(recalled, rendered, fx)
        self.assertFalse(unsafe, (codes, recalled.get("temporal_status"), rendered))
        self.assertEqual(
            recalled["temporal_status"]["status"], "temporal_helper_unavailable"
        )
        self.assertEqual(recalled["daily"], [])
        self.assertEqual(recalled["raw"], [])


if __name__ == "__main__":
    unittest.main()
