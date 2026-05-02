# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Signal baseline sufficiency report (Phase 2 prep).

Read-only diagnostic CLI over ``logs/signals/YYYY-MM-DD.jsonl``.
Per signal kind, classifies data sufficiency as
``insufficient`` / ``emerging`` / ``usable`` so an operator can
see whether Maez has enough behavioral history to build a baseline
for that kind.

Why this exists
---------------

The user wants Maez to eventually detect "your usual location has
shifted" and ask "did you move?" — pattern detection plus
curiosity-driven outreach. That requires a learned baseline of
what's normal. As of 2026-05-02 the signal logs hold ~29 events
total, two of which are ``location`` (both at the same address).
Building a delta detector against this would either fire
constantly (false positives) or never fire (no statistical power).
Both are worse than no detector.

This report is the diagnostic step BEFORE the detector — measure
density honestly so the next slice's design is grounded in data
rather than guessed.

Read-only contract: no Chroma writes, no memory manager
involvement, no daemon hook. AST-parse test enforces the import
boundary.

Sufficiency thresholds (user-pinned)
------------------------------------

  insufficient: count <5 OR span_days <7
  emerging:     count >=5 AND span_days >=7 (and not usable)
  usable:       count >=21 AND span_days >=14 AND
                distinct_active_days >=3

Special granularity flag for sparse high-value kinds (currently
just ``location``): when ``distinct_places <2``,
``needs_more_granularity`` is set regardless of span. Two pings
at the same address aren't a baseline even if they're 10 days
apart.

Expected-but-missing whitelist (advisory)
-----------------------------------------

``EXPECTED_KINDS = {location, arrive_home, focus_mode, workout,
sleep, calendar, battery}``. When a kind is absent from logs
it's reported as "not present in logs" — Maez doesn't know
every signal it should have, so this isn't a "broken" claim.

CLI::

    .venv/bin/python scripts/probe/signal_baseline_report.py
        # Reads logs/signals/

    .venv/bin/python scripts/probe/signal_baseline_report.py \\
        --dir custom/path/

    .venv/bin/python scripts/probe/signal_baseline_report.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# Whitelist of signal kinds we expect Maez to have at least SOME
# of. Advisory only — missing-from-logs is reported as
# "not present in logs," not as an error. The whitelist is small
# and pragmatic; a future slice can extend it as Shortcuts come
# online.
EXPECTED_KINDS = frozenset({
    "location",
    "arrive_home",
    "focus_mode",
    "workout",
    "sleep",
    "calendar",
    "battery",
})

# Kinds where distinct-place counting is meaningful. Currently only
# ``location``; future kinds with similar geometry (e.g. workout
# with location data) could join.
GRANULARITY_AWARE_KINDS = frozenset({"location"})

# Threshold constants — explicit names so a future agent reading
# the classifier sees the user's pinned values rather than magic
# numbers in conditional logic.
MIN_EMERGING_COUNT = 5
MIN_EMERGING_SPAN_DAYS = 7.0
MIN_USABLE_COUNT = 21
MIN_USABLE_SPAN_DAYS = 14.0
MIN_USABLE_ACTIVE_DAYS = 3
MIN_DISTINCT_PLACES = 2


# ── dataclasses ─────────────────────────────────────────────────────


@dataclass
class ParseStats:
    """Parser transparency counts. The funnel is:

        total_lines  = every non-blank line read
        parsed       = lines that decoded as a JSON object (dict)
        malformed_json = lines that failed json.loads OR weren't a dict
        missing_kind = subset of `parsed` whose ``kind`` field was
                       missing or empty (these don't make it to
                       ``kinds_observed`` because Maez can't
                       classify a kind it doesn't know).

    So the usable-entry count is ``parsed - missing_kind``;
    ``total_lines`` is the input volume. Surfacing the funnel lets
    an operator distinguish "no signals" from "signals broken on
    write."
    """
    total_lines: int = 0
    parsed: int = 0
    malformed_json: int = 0
    missing_kind: int = 0
    files_read: int = 0


@dataclass
class KindStat:
    kind: str
    count: int
    span_days: float
    distinct_active_days: int
    first_seen: str | None
    last_seen: str | None
    classification: str
    distinct_places: int | None = None
    granularity_note: str | None = None


@dataclass
class SignalBaselineReport:
    source: str
    total_events: int
    overall_first_seen: str | None
    overall_last_seen: str | None
    overall_span_days: float
    kinds_observed: dict[str, KindStat] = field(default_factory=dict)
    kinds_missing: list[str] = field(default_factory=list)
    parse_stats: ParseStats = field(default_factory=ParseStats)


# ── classifier ──────────────────────────────────────────────────────


