# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Owner birth ceremony script tests.

Thirteenth round: the free-string --s7-receipt-ref is dead. Every
transaction here runs against a temp S7 store holding a real, consumed
birth authorization (minted through the real ceremony service with the
established fake-verifier duck-type) — see
tests/test_birth_authorization_rail.py for the rail's own tests.
"""
from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from scripts.birth_ceremony import main, run_transaction
from tests.test_birth_authorization_rail import authorized_ceremony_fixture


def _dry_kwargs(td: Path, **kw):
    """run_transaction kwargs for an authorized dry-run in ``td``."""
    kwargs, _facts = authorized_ceremony_fixture(Path(td), **kw)
    return kwargs


def _for_real_patches(td: Path, db: Path):
    """(kwargs, facts, ExitStack) — a consumed for-real authorization
    bound to ``db``, with the canonical resolvers patched into ``td`` so
    a test never touches the real ledger/store/manifest."""
    kwargs, facts = authorized_ceremony_fixture(
        Path(td), mode="for_real", db_path=db
    )
    stack = ExitStack()
    stack.enter_context(
        mock.patch(
            "core.governance.birth_authorization.canonical_ledger_realpath",
            return_value=str(Path(db).resolve()),
        )
    )
    stack.enter_context(
        mock.patch(
            "core.governance.birth_authorization.canonical_s7_store_path",
            return_value=Path(kwargs["s7_store_path"]),
        )
    )
    stack.enter_context(
        mock.patch(
            "core.governance.birth_authorization.canonical_manifest_path",
            return_value=Path(kwargs["manifest_path"]),
        )
    )
    stack.enter_context(
        mock.patch(
            "core.governance.birth_authorization.fresh_birth_run_id",
            return_value=kwargs["run_id"],
        )
    )
    stack.enter_context(
        mock.patch(
            "scripts.birth_ceremony._mint_for_ceremony",
            return_value=facts,
        )
    )
    return kwargs, facts, stack


class BirthTransactionDryRun(unittest.TestCase):
    def test_dry_run_births_a_temp_ledger(self):
        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            db = kwargs["db_path"]
            result = run_transaction(dry_run=True, **kwargs)
            self.assertTrue(result["birth_turn_id"])
            conn = sqlite3.connect(db)
            meta = conn.execute(
                "SELECT value FROM meta WHERE key='birth_event_turn_id'"
            ).fetchone()[0]
            row = conn.execute(
                "SELECT raw_text, lifecycle_stage FROM turns WHERE turn_id=?",
                (meta,),
            ).fetchone()
            conn.close()
            self.assertEqual(meta, result["birth_turn_id"])
            payload = json.loads(row[0])
            self.assertEqual(payload["event"], "birth")
            # Resolved facts, never a caller string.
            self.assertNotIn("s7_receipt_ref", payload)
            self.assertTrue(payload["s7_artifact_id"].startswith("s7authz_"))
            self.assertEqual(payload["ceremony_run_id"], kwargs["run_id"])
            self.assertIn("s7_receipt_projection_sha256", payload)
            self.assertEqual(row[1], "gestation")  # the hinge row

    def test_double_run_refuses(self):
        from core.governance import birth_authorization as ba

        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            run_transaction(dry_run=True, **kwargs)
            # The execution marker refuses FIRST (execute-once, Codex
            # validation F3); the born-ledger refusal remains behind it.
            with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
                run_transaction(dry_run=True, **kwargs)
            self.assertEqual(ctx.exception.reason, "receipt_already_executed")

    def test_no_first_person_content_in_birth_row(self):
        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            run_transaction(dry_run=True, **kwargs)
            conn = sqlite3.connect(kwargs["db_path"])
            raw = conn.execute(
                "SELECT raw_text FROM turns WHERE turn_id != 'genesis'"
            ).fetchone()[0]
            conn.close()
            self.assertNotIn("I want", raw)
            self.assertNotIn("I feel", raw)

    def test_dry_run_without_db_path_exits_2(self):
        with mock.patch("sys.stderr") as stderr:
            self.assertEqual(main([]), 2)
        stderr.write.assert_any_call(
            "--dry-run requires --db-path (a temp path, never the real ledger)"
        )

    def test_dry_run_without_rail_paths_exits_2(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            with mock.patch("sys.stderr") as stderr:
                self.assertEqual(main(["--db-path", str(db)]), 2)
        printed = "".join(c.args[0] for c in stderr.write.call_args_list)
        self.assertIn("--s7-store-path", printed)

    def test_dry_run_refuses_default_ledger_path(self):
        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            default_db = kwargs["db_path"]
            with mock.patch(
                "scripts.birth_ceremony.birth_phase.default_ledger_path",
                return_value=default_db,
            ):
                with self.assertRaisesRegex(ValueError, "REFUSED.*real ledger"):
                    run_transaction(dry_run=True, **kwargs)
            self.assertFalse(default_db.exists())

    def test_dry_run_real_ledger_cli_exits_2(self):
        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            default_db = kwargs["db_path"]
            with mock.patch(
                "scripts.birth_ceremony.birth_phase.default_ledger_path",
                return_value=default_db,
            ), mock.patch("sys.stderr") as stderr:
                self.assertEqual(
                    main(
                        [
                            "--db-path", str(default_db),
                            "--s7-store-path", str(kwargs["s7_store_path"]),
                            "--manifest-path", str(kwargs["manifest_path"]),
                            "--run-id", kwargs["run_id"],
                        ]
                    ),
                    2,
                )
            self.assertFalse(default_db.exists())
        self.assertIn("REFUSED", "".join(c.args[0] for c in stderr.write.call_args_list))

    def test_for_real_refuses_without_interactive_tty(self):
        with mock.patch("sys.stdin.isatty", return_value=False), mock.patch(
            "sys.stderr"
        ) as stderr:
            self.assertEqual(main(["--for-real"]), 2)
        stderr.write.assert_any_call(
            "REFUSED: --for-real requires an interactive owner TTY"
        )

    def test_for_real_refuses_env_overrides_first(self):
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch.dict(
            os.environ, {"MAEZ_DATA": "/decoy"}
        ), mock.patch("sys.stderr") as stderr:
            self.assertEqual(main(["--for-real"]), 2)
        printed = "".join(c.args[0] for c in stderr.write.call_args_list)
        self.assertIn("env_override_in_for_real", printed)

    def test_for_real_refuses_rehearsal_knobs(self):
        with TemporaryDirectory() as td:
            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "sys.stderr"
            ) as stderr:
                self.assertEqual(
                    main(
                        ["--for-real", "--s7-store-path", str(Path(td) / "s")]
                    ),
                    2,
                )
        printed = "".join(c.args[0] for c in stderr.write.call_args_list)
        self.assertIn("rehearsal", printed)

    def test_for_real_refuses_noncanonical_db_path(self):
        with TemporaryDirectory() as td:
            canonical = Path(td) / "ledger.db"
            decoy = Path(td) / "decoy.db"
            with mock.patch(
                "scripts.birth_ceremony.birth_phase.default_ledger_path",
                return_value=canonical,
            ), mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "sys.stderr"
            ) as stderr:
                self.assertEqual(
                    main(["--for-real", "--db-path", str(decoy)]),
                    2,
                )
        printed = "".join(c.args[0] for c in stderr.write.call_args_list)
        self.assertIn("canonical", printed)

    def test_env_flag_restored_after_writer_construction(self):
        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            os.environ["MAEZ_LEDGER_WRITES"] = "0"
            self.addCleanup(os.environ.pop, "MAEZ_LEDGER_WRITES", None)
            run_transaction(dry_run=True, **kwargs)
            self.assertEqual(os.environ.get("MAEZ_LEDGER_WRITES"), "0")

    def test_checklist_prints_remaining_manual_steps(self):
        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            with mock.patch("sys.stdout") as stdout:
                self.assertEqual(
                    main(
                        [
                            "--db-path", str(kwargs["db_path"]),
                            "--s7-store-path", str(kwargs["s7_store_path"]),
                            "--manifest-path", str(kwargs["manifest_path"]),
                            "--run-id", kwargs["run_id"],
                        ]
                    ),
                    0,
                )
        printed = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertIn("birth transaction committed:", printed)
        self.assertIn("OWNER CHECKLIST", printed)
        self.assertIn("MAEZ_LEDGER_WRITES=1", printed)
        self.assertIn("systemctl --user restart maez.service", printed)
        self.assertIn("six live witnesses", printed)
        self.assertIn("receipts bundle", printed)


def _latch_probe(db: Path) -> bool:
    """True if someone holds the ownerlock flock for ``db`` right now.

    Probes on a separate fd (separate open-file-description), so a
    successful trial lock proves the latch is FREE; unlocking our own
    probe fd releases nothing anyone else holds.
    """
    lock = Path(f"{os.path.abspath(db)}.ownerlock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


class MaintenanceLeaseTests(unittest.TestCase):
    """Council ruling (fifth round, 3 seats + executed probes): the
    enabled writer IS the lease. It constructs FIRST — the latch is held
    continuously from before migrate.run() (an unlatched WAL writer,
    trap #4) through the birth write. No release-reacquire window
    (trap #3), no bypass parameter, no module-global registry."""

    def test_latch_is_held_while_migrate_runs(self):
        from core.ledger import migrate as migrate_mod

        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            seen: dict = {}
            orig_run = migrate_mod.run

            def probing_run(db_path):
                seen["latched_during_migrate"] = _latch_probe(Path(db_path))
                return orig_run(db_path)

            with mock.patch.object(migrate_mod, "run", side_effect=probing_run):
                run_transaction(dry_run=True, **kwargs)
            self.assertTrue(
                seen.get("latched_during_migrate"),
                "migrate.run() must execute UNDER the owner latch — "
                "lease-before-migrate is mandatory (trap #4)",
            )

    def test_latch_released_after_transaction(self):
        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            run_transaction(dry_run=True, **kwargs)
            self.assertFalse(_latch_probe(kwargs["db_path"]))


class QuiesceInsideRunTransactionTests(unittest.TestCase):
    """Trap #9: run_transaction() is importable — the quiesce must live
    inside it, not only in main()."""

    def test_for_real_transaction_quiesces_before_any_mutation(self):
        from core.ledger import migrate as migrate_mod

        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            kwargs, _facts, stack = _for_real_patches(td, db)
            order: list[str] = []
            orig_run = migrate_mod.run

            def recording_migrate(db_path):
                order.append("migrate")
                return orig_run(db_path)

            with stack, mock.patch.object(
                migrate_mod, "run", side_effect=recording_migrate
            ):
                run_transaction(
                    dry_run=False,
                    quiesce=lambda path: order.append("quiesce"),
                    **kwargs,
                )
            self.assertEqual(
                order[:2],
                ["quiesce", "migrate"],
                "the importable path must quiesce BEFORE mutating anything",
            )

    def test_dry_run_does_not_quiesce(self):
        called: list = []
        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            run_transaction(
                dry_run=True,
                quiesce=lambda path: called.append(path),
                **kwargs,
            )
        self.assertEqual(called, [], "dry runs on temp dbs never touch systemd")


class CommitClassificationTests(unittest.TestCase):
    """Codex seat, verified: is_born() maps missing/unreadable/corrupt
    to False — it cannot classify commit status. Only a readable, intact
    db with no anchor proves NOT_COMMITTED; failures are UNKNOWN."""

    def test_empty_file_is_not_committed(self):
        from scripts.birth_ceremony import classify_commit

        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            db.touch()
            self.assertEqual(classify_commit(db), "NOT_COMMITTED")

    def test_migrated_unborn_is_not_committed(self):
        from core.ledger import migrate
        from scripts.birth_ceremony import classify_commit

        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            migrate.run(str(db))
            self.assertEqual(classify_commit(db), "NOT_COMMITTED")

    def test_birthed_ledger_is_committed(self):
        from scripts.birth_ceremony import classify_commit

        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            run_transaction(dry_run=True, **kwargs)
            self.assertEqual(classify_commit(kwargs["db_path"]), "COMMITTED")

    def test_garbage_file_is_unknown_never_not_committed(self):
        from scripts.birth_ceremony import classify_commit

        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            db.write_bytes(b"this is not a sqlite database, at all....")
            self.assertEqual(
                classify_commit(db), "UNKNOWN",
                "corruption must never classify as NOT_COMMITTED — that "
                "mislabel is what authorizes an unsafe restart",
            )


class FakeSystemctl:
    """Scriptable systemctl/pgrep/fuser runner for choreography tests."""

    def __init__(self, unit_states: dict[str, str] | None = None):
        self.unit_states = dict(unit_states or {})
        self.calls: list[list[str]] = []
        self.bus_down = False

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if cmd[0] == "systemctl":
            if self.bus_down:
                return subprocess.CompletedProcess(
                    cmd, 1, stdout="", stderr="Failed to connect to bus"
                )
            verb = cmd[2]
            unit = cmd[3] if len(cmd) > 3 else ""
            if verb == "is-active":
                state = self.unit_states.get(unit, "inactive")
                return subprocess.CompletedProcess(
                    cmd, 0 if state == "active" else 3, stdout=state + "\n",
                    stderr="",
                )
            if verb == "stop":
                self.unit_states[unit] = "inactive"
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            if verb == "start":
                self.unit_states[unit] = self.unit_states.get(
                    f"{unit}:on_start", "active"
                )
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            if verb == "reset-failed":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[0] == "pgrep":
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        if cmd[0] == "fuser":
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


class UnitStateHonestyTests(unittest.TestCase):
    """Trap #10 + Grok seat: a dead user bus must REFUSE, never read as
    'inactive' — empty stdout comparing != 'active' silently passes the
    old quiesce probe."""

    def test_bus_down_refuses_instead_of_reading_inactive(self):
        from scripts.birth_ceremony import _unit_active_state

        runner = FakeSystemctl()
        runner.bus_down = True
        with self.assertRaisesRegex(RuntimeError, "(?i)bus|determine"):
            _unit_active_state("maez.service", runner=runner)

    def test_inactive_and_active_parse(self):
        from scripts.birth_ceremony import _unit_active_state

        runner = FakeSystemctl({"maez.service": "active"})
        self.assertEqual(
            _unit_active_state("maez.service", runner=runner), "active"
        )
        self.assertEqual(
            _unit_active_state("maez-web.service", runner=runner), "inactive"
        )


class QuiesceCoversWebTests(unittest.TestCase):
    """Trap #2: maez-web is Wants=, not Requires= — stopping the daemon
    does NOT cascade; quiesce must check maez-web explicitly."""

    def test_active_web_refuses_quiesce(self):
        from scripts.birth_ceremony import _assert_quiesced

        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            runner = FakeSystemctl(
                {"maez.service": "inactive", "maez-web.service": "active"}
            )
            with self.assertRaisesRegex(RuntimeError, "maez-web"):
                _assert_quiesced(db, runner=runner)

    def test_quiesce_probes_wal_sidecars(self):
        from scripts.birth_ceremony import _assert_quiesced

        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            db.touch()
            Path(f"{db}-wal").touch()
            Path(f"{db}-shm").touch()
            runner = FakeSystemctl()
            _assert_quiesced(db, runner=runner)
            fuser_targets = [
                arg
                for cmd in runner.calls
                if cmd[0] == "fuser"
                for arg in cmd[1:]
            ]
            self.assertIn(f"{db}-wal", fuser_targets,
                          "a process holding only the -wal escapes a "
                          "db-only fuser probe")
            self.assertIn(f"{db}-shm", fuser_targets)


class VendoredSqliteReexecTests(unittest.TestCase):
    """Trap #10 second half, falsified claim executed 2026-08-24: bare
    .venv python loads 3.46.1; in-process env export cannot rebind an
    already-loaded libsqlite — the script must re-exec, once, and abort
    loudly if the second execution is still unfixed."""

    def test_reexec_prepends_vendor_path_and_guards(self):
        from scripts import birth_ceremony as bc

        with mock.patch(
            "core.infra.sqlite_runtime.has_wal_reset_fix", return_value=False
        ), mock.patch.dict(os.environ, {}, clear=False), mock.patch(
            "os.execve"
        ) as execve:
            os.environ.pop(bc._REEXEC_GUARD_ENV, None)
            bc._ensure_vendored_sqlite()
        execve.assert_called_once()
        args, kwargs = execve.call_args
        env = args[2]
        self.assertIn("vendor/sqlite/lib", env.get("LD_LIBRARY_PATH", ""))
        self.assertEqual(env.get(bc._REEXEC_GUARD_ENV), "1")

    def test_second_execution_still_unfixed_aborts(self):
        from scripts import birth_ceremony as bc

        with mock.patch(
            "core.infra.sqlite_runtime.has_wal_reset_fix", return_value=False
        ), mock.patch.dict(
            os.environ, {bc._REEXEC_GUARD_ENV: "1"}
        ), mock.patch("os.execve") as execve:
            with self.assertRaises(SystemExit):
                bc._ensure_vendored_sqlite()
        execve.assert_not_called()

    def test_bare_interpreter_reexecs_end_to_end(self):
        """Integration: launch the script with the corruption-window
        SQLite; it must re-exec under the vendored library and then
        behave normally (exit 2: dry-run without --db-path)."""
        repo = Path(__file__).resolve().parents[1]
        env = {
            k: v for k, v in os.environ.items() if k != "LD_LIBRARY_PATH"
        }
        proc = subprocess.run(
            [
                str(repo / ".venv" / "bin" / "python"),
                str(repo / "scripts" / "birth_ceremony.py"),
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(repo),
            timeout=120,
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("re-exec", proc.stderr.lower())
        self.assertIn("--dry-run requires --db-path", proc.stderr)


class ForRealChoreographyTests(unittest.TestCase):
    """The hardened state machine: stop both units → transaction (quiesce
    + lease inside) → tri-state classify → bring-up with at most one
    reset-failed + start per unit — failing toward daemon-STOPPED."""

    def _run_main(self, td: Path, runner: FakeSystemctl, *, argv=None):
        canonical = td / "ledger.db"
        kwargs, _facts, stack = _for_real_patches(td, canonical)
        with stack, mock.patch(
            "scripts.birth_ceremony.birth_phase.default_ledger_path",
            return_value=canonical,
        ), mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
            "builtins.input", return_value="birth maez"
        ), mock.patch(
            "scripts.birth_ceremony._activation_flag_landed",
            return_value=True,
        ), mock.patch(
            "scripts.birth_ceremony._unit_main_pid", return_value=4242
        ), mock.patch(
            "scripts.birth_ceremony._pid_env_has_flag", return_value=True
        ), mock.patch(
            "scripts.birth_ceremony._latch_is_held", return_value=True
        ):
            rc = main(argv or ["--for-real"], runner=runner)
        return rc, canonical

    def _receipt(self, db: Path) -> dict:
        receipts = sorted((db.parent / "birth_ceremony_receipts").iterdir())
        return json.loads(receipts[-1].read_text())

    def test_happy_path_commits_and_terminates_committed_active(self):
        with TemporaryDirectory() as td:
            runner = FakeSystemctl(
                {"maez.service": "active", "maez-web.service": "active"}
            )
            rc, db = self._run_main(Path(td), runner)
            self.assertEqual(rc, 0)
            receipt = self._receipt(db)
            self.assertEqual(receipt["terminal_state"], "COMMITTED_ACTIVE")
            self.assertEqual(receipt["commit_classification"], "COMMITTED")
            from scripts.birth_ceremony import classify_commit

            self.assertEqual(classify_commit(db), "COMMITTED")
            stops = [c for c in runner.calls if c[:3] == ["systemctl", "--user", "stop"]]
            self.assertEqual(
                stops[0][3], "maez-web.service",
                "web stops FIRST (it Wants= the daemon but survives it)",
            )
            self.assertEqual(stops[1][3], "maez.service")

    def test_ceremony_receipt_persists_the_rendered_statement(self):
        # Freeze a hash, persist its pre-image: the ledger row carries
        # rendered_text_hash; the exact statement text survives in the
        # durable ceremony journal.
        with TemporaryDirectory() as td:
            runner = FakeSystemctl(
                {"maez.service": "active", "maez-web.service": "active"}
            )
            rc, db = self._run_main(Path(td), runner)
            self.assertEqual(rc, 0)
            receipt = self._receipt(db)
            self.assertIn("S7 work-on-Maez authorization",
                          receipt["s7_rendered_statement_text"])
            self.assertTrue(receipt["ceremony_run_id"].startswith("birth-"))

    def test_daemon_start_failure_fails_toward_stopped(self):
        with TemporaryDirectory() as td:
            runner = FakeSystemctl(
                {
                    "maez.service": "active",
                    "maez-web.service": "active",
                    "maez.service:on_start": "failed",
                }
            )
            rc, db = self._run_main(Path(td), runner)
            self.assertEqual(rc, 1)
            receipt = self._receipt(db)
            self.assertEqual(
                receipt["terminal_state"], "COMMITTED_SERVICES_DOWN"
            )
            resets = [
                c for c in runner.calls
                if c[:3] == ["systemctl", "--user", "reset-failed"]
                and c[3] == "maez.service"
            ]
            starts = [
                c for c in runner.calls
                if c[:3] == ["systemctl", "--user", "start"]
                and c[3] == "maez.service"
            ]
            self.assertEqual(len(resets), 1, "at most ONE reset-failed")
            self.assertEqual(len(starts), 1, "at most ONE start attempt")
            web_starts = [
                c for c in runner.calls
                if c[:3] == ["systemctl", "--user", "start"]
                and c[3] == "maez-web.service"
            ]
            self.assertEqual(
                web_starts, [],
                "web must never start on top of a down daemon",
            )
            # Restart=on-failure scar: a failed start ends with a FINAL
            # stop so systemd does not keep retrying in the background.
            start_idx = runner.calls.index(starts[0])
            later_stops = [
                c for c in runner.calls[start_idx:]
                if c[:3] == ["systemctl", "--user", "stop"]
                and c[3] == "maez.service"
            ]
            self.assertTrue(later_stops)

    def test_unknown_classification_restarts_nothing(self):
        # Post-transaction UNKNOWN (preflight sees a clean unborn db;
        # the transaction fails leaving an unclassifiable one — staged
        # via classify_commit side_effect, since the preflight refusal
        # now blocks a pre-corrupted db from ever entering the ceremony).
        with TemporaryDirectory() as td:
            runner = FakeSystemctl(
                {"maez.service": "active", "maez-web.service": "active"}
            )
            with mock.patch(
                "scripts.birth_ceremony.classify_commit",
                side_effect=["NOT_COMMITTED", "UNKNOWN"],
            ), mock.patch(
                "scripts.birth_ceremony.run_transaction",
                side_effect=RuntimeError("simulated mid-transaction death"),
            ):
                rc, db = self._run_main(Path(td), runner)
            self.assertEqual(rc, 1)
            receipt = self._receipt(db)
            self.assertEqual(
                receipt["terminal_state"],
                "COMMIT_STATUS_UNKNOWN_SERVICES_DOWN",
            )
            self.assertEqual(
                [c for c in runner.calls if "start" in c or "reset-failed" in c],
                [],
                "UNKNOWN must never authorize a restart",
            )

    def test_quiesce_refusal_is_hands_off(self):
        class StuckWeb(FakeSystemctl):
            def __call__(self, cmd, **kwargs):
                if cmd[:3] == ["systemctl", "--user", "stop"]:
                    self.calls.append(list(cmd))
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                return super().__call__(cmd, **kwargs)

        with TemporaryDirectory() as td:
            runner = StuckWeb(
                {"maez.service": "inactive", "maez-web.service": "active"}
            )
            rc, db = self._run_main(Path(td), runner)
            self.assertEqual(rc, 1)
            receipt = self._receipt(db)
            self.assertEqual(
                receipt["terminal_state"], "QUIESCE_FAILED_HANDS_OFF"
            )
            self.assertEqual(
                [c for c in runner.calls if "start" in c], [],
                "quiesce failure means hands off — nothing starts",
            )

    def test_already_born_refuses_and_points_to_resume(self):
        with TemporaryDirectory() as td:
            # Birth the canonical db FIRST (before mocking the default
            # path, so the dry-run guard doesn't trip).
            birth_kwargs = _dry_kwargs(Path(td) / "prebirth")
            os.makedirs(Path(td) / "prebirth", exist_ok=True)
            canonical = birth_kwargs["db_path"]
            run_transaction(dry_run=True, **birth_kwargs)
            runner = FakeSystemctl()
            with mock.patch(
                "scripts.birth_ceremony.birth_phase.default_ledger_path",
                return_value=canonical,
            ), mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "sys.stderr"
            ) as stderr:
                rc = main(["--for-real"], runner=runner)
            self.assertEqual(rc, 2)
            printed = "".join(c.args[0] for c in stderr.write.call_args_list)
            self.assertIn("do not re-birth", printed.lower())
            self.assertIn("--resume-services", printed)


class ValidationRoundFixesTests(unittest.TestCase):
    """Codex validation round (2026-08-24): confirmed findings, each
    encoded as a test that fails on the pre-fix code."""

    def test_for_real_refuses_unclassifiable_ledger_before_touching_anything(self):
        # CRITICAL #2: preflight refused only COMMITTED; an UNKNOWN
        # (unclassifiable) canonical db walked straight into the
        # irreversible transaction.
        with TemporaryDirectory() as td:
            canonical = Path(td) / "ledger.db"
            canonical.write_bytes(b"garbage that is definitely not sqlite..")
            runner = FakeSystemctl()
            with mock.patch(
                "scripts.birth_ceremony.birth_phase.default_ledger_path",
                return_value=canonical,
            ), mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "sys.stderr"
            ) as stderr:
                rc = main(["--for-real"], runner=runner)
            self.assertEqual(rc, 2)
            self.assertEqual(
                runner.calls, [],
                "an unclassifiable ledger refuses BEFORE any unit is touched",
            )
            printed = "".join(c.args[0] for c in stderr.write.call_args_list)
            self.assertIn("UNKNOWN", printed)

    def test_classify_detects_logically_tampered_chain(self):
        # CRITICAL #3: physical integrity_check is green after a logical
        # tamper; classification must recompute the chain.
        from scripts.birth_ceremony import classify_commit

        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            db = kwargs["db_path"]
            run_transaction(dry_run=True, **kwargs)
            self.assertEqual(classify_commit(db), "COMMITTED")
            conn = sqlite3.connect(db)
            try:
                # Simulate OFFLINE tampering (raw file edit): SQL-level
                # UPDATE is blocked by the append-only trigger, so drop
                # it first — the classifier must not depend on triggers
                # that a file editor never runs. Same event, different
                # witness: payload check alone stays green; only chain
                # recomputation catches it.
                for (trig,) in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger'"
                ).fetchall():
                    conn.execute(f"DROP TRIGGER {trig}")
                conn.execute(
                    "UPDATE turns SET raw_text = replace(raw_text,"
                    " '\"rohit\"', '\"mallory\"')"
                    " WHERE raw_text LIKE '%\"event\": \"birth\"%'"
                    " OR raw_text LIKE '%\"event\":\"birth\"%'"
                )
                conn.commit()
            finally:
                conn.close()
            self.assertEqual(
                classify_commit(db), "UNKNOWN",
                "a logically tampered ledger must never classify COMMITTED",
            )

    def test_mute_web_is_its_own_terminal_state(self):
        # MAJOR #4: web up but blind to the flag was labeled
        # COMMITTED_ACTIVE — the exact silent-omission state Theme 2
        # exists to name.
        from scripts import birth_ceremony as bc

        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            db = kwargs["db_path"]
            run_transaction(dry_run=True, **kwargs)
            runner = FakeSystemctl()
            pids = {"maez.service": 4242, "maez-web.service": 5555}
            with mock.patch(
                "scripts.birth_ceremony._activation_flag_landed",
                return_value=True,
            ), mock.patch(
                "scripts.birth_ceremony._unit_main_pid",
                side_effect=lambda unit, runner=None: pids[unit],
            ), mock.patch(
                "scripts.birth_ceremony._pid_env_has_flag",
                side_effect=lambda pid: pid == 4242,
            ), mock.patch(
                "scripts.birth_ceremony._latch_is_held", return_value=True
            ):
                state = bc._bring_up_after_commit(
                    db, runner=runner, prompt=lambda *_: "",
                    printer=lambda *_: None,
                )
            self.assertEqual(state, "COMMITTED_WEB_MUTE")

    def test_a_blind_web_process_is_STOPPED_not_left_serving(self):
        """A2 fail-closed (owner-ruled 2026-08-28).

        A born Maez must never keep an available but autobiographically
        BLIND mouth. Naming the state honestly was necessary but not
        sufficient: while the unit kept serving, web turns were silently
        omitted from admission for as long as the owner left it up.
        """
        from scripts import birth_ceremony as bc

        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            db = kwargs["db_path"]
            run_transaction(dry_run=True, **kwargs)
            runner = FakeSystemctl()
            pids = {"maez.service": 4242, "maez-web.service": 5555}
            with mock.patch(
                "scripts.birth_ceremony._activation_flag_landed",
                return_value=True,
            ), mock.patch(
                "scripts.birth_ceremony._unit_main_pid",
                side_effect=lambda unit, runner=None: pids[unit],
            ), mock.patch(
                "scripts.birth_ceremony._pid_env_has_flag",
                side_effect=lambda pid: pid == 4242,
            ), mock.patch(
                "scripts.birth_ceremony._latch_is_held", return_value=True
            ):
                state = bc._bring_up_after_commit(
                    db, runner=runner, prompt=lambda *_: "",
                    printer=lambda *_: None,
                )
            self.assertEqual(state, "COMMITTED_WEB_MUTE")
            stopped = [
                c for c in runner.calls
                if "stop" in c and "maez-web.service" in c
            ]
            self.assertTrue(
                stopped,
                "a web process that cannot prove MAEZ_LEDGER_WRITES was "
                "left SERVING. Fail closed: stop the unit rather than "
                "leave a born Maez with a blind mouth.",
            )

    def test_restore_starts_only_what_was_running(self):
        # MAJOR #13: restore must not activate a unit the owner had
        # deliberately stopped before the ceremony.
        with TemporaryDirectory() as td:
            canonical = Path(td) / "ledger.db"
            kwargs, _facts, stack = _for_real_patches(Path(td), canonical)
            runner = FakeSystemctl(
                {"maez.service": "active", "maez-web.service": "inactive"}
            )
            with stack, mock.patch(
                "scripts.birth_ceremony.birth_phase.default_ledger_path",
                return_value=canonical,
            ), mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "builtins.input", return_value="birth maez"
            ), mock.patch(
                "scripts.birth_ceremony.run_transaction",
                side_effect=RuntimeError("transaction failed on purpose"),
            ):
                rc = main(["--for-real"], runner=runner)
            self.assertEqual(rc, 1)
            web_starts = [
                c for c in runner.calls
                if c[:3] == ["systemctl", "--user", "start"]
                and c[3] == "maez-web.service"
            ]
            self.assertEqual(
                web_starts, [],
                "maez-web was NOT running before the ceremony — restore "
                "must not start it",
            )

    def test_quiesce_refuses_on_probe_error(self):
        # MAJOR #14: pgrep rc>=2 is a probe ERROR, not 'no process'.
        from scripts.birth_ceremony import QuiesceRefused, _assert_quiesced

        class BrokenPgrep(FakeSystemctl):
            def __call__(self, cmd, **kwargs):
                if cmd[0] == "pgrep":
                    self.calls.append(list(cmd))
                    return subprocess.CompletedProcess(
                        cmd, 2, stdout="", stderr="pgrep: bad pattern"
                    )
                return super().__call__(cmd, **kwargs)

        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            with self.assertRaisesRegex(QuiesceRefused, "(?i)probe|error"):
                _assert_quiesced(db, runner=BrokenPgrep())

    def test_resume_services_parses_without_rail_args(self):
        # MINOR #17: the printed recovery command must parse as printed.
        with TemporaryDirectory() as td:
            canonical = Path(td) / "ledger.db"
            canonical.touch()
            with mock.patch(
                "scripts.birth_ceremony.birth_phase.default_ledger_path",
                return_value=canonical,
            ), mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "sys.stderr"
            ):
                rc = main(["--resume-services"], runner=FakeSystemctl())
            self.assertEqual(
                rc, 2,
                "must reach the uncommitted-ledger refusal, not argparse",
            )


