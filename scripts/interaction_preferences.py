#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.infra import paths
from core.interaction_preferences.store import (
    InteractionPreferencesStore,
    get_readonly,
    list_all_readonly,
)


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _statement_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _db_path(args: argparse.Namespace) -> Path:
    return Path(args.db) if args.db else paths.interaction_preferences_db()


def _store(args: argparse.Namespace) -> InteractionPreferencesStore:
    return InteractionPreferencesStore(_db_path(args))


def _cmd_list(args: argparse.Namespace) -> int:
    rows = list_all_readonly(_db_path(args))
    for row in rows:
        print(
            f"{row.preference_id}\t{row.status}\t{row.preference_class}\t"
            f"{row.created_at}\t{row.owner_statement}"
        )
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    row = get_readonly(_db_path(args), args.preference_id)
    if row is None:
        print(f"not found: {args.preference_id}", file=sys.stderr)
        return 1
    for field in (
        "preference_id",
        "created_at",
        "updated_at",
        "status",
        "preference_class",
        "owner_statement",
        "source_ref",
        "surface",
        "statement_sha256",
        "supersedes_preference_id",
        "superseded_by_preference_id",
        "retraction_reason",
        "revision_statement",
    ):
        print(f"{field}: {getattr(row, field)}")
    return 0


def _cmd_retract(args: argparse.Namespace) -> int:
    if not args.owner_approved:
        print("retract requires --owner-approved", file=sys.stderr)
        return 2
    store = _store(args)
    existing = store.get(args.preference_id)
    if existing is None:
        print(f"not found: {args.preference_id}", file=sys.stderr)
        return 1
    if existing.status != "active":
        print(f"not active: {args.preference_id}", file=sys.stderr)
        return 1
    reason = str(args.reason or "").strip()
    if not reason:
        print("retract requires --reason", file=sys.stderr)
        return 2
    now = _now_utc()
    new_id = f"retract-{uuid.uuid4().hex}"
    store.record_retraction(
        preference_id=new_id,
        preference_class=existing.preference_class,
        owner_statement=reason,
        source_ref=f"script:retract:{existing.preference_id}:{new_id}",
        surface="script",
        statement_sha256=_statement_sha(reason),
        supersedes_preference_id=existing.preference_id,
        retraction_reason=reason,
        created_at=now,
    )
    print(f"retracted {existing.preference_id} via {new_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect owner interaction preferences.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List active and historical preferences")
    list_p.add_argument("--db", default=None, help="Override interaction_preferences.db path")
    list_p.set_defaults(func=_cmd_list)

    show_p = sub.add_parser("show", help="Show one preference")
    show_p.add_argument("preference_id")
    show_p.add_argument("--db", default=None, help="Override interaction_preferences.db path")
    show_p.set_defaults(func=_cmd_show)

    retract_p = sub.add_parser("retract", help="Retract one active preference")
    retract_p.add_argument("preference_id")
    retract_p.add_argument("--reason", required=True)
    retract_p.add_argument("--owner-approved", action="store_true")
    retract_p.add_argument("--db", default=None, help="Override interaction_preferences.db path")
    retract_p.set_defaults(func=_cmd_retract)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
