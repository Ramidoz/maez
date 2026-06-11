from dataclasses import dataclass, field
import json
import os
import tempfile
import time
import unittest

from core.cognition import grounding_shadow as gs
from core.cognition.support_verifier import FakeSupportVerifier, SUPPORTED, UNSUPPORTED


CLAIMABLE = [
    {
        "text": "f",
        "provenance": "memory",
        "evidence": "The recall flip was a No-Go on latency.",
    }
]


class SplitTests(unittest.TestCase):
    def test_split_sentences(self):
        self.assertEqual(gs.split_sentences("A b. C d! E f?"), ["A b.", "C d!", "E f?"])

    def test_split_empty(self):
        self.assertEqual(gs.split_sentences("   "), [])


class ComputeTests(unittest.TestCase):
    def test_no_claimable_calls_no_verifier(self):
        v = FakeSupportVerifier()
        out = gs.compute_shadow("A sentence.", [], v)
        self.assertEqual(out["status"], "no_claimable")
        self.assertEqual(v.calls, [])

    def test_no_sentences(self):
        out = gs.compute_shadow("   ", CLAIMABLE, FakeSupportVerifier())
        self.assertEqual(out["status"], "no_sentences")

    def test_ok_runs_per_sentence(self):
        v = FakeSupportVerifier(default=(SUPPORTED, 0.9))
        out = gs.compute_shadow("One. Two.", CLAIMABLE, v)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(len(out["sentences"]), 2)
        self.assertEqual(out["sentences"][0]["verdict"], SUPPORTED)

    def test_budget_exceeded_stops_and_counts(self):
        v = FakeSupportVerifier(sleep_s=0.2)
        out = gs.compute_shadow("One. Two. Three.", CLAIMABLE, v, per_job_budget_s=0.25)
        self.assertEqual(out["status"], "budget_exceeded")
        self.assertGreaterEqual(out["remaining_count"], 1)
        self.assertLess(out["shadowed_count"], 3)

    def test_verifier_error_marks_unavailable(self):
        v = FakeSupportVerifier(raises=RuntimeError("boom"))
        out = gs.compute_shadow("One.", CLAIMABLE, v)
        self.assertEqual(out["status"], "verifier_unavailable")


@dataclass
class _FakeAudit:
    text: str = "Final served text."
    rewritten: bool = False
    mode: str = "sentence"
    flags: list = field(default_factory=list)
    skipped_reason: object = None


class TelemetryTests(unittest.TestCase):
    def _compute(self):
        return gs.compute_shadow(
            "Sky is blue. Sky is green.",
            CLAIMABLE,
            FakeSupportVerifier(scripted={"Sky is green.": (UNSUPPORTED, 0.1)}),
        )

    def test_content_light_by_default(self):
        rec = gs.build_telemetry(
            "sid",
            123,
            "telegram",
            "boot1",
            gs.audit_summary_from_result(_FakeAudit()),
            CLAIMABLE,
            self._compute(),
        )
        blob = repr(rec)
        self.assertNotIn("Sky is blue", blob)
        self.assertNotIn("recall flip", blob)
        self.assertIn("sentence_hash", rec["sentences"][0])
        self.assertNotIn("snippet", rec["sentences"][0])

    def test_debug_includes_bounded_snippet(self):
        rec = gs.build_telemetry(
            "sid",
            123,
            "telegram",
            "boot1",
            gs.audit_summary_from_result(_FakeAudit()),
            CLAIMABLE,
            self._compute(),
            debug=True,
        )
        self.assertIn("snippet", rec["sentences"][0])
        self.assertLessEqual(len(rec["sentences"][0]["snippet"]), 120)

    def test_counts(self):
        rec = gs.build_telemetry(
            "sid",
            123,
            "telegram",
            "boot1",
            gs.audit_summary_from_result(_FakeAudit()),
            CLAIMABLE,
            self._compute(),
        )
        self.assertEqual(rec["sentence_count"], 2)
        self.assertEqual(rec["unsupported_count"], 1)
        self.assertEqual(rec["supported_count"], 1)
        self.assertEqual(rec["status"], "ok")

    def test_audit_summary_derives_available(self):
        self.assertTrue(
            gs.audit_summary_from_result(_FakeAudit(mode="sentence"))["audit_available"]
        )
        self.assertFalse(
            gs.audit_summary_from_result(_FakeAudit(mode="judge_unavailable"))[
                "audit_available"
            ]
        )

    def test_audit_summary_has_no_owner_text(self):
        summary = gs.audit_summary_from_result(_FakeAudit(text="secret reply"))
        self.assertNotIn("secret reply", repr(summary))


class GroundingShadowQueueTests(unittest.TestCase):
    def _shadow(self, **kwargs):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return gs.GroundingShadow(FakeSupportVerifier(), path, **kwargs), path

    def _job(self, sid="s1"):
        return {
            "final_text": "One. Two.",
            "claimable_items": CLAIMABLE,
            "audit_summary": {"mode": "sentence", "audit_available": True},
            "surface": "telegram",
            "boot_id": "b",
            "shadow_id": sid,
            "ts": 1,
        }

    def test_enqueue_returns_enqueued(self):
        shadow, _ = self._shadow(maxsize=4)
        self.assertEqual(shadow.enqueue(self._job()), "enqueued")

    def test_full_queue_returns_shadow_enqueue_failed(self):
        shadow, path = self._shadow(maxsize=1)
        self.assertEqual(shadow.enqueue(self._job("s1")), "enqueued")
        self.assertEqual(shadow.enqueue(self._job("s2")), "shadow_enqueue_failed")
        with open(path) as f:
            recs = [json.loads(line) for line in f if line.strip()]
        self.assertTrue(any(r["status"] == "shadow_enqueue_failed" for r in recs))

    def test_enqueue_never_raises(self):
        shadow, _ = self._shadow(maxsize=1)
        try:
            shadow.enqueue(self._job())
            shadow.enqueue(self._job())
        except Exception:  # noqa: BLE001
            self.fail("enqueue must never raise")

    def test_worker_processes_and_writes_telemetry(self):
        shadow, path = self._shadow(maxsize=8)
        shadow.start()
        self.addCleanup(shadow.stop)
        shadow.enqueue(self._job("done"))
        deadline = time.monotonic() + 3.0
        recs = []
        while time.monotonic() < deadline:
            if os.path.getsize(path) > 0:
                with open(path) as f:
                    recs = [json.loads(line) for line in f if line.strip()]
                if any(r.get("shadow_id") == "done" for r in recs):
                    break
            time.sleep(0.02)
        self.assertTrue(
            any(r.get("shadow_id") == "done" and r["status"] == "ok" for r in recs)
        )


if __name__ == "__main__":
    unittest.main()
