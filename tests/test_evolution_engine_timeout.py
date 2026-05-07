# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Proposal-worker LLM timeout contract.

The proposal worker is background work. It must not ask the local backend
for multi-minute or unbounded generations during daemon operation.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


class ProposalIntentTimeoutTests(unittest.TestCase):
    def test_intent_call_uses_bounded_default_timeout(self):
        from skills import evolution_engine as ee

        with patch.dict(os.environ, {}, clear=False), \
                patch("core.llm_client.generate",
                      return_value='{"target_name":"X"}') as gen:
            ee._call_ollama_for_intent("prompt")

        timeout = gen.call_args.kwargs.get("timeout_s")
        self.assertIsNotNone(timeout)
        self.assertLessEqual(float(timeout), 60.0)

    def test_intent_timeout_env_override(self):
        from skills import evolution_engine as ee

        with patch.dict(os.environ, {"MAEZ_PROPOSAL_INTENT_TIMEOUT_S": "9.5"}), \
                patch("core.llm_client.generate",
                      return_value='{"target_name":"X"}') as gen:
            ee._call_ollama_for_intent("prompt")

        self.assertEqual(gen.call_args.kwargs.get("timeout_s"), 9.5)

    def test_generate_patch_intent_timeout_is_terminal_without_retry(self):
        from skills import evolution_engine as ee

        editable = [{
            "name": "SCORE_WEIGHT_GROUNDING",
            "type": "int",
            "current_value": 20,
            "lineno": 1,
            "target_rank": 1,
        }]

        with patch.object(ee, "_call_ollama_for_intent",
                          return_value=("__TIMEOUT__", None)) as call:
            with self.assertRaises(ee.ProposalIntentTimeout):
                ee._generate_patch_intent("weakness", {}, editable)

        self.assertEqual(call.call_count, 1)

    def test_worker_marks_intent_timeout_failed_not_pending(self):
        from skills import evolution_engine as ee

        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "evolution_track.db")
            with patch.object(ee, "EVOLUTION_DB", db_path):
                ee._init_rail_schema()
                job_id = ee.enqueue_proposal_job(
                    "weakness",
                    {"dominant_failure_mode": "weak_retrieval"},
                    "cooldown-key",
                )
                self.assertIsNotNone(job_id)

                editable = [{
                    "name": "SCORE_WEIGHT_GROUNDING",
                    "type": "int",
                    "current_value": 20,
                    "lineno": 1,
                    "target_rank": 1,
                }]
                with patch.object(ee, "_extract_editable_targets", return_value=editable), \
                        patch.object(ee, "_generate_patch_intent",
                                     side_effect=ee.ProposalIntentTimeout(
                                         "proposal intent LLM timed out"
                                     )), \
                        patch.object(ee, "_log_evolution"):
                    ee._worker_tick()

                with sqlite3.connect(db_path) as conn:
                    state, attempts, error = conn.execute(
                        "SELECT state, attempt_count, last_error FROM proposal_jobs WHERE id=?",
                        (job_id,),
                    ).fetchone()

        self.assertEqual(state, "failed")
        self.assertEqual(attempts, 1)
        self.assertIn("proposal intent LLM timed out", error)


if __name__ == "__main__":
    unittest.main()
