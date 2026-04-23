# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
scripts/audit_inspect.py — Session 11h, staging-only.

Manual CLI for inspecting the staging fast-lane audit log. Reads the
active audit file at memory/fast_reply_audit.jsonl plus optional rotated
slots .1 .. .5 and prints a small set of useful aggregates:

  • Requests per scope per hour
  • p50 / p95 / p99 model_call_ms by backend
  • Retry frequency (counts and rate)
  • Rate-limit hit rate
  • Redaction count distribution
  • Adapter-vs-direct caller split (Session 11h)

This is a manual inspector. It does NOT tail. It does NOT run in the
background. It does NOT touch the daemon. It only reads files under
memory/ that the staging fast-lane stack owns.

Usage:
    cd /home/rohit/maez
    source .venv/bin/activate
    python scripts/audit_inspect.py
    python scripts/audit_inspect.py --include-rotated
    python scripts/audit_inspect.py --since-hours 24
    python scripts/audit_inspect.py --json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict, Counter
from pathlib import Path
from typing import Iterable

# Allow running from repo root with `python scripts/audit_inspect.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.fast_reply_audit import AUDIT_PATH, MAX_ROTATIONS, _rotated_path


# ── reading ────────────────────────────────────────────────────────────
def iter_audit_files(include_rotated: bool) -> Iterable[Path]:
    if include_rotated:
        # Read oldest first so chronological order is preserved within
        # the merged stream. .5 is oldest, .1 is younger, active is youngest.
        for n in range(MAX_ROTATIONS, 0, -1):
            p = _rotated_path(n)
            if p.exists():
                yield p
    if AUDIT_PATH.exists():
        yield AUDIT_PATH


def load_records(include_rotated: bool, since_hours: float | None) -> list[dict]:
    cutoff = (time.time() - since_hours * 3600.0) if since_hours else None
    records: list[dict] = []
    for path in iter_audit_files(include_rotated):
        try:
            with open(path, 'rb') as f:
                data = f.read().decode('utf-8', errors='replace')
        except Exception as e:
            print(f'  warning: could not read {path}: {e}', file=sys.stderr)
            continue
        for ln in data.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rec = json.loads(ln)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            if cutoff is not None:
                ts = rec.get('ts')
                if isinstance(ts, (int, float)) and ts < cutoff:
                    continue
            records.append(rec)
    return records


# ── stats ──────────────────────────────────────────────────────────────
def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    # Linear interpolation, R-7 style
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_values[int(k)])
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return float(d0 + d1)


def _hour_bucket(ts: float) -> str:
    return time.strftime('%Y-%m-%d %H:00', time.localtime(ts))


def compute_stats(records: list[dict]) -> dict:
    total = len(records)
    by_event = Counter(r.get('event', '<missing>') for r in records)

    # Per-scope per-hour buckets
    per_scope_hour: dict[tuple[str, str], int] = defaultdict(int)
    for r in records:
        scope = r.get('trust_scope') or '<unknown>'
        ts    = r.get('ts')
        if not isinstance(ts, (int, float)):
            continue
        per_scope_hour[(scope, _hour_bucket(ts))] += 1

    # Latency by backend (only successful 'reply' events)
    by_backend_lat: dict[str, list[float]] = defaultdict(list)
    for r in records:
        if r.get('event') != 'reply':
            continue
        if r.get('http_status') != 200:
            continue
        be = r.get('backend_name') or '<unknown>'
        v = r.get('model_call_ms')
        if isinstance(v, (int, float)) and v >= 0:
            by_backend_lat[be].append(float(v))

    backend_latency = {}
    for be, vs in by_backend_lat.items():
        vs_sorted = sorted(vs)
        backend_latency[be] = {
            'n':   len(vs),
            'min': int(vs_sorted[0]),
            'p50': int(_percentile(vs_sorted, 50)),
            'p95': int(_percentile(vs_sorted, 95)),
            'p99': int(_percentile(vs_sorted, 99)),
            'max': int(vs_sorted[-1]),
        }

    # Retry frequency
    reply_records = [r for r in records if r.get('event') == 'reply']
    retry_attempted = sum(1 for r in reply_records if r.get('retry_strategy'))
    retry_by_strategy = Counter(
        r.get('retry_strategy') or '<none>' for r in reply_records
    )

    # Rate-limit hit rate (denominator: reply + rate_limited events)
    rate_limited = sum(1 for r in records if r.get('event') == 'rate_limited')
    request_total = len(reply_records) + rate_limited
    rate_limit_rate = (rate_limited / request_total) if request_total else 0.0

    # Redaction distribution (only reply records have redaction fields)
    redaction_counts = Counter()
    for r in reply_records:
        n = r.get('cloud_redactions', 0) or 0
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 0
        redaction_counts[n] += 1

    # Adapter-vs-direct caller split (Session 11h)
    adapter_versions = Counter()
    direct_count = 0
    for r in records:
        av = r.get('adapter_version')
        if av:
            adapter_versions[str(av)] += 1
        else:
            direct_count += 1

    return {
        'total_records':           total,
        'by_event':                dict(by_event),
        'per_scope_per_hour':      {f'{s}@{h}': c for (s, h), c in sorted(per_scope_hour.items())},
        'backend_latency_ms':      backend_latency,
        'retry':                   {
            'replies_total':       len(reply_records),
            'retry_attempted':     retry_attempted,
            'attempt_rate':        (retry_attempted / len(reply_records)) if reply_records else 0.0,
            'by_strategy':         dict(retry_by_strategy),
        },
        'rate_limit':              {
            'rate_limited':        rate_limited,
            'request_total':       request_total,
            'hit_rate':            round(rate_limit_rate, 4),
        },
        'redaction_distribution':  dict(sorted(redaction_counts.items())),
        'adapter_vs_direct':       {
            'direct':              direct_count,
            'adapter_versions':    dict(adapter_versions),
        },
    }


