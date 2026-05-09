#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Write one Slice X.0 moment assembly diagnostic record.

This is read-only/probe-only diagnostic infrastructure. It writes JSONL
diagnostics, not ledger truth, prompt context, or audit evidence.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from core.cognition.moment_assembly_diagnostic import (  # noqa: E402
    DEFAULT_LOG_PATH,
    build_diagnostic_record,
    write_diagnostic_record,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface", default="probe")
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    args = parser.parse_args(argv)

    record = build_diagnostic_record(
        surface=args.surface,
        source_ids=args.source_id or ["manual-probe"],
    )
    write_diagnostic_record(record=record, log_path=Path(args.log_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
