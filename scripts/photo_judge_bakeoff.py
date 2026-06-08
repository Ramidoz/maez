# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""scripts/photo_judge_bakeoff.py — offline Photo-Contradiction Judge Bakeoff.

A MEASUREMENT REPORT, not a live gate. For each candidate verifier, scores a
stratified photo-contradiction corpus and reports a catch x latency frontier.

Hard contract (mirrors scripts/judge_bakeoff.py): this runner does NOT flip
MAEZ_JUDGE_BASE_URL for the live daemon, does NOT edit model.env, does NOT
start/stop/restart any systemd unit, and does NOT download anything — it consumes
artifacts already present under models/bakeoff/. Downloads live solely in the
separate scripts/photo_judge_bakeoff_fetch.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_corpus(path: str) -> list[dict[str, Any]]:
    """Load + validate the photo-contradiction corpus (one JSON object/line)."""
    rows: list[dict[str, Any]] = []
    valid_strata = {
        "real_anchor", "numeric_ocr", "entity_title",
        "grounded_control", "uncertainty_control",
    }
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for f in ("id", "stratum", "premise", "reply", "hypothesis",
                      "expected", "must_catch", "source"):
                if f not in row:
                    raise ValueError(f"line {i}: missing field {f!r}")
            if row["stratum"] not in valid_strata:
                raise ValueError(f"{row['id']}: bad stratum {row['stratum']!r}")
            if row["expected"] not in {"grounded", "contradicts"}:
                raise ValueError(f"{row['id']}: bad expected {row['expected']!r}")
            if not isinstance(row["must_catch"], bool):
                raise ValueError(f"{row['id']}: must_catch not bool")
            rows.append(row)
    return rows


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)


def aggregate_candidate(name, rows, verdicts, meta):
    """verdicts: {id: (label, latency_s)}. label in {grounded, contradicts, error}.
    A 'contradicts' case is CAUGHT iff graded 'contradicts'. A 'grounded' case is
    FALSE-FLAGGED iff graded 'contradicts'. A per-case 'error' (predict raised for
    that one case while the candidate is otherwise runnable) is NEITHER caught nor
    a false flag — it is counted in errors, and for a must_catch contradiction it
    counts as MISSED (it != 'contradicts')."""
    def graded(r):
        return verdicts.get(r["id"], ("", 0))[0]
    contra = [r for r in rows if r["expected"] == "contradicts"]
    grounded = [r for r in rows if r["expected"] == "grounded"]
    caught = [r for r in contra if graded(r) == "contradicts"]
    flagged = [r for r in grounded if graded(r) == "contradicts"]
    errored = [r for r in rows if graded(r) == "error"]
    missed_must = [r["id"] for r in contra
                   if r["must_catch"] and graded(r) != "contradicts"]
    per_stratum: dict[str, dict] = {}
    for r in rows:
        s = per_stratum.setdefault(r["stratum"], {
            "contradiction_n": 0, "caught": 0, "catch_rate": None,
            "grounded_n": 0, "false_flags": 0, "false_flag_rate": None,
            "errors": 0})
        g = graded(r)
        if g == "error":
            s["errors"] += 1
        if r["expected"] == "contradicts":
            s["contradiction_n"] += 1
            if g == "contradicts":
                s["caught"] += 1
        else:  # grounded
            s["grounded_n"] += 1
            if g == "contradicts":
                s["false_flags"] += 1
    for s in per_stratum.values():
        if s["contradiction_n"]:
            s["catch_rate"] = round(s["caught"] / s["contradiction_n"], 4)
        if s["grounded_n"]:
            s["false_flag_rate"] = round(s["false_flags"] / s["grounded_n"], 4)
    lat = [verdicts[r["id"]][1] for r in rows if r["id"] in verdicts]
    return {
        "name": name,
        "runnable": True,
        "catch_rate": round(len(caught) / len(contra), 4) if contra else None,
        "false_flag_rate": round(len(flagged) / len(grounded), 4) if grounded else None,
        "error_count": len(errored),
        "error_rate": round(len(errored) / len(rows), 4) if rows else None,
        "missed_must_catch": missed_must,
        "per_stratum": per_stratum,
        "latency": {"p50": _pct(lat, 50), "p95": _pct(lat, 95),
                    "mean": round(sum(lat) / len(lat), 4) if lat else None},
        "meta": meta,
    }


