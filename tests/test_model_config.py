# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.model_config — the single source of truth for which
model Maez uses.

Guarantees:
  - Env vars drive everything. No hardcoded model names in the module.
  - Swapping MAEZ_PRIMARY_MODEL via env var and calling refresh() picks
    up the new alias without restart.
  - Malformed CHAT_KWARGS JSON fails safely to an empty dict.
  - The module never raises at import.

Codebase-level invariant: no module under daemon/, skills/, core/,
cli/ should contain a hardcoded Qwen / Gemma / SuperGemma alias.
The invariant test below enforces that.
"""
from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


class ImportSafety(unittest.TestCase):

    def test_module_imports_without_env(self):
        # Fresh import in a subprocess with minimal env. Must not raise.
        env = {k: v for k, v in os.environ.items() if not k.startswith("MAEZ_")}
        result = subprocess.run(
            ["python3", "-c", "from core import model_config as mc; "
             "print(mc.PRIMARY_MODEL, mc.PRIMARY_BASE_URL, "
             "len(mc.PRIMARY_CHAT_KWARGS))"],
            capture_output=True, text=True, env=env, cwd="/home/rohit/maez",
            timeout=10,
        )
        self.assertEqual(
            result.returncode, 0,
            f"import failed: stderr={result.stderr}",
        )
        # With no env, should get the safe defaults.
        self.assertIn("primary-model", result.stdout)
        self.assertIn("127.0.0.1:8080", result.stdout)


class EnvDrivenConfig(unittest.TestCase):

    def test_primary_model_read_from_env(self):
        with patch.dict(os.environ, {
            "MAEZ_PRIMARY_MODEL": "test-model-alias-42",
            "MAEZ_PRIMARY_BASE_URL": "http://test.local:9999",
            "MAEZ_PRIMARY_CHAT_KWARGS": '{"test_kw": true}',
        }, clear=False):
            from core import model_config
            model_config.refresh()
            self.assertEqual(model_config.PRIMARY_MODEL, "test-model-alias-42")
            self.assertEqual(
                model_config.PRIMARY_BASE_URL, "http://test.local:9999",
            )
            self.assertEqual(
                model_config.PRIMARY_CHAT_KWARGS, {"test_kw": True},
            )

    def test_judge_model_read_from_env(self):
        with patch.dict(os.environ, {
            "MAEZ_JUDGE_MODEL": "some-judge",
            "MAEZ_JUDGE_BASE_URL": "http://judge.local:7777",
            "MAEZ_JUDGE_CHAT_KWARGS": '{"foo": 1}',
        }, clear=False):
            from core import model_config
            model_config.refresh()
            self.assertEqual(model_config.JUDGE_MODEL, "some-judge")
            self.assertEqual(
                model_config.JUDGE_BASE_URL, "http://judge.local:7777",
            )
            self.assertEqual(model_config.JUDGE_CHAT_KWARGS, {"foo": 1})

    def test_malformed_chat_kwargs_falls_back_to_empty(self):
        with patch.dict(os.environ, {
            "MAEZ_PRIMARY_CHAT_KWARGS": "{not valid json",
        }, clear=False):
            from core import model_config
            model_config.refresh()
            self.assertEqual(model_config.PRIMARY_CHAT_KWARGS, {})

    def test_non_object_chat_kwargs_falls_back_to_empty(self):
        with patch.dict(os.environ, {
            "MAEZ_PRIMARY_CHAT_KWARGS": '[1, 2, 3]',
        }, clear=False):
            from core import model_config
            model_config.refresh()
            self.assertEqual(model_config.PRIMARY_CHAT_KWARGS, {})

    def test_base_url_trailing_slash_stripped(self):
        with patch.dict(os.environ, {
            "MAEZ_PRIMARY_BASE_URL": "http://test/",
            "MAEZ_JUDGE_BASE_URL": "http://judge/",
        }, clear=False):
            from core import model_config
            model_config.refresh()
            self.assertEqual(model_config.PRIMARY_BASE_URL, "http://test")
            self.assertEqual(model_config.JUDGE_BASE_URL, "http://judge")


class NoHardcodedModelNamesInvariant(unittest.TestCase):
    """The whole point: swapping models should be an env-var change.
    This test scans daemon/, skills/, core/, cli/ for literal model-
    name strings — if it finds any, the refactor is incomplete.

    Allowed: test files, plans, docs, trace fixtures.
    Flagged: production .py that mentions qwen/gemma/supergemma/etc.
    """

    _FORBIDDEN_ALIASES = (
        "qwen36-35b-base", "qwen36-35b-sft", "gemma-4-26b-base",
        "supergemma-4-26b", "qwen3-vl", "gemma-4-E4B",
    )

    def test_production_modules_have_no_hardcoded_model_names(self):
        root = Path("/home/rohit/maez")
        check_dirs = ["daemon", "skills", "core", "cli"]
        offenders: list[tuple[str, str, int]] = []
        for d in check_dirs:
            for py in (root / d).rglob("*.py"):
                if "__pycache__" in py.parts or "/tests/" in str(py):
                    continue
                content = py.read_text(encoding="utf-8", errors="replace")
                for alias in self._FORBIDDEN_ALIASES:
                    for lineno, line in enumerate(
                        content.splitlines(), start=1,
                    ):
                        if alias in line:
                            # Allow mentions in comments/docstrings (they
                            # are explanatory, not hardcoded behavior).
                            stripped = line.strip()
                            is_comment = (
                                stripped.startswith("#")
                                or stripped.startswith('"""')
                                or stripped.startswith("'''")
                                or stripped.startswith("*")
                            )
                            if not is_comment:
                                offenders.append(
                                    (str(py.relative_to(root)), alias, lineno),
                                )
        self.assertEqual(
            offenders, [],
            "Production modules still contain hardcoded model aliases "
            f"(swap via env, not code): {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
