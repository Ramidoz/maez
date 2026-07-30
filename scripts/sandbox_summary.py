#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""sandbox_summary.py — read-only diagnostic helper for the 2.5c
sandbox window.

Scans ``logs/maez.log`` and ``logs/cognition.log`` over a time window
and prints a compact summary of the slice-3 telemetry surfaces:

  * Envelope truncation events (kind × section × count)
  * Grounding-judge unavailability (error_class × count)
  * Audit rewrite distribution (mode × count, surface × count)
  * Recall-cap-hit signal (best-effort proxy)
  * Disabled-mode signal (best-effort proxy)

Strictly read-only:
  - imports stdlib + ``pathlib`` only
  - no daemon imports
  - no DB access
  - no log writes (output is stdout text)
  - no service / config changes

Usage:
  scripts/sandbox_summary.py                         # last 24h
  scripts/sandbox_summary.py --hours 6
  scripts/sandbox_summary.py --since "2026-05-08 09:00:00"
  scripts/sandbox_summary.py --since "..." --until "..."
  scripts/sandbox_summary.py --logs-dir /custom/path

Exits 0 always (read-only diagnostic; no health-check semantics).
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

# ── Log line patterns ──────────────────────────────────────────────────
# maez.log format: "YYYY-MM-DD HH:MM:SS [LEVEL] message"
# cognition.log format: "YYYY-MM-DD HH:MM:SS | message"

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

_ENVELOPE_TRUNC_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"\[WARNING\] envelope_truncated "
    r"section=(\S+) kind=(\S+) "
    r"dropped_entries=(\S+) dropped_chars=(\S+) "
    r"before=(\S+) after=(\S+) cap=(\S+)"
)

_JUDGE_UNAVAIL_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"\[WARNING\] self_claim_audit: grounding judge unavailable "
    r"\(error_class=(\w+)\)"
)

# cognition.log audit emit line.
_AUDIT_COG_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| "
    r"self_claim_audit \| "
    r"surface=(\S+) flagged=(\d+) mode=(\S+)"
)

_TS_FMT = "%Y-%m-%d %H:%M:%S"


def _parse_ts(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, _TS_FMT)
    except ValueError:
        return None


def _iter_log_lines(path: Path) -> Iterable[str]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            yield line.rstrip("\n")


def scan_logs(
    *,
    logs_dir: Path,
    since: datetime,
    until: datetime,
) -> dict:
    """Walk maez.log + cognition.log and accumulate slice-3 events
    in [since, until]. Returns a dict-shaped report.
    """
    truncations: list[dict] = []
    judge_unavail: Counter = Counter()
    audit_modes: Counter = Counter()
    audit_surfaces: Counter = Counter()
    audit_flagged_total = 0
    audit_total = 0

    # First / last timestamp seen — useful when the requested window
    # is wider than the available log span.
    first_seen: datetime | None = None
    last_seen: datetime | None = None

    def _track_ts(ts: datetime) -> None:
        nonlocal first_seen, last_seen
        if first_seen is None or ts < first_seen:
            first_seen = ts
        if last_seen is None or ts > last_seen:
            last_seen = ts

    # maez.log: envelope truncations + judge unavailability
    for line in _iter_log_lines(logs_dir / "maez.log"):
        m = _ENVELOPE_TRUNC_RE.match(line)
        if m:
            ts = _parse_ts(m.group(1))
            if ts is None:
                continue
            _track_ts(ts)
            if not (since <= ts <= until):
                continue
            try:
                truncations.append({
                    "ts": ts,
                    "section": m.group(2),
                    "kind": m.group(3),
                    "dropped_entries": int(m.group(4)),
                    "dropped_chars": int(m.group(5)),
                    "before": int(m.group(6)),
                    "after": int(m.group(7)),
                    "cap": int(m.group(8)),
                })
            except ValueError:
                # Numeric field non-int — skip the line, keep going.
                pass
            continue

        m = _JUDGE_UNAVAIL_RE.match(line)
        if m:
            ts = _parse_ts(m.group(1))
            if ts is None:
                continue
            _track_ts(ts)
            if not (since <= ts <= until):
                continue
            judge_unavail[m.group(2)] += 1
            continue

        # Track-ts for context lines (any timestamped line in the
        # requested window indicates the daemon was alive).
        m = _TS_RE.match(line)
        if m:
            ts = _parse_ts(m.group(1))
            if ts is not None:
                _track_ts(ts)

    # cognition.log: audit emit telemetry
    for line in _iter_log_lines(logs_dir / "cognition.log"):
        m = _AUDIT_COG_RE.match(line)
        if m:
            ts = _parse_ts(m.group(1))
            if ts is None:
                continue
            _track_ts(ts)
            if not (since <= ts <= until):
                continue
            try:
                flagged = int(m.group(3))
            except ValueError:
                continue
            audit_total += 1
            audit_flagged_total += flagged
            audit_modes[m.group(4)] += 1
            audit_surfaces[m.group(2)] += 1
            continue

        m = _TS_RE.match(line)
        if m:
            ts = _parse_ts(m.group(1))
            if ts is not None:
                _track_ts(ts)

    return {
        "truncations": truncations,
        "judge_unavail": judge_unavail,
        "audit_modes": audit_modes,
        "audit_surfaces": audit_surfaces,
        "audit_total": audit_total,
        "audit_flagged_total": audit_flagged_total,
        "first_seen": first_seen,
        "last_seen": last_seen,
    }


