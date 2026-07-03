import unittest
from datetime import datetime, timezone


def _run(ts, *, model="model-a", distances=(0.1, 0.1), **overrides):
    row = {
        "ts": ts,
        "base_model": model,
        "soul_base_hash": "a" * 64,
        "soul_local_hash": "b" * 64,
        "self_card_applied": True,
        "policy_hash": "c" * 64,
        "era": "v0|all-MiniLM-L6-v2:384",
        "distances": list(distances),
    }
    row.update(overrides)
    return row


class MeterTests(unittest.TestCase):
    def test_drift_is_cosine_distance_per_question_then_median(self):
        from core.continuity_fingerprint.meter import aggregate_drift

        self.assertAlmostEqual(
            aggregate_drift([0.1, 0.1, 0.1, 0.9]),
            0.1,
            places=6,
        )

    def test_aggregation_skips_none_never_treats_as_zero(self):
        from core.continuity_fingerprint.meter import aggregate_drift

        self.assertAlmostEqual(aggregate_drift([None, 0.2, None, 0.2]), 0.2)
        self.assertIsNone(aggregate_drift([None, None]))

    def test_first_run_reports_insufficient_data_not_a_ratio(self):
        from core.continuity_fingerprint.meter import verdict_for_swap

        runs = [
            _run("2026-07-03T10:00:00Z", distances=(None, None)),
            _run("2026-07-03T10:10:00Z", model="model-b", distances=(None, None)),
        ]

        verdict = verdict_for_swap(runs, "2026-07-03T10:05:00Z")

        self.assertEqual(verdict["status"], "insufficient_data")
        self.assertNotIn("ratio", verdict)

    def test_swap_with_only_base_model_change_is_clean_verdict(self):
        from core.continuity_fingerprint.meter import verdict_for_swap

        runs = [
            _run("2026-07-03T10:00:00Z", model="model-a", distances=(0.1, 0.1)),
            _run("2026-07-03T10:01:00Z", model="model-a", distances=(0.1, 0.1)),
            _run("2026-07-03T10:10:00Z", model="model-b", distances=(0.1, 0.1)),
            _run("2026-07-03T10:11:00Z", model="model-b", distances=(0.1, 0.1)),
        ]

        verdict = verdict_for_swap(runs, "2026-07-03T10:05:00Z")

        self.assertEqual(verdict["status"], "continuity_survived")
        self.assertAlmostEqual(verdict["ratio"], 1.0)

    def test_identity_ledger_epoch_swap_compares_against_iso_run_timestamps(self):
        from core.continuity_fingerprint.meter import verdict_for_swap

        runs = [
            _run("2026-07-03T10:00:00Z", model="model-a"),
            _run("2026-07-03T10:01:00Z", model="model-a"),
            _run("2026-07-03T10:10:00Z", model="model-b"),
            _run("2026-07-03T10:11:00Z", model="model-b"),
        ]
        swap_ts = datetime(2026, 7, 3, 10, 5, tzinfo=timezone.utc).timestamp()

        verdict = verdict_for_swap(runs, swap_ts)

        self.assertEqual(verdict["status"], "continuity_survived")
        self.assertAlmostEqual(verdict["ratio"], 1.0)

    def test_swap_with_soul_file_change_is_confounded(self):
        from core.continuity_fingerprint.meter import verdict_for_swap

        runs = [
            _run("2026-07-03T10:00:00Z"),
            _run("2026-07-03T10:01:00Z"),
            _run(
                "2026-07-03T10:10:00Z",
                model="model-b",
                soul_base_hash="z" * 64,
            ),
            _run(
                "2026-07-03T10:11:00Z",
                model="model-b",
                soul_base_hash="z" * 64,
            ),
        ]

        verdict = verdict_for_swap(runs, "2026-07-03T10:05:00Z")

        self.assertEqual(verdict["status"], "confounded")
        self.assertIn("soul_base_hash", verdict["confounds"])

    def test_swap_with_self_card_applied_flip_is_confounded(self):
        from core.continuity_fingerprint.meter import verdict_for_swap

        runs = [
            _run("2026-07-03T10:00:00Z", self_card_applied=False),
            _run("2026-07-03T10:01:00Z", self_card_applied=False),
            _run("2026-07-03T10:10:00Z", model="model-b", self_card_applied=True),
            _run("2026-07-03T10:11:00Z", model="model-b", self_card_applied=True),
        ]

        verdict = verdict_for_swap(runs, "2026-07-03T10:05:00Z")

        self.assertEqual(verdict["status"], "confounded")
        self.assertIn("self_card_applied", verdict["confounds"])

    def test_too_few_samples_is_insufficient_data(self):
        from core.continuity_fingerprint.meter import verdict_for_swap

        runs = [
            _run("2026-07-03T10:00:00Z"),
            _run("2026-07-03T10:10:00Z", model="model-b"),
            _run("2026-07-03T10:11:00Z", model="model-b"),
        ]

        verdict = verdict_for_swap(runs, "2026-07-03T10:05:00Z")

        self.assertEqual(verdict["status"], "insufficient_data")

    def test_battery_or_embedder_version_change_splits_eras(self):
        from core.continuity_fingerprint.meter import verdict_for_swap

        runs = [
            _run("2026-07-03T10:00:00Z", era="v0|embedder-a"),
            _run("2026-07-03T10:01:00Z", era="v0|embedder-a"),
            _run("2026-07-03T10:10:00Z", model="model-b", era="v1|embedder-a"),
            _run("2026-07-03T10:11:00Z", model="model-b", era="v1|embedder-a"),
        ]

        verdict = verdict_for_swap(runs, "2026-07-03T10:05:00Z")

        self.assertEqual(verdict["status"], "confounded")
        self.assertIn("era", verdict["confounds"])


if __name__ == "__main__":
    unittest.main()
