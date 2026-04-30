# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""``python -m core.capability_evaluator '<query>'`` — runs the
matcher then the evaluator and prints JSON.

Exit codes:
  0 : evaluations produced (some may be defer/reject; that's OK —
      the CLI just reports the ranked answer)
  1 : matcher returned no candidates to evaluate
  2 : argparse / CLI error
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _evaluation_to_dict(ev) -> dict:
    return {
        "capability_id": ev.capability_id,
        "title": ev.title,
        "match_score": round(ev.match_score, 4),
        "decision": ev.decision,
        "reasons": [
            {
                "code": r.code,
                "severity": r.severity,
                "message": r.message,
                "evidence": r.evidence,
            }
            for r in ev.reasons
        ],
        "missing_prerequisites": ev.missing_prerequisites,
        "external_prerequisites": ev.external_prerequisites,
        "covenant_touch": ev.covenant_touch,
        "consent_card_required": ev.consent_card_required,
        "exact_phrase_ratification": ev.exact_phrase_ratification,
        "hardware_snapshot": ev.hardware_snapshot,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m core.capability_evaluator",
        description=(
            "Match a felt-limitation query, then evaluate each "
            "candidate. Returns ranked structured evaluations "
            "(eligible / defer / reject) with reasons. Step 3 of "
            "the capability pipeline; does NOT generate proposals."
        ),
    )
    p.add_argument("query", type=str, help="Felt-limitation phrasing.")
    p.add_argument(
        "--include-deprecated", action="store_true",
        help="Include deprecated entries in matching (default: excluded).",
    )
    p.add_argument(
        "--limit", type=int, default=5,
        help="Cap on candidates evaluated (default: 5).",
    )
    p.add_argument(
        "--root", type=Path, default=None,
        help="Manual directory (default: docs/maez_manual).",
    )
    args = p.parse_args(argv)

    from core.capability_evaluator import evaluate_matches
    from core.capability_gap_matcher import clear_cache, match_gap
    from core.capability_manual import load_manual

    if args.root is not None:
        manual = load_manual(args.root)
    else:
        clear_cache()
        manual = None

    matches = match_gap(
        args.query, manual=manual,
        include_deprecated=args.include_deprecated,
        limit=args.limit,
    )
    if not matches:
        print(json.dumps([], indent=2))
        return 1

    evaluations = evaluate_matches(matches, manual=manual)
    print(json.dumps(
        [_evaluation_to_dict(ev) for ev in evaluations],
        indent=2, sort_keys=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
