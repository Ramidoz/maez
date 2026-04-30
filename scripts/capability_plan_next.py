# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Generate an integration plan for a queued capability acquisition.

Step 5a of the Decision-19/20 pipeline. The planner reads one row
from the acquisition queue, revalidates it against the manual entry,
and emits a draft *plan* — never an installation.

Usage::

    python -m scripts.capability_plan_next
    python -m scripts.capability_plan_next --id acq-abcdef123456
    python -m scripts.capability_plan_next --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.capability_plan_next",
        description=(
            "Plan capability integration from a queued acquisition "
            "intent (Step 5a). Produces a reviewable plan only — "
            "nothing is fetched, installed, or modified."
        ),
    )
    p.add_argument(
        "--id", dest="queue_id", default=None,
        help="Plan against a specific queue row id "
             "(default: oldest queued row).",
    )
    p.add_argument(
        "--db", type=Path, default=None,
        help="Override queue DB path (default: "
             "memory/capability_acquisition_queue.db).",
    )
    p.add_argument(
        "--manual-root", type=Path, default=None,
        help="Override the manual root used for path containment "
             "(default: <repo>/docs/maez_manual).",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit JSON (default: human-readable plan).",
    )
    args = p.parse_args(argv)

    from core.capability_acquisition_queue import AcquisitionQueue
    from core.capability_integration_planner import (
        IntegrationPlannerError, plan_next,
    )

    queue = AcquisitionQueue(args.db) if args.db else AcquisitionQueue()
    try:
        plan = plan_next(
            queue,
            queue_id=args.queue_id,
            manual_root=args.manual_root,
        )
    except IntegrationPlannerError as e:
        print(f"planner error: {e}", file=sys.stderr)
        return 2

    if plan is None:
        print("(no queued acquisition rows to plan)")
        print(
            "NOTE: Step 5a is the planner; nothing is fetched or "
            "installed by listing or by planning. Step 5b/5c "
            "(later) will consume reviewed plans.",
            file=sys.stderr,
        )
        return 0

    if args.json:
        print(json.dumps(asdict(plan), indent=2, sort_keys=True, default=str))
        return 0

    print(plan.render_text())
    print()
    print(
        "NOTE: This planner does NOT fetch code, install dependencies, "
        "modify Maez files, or mark the queue completed. It produces "
        "an integration plan only. Acting on the plan is a separate "
        "slice (Step 5b/5c), gated by additional consent at that time.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