def classify(count: int, span_days: float,
             distinct_active_days: int) -> str:
    """Return the sufficiency classification for a single kind.

    Strict precedence: usable > emerging > insufficient.
    Conditions match the user-pinned thresholds at the module top."""
    if (count >= MIN_USABLE_COUNT
            and span_days >= MIN_USABLE_SPAN_DAYS
            and distinct_active_days >= MIN_USABLE_ACTIVE_DAYS):
        return "usable"
    if (count >= MIN_EMERGING_COUNT
            and span_days >= MIN_EMERGING_SPAN_DAYS):
        return "emerging"
    return "insufficient"


# ── parser ──────────────────────────────────────────────────────────


def _parse_timestamp(ts: str) -> datetime | None:
    """Match ambient.py:89,120 — call ``.replace("Z", "+00:00")``
    before ``fromisoformat()`` so the probe and the production
    reader agree on what a valid timestamp looks like."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _walk_signals(jsonl_dir: Path, stats: ParseStats):
    """Streaming walk that updates ``stats`` and yields valid
    entries. Silent-skip behavior matches ambient.py — malformed
    JSON / missing kind are counted but not raised."""
    if not jsonl_dir.exists():
        return
    paths = sorted(jsonl_dir.glob("*.jsonl"))
    stats.files_read = len(paths)
    for path in paths:
        try:
            text = path.read_text()
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            stats.total_lines += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                stats.malformed_json += 1
                continue
            if not isinstance(entry, dict):
                stats.malformed_json += 1
                continue
            stats.parsed += 1
            kind = entry.get("kind")
            if not kind:
                stats.missing_kind += 1
                continue
            yield entry


def _distinct_active_days(timestamps: list[datetime]) -> int:
    """Count unique UTC calendar dates across the timestamps."""
    return len({t.astimezone(timezone.utc).date() for t in timestamps})


def _span_days(timestamps: list[datetime]) -> float:
    if len(timestamps) < 2:
        return 0.0
    delta = max(timestamps) - min(timestamps)
    return delta.total_seconds() / 86400.0


def _distinct_places(entries: list[dict]) -> int:
    """Count distinct ``data.place`` strings across location-shaped
    entries. Uses the ``place`` text field rather than lat/lon
    because GPS drift produces many near-duplicate coords for a
    single physical address."""
    places: set[str] = set()
    for e in entries:
        data = e.get("data") or {}
        place = data.get("place")
        if isinstance(place, str) and place.strip():
            places.add(place.strip())
    return len(places)


def build_report(jsonl_dir: Path,
                 source_label: str | None = None) -> SignalBaselineReport:
    """Read every JSONL under ``jsonl_dir`` and produce a
    sufficiency report. The function is the public entry point;
    tests call it directly with a tmpdir."""
    stats = ParseStats()
    by_kind: dict[str, list[dict]] = {}

    for entry in _walk_signals(jsonl_dir, stats):
        kind = entry["kind"]
        by_kind.setdefault(kind, []).append(entry)

    kinds_observed: dict[str, KindStat] = {}
    overall_ts: list[datetime] = []
    for kind, entries in by_kind.items():
        timestamps: list[datetime] = []
        for e in entries:
            dt = _parse_timestamp(e.get("timestamp", ""))
            if dt is not None:
                timestamps.append(dt)
        count = len(entries)
        span = _span_days(timestamps) if timestamps else 0.0
        active = _distinct_active_days(timestamps) if timestamps else 0
        first = (min(timestamps).isoformat() if timestamps else None)
        last = (max(timestamps).isoformat() if timestamps else None)
        cls = classify(count, span, active)

        # Granularity flag for sparse high-value kinds.
        distinct_pl = None
        granularity_note = None
        if kind in GRANULARITY_AWARE_KINDS:
            distinct_pl = _distinct_places(entries)
            if distinct_pl == 0 and entries:
                # Distinct from "1 distinct place" — this means the
                # entries exist but none carried a parseable
                # ``data.place`` text field. Most likely the
                # iOS Shortcut isn't writing the address field at
                # all, not that Rohit only went to one place.
                granularity_note = (
                    "no `place` text found on any entry of this "
                    "kind. The iOS Shortcut may not be writing the "
                    "address field — fix at the Shortcut layer "
                    "before relying on this signal."
                )
            elif distinct_pl < MIN_DISTINCT_PLACES:
                granularity_note = (
                    f"distinct_places={distinct_pl} "
                    f"(<{MIN_DISTINCT_PLACES}) — this kind needs at "
                    "least 2 *physically distinct* addresses observed "
                    "in the wild before a baseline is meaningful. "
                    "Synthetic entries do not count: the goal is to "
                    "see real movement, not to bump the counter."
                )

        kinds_observed[kind] = KindStat(
            kind=kind,
            count=count,
            span_days=span,
            distinct_active_days=active,
            first_seen=first,
            last_seen=last,
            classification=cls,
            distinct_places=distinct_pl,
            granularity_note=granularity_note,
        )
        overall_ts.extend(timestamps)

    overall_span = _span_days(overall_ts) if overall_ts else 0.0
    kinds_missing = sorted(
        k for k in EXPECTED_KINDS if k not in kinds_observed
    )

    # ``total_events`` counts events with a recognized ``kind``
    # (i.e. lines that made it into ``kinds_observed``). Lines with
    # missing/empty ``kind`` or malformed JSON are tracked separately
    # in ``parse_stats`` — see ``ParseStats`` docstring for the funnel
    # definition. ``parse_stats.total_lines`` is the raw line count.
    return SignalBaselineReport(
        source=source_label or str(jsonl_dir),
        total_events=sum(s.count for s in kinds_observed.values()),
        overall_first_seen=(
            min(overall_ts).isoformat() if overall_ts else None
        ),
        overall_last_seen=(
            max(overall_ts).isoformat() if overall_ts else None
        ),
        overall_span_days=overall_span,
        kinds_observed=kinds_observed,
        kinds_missing=kinds_missing,
        parse_stats=stats,
    )


# ── output ──────────────────────────────────────────────────────────


def to_json_payload(rep: SignalBaselineReport) -> dict:
    """Serialize the report to a JSON-friendly dict. dataclasses
    nest cleanly via ``asdict``; the kinds_observed dict is
    flattened to a stable schema (one entry per kind)."""
    payload = {
        "source": rep.source,
        "total_events": rep.total_events,
        "overall_first_seen": rep.overall_first_seen,
        "overall_last_seen": rep.overall_last_seen,
        "overall_span_days": rep.overall_span_days,
        "kinds_observed": {
            k: asdict(v) for k, v in rep.kinds_observed.items()
        },
        "kinds_missing": list(rep.kinds_missing),
        "parse_stats": asdict(rep.parse_stats),
    }
    return payload


def format_human(rep: SignalBaselineReport) -> str:
    lines = [
        "=== SIGNAL BASELINE REPORT ===",
        f"source:               {rep.source}",
        f"files read:           {rep.parse_stats.files_read}",
        f"total events:         {rep.total_events}",
        f"overall span (days):  {rep.overall_span_days:.2f}",
        f"first seen:           {rep.overall_first_seen or '-'}",
        f"last seen:            {rep.overall_last_seen or '-'}",
        "",
        "parse stats:",
        f"  lines:              {rep.parse_stats.total_lines}",
        f"  parsed:             {rep.parse_stats.parsed}",
        f"  malformed_json:     {rep.parse_stats.malformed_json}",
        f"  missing_kind:       {rep.parse_stats.missing_kind}",
        "",
        "kinds observed:",
    ]
    if not rep.kinds_observed:
        lines.append("  (none)")
    for kind in sorted(rep.kinds_observed):
        s = rep.kinds_observed[kind]
        lines.append(
            f"  [{kind:>14s}] count={s.count:>4d} "
            f"span={s.span_days:>5.1f}d "
            f"active_days={s.distinct_active_days:>2d}  "
            f"-> {s.classification}"
        )
        if s.distinct_places is not None:
            lines.append(
                f"  {'':14s}  distinct_places={s.distinct_places}"
            )
        if s.granularity_note:
            lines.append(f"  {'':14s}  NOTE: {s.granularity_note}")
    lines.extend([
        "",
        f"expected kinds not present in logs ({len(rep.kinds_missing)}):",
    ])
    if rep.kinds_missing:
        for k in rep.kinds_missing:
            lines.append(f"  - {k}")
    else:
        lines.append("  (none — every expected kind has at least one event)")
    lines.extend([
        "",
        "Reminder: 'not present in logs' is advisory; it does NOT mean",
        "the corresponding Shortcut is broken. Check ",
        "logs/iphone_shortcuts_status.md for operator diagnosis.",
    ])
    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "").strip().splitlines()[0]
        if (__doc__ or "").strip()
        else "Signal baseline sufficiency report",
    )
    ap.add_argument(
        "--dir", type=Path,
        default=_REPO_ROOT / "logs" / "signals",
        help="JSONL directory to read (default: logs/signals/)",
    )
    ap.add_argument(
        "--json", action="store_true",
        help="emit machine-readable JSON instead of human-readable",
    )
    args = ap.parse_args(argv)

    rep = build_report(args.dir, source_label=str(args.dir))
    if args.json:
        print(json.dumps(to_json_payload(rep), indent=2, sort_keys=True))
    else:
        print(format_human(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
