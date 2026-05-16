#!/usr/bin/env python3
"""Operator CLI for S5 voice-continuity ceremonies."""

from __future__ import annotations

import argparse
import json
import sys

from core.voice_continuity.owner_verdict_writer import mint_operator_origin_marker


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="S5 Voice Continuity Gate operator commands",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    marker = subparsers.add_parser(
        "mint-origin-marker",
        help="Mint an operator-origin marker bound to one S5 review package.",
    )
    marker.add_argument("--origin", required=True, choices=("operator_manual", "operator_cli_tty"))
    marker.add_argument("--attested-by", required=True)
    marker.add_argument("--review-id", required=True)
    marker.add_argument("--baseline-id", required=True)
    marker.add_argument("--review-package-hash", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "mint-origin-marker":
        marker = mint_operator_origin_marker(
            origin=args.origin,
            attested_by=args.attested_by,
            review_id=args.review_id,
            baseline_id=args.baseline_id,
            review_package_hash=args.review_package_hash,
            is_tty=sys.stdin.isatty(),
        )
        print(json.dumps(marker, sort_keys=True))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
