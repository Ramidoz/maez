# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Timeout contract for core.routing.llm_client.generate.

The proposal worker uses generate() for background LLM calls. A timeout_s
argument that is ignored is a daemon-survivability bug: the worker can sit
inside a backend call far longer than the caller intended.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


class GenerateTimeoutTests(unittest.TestCase):
    def test_ollama_generate_honors_timeout_s(self):
        from core.routing import llm_client

        fake_client = MagicMock()
        fake_client.generate.return_value = {"response": "ok"}

        with patch.dict(os.environ, {"MAEZ_LLM_BACKEND": "ollama"}), \
                patch("ollama.Client", return_value=fake_client) as client_cls:
            out = llm_client.generate("hello", timeout_s=12.5)

        self.assertEqual(out, "ok")
        client_cls.assert_called_once()
        self.assertEqual(client_cls.call_args.kwargs.get("timeout"), 12.5)
        fake_client.generate.assert_called_once()

    def test_llamacpp_generate_forwards_timeout_s(self):
        from core.routing import llm_client

        fake_resp = MagicMock()
        fake_resp.message.content = "ok"

        with patch.dict(os.environ, {"MAEZ_LLM_BACKEND": "llamacpp"}), \
                patch.object(llm_client, "_chat_llamacpp",
                             return_value=fake_resp) as chat:
            out = llm_client.generate("hello", timeout_s=7.0)

        self.assertEqual(out, "ok")
        self.assertEqual(chat.call_args.kwargs.get("timeout_s"), 7.0)


if __name__ == "__main__":
    unittest.main()
