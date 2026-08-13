#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""READ-ONLY preflight: can the R11 cutover ceremony run against this store?

Answers one question per check, and CANNOT change anything. The store is
opened `mode=ro` so a write is refused by SQLite itself rather than by this
module's good intentions; a test fails if that mode ever changes.

Run it before migrating, after migrating, and after provisioning. It is
cheap and repeatable on purpose: the owner should never have to infer the
store's state from what a previous command claimed.

    python3 -m scripts.s7_r11_preflight

Exit status is 0 when every check passes, 1 otherwise. A FAIL is a fact,
not an error -- a store that has not been migrated yet is expected to fail
the v2 checks, and the point is to say so plainly.
"""

from __future__ import annotations

import sqlite3
import stat as stat_module
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORE = REPO / "memory" / "s7_1_webauthn" / "ceremony.sqlite3"
RECEIPT = STORE.parent / "s7_migration_receipt.json"

#: SQLite URI mode. Pinned as a module constant so the "cannot write" test
#: has something exact to assert against; changing it must break that test.
READ_ONLY_URI_MODE = "ro"

V2_AUTH_TABLE = "s7_authorization_artifacts_v2"
#: The real table, read from the module that owns it rather than
#: retyped here -- I first invented a name and the preflight cheerfully
#: reported a table that would never exist.
from core.governance.s7_guarded_execution import (  # noqa: E402
    R11_EXEMPTION_EVIDENCE_TABLE as R11_EVIDENCE_TABLE,
)
CREDENTIALS_TABLE = "s7_founder_webauthn_credentials"


class Check:
    __slots__ = ("name", "passed", "detail")

    def __init__(self, name: str, passed: bool, detail: str) -> None:
        self.name = name
        self.passed = passed
        self.detail = detail


def _open_read_only(path: Path) -> sqlite3.Connection:
    """Open strictly read-only. SQLite enforces it, not this module."""
    return sqlite3.connect(f"file:{path}?mode={READ_ONLY_URI_MODE}", uri=True)


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _check_store_present() -> Check:
    if not STORE.exists():
        return Check("store present", False, f"absent: {STORE}")
    mode = stat_module.S_IMODE(STORE.stat().st_mode)
    if mode != 0o600:
        return Check("store present", False, f"mode is 0{mode:o}, expected 0600")
    return Check("store present", True, f"mode 0600, {STORE.stat().st_size} bytes")


def _check_v2_activated(tables: set[str]) -> Check:
    has_table = V2_AUTH_TABLE in tables
    has_receipt = RECEIPT.exists()
    if has_table and has_receipt:
        return Check("v2 plane activated", True, "table and migration receipt present")
    # Creating the table is NOT activation: the receipt is what says the
    # migration actually ran, and guarded execution refuses without it.
    missing = []
    if not has_table:
        missing.append(f"{V2_AUTH_TABLE} absent")
    if not has_receipt:
        missing.append(f"{RECEIPT.name} absent")
    return Check("v2 plane activated", False, "; ".join(missing))


def _check_r11_evidence(tables: set[str]) -> Check:
    if R11_EVIDENCE_TABLE in tables:
        return Check("R11 evidence table", True, "present")
    return Check("R11 evidence table", False, f"{R11_EVIDENCE_TABLE} absent")


def _check_credentials(conn: sqlite3.Connection, tables: set[str]) -> Check:
    if CREDENTIALS_TABLE not in tables:
        return Check("founder credential", False, f"{CREDENTIALS_TABLE} absent")
    try:
        rows = list(
            conn.execute(
                f"SELECT credential_ref, enabled, role_names_json "
                f"FROM {CREDENTIALS_TABLE}"
            )
        )
    except sqlite3.DatabaseError as exc:
        return Check("founder credential", False, f"unreadable: {type(exc).__name__}")
    usable = [
        ref
        for ref, enabled, roles in rows
        if enabled and "bonded_user" in (roles or "")
    ]
    if usable:
        return Check(
            "founder credential",
            True,
            f"{len(usable)} of {len(rows)} enabled and bonded_user",
        )
    return Check(
        "founder credential",
        False,
        f"none of {len(rows)} are enabled with bonded_user",
    )


def _check_bench_receipt() -> Check:
    from core.governance import s7_consultation_exemption as exemption

    if exemption._quality_receipt_still_matches():
        return Check("bench receipt", True, "present and matches the frozen hash")
    path = exemption.R11_QUALITY_EVIDENCE_PATH
    return Check(
        "bench receipt",
        False,
        "absent or altered" if path.exists() else f"absent: {path}",
    )


def _check_not_born() -> Check:
    from core.governance import s7_consultation_exemption as exemption

    if exemption.born_by_any_signal():
        return Check("pre-birth", False, "birth signalled -- R11 has expired")
    return Check("pre-birth", True, "no birth signal; R11 still applies")


def _check_cutover_authorization() -> Check:
    """The document the ceremony actually consumes.

    Added after the preflight reported READY while this was absent: it
    checked the database and the locator but never the authority itself, so
    the owner would have discovered it by running the ceremony. It is
    time-boxed (4h) and boot-bound on purpose, so it is minted shortly
    before the ceremony -- an expired or stale-boot one must FAIL here
    rather than at the execution edge.
    """
    from scripts import cuda_cutover
    from scripts import cuda_migration as cm

    path = cuda_cutover.BENCH_ROOT / cuda_cutover.AUTHORIZATION_NAME
    if not path.exists():
        return Check(
            "cutover authorization",
            False,
            f"absent: {cuda_cutover.AUTHORIZATION_NAME} -- mint it before the ceremony",
        )
    try:
        doc = cm.PersistedDoc(path.read_bytes()).obj
    except Exception as exc:
        return Check(
            "cutover authorization", False, f"unreadable: {type(exc).__name__}: {exc}"
        )
    if type(doc) is not cm.CutoverAuthorizationDoc:
        return Check("cutover authorization", False, "not a cutover authorization")

    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        expires = datetime.datetime.strptime(
            doc.expires_at, "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return Check("cutover authorization", False, "expiry is not canonical")
    if expires <= now:
        return Check(
            "cutover authorization", False, f"EXPIRED at {doc.expires_at} -- re-mint"
        )

    try:
        boot_now = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        boot_now = ""
    if boot_now and doc.boot_id != boot_now:
        return Check(
            "cutover authorization",
            False,
            "boot id differs from this boot -- the host restarted since minting",
        )
    remaining = int((expires - now).total_seconds() // 60)
    return Check(
        "cutover authorization",
        True,
        f"window {doc.window_id}, {remaining} min remaining, boot matches",
    )


def _check_completion_locator() -> Check:
    from scripts import cuda_cutover

    try:
        locator = cuda_cutover._read_owner_completion_locator()
    except Exception as exc:
        return Check(
            "completion locator", False, f"unreadable: {type(exc).__name__}: {exc}"
        )
    return Check("completion locator", True, f"readable: {locator}")


def _check_pinned_sources() -> Check:
    """Every file the burn would pin, against the ceremony's OWN predicate.

    Added after the live run: the CUDA override and both llama unit files
    were group-writable, and the ceremony was the first thing to look. The
    predicate is imported from the ceremony, never re-encoded here, so a
    report of PASS and a mid-ceremony refusal cannot disagree. Read-only:
    each candidate is opened O_RDONLY and only fstat'd, exactly as the pin
    does, without reading a byte.
    """
    import os
    from scripts import cuda_cutover

    candidates: list[tuple[Path, str, int | None, bool]] = [
        (path, f"recovery-source:{leaf}", os.getuid(), False)
        for path, leaf in cuda_cutover.CUTOVER_RECOVERY_SOURCES
    ]
    candidates.append(
        (cuda_cutover.CUTOVER_OVERRIDE_SOURCE, "cuda-override-source", os.getuid(), False)
    )
    try:
        fragments = cuda_cutover._resolve_user_unit_fragments(
            cuda_cutover.CUTOVER_UNIT_NAMES
        )
    except Exception as exc:
        return Check(
            "pinned sources",
            False,
            f"unit fragments unresolvable: {type(exc).__name__}: {exc}",
        )
    candidates.extend(
        (path, f"unit-fragment:{unit_name}", os.getuid(), False)
        for unit_name, path in fragments.items()
    )
    candidates.extend(
        (path, label, None, True)
        for path, label in (
            (cuda_cutover.CUTOVER_INSTALL_EXECUTABLE, "install-executable"),
            (cuda_cutover.CUTOVER_SYSTEMCTL_EXECUTABLE, "systemctl-executable"),
        )
    )

    failures: list[str] = []
    for path, label, expected_uid, executable in candidates:
        fd = -1
        try:
            selected = path.resolve(strict=True) if executable else path
            fd = os.open(selected, os.O_RDONLY | os.O_NOFOLLOW)
            violation = cuda_cutover._pinned_file_mode_violation(
                os.fstat(fd), expected_uid=expected_uid, executable=executable
            )
        except OSError as exc:
            violation = f"unopenable: {type(exc).__name__}"
        finally:
            if fd >= 0:
                os.close(fd)
        if violation:
            failures.append(f"{label}: {violation}")
    if failures:
        return Check("pinned sources", False, "; ".join(failures))
    return Check(
        "pinned sources", True, f"{len(candidates)} files pass the pin predicate"
    )


def _check_pinned_directories() -> Check:
    """Both directories the burn would pin; the 775 finding, pre-ceremony.

    Same discipline as `_check_pinned_sources`: the ceremony's predicate,
    imported, applied to the ceremony's constants, fstat only.
    """
    import os
    from scripts import cuda_cutover

    targets = (
        (Path(cuda_cutover.BENCH_ROOT) / "recovery", "cutover-recovery-directory"),
        (cuda_cutover.CUTOVER_OVERRIDE_DIRECTORY, "systemd-user-override-directory"),
    )
    failures: list[str] = []
    for path, label in targets:
        fd = -1
        try:
            fd = cuda_cutover.s7._open_directory_by_components(path)
            violation = cuda_cutover._pinned_directory_mode_violation(
                os.fstat(fd), expected_uid=os.getuid()
            )
        except OSError as exc:
            violation = f"unopenable: {type(exc).__name__}"
        finally:
            if fd >= 0:
                os.close(fd)
        if violation:
            failures.append(f"{label}: {violation}")
    if failures:
        return Check("pinned directories", False, "; ".join(failures))
    return Check(
        "pinned directories", True, f"{len(targets)} directories pass the pin predicate"
    )


def run_preflight() -> list[Check]:
    """Every check, in order. Never raises for an ordinary FAIL."""
    checks: list[Check] = [_check_store_present()]
    if not checks[0].passed:
        return checks

    conn = _open_read_only(STORE)
    try:
        tables = _table_names(conn)
        checks.append(_check_v2_activated(tables))
        checks.append(_check_r11_evidence(tables))
        checks.append(_check_credentials(conn, tables))
    finally:
        conn.close()

    for probe in (
        _check_bench_receipt,
        _check_not_born,
        _check_completion_locator,
        _check_cutover_authorization,
        _check_pinned_sources,
        _check_pinned_directories,
    ):
        try:
            checks.append(probe())
        except Exception as exc:  # a broken probe is a FAIL, never a crash
            checks.append(Check(probe.__name__, False, f"{type(exc).__name__}: {exc}"))
    return checks


def main() -> int:
    checks = run_preflight()
    width = max(len(c.name) for c in checks)
    for check in checks:
        mark = "PASS" if check.passed else "FAIL"
        print(f"  [{mark}] {check.name.ljust(width)}  {check.detail}")
    ready = all(c.passed for c in checks)
    print()
    print(
        "READY: the ceremony's preconditions hold."
        if ready
        else "NOT READY: the checks above marked FAIL must be resolved first."
    )
    print("This preflight is read-only. It changed nothing.")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
