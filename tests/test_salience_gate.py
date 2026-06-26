import unittest

from core.cognition.salience_gate import (
    MAX_FACT_SHARE,
    MAX_PLACEBO_DELTA,
    MIN_COHERENT,
    MIN_CONTROL_NONE,
    MIN_LIFT,
    MIN_LIFT_Z,
    MIN_PROPOSED_ARM,
    MIN_ROWS,
    MIN_WITHHELD,
    evaluate_gate,
    two_proportion_z,
)


def _row(arm, fact="time_facts", coherent=False, repetition_signal="not_applicable"):
    return {
        "arm": arm,
        "fact_key": fact if arm in ("proposed", "control_withheld") else "none",
        "thought_formed": int(coherent),
        "non_duplicate_stored": int(coherent),
        "repetition_signal": repetition_signal,
        "unmoved": int(not coherent),
    }


class GateThresholdsTest(unittest.TestCase):
    def test_locked_threshold_values(self):
        # PRE-REGISTERED -- these must not drift without a documented amendment.
        self.assertEqual(
            (
                MIN_ROWS,
                MIN_PROPOSED_ARM,
                MIN_CONTROL_NONE,
                MIN_WITHHELD,
                MIN_COHERENT,
                MIN_LIFT,
                MIN_LIFT_Z,
                MAX_PLACEBO_DELTA,
                MAX_FACT_SHARE,
            ),
            (500, 100, 100, 20, 20, 0.05, 1.96, 0.05, 0.80),
        )

    def test_today_small_ledger_is_baseline_only(self):
        rows = [_row("proposed")] * 6 + [_row("control_none")] * 2 + [_row("cold_start")]
        rep = evaluate_gate(rows, welfare={"backup_freshness": "unavailable"})
        self.assertEqual(rep["gate_state"], "BASELINE_ONLY")
        self.assertIn("insufficient_sample", rep["failing_codes"])

    def test_enough_data_no_lift_is_no_go(self):
        rows = (
            [_row("proposed", coherent=(i < 10)) for i in range(120)]
            + [_row("control_none", coherent=(i < 10)) for i in range(120)]
            + [_row("control_withheld") for _ in range(25)]
            + [_row("cold_start") for _ in range(235)]
        )
        rep = evaluate_gate(rows, welfare={"backup_freshness": "fresh"})
        self.assertEqual(rep["gate_state"], "NO_GO")
        self.assertIn("no_lift", rep["failing_codes"])

    def test_monoculture_fires(self):
        rows = (
            [_row("proposed", fact="time_facts", coherent=(i < 60)) for i in range(120)]
            + [_row("control_none", coherent=(i < 10)) for i in range(120)]
            + [_row("control_withheld", fact="time_facts", coherent=(i < 13)) for i in range(25)]
            + [_row("cold_start") for _ in range(235)]
        )
        rep = evaluate_gate(rows, welfare={"backup_freshness": "fresh"})
        self.assertIn("monoculture", rep["failing_codes"])

    def test_instrumentation_effect_fires(self):
        rows = (
            [_row("proposed", fact=("time_facts" if i % 2 else "body_state"), coherent=(i < 40)) for i in range(120)]
            + [_row("control_none", coherent=(i < 5)) for i in range(120)]
            + [_row("control_withheld", fact=("time_facts" if i % 2 else "body_state"), coherent=False) for i in range(25)]
            + [_row("cold_start") for _ in range(235)]
        )
        rep = evaluate_gate(rows, welfare={"backup_freshness": "fresh"})
        self.assertIn("instrumentation_effect", rep["failing_codes"])

    def test_fixation_risk_fires_on_duplicate_repetition_signal(self):
        rows = (
            [_row("proposed", fact=("time_facts" if i % 2 else "body_state"), coherent=(i < 60)) for i in range(160)]
            + [_row("control_none", coherent=(i < 10)) for i in range(160)]
            + [_row("control_withheld", fact=("time_facts" if i % 2 else "body_state"), coherent=(i < 9)) for i in range(25)]
            + [_row("proposed", fact="body_state", repetition_signal="duplicate")]
            + [_row("cold_start") for _ in range(154)]
        )
        rep = evaluate_gate(rows, welfare={"backup_freshness": "fresh"})
        self.assertIn("fixation_risk", rep["failing_codes"])

    def test_clean_pass_but_backup_blocks_canary(self):
        rows = (
            [_row("proposed", fact=("time_facts" if i % 2 else "body_state"), coherent=(i < 60)) for i in range(160)]
            + [_row("control_none", coherent=(i < 10)) for i in range(160)]
            + [_row("control_withheld", fact=("time_facts" if i % 2 else "body_state"), coherent=(i < 9)) for i in range(25)]
            + [_row("cold_start") for _ in range(155)]
        )
        blocked = evaluate_gate(rows, welfare={"backup_freshness": "unavailable"})
        allowed = evaluate_gate(rows, welfare={"backup_freshness": "fresh"})
        self.assertEqual(blocked["gate_state"], "CANARY_BLOCKED")
        self.assertEqual(allowed["gate_state"], "CANARY_ALLOWED")
        self.assertNotIn("FULL_GO", str(allowed))

    def test_report_is_content_light(self):
        rep = evaluate_gate([_row("proposed")], welfare={"backup_freshness": "fresh"})
        blob = str(rep).lower()
        for forbidden in ("prompt", "secret", "raw", "owner replied", "owner seemed pleased"):
            self.assertNotIn(forbidden, blob)

    def test_z_test_basic(self):
        self.assertAlmostEqual(two_proportion_z(0, 100, 0, 100), 0.0, places=3)
        self.assertGreater(two_proportion_z(60, 100, 10, 100), 1.96)


class WelfareBaselineTest(unittest.TestCase):
    def test_welfare_baseline_is_content_light_snapshot(self):
        from core.cognition.salience_gate import welfare_baseline

        class _PrivateThoughts:
            def count(self):
                return 2

            def recent(self, limit=20):
                return [
                    {"context": {"extra": {"output_sha256": "abc"}}},
                    {"context": {"extra": {}}},
                ]

        snap = welfare_baseline(
            private_thoughts=_PrivateThoughts(),
            operator_health={"backup_freshness_class": "unavailable"},
            watchdog={"watchdog_state": "observing"},
        )
        self.assertEqual(snap["substrate"]["backup_freshness"], "unavailable")
        self.assertEqual(snap["substrate"]["watchdog"], "observing")
        self.assertEqual(snap["internal"]["private_thought_count"], 2)
        self.assertEqual(snap["internal"]["dedup_proxy"], 0.5)
        self.assertEqual(
            snap["voice_relationship"]["note"],
            "captured by human witness checklist, not numbers",
        )
        self.assertNotIn("thought_text", str(snap).lower())