def build_report(aggregates: list[dict]) -> dict:
    """Render the frontier report. aggregates may be empty or all-unavailable."""
    runnable = [a for a in aggregates if a.get("runnable")]
    lines = ["# Photo-Contradiction Judge Bakeoff", ""]
    lines.append("| candidate | runnable | catch | false-flag | errors | p50 s | p95 s | threshold | device | sha256 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|---|---|")
    for a in aggregates:
        m = a.get("meta", {})
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            a["name"], a.get("runnable"),
            a.get("catch_rate"), a.get("false_flag_rate"), a.get("error_count"),
            a.get("latency", {}).get("p50"), a.get("latency", {}).get("p95"),
            m.get("threshold"), m.get("device"),
            (m.get("sha256") or "")[:12] or m.get("unavailable_reason", "")))
    lines.append("")
    for a in runnable:
        if a["missed_must_catch"]:
            lines.append("**MISSED MUST-CATCH ({}): {}**".format(
                a["name"], ", ".join(a["missed_must_catch"])))
    # frontier + recommendation
    if not runnable:
        lines.append("")
        lines.append("RECOMMENDATION: none — 0/{} candidates runnable; "
                     "see unavailable_reason.".format(len(aggregates)))
        rec = None
    else:
        # rank: most catch, then fewest false-flags, then lowest p95
        ranked = sorted(runnable, key=lambda a: (
            -(a["catch_rate"] or 0), a["false_flag_rate"] or 1,
            a["latency"].get("p95") or 9e9))
        top = ranked[0]
        rec = top["name"]
        lines.append("")
        lines.append("RECOMMENDATION: {} (catch {}, false-flag {}, p95 {}s). "
                     "Owner picks final winner + placement in Lane 2b.".format(
                         top["name"], top["catch_rate"],
                         top["false_flag_rate"], top["latency"].get("p95")))
    return {"text": "\n".join(lines), "aggregates": aggregates,
            "recommendation": rec}


import argparse

from scripts.photo_judge_bakeoff_adapters import (   # adapters only — never fetch/hf
    ADAPTER_VERSION, THRESHOLD_GRID, score_to_label)


def run_candidate(adapter, rows):
    """Returns a LIST of aggregates. Score-based candidates are EXPANDED across
    the FIXED THRESHOLD_GRID (one aggregate per grid point — the un-riggable
    frontier); label-native candidates yield a single aggregate (threshold=None).
    The model is called ONCE per case; each grid threshold re-grades the SAME raw
    score, so the sweep costs no extra model calls."""
    raw = {}  # id -> (label_at_default, score, latency)
    for r in rows:
        v = adapter.predict(r["premise"], r["hypothesis"])
        raw[r["id"]] = (v.label, v.score, v.latency_s)
    runnable = any(lbl != "unavailable" for lbl, _, _ in raw.values())
    base_meta = {
        "model_id": getattr(adapter, "model_id", adapter.name),
        "adapter_version": ADAPTER_VERSION,
        "device": getattr(adapter, "device", "cpu"),
        "unavailable_reason": adapter.unavailable_reason,
        "sha256": getattr(adapter, "sha256", None),
    }
    if not runnable:
        return [{"name": adapter.name, "runnable": False, "catch_rate": None,
                 "false_flag_rate": None, "missed_must_catch": [],
                 "per_stratum": {}, "latency": {},
                 "meta": {**base_meta, "threshold": adapter.threshold}}]
    if adapter.score_based:
        aggs = []
        for thr in THRESHOLD_GRID:
            verdicts = {}
            for cid, (lbl, score, lat) in raw.items():
                if lbl == "unavailable" or score is None:
                    verdicts[cid] = ("error", lat)   # per-case predict failure
                else:
                    verdicts[cid] = (score_to_label(score, thr), lat)
            aggs.append(aggregate_candidate(
                f"{adapter.name}@{thr}", rows, verdicts,
                {**base_meta, "threshold": thr}))
        return aggs
    # label-native: a per-case "unavailable" is a per-case error, not a verdict
    verdicts = {cid: (("error" if lbl == "unavailable" else lbl), lat)
                for cid, (lbl, score, lat) in raw.items()}
    return [aggregate_candidate(adapter.name, rows, verdicts,
                                {**base_meta, "threshold": None})]


def main(argv=None, adapters=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--label", default="bakeoff")
    p.add_argument("--corpus",
                   default="tests/data/judge_eval_photo_contradiction_v1.jsonl")
    p.add_argument("--out-dir", default="logs/photo_judge_bakeoff")
    args = p.parse_args(argv)

    rows = load_corpus(args.corpus)
    if adapters is None:
        from scripts.photo_judge_bakeoff_adapters import ALL_ADAPTERS
        adapters = [cls() for cls in ALL_ADAPTERS]
    aggregates = [a for adapter in adapters for a in run_candidate(adapter, rows)]
    report = build_report(aggregates)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.label}.md").write_text(report["text"], encoding="utf-8")
    (out / f"{args.label}.json").write_text(
        json.dumps({"recommendation": report["recommendation"],
                    "aggregates": aggregates}, indent=2, default=str),
        encoding="utf-8")
    print(report["text"].splitlines()[-1])  # the RECOMMENDATION line
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
