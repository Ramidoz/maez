#!/usr/bin/env python3
"""judge_bench/bench.py — compare grounding-judge candidates.

Runs the full test set through any llama.cpp-compatible OpenAI-style
endpoint and reports agreement with the expected verdicts, plus
latency percentiles. Compare multiple candidates by running with
different --url/--model pairs and pointing --report-csv at the same
file — rows accumulate.

Usage:
    # Baseline: current judge on whatever port it's running
    python scripts/judge_bench/bench.py \\
        --url http://127.0.0.1:8081 \\
        --model maez-judge \\
        --label current-4B-cpu

    # Another candidate: same shape, different port/model
    python scripts/judge_bench/bench.py \\
        --url http://127.0.0.1:8082 \\
        --model qwen2.5-1.5b-instruct \\
        --label qwen-1.5b

    # All results write to scripts/judge_bench/results.csv and a
    # human-readable results.md alongside it.

The test set lives in scripts/judge_bench/test_set.json. Expected
verdicts are author-labeled; agreement ≥ 85% with reasonable latency
is the go/no-go bar.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. pip install httpx", file=sys.stderr)
    sys.exit(1)


HERE = Path(__file__).resolve().parent
TEST_SET_PATH = HERE / "test_set.json"
RESULTS_CSV = HERE / "results.csv"
RESULTS_MD = HERE / "results.md"


JUDGE_SYSTEM_PROMPT = (
    "You are the grounding judge for an AI assistant named Maez. For each "
    "candidate reply, decide whether it is GROUNDED (every claim is "
    "supportable from the inputs available at the time) or FABRICATED "
    "(the reply claims a fact, action, or state that isn't supported by "
    "the inputs).\n\n"
    "Respond with EXACTLY one word: GROUNDED or FABRICATED. Then, on a "
    "new line, give a one-sentence reason. Nothing else — no preamble, "
    "no JSON, no code fences."
)


def build_user_prompt(item: dict) -> str:
    absent = item.get("signals_absent") or []
    absent_block = (
        "signals_absent (things NOT available to the speaker at the time):\n  "
        + "\n  ".join(f"- {s}" for s in absent)
        if absent
        else "signals_absent: (none — full context was available)"
    )
    return (
        f"{absent_block}\n\n"
        f"candidate reply:\n"
        f"  {item['text']!r}\n\n"
        f"verdict:"
    )


def call_judge(url: str, model: str, user_prompt: str, timeout_s: float = 60.0) -> tuple[str, float]:
    """Returns (verdict_word, latency_seconds). Verdict is 'GROUNDED' or
    'FABRICATED' (uppercase) if parseable, else the raw first token."""
    endpoint = url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 80,
        # Qwen3 "thinking" variants default to emitting reasoning
        # tokens first and only write a final answer after a </think>
        # block. For a binary judgement the reasoning is a latency tax
        # and often consumes the whole token budget, leaving `content`
        # empty. Disable via the Qwen-specific chat_template_kwarg and
        # a generic `reasoning_effort` knob — llama.cpp honours one or
        # the other depending on the template.
        "chat_template_kwargs": {"enable_thinking": False},
        "reasoning_effort": "none",
    }
    t0 = time.time()
    try:
        r = httpx.post(endpoint, json=payload, timeout=timeout_s)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"ERROR({type(e).__name__})", time.time() - t0
    latency = time.time() - t0
    if not content:
        return "EMPTY", latency
    first = content.split(None, 1)[0].upper().rstrip(":,.")
    if first in ("GROUNDED", "FABRICATED"):
        return first, latency
    # Fallback: look for either keyword in the response
    up = content.upper()
    if "FABRICATED" in up and "GROUNDED" not in up:
        return "FABRICATED", latency
    if "GROUNDED" in up and "FABRICATED" not in up:
        return "GROUNDED", latency
    return f"UNPARSED({content[:40]!r})", latency


def run_bench(url: str, model: str, label: str, test_set: dict) -> dict:
    items = test_set["items"]
    rows: list[dict] = []
    latencies: list[float] = []
    agree = 0
    disagree_details: list[tuple[str, str, str]] = []
    errors = 0

    print(f"\n═══ {label} ({url} / {model}) ═══", flush=True)
    for item in items:
        user_prompt = build_user_prompt(item)
        verdict, latency = call_judge(url, model, user_prompt)
        latencies.append(latency)
        is_match = (verdict == item["expected"])
        if verdict.startswith("ERROR") or verdict.startswith("UNPARSED"):
            errors += 1
        if is_match:
            agree += 1
            mark = "✓"
        else:
            mark = "✗"
            disagree_details.append((item["id"], item["expected"], verdict))
        print(f"  {mark} {item['id']:<8} expected={item['expected']:<10} "
              f"got={verdict:<22} ({latency:.2f}s)", flush=True)
        rows.append({
            "id": item["id"],
            "expected": item["expected"],
            "got": verdict,
            "match": int(is_match),
            "latency_s": round(latency, 3),
        })

    n = len(items)
    return {
        "label": label,
        "url": url,
        "model": model,
        "n": n,
        "agreement_pct": round(100.0 * agree / n, 1) if n else 0.0,
        "errors": errors,
        "latency_p50": round(statistics.median(latencies), 2) if latencies else 0.0,
        "latency_p95": round(
            sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)], 2
        ) if latencies else 0.0,
        "latency_mean": round(statistics.mean(latencies), 2) if latencies else 0.0,
        "disagreements": disagree_details,
        "per_item": rows,
    }


def append_to_csv(summary: dict) -> None:
    is_new = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a") as f:
        if is_new:
            f.write("timestamp,label,url,model,n,agreement_pct,errors,latency_p50,latency_p95,latency_mean\n")
        f.write(
            f"{int(time.time())},{summary['label']},{summary['url']},"
            f"{summary['model']},{summary['n']},{summary['agreement_pct']},"
            f"{summary['errors']},{summary['latency_p50']},"
            f"{summary['latency_p95']},{summary['latency_mean']}\n"
        )


def render_markdown(summaries: list[dict]) -> str:
    lines = ["# Grounding-judge benchmark results", ""]
    lines.append("| label | model | agree % | errors | p50 s | p95 s | mean s |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for s in summaries:
        lines.append(
            f"| {s['label']} | {s['model']} | {s['agreement_pct']} | "
            f"{s['errors']} | {s['latency_p50']} | {s['latency_p95']} | "
            f"{s['latency_mean']} |"
        )
    lines.append("")
    for s in summaries:
        if not s["disagreements"]:
            continue
        lines.append(f"## {s['label']} — disagreements")
        lines.append("")
        lines.append("| id | expected | got |")
        lines.append("|---|---|---|")
        for item_id, expected, got in s["disagreements"]:
            lines.append(f"| {item_id} | {expected} | {got} |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True,
                    help="Base URL of the OpenAI-compat endpoint, e.g. http://127.0.0.1:8081")
    ap.add_argument("--model", required=True,
                    help="Model alias the endpoint uses, e.g. maez-judge")
    ap.add_argument("--label", required=True,
                    help="Short name for this run in the results table (e.g. 'current-4B-cpu')")
    ap.add_argument("--test-set", default=str(TEST_SET_PATH))
    args = ap.parse_args()

    with open(args.test_set) as f:
        test_set = json.load(f)

    summary = run_bench(args.url, args.model, args.label, test_set)
    append_to_csv(summary)

    # Summary for this run
    print()
    print(f"agreement: {summary['agreement_pct']}%  "
          f"({summary['n'] - len(summary['disagreements'])}/{summary['n']})")
    print(f"errors:    {summary['errors']}")
    print(f"latency:   p50={summary['latency_p50']}s  "
          f"p95={summary['latency_p95']}s  mean={summary['latency_mean']}s")
    if summary["disagreements"]:
        print(f"disagreements: {len(summary['disagreements'])}")
        for item_id, expected, got in summary["disagreements"]:
            print(f"  - {item_id}: expected {expected}, got {got}")

    # Re-read CSV and render the aggregate markdown
    summaries: list[dict] = [summary]
    # Rewrite the markdown from scratch each run so the latest run is visible.
    RESULTS_MD.write_text(render_markdown(summaries))
    print(f"\nresults appended to {RESULTS_CSV}")
    print(f"markdown snapshot at  {RESULTS_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
