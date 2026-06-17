import unittest
from pathlib import Path


class ApplySupportGateTest(unittest.TestCase):
    def _gate(self, draft, evidence_map, verifier, budget_s=5.0):
        from core.cognition.grounding_shadow import apply_support_gate

        return apply_support_gate(
            draft,
            evidence_map,
            verifier,
            surface="cockpit",
            budget_s=budget_s,
        )

    def test_unsupported_sentence_gets_inline_caveat_not_deleted(self):
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        v = FakeSupportVerifier(default=(UNSUPPORTED, 0.1))

        out = self._gate(
            "Anthropic launched Mythos 5 [E1].",
            {"E1": "Anthropic released Opus."},
            v,
        )

        self.assertIn("Anthropic launched Mythos 5 [E1].", out.gated_marked_draft)
        self.assertIn(
            "I couldn't confirm this from the source I cited.",
            out.gated_marked_draft,
        )

    def test_supported_sentence_unchanged_and_inline_exactness(self):
        from core.cognition.support_verifier import (
            FakeSupportVerifier,
            SUPPORTED,
            UNSUPPORTED,
        )

        v = FakeSupportVerifier(
            scripted={
                "Claim A [E1].": (UNSUPPORTED, 0.1),
                "Claim B [E2].": (SUPPORTED, 0.9),
            }
        )

        out = self._gate("Claim A [E1]. Claim B [E2].", {"E1": "ev1", "E2": "ev2"}, v)
        g = out.gated_marked_draft

        self.assertIn(
            "Claim A [E1]. I couldn't confirm this from the source I cited.",
            g,
        )
        self.assertIn("Claim B [E2].", g)
        self.assertNotIn("Claim B [E2]. I couldn't confirm", g)

    def test_unmatched_citation_structural_caveat(self):
        from core.cognition.support_verifier import FakeSupportVerifier, SUPPORTED

        v = FakeSupportVerifier(default=(SUPPORTED, 0.99))

        out = self._gate("Claim [E9].", {"E1": "x"}, v)

        self.assertIn("I cited a source I can't match here.", out.gated_marked_draft)
        self.assertEqual(v.calls, [])

    def test_budget_exhausted_gets_unverified_caveat(self):
        from core.cognition.support_verifier import FakeSupportVerifier, SUPPORTED

        v = FakeSupportVerifier(default=(SUPPORTED, 0.99))

        out = self._gate(
            "First [E1]. Second [E2].",
            {"E1": "a", "E2": "b"},
            v,
            budget_s=-1.0,
        )

        self.assertIn("I couldn't verify this before sending.", out.gated_marked_draft)

    def test_no_citation_sentence_unchanged(self):
        from core.cognition.support_verifier import FakeSupportVerifier

        v = FakeSupportVerifier()

        out = self._gate("Just a thought.", {"E1": "x"}, v)

        self.assertEqual(out.gated_marked_draft.strip(), "Just a thought.")

    def test_uncited_unsupported_sentence_gets_evidence_caveat(self):
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        v = FakeSupportVerifier(default=(UNSUPPORTED, 0.1))

        out = self._gate(
            "Anthropic launched Mythos 5.",
            {"E1": "Anthropic released Claude Opus 4.5."},
            v,
        )

        self.assertIn("Anthropic launched Mythos 5.", out.gated_marked_draft)
        self.assertIn(
            "I couldn't confirm this from the evidence I had.",
            out.gated_marked_draft,
        )
        self.assertEqual(v.calls[0][1], "Anthropic launched Mythos 5.")

    def test_detached_citation_folds_onto_previous_sentence(self):
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        v = FakeSupportVerifier(default=(UNSUPPORTED, 0.1))

        out = self._gate("Anthropic launched Mythos 5. [E1]", {"E1": "Anthropic released Opus."}, v)

        self.assertIn("Anthropic launched Mythos 5. [E1]", out.gated_marked_draft)
        self.assertIn(
            "I couldn't confirm this from the source I cited.",
            out.gated_marked_draft,
        )
        self.assertEqual(v.calls[0][1], "Anthropic launched Mythos 5. [E1]")

    def test_detached_citation_newline_folds_onto_previous_sentence(self):
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        v = FakeSupportVerifier(default=(UNSUPPORTED, 0.1))

        out = self._gate("Anthropic launched Mythos 5.\n[E1]", {"E1": "Anthropic released Opus."}, v)

        self.assertIn("Anthropic launched Mythos 5. [E1]", out.gated_marked_draft)
        self.assertEqual(v.calls[0][1], "Anthropic launched Mythos 5. [E1]")


