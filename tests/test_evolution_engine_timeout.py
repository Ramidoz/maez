# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Proposal-worker LLM timeout contract.

The proposal worker is background work. It must not ask the local backend
for multi-minute or unbounded generations during daemon operation.
"""
from __future__ import annotations

import os
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


if __name__ == "__main__":
    unittest.main()
