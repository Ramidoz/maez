"""Phase 5.B — behavioral regression tests for the audit's blocker
and major findings that were fixed in Batches A–E (Phase 1.G).

One test per fix. If the underlying bug regresses, exactly one named
test breaks and names the finding it corresponds to.

Covered here:
  07-B1  soul_loader.append_to_local concurrent-write race
  05-B1  cognition_quality ring-buffer rollback on exception
  07-M1  temperament first-event log renders "NULL" (not "nan")
  10-B1  fast_backend_router distinguishes policy-deny from outage
  02-B1  decision_pipeline survives a card that raced to terminal

Not covered (explicitly deferred):
  02-M2  _SyntheticCls audit_request_id — belt-and-suspenders plumbing
         with no current caller that reads cls.audit_request_id.
  06-M1  destructive_snapshot errors-list check — would require a
         filesystem-fault harness that's worth its own work.
  10-M2  fast_backend_local backend-awareness probe — exercises real
         HTTP probes; kept as a Phase 5 extension rather than a unit.
"""
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


# ─────────────────────────────────────────────────────────────────────
#  07-B1 — soul_loader append_to_local race
# ─────────────────────────────────────────────────────────────────────
class SoulLoaderConcurrentAppendTest(unittest.TestCase):
    """Two threads appending concurrently must both land in the file.

    Pre-fix: the read of `existing` happened outside the lock, so
    thread A's contribution could be silently overwritten by thread B.
    """

    def test_concurrent_appends_preserve_both_writes(self):
        from core.evolution import soul_loader

        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "soul.local.md"
            local.write_text("seed\n")

            # Point soul_loader's paths.soul_local_path() at our tmp
            # file for the duration of the test.
            with patch("core.evolution.soul_loader.paths.soul_local_path",
                        return_value=local):

                barrier = threading.Barrier(2)
                results: list[str] = []

                def worker(tag: str):
                    barrier.wait()   # maximise contention
                    soul_loader.append_to_local(f"[{tag}]")
                    results.append(tag)

                t1 = threading.Thread(target=worker, args=("A",))
                t2 = threading.Thread(target=worker, args=("B",))
                t1.start(); t2.start()
                t1.join(5); t2.join(5)

                final = local.read_text()

            self.assertIn("seed", final,
                           "original content must be preserved")
            self.assertIn("[A]", final,
                           "worker A's append got clobbered — race regressed")
            self.assertIn("[B]", final,
                           "worker B's append got clobbered — race regressed")


# ─────────────────────────────────────────────────────────────────────
#  05-B1 — cognition_quality ring-buffer rollback
# ─────────────────────────────────────────────────────────────────────
class CognitionRingBufferRollbackTest(unittest.TestCase):
    """If classify() succeeds but score() raises, the ring buffers must
    stay at their pre-call length. Pre-fix they desynced, corrupting
    fixation detection on every subsequent turn."""

    def test_exception_rolls_buffers_back(self):
        from core.cognition import cognition_quality as cq

        # Isolate the module-level buffers for this test.
        with patch.object(cq, "_recent_topics", []), \
             patch.object(cq, "_recent_scores", []), \
             patch.object(cq, "_recent_labels", []), \
             patch.object(cq, "classify", return_value={
                 "topic": "t1", "primary": "p", "labels": ["l"],
                 "topics": ["t1"],
             }), \
             patch.object(cq, "score",
                           side_effect=RuntimeError("boom")):

            result = cq.score_and_classify("anything")

            # Fallback result sentinel.
            self.assertEqual(result["cog_score"], 50)
            self.assertEqual(result["cog_primary"], "unknown")

            # Buffers must still be empty — no partial append survived.
            self.assertEqual(len(cq._recent_topics), 0,
                              "topics buffer was not rolled back")
            self.assertEqual(len(cq._recent_scores), 0,
                              "scores buffer was not rolled back")
            self.assertEqual(len(cq._recent_labels), 0,
                              "labels buffer was not rolled back")


