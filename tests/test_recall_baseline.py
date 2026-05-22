from __future__ import annotations

import unittest


class RecallBaselineProbeTests(unittest.TestCase):
    def test_canonical_probe_seed_is_rohit_authored_and_byte_faithful(self):
        from scripts.measure_recall_baseline import load_probe_seed

        probes = load_probe_seed()

        self.assertEqual(
            [(p.probe_id, p.query) for p in probes],
            [
                ("trust_boundary_01", "Do you want to know something about me?"),
                (
                    "careful_access_01",
                    "I am allowing you to explore my files given you treat them with care.",
                ),
                (
                    "sleep_drift_01",
                    "I have been going to sleep little later than usual. Wonder what keeps me",
                ),
            ],
        )

    def test_run_baseline_calls_lived_recall_builder_not_daemon(self):
        from scripts.measure_recall_baseline import Probe, run_recall_baseline

        calls = []

        def fake_builder(query, *, episode_store, graph, max_items):
            calls.append((query, episode_store, graph, max_items))
            return (
                "=== LIVED RECALL -- EVIDENCE-BACKED ===\n"
                "- Past episode: careful access [episode: ep-care | sources: raw-care]\n"
                "- Open loop: sleep drift [episode: ep-sleep | sources: core-sleep]"
            )

        report = run_recall_baseline(
            probes=[Probe("p1", "hello", "intent")],
            episode_store="episodes",
            graph="graph",
            max_items=4,
            build_fn=fake_builder,
        )

        self.assertEqual(calls, [("hello", "episodes", "graph", 4)])
        self.assertEqual(report["probes"][0]["memory_ids"], ["ep-care", "raw-care", "ep-sleep", "core-sleep"])
        self.assertNotIn("daemon", str(report).lower())

    def test_regression_metric_is_deterministic_overlap_and_rank(self):
        from scripts.measure_recall_baseline import compare_memory_id_rankings

        metric = compare_memory_id_rankings(
            baseline=["raw-a", "raw-b", "raw-c"],
            candidate=["raw-b", "raw-a", "raw-d"],
        )

        self.assertEqual(metric["baseline_count"], 3)
        self.assertEqual(metric["candidate_count"], 3)
        self.assertEqual(metric["overlap_count"], 2)
        self.assertAlmostEqual(metric["overlap_ratio"], 2 / 3)
        self.assertEqual(metric["rank_delta_sum"], 2)
        self.assertFalse(metric["passes"])
