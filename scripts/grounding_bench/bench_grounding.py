"""Grounding-verifier audition harness. Offline scorecard; no live-daemon change.

Mirrors scripts/judge_bench/bench.py, with two differences that matter:
  - an ABSTAIN precondition (no model is called on claimable_absent), and
  - a per-mode FALSE-NEGATIVE headline (the dangerous error: an UNSUPPORTED
    claim wrongly blessed SUPPORTED).
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus.json"
RESULTS_CSV = HERE / "results_grounding.csv"
RESULTS_MD = HERE / "results_grounding.md"


def judge_case(verifier, case: dict) -> tuple[str, float]:
    """ABSTAIN precondition: claimable_absent -> ABSTAIN without calling any model."""
    if case["evidence_kind"] == "claimable_absent":
        return "ABSTAIN", 0.0
    return verifier.support(case["evidence"], case["claim"])


def _scored(expected: str, got: str) -> str:
    if got == "ABSTAIN":
        return "abstain_ok" if expected == "ABSTAIN_EXPECTED" else "abstain_wrong"
    if got == expected:
        return "match"
    if expected == "UNSUPPORTED" and got == "SUPPORTED":
        return "false_negative"   # the dangerous one
    if expected == "SUPPORTED" and got == "UNSUPPORTED":
        return "false_positive"
    return "error"                # EMPTY/ERROR/UNPARSED


def false_negatives_by_mode(per_item: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for r in per_item:
        if r["expected"] != "UNSUPPORTED":
            continue
        m = out.setdefault(r["mode"], {"false_neg": 0, "total_unsupported": 0})
        m["total_unsupported"] += 1
        if r["got"] == "SUPPORTED":
            m["false_neg"] += 1
    return out


def run_candidate(verifier, label: str, items: list[dict]) -> dict:
    per_item, latencies = [], []
    tally: dict[str, int] = defaultdict(int)
    print(f"\n=== {label} ===", flush=True)
    for case in items:
        got, lat = judge_case(verifier, case)
        latencies.append(lat)
        outcome = _scored(case["expected"], got)
        tally[outcome] += 1
        per_item.append({"id": case["id"], "mode": case["mode"],
                         "expected": case["expected"], "got": got, "outcome": outcome,
                         "latency_s": round(lat, 3)})
        mark = {"match": "OK", "abstain_ok": "OK", "false_negative": "!!FN",
                "false_positive": "fp", "abstain_wrong": "!abs", "error": "err"}.get(outcome, "?")
        print(f"  {mark:<4} {case['id']:<10} exp={case['expected']:<16} got={got:<22} ({lat:.2f}s)", flush=True)
    return {
        "label": label,
        "n": len(items),
        "false_neg_by_mode": false_negatives_by_mode(per_item),
        "false_positives": tally["false_positive"],
        "abstain_ok": tally["abstain_ok"],
        "abstain_wrong": tally["abstain_wrong"],
        "errors": tally["error"],
        "matches": tally["match"] + tally["abstain_ok"],
        "latency_p50": round(statistics.median(latencies), 3) if latencies else 0.0,
        "latency_p95": round(sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)], 3) if latencies else 0.0,
        "per_item": per_item,
    }


def load_corpus() -> list[dict]:
    sys.path.insert(0, str(HERE))
    from corpus_schema import validate_corpus
    items = json.loads(CORPUS.read_text())["items"]
    validate_corpus(items)
    return items


def render_markdown(summaries: list[dict]) -> str:
    lines = ["# Evidence-grounding verifier audition", "",
             "Headline metric: **per-mode false-negative rate** (an UNSUPPORTED claim "
             "wrongly blessed SUPPORTED — the dangerous miss).", ""]
    lines += ["## False-negatives by mode (lower is safer)", "",
              "| candidate | cited_but_unsupported | fabricated_false_specific | stale_over_current |",
              "|---|---|---|---|"]
    modes = ["cited_but_unsupported", "fabricated_false_specific", "stale_over_current"]
    for s in summaries:
        cells = []
        for m in modes:
            d = s["false_neg_by_mode"].get(m)
            cells.append(f"{d['false_neg']}/{d['total_unsupported']}" if d else "—")
        lines.append(f"| {s['label']} | " + " | ".join(cells) + " |")
    lines += ["", "## Side metrics", "",
              "| candidate | n | false_pos | abstain_ok | abstain_wrong | errors | p50 s | p95 s |",
              "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for s in summaries:
        lines.append(f"| {s['label']} | {s['n']} | {s['false_positives']} | {s['abstain_ok']} | "
                     f"{s['abstain_wrong']} | {s['errors']} | {s['latency_p50']} | {s['latency_p95']} |")
    return "\n".join(lines) + "\n"


def append_to_csv(summary: dict) -> None:
    is_new = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a") as f:
        if is_new:
            f.write("timestamp,label,n,false_pos,abstain_ok,abstain_wrong,errors,matches,p50,p95\n")
        f.write(f"{int(time.time())},{summary['label']},{summary['n']},{summary['false_positives']},"
                f"{summary['abstain_ok']},{summary['abstain_wrong']},{summary['errors']},"
                f"{summary['matches']},{summary['latency_p50']},{summary['latency_p95']}\n")


def main() -> int:
    import argparse

    from verifiers import FourBAdapterVerifier, HhemVerifier, MinicheckVerifier
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-url", default="http://127.0.0.1:8081")
    ap.add_argument("--judge-model", default="maez-judge")
    ap.add_argument("--only", default="", help="comma list: hhem,minicheck,4b")
    args = ap.parse_args()

    items = load_corpus()
    want = set(args.only.split(",")) if args.only else {"hhem", "minicheck", "4b"}
    summaries = []
    if "minicheck" in want:
        summaries.append(run_candidate(MinicheckVerifier(), "minicheck-deberta", items))
    if "hhem" in want:
        for thr in (0.3, 0.5, 0.7):
            summaries.append(run_candidate(HhemVerifier(threshold=thr), f"hhem@{thr}", items))
    if "4b" in want:
        summaries.append(run_candidate(
            FourBAdapterVerifier(args.judge_url, args.judge_model), "4b-entailment-adapter", items))

    for s in summaries:
        append_to_csv(s)
    RESULTS_MD.write_text(render_markdown(summaries))
    print(f"\nWrote {RESULTS_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
