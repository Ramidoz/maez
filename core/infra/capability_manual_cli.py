# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""CLI entry for the capability manual loader/validator.

Usage::

    python -m core.capability_manual validate
    python -m core.capability_manual validate --root /path/to/manual
    python -m core.capability_manual validate --json

Exits 1 on any validation error, 0 if clean or warnings-only.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path


def _summary(result, *, as_json: bool) -> str:
    if as_json:
        return json.dumps({
            "entries": [
                {
                    "capability_id": e.capability_id,
                    "title": e.title,
                    "status": e.status,
                    "source_path": str(e.source_path),
                }
                for e in result.entries
            ],
            "errors": [asdict(i) for i in result.errors],
            "warnings": [asdict(i) for i in result.warnings],
        }, indent=2, sort_keys=True)

    lines: list[str] = []
    lines.append(f"loaded {len(result.entries)} entries")
    for e in result.entries:
        lines.append(f"  - {e.capability_id} [{e.status}] — {e.title}")
    if result.errors:
        lines.append("")
        lines.append(f"errors ({len(result.errors)}):")
        for i in result.errors:
            lines.append(f"  ✗ [{i.capability_id}] {i.code}: {i.message}")
    if result.warnings:
        lines.append("")
        lines.append(f"warnings ({len(result.warnings)}):")
        for i in result.warnings:
            lines.append(f"  ⚠ [{i.capability_id}] {i.code}: {i.message}")
    if not result.errors and not result.warnings:
        lines.append("")
        lines.append("manual is clean — no errors, no warnings.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m core.capability_manual",
        description=(
            "Capability manual loader/validator (Decision 19/20 "
            "step 1). Validates docs/maez_manual/*.md against the "
            "schema in BAD §19."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)
    val = sub.add_parser(
        "validate",
        help="Load and validate the manual; exit 1 on errors.",
    )
    val.add_argument(
        "--root", type=Path, default=None,
        help="Manual directory (default: docs/maez_manual).",
    )
    val.add_argument(
        "--json", action="store_true",
        help="Emit a JSON summary instead of human-readable text.",
    )
    args = p.parse_args(argv)

    if args.command == "validate":
        from core.capability_manual import load_manual

        result = load_manual(args.root)
        print(_summary(result, as_json=args.json))
        return 1 if result.errors else 0

    return 2  # unknown command — argparse will have raised already


if __name__ == "__main__":
    raise SystemExit(main())