class GateRecordsTest(unittest.TestCase):
    def _gate(self, draft, evidence_map, verifier):
        from core.cognition.grounding_shadow import apply_support_gate

        return apply_support_gate(
            draft,
            evidence_map,
            verifier,
            surface="cockpit",
            shadow_id="sid",
            ts=0,
            boot_id="b",
        )

    def test_one_pass_no_duplicate_calls(self):
        from core.cognition.support_verifier import (
            FakeSupportVerifier,
            SUPPORTED,
            UNSUPPORTED,
        )

        v = FakeSupportVerifier(
            scripted={
                "A [E1].": (UNSUPPORTED, 0.1),
                "B [E2].": (SUPPORTED, 0.9),
            }
        )

        self._gate("A [E1]. B [E2].", {"E1": "x", "E2": "y"}, v)

        self.assertEqual(len(v.calls), 2)

    def test_support_row_marked_gate_applied_and_post_audit(self):
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        out = self._gate(
            "A [E1].",
            {"E1": "x"},
            FakeSupportVerifier(default=(UNSUPPORTED, 0.1)),
        )

        self.assertTrue(out.support_row["gate_applied"])
        self.assertTrue(out.support_row["post_audit"])
        self.assertEqual(out.support_row["sentences"][0]["support_verdict"], "UNSUPPORTED")
        self.assertEqual(out.support_row["sentences"][0]["cited_evidence_ids"], ["E1"])

    def test_gate_receipt_counts_match_actions(self):
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        out = self._gate(
            "A [E1]. B [E2].",
            {"E1": "x"},
            FakeSupportVerifier(default=(UNSUPPORTED, 0.1)),
        )

        receipt = out.gate_receipt
        self.assertEqual(receipt["caveated_unsupported"], 1)
        self.assertEqual(receipt["caveated_unmatched"], 1)
        self.assertIn("latency_ms", receipt)

    def test_uncited_gate_verdict_does_not_count_as_grounded_support(self):
        from core.cognition.support_verifier import FakeSupportVerifier, SUPPORTED

        out = self._gate(
            "Anthropic released Claude Opus 4.5.",
            {"E1": "Anthropic released Claude Opus 4.5."},
            FakeSupportVerifier(default=(SUPPORTED, 0.9)),
        )

        self.assertEqual(out.gate_receipt["cited"], 0)
        self.assertEqual(out.gate_receipt["uncited_checked"], 1)
        self.assertEqual(out.support_row["supported_count"], 0)
        self.assertFalse(out.support_row["sentences"][0]["counts_as_grounded"])
        self.assertEqual(
            out.support_row["sentences"][0]["mode"],
            "uncited_all_evidence_gate",
        )

    def test_support_row_status_reports_verifier_unavailable(self):
        from core.cognition.support_verifier import FakeSupportVerifier

        out = self._gate(
            "A [E1].",
            {"E1": "x"},
            FakeSupportVerifier(raises=RuntimeError("down")),
        )

        self.assertEqual(out.support_row["status"], "verifier_unavailable")

    def test_support_row_status_reports_budget_exhausted(self):
        from core.cognition.support_verifier import FakeSupportVerifier, SUPPORTED
        from core.cognition.grounding_shadow import apply_support_gate

        out = self._gate(
            "A [E1].",
            {"E1": "x"},
            FakeSupportVerifier(default=(SUPPORTED, 0.9)),
        )

        self.assertEqual(out.support_row["status"], "ok")

        exhausted = apply_support_gate(
            "A [E1].",
            {"E1": "x"},
            FakeSupportVerifier(default=(SUPPORTED, 0.9)),
            surface="cockpit",
            budget_s=-1.0,
        )
        self.assertEqual(exhausted.support_row["status"], "budget_exceeded")


