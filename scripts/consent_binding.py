"""CLI for the conversational-consent owner-surface binding registry."""

from __future__ import annotations

import argparse
from dataclasses import asdict

from core.consent.bindings import BindingRegistry, ConsentBindingPaths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    enroll = sub.add_parser("enroll")
    enroll.add_argument("--surface-kind", required=True)
    enroll.add_argument("--surface-identity", required=True)

    revoke = sub.add_parser("revoke")
    revoke.add_argument("--binding-id", required=True)

    sub.add_parser("list")
    return parser


def main(argv: list[str] | None = None, *, paths: ConsentBindingPaths | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = BindingRegistry(paths)

    if args.command == "enroll":
        binding = registry.enroll(
            args.surface_kind,
            args.surface_identity,
            enrolled_via="cli",
        )
        print(binding.binding_id)
        return 0

    if args.command == "revoke":
        binding = registry.revoke(args.binding_id)
        print(binding.binding_id)
        return 0

    if args.command == "list":
        for binding in registry.list_bindings():
            row = asdict(binding)
            print(
                "\t".join(
                    [
                        row["binding_id"],
                        row["surface_kind"],
                        row["surface_identity"],
                        row["status"],
                    ]
                )
            )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
