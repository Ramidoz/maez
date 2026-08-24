# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Maez ledger reconciliation CLI.

Wraps ``core.ledger.reconcile.reconcile`` with the operator surface
described in docs/ledger/envelope-schema.md §6.2.

Usage:
    python scripts/reconcile_ledger.py LEDGER_DB \\
        --audit-log AUDIT_DB \\
        --fabrication-log FAB_DB \\
        --pending-cards CARDS_DB \\
        --self-mod-dialogs SMOD_DB \\
        [--apply] [--json] [--quiet]

Default mode is dry-run (no writes, ``mode=ro`` reads only). Pass
--apply to ENQUEUE a synthetic ``system_event`` repair for each detected
orphan through the admission spool — the live owner (daemon) drains and
commits them; this CLI never opens the ledger for writing (owner-client
contract, council 2026-08-24). --apply additionally requires
``MAEZ_LEDGER_WRITES=1`` in the environment.

Exit codes:
    0 = clean (no orphans, or repairs enqueued/pending with --apply)
    1 = orphans found in dry-run mode (operator must --apply)
    2 = error (DB missing/malformed/era missing/MAEZ_LEDGER_WRITES off)
    3 = state_c turns detected (only if no higher-priority signal)

Precedence: 2 > 1 > 3 > 0.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root with `python scripts/reconcile_ledger.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.ledger import reconcile  # noqa: E402


def _parse_args(argv: list | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="reconcile_ledger",
        description=(
            "Reconcile cross-DB FK orphans between the Maez ledger and "
            "its four external dependent DBs (audit_log, "
            "fabrication_events, pending_cards, self_mod_dialogs). "
            "Default is dry-run; --apply requires MAEZ_LEDGER_WRITES=1."
        ),
    )
    parser.add_argument("ledger_db",
        help="Path to the ledger SQLite database file.")
    parser.add_argument("--audit-log", dest="audit_log",
        required=True, help="Path to the audit_log SQLite DB.")
    parser.add_argument("--fabrication-log", dest="fabrication_log",
        required=True, help="Path to the fabrication_events SQLite DB.")
    parser.add_argument("--pending-cards", dest="pending_cards",
        required=True, help="Path to the pending_cards SQLite DB.")
    parser.add_argument("--self-mod-dialogs", dest="self_mod_dialogs",
        required=True, help="Path to the self_mod_dialogs SQLite DB.")
    parser.add_argument("--apply", action="store_true",
        help="Apply synthetic repair writes (requires MAEZ_LEDGER_WRITES=1).")
    parser.add_argument("--force-low-era", action="store_true",
        help="Override the low-era guard. Required when era<2001 + many "
             "orphans + --apply (would otherwise refuse to flood the "
             "ledger with synthetic rows for pre-existing dependent rows).")
    parser.add_argument("--json", dest="emit_json", action="store_true",
        help="Emit a single JSON object on stdout instead of human text.")
    parser.add_argument("--quiet", action="store_true",
        help="Suppress all stdout/stderr on the success path.")
    return parser.parse_args(argv)


def _print_human(result: dict) -> None:
    orph = result["orphans_found"]
    total = sum(len(v) for v in orph.values())
    print(
        f"Reconciliation: era={result['ledger_era_starts_at']:.6f}, "
        f"orphans={total}, repairs_enqueued={result['repairs_enqueued']}, "
        f"verdict={result['verdict']}"
    )
    for key in ("audit_log", "fabrication_events",
                "pending_cards", "self_mod_dialogs"):
        ids = orph.get(key, [])
        if ids:
            print(f"  {key}: {len(ids)} orphan(s) -> {ids}")
    state_c = result.get("state_c_turns") or []
    if state_c:
        print(
            f"  state_c: {len(state_c)} was_rewritten turn(s) without "
            f"claims (detect-only): {state_c}"
        )


def main(argv: list | None = None) -> int:
    args = _parse_args(argv)

    # Pre-flight: ledger DB must exist on disk.
    if not Path(args.ledger_db).exists():
        if not args.quiet:
            print(
                f"error: ledger DB does not exist: {args.ledger_db!r}",
                file=sys.stderr,
            )
        return 2

    # External DBs are tolerated as missing (treated as State A by the
    # reconciler), but a typo in --audit-log etc. is a common operator
    # mistake. We surface a friendly warning to stderr if any external
    # path doesn't exist; the reconciler proceeds with empty results
    # for those tables.
    for label, path in (
        ("--audit-log", args.audit_log),
        ("--fabrication-log", args.fabrication_log),
        ("--pending-cards", args.pending_cards),
        ("--self-mod-dialogs", args.self_mod_dialogs),
    ):
        if not Path(path).exists() and not args.quiet:
            print(
                f"warning: {label} path does not exist: {path!r} "
                f"(treating as empty / State A)",
                file=sys.stderr,
            )

    try:
        result = reconcile.reconcile(
            args.ledger_db,
            audit_log_db_path=args.audit_log,
            fabrication_log_db_path=args.fabrication_log,
            pending_cards_db_path=args.pending_cards,
            self_mod_dialogs_db_path=args.self_mod_dialogs,
            dry_run=not args.apply,
            force_low_era=args.force_low_era,
        )
    except RuntimeError as e:
        if not args.quiet:
            print(f"error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        if not args.quiet:
            print(f"error: reconciliation failed: {e}", file=sys.stderr)
        return 2

    # Determine exit code with documented precedence: 2 > 1 > 3 > 0.
    # (2 already handled in except blocks above.)
    total_orphans = sum(len(v) for v in result["orphans_found"].values())
    has_state_c = bool(result.get("state_c_turns"))

    if not args.apply and total_orphans > 0:
        exit_code = 1
    elif has_state_c:
        exit_code = 3
    else:
        exit_code = 0

    if not args.quiet:
        if args.emit_json:
            print(json.dumps(result, sort_keys=True))
        else:
            _print_human(result)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