def format_report(
    report: dict,
    *,
    since: datetime,
    until: datetime,
    logs_dir: Path,
) -> str:
    lines: list[str] = []
    push = lines.append

    push("=" * 70)
    push("MAEZ SANDBOX SUMMARY")
    push("=" * 70)
    push(f"Window:    {since.strftime(_TS_FMT)}  →  {until.strftime(_TS_FMT)}")
    push(f"Logs dir:  {logs_dir}")
    if report["first_seen"] and report["last_seen"]:
        push(
            f"Log span:  {report['first_seen'].strftime(_TS_FMT)}  →  "
            f"{report['last_seen'].strftime(_TS_FMT)}"
        )
    else:
        push("Log span:  (no timestamped lines found)")
    push("")

    # ── Envelope truncations ──────────────────────────────────────
    truncations = report["truncations"]
    push("─" * 70)
    push("ENVELOPE TRUNCATIONS (slice 3.0d telemetry)")
    push("─" * 70)
    if not truncations:
        push("  none in window — envelope stayed under cap, OR")
        push("  MAEZ_EVIDENCE_ENVELOPE_DISABLED=1 was set.")
    else:
        kind_section: Counter = Counter()
        for t in truncations:
            kind_section[(t["kind"], t["section"])] += 1
        push(f"  total events: {len(truncations)}")
        push(f"  {'kind':<22} {'section':<22} count")
        push(f"  {'-' * 22} {'-' * 22} -----")
        for (kind, section), count in sorted(
            kind_section.items(), key=lambda x: (-x[1], x[0]),
        ):
            push(f"  {kind:<22} {section:<22} {count}")
        # Char-savings rollup
        total_dropped_chars = sum(t["dropped_chars"] for t in truncations)
        total_dropped_entries = sum(t["dropped_entries"] for t in truncations
                                    if t["dropped_entries"] >= 0)
        push("")
        push(f"  total chars dropped:   {total_dropped_chars}")
        push(f"  total entries dropped: {total_dropped_entries}")
        # Per-section pressure: max envelope_chars_before across the window.
        max_before = max((t["before"] for t in truncations), default=0)
        push(f"  peak envelope_chars_before: {max_before}")
    push("")

    # ── Judge unavailability ─────────────────────────────────────
    judge_unavail = report["judge_unavail"]
    push("─" * 70)
    push("GROUNDING JUDGE UNAVAILABILITY")
    push("─" * 70)
    if not judge_unavail:
        push("  none in window — judge endpoint healthy, OR no audit ran.")
    else:
        total = sum(judge_unavail.values())
        push(f"  total events: {total}")
        push(f"  {'error_class':<22} count")
        push(f"  {'-' * 22} -----")
        for cls, count in sorted(
            judge_unavail.items(), key=lambda x: (-x[1], x[0]),
        ):
            push(f"  {cls:<22} {count}")
    push("")

    # ── Audit rewrite distribution ───────────────────────────────
    audit_total = report["audit_total"]
    push("─" * 70)
    push("AUDIT REWRITE DISTRIBUTION (cognition.log)")
    push("─" * 70)
    if audit_total == 0:
        push("  no audit emissions in window.")
    else:
        push(f"  total audits: {audit_total}")
        push(f"  total flagged sentences: {report['audit_flagged_total']}")
        if audit_total > 0:
            rewrite_modes = ("sentence", "shortcircuit")
            rewrites = sum(
                report["audit_modes"].get(m, 0) for m in rewrite_modes
            )
            judge_unavail_audits = report["audit_modes"].get(
                "judge_unavailable", 0,
            )
            push(
                f"  rewrite rate: {rewrites}/{audit_total} = "
                f"{100*rewrites/audit_total:.1f}%"
            )
            push(
                f"  judge_unavailable rate: "
                f"{judge_unavail_audits}/{audit_total} = "
                f"{100*judge_unavail_audits/audit_total:.1f}%"
            )
        push("")
        push(f"  {'mode':<22} count")
        push(f"  {'-' * 22} -----")
        for mode, count in sorted(
            report["audit_modes"].items(), key=lambda x: (-x[1], x[0]),
        ):
            push(f"  {mode:<22} {count}")
        push("")
        push(f"  {'surface':<22} count")
        push(f"  {'-' * 22} -----")
        for surf, count in sorted(
            report["audit_surfaces"].items(), key=lambda x: (-x[1], x[0]),
        ):
            push(f"  {surf:<22} {count}")
    push("")

    # ── Recall-cap-hit signal ────────────────────────────────────
    push("─" * 70)
    push("RECALL CAP PRESSURE (proxy)")
    push("─" * 70)
    push("  No direct log line records recall-cap hits today.")
    push("  Closest proxy: envelope_truncated total_cap events above")
    push("  signal that the prompt budget bit. Cross-reference with")
    push("  peak envelope_chars_before (above) and your llama.cpp")
    push("  ctx-utilization metric if available.")
    push("")

    # ── Disabled-mode signal ─────────────────────────────────────
    push("─" * 70)
    push("DISABLED-MODE SIGNAL (proxy)")
    push("─" * 70)
    push("  MAEZ_EVIDENCE_ENVELOPE_DISABLED=1 is not directly logged.")
    if not truncations and audit_total > 0:
        push("  Inference: zero envelope_truncated events but audits ran.")
        push("  Either the bypass was active, OR envelopes never bit caps.")
        push("  Confirm by checking the env var on the daemon process:")
        push(
            "    sudo tr '\\0' '\\n' < "
            "/proc/$(systemctl --user show -p MainPID --value maez.service)/environ "
            "| grep MAEZ_EVIDENCE_ENVELOPE_DISABLED"
        )
    elif truncations:
        push("  Inference: envelope_truncated events fired → bypass NOT active")
        push("  for at least part of the window.")
    else:
        push("  Inference: insufficient signal (no audits, no truncations).")
    push("")
    push("=" * 70)

    return "\n".join(lines)


