# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Mark a queued capability acquisition completed.

Step 5d of the Decision-19/20 pipeline. After a capability
implementation has landed and tests pass, this CLI files an
activation registry row and transitions the queue row to
'completed' atomically (registry FIRST, queue SECOND).

The CLI assumes it runs inside the Maez repo so ``git cat-file -e``
can validate the supplied commit SHA.

Usage::

    python -m scripts.capability_mark_completed \\
        --queue-id acq-abcd1234 \\
        --capability-id temporal-arithmetic-at-recall \\
        --commit b617234 \\
        --files core/memory/temporal_arithmetic.py \\
        --tests tests/test_temporal_arithmetic.py \\
        --notes "Step 5c"

Pass ``--supersedes <prior_registry_id>`` when this completion
replaces a previously-active capability of the same id.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.capability_mark_completed",
        description=(
            "Mark a queued capability completed (Step 5d). Files an "
            "activation registry row and transitions the queue. "
            "Atomicity: registry FIRST, queue SECOND, idempotent on "
            "queue_id so retry after a partial failure is safe."
        ),
    )
    p.add_argument("--queue-id", required=True)
    p.add_argument("--capability-id", required=True)
    p.add_argument("--commit", required=True, dest="commit_sha")
    p.add_argument(
        "--files", nargs="+", default=[],
        help="Implementation files (relative to repo root).",
    )
    p.add_argument(
        "--tests", nargs="+", default=[],
        help="Test files (relative to repo root).",
    )
    p.add_argument(
        "--notes", default=None,
        help="Free-form notes attached to the registry row.",
    )
    p.add_argument(
        "--supersedes", default=None,
        help="Prior registry id this completion replaces; default "
             "behaviour rejects a duplicate active capability.",
    )
    p.add_argument(
        "--queue-db", type=Path, default=None,
        help="Override queue DB path.",
    )
    p.add_argument(
        "--registry-db", type=Path, default=None,
        help="Override registry DB path.",
    )
    args = p.parse_args(argv)

    from core.capability_acquisition_queue import AcquisitionQueue
    from core.capability_activation_registry import (
        ActivationRegistry, CompletionError, RegistryError,
        complete,
    )

    queue = (
        AcquisitionQueue(args.queue_db)
        if args.queue_db else AcquisitionQueue()
    )
    registry = (
        ActivationRegistry(args.registry_db)
        if args.registry_db else ActivationRegistry()
    )

    try:
        reg_id = complete(
            queue=queue,
            registry=registry,
            queue_id=args.queue_id,
            capability_id=args.capability_id,
            commit_sha=args.commit_sha,
            implementation_files=list(args.files),
            tests=list(args.tests),
            notes=args.notes,
            supersedes=args.supersedes,
        )
    except (CompletionError, RegistryError) as e:
        print(f"completion error: {e}", file=sys.stderr)
        return 2

    row = registry.get(reg_id)
    print(
        f"Capability {args.capability_id} marked completed.\n"
        f"  registry id:  {reg_id}\n"
        f"  queue id:     {args.queue_id}\n"
        f"  commit:       {args.commit_sha}\n"
        f"  status:       {row['status']}\n"
        f"  completed_at: {row['completed_at']}\n"
        f"  files:        {row['implementation_files']}\n"
        f"  tests:        {row['tests']}"
    )
    if args.supersedes:
        print(f"  supersedes:   {args.supersedes}")
    print(
        "\nNOTE: This records that the implementation has landed and "
        "tests have been run. activated_at remains null — runtime "
        "activation (when the daemon picks up the new code) is a "
        "separate event and may be recorded later by the daemon.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
