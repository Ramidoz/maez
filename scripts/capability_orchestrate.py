# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Run the capability-acquisition orchestrator on a felt-limitation.

Stages 2 → 3 → 4 → 4b of the Decision-19/20 pipeline. Match the
limitation against the manual, evaluate matches against current
hardware, generate proposals, and (when ``--commit`` is passed)
create real PendingCards on each eligible proposal.

Stage 1 (autonomous gap-sensing) is out of scope; this CLI is the
operator-driven entry point that lets the owner say "I felt this
limitation today" and walk it through the full pipeline.

Usage::

    python -m scripts.capability_orchestrate "when did X happen?"
    python -m scripts.capability_orchestrate "..." --commit
    python -m scripts.capability_orchestrate "..." --include-deferred
    python -m scripts.capability_orchestrate "..." --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.capability_orchestrate",
        description=(
            "Orchestrate stages 2-4 of the capability-acquisition "
            "pipeline against a single felt-limitation string. "
            "Default is dry-run (no card created); --commit creates "
            "real PendingCards for every eligible proposal."
        ),
    )
    p.add_argument(
        "felt_limitation",
        help="Natural-language description of what Maez can't do.",
    )
    p.add_argument(
        "--commit", action="store_true",
        help="Create real PendingCards. Default is dry-run.",
    )
    p.add_argument(
        "--include-deferred", action="store_true",
        help="Surface deferred/rejected proposals in the output "
             "(no cards are created for them either way).",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit structured JSON instead of human-readable text.",
    )
    p.add_argument(
        "--limit", type=int, default=5,
        help="Cap on matches considered (default 5).",
    )
    args = p.parse_args(argv)

    from core.infra.capability_orchestrator import (
        orchestrate_from_felt_limitation,
    )
    pcs = None
    if args.commit:
        from core.decision.pending_cards import PendingCardStore
        pcs = PendingCardStore()

    r = orchestrate_from_felt_limitation(
        args.felt_limitation,
        pending_card_store=pcs,
        include_deferred=args.include_deferred,
        limit=args.limit,
    )

    if args.json:
        out = {
            "felt_limitation": r.felt_limitation,
            "matches": [
                {"capability_id": m.capability_id, "title": m.title,
                 "score": m.score, "matched_signals": m.matched_signals}
                for m in r.matches
            ],
            "evaluations": [
                {"capability_id": e.capability_id, "decision": e.decision}
                for e in r.evaluations
            ],
            "proposals": [
                {"proposal_id": p.proposal_id,
                 "capability_id": p.capability_id,
                 "evaluation_decision": p.evaluation_decision,
                 "actionable": p.actionable}
                for p in r.proposals
            ],
            "cards_created": r.cards_created,
            "cards_skipped": r.cards_skipped,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    # Human-readable
    print(f"felt_limitation: {r.felt_limitation!r}")
    print(f"matches: {len(r.matches)}")
    for m in r.matches:
        print(f"  - {m.capability_id} (score={m.score:.2f}) "
              f"signals={m.matched_signals}")
    print(f"evaluations: {len(r.evaluations)}")
    for e in r.evaluations:
        print(f"  - {e.capability_id}: {e.decision}")
    print(f"proposals: {len(r.proposals)}")
    for p in r.proposals:
        flag = "[ACTIONABLE]" if p.actionable else "[non-actionable]"
        print(f"  - {p.capability_id}: {p.evaluation_decision} {flag}")
    if args.commit:
        print(f"cards_created: {len(r.cards_created)}")
        for rid in r.cards_created:
            print(f"  - {rid}")
        if r.cards_skipped:
            print(f"cards_skipped: {len(r.cards_skipped)}")
            for cap_id, reason in r.cards_skipped:
                print(f"  - {cap_id}: {reason}")
    else:
        print("(dry run — pass --commit to create real cards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