def _resolve_window(args, *, _now: datetime | None = None) -> tuple[datetime, datetime]:
    now = _now or datetime.now()
    if args.since:
        since = datetime.strptime(args.since, _TS_FMT)
    elif args.hours:
        since = now - timedelta(hours=args.hours)
    else:
        since = now - timedelta(hours=24)
    until = (
        datetime.strptime(args.until, _TS_FMT) if args.until else now
    )
    if since > until:
        raise SystemExit(
            f"--since ({since}) is after --until ({until})"
        )
    return since, until


def _resolve_logs_dir(args) -> Path:
    if args.logs_dir:
        return Path(args.logs_dir).expanduser().resolve()
    # Default: <maez_home>/logs based on this script's location.
    # scripts/sandbox_summary.py → maez_home is parent of scripts/.
    return (Path(__file__).resolve().parent.parent / "logs").resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize slice-3 telemetry from logs/maez.log + "
            "logs/cognition.log over a time window. Read-only."
        ),
    )
    parser.add_argument(
        "--hours", type=float, default=None,
        help="Window length in hours back from now (default 24 if "
             "neither --hours nor --since given).",
    )
    parser.add_argument(
        "--since", type=str, default=None,
        help='Lower bound timestamp "YYYY-MM-DD HH:MM:SS".',
    )
    parser.add_argument(
        "--until", type=str, default=None,
        help='Upper bound timestamp "YYYY-MM-DD HH:MM:SS" (default now).',
    )
    parser.add_argument(
        "--logs-dir", type=str, default=None,
        help="Override the default <maez_home>/logs path.",
    )
    args = parser.parse_args(argv)

    since, until = _resolve_window(args)
    logs_dir = _resolve_logs_dir(args)

    report = scan_logs(logs_dir=logs_dir, since=since, until=until)
    print(format_report(report, since=since, until=until, logs_dir=logs_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
