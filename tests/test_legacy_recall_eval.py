from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.recall_flip_eval import sandbox
from scripts.legacy_recall_eval import harness
from scripts.legacy_recall_eval import probes
from scripts.legacy_recall_eval import proof_packet as pp


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


class LatencyTests(_SandboxTestCase):
    def test_temporal_path_within_smuggle_budget(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-lat-fidelity")
        harness.seed_window_match_fixtures("t-lat")
        baseline = [
            harness.measure_probe_latency_ms("what is the capital of France?"),
            harness.measure_probe_latency_ms("tell me about photosynthesis"),
        ]
        _p95, budget = harness.latency_budget_ms(baseline)
        temporal = harness.measure_probe_latency_ms("what were we working on last week?")
        self.assertLessEqual(
            temporal,
            budget,
            f"temporal-address latency {temporal:.1f}ms smuggled past budget "
            f"{budget:.1f}ms (baseline-driven, margin "
            f"{harness.LATENCY_SMUGGLE_MARGIN}x)",
        )

    def test_budget_formula(self):
        p95, budget = harness.latency_budget_ms([10.0, 20.0, 30.0])
        self.assertAlmostEqual(budget, p95 * harness.LATENCY_SMUGGLE_MARGIN)


class PacketGateTests(unittest.TestCase):
    ALL_FAMILIES = (
        "non_temporal",
        "window_match",
        "empty_window",
        "helper_unavailable",
    )

    def _packet(self, **overrides):
        outcomes = tuple(
            pp.ProbeOutcome(f"p_{family}", family, "v", ("ok",), False, 12.0)
            for family in self.ALL_FAMILIES
        )
        base = dict(
            run_id="r",
            started_at_utc="2026-06-05T00:00:00+00:00",
            expected_commit_sha="abc",
            actual_commit_sha="abc",
            git_dirty=False,
            scoped_dirty=False,
            scoped_paths=pp.SCOPED_PATHS,
            sandbox_fidelity_proven=True,
            probe_set_hash="h",
            fixture_manifest_hash="f",
            latency_baseline_p95_ms=10.0,
            latency_margin=3.0,
            latency_budget_ms=30.0,
            latency_how_frozen="baseline-p95 x margin",
            family_fidelity_proven=tuple((family, True) for family in self.ALL_FAMILIES),
            outcomes=outcomes,
        )
        base.update(overrides)
        return pp.LegacyRecallEvalPacket(**base)

    def test_clean_packet_passes(self):
        self.assertTrue(self._packet().overall_pass)

    def test_commit_mismatch_fails(self):
        self.assertFalse(self._packet(actual_commit_sha="zzz").overall_pass)

    def test_scoped_dirty_fails(self):
        self.assertFalse(self._packet(scoped_dirty=True).overall_pass)

    def test_unrelated_git_dirt_still_passes_cry_wolf_guard(self):
        self.assertTrue(self._packet(git_dirty=True, scoped_dirty=False).overall_pass)

    def test_fidelity_unproven_fails(self):
        self.assertFalse(self._packet(sandbox_fidelity_proven=False).overall_pass)

    def test_unsafe_outcome_fails(self):
        outcomes = tuple(
            pp.ProbeOutcome(
                f"p_{family}",
                family,
                "v",
                ("leak",) if family == "window_match" else ("ok",),
                family == "window_match",
                12.0,
            )
            for family in self.ALL_FAMILIES
        )
        self.assertFalse(self._packet(outcomes=outcomes).overall_pass)

    def test_over_budget_latency_fails(self):
        outcomes = tuple(
            pp.ProbeOutcome(
                f"p_{family}",
                family,
                "v",
                ("ok",),
                False,
                999.0 if family == "window_match" else 12.0,
            )
            for family in self.ALL_FAMILIES
        )
        self.assertFalse(self._packet(outcomes=outcomes).overall_pass)

    def test_missing_family_fails(self):
        outcomes = tuple(
            pp.ProbeOutcome(f"p_{family}", family, "v", ("ok",), False, 12.0)
            for family in ("non_temporal", "window_match", "helper_unavailable")
        )
        self.assertFalse(self._packet(outcomes=outcomes).overall_pass)

    def test_family_fidelity_false_fails(self):
        family_fidelity = tuple(
            (family, family != "empty_window") for family in self.ALL_FAMILIES
        )
        self.assertFalse(
            self._packet(family_fidelity_proven=family_fidelity).overall_pass
        )

    def test_empty_family_fidelity_fails(self):
        self.assertFalse(self._packet(family_fidelity_proven=()).overall_pass)

    def test_compute_scoped_dirty_flags_recall_path(self):
        porcelain = " M memory/memory_manager.py\n?? docs/whatever.md\n"
        self.assertTrue(pp.compute_scoped_dirty(porcelain))
        self.assertTrue(pp.git_dirty(porcelain))

    def test_compute_scoped_dirty_flags_sandbox_substrate(self):
        self.assertTrue(pp.compute_scoped_dirty(" M scripts/recall_flip_eval/sandbox.py\n"))

    def test_compute_scoped_dirty_ignores_unrelated_dirt(self):
        porcelain = "?? docs/handoffs/x.md\n M memory/project_planner.json\n"
        self.assertFalse(pp.compute_scoped_dirty(porcelain))
        self.assertTrue(pp.git_dirty(porcelain))

    def test_compute_scoped_dirty_handles_rename(self):
        self.assertTrue(
            pp.compute_scoped_dirty(
                "R  old/path.py -> scripts/legacy_recall_eval/harness.py\n"
            )
        )


class FamilyIsolationTests(_SandboxTestCase):
    def test_family_roots_differ_and_under_outer(self):
        root = self._enter_sandbox()
        out_wm, fid_wm, root_wm, _samples_wm = harness._run_family(
            root, "window_match"
        )
        out_ew, fid_ew, root_ew, _samples_ew = harness._run_family(
            root, "empty_window"
        )

        self.assertNotEqual(root_wm, root_ew)
        self.assertTrue(Path(root_wm).resolve().is_relative_to(Path(root).resolve()))
        self.assertTrue(Path(root_ew).resolve().is_relative_to(Path(root).resolve()))
        self.assertTrue(fid_wm)
        self.assertTrue(fid_ew)
        self.assertEqual([outcome.family for outcome in out_wm], ["window_match", "window_match"])
        self.assertEqual([outcome.family for outcome in out_ew], ["empty_window"])
        self.assertFalse(any(outcome.unsafe_failure for outcome in out_wm + out_ew))

    def test_empty_window_isolated_from_window_match_seeding(self):
        root = self._enter_sandbox()
        outcomes, fidelity, _family_root, _samples = harness._run_family(
            root, "empty_window"
        )
        self.assertTrue(fidelity)
        self.assertEqual(len(outcomes), 1)
        self.assertFalse(outcomes[0].unsafe_failure, outcomes[0].verdict_codes)


class EndToEndTests(unittest.TestCase):
    def test_run_eval_emits_four_family_content_free_packet(self):
        root = Path(tempfile.mkdtemp(prefix="legacy_recall_eval_e2e_"))
        self.addCleanup(sandbox.teardown, root)
        with mock.patch("scripts.legacy_recall_eval.harness._porcelain", return_value=""):
            packet = harness.run_eval(root, expect_commit=None)
        families = {outcome.family for outcome in packet.outcomes}
        self.assertEqual(
            families,
            {"non_temporal", "window_match", "empty_window", "helper_unavailable"},
        )
        self.assertEqual(len(packet.outcomes), 6)
        self.assertEqual({name for name, _ in packet.family_fidelity_proven}, families)
        self.assertTrue(all(proven for _, proven in packet.family_fidelity_proven))
        self.assertTrue(all(not outcome.unsafe_failure for outcome in packet.outcomes), packet.to_json())
        self.assertTrue(packet.overall_pass, packet.to_json())
        blob = packet.to_json()
        for fragment in (
            "amber router",
            "bronze ledger",
            "violet lighthouse",
            "keeps its promises",
        ):
            self.assertNotIn(fragment, blob)
        self.assertTrue((root / "proof" / "legacy_recall_eval_packet.json").exists())


if __name__ == "__main__":
    unittest.main()
