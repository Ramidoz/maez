#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""validate_judge.py — offline recall/FP harness for the grounding judge.

Pulls real traces from Langfuse (or a local JSONL dump), classifies each
as fabricated/clean based on whether self_claim_audit detected and rewrote
it, then runs the semantic grounding judge and reports:

  Recall on fabricated set:  judge caught / total fabricated  (target ≥0.90)
  FP rate on clean set:      judge flagged / total clean       (target ≤0.10)

Usage:
  # Against Langfuse (needs creds in /etc/maez/langfuse.env or env):
  python scripts/validate_judge.py --source langfuse --limit 100

  # Against a local JSONL dump (one JSON obj per line, fields: text,
  # signals_present, signals_absent, fabricated):
  python scripts/validate_judge.py --source file --file path/to/dump.jsonl

  # Dry-run: print first 5 traces and exit
  python scripts/validate_judge.py --source langfuse --limit 5 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.grounding_judge import judge
from core.fabrication_memory import few_shots_for


# ── Langfuse source ──────────────────────────────────────────────────────

def _load_langfuse_env() -> None:
    env_path = Path("/etc/maez/langfuse.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _fetch_langfuse_traces(limit: int) -> list[dict]:
    """Fetch recent Langfuse traces. Each trace must have input/output
    text and ideally a 'signals_absent' tag. Returns list of dicts with
    keys: text, signals_present, signals_absent, fabricated (bool).

    fabricated=True when the trace output contains the audit-rewrite
    marker (self_claim_audit flagged the response).
    """
    _load_langfuse_env()
    try:
        from langfuse import Langfuse
    except ImportError:
        print("ERROR: langfuse not installed. Run: pip install langfuse")
        sys.exit(1)

    base_url = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST")
    client = Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=base_url,
    )
    try:
        # Newer Langfuse SDK: client.api.trace.list(limit=...)
        traces_page = client.api.trace.list(limit=limit)
        raw_traces = traces_page.data
    except Exception as e:
        print(f"ERROR fetching Langfuse traces: {e}")
        sys.exit(1)

    results = []
    for t in raw_traces:
        # Output text: try output field, then last observation
        text = ""
        if hasattr(t, "output") and t.output:
            if isinstance(t.output, str):
                text = t.output
            elif isinstance(t.output, dict):
                text = t.output.get("text") or t.output.get("content") or ""

        if not text:
            continue

        # Signal manifest: look for tags or metadata
        tags = getattr(t, "tags", []) or []
        metadata = getattr(t, "metadata", {}) or {}
        signals_present = metadata.get("signals_present", [])
        signals_absent = metadata.get("signals_absent", [])

        # fabricated=True if the audit rewrote this response.
        # Marker: text was logged before AND after rewrite; or the trace
        # has a "rewritten=True" metadata field. Fall back to keyword heuristic.
        fabricated = bool(metadata.get("audit_rewritten")) or \
                     "self_claim_audit" in str(tags)

        results.append({
            "text": text,
            "signals_present": signals_present,
            "signals_absent": signals_absent,
            "fabricated": fabricated,
            "trace_id": getattr(t, "id", ""),
        })
    return results


# ── File source ─────────────────────────────────────────────────────────

def _load_file_traces(path: str) -> list[dict]:
    """Load traces from a JSONL file. Each line: JSON obj with keys:
    text, signals_present (list), signals_absent (list), fabricated (bool).
    """
    results = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                results.append({
                    "text": obj["text"],
                    "signals_present": obj.get("signals_present", []),
                    "signals_absent": obj.get("signals_absent", []),
                    "fabricated": bool(obj.get("fabricated", False)),
                    "trace_id": obj.get("trace_id", f"line-{lineno}"),
                })
            except Exception as e:
                print(f"  warn: skipping line {lineno}: {e}")
    return results


# ── Main evaluation loop ─────────────────────────────────────────────────

