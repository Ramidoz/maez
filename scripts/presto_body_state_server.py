#!/usr/bin/env python3
"""Compatibility entry point for the Presto bedside state relay."""

from hardware.presto.body_state_server import main


if __name__ == "__main__":
    raise SystemExit(main())
