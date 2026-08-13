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
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORE_DIR = REPO / "memory" / "s7_1_webauthn"
STORE = STORE_DIR / "ceremony.sqlite3"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _backup(label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = STORE_DIR / f"ceremony.sqlite3.pre-{label}-{stamp}.bak"
    if target.exists():
        raise SystemExit(f"refusing to overwrite an existing backup: {target}")
    shutil.copyfile(STORE, target)
    target.chmod(0o600)
    if _digest(target) != _digest(STORE):
        raise SystemExit("backup does not match the store; refusing to proceed")
    return target


def _run_phase(label: str, work) -> int:
    if not STORE.exists():
        print(f"live store absent: {STORE}")
        return 1
    before = _digest(STORE)
    print(f"store before : {before}")
    backup = _backup(label)
    print(f"backup       : {backup.name}")

    dir_fd = os.open(STORE_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        work(dir_fd)
    except Exception as exc:
        # Loud, and never mistaken for an ordinary refusal. The backup above
        # is the recovery path and its name is printed before any write.
        print(f"\nPHASE FAILED: {type(exc).__name__}: {exc}")
        print(f"store is at  : {_digest(STORE)}")
        print(f"restore with : cp {backup} {STORE}")
        return 1
    finally:
        os.close(dir_fd)

    after = _digest(STORE)
    print(f"store after  : {after}")
    print("\nunchanged." if after == before else "\nstore updated.")
    print("Now run:  python3 -m scripts.s7_r11_preflight")
    return 0


def phase_migrate(dir_fd: int) -> None:
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
