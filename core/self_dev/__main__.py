# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""CLI entry point for `python -m core.self_dev`.

Delegates to the package's argparser defined in __init__.py, preserving
the pre-Phase-3 behavior where `python -m core.self_dev <subcommand>`
ran the self-dev CLI.
"""
import logging
import sys

from core.self_dev import _build_argparser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_parser = _build_argparser()
_ns = _parser.parse_args()
sys.exit(_ns.func(_ns))
