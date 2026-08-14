#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""OWNER-RUN. Prepare the live ceremony store for the R11 cutover.

Two phases, deliberately separate commands rather than one:

    python3 -m scripts.s7_prepare_store migrate    # v1 -> v2 plane
    python3 -m scripts.s7_prepare_store provision  # R11 evidence table

Bundled, a failure in the second leaves the store mid-way with no clean
statement of where it is. Separate, the read-only preflight can be run
between them and will say exactly what happened.

BOTH PHASES WRITE TO THE STORE HOLDING THE FOUNDER CREDENTIALS. Rehearse
first -- `python3 -m scripts.s7_migration_rehearsal` runs this whole
sequence against a byte-identical COPY and reports what it did -- so the
live run repeats something already observed rather than attempting it for
the first time.

Each phase takes a backup of the store beside itself before writing, and
prints the before/after digest so the change is visible rather than
asserted.
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORE_DIR = REPO / "memory" / "s7_1_webauthn"
STORE = STORE_DIR / "ceremony.sqlite3"


def _read_via(dir_fd: int, name: str) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
    try:
        chunks = []
        offset = 0
        while True:
            chunk = os.pread(fd, 1024 * 1024, offset)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            offset += len(chunk)
    finally:
        os.close(fd)


def _digest_via(dir_fd: int, name: str) -> str:
    return hashlib.sha256(_read_via(dir_fd, name)).hexdigest()


def _backup(label: str, dir_fd: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"ceremony.sqlite3.pre-{label}-{stamp}.bak"
    payload = _read_via(dir_fd, STORE.name)
    fd = os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=dir_fd
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    if _digest_via(dir_fd, name) != hashlib.sha256(payload).hexdigest():
        raise SystemExit("backup does not match the store; refusing to proceed")
    return name


def _run_phase(label: str, work) -> int:
    # ONE held descriptor from before the backup until after the write
    # (Codex review, 2026-08-14): the previous shape took the backup under
    # a pathname observation and then let the phase re-walk the canonical
    # path, so a directory swap in between meant the backup covered store
    # A while the migration -- and the printed restore instruction --
    # targeted store B. Every read, the backup, and the phase itself now
    # go through this fd; the pathname is walked exactly once.
    try:
        dir_fd = os.open(
            STORE_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
    except FileNotFoundError:
        print(f"live store dir absent: {STORE_DIR}")
        return 1
    try:
        try:
            before = _digest_via(dir_fd, STORE.name)
            start_stat = os.stat(STORE.name, dir_fd=dir_fd, follow_symlinks=False)
        except FileNotFoundError:
            print(f"live store absent: {STORE}")
            return 1
        print(f"store before : {before}")
        backup_name = _backup(label, dir_fd)
        print(f"backup       : {backup_name}")
        try:
            work(dir_fd)
        except Exception as exc:
            # Loud, and never mistaken for an ordinary refusal. The backup
            # above is the recovery path; its name is printed before any
            # write, and the digest below reads through the SAME held fd.
            print(f"\nPHASE FAILED: {type(exc).__name__}: {exc}")
            print(f"store is at  : {_digest_via(dir_fd, STORE.name)}")
            print(f"restore with : cp {STORE_DIR / backup_name} {STORE}")
            return 1
        after = _digest_via(dir_fd, STORE.name)
        # The LEAF must still be the inode the phase started on (Codex
        # third pass): the held dir fd anchors the directory, not the
        # database file, so a concurrent tool replacing the leaf mid-
        # phase would leave the backup covering one store and the writes
        # on another. The migration mutates in place, so identity is
        # stable across an honest run.
        end_stat = os.stat(STORE.name, dir_fd=dir_fd, follow_symlinks=False)
        if (start_stat.st_dev, start_stat.st_ino) != (
            end_stat.st_dev,
            end_stat.st_ino,
        ):
            print("\nPHASE FAILED: the store file was replaced mid-phase")
            print(f"backup covers the ORIGINAL store: {backup_name}")
            return 1
    finally:
        os.close(dir_fd)
    print(f"store after  : {after}")
    print("\nunchanged." if after == before else "\nstore updated.")
    print("Now run:  python3 -m scripts.s7_r11_preflight")
    return 0


def phase_migrate(dir_fd: int) -> None:
    # Through the descriptor-injection helper ON PURPOSE (reversal of
    # d2f4f29's rewiring, Codex review 2026-08-14): the public edge
    # re-walks the canonical path, which reopened the swap window between
    # the backup and the migration. The held fd IS the store the backup
    # covered; the migration must target exactly that inode. The private
    # helper's callsite allowlist names this caller and why.
    from core.governance import s7_v2_migration as migration

    migration._migrate_authorization_store_to_v2_at(store_dir_fd=dir_fd)


def phase_provision(dir_fd: int) -> None:
    from core.governance import s7_guarded_execution as guarded

    guarded._provision_r11_exemption_evidence_at(store_dir_fd=dir_fd)


PHASES = {"migrate": phase_migrate, "provision": phase_provision}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in PHASES:
        print(__doc__)
        print(f"phases: {', '.join(PHASES)}")
        return 2
    label = argv[1]
    print(f"S7 store preparation -- phase: {label}")
    print(f"store: {STORE}\n")
    return _run_phase(label, PHASES[label])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