class ObserveFocusedSupportGateTest(unittest.TestCase):
    def test_returns_gated_reply_logs_receipt_writes_row(self):
        import json
        import os
        import tempfile
        from unittest import mock

        import core.cognition.grounding_shadow as gs
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "grounding_shadow.jsonl")
            with (
                mock.patch.object(gs, "_default_telemetry_path", return_value=path),
                mock.patch.object(
                    gs,
                    "HttpSupportVerifier",
                    lambda: FakeSupportVerifier(default=(UNSUPPORTED, 0.1)),
                ),
                self.assertLogs("maez.grounding_shadow", level="INFO") as cm,
            ):
                gated = gs.observe_focused_support_gate(
                    "Claim [E1].",
                    {"E1": "x"},
                    surface="cockpit",
                    boot_id="b",
                    shadow_id="s",
                    ts=0,
                )

            self.assertIn("I couldn't confirm this from the source I cited.", gated)
            self.assertTrue(any("support_gate_applied" in message for message in cm.output))
            self.assertTrue(any("row_written=True" in message for message in cm.output))
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(line) for line in f]
            self.assertTrue(rows)
            self.assertTrue(rows[0]["gate_applied"])

    def test_row_write_failure_is_logged(self):
        from unittest import mock

        import core.cognition.grounding_shadow as gs
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        with (
            mock.patch.object(
                gs,
                "HttpSupportVerifier",
                lambda: FakeSupportVerifier(default=(UNSUPPORTED, 0.1)),
            ),
            mock.patch.object(gs, "emit_support_row", return_value=False),
            self.assertLogs("maez.grounding_shadow", level="INFO") as cm,
        ):
            gated = gs.observe_focused_support_gate(
                "Claim [E1].",
                {"E1": "x"},
                surface="cockpit",
                boot_id="b",
                shadow_id="s",
                ts=0,
            )

        self.assertIn("I couldn't confirm this from the source I cited.", gated)
        self.assertTrue(any("row_written=False" in message for message in cm.output))

    def test_gate_failure_logs_warning_and_returns_original(self):
        import json
        import os
        import tempfile
        from unittest import mock

        import core.cognition.grounding_shadow as gs

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "grounding_shadow.jsonl")
            with (
                mock.patch.object(gs, "_default_telemetry_path", return_value=path),
                mock.patch.object(
                    gs,
                    "apply_support_gate",
                    side_effect=RuntimeError("boom"),
                ),
                self.assertLogs("maez.grounding_shadow", level="WARNING") as cm,
            ):
                gated = gs.observe_focused_support_gate(
                    "Claim [E1].",
                    {"E1": "x"},
                    surface="cockpit",
                    boot_id="b",
                    shadow_id="s",
                    ts=0,
                )

            with open(path, encoding="utf-8") as f:
                rows = [json.loads(line) for line in f]

        self.assertEqual(gated, "Claim [E1]. I couldn't verify this before sending.")
        self.assertTrue(rows)
        self.assertEqual(rows[0]["status"], "gate_failed")
        self.assertEqual(rows[0]["error_class"], "RuntimeError")
        self.assertTrue(any("support_gate_failed" in message for message in cm.output))


class FlagMatrixTest(unittest.TestCase):
    def _decide(self, gate, shadow):
        from core.cognition.grounding_shadow import decide_support_path

        return decide_support_path(gate_enabled=gate, shadow_enabled=shadow)

    def test_matrix(self):
        self.assertEqual(self._decide(False, False), "none")
        self.assertEqual(self._decide(False, True), "async_shadow")
        self.assertEqual(self._decide(True, False), "sync_gate")
        self.assertEqual(self._decide(True, True), "sync_gate")


class DaemonSupportGateSourceTests(unittest.TestCase):
    def test_daemon_reads_gate_flag_independently_at_marked_draft_seam(self):
        src = Path("daemon/maez_daemon.py").read_text()
        guard_idx = src.find("reply = self._trf_apply_fragment_guard(")
        receipt_idx = src.find("retain_receipt(", guard_idx)
        render_idx = src.find("reply = render_natural(", guard_idx)
        gate_flag_idx = src.find('strict_env_flag("MAEZ_SUPPORT_GATE_ENABLED")', guard_idx)
        shadow_flag_idx = src.find('strict_env_flag("MAEZ_GROUNDING_SHADOW_ENABLED")', guard_idx)
        gate_call_idx = src.find("observe_focused_support_gate(", guard_idx)
        async_call_idx = src.find("observe_focused_support(", guard_idx)

        self.assertGreater(guard_idx, 0)
        self.assertGreater(receipt_idx, guard_idx)
        self.assertGreater(render_idx, receipt_idx)
        self.assertGreater(gate_flag_idx, guard_idx)
        self.assertGreater(shadow_flag_idx, guard_idx)
        self.assertGreater(gate_call_idx, guard_idx)
        self.assertGreater(async_call_idx, guard_idx)
        self.assertLess(gate_call_idx, receipt_idx)
        self.assertLess(async_call_idx, receipt_idx)


class RenderNaturalSurvivalTest(unittest.TestCase):
    def test_caveat_survives_render_natural_and_markers_stripped(self):
        from unittest import mock

        from core.routing.attribution_render import render_natural

        gated = (
            "Anthropic launched Mythos 5 [E1]. "
            "I couldn't confirm this from the source I cited."
        )
        with mock.patch("core.routing.attribution_render.sense_enabled", return_value=True):
            out = render_natural(gated, web_evidence_present=False)

        self.assertNotIn("[E1]", out)
        self.assertIn("I couldn't confirm this from the source I cited.", out)

    def test_receipts_retains_gated_marked_draft(self):
        from core.routing.attribution_render import last_receipt, retain_receipt

        gated = "Claim [E1]. I couldn't confirm this from the source I cited."

        retain_receipt("support-gate-test-chat", marked=gated, sources=["https://example.test"])

        self.assertEqual(last_receipt("support-gate-test-chat")["marked"], gated)


class FlagOffByteIdenticalTest(unittest.TestCase):
    def test_gate_off_no_support_gate_path(self):
        from core.cognition.grounding_shadow import decide_support_path

        self.assertEqual(
            decide_support_path(gate_enabled=False, shadow_enabled=False),
            "none",
        )
        self.assertEqual(
            decide_support_path(gate_enabled=False, shadow_enabled=True),
            "async_shadow",
        )