def evaluate(traces: list[dict], dry_run: bool = False) -> None:
    fabricated = [t for t in traces if t["fabricated"]]
    clean = [t for t in traces if not t["fabricated"]]

    print(f"\nLoaded {len(traces)} traces: {len(fabricated)} fabricated, {len(clean)} clean\n")

    if dry_run:
        print("DRY RUN — first 5 traces:")
        for t in traces[:5]:
            print(f"  [{t['trace_id']}] fabricated={t['fabricated']}")
            print(f"    text: {t['text'][:120]!r}")
            print(f"    signals_absent: {t['signals_absent']}")
        return

    if not fabricated and not clean:
        print("No usable traces found. Check Langfuse connection or file.")
        return

    # Run judge on fabricated set — count how many it catches (recall)
    fab_caught = 0
    fab_missed = []
    for t in fabricated:
        fs = few_shots_for(signals_absent=t["signals_absent"], k=3)
        flags = judge(
            text=t["text"],
            signals_present=t["signals_present"],
            signals_absent=t["signals_absent"],
            few_shots=fs,
        )
        if flags:
            fab_caught += 1
        else:
            fab_missed.append(t)

    # Run judge on clean set — count how many it wrongly flags (FP)
    clean_flagged = 0
    clean_fp = []
    for t in clean:
        fs = few_shots_for(signals_absent=t["signals_absent"], k=3)
        flags = judge(
            text=t["text"],
            signals_present=t["signals_present"],
            signals_absent=t["signals_absent"],
            few_shots=fs,
        )
        if flags:
            clean_flagged += 1
            clean_fp.append((t, flags))

    recall = fab_caught / len(fabricated) if fabricated else float("nan")
    fp_rate = clean_flagged / len(clean) if clean else float("nan")

    print("=" * 60)
    print("GROUNDING JUDGE VALIDATION REPORT")
    print("=" * 60)
    print(f"  Fabricated set: {len(fabricated)} traces")
    print(f"    Caught by judge: {fab_caught}  ({recall:.0%})")
    print(f"    Missed:          {len(fab_missed)}")
    print(f"  Clean set: {len(clean)} traces")
    print(f"    Flagged (FP):    {clean_flagged}  ({fp_rate:.0%})")
    print(f"    True negatives:  {len(clean) - clean_flagged}")
    print()

    # Thresholds
    recall_ok = recall >= 0.90 or (len(fabricated) == 0)
    fp_ok = fp_rate <= 0.10 or (len(clean) == 0)
    print("THRESHOLDS (≥90% recall, ≤10% FP):")
    print(f"  Recall:  {'PASS ✓' if recall_ok else 'FAIL ✗'}  ({recall:.0%})")
    print(f"  FP rate: {'PASS ✓' if fp_ok else 'FAIL ✗'}  ({fp_rate:.0%})")
    print()

    if recall_ok and fp_ok:
        print("VERDICT: PASS — judge meets thresholds. Ready for Task 5 (delete regex).")
    else:
        print("VERDICT: FAIL — iterate on judge prompt / few-shot selection before Task 5.")

    if fab_missed:
        print(f"\nMissed fabrications ({len(fab_missed)}):")
        for t in fab_missed[:5]:
            print(f"  [{t['trace_id']}] {t['text'][:100]!r}")

    if clean_fp:
        print(f"\nFalse positives ({len(clean_fp)}):")
        for t, flags in clean_fp[:5]:
            reasons = [f.get("reason", "") for f in flags]
            print(f"  [{t['trace_id']}] {t['text'][:80]!r}")
            print(f"    judge reason: {reasons[0][:80]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--source", choices=["langfuse", "file"], default="langfuse")
    parser.add_argument("--limit", type=int, default=100,
                        help="max traces to fetch (langfuse only)")
    parser.add_argument("--file", help="path to JSONL file (file source only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print first 5 traces and exit without evaluating")
    args = parser.parse_args()

    if args.source == "langfuse":
        traces = _fetch_langfuse_traces(args.limit)
    else:
        if not args.file:
            parser.error("--file required when --source=file")
        traces = _load_file_traces(args.file)

    evaluate(traces, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
