from __future__ import annotations

import unittest

from core.cognition import intake_faculty as inf


class IntakeReadSchemaTests(unittest.TestCase):
    def test_valid_read_parses_closed_fields(self):
        raw = {
            "turn_kind": "commitment_response",
            "stance": "yes",
            "boundary_signal": "none",
            "needs": "search",
            "referent_kind": "pending_offer",
            "confidence": 0.84,
            "rationale": "The owner is accepting the pending search offer.",
        }

        read = inf.IntakeRead.from_model(raw)

        self.assertEqual(read.turn_kind, "commitment_response")
        self.assertEqual(read.stance, "yes")
        self.assertEqual(read.needs, "search")
        self.assertEqual(read.referent_kind, "pending_offer")
        self.assertEqual(read.confidence_bucket, "high")

    def test_malformed_read_becomes_safe_ambiguous(self):
        read = inf.IntakeRead.from_model({
            "turn_kind": "act_now",
            "stance": "definitely",
            "boundary_signal": "urgent",
            "needs": "delete_files",
            "referent_kind": "full raw referent",
            "confidence": "high",
            "rationale": "bad shape",
        })

        self.assertEqual(read.turn_kind, "ambiguous")
        self.assertEqual(read.stance, "ambiguous")
        self.assertEqual(read.boundary_signal, "none")
        self.assertEqual(read.needs, "none")
        self.assertEqual(read.referent_kind, "none")
        self.assertEqual(read.confidence_bucket, "unknown")

    def test_content_light_payload_excludes_rationale(self):
        read = inf.IntakeRead.from_model({
            "turn_kind": "boundary",
            "stance": "n_a",
            "boundary_signal": "hard",
            "needs": "none",
            "referent_kind": "none",
            "confidence": 0.7,
            "rationale": "Owner wants to step back from the conversation.",
        })

        telemetry = read.to_telemetry(debug=False)

        self.assertEqual(telemetry["turn_kind"], "boundary")
        self.assertEqual(telemetry["boundary_signal"], "hard")
        self.assertNotIn("rationale", telemetry)
        self.assertNotIn("step back", str(telemetry))

    def test_debug_payload_may_include_rationale(self):
        read = inf.IntakeRead.from_model({
            "turn_kind": "boundary",
            "stance": "n_a",
            "boundary_signal": "soft",
            "needs": "none",
            "referent_kind": "none",
            "confidence": 0.6,
            "rationale": "diagnostic rationale",
        })

        telemetry = read.to_telemetry(debug=True)

        self.assertEqual(telemetry["rationale"], "diagnostic rationale")


class FakeIntakeBackendTests(unittest.TestCase):
    def test_fake_backend_returns_scripted_read(self):
        backend = inf.FakeIntakeBackend({
            "yeah sure": inf.IntakeRead(
                turn_kind="commitment_response",
                stance="yes",
                boundary_signal="none",
                needs="search",
                referent_kind="pending_offer",
                confidence=0.9,
                rationale="accepting offer",
            )
        })

        read, latency = backend.read("yeah sure", {"turns": []}, timeout_s=0.1)

        self.assertEqual(read.turn_kind, "commitment_response")
        self.assertEqual(read.stance, "yes")
        self.assertGreaterEqual(latency, 0.0)

    def test_fake_backend_can_report_busy(self):
        backend = inf.FakeIntakeBackend(busy=True)

        read, latency = backend.read("anything", {}, timeout_s=0.1)

        self.assertEqual(read.status, "judge_busy")
        self.assertEqual(read.turn_kind, "ambiguous")
