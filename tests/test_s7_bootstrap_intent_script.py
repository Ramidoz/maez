"""Owner TTY bootstrap-intent ceremony tests."""

from __future__ import annotations

from contextlib import redirect_stderr
from contextlib import redirect_stdout
from datetime import datetime
from datetime import timedelta
from pathlib import Path
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore


NOW = "2026-07-07T12:00:00+00:00"
REAL_CEREMONY_DB = Path("/home/rohit/maez/memory/s7_1_webauthn/ceremony.sqlite3")


class _InputTTY(io.StringIO):
    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        raise OSError("test tty has no file descriptor")


class _InputPipe(io.StringIO):
    def isatty(self) -> bool:
        return False


class S7BootstrapIntentScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store_root = Path(self._tmp.name) / "memory" / "s7_1_webauthn"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_cli(
        self,
        argv: list[str],
        *,
        stdin: io.StringIO,
    ) -> tuple[int, str, str]:
        from scripts import s7_bootstrap_intent

        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdin", stdin):
            with redirect_stdout(out), redirect_stderr(err):
                rc = s7_bootstrap_intent.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def _mint(self, *extra_args: str) -> tuple[int, str, str]:
        return self._run_cli(
            [
                "--store-root",
                str(self.store_root),
                "--now",
                NOW,
                *extra_args,
            ],
            stdin=_InputTTY("mint s7 primary key\n"),
        )

    def test_non_tty_input_is_refused(self):
        rc, out, err = self._run_cli(
            ["--store-root", str(self.store_root), "--now", NOW],
            stdin=_InputPipe("mint s7 primary key\n"),
        )

        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("interactive owner TTY", err)

    def test_wrong_confirmation_phrase_is_refused(self):
        rc, out, err = self._run_cli(
            ["--store-root", str(self.store_root), "--now", NOW],
            stdin=_InputTTY("wrong phrase\n"),
        )

        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("phrase mismatch", err)

    def test_overlong_expiry_is_clamped_to_ten_minutes(self):
        rc, out, err = self._mint("--expires-min", "99999")

        self.assertEqual(rc, 0, err)
        expected = datetime.fromisoformat(NOW) + timedelta(minutes=10)
        self.assertIn(f"expires_at: {expected.isoformat()}", out)
        self.assertIn("within 10 minutes", out)
        with sqlite3.connect(self.store_root / "ceremony.sqlite3") as conn:
            expires_at = conn.execute(
                "SELECT expires_at FROM s7_bootstrap_intents"
            ).fetchone()[0]
        self.assertEqual(expires_at, expected.isoformat())

    def test_minted_intent_round_trips_through_production_validator(self):
        rc, out, err = self._mint()

        self.assertEqual(rc, 0, err)
        intent_id = next(
            line.split(": ", 1)[1]
            for line in out.splitlines()
            if line.startswith("intent_id: ")
        )
        token = next(
            line.split(": ", 1)[1]
            for line in out.splitlines()
            if line.startswith("bootstrap_token: ")
        )
        expected = datetime.fromisoformat(NOW) + timedelta(minutes=5)
        self.assertIn(f"expires_at: {expected.isoformat()}", out)
        self.assertIn("within 5 minutes", out)
        store = S7WebAuthnBootstrapStore(self.store_root)

        self.assertTrue(
            store.bootstrap_intent_valid(
                intent_id=intent_id,
                raw_token=token,
                now=NOW,
            )
        )

    def test_expired_intent_is_reported_invalid_by_production_validator(self):
        store = S7WebAuthnBootstrapStore(self.store_root)
        intent = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=5,
            now=NOW,
            effective_uid=os.getuid(),
            is_interactive=True,
            tty_path="/dev/pts/test",
            token_bytes=b"x" * 32,
        )
        after_expiry = (datetime.fromisoformat(NOW) + timedelta(minutes=6)).isoformat()

        self.assertFalse(
            store.bootstrap_intent_valid(
                intent_id=intent.intent_id,
                raw_token=intent.raw_token,
                now=after_expiry,
            )
        )

    def test_audit_line_is_append_only_and_content_light(self):
        rc1, out1, err1 = self._mint()
        self.assertEqual(rc1, 0, err1)
        token = next(
            line.split(": ", 1)[1]
            for line in out1.splitlines()
            if line.startswith("bootstrap_token: ")
        )
        audit_path = self.store_root / "ceremony.audit.jsonl"
        first_lines = audit_path.read_text(encoding="utf-8").splitlines()
        store = S7WebAuthnBootstrapStore(self.store_root)
        row = json.loads(first_lines[-1])

        store.revoke_bootstrap_intent(
            row["intent_id"],
            now=NOW,
            effective_uid=os.getuid(),
        )
        rc2, _out2, err2 = self._mint()
        self.assertEqual(rc2, 0, err2)
        second_lines = audit_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(second_lines[: len(first_lines)], first_lines)
        self.assertGreater(len(second_lines), len(first_lines))
        self.assertEqual(row["event"], "bootstrap_intent_created")
        self.assertEqual(row["purpose"], "register_primary")
        self.assertNotIn(token, first_lines[-1])
        self.assertNotIn("bootstrap_token", first_lines[-1])
        self.assertNotIn("raw_token", first_lines[-1])

    def test_real_ceremony_sqlite_is_untouched_by_temp_store_cli(self):
        before = _sha256_or_missing(REAL_CEREMONY_DB)

        rc, _out, err = self._mint()

        self.assertEqual(rc, 0, err)
        self.assertEqual(_sha256_or_missing(REAL_CEREMONY_DB), before)


def _sha256_or_missing(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
