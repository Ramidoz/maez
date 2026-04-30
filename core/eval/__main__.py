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
    by_type_judge: dict[str, list[int]] = defaultdict(list)
    for r in results:
        qt = str(r.get("question_type") or "unknown")
        by_type[qt].append(float(r.get("score") or 0.0))
        js = r.get("judge_score")
        if js is not None:
            by_type_judge[qt].append(int(js))
    out: dict = {}
    for qtype in sorted(by_type):
        scores = by_type[qtype]
        agg = {
            "n": len(scores),
            "mean_score": round(mean(scores), 4) if scores else 0.0,
        }
        if by_type_judge.get(qtype):
            agg["judge_n"] = len(by_type_judge[qtype])
            agg["judge_accuracy"] = round(mean(by_type_judge[qtype]), 4)
        out[qtype] = agg
    return out


def _format_report(results: list[dict], aggregate: dict) -> str:
    lines: list[str] = [
        "# LongMemEval — Maez subset run",
        "",
        f"Total questions: {len(results)}",
    ]
    if results:
        scores = [float(r.get("score") or 0.0) for r in results]
        judges = [int(r["judge_score"]) for r in results
                  if r.get("judge_score") is not None]
        lines += [
            f"Mean score (token-overlap lower bound): {mean(scores):.4f}",
        ]
        if judges:
            lines.append(
                f"Judge accuracy ({len(judges)} judged): {mean(judges):.4f}"
            )
        lines += ["", "## By question type", ""]
        if judges:
            lines += [
                "| type | n | mean score | judge n | judge accuracy |",
                "|---|---|---|---|---|",
            ]
            for qtype, agg in aggregate.items():
                lines.append(
                    f"| {qtype} | {agg['n']} | {agg['mean_score']} | "
                    f"{agg.get('judge_n', '-')} | "
                    f"{agg.get('judge_accuracy', '-')} |"
                )
        else:
            lines += ["| type | n | mean score |", "|---|---|---|"]
            for qtype, agg in aggregate.items():
                lines.append(
                    f"| {qtype} | {agg['n']} | {agg['mean_score']} |"
                )
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
    parser.add_argument(
        "--judge", action="store_true",
        help="Run the LLM judge on each question. "
             "Default provider is local (llama-server); pass "
             "--judge-provider sonnet/opus/haiku to route through "
             "the subscription proxy instead.",
    )
    parser.add_argument(
        "--judge-provider",
        choices=("local", "sonnet", "opus", "haiku", "gpt-4o", "gpt-5"),
        default="local",
        help="Which LLM judges the answers. 'local' = llama-server "
             "via llm_client; 'sonnet'/'opus'/'haiku' route through "
             "the Claude subscription via claude_tier; 'gpt-4o'/"
             "'gpt-5' route through OpenAI. GPT-4o matches the "
             "judge used in the published LongMemEval paper.",
    )
    parser.add_argument(
        "--with-surfaced", action="store_true",
        help="Include the raw surfaced recall text in --json-out "
             "records (bloats the file; useful for offline judging).",
    )
    parser.add_argument(
        "--ids-from", type=str, default=None,
        help="Optional path to a newline-delimited list of "
             "question_ids to restrict the run to (post-load filter; "
             "limit still caps).",
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

    ids: set[str] | None = None
    if args.ids_from:
        ids_path = Path(args.ids_from)
        if not ids_path.is_file():
            print(
                f"--ids-from file not found: {ids_path}", file=sys.stderr,
            )
            return 2
        ids = {
            line.strip() for line in ids_path.read_text().splitlines()
            if line.strip()
        }
        if not ids:
            print(
                f"--ids-from file is empty: {ids_path}", file=sys.stderr,
            )
            return 2
        if args.limit < len(ids):
            print(
                f"--ids-from has {len(ids)} ids but --limit is "
                f"{args.limit}; results will be truncated to {args.limit}. "
                "Pass a higher --limit to keep the stratified sample.",
                file=sys.stderr,
            )
    try:
        results = run_subset(
            qpath,
            limit=args.limit,
            with_judge=args.judge,
            with_surfaced=args.with_surfaced,
            question_ids=ids,
            judge_provider=args.judge_provider,
        )
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
