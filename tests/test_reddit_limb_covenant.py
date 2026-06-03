# tests/test_reddit_limb_covenant.py
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

from core.information_limb import reddit_limb  # noqa: E402

_LIMB_SRC = (_REPO / "core" / "information_limb" / "reddit_limb.py").read_text(encoding="utf-8")
SENTINEL = "SENTINEL_TOKEN_LEAK_CANARY"


class TokenNeverLeaksTests(unittest.TestCase):
    def test_token_absent_from_logs_and_health(self):
        os.environ[reddit_limb.REDDIT_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, reddit_limb.REDDIT_HANDOFF_TOKEN_ENV, None)
        limb = reddit_limb.RedditLimb()
        with self.assertLogs(level="DEBUG") as logs:
            logging.getLogger("maez").debug("driving handoff")
            with mock.patch.object(reddit_limb, "fetch_identity", return_value="available"):
                tile, _ = reddit_limb.handle_handoff(
                    headers={reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"},
                    body_loader=lambda: {"access_token": SENTINEL, "scopes": ["identity"]},
                    limb=limb,
                )
        blob = repr(tile) + "\n".join(logs.output)
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
                # check BOTH the module path AND the imported names, so
                # `from core.routing import llm_client` is caught (the name is
                # banned even though the module path "core.routing" is not).
                if node.module:
                    imported.append(node.module)
                imported += [a.name for a in node.names]
        for mod in imported:
            for b in banned:
                self.assertNotIn(b, mod, f"reddit_limb must not import {mod}")


class PersistsNothingTests(unittest.TestCase):
    def test_no_durable_writes(self):
        # no sqlite, no file-open-for-write in the limb — session is memory-only
        self.assertNotIn("sqlite3", _LIMB_SRC)
        tree = ast.parse(_LIMB_SRC)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
                modes = [a.value for a in node.args[1:2] if isinstance(a, ast.Constant)]
                for m in modes:
                    self.assertNotIn("w", str(m), "reddit_limb must not open files for writing")
                    self.assertNotIn("a", str(m), "reddit_limb must not append to files")


if __name__ == "__main__":
    unittest.main()