# ─────────────────────────────────────────────────────────────────────
#  07-M1 — temperament log renders NULL not nan on first event
# ─────────────────────────────────────────────────────────────────────
class TemperamentNullLogFormatTest(unittest.TestCase):
    """The log line that fires on a first-event write (prior is None)
    must format the prior as 'NULL', not the literal 'nan'.

    Source-level check: the logger call lives inside a db-writing
    method whose full harness isn't worth constructing just to assert
    on a format string. If the format reverts, grepping the source
    catches it.
    """

    def test_source_uses_null_not_nan_for_missing_prior(self):
        import inspect
        from core.evolution import temperament
        src = inspect.getsource(temperament)
        self.assertIn('"NULL"', src,
                       "temperament.py should render missing prior as NULL; "
                       "the 07-M1 fix appears to have reverted")
        self.assertNotIn('float("nan")', src,
                          "temperament.py still emits float(\"nan\") in a log; "
                          "the 07-M1 fix has regressed")


# ─────────────────────────────────────────────────────────────────────
#  10-B1 — fast_backend_router policy_denied flag
# ─────────────────────────────────────────────────────────────────────
class BackendRouterPolicyDeniedTest(unittest.TestCase):
    """When policy forbids cloud *and* local is down, BackendSelection
    must mark policy_denied=True so callers can distinguish from a
    plain local-outage case."""

    def _policy(self, effective, allow_cloud, downgraded=False):
        from core.routing import fast_backend_router as r
        return r.PolicyDecision(
            trust_scope="test",
            rule_fired="external_guests_local_only",
            requested_policy=effective,
            effective_policy=effective,
            allow_cloud=allow_cloud,
            downgraded=downgraded,
            reasons=["policy test"],
        )

    def test_cloud_explicit_with_policy_deny_sets_flag(self):
        from core.routing import fast_backend_router as r
        sel = r.select_backend(self._policy(r.POLICY_CLOUD, allow_cloud=False))
        self.assertIsNone(sel.backend,
                           "cloud-forbidden should yield no backend")
        self.assertTrue(sel.policy_denied,
                         "policy_denied must be True when policy forbids cloud")

    def test_auto_with_local_down_and_policy_deny_sets_flag(self):
        from core.routing import fast_backend_router as r
        # Force local.is_available() to False so we reach the fall-through
        # branch of select_backend.
        with patch("core.routing.fast_backend_router._local") as mlocal:
            mlocal.return_value.is_available.return_value = False
            sel = r.select_backend(
                self._policy(r.POLICY_AUTO, allow_cloud=False, downgraded=True)
            )
        self.assertIsNone(sel.backend)
        self.assertTrue(sel.policy_denied,
                         "auto + local-down + cloud-forbidden must "
                         "mark policy_denied=True")

    def test_successful_local_does_not_set_policy_denied(self):
        """Sanity inverse: a healthy local selection should not be flagged."""
        from core.routing import fast_backend_router as r
        with patch("core.routing.fast_backend_router._local") as mlocal:
            mlocal.return_value.is_available.return_value = True
            mlocal.return_value.name = "local-test"
            sel = r.select_backend(self._policy(r.POLICY_LOCAL, allow_cloud=True))
        self.assertIsNotNone(sel.backend)
        self.assertFalse(sel.policy_denied,
                          "healthy local select should not set policy_denied")


# ─────────────────────────────────────────────────────────────────────
#  02-B1 — decision_pipeline survives an already-terminal card
# ─────────────────────────────────────────────────────────────────────
class DecisionPipelineTerminalCardTest(unittest.TestCase):
    """If a racing path terminates the card between the will-I check and
    mark_running (or between mark_running and mark_done/mark_failed),
    the pipeline must catch CardStoreError rather than let it propagate.

    Source-level check: constructing a full DecisionPipeline with every
    collaborator stubbed is fragile and tightly couples the test to
    internal construction. The regression is shape-level — if the
    except-CardStoreError handlers disappear, the code can't survive
    the race at all. A grep-based assertion catches removal without
    pretending to exercise the full path.
    """

    def test_on_approve_catches_cardstoreerror_on_mark_transitions(self):
        import inspect
        from core.decision import decision_pipeline as dp
        src = inspect.getsource(dp)

        # The 02-B1 fix added three try/except CardStoreError blocks
        # around mark_running / mark_done / mark_failed. Count them —
        # if any disappear, regression.
        self.assertGreaterEqual(
            src.count("except CardStoreError"), 3,
            "decision_pipeline should catch CardStoreError around "
            "mark_running / mark_done / mark_failed (02-B1 fix); "
            "fewer than 3 handlers found",
        )
        # And the explanatory comment tag shouldn't vanish either.
        self.assertIn("02-B1", src,
                       "02-B1 comment tag missing — the commented rationale "
                       "for the race handling was removed")


if __name__ == "__main__":
    unittest.main()
