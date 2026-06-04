# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""GitHub Limb covenant guards — token-never-leaks, no-egress/LLM, persists-nothing."""

from __future__ import annotations

import ast
import logging
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.information_limb import github_limb  # noqa: E402

_LIMB_SRC = (_REPO / "core" / "information_limb" / "github_limb.py").read_text(encoding="utf-8")
SENTINEL = "SENTINEL_GH_TOKEN_LEAK_CANARY"


class TokenNeverLeaksTests(unittest.TestCase):
    def test_token_absent_from_logs_and_health(self):
        os.environ[github_limb.GITHUB_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, github_limb.GITHUB_HANDOFF_TOKEN_ENV, None)
        records: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = records.append  # type: ignore[method-assign]
        root = logging.getLogger()
        prev_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.setLevel, prev_level)
        self.addCleanup(root.removeHandler, handler)

        limb = github_limb.GithubLimb()
        with mock.patch.object(github_limb, "fetch_identity", return_value="available"):
            tile, _ = github_limb.handle_handoff(
                headers={github_limb.GITHUB_HANDOFF_HEADER: "GOODSECRET"},
                body_loader=lambda: {"access_token": SENTINEL, "scopes": ["read:user"]},
                limb=limb,
            )
        blob = repr(tile) + "\n".join(r.getMessage() for r in records)
        self.assertNotIn(SENTINEL, blob)


class NoEgressNoLLMTests(unittest.TestCase):
    def test_limb_imports_no_cloud_egress_or_llm_modules(self):
        tree = ast.parse(_LIMB_SRC)
        banned = ("llm_client", "subscription_proxy", "egress.gate", "cloud_redactor",
                  "claude_tier", "openai", "anthropic")
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                # check BOTH module path AND imported names
                if node.module:
                    imported.append(node.module)
                imported += [a.name for a in node.names]
        for mod in imported:
            for b in banned:
                self.assertNotIn(b, mod, f"github_limb must not import {mod}")


class PersistsNothingTests(unittest.TestCase):
    def test_no_durable_writes(self):
        self.assertNotIn("sqlite3", _LIMB_SRC)
        tree = ast.parse(_LIMB_SRC)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
                for a in node.args[1:2]:
                    if isinstance(a, ast.Constant):
                        self.assertNotIn("w", str(a.value))
                        self.assertNotIn("a", str(a.value))


if __name__ == "__main__":
    unittest.main()
