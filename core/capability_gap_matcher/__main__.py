# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""``python -m core.capability_gap_matcher "<query>"`` — prints
JSON match list. Useful for interactive smoke tests and CI checks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _match_to_dict(m) -> dict:
    """JSON-friendly view of a CapabilityMatch. Drops the full
    entry object (which includes the body markdown — too big for
    a CLI summary)."""
    return {
        "capability_id": m.capability_id,
        "title": m.title,
        "score": round(m.score, 4),
        "status": m.status,
        "matched_signals": m.matched_signals,
        "matched_terms": m.matched_terms,
        "source_path": (
            str(m.source_path) if m.source_path is not None else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m core.capability_gap_matcher",
        description=(
            "Rank manual entries by lexical overlap with a "
            "felt-limitation query. v1 deterministic; semantic "
            "upgrade is v1.5."
        ),
    )
    p.add_argument(
        "query", type=str,
        help="Felt-limitation phrasing — what the user / Maez can't do.",
    )
    p.add_argument(
        "--include-deprecated", action="store_true",
        help="Include deprecated entries in the result (default: excluded).",
    )
    p.add_argument(
        "--limit", type=int, default=5,
        help="Cap on returned matches (default: 5).",
    )
    p.add_argument(
        "--root", type=Path, default=None,
        help="Manual directory (default: docs/maez_manual).",
    )
    args = p.parse_args(argv)

    from core.capability_gap_matcher import (
        clear_cache, match_gap,
    )
    from core.capability_manual import load_manual

    if args.root is not None:
        manual = load_manual(args.root)
    else:
        clear_cache()  # reload the default manual on each CLI call
        manual = None

    matches = match_gap(
        args.query,
        manual=manual,
        include_deprecated=args.include_deprecated,
        limit=args.limit,
    )
    print(json.dumps(
        [_match_to_dict(m) for m in matches],
        indent=2, sort_keys=False,
    ))
    return 0 if matches else 1  # 1 on no match — useful for scripted callers


if __name__ == "__main__":
    raise SystemExit(main())
