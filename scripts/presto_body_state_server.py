#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Compatibility entry point for the Presto bedside state relay."""

from hardware.presto.body_state_server import main


if __name__ == "__main__":
    raise SystemExit(main())
