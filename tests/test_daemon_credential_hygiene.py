"""Credential-hygiene contract for Decision 26 / ADR 0031.

Tests use synthetic paths and fake values only. They must never read or print
the operator's real credential files.
"""

from __future__ import annotations

import os
import ast
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


class TestSecretLoader(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.config = self.root / "config"
        self.config.mkdir()
        self.fallback = self.config / "secrets.local.env"
        self.creds = self.root / "creds"
        self.creds.mkdir()

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_source_priority_systemd_wins_and_fallback_fills_missing(self):
        from core.infra.secrets import load_secrets_for_process

        (self.creds / "MAEZ_TELEGRAM_TOKEN").write_text("systemd-token\n")
        self.fallback.write_text(
            "MAEZ_TELEGRAM_TOKEN=fallback-token\n"
            "ANTHROPIC_API_KEY=fallback-anthropic\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"CREDENTIALS_DIRECTORY": str(self.creds)}, clear=True):
            report = load_secrets_for_process(
                required={"MAEZ_TELEGRAM_TOKEN"},
                optional={"ANTHROPIC_API_KEY"},
                fallback_file=self.fallback,
                populate_environ=False,
            )

        self.assertEqual(report.source, "mixed")
        self.assertEqual(report.loaded_count, 2)
        self.assertEqual(report.get_secret("MAEZ_TELEGRAM_TOKEN"), "systemd-token")
        self.assertEqual(report.get_secret("ANTHROPIC_API_KEY"), "fallback-anthropic")

    def test_fallback_source_loads_without_systemd_credentials(self):
        from core.infra.secrets import load_secrets_for_process

        self.fallback.write_text("MAEZ_TELEGRAM_TOKEN=fallback-token\n", encoding="utf-8")

        with patch.dict(os.environ, {}, clear=True):
            report = load_secrets_for_process(
                required={"MAEZ_TELEGRAM_TOKEN"},
                optional=set(),
                fallback_file=self.fallback,
                populate_environ=False,
            )

        self.assertEqual(report.source, "secrets-local-env")
        self.assertEqual(report.get_secret("MAEZ_TELEGRAM_TOKEN"), "fallback-token")

    def test_malformed_fallback_rejected(self):
        from core.infra.secrets import SecretLoadError, load_secrets_for_process

        cases = [
            "MAEZ_TELEGRAM_TOKEN=one\nMAEZ_TELEGRAM_TOKEN=two\n",
            "not a key value line\n",
            "MAEZ_TELEGRAM_TOKEN=\n",
        ]
        for body in cases:
            with self.subTest(body=body):
                self.fallback.write_text(body, encoding="utf-8")
                with self.assertRaises(SecretLoadError):
                    load_secrets_for_process(
                        required={"MAEZ_TELEGRAM_TOKEN"},
                        optional=set(),
                        fallback_file=self.fallback,
                        populate_environ=False,
                    )

    def test_config_env_is_not_a_secret_source_but_ordinary_config_loads(self):
        from core.infra.secrets import (
            load_ordinary_config_for_process,
            load_secrets_for_process,
        )

        env_file = self.config / ".env"
        env_file.write_text(
            "MAEZ_HOME=/tmp/maez-test\n"
            "MAEZ_TELEGRAM_TOKEN=must-not-load-from-dotenv\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {}, clear=True):
            loaded = load_ordinary_config_for_process(env_file=env_file)
            report = load_secrets_for_process(
                required=set(),
                optional={"MAEZ_TELEGRAM_TOKEN"},
                fallback_file=self.fallback,
                populate_environ=False,
            )
            self.assertEqual(os.environ.get("MAEZ_HOME"), "/tmp/maez-test")
            self.assertIsNone(os.environ.get("MAEZ_TELEGRAM_TOKEN"))

        self.assertEqual(loaded, {"MAEZ_HOME"})
        self.assertEqual(report.source, "none")
        self.assertEqual(report.loaded_count, 0)

    def test_required_missing_fails_with_name_only(self):
        from core.infra.secrets import SecretLoadError, load_secrets_for_process

        with self.assertRaises(SecretLoadError) as cm:
            load_secrets_for_process(
                required={"MAEZ_TELEGRAM_TOKEN"},
                optional=set(),
                fallback_file=self.fallback,
                populate_environ=False,
            )

        msg = str(cm.exception)
        self.assertIn("MAEZ_TELEGRAM_TOKEN", msg)
        self.assertNotIn("=", msg)

    def test_optional_absent_does_not_fail_and_compatibility_population_works(self):
        from core.infra.secrets import load_secrets_for_process

        self.fallback.write_text("MAEZ_TELEGRAM_TOKEN=fallback-token\n", encoding="utf-8")

        with patch.dict(os.environ, {}, clear=True):
            report = load_secrets_for_process(
                required={"MAEZ_TELEGRAM_TOKEN"},
                optional={"MAEZ_GITHUB_TOKEN"},
                fallback_file=self.fallback,
                populate_environ=True,
            )
            self.assertEqual(os.environ.get("MAEZ_TELEGRAM_TOKEN"), "fallback-token")
            self.assertIsNone(os.environ.get("MAEZ_GITHUB_TOKEN"))

        self.assertEqual(report.missing_required_count, 0)
        self.assertEqual(report.missing_optional_count, 1)

    def test_s7_internal_channel_token_is_managed_secret_from_local_fallback(self):
        from core.infra.secrets import SECRET_NAMES, is_secret_name, load_secrets_for_process

        self.assertTrue(is_secret_name("S7_INTERNAL_CHANNEL_TOKEN"))
        self.assertIn("S7_INTERNAL_CHANNEL_TOKEN", SECRET_NAMES)
        self.fallback.write_text(
            "S7_INTERNAL_CHANNEL_TOKEN=managed-s7-token\n",
            encoding="utf-8",
        )

        with patch.dict(
            os.environ,
            {"S7_INTERNAL_CHANNEL_TOKEN": "launch-env-token-must-not-survive"},
            clear=True,
        ):
            report = load_secrets_for_process(
                required=set(),
                optional=set(SECRET_NAMES),
                fallback_file=self.fallback,
                populate_environ=True,
            )
            self.assertEqual(os.environ.get("S7_INTERNAL_CHANNEL_TOKEN"), "managed-s7-token")

        self.assertEqual(report.get_secret("S7_INTERNAL_CHANNEL_TOKEN"), "managed-s7-token")

    def test_normal_loader_purges_inherited_legacy_secret_env(self):
        from core.infra.secrets import load_secrets_for_process

        self.fallback.write_text("MAEZ_TELEGRAM_TOKEN=fallback-token\n", encoding="utf-8")

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "legacy-env-must-not-survive",
                "PATH": "/bin",
            },
            clear=True,
        ):
            report = load_secrets_for_process(
                required={"MAEZ_TELEGRAM_TOKEN"},
                optional={"ANTHROPIC_API_KEY"},
                fallback_file=self.fallback,
                populate_environ=True,
            )
            self.assertEqual(os.environ.get("MAEZ_TELEGRAM_TOKEN"), "fallback-token")
            self.assertNotIn("ANTHROPIC_API_KEY", os.environ)

        self.assertIsNone(report.get_secret("ANTHROPIC_API_KEY"))

    def test_rollback_flag_can_read_restored_legacy_config_env(self):
        from core.infra import paths
        from core.infra.secrets import load_secrets_for_process

        legacy_env = self.config / ".env"
        legacy_env.write_text("MAEZ_TELEGRAM_TOKEN=legacy-rollback-token\n", encoding="utf-8")

        with (
            patch.object(paths, "env_file", return_value=legacy_env),
            patch.dict(os.environ, {"MAEZ_SECRETS_DISABLE_NEW_LOADER": "1"}, clear=True),
        ):
            report = load_secrets_for_process(
                required={"MAEZ_TELEGRAM_TOKEN"},
                optional=set(),
                fallback_file=self.fallback,
                populate_environ=True,
            )
            self.assertEqual(os.environ.get("MAEZ_TELEGRAM_TOKEN"), "legacy-rollback-token")

        self.assertEqual(report.source, "legacy-env")
        self.assertTrue(report.rollback_enabled)

    def test_health_and_log_surface_are_aggregate_only(self):
        from core.infra.secrets import load_secrets_for_process

        self.fallback.write_text("MAEZ_TELEGRAM_TOKEN=fallback-token\n", encoding="utf-8")
        report = load_secrets_for_process(
            required={"MAEZ_TELEGRAM_TOKEN"},
            optional={"MAEZ_GITHUB_TOKEN"},
            fallback_file=self.fallback,
            populate_environ=False,
        )

        health = report.health()
        log_line = report.source_log_line()
        self.assertEqual(health["source"], "secrets-local-env")
        self.assertEqual(health["required_present"], True)
        self.assertEqual(health["optional_loaded_count"], 0)
        self.assertNotIn("MAEZ_TELEGRAM_TOKEN", repr(health))
        self.assertNotIn("fallback-token", repr(health))
        self.assertNotIn("MAEZ_TELEGRAM_TOKEN", log_line)
        self.assertNotIn("fallback-token", log_line)


class TestSanitizedEnvironment(unittest.TestCase):
    def test_default_sanitized_env_removes_secret_shaped_names_and_keeps_basics(self):
        from core.infra.secrets import sanitize_env

        base = {
            "PATH": "/bin",
            "HOME": "/home/test",
            "MAEZ_HOME": "/tmp/maez",
            "DISPLAY": ":1",
            "SSH_AUTH_SOCK": "/tmp/ssh",
            "MAEZ_TELEGRAM_TOKEN": "fake-token",
            "ANTHROPIC_API_KEY": "fake-key",
            "NOT_A_SECRET": "remove-me-too",
            "CREDENTIAL_PATH": "remove",
        }

        env = sanitize_env(base)
        self.assertEqual(env["PATH"], "/bin")
        self.assertEqual(env["HOME"], "/home/test")
        self.assertEqual(env["MAEZ_HOME"], "/tmp/maez")
        self.assertEqual(env["DISPLAY"], ":1")
        self.assertNotIn("MAEZ_TELEGRAM_TOKEN", env)
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("NOT_A_SECRET", env)
        self.assertNotIn("CREDENTIAL_PATH", env)

    def test_exact_secret_opt_in_passes_one_name_only(self):
        from core.infra.secrets import sanitize_env

        base = {
            "MAEZ_GITHUB_TOKEN": "allowed-fake",
            "ANTHROPIC_API_KEY": "blocked-fake",
        }
        env = sanitize_env(base, allow={"MAEZ_GITHUB_TOKEN"})
        self.assertEqual(env["MAEZ_GITHUB_TOKEN"], "allowed-fake")
        self.assertNotIn("ANTHROPIC_API_KEY", env)


class TestProcAndScanner(unittest.TestCase):
    def test_runtime_assignment_not_visible_in_proc_environ_on_this_host(self):
        script = textwrap.dedent(
            """
            import os
            import sys
            name = "MAEZ_PROC_REGRESSION_TOKEN"
            os.environ[name] = "proc-regression-fake-value"
            data = open(f"/proc/{os.getpid()}/environ", "rb").read()
            sys.exit(1 if name.encode() in data else 0)
            """
        )
        proc = subprocess.run([sys.executable, "-c", script], timeout=5)
        self.assertEqual(
            proc.returncode,
            0,
            "Runtime os.environ assignments are visible in /proc; v1 compatibility exposure claim is invalid.",
        )

    def test_pattern_scanner_catches_realistic_fake_and_allows_fixture(self):
        from core.infra.secrets import find_secret_pattern_hits

        bad = "token=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabc"
        ok = "fixture token sk-lf-test is intentionally allowed"
        self.assertTrue(find_secret_pattern_hits(bad))
        self.assertEqual(find_secret_pattern_hits(ok), [])

    def test_fixture_allowlist_does_not_mask_embedded_realistic_tokens(self):
        from core.infra.secrets import find_secret_pattern_hits

        embedded = "token sk-lf-test-THISPARTMAKESITLOOKLIKEAREALTOKEN"
        self.assertTrue(find_secret_pattern_hits(embedded))


class TestRepoPosture(unittest.TestCase):
    def test_gitignore_ignores_local_secret_file(self):
        text = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("config/secrets.local.env", text)

    def test_backup_manifest_covers_local_secret_file_as_secret_file(self):
        text = Path("scripts/backup/backup_state_manifest.json").read_text(encoding="utf-8")
        self.assertIn('"type": "secret_file"', text)
        self.assertIn('"path": "config/secrets.local.env"', text)

    def test_service_templates_do_not_describe_config_env_as_token_storage(self):
        for path in [
            Path("scripts/maez.template.service"),
            Path("scripts/maez-subscription-proxy.service"),
            Path("scripts/maez-subscription-proxy.template.service"),
            Path("scripts/maez-lived-memory-reflection.service"),
            Path("scripts/maez-self-dev-scheduled.service"),
            Path("scripts/maez-self-dev-scheduled.template.service"),
        ]:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"EnvironmentFile=.*config/\.env")
            self.assertNotIn("holds tokens", text)
            self.assertNotIn("API_KEY", text)
            self.assertNotIn("SetCredential=", text)

    def test_web_interface_requires_iphone_ingest_token_at_startup(self):
        text = Path("skills/web_interface.py").read_text(encoding="utf-8")
        self.assertIn('required={"MAEZ_IPHONE_INGEST_TOKEN"}', text)

    def test_web_interface_loads_s7_internal_channel_token_as_optional_secret(self):
        tree = ast.parse(Path("skills/web_interface.py").read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "load_secrets_for_process"
        ]
        self.assertEqual(len(calls), 1)
        optional_kw = next(kw for kw in calls[0].keywords if kw.arg == "optional")
        self.assertIsInstance(optional_kw.value, ast.Set)
        optional_names = {
            elt.value
            for elt in optional_kw.value.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        }
        self.assertIn("S7_INTERNAL_CHANNEL_TOKEN", optional_names)

    def test_github_publish_does_not_place_token_in_remote_url(self):
        text = Path("skills/github_publish.py").read_text(encoding="utf-8")
        self.assertNotIn("self.token}@github.com", text)
        self.assertIn("git@github.com:", text)

    def test_high_risk_daemon_subprocess_sites_use_sanitized_env_or_exception(self):
        files = {
            Path("core/actions/action_engine.py"),
            Path("core/actions/tool_loop.py"),
            Path("core/self_dev/__init__.py"),
            Path("skills/web_interface.py"),
            Path("skills/telegram_voice.py"),
            Path("skills/github_publish.py"),
        }
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = None
                if isinstance(func, ast.Attribute):
                    name = func.attr
                if name not in {"run", "Popen", "check_output", "check_call"}:
                    continue
                if not isinstance(func, ast.Attribute):
                    continue
                receiver = func.value
                if not (
                    isinstance(receiver, ast.Name)
                    and receiver.id in {"subprocess", "_sp", "_subprocess"}
                ):
                    continue
                has_env = any(kw.arg == "env" for kw in node.keywords)
                self.assertTrue(
                    has_env,
                    f"{path}:{node.lineno} subprocess.{name} must pass sanitized env",
                )

    def test_high_risk_startup_imports_do_not_call_raw_load_dotenv(self):
        files = [
            Path("daemon/maez_daemon.py"),
            Path("skills/web_interface.py"),
            Path("skills/github_skill.py"),
            Path("skills/github_publish.py"),
            Path("skills/telegram_public.py"),
            Path("skills/dynamic_dns.py"),
        ]
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("from dotenv import load_dotenv", text, str(path))
            self.assertNotIn("load_dotenv(", text, str(path))

    def test_daemon_health_exposes_credential_aggregate_only(self):
        text = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")
        self.assertIn('"credentials": _credential_health()', text)
        health_line = next(
            line for line in text.splitlines() if '"credentials": _credential_health()' in line
        )
        self.assertNotIn("MAEZ_TELEGRAM_TOKEN", health_line)

    def test_public_web_state_strips_credential_health(self):
        text = Path("skills/web_interface.py").read_text(encoding="utf-8")
        self.assertIn('daemon_health.pop("credentials", None)', text)


if __name__ == "__main__":
    unittest.main()
