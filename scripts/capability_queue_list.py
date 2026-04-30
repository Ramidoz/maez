# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""List capability-acquisition queue entries.

Step 4b of the Decision-19/20 pipeline. The queue records *intent*
— owner approved acquiring capability X — but does NOT actually
fetch or install. Step 5 (later) will consume this queue.

Usage::

    python -m scripts.capability_queue_list                # list open
    python -m scripts.capability_queue_list --all
    python -m scripts.capability_queue_list --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.capability_queue_list",
        description=(
            "List capability-acquisition queue entries (Step 4b). "
            "The queue records approved intent only; nothing has "
            "been fetched or installed."
        ),
    )
    p.add_argument(
        "--all", action="store_true",
        help="Include cancelled/completed/failed rows (default: open only).",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit JSON (default: human-readable summary).",
    )
    p.add_argument(
        "--db", type=Path, default=None,
        help="Override queue DB path (default: "
             "memory/capability_acquisition_queue.db).",
    )
    args = p.parse_args(argv)

    from core.capability_acquisition_queue import AcquisitionQueue

    queue = AcquisitionQueue(args.db) if args.db else AcquisitionQueue()
    rows = queue.list_all() if args.all else queue.list_open()

    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True, default=str))
        return 0

    if not rows:
        scope = "all" if args.all else "open"
        print(f"(no {scope} acquisition-queue entries)")
        return 0

    print(f"capability acquisition queue ({len(rows)} row(s)):\n")
    for r in rows:
        print(f"  [{r['status']}] {r['capability_id']}  ({r['id']})")
        print(f"    proposed: {r.get('reason') or '(no reason)'}")
        if r.get("proposal_id"):
            print(f"    proposal_id: {r['proposal_id']}")
        if r.get("card_request_id"):
            print(f"    card_request_id: {r['card_request_id']}")
        print(
            f"    source: {r['source']}  acquisition: {r['acquisition']}"
        )
        print()

    print(
        "NOTE: queue records APPROVED INTENT only. No code was "
        "fetched or installed by listing or by enqueueing. Actual "
        "integration is Step 5 (separate slice, gated by additional "
        "consent at that time).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