class ResumeServicesTests(unittest.TestCase):
    """COMMITTED_SERVICES_DOWN must not be stranded: resume finishes the
    bring-up of an already-committed birth WITHOUT ever re-entering the
    transaction."""

    def test_resume_refuses_uncommitted_ledger(self):
        with TemporaryDirectory() as td:
            canonical = Path(td) / "ledger.db"
            canonical.touch()
            with mock.patch(
                "scripts.birth_ceremony.birth_phase.default_ledger_path",
                return_value=canonical,
            ), mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "sys.stderr"
            ) as stderr:
                rc = main(["--resume-services"], runner=FakeSystemctl())
            self.assertEqual(rc, 2)
            printed = "".join(c.args[0] for c in stderr.write.call_args_list)
            self.assertIn("COMMITTED", printed)

    def test_resume_brings_up_without_touching_the_transaction(self):
        with TemporaryDirectory() as td:
            kwargs = _dry_kwargs(td)
            canonical = kwargs["db_path"]
            run_transaction(dry_run=True, **kwargs)
            runner = FakeSystemctl()
            with mock.patch(
                "scripts.birth_ceremony.birth_phase.default_ledger_path",
                return_value=canonical,
            ), mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "scripts.birth_ceremony.run_transaction",
                side_effect=AssertionError("resume must NEVER write"),
            ), mock.patch(
                "scripts.birth_ceremony._activation_flag_landed",
                return_value=True,
            ), mock.patch(
                "scripts.birth_ceremony._unit_main_pid", return_value=4242
            ), mock.patch(
                "scripts.birth_ceremony._pid_env_has_flag", return_value=True
            ), mock.patch(
                "scripts.birth_ceremony._latch_is_held", return_value=True
            ):
                rc = main(["--resume-services"], runner=runner)
            self.assertEqual(rc, 0)
            starts = [
                c for c in runner.calls
                if c[:3] == ["systemctl", "--user", "start"]
            ]
            self.assertEqual(
                [c[3] for c in starts],
                ["maez.service", "maez-web.service"],
                "daemon first, web on top of a proven-live daemon",
            )


if __name__ == "__main__":
    unittest.main()
