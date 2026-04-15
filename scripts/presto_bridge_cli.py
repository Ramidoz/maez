#!/usr/bin/env python3
"""
Small CLI for the Maez Presto bridge.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path("/home/rohit/maez")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.presto.bridge import PrestoBridge, PrestoBridgeError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and control a Pimoroni Presto for Maez.")
    parser.add_argument("--port", help="Explicit serial port, eg /dev/ttyACM0")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Print runtime information from the connected Presto.")
    sub.add_parser("ls", help="List root files on the Presto filesystem.")

    push = sub.add_parser("push", help="Copy a local .py file to the Presto.")
    push.add_argument("local_path")
    push.add_argument("--remote-name")

    launch = sub.add_parser("launch", help="Set the script launched on next reset.")
    launch.add_argument("script_name")

    read = sub.add_parser("read", help="Read a text file from the Presto.")
    read.add_argument("remote_path")

    sub.add_parser("reset", help="Soft-reset the Presto runtime.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        bridge = PrestoBridge(port=args.port)
        if args.cmd == "info":
            print(json.dumps(bridge.device_info(), indent=2, default=str))
        elif args.cmd == "ls":
            for name in bridge.list_root():
                print(name)
        elif args.cmd == "push":
            print(bridge.install_repo_app(args.local_path, args.remote_name))
        elif args.cmd == "launch":
            print(bridge.set_launch(args.script_name))
        elif args.cmd == "read":
            print(bridge.read_file(args.remote_path))
        elif args.cmd == "reset":
            print(bridge.soft_reset())
        else:
            parser.error(f"Unknown command {args.cmd}")
    except PrestoBridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
