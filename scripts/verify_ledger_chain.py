# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""End-to-end Maez ledger chain verification.

Walks a real SQLite ledger.db file, loads all turns/claims/claim_judgements,
and reports any chain or witness violations per docs/ledger/envelope-schema.md §6.

This script is strictly READ-ONLY. It opens the DB via the
``file:{path}?mode=ro`` URI and never issues any write. It is invoked by
the nightly orchestrator (Slice 2.4 reconciliation) and by Rohit ad-hoc.

Usage:
    # Human-readable summary, exits 0 clean / 1 violations / 2 error
    python scripts/verify_ledger_chain.py memory/ledger.db

    # JSON-shaped output (for orchestrator / pipelines)
    python scripts/verify_ledger_chain.py memory/ledger.db --json

    # Cron-friendly: silent, exit code only
    python scripts/verify_ledger_chain.py memory/ledger.db --quiet

Exit codes:
    0 = no violations (clean)
    1 = violations found (chain or witness mismatches)
    2 = error (DB missing, malformed, missing tables, missing/multiple genesis)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Allow running from repo root with `python scripts/verify_ledger_chain.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.ledger import chain  # noqa: E402


REQUIRED_TABLES = ("turns", "claims", "claim_judgements")


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def _open_readonly(db_path: str) -> sqlite3.Connection:
    """Open the SQLite DB in read-only mode via URI. Never writes."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _check_required_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    present = {r["name"] for r in rows}
    return [t for t in REQUIRED_TABLES if t not in present]


def _load_turns_in_chain_order(conn: sqlite3.Connection) -> list[dict]:
    """Load all turns from the DB in chain order.

    Walk strategy:
      1. Find the genesis row (prev_chain_hash IS NULL). Exactly one
         is expected; zero or multiple is a structural error (raise).
      2. From there, repeatedly look up the row whose prev_chain_hash
         equals the current row's chain_hash. Exactly one match means
         the chain continues; zero means the chain has ended; multiple
         means the chain has forked (raise).

    Returns turns as dicts in chain order.
    """
    all_rows = conn.execute("SELECT * FROM turns").fetchall()
    if not all_rows:
        return []

    rows_as_dicts = [_row_to_dict(r) for r in all_rows]

    by_prev: dict[object, list[dict]] = {}
    for row in rows_as_dicts:
        by_prev.setdefault(row["prev_chain_hash"], []).append(row)

    genesis_candidates = by_prev.get(None, [])
    if len(genesis_candidates) == 0:
        raise ValueError(
            "no genesis row found: every row in `turns` has a non-NULL "
            "prev_chain_hash. The chain has no start."
        )
    if len(genesis_candidates) > 1:
        ids = [r.get("turn_id") for r in genesis_candidates]
        raise ValueError(
            f"multiple genesis rows found ({len(genesis_candidates)}): "
            f"turn_ids={ids!r}. Exactly one row must have "
            f"prev_chain_hash IS NULL."
        )

    ordered: list[dict] = []
    seen_turn_ids: set = set()
    current = genesis_candidates[0]

    while True:
        turn_id = current.get("turn_id")
        if turn_id in seen_turn_ids:
            raise ValueError(
                f"chain cycle detected at turn_id={turn_id!r}; "
                f"chain walk revisited a row."
            )
        seen_turn_ids.add(turn_id)
        ordered.append(current)

        successors = by_prev.get(current["chain_hash"], [])
        if len(successors) == 0:
            break
        if len(successors) > 1:
            ids = [r.get("turn_id") for r in successors]
            raise ValueError(
                f"chain fork detected after turn_id={turn_id!r}: "
                f"{len(successors)} rows share prev_chain_hash="
                f"{current['chain_hash']!r}; turn_ids={ids!r}."
            )
        current = successors[0]

    if len(ordered) != len(rows_as_dicts):
        unreached = [
            r.get("turn_id") for r in rows_as_dicts
            if r.get("turn_id") not in seen_turn_ids
        ]
        raise ValueError(
            f"chain walk reached {len(ordered)} of {len(rows_as_dicts)} "
            f"rows; {len(unreached)} rows are not connected to the "
            f"primary chain. Unreached turn_ids (first 10): "
            f"{unreached[:10]!r}"
        )

    return ordered


def _load_claims(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM claims").fetchall()
    return [_row_to_dict(r) for r in rows]


def _load_judgements(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM claim_judgements").fetchall()
    return [_row_to_dict(r) for r in rows]


def _build_result(
    chain_violations: list[dict],
    claim_violations: list[dict],
    judgement_violations: list[dict],
    n_turns: int,
    n_claims: int,
    n_judgements: int,
) -> dict:
    total = (
        len(chain_violations)
        + len(claim_violations)
        + len(judgement_violations)
    )
    return {
        "chain_violations": chain_violations,
        "claim_violations": claim_violations,
        "judgement_violations": judgement_violations,
        "total_rows_walked": {
            "turns": n_turns,
            "claims": n_claims,
            "judgements": n_judgements,
        },
        "verdict": "pass" if total == 0 else "fail",
    }


def _print_human(result: dict) -> None:
    walked = result["total_rows_walked"]
    chain_v = result["chain_violations"]
    claim_v = result["claim_violations"]
    judg_v = result["judgement_violations"]

    print(
        f"Chain: {walked['turns']} rows verified, "
        f"{len(chain_v)} violations."
    )
    print(
        f"Claims: {walked['claims']} rows verified, "
        f"{len(claim_v)} witness violations."
    )
    print(
        f"Judgements: {walked['judgements']} rows verified, "
        f"{len(judg_v)} witness violations."
    )

    if chain_v:
        print("\n-- Chain violations --")
        for v in chain_v:
            print(f"  {v}")
    if claim_v:
        print("\n-- Claim witness violations --")
        for v in claim_v:
            print(f"  {v}")
    if judg_v:
        print("\n-- Judgement witness violations --")
        for v in judg_v:
            print(f"  {v}")

    print()
    print(f"Verdict: {result['verdict'].upper()}")


def _parse_args(argv: list | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify_ledger_chain",
        description=(
            "Walk a Maez ledger.db file and verify its chain + witness "
            "integrity. Read-only; never modifies the database."
        ),
    )
    parser.add_argument("db_path",
        help="Path to the ledger SQLite database file.")
    parser.add_argument("--json", dest="emit_json", action="store_true",
        help="Emit a single JSON object on stdout instead of human text.")
    parser.add_argument("--quiet", action="store_true",
        help="Suppress all output; report only via exit code (cron use).")
    return parser.parse_args(argv)


def main(argv: list | None = None) -> int:
    args = _parse_args(argv)

    try:
        conn = _open_readonly(args.db_path)
    except sqlite3.OperationalError as e:
        if not args.quiet:
            print(f"error: cannot open ledger DB at {args.db_path!r}: {e}",
                file=sys.stderr)
        return 2
    except sqlite3.Error as e:
        if not args.quiet:
            print(f"error: sqlite error opening {args.db_path!r}: {e}",
                file=sys.stderr)
        return 2

    try:
        missing = _check_required_tables(conn)
        if missing:
            if not args.quiet:
                print(
                    f"error: ledger DB at {args.db_path!r} is missing "
                    f"required tables: {missing!r}. Has migrate.run() "
                    f"been executed against this file?",
                    file=sys.stderr,
                )
            return 2

        try:
            turns = _load_turns_in_chain_order(conn)
        except ValueError as e:
            if not args.quiet:
                print(f"error: chain structure invalid: {e}", file=sys.stderr)
            return 2

        # Head-pointer check: the final reached row's chain_hash MUST
        # equal meta.last_chain_hash. Without this, truncation of the
        # chain tail (delete the last N rows) is undetectable —
        # internal consistency of the remaining rows would still pass.
        head_row = conn.execute(
            "SELECT value FROM meta WHERE key='last_chain_hash'"
        ).fetchone()
        head_violation: dict | None = None
        if head_row is None:
            head_violation = {
                "reason": "missing-head-pointer",
                "expected": "<meta.last_chain_hash row>",
                "actual": "(absent)",
            }
        elif turns:
            stored_head = head_row["value"]
            actual_head = turns[-1].get("chain_hash", "")
            if stored_head != actual_head:
                head_violation = {
                    "reason": "head-pointer-mismatch",
                    "expected": stored_head,
                    "actual": actual_head,
                    "note": (
                        "meta.last_chain_hash does not match the chain head. "
                        "This typically indicates the chain was truncated "
                        "(rows deleted from the tail) or the head pointer "
                        "was tampered with."
                    ),
                }

        claims = _load_claims(conn)
        judgements = _load_judgements(conn)
    except sqlite3.Error as e:
        if not args.quiet:
            print(f"error: sqlite error reading from {args.db_path!r}: {e}",
                file=sys.stderr)
        return 2
    finally:
        conn.close()

    turns_by_id = {t["turn_id"]: t for t in turns}
    claims_by_id = {c["claim_id"]: c for c in claims}

    try:
        chain_violations = chain.verify_chain(turns)
        if head_violation is not None:
            chain_violations = [*chain_violations, head_violation]
        claim_violations = chain.verify_claim_witnesses(turns_by_id, claims)
        judgement_violations = chain.verify_judgement_witnesses(
            claims_by_id, judgements
        )
    except Exception as e:  # pragma: no cover
        if not args.quiet:
            print(f"error: verifier raised unexpectedly: {e}",
                file=sys.stderr)
        return 2

    result = _build_result(
        chain_violations,
        claim_violations,
        judgement_violations,
        n_turns=len(turns),
        n_claims=len(claims),
        n_judgements=len(judgements),
    )

    if args.quiet:
        pass
    elif args.emit_json:
        print(json.dumps(result, sort_keys=True))
    else:
        _print_human(result)

    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