# ── pretty printing ────────────────────────────────────────────────────
def banner(text: str) -> None:
    print()
    print('=' * 76)
    print(f'  {text}')
    print('=' * 76)


def print_text(stats: dict) -> None:
    banner('AUDIT INSPECTOR — staging fast-lane boundary')
    print(f'  records loaded     : {stats["total_records"]}')
    print(f'  events             : {stats["by_event"]}')
    print()

    print('  per scope per hour :')
    if not stats['per_scope_per_hour']:
        print('    (none)')
    else:
        for k, c in stats['per_scope_per_hour'].items():
            print(f'    {k:50s}  {c:6d}')

    banner('LATENCY BY BACKEND (model_call_ms, successful replies only)')
    if not stats['backend_latency_ms']:
        print('  (no successful replies recorded)')
    else:
        print(f'  {"backend":35s} {"n":>5s} {"min":>7s} {"p50":>7s} {"p95":>7s} {"p99":>7s} {"max":>7s}')
        for be, d in stats['backend_latency_ms'].items():
            print(f'  {be:35s} {d["n"]:5d} {d["min"]:7d} {d["p50"]:7d} '
                  f'{d["p95"]:7d} {d["p99"]:7d} {d["max"]:7d}')

    banner('RETRY FREQUENCY')
    rt = stats['retry']
    print(f'  replies total      : {rt["replies_total"]}')
    print(f'  retry attempted    : {rt["retry_attempted"]}')
    print(f'  attempt rate       : {rt["attempt_rate"]:.2%}')
    print(f'  by strategy        :')
    for k, v in rt['by_strategy'].items():
        print(f'    {k:25s} {v:6d}')

    banner('RATE LIMIT HIT RATE')
    rl = stats['rate_limit']
    print(f'  rate_limited       : {rl["rate_limited"]}')
    print(f'  request_total      : {rl["request_total"]}')
    print(f'  hit_rate           : {rl["hit_rate"]:.2%}')

    banner('CLOUD REDACTION DISTRIBUTION')
    rd = stats['redaction_distribution']
    if not rd:
        print('  (no reply records to score)')
    else:
        for n_redactions, count in rd.items():
            bar = '█' * min(40, count)
            print(f'  {n_redactions:3d} redactions : {count:6d}  {bar}')

    banner('ADAPTER vs DIRECT CALLER SPLIT')
    ad = stats['adapter_vs_direct']
    print(f'  direct (no header) : {ad["direct"]}')
    if ad['adapter_versions']:
        for av, c in ad['adapter_versions'].items():
            print(f'    via {av}  →  {c}')
    else:
        print('  (no adapter-tagged calls yet)')


def main() -> int:
    ap = argparse.ArgumentParser(description='Manual audit inspector for the staging fast-lane log.')
    ap.add_argument('--include-rotated', action='store_true',
                    help='also read rotated audit files .1 .. .5')
    ap.add_argument('--since-hours', type=float, default=None,
                    help='only consider records newer than this many hours')
    ap.add_argument('--json', action='store_true',
                    help='emit raw stats as JSON instead of formatted text')
    args = ap.parse_args()

    records = load_records(args.include_rotated, args.since_hours)
    stats = compute_stats(records)

    if args.json:
        print(json.dumps(stats, indent=2, default=str))
    else:
        print_text(stats)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
