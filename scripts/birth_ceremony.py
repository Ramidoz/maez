# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The birth transaction — owner's tool, hardened into one fail-closed
maintenance transaction (ceremony spec + council rulings 2026-08-24,
docs/superpowers/witness/theme2-s2-owner-delegated-council-rulings.md).

Performs: quiesce → lease → init → birth system_event write → meta anchor
(atomic, via the production writer's birth_anchor path) → independent
commit classification → service bring-up with explicit terminal states.
The activation flag flip stays the OWNER's hands (a guided pause), and
WebAuthn verification stays the owner's eyes.

Hardening encoded here, each against a named, verified trap:
- The LEASE IS THE WRITER (this-round council, 3 seats + executed
  probes): the enabled LedgerWriter constructs FIRST, so the owner latch
  is held continuously from before ``migrate.run()`` (an unlatched WAL
  writer, trap #4) through the birth write. No release-reacquire window
  (trap #3), no latch-bypass parameter, no module-global lease registry
  (the ``python -m`` dual-module-identity scar).
- Quiesce lives INSIDE ``run_transaction()`` (importable, trap #9) and
  covers maez-web explicitly (Wants= does not cascade, trap #2), the
  WAL sidecars, and both process shapes.
- ``systemctl --user`` everywhere; a dead user bus REFUSES instead of
  reading as inactive (trap #10 — the system bus is a silent no-op).
- Commit-ness is a TRI-STATE derived from the db, never stdout:
  corruption classifies UNKNOWN, never NOT_COMMITTED — that mislabel is
  what authorizes an unsafe restart. Birth is never re-run because an
  ACK was lost; ``--resume-services`` finishes an interrupted bring-up
  without ever re-entering the transaction.
- Bare shells load SQLite 3.46.1 (inside the WAL-reset corruption
  window — executed probe, not a docstring claim): the script re-execs
  itself once under the vendored library and aborts loudly if the
  second execution is still unfixed. In-process env export is a
  placebo — it cannot rebind an already-loaded libsqlite.

--dry-run (default): runs the full transaction against caller-supplied
  temp paths (--db-path, --s7-store-path, --manifest-path, --run-id —
  a rehearsal store holding a consumed birth authorization). Never the
  real ledger or the real S7 store. No systemd contact.
--for-real: interactive TTY + typed phrase, canonical paths only. Mints
  and atomically consumes a REAL S7 birth authorization (owner taps the
  physical key against the cockpit origin), stops both writer-capable
  units, runs the transaction (which re-proves the consumed receipt from
  the store), classifies, brings services back up with at most ONE
  reset-failed + start per unit, and fails toward daemon-STOPPED loudly.
--resume-services: finishes the bring-up of an ALREADY-COMMITTED birth
  (crash after commit; COMMITTED_SERVICES_DOWN). Never writes.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from core.ledger import migrate
from core.memory import birth_phase

_CONFIRM_PHRASE = "birth maez"

_REEXEC_GUARD_ENV = "MAEZ_BIRTH_CEREMONY_REEXEC"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENDOR_LIB = _REPO_ROOT / "vendor" / "sqlite" / "lib"

#: Every direct-writer-capable unit. maez-web is Wants=maez.service, not
#: Requires= — stopping the daemon does NOT cascade (trap #2, verified).
_WRITER_UNITS = ("maez.service", "maez-web.service")

# Terminal states. Structured: commit axis x service axis. UNKNOWN never
# restarts anything — restarting over an unprovable birth is the one
# unrecoverable direction.
QUIESCE_FAILED_HANDS_OFF = "QUIESCE_FAILED_HANDS_OFF"
NOT_COMMITTED_SERVICES_RESTORED = "NOT_COMMITTED_SERVICES_RESTORED"
NOT_COMMITTED_SERVICES_DOWN = "NOT_COMMITTED_SERVICES_DOWN"
COMMITTED_ACTIVE = "COMMITTED_ACTIVE"
COMMITTED_WEB_DOWN = "COMMITTED_WEB_DOWN"
COMMITTED_WEB_MUTE = "COMMITTED_WEB_MUTE"
COMMITTED_SERVICES_DOWN = "COMMITTED_SERVICES_DOWN"
COMMIT_STATUS_UNKNOWN_SERVICES_DOWN = "COMMIT_STATUS_UNKNOWN_SERVICES_DOWN"


class QuiesceRefused(RuntimeError):
    """Quiesce could not be proven — hands off everything."""


def _ensure_vendored_sqlite() -> None:
    """Re-exec once under the vendored SQLite if this process loaded a
    library inside the WAL-reset corruption window. Called from the
    ``__main__`` guard only (an imported module must never exec the
    importing process). The second execution re-verifies: a guard that
    proves 'an exec was attempted' is not a guard that proves the fix."""
    from core.infra import sqlite_runtime

    if sqlite_runtime.has_wal_reset_fix():
        return
    if os.environ.get(_REEXEC_GUARD_ENV):
        sys.stderr.write(
            "REFUSED: still linked against SQLite "
            f"{sqlite3.sqlite_version} after re-exec under "
            f"{_VENDOR_LIB} — the vendored library is missing or broken. "
            "A birth on this version runs inside the WAL-reset corruption "
            "window. Fix vendor/sqlite and retry.\n"
        )
        raise SystemExit(2)
    env = dict(os.environ)
    prior = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = (
        f"{_VENDOR_LIB}:{prior}" if prior else str(_VENDOR_LIB)
    )
    env[_REEXEC_GUARD_ENV] = "1"
    sys.stderr.write(
        f"birth_ceremony: re-exec under vendored SQLite ({_VENDOR_LIB}) — "
        f"this interpreter loaded {sqlite3.sqlite_version}\n"
    )
    sys.stderr.flush()
    os.execve(sys.executable, [sys.executable] + sys.argv, env)


def _unit_active_state(unit: str, *, runner=subprocess.run) -> str:
    """'active' | 'inactive', or REFUSE when the answer cannot be known.

    The old probe compared stdout == "active": with a dead user bus the
    output is empty, which silently reads as quiesced. An answer we
    cannot prove is a refusal, not an 'inactive'.
    """
    result = runner(
        ["systemctl", "--user", "is-active", unit],
        capture_output=True,
        text=True,
    )
    state = (result.stdout or "").strip()
    if state in ("active", "activating", "reloading"):
        return "active"
    if state in ("inactive", "failed", "dead", "deactivating"):
        return "inactive"
    raise RuntimeError(
        f"cannot determine {unit} state (user bus down?): "
        f"rc={result.returncode} stdout={state!r} "
        f"stderr={(result.stderr or '').strip()!r}"
    )


def _assert_quiesced(db_path: Path, *, runner=subprocess.run) -> None:
    """Ceremony quiesce: every writer-capable surface provably stopped.

    LIVE-BODY FACTS: the units are USER-scoped (``systemctl`` without
    --user probes the wrong bus and no-ops); maez-web is a separate
    direct-writer-capable service that Wants= does not stop with the
    daemon; a process holding only the -wal/-shm sidecar escapes a
    db-only fuser probe.
    """
    for unit in _WRITER_UNITS:
        try:
            state = _unit_active_state(unit, runner=runner)
        except RuntimeError as exc:
            raise QuiesceRefused(f"REFUSED: {exc}") from exc
        if state == "active":
            raise QuiesceRefused(
                f"REFUSED: {unit} (user unit) is active — quiesce first "
                f"(systemctl --user stop {unit})"
            )
    for pattern, label in (
        ("daemon/maez_daemon.py", "maez daemon"),
        ("skills/web_interface.py", "maez web surface"),
    ):
        probe = runner(
            ["pgrep", "-f", pattern], capture_output=True, text=True
        )
        if probe.returncode == 0:
            raise QuiesceRefused(
                f"REFUSED: {label} process is running (pids: "
                f"{' '.join(probe.stdout.split())}) — quiesce first"
            )
        if probe.returncode != 1:
            # pgrep rc 1 means 'no process matched'; anything else is a
            # PROBE ERROR — quiesce can only fail closed (Codex
            # validation #14: an errored probe must never read as clean).
            raise QuiesceRefused(
                f"REFUSED: {label} probe error (pgrep rc="
                f"{probe.returncode}, stderr="
                f"{(probe.stderr or '').strip()!r}) — cannot prove quiesce"
            )
    db_path = Path(db_path)
    for target in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        if target.exists():
            probe = runner(
                ["fuser", str(target)], capture_output=True, text=True
            )
            if probe.returncode == 0:
                raise QuiesceRefused(
                    f"REFUSED: a process holds {target} open — "
                    "no live writer allowed"
                )
            if probe.returncode != 1:
                raise QuiesceRefused(
                    f"REFUSED: fuser probe error on {target} (rc="
                    f"{probe.returncode}) — cannot prove quiesce"
                )


def classify_commit(db_path: Path | str) -> str:
    """'COMMITTED' | 'NOT_COMMITTED' | 'UNKNOWN' — from the db, never
    stdout.

    ``is_born()`` cannot classify commit status: it maps missing,
    unreadable and corrupt ledgers to False (verified). Only a readable,
    integrity-ok db with no anchor proves NOT_COMMITTED; every failure
    to prove is UNKNOWN, and UNKNOWN never authorizes a restart.
    """
    path = Path(db_path)
    try:
        if not path.exists() or path.stat().st_size == 0:
            # Known-good pre-init states: nothing was ever written.
            return "NOT_COMMITTED"
    except OSError:
        return "UNKNOWN"
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return "UNKNOWN"
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            return "UNKNOWN"
        row = conn.execute(
            "SELECT value FROM meta WHERE key='birth_event_turn_id'"
        ).fetchone()
        anchor = (row[0] or "").strip() if row else ""
        if not anchor:
            return "NOT_COMMITTED"
        conn.row_factory = sqlite3.Row
        birth = conn.execute(
            "SELECT turn_kind, raw_text FROM turns WHERE turn_id = ?",
            (anchor,),
        ).fetchone()
        if birth is None or birth["turn_kind"] != "system_event":
            return "UNKNOWN"
        payload = json.loads(birth["raw_text"])
        if payload.get("event") != "birth":
            return "UNKNOWN"
        # Logical chain verification (Codex validation #3): PRAGMA
        # integrity_check is PHYSICAL — a tampered row's content leaves
        # it green. Recompute the hash chain; any break is UNKNOWN.
        from core.ledger import chain as _chain

        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM turns ORDER BY chain_position"
            ).fetchall()
        ]
        if _chain.verify_chain(rows):
            return "UNKNOWN"
        return "COMMITTED"
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        return "UNKNOWN"
    finally:
        conn.close()


def _write_execution_marker(marker: Path, doc: dict) -> None:
    """Atomic, fsynced execution-marker write (file then directory)."""
    marker.parent.mkdir(parents=True, exist_ok=True)
    tmp = marker.parent / f".tmp-{marker.name}"
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    try:
        os.write(fd, json.dumps(doc, sort_keys=True).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, marker)
    dir_fd = os.open(marker.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def run_transaction(
    *,
    db_path: Path,
    run_id: str,
    s7_store_path: Path,
    manifest_path: Path,
    owner_witness: str,
    dry_run: bool,
    quiesce=None,
    runner=subprocess.run,
) -> dict:
    """The birth transaction under a continuously-held maintenance lease.

    Order is the invariant: quiesce (for-real) → construct the ENABLED
    writer (this takes the owner latch AND fires require_fixed — the
    lease exists before any mutation) → migrate under the latch → refuse
    if already born → birth write through the same writer → independent
    tri-state verification. Verified 2026-08-24 by executed probe:
    LedgerWriter.__init__ touches only pragmas, so constructing it on an
    unmigrated db is safe, and its connection adopts WAL at its first
    write after migrate runs.
    """
    from core.governance import birth_authorization as _birth_auth

    # Re-validation F2 (executed symlink probe): an alias spelling that
    # RESOLVES to the canonical path passed the equality checks, but the
    # execution marker and the writer's owner latch derived from the
    # UNRESOLVED spelling — landing beside the alias and splitting their
    # identity. Normalize ONCE, here; every consumer below sees the real
    # path.
    db_path = Path(db_path).resolve()
    s7_store_path = Path(s7_store_path).resolve()
    manifest_path = Path(manifest_path).resolve()

    if dry_run and (
        db_path == birth_phase.default_ledger_path().resolve()
        or str(db_path) == _birth_auth.canonical_ledger_realpath()
    ):
        # BOTH resolvers (Codex validation F1, reproduced): with
        # MAEZ_LEDGER_DB_PATH set, default_ledger_path() stops
        # recognizing the real ledger — the env-blind canonical path
        # must also refuse.
        raise ValueError(
            "REFUSED: dry-run may not target the real ledger; use a temp --db-path"
        )
    if dry_run and (
        Path(s7_store_path).resolve()
        == _birth_auth.canonical_s7_store_path().resolve()
    ):
        raise ValueError(
            "REFUSED: dry-run may not consume from the real S7 store; "
            "use a rehearsal --s7-store-path"
        )
    if not (run_id or "").strip():
        raise ValueError("run_id is required — the act ties to the proof")

    if not dry_run:
        # The env-override CLASS refuses INSIDE the importable function
        # (thirteenth round): any path redirector can point the ceremony
        # at a decoy ledger/store/manifest while the daemon reads the
        # real ones.
        _birth_auth.refuse_env_overrides()
        # Codex validation F2 (reproduced): the preimage names the
        # canonical targets, but migrate/write would use the CALLER's
        # paths — an importer could redirect the write while the receipt
        # claims the canonical target. For-real binds all three.
        mismatched = [
            name
            for name, got, want in (
                (
                    "db_path",
                    str(Path(db_path).resolve()),
                    _birth_auth.canonical_ledger_realpath(),
                ),
                (
                    "s7_store_path",
                    str(Path(s7_store_path).resolve()),
                    str(_birth_auth.canonical_s7_store_path().resolve()),
                ),
                (
                    "manifest_path",
                    str(Path(manifest_path).resolve()),
                    str(_birth_auth.canonical_manifest_path().resolve()),
                ),
            )
            if got != want
        ]
        if mismatched:
            raise _birth_auth.BirthAuthorizationRefusal(
                "noncanonical_target_in_for_real",
                f"{', '.join(mismatched)} differ from the canonical paths",
            )
        # Trap #9: this function is importable; the quiesce must live
        # HERE, not only in main(). Dry runs on temp dbs never touch
        # systemd. The `quiesce` parameter is a TEST SEAM: an importer
        # substituting a no-op is a same-UID actor deliberately defeating
        # its own safety check — inside the stated proof boundary
        # (tamper-evidence, not tamper-prevention), and it cannot fake
        # the receipt rail above/below this line.
        quiesce_fn = quiesce or (
            lambda path: _assert_quiesced(path, runner=runner)
        )
        quiesce_fn(Path(db_path))

    # THE RECEIPT RAIL (A1/B2, thirteenth round): the transaction itself
    # re-verifies the consumed S7 authorization FROM THE STORE, by
    # recomputation against reality — the manifest bytes are re-hashed and
    # the target path re-resolved HERE, never taken from the caller's
    # word. An importer bypassing main() hits this wall. Pure reads, so
    # they run BEFORE the lease: a refused rail leaves ZERO ledger bytes
    # (LedgerWriter construction would create the file). The ro snapshot
    # then stays open across the birth write.
    expected_params = _birth_auth.birth_action_params(
        ledger_db_realpath=(
            _birth_auth.canonical_ledger_realpath()
            if not dry_run
            else str(Path(db_path).resolve())
        ),
        creation_manifest_sha256=_birth_auth.read_manifest_sha256(
            Path(manifest_path)
        ),
        owner_witness=owner_witness,
        mode="dry_run" if dry_run else "for_real",
    )
    with _birth_auth.held_birth_authorization_proof(
        store_path=Path(s7_store_path),
        run_id=run_id,
        expected_params=expected_params,
    ) as receipt_facts:
        # Codex validation F3 (reproduced): consume-once must mean
        # EXECUTE-once. Within the freshness window, a birthed-then-
        # deleted ledger would otherwise re-birth on the same consumed
        # artifact. The durable execution marker (written after the
        # birth commit, below) refuses a second execution by name.
        _marker = (
            Path(db_path).parent
            / "birth_ceremony_receipts"
            / f"birth-executed-{receipt_facts['s7_artifact_id']}.json"
        )
        if _marker.exists():
            raise _birth_auth.BirthAuthorizationRefusal(
                "receipt_already_executed",
                f"{_marker.name} exists — this authorization already "
                "executed a birth transaction; re-tap for a new attempt",
            )
        # THE LEASE: the enabled writer, constructed before any mutation.
        # The flag is raised only around construction (the writer reads it
        # at __init__) and restored after — a dry run inside a test
        # process never leaks an enabled flag into later
        # refusal-by-default tests.
        from core.ledger.writer import LedgerWriter

        prior = os.environ.get("MAEZ_LEDGER_WRITES")
        os.environ["MAEZ_LEDGER_WRITES"] = "1"
        try:
            try:
                writer = LedgerWriter(db_path=str(db_path))
            except sqlite3.DatabaseError as exc:
                # An unreadable target dies in the lease's own pragmas
                # before the under-latch classification can name it. No
                # mutation happened; refuse by the same name.
                raise _birth_auth.BirthAuthorizationRefusal(
                    "preflight_not_unborn",
                    f"the target is unreadable as a database "
                    f"(classifies {classify_commit(db_path)}): {exc}",
                ) from exc
        finally:
            if prior is None:
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
            else:
                os.environ["MAEZ_LEDGER_WRITES"] = prior

        try:
            # Re-validation F4 (executed TOCTOU probe): a foreign db
            # inserted between an early classification and the latch was
            # migrated and birthed. The NOT_COMMITTED classification now
            # runs UNDER the latch, where nothing can swap the file.
            _classification = classify_commit(db_path)
            if _classification != "NOT_COMMITTED":
                raise _birth_auth.BirthAuthorizationRefusal(
                    "preflight_not_unborn",
                    f"the target classifies {_classification} under the "
                    "latch — only a provably unborn ledger enters the "
                    "birth write",
                )
            # Re-validation F3, corrected by the third pass: the marker
            # is a durable CLAIM written BEFORE the first mutation and
            # AFTER every refusal gate — an ordinary refusal (foreign
            # db, unreadable target) must spend nothing, while every
            # crash ordering from here on leaves either a born ledger or
            # a spent marker (including commit-then-delete). Cost
            # accepted by ruling: a crash between this line and the
            # commit spends the receipt; the owner re-taps.
            _write_execution_marker(
                _marker,
                {
                    "state": "executing",
                    "ceremony_run_id": run_id,
                    "s7_artifact_id": receipt_facts["s7_artifact_id"],
                    "claimed_at": time.time(),
                },
            )
            # Transaction step 1: init (idempotent), UNDER the latch —
            # migrate.run() is itself an unlatched WAL writer (trap #4).
            migrate.run(str(db_path))
            if not migrate.ledger_is_initialized(str(db_path)):
                raise RuntimeError(f"ledger init failed to verify: {db_path}")
            if birth_phase.is_born(db_path):
                raise ValueError(
                    "birth_event_turn_id already set — we do not re-birth"
                )
            payload = {
                "event": "birth",
                "phase_transition": "gestation -> lived",
                "owner_witness": owner_witness,
                "ceremony_ts": time.time(),
                "mode": "dry_run" if dry_run else "for_real",
                # Resolved facts, never a caller string (the free-string
                # s7_receipt_ref died in the thirteenth round). The
                # projection hash is the "hash of the ceremony receipts"
                # the 2026-07-05 design puts in the birth row.
                **receipt_facts,
                "s7_receipt_projection_sha256": (
                    _birth_auth.birth_receipt_projection_sha256(receipt_facts)
                ),
            }
            # Transaction steps 2+3: birth write + anchor, atomic in the
            # writer, through the SAME writer that holds the lease. The
            # proof snapshot is still open here.
            birth_turn_id = writer.write_turn(
                "system_event",
                json.dumps(payload, sort_keys=True),
                birth_anchor=True,
                taint_labels=["self_generated"],
                privacy_access="public",
            )
            # The marker was claimed BEFORE the mutation; now that the
            # commit exists, rewrite it with the outcome (atomic replace
            # — a crash here leaves the "executing" claim, which refuses
            # identically).
            _write_execution_marker(
                _marker,
                {
                    "state": "committed",
                    "birth_turn_id": birth_turn_id,
                    "ceremony_run_id": run_id,
                    "s7_artifact_id": receipt_facts["s7_artifact_id"],
                    "executed_at": time.time(),
                },
            )
        finally:
            writer.close()

    # Independent verification — the tri-state, not the returned id.
    verdict = classify_commit(db_path)
    if verdict != "COMMITTED":
        raise RuntimeError(
            f"birth commit did not verify: classification={verdict} — "
            "do NOT re-run; classify and recover by hand"
        )
    return {"birth_turn_id": birth_turn_id, "db_path": str(db_path)}


# ------------------------------------------------------------------ bring-up


def _start_unit_once(unit: str, *, runner=subprocess.run) -> bool:
    """Exactly one reset-failed + start attempt (start-limit scar). Both
    units are Restart=on-failure: after a failed start the unit would
    keep retrying in the background, so failure ends with a final stop
    and verification — one `start` command is not one process attempt."""
    runner(
        ["systemctl", "--user", "reset-failed", unit],
        capture_output=True,
        text=True,
    )
    runner(["systemctl", "--user", "start", unit], capture_output=True, text=True)
    try:
        if _unit_active_state(unit, runner=runner) == "active":
            return True
    except RuntimeError:
        pass
    runner(["systemctl", "--user", "stop", unit], capture_output=True, text=True)
    return False


def _stop_unit(unit: str, *, runner=subprocess.run) -> None:
    runner(["systemctl", "--user", "stop", unit], capture_output=True, text=True)


def _restore_services(
    *, runner=subprocess.run, initially_active: dict | None = None
) -> bool:
    """NOT_COMMITTED path: put the organism back the way we FOUND it —
    a unit the owner had deliberately stopped before the ceremony must
    stay stopped (Codex validation #13). Daemon first; web only on top
    of a live daemon."""
    if initially_active is None:
        initially_active = {u: True for u in _WRITER_UNITS}
    ok = True
    daemon_wanted = initially_active.get("maez.service", True)
    daemon_up = False
    if daemon_wanted:
        daemon_up = _start_unit_once("maez.service", runner=runner)
        ok = ok and daemon_up
    if initially_active.get("maez-web.service", True):
        if daemon_wanted and not daemon_up:
            _stop_unit("maez-web.service", runner=runner)
            ok = False
        else:
            ok = _start_unit_once("maez-web.service", runner=runner) and ok
    return ok


def _activation_flag_landed() -> bool:
    """Has the owner landed MAEZ_LEDGER_WRITES=1 in the env file the
    daemon unit actually loads? (Scan only — never print the file: it
    holds tokens.)"""
    env_file = Path.home() / ".config" / "maez" / "model.env"
    try:
        text = env_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.replace(" ", "") in (
            "MAEZ_LEDGER_WRITES=1",
            "MAEZ_LEDGER_WRITES=true",
        ):
            return True
    return False


def _unit_main_pid(unit: str, *, runner=subprocess.run) -> int:
    result = runner(
        ["systemctl", "--user", "show", "--property=MainPID", "--value", unit],
        capture_output=True,
        text=True,
    )
    try:
        return int((result.stdout or "").strip() or "0")
    except ValueError:
        return 0


def _pid_env_has_flag(pid: int) -> bool:
    try:
        environ = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return False
    return b"MAEZ_LEDGER_WRITES=1" in environ or b"MAEZ_LEDGER_WRITES=true" in environ


def _latch_is_held(db_path: Path) -> bool:
    """Probe on a separate fd: trial-lock success proves the latch is
    free (we release our probe immediately); EWOULDBLOCK proves held."""
    import fcntl

    lock = Path(f"{os.path.abspath(db_path)}.ownerlock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _bring_up_after_commit(
    db_path: Path,
    *,
    runner=subprocess.run,
    prompt=input,
    printer=print,
) -> str:
    """Post-commit bring-up. 'active' is not owner-active (verified: the
    daemon survives an ownership-claim failure at startup) — so verify
    the daemon actually SEES the flag and HOLDS the latch before calling
    the birth green."""
    tries = 0
    while not _activation_flag_landed() and tries < 3:
        printer(
            "OWNER STEP — land the activation flag now (your hands, not "
            "the script's):\n"
            "    MAEZ_LEDGER_WRITES=1   # <today's date> birth ceremony\n"
            "  in ~/.config/maez/model.env (the file maez.service loads).\n"
            "  NOTE (verified 2026-08-24): maez-web.service loads NO "
            "EnvironmentFile — until the flag is wired into a maez-web "
            "drop-in, web turns will be SILENTLY OMITTED from admission."
        )
        prompt("Press Enter when landed (attempt %d/3): " % (tries + 1))
        tries += 1
    if not _activation_flag_landed():
        printer(
            "activation flag not found in ~/.config/maez/model.env — the "
            "daemon stays STOPPED. Land the flag, then run "
            "--resume-services."
        )
        return COMMITTED_SERVICES_DOWN

    if not _start_unit_once("maez.service", runner=runner):
        _stop_unit("maez-web.service", runner=runner)
        return COMMITTED_SERVICES_DOWN

    pid = _unit_main_pid("maez.service", runner=runner)
    deadline = time.monotonic() + 15
    owner_ok = False
    while time.monotonic() < deadline:
        if pid and _pid_env_has_flag(pid) and _latch_is_held(db_path):
            owner_ok = True
            break
        time.sleep(0.5)
        pid = pid or _unit_main_pid("maez.service", runner=runner)
    if not owner_ok:
        printer(
            "maez.service is 'active' but did not prove ownership (flag "
            "in process env + ownerlock held) — that is a mute daemon, "
            "not a live one. Stopping both units."
        )
        _stop_unit("maez-web.service", runner=runner)
        _stop_unit("maez.service", runner=runner)
        return COMMITTED_SERVICES_DOWN

    if not _start_unit_once("maez-web.service", runner=runner):
        return COMMITTED_WEB_DOWN
    web_pid = _unit_main_pid("maez-web.service", runner=runner)
    if not (web_pid and _pid_env_has_flag(web_pid)):
        # Codex validation #4: web-up-but-blind is the exact
        # silent-omission state Theme 2 exists to name — it must be its
        # own terminal state, never folded into green.
        printer(
            "maez-web.service is up but does NOT see MAEZ_LEDGER_WRITES "
            "in its process environment (it loads no EnvironmentFile) — "
            "web conversation turns will be silently omitted from "
            "admission until the owner wires the flag into a maez-web "
            "drop-in. The birth stands; the web surface is MUTE."
        )
        return COMMITTED_WEB_MUTE
    return COMMITTED_ACTIVE


# ------------------------------------------------------------------ receipt


def _write_receipt(db_path: Path, doc: dict) -> Path:
    """Durable ceremony journal beside the ledger, atomic + fsynced. The
    receipt is a convenience narrative — commit-ness always re-derives
    from the db (classify_commit), never from this file or stdout."""
    receipts = Path(db_path).parent / "birth_ceremony_receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    target = receipts / f"ceremony-{doc['started_at']}.json"
    tmp = receipts / f".tmp-{target.name}"
    payload = json.dumps(doc, sort_keys=True, indent=2).encode("utf-8")
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, target)
    dir_fd = os.open(receipts, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return target


# --------------------------------------------------------------------- main


def _refuse(msg: str) -> int:
    print(msg, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None, *, runner=subprocess.run) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=None)
    # The free-string --s7-receipt-ref is RETIRED (thirteenth round): the
    # ceremony now mints, consumes, verifies and RECORDS the S7 receipt
    # itself. Dry-run rehearses the same rail against caller-supplied
    # temp paths; --for-real binds to the canonical paths only.
    parser.add_argument(
        "--s7-store-path",
        type=Path,
        default=None,
        help="dry-run only: rehearsal S7 store holding a consumed "
        "birth authorization (never the real store)",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="dry-run only: rehearsal creation-manifest file "
        "(for-real always reads config/creation_manifest.md)",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="dry-run only: the ceremony run id the rehearsal "
        "authorization was minted and consumed under",
    )
    parser.add_argument("--owner-witness", default="rohit")
    parser.add_argument("--for-real", action="store_true")
    parser.add_argument(
        "--resume-services",
        action="store_true",
        help="finish the bring-up of an ALREADY-COMMITTED birth; never writes",
    )
    args = parser.parse_args(argv)

    if args.resume_services:
        return _main_resume(args, runner=runner)
    if not args.for_real:
        return _main_dry_run(args)
    return _main_for_real(args, runner=runner)


def _main_dry_run(args) -> int:
    if args.db_path is None:
        return _refuse(
            "--dry-run requires --db-path (a temp path, never the real ledger)"
        )
    if args.s7_store_path is None or args.manifest_path is None:
        return _refuse(
            "--dry-run requires --s7-store-path and --manifest-path "
            "(rehearsal copies; the rail runs at full fidelity)"
        )
    if not args.run_id.strip():
        return _refuse(
            "--dry-run requires --run-id — the id the rehearsal "
            "authorization was consumed under"
        )
    try:
        result = run_transaction(
            db_path=args.db_path,
            run_id=args.run_id,
            s7_store_path=args.s7_store_path,
            manifest_path=args.manifest_path,
            owner_witness=args.owner_witness,
            dry_run=True,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        from core.governance.birth_authorization import BirthAuthorizationRefusal

        if isinstance(exc, BirthAuthorizationRefusal):
            print(str(exc), file=sys.stderr)
            return 2
        raise
    print(
        f"birth transaction committed: turn={result['birth_turn_id']} "
        f"db={result['db_path']}"
    )
    print("\nOWNER CHECKLIST (remaining ceremony steps — your hands):")
    print("  4. Land MAEZ_LEDGER_WRITES=1 in the owner-local env path (dated comment).")
    print("     NOTE: maez-web.service loads NO EnvironmentFile (verified "
          "2026-08-24) — wire the flag into a maez-web drop-in too, or web "
          "turns are silently omitted from admission.")
    print("  5. systemctl --user restart maez.service && systemctl --user "
          "restart maez-web.service")
    print("  6. Run the six live witnesses (spec, 'The ceremony itself' step 6).")
    print("  7. Commit the receipts bundle to docs/proof.")
    print("  (For real, the script sequences 5 itself with explicit terminal "
          "states; --resume-services finishes an interrupted bring-up.)")
    return 0


def _require_owner_tty() -> bool:
    return sys.stdin.isatty()


def _canonical_db_or_refuse(args) -> Path | None:
    canonical = Path(birth_phase.default_ledger_path())
    db_path = Path(args.db_path) if args.db_path else canonical
    if db_path.resolve() != canonical.resolve():
        return None
    return db_path


def _main_resume(args, *, runner=subprocess.run) -> int:
    if not _require_owner_tty():
        return _refuse("REFUSED: --resume-services requires an interactive owner TTY")
    db_path = _canonical_db_or_refuse(args)
    if db_path is None:
        return _refuse(
            "REFUSED: --resume-services binds to the canonical ledger path "
            "only — no --db-path aliases"
        )
    verdict = classify_commit(db_path)
    if verdict != "COMMITTED":
        return _refuse(
            f"REFUSED: --resume-services only finishes a COMMITTED birth "
            f"(classification: {verdict}). It never writes."
        )
    started = time.time()
    state = _bring_up_after_commit(db_path, runner=runner)
    receipt = {
        "mode": "resume_services",
        "started_at": started,
        "db_path": str(db_path),
        "commit_classification": verdict,
        "terminal_state": state,
        "finished_at": time.time(),
    }
    path = _write_receipt(db_path, receipt)
    print(f"terminal state: {state}  (receipt: {path})")
    return 0 if state == COMMITTED_ACTIVE else 1


def _mint_for_ceremony(*, run_id: str, params: dict) -> dict:
    """The mint+consume phase, module-level so the choreography tests can
    stub it while the real rail is exercised by its own named tests. The
    production path hosts the existing S7 guarded ceremony with the
    PRODUCTION verifier — the owner taps the physical key."""
    from core.governance import birth_authorization as _birth_auth

    return _birth_auth.mint_and_consume_birth_authorization(
        store_root=_birth_auth.canonical_s7_store_path().parent,
        run_id=run_id,
        params=params,
    )


def _main_for_real(args, *, runner=subprocess.run) -> int:
    from core.governance import birth_authorization as _birth_auth

    if not _require_owner_tty():
        return _refuse("REFUSED: --for-real requires an interactive owner TTY")
    try:
        # The env-override CLASS refuses before anything else (executed
        # finding: MAEZ_LEDGER_DB_PATH made a decoy pass the canonical
        # check; the class is every path redirector).
        _birth_auth.refuse_env_overrides()
    except _birth_auth.BirthAuthorizationRefusal as exc:
        return _refuse(f"REFUSED: {exc}")
    if args.s7_store_path is not None or args.manifest_path is not None or args.run_id:
        return _refuse(
            "REFUSED: --s7-store-path/--manifest-path/--run-id are dry-run "
            "rehearsal knobs — --for-real binds to the canonical paths and "
            "mints its own run id"
        )
    db_path = _canonical_db_or_refuse(args)
    if db_path is None:
        return _refuse(
            "REFUSED: --for-real binds to the canonical ledger path only — "
            "a ceremony must not commit a decoy db while the daemon reads "
            "another"
        )
    preflight = classify_commit(db_path)
    if preflight == "COMMITTED":
        return _refuse(
            "REFUSED: this ledger is already birthed — we do not re-birth. "
            "If the bring-up was interrupted, run --resume-services."
        )
    if preflight != "NOT_COMMITTED":
        # Codex validation #2: an unclassifiable canonical db must never
        # enter the irreversible transaction — migration would stamp the
        # Maez schema onto whatever it is and launder it into COMMITTED.
        return _refuse(
            f"REFUSED: the canonical ledger classifies {preflight} — "
            "cannot prove it is an unborn Maez ledger. Hands off; "
            "recover/classify by hand before any ceremony."
        )
    typed = input(f'Type "{_CONFIRM_PHRASE}" to proceed: ').strip().lower()
    if typed != _CONFIRM_PHRASE:
        print("aborted: phrase mismatch — not born", file=sys.stderr)
        return 2

    # MINT + CONSUME while the services are still UP: the owner's browser
    # tap needs the cockpit origin alive. The consumed artifact is durable
    # and single-use; the transaction below re-verifies it from the store
    # under quiesce. A crash between here and the birth write spends the
    # receipt — the recovery is a re-tap, never a resume.
    run_id = _birth_auth.fresh_birth_run_id()
    try:
        manifest_sha = _birth_auth.read_manifest_sha256(
            _birth_auth.canonical_manifest_path()
        )
        mint_params = _birth_auth.birth_action_params(
            ledger_db_realpath=_birth_auth.canonical_ledger_realpath(),
            creation_manifest_sha256=manifest_sha,
            owner_witness=args.owner_witness,
            mode="for_real",
        )
        mint_facts = _mint_for_ceremony(run_id=run_id, params=mint_params)
    except _birth_auth.BirthAuthorizationRefusal as exc:
        return _refuse(f"REFUSED: {exc}")

    started = time.time()
    receipt = {
        "mode": "for_real",
        "started_at": started,
        "db_path": str(db_path),
        "phase": "CEREMONY_STARTED",
        "ceremony_run_id": run_id,
        "s7_artifact_id": mint_facts.get("s7_artifact_id"),
        # Freeze a hash, persist its pre-image: the ledger row carries
        # rendered_text_hash; the exact statement the owner read survives
        # here, in the durable ceremony journal beside the ledger.
        "s7_rendered_statement_text": mint_facts.get(
            "rendered_statement_text"
        ),
    }
    _write_receipt(db_path, receipt)

    # Record what was actually running BEFORE we touch anything, so a
    # restore never activates a unit the owner had deliberately stopped
    # (Codex validation #13). An unanswerable probe refuses pre-stop.
    try:
        initially_active = {
            unit: _unit_active_state(unit, runner=runner) == "active"
            for unit in _WRITER_UNITS
        }
    except RuntimeError as exc:
        return _refuse(f"REFUSED: cannot read unit states before stopping: {exc}")
    receipt["initially_active"] = initially_active

    # Stop web first (it Wants= the daemon but survives it), then the
    # daemon. Quiesce is then ASSERTED inside run_transaction.
    _stop_unit("maez-web.service", runner=runner)
    _stop_unit("maez.service", runner=runner)

    error: str | None = None
    try:
        result = run_transaction(
            db_path=db_path,
            run_id=run_id,
            s7_store_path=_birth_auth.canonical_s7_store_path(),
            manifest_path=_birth_auth.canonical_manifest_path(),
            owner_witness=args.owner_witness,
            dry_run=False,
            runner=runner,
        )
        receipt["birth_turn_id"] = result["birth_turn_id"]
    except QuiesceRefused as exc:
        receipt.update(
            {
                "phase": "QUIESCE_FAILED",
                "error": str(exc),
                "terminal_state": QUIESCE_FAILED_HANDS_OFF,
                "finished_at": time.time(),
            }
        )
        path = _write_receipt(db_path, receipt)
        print(str(exc), file=sys.stderr)
        print(
            f"terminal state: {QUIESCE_FAILED_HANDS_OFF} — something is "
            f"still alive; NOTHING was started or stopped further. "
            f"(receipt: {path})",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001 — classified below, honestly
        error = repr(exc)

    verdict = classify_commit(db_path)
    receipt["commit_classification"] = verdict
    if error:
        receipt["error"] = error

    if verdict == "COMMITTED":
        state = _bring_up_after_commit(db_path, runner=runner)
    elif verdict == "NOT_COMMITTED":
        state = (
            NOT_COMMITTED_SERVICES_RESTORED
            if _restore_services(
                runner=runner, initially_active=initially_active
            )
            else NOT_COMMITTED_SERVICES_DOWN
        )
    else:
        # UNKNOWN: restarting over an unprovable birth is the one
        # unrecoverable direction. Touch nothing. Loudest.
        state = COMMIT_STATUS_UNKNOWN_SERVICES_DOWN

    receipt.update({"terminal_state": state, "finished_at": time.time()})
    path = _write_receipt(db_path, receipt)

    if state == COMMITTED_ACTIVE:
        print(
            f"birth transaction committed: turn={receipt.get('birth_turn_id')} "
            f"db={db_path}"
        )
        print(f"terminal state: {state}  (receipt: {path})")
        print("\nOWNER CHECKLIST (remaining — your eyes):")
        print("  6. Run the six live witnesses (spec, 'The ceremony itself' step 6).")
        print("  7. Commit the receipts bundle to docs/proof.")
        return 0

    loud = {
        COMMITTED_WEB_MUTE: (
            "birth COMMITTED; daemon is live and owns the ledger; maez-web "
            "is UP but cannot see MAEZ_LEDGER_WRITES (no EnvironmentFile) "
            "— every web turn will be SILENTLY OMITTED from admission. "
            "Wire the flag into a maez-web drop-in and restart maez-web."
        ),
        COMMITTED_WEB_DOWN: (
            "birth COMMITTED; daemon is live and owns the ledger; maez-web "
            "FAILED to start and was left stopped. Fix web, then "
            "systemctl --user start maez-web.service."
        ),
        COMMITTED_SERVICES_DOWN: (
            "birth COMMITTED but the daemon could not be brought up as the "
            "proven owner. Both units are STOPPED — deliberately. Do NOT "
            "re-run the birth. Land/verify the activation flag, then run "
            "--resume-services."
        ),
        NOT_COMMITTED_SERVICES_RESTORED: (
            "birth did NOT commit (ledger verified intact, no anchor). "
            "Services were restored. Investigate the error above, then "
            "re-run the ceremony."
        ),
        NOT_COMMITTED_SERVICES_DOWN: (
            "birth did NOT commit, and service restore FAILED — units are "
            "stopped. Investigate before starting anything."
        ),
        COMMIT_STATUS_UNKNOWN_SERVICES_DOWN: (
            "COMMIT STATUS UNKNOWN — the ledger could not be classified "
            "(unreadable or failed integrity). NOTHING was restarted. Do "
            "NOT re-run the birth. Recover the db (backups exist), "
            "classify by hand, then decide."
        ),
    }[state]
    print(f"terminal state: {state}  (receipt: {path})", file=sys.stderr)
    print(loud, file=sys.stderr)
    if error:
        print(f"transaction error: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    _ensure_vendored_sqlite()
    raise SystemExit(main())
