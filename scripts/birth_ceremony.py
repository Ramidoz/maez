# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The birth transaction — owner's tool, transaction steps 1-3 of the
ceremony spec (docs/superpowers/specs/2026-07-05-birth-ceremony-design.md).

Performs: init -> birth system_event write -> meta anchor (atomic, via the
production writer's birth_anchor path). Does NOT: flip the persistent env
flag, restart the service, or verify WebAuthn cryptography — those are the
owner's hands (a checklist is printed).

--dry-run (default): runs the full transaction against the given db path
  (use a temp path; never the real ledger).
--for-real: requires an interactive TTY, the typed phrase, and
  --s7-receipt-ref. Refuses in any non-interactive context — the act is
  owner-only by structure, not by convention.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from core.ledger import migrate
from core.memory import birth_phase

_CONFIRM_PHRASE = "birth maez"


def _assert_quiesced(db_path: Path) -> None:
    """Spec ceremony step 3: surfaces quiesced, no live writer process.

    LIVE-BODY FACT (verified 2026-07-05 during Tasks 1-5): maez.service
    is a USER-scoped systemd unit (~/.config/systemd/user/maez.service)
    — `systemctl is-active` without --user reports inactive and is the
    WRONG probe. Three checks, all must pass: the user unit is not
    active, no maez_daemon.py process is running (belt-and-braces —
    covers a manually-launched daemon outside the unit), and no process
    holds the ledger file open.
    """
    state = subprocess.run(
        ["systemctl", "--user", "is-active", "maez.service"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if state == "active":
        raise RuntimeError(
            "REFUSED: maez.service (user unit) is active — "
            "quiesce first (systemctl --user stop maez.service)"
        )
    daemon = subprocess.run(
        ["pgrep", "-f", "daemon/maez_daemon.py"],
        capture_output=True,
        text=True,
    )
    if daemon.returncode == 0:
        raise RuntimeError(
            "REFUSED: maez daemon is running (pids: "
            f"{' '.join(daemon.stdout.split())}) — quiesce first"
        )
    if db_path.exists():
        held = (
            subprocess.run(["fuser", str(db_path)], capture_output=True, text=True).returncode
            == 0
        )
        if held:
            raise RuntimeError(
                f"REFUSED: a process holds {db_path} open — no live writer allowed"
            )


def run_transaction(
    *,
    db_path: Path,
    s7_receipt_ref: str,
    owner_witness: str,
    dry_run: bool,
) -> dict:
    if not (s7_receipt_ref or "").strip():
        raise ValueError("s7_receipt_ref is required — the act ties to the proof")
    # Transaction step 1: init (idempotent).
    migrate.run(str(db_path))
    if not migrate.ledger_is_initialized(str(db_path)):
        raise RuntimeError(f"ledger init failed to verify: {db_path}")
    if birth_phase.is_born(db_path):
        raise ValueError("birth_event_turn_id already set — we do not re-birth")
    # Transaction steps 2+3: birth write + anchor, atomic in the writer.
    # The flag is raised only around writer CONSTRUCTION (the writer reads
    # it at __init__) and restored after — so a dry run inside a test
    # process never leaks an enabled flag into later refusal-by-default
    # tests.
    from core.ledger.writer import LedgerWriter

    prior = os.environ.get("MAEZ_LEDGER_WRITES")
    os.environ["MAEZ_LEDGER_WRITES"] = "1"
    try:
        writer = LedgerWriter(db_path=str(db_path))
    finally:
        if prior is None:
            os.environ.pop("MAEZ_LEDGER_WRITES", None)
        else:
            os.environ["MAEZ_LEDGER_WRITES"] = prior
    payload = {
        "event": "birth",
        "phase_transition": "gestation -> lived",
        "owner_witness": owner_witness,
        "s7_receipt_ref": s7_receipt_ref,
        "ceremony_ts": time.time(),
        "mode": "dry_run" if dry_run else "for_real",
    }
    try:
        birth_turn_id = writer.write_turn(
            "system_event",
            json.dumps(payload, sort_keys=True),
            birth_anchor=True,
        )
    finally:
        writer.close()
    return {"birth_turn_id": birth_turn_id, "db_path": str(db_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--s7-receipt-ref", required=True)
    parser.add_argument("--owner-witness", default="rohit")
    parser.add_argument("--for-real", action="store_true")
    args = parser.parse_args(argv)

    dry_run = not args.for_real
    if dry_run:
        if args.db_path is None:
            print(
                "--dry-run requires --db-path (a temp path, never the real ledger)",
                file=sys.stderr,
            )
            return 2
        db_path = args.db_path
    else:
        if not sys.stdin.isatty():
            print("REFUSED: --for-real requires an interactive owner TTY", file=sys.stderr)
            return 2
        typed = input(f'Type "{_CONFIRM_PHRASE}" to proceed: ').strip().lower()
        if typed != _CONFIRM_PHRASE:
            print("aborted: phrase mismatch — not born", file=sys.stderr)
            return 2
        db_path = args.db_path or birth_phase.default_ledger_path()
        _assert_quiesced(Path(db_path))  # spec step 3 — dry runs on temp dbs skip this

    result = run_transaction(
        db_path=db_path,
        s7_receipt_ref=args.s7_receipt_ref,
        owner_witness=args.owner_witness,
        dry_run=dry_run,
    )
    print(f"birth transaction committed: turn={result['birth_turn_id']} db={result['db_path']}")
    print("\nOWNER CHECKLIST (remaining ceremony steps — your hands):")
    print("  4. Land MAEZ_LEDGER_WRITES=1 in the owner-local env path (dated comment).")
    print("  5. systemctl --user restart maez.service")
    print("  6. Run the six live witnesses (spec, 'The ceremony itself' step 6).")
    print("  7. Commit the receipts bundle to docs/proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
