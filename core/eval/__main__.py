# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""CLI driver for the LongMemEval adapter.

Usage::

    python -m core.eval --questions data/longmemeval/longmemeval_oracle.json --limit 10
    python -m core.eval --questions ... --report docs/eval/longmemeval_2026-04-29.md

Stays deliberately thin — the heavy lifting lives in ``longmemeval.py``;
this is just argument plumbing + a per-type aggregate report.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean


def _aggregate_by_type(results: list[dict]) -> dict:
    by_type: dict[str, list[float]] = defaultdict(list)
    for r in results:
        by_type[str(r.get("question_type") or "unknown")].append(
            float(r.get("score") or 0.0)
        )
    return {
        qtype: {
            "n": len(scores),
            "mean_score": round(mean(scores), 4) if scores else 0.0,
        }
        for qtype, scores in sorted(by_type.items())
    }


def _format_report(results: list[dict], aggregate: dict) -> str:
    lines: list[str] = [
        "# LongMemEval — Maez subset run",
        "",
        f"Total questions: {len(results)}",
    ]
    if results:
        scores = [float(r.get("score") or 0.0) for r in results]
        lines += [
            f"Mean score (token-overlap lower bound): {mean(scores):.4f}",
            "",
            "## By question type",
            "",
            "| type | n | mean score |",
            "|---|---|---|",
        ]
        for qtype, agg in aggregate.items():
            lines.append(f"| {qtype} | {agg['n']} | {agg['mean_score']} |")
    lines += ["", "## Notes", ""]
    lines += [
        "- Score is a token-overlap heuristic, NOT the official GPT-4o judge.",
        "- Use as a recall-floor signal until the judge wires up (Session 2).",
        "- Each question runs in an isolated tmpdir MemoryManager — the live store is never touched.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.eval",
        description="Run a subset of LongMemEval through Maez's memory stack.",
    )
    parser.add_argument(
        "--questions", required=True,
        help="Path to a LongMemEval JSON file "
             "(e.g. longmemeval_oracle.json).",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="Number of questions to run (default 10).",
    )
    parser.add_argument(
        "--report", type=str, default=None,
        help="Optional markdown report path. Stdout always shows the summary.",
    )
    parser.add_argument(
        "--json-out", type=str, default=None,
        help="Optional path for the per-question JSON results.",
    )
    args = parser.parse_args(argv)

    qpath = Path(args.questions)
    if not qpath.is_file():
        print(
            f"questions file not found: {qpath}\n"
            "  download via: "
            "https://huggingface.co/datasets/xiaowu0162/longmemeval",
            file=sys.stderr,
        )
        return 2

    from core.eval.longmemeval import run_subset

    try:
        results = run_subset(qpath, limit=args.limit)
    except ValueError as e:
        print(f"failed to load/run questions: {e}", file=sys.stderr)
        return 2
    aggregate = _aggregate_by_type(results)
    report = _format_report(results, aggregate)
    print(report)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(report, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
