# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""``python -m core.capability_proposal '<query>'`` — chains
matcher → evaluator → proposal generator and prints JSON.

Step 4 deliberately stops at "consent-card-ready proposal" — no
actual card is opened, no acquisition runs.

Exit codes:
  0 : at least one actionable=True proposal generated
  1 : matcher returned no candidates, OR no actionable proposals
  2 : argparse / CLI error
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path


def _proposal_to_dict(p) -> dict:
    """JSON-safe view, dropping the entry object reference."""
    d = asdict(p)
    d.pop("entry", None)
    # Round score for compact output.
    d["match_score"] = round(d["match_score"], 4)
    return d


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m core.capability_proposal",
        description=(
            "Chain matcher -> evaluator -> proposal generator. "
            "Step 4 produces consent-card-ready payloads but does "
            "NOT open cards. Card creation is Step 4b."
        ),
    )
    p.add_argument("query", type=str, help="Felt-limitation phrasing.")
    p.add_argument(
        "--include-deferred", action="store_true",
        help="Emit non-actionable explanatory artifacts for defer/"
             "reject evaluations alongside actionable proposals.",
    )
    p.add_argument(
        "--include-deprecated-matches", action="store_true",
        help="Include deprecated entries in the matcher stage.",
    )
    p.add_argument(
        "--limit", type=int, default=5,
        help="Cap on candidates considered (default: 5).",
    )
    p.add_argument(
        "--root", type=Path, default=None,
        help="Manual directory (default: docs/maez_manual).",
    )
    args = p.parse_args(argv)

    from core.capability_evaluator import evaluate_matches
    from core.capability_gap_matcher import clear_cache, match_gap
    from core.capability_manual import load_manual
    from core.capability_proposal import generate_proposals

    if args.root is not None:
        manual = load_manual(args.root)
    else:
        clear_cache()
        manual = None

    matches = match_gap(
        args.query, manual=manual,
        include_deprecated=args.include_deprecated_matches,
        limit=args.limit,
    )
    if not matches:
        print(json.dumps([], indent=2))
        return 1

    evaluations = evaluate_matches(matches, manual=manual)
    proposals = generate_proposals(
        args.query, evaluations,
        include_deferred=args.include_deferred,
    )

    print(json.dumps(
        [_proposal_to_dict(prop) for prop in proposals],
        indent=2, sort_keys=False,
    ))

    actionable = sum(1 for prop in proposals if prop.actionable)
    return 0 if actionable > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
