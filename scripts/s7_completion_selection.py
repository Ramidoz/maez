#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""OWNER-RUN. List the completed bench runs, and write the one you choose.

The cutover ceremony reads ONE owner-written file naming which completed
run it is authorizing. That file must be byte-canonical: the reader rebuilds
the canonical bytes and refuses anything that differs, so a stray space or a
reordered key produces `completion_locator_unavailable` with no hint why.
Hand-writing it is a trap; this writes it correctly.

    python3 -m scripts.s7_completion_selection            # list candidates
    python3 -m scripts.s7_completion_selection --select N # write choice N

Choosing is the owner's act -- this names what the founder tap authorizes.
The helper shows what each candidate actually is and refuses to guess.
"""

from __future__ import annotations

import json
import os
import stat as stat_module
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BENCH_ROOT = REPO / "local" / "cuda_migration_bench"
SELECTION_NAME = "cutover-completion-selection.json"


def _candidates() -> list[dict[str, str]]:
    """Completed command terminals, newest last, with what they point at."""
    found: list[dict[str, str]] = []
    for path in sorted(BENCH_ROOT.glob("command-*-terminal.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        fields = payload.get("fields", payload)
        if not isinstance(fields, dict):
            continue
        if fields.get("status") != "completed":
            continue
        ref = fields.get("artifact_ref")
        if not isinstance(ref, str) or not ref:
            continue
        found.append(
            {
                "artifact_ref": ref,
                "command": str(fields.get("command", "?")),
                "window_id": str(fields.get("window_id", "?")),
                "timestamp": str(fields.get("timestamp", "?")),
                "terminal": path.name,
            }
        )
    found.sort(key=lambda c: c["timestamp"])
    return found


def _write_selection(locator: str) -> Path:
    from scripts import cuda_cutover
    from scripts import cuda_migration as cm

    # Validated with the SAME predicates the reader uses, before writing --
    # so a bad choice is refused here rather than at ceremony time.
    cm._validate_private_ref(locator)
    from scripts import cuda_bench_driver as driver

    driver._relative_parts(locator)

    wrapper = {
        "schema": cuda_cutover.COMPLETION_SELECTION_SCHEMA,
        "fields": {"completion_locator": locator},
    }
    payload = cm._canonical_wrapper_bytes(wrapper)

    root_stat = BENCH_ROOT.stat()
    if stat_module.S_IMODE(root_stat.st_mode) != 0o700:
        raise SystemExit(
            f"{BENCH_ROOT} must be mode 0700 (it is "
            f"0{stat_module.S_IMODE(root_stat.st_mode):o})"
        )

    target = BENCH_ROOT / SELECTION_NAME
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    target.chmod(0o600)

    # Read it back through the REAL reader, so success here means the
    # ceremony will accept it -- not merely that a file was written.
    readback = cuda_cutover._read_owner_completion_locator()
    if readback != locator:
        raise SystemExit(f"written file did not read back as chosen: {readback!r}")
    return target


def main(argv: list[str]) -> int:
    candidates = _candidates()
    if not candidates:
        print(f"no completed command terminals found under {BENCH_ROOT}")
        return 1

    if "--select" not in argv:
        print(f"Completed bench runs under {BENCH_ROOT.name}:\n")
        for index, cand in enumerate(candidates, start=1):
            print(f"  [{index}] {cand['command']}  window {cand['window_id']}")
            print(f"      at   {cand['timestamp']}")
            print(f"      ref  {cand['artifact_ref']}")
        current = BENCH_ROOT / SELECTION_NAME
        print(
            f"\ncurrent selection: "
            f"{'none written' if not current.exists() else current.name}"
        )
        print("\nChoose with:  python3 -m scripts.s7_completion_selection --select N")
        print("This lists only; it wrote nothing.")
        return 0

    try:
        choice = int(argv[argv.index("--select") + 1])
        chosen = candidates[choice - 1]
    except (IndexError, ValueError):
        print(f"--select needs a number between 1 and {len(candidates)}")
        return 2

    print(f"selecting [{choice}] {chosen['command']}  window {chosen['window_id']}")
    print(f"  ref: {chosen['artifact_ref']}")
    target = _write_selection(chosen["artifact_ref"])
    print(f"\nwrote {target} (mode 0600), and it reads back correctly.")
    print("Now run:  python3 -m scripts.s7_r11_preflight")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
