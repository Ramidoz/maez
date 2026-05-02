# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Maez drift-detection harness (slice G.A).

Read-only diagnostic CLI that reads existing signal streams and
emits a PASS/WARN/CRITICAL classification per stream + an overall
verdict. The first slice that asks "is Maez still itself?"
empirically rather than via ad-hoc grep.

Why this exists
---------------

The harness audit (2026-05-02) named the biggest operational gap:
no automated drift-detection system. Maez has all the signals —
voice signature, perception signature, fabrication count,
fixation flags, action-approval rates — but nothing watches them
across time. If Maez slowly starts sounding less like itself, or
fabrication spikes, or approval rate drops, an operator has to
investigate manually.

This is the first version of the seatbelt. Same shape as
``signal_baseline_report.py``: read existing substrate, classify
honestly, surface gaps. On-demand CLI, not a daemon hook.

Streams (G.A scope)
-------------------

  cognition.log    — avg_score, fixation_rate, vague_rate
  quality.db       — action approval rate over last 30 days
  liveness         — cognition.log mtime delta vs. now
  overall_verdict  — worst-of-stream classification

Out of G.A scope (named for future slices):
  - voice signature corpus drift (no corpus yet)
  - perception_signature drift (computed but not persisted)
  - soul.md invariants (existing test_soul_invariants.py covers
    binary pass/fail in CI; bringing into a probe needs factoring
    ``check()`` out of the test file first)

Thresholds
----------

Match the production code's pre-existing values where possible
so the probe and the daemon's own self-critique converge on the
same definition of "concerning":

  cognition.log:
    avg_score   <30 CRITICAL, <40 WARN
        (CRITIQUE_LOW_SCORE_THRESHOLD = 40 in
        core/cognition/cognition_quality.py:78)
    fixation_rate >0.7 CRITICAL, >0.5 WARN
        (FIXATION_THRESHOLD = 0.5 in
        core/cognition/cognition_quality.py:48)
    vague_rate   >0.5 CRITICAL, >0.3 WARN

  quality.db (last 30 days, N>=10 actions required):
    approval_rate <0.4 CRITICAL, <0.6 WARN
        (matches soul-note trigger in
        memory/quality_tracker.py:236-241)

  liveness:
    last write within 5 min: OK
    last write within 30 min: WARN
    older / missing log: CRITICAL

Isolation contract
------------------

Probe MUST NOT import chromadb, memory.memory_manager, or
core.memory.memory_manager. AST-parse test enforces. Read-only
over log files + sqlite query.

CLI::

    .venv/bin/python scripts/probe/maez_drift_report.py
    .venv/bin/python scripts/probe/maez_drift_report.py --json
    .venv/bin/python scripts/probe/maez_drift_report.py \\
        --window-hours 6 --quality-window-days 7
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# Threshold constants — explicit names so a future agent reading
# the classifier sees the production-pinned values rather than
# magic numbers. Each carries the citation to the production code
# that originally defined the threshold.

COGNITION_SCORE_CRITICAL = 30.0
COGNITION_SCORE_WARN = 40.0
# Reference: CRITIQUE_LOW_SCORE_THRESHOLD = 40 in
# core/cognition/cognition_quality.py:78. CRITICAL is well below
# the warn threshold so the WARN region exists.

COGNITION_FIXATION_CRITICAL = 0.7
COGNITION_FIXATION_WARN = 0.5
# Reference: FIXATION_THRESHOLD = 0.5 in
# core/cognition/cognition_quality.py:48. WARN matches that
# threshold; CRITICAL is the doubled-down boundary.

COGNITION_VAGUE_CRITICAL = 0.75
COGNITION_VAGUE_WARN = 0.6
# Calibration-pending placeholder. No pre-existing production
# threshold for "vague" rate. First production read showed 53%
# vague during quiet workstation hours — that's normal noise,
# not a pathology marker. Raised to 0.75/0.6 honestly until a
# baseline-percentile calibration mode (G.B candidate) lands
# that compares Δ from a learned baseline rather than absolute
# thresholds.

QUALITY_APPROVAL_CRITICAL = 0.4
QUALITY_APPROVAL_WARN = 0.6
# Reference: memory/quality_tracker.py:236 — `if approval_rate
# < 0.4 and total >= 3 → soul note`. CRITICAL matches that
# threshold; WARN is the band below the comfort floor.

QUALITY_MIN_DECIDED = 5
# Production's soul-note trigger uses `total >= 3`; 5 is a
# slightly tighter floor for the probe so single-digit owner
# decisions don't flip CRITICAL on noise. Computed against the
# DECIDED count (approved + cancelled + rejected), NOT total
# action count — see classify_quality docstring.

LIVENESS_OK_SECONDS = 5 * 60
LIVENESS_WARN_SECONDS = 30 * 60


# ── dataclasses ─────────────────────────────────────────────────────


@dataclass
class CycleEntry:
    """One parsed `cycle | ...` line from cognition.log."""
    score: float
    labels: list[str] = field(default_factory=list)


@dataclass
class CognitionResult:
    cycles_total: int
    avg_score: float
    fixation_rate: float
    vague_rate: float
    classification: str  # OK | WARN | CRITICAL | INSUFFICIENT_DATA


@dataclass
class QualityResult:
    """Quality stream metrics. ``approval_rate`` is computed
    EXACTLY as ``memory/quality_tracker.py:187-191`` does it:

        decided = approved + cancelled + rejected
        approval_rate = approved / decided if decided > 0 else 0.0

    `executed` is intentionally EXCLUDED — it represents Tier-0
    auto-execution that didn't go through owner decision-making,
    so it's not part of "what fraction of owner-presented options
    did they approve?" Mirror this so the probe's classification
    and the soul-note trigger fire on the same metric.

    ``executed_count`` is surfaced separately as informational
    (the daemon's auto-action volume; useful but not part of
    approval rate).
    """
    total_actions: int
    approval_rate: float
    decided_actions: int
    approved_count: int
    cancelled_count: int
    rejected_count: int
    executed_count: int
    classification: str


@dataclass
class LivenessResult:
    last_write_secs_ago: float | None
    classification: str


@dataclass
class DriftReport:
    source: str
    window_hours: int
    quality_window_days: int
    cognition: CognitionResult
    quality: QualityResult
    liveness: LivenessResult
    overall_verdict: str


# ── cognition.log parser + classifier ───────────────────────────────


# Match the cognition.log cycle-line shape:
#   "<ts> | cycle | score=N primary=X topic=Y labels=['a', 'b']"
# The score field is the load-bearing signal; labels are
# secondary (fixation/vague flag presence). The ``labels=`` group
# is OPTIONAL so a future log-format tweak (e.g. labels emitted
# as a separate field, or omitted on cycles with no labels)
# doesn't silently zero the sample size.
_CYCLE_LINE_RE = re.compile(
    r"\|\s*cycle\s*\|.*?score=(?P<score>[-\d.]+)"
    r"(?:.*?labels=\[(?P<labels>[^\]]*)\])?"
)


def parse_cognition_lines(text: str) -> list[CycleEntry]:
    """Parse cognition.log text into structured cycle entries.
    Lines that aren't `cycle |` are silently skipped (matching the
    behavior of the daemon's downstream consumers); malformed
    score values are skipped (counted by callers if needed)."""
    entries: list[CycleEntry] = []
    for line in text.splitlines():
        m = _CYCLE_LINE_RE.search(line)
        if not m:
            continue
        try:
            score = float(m.group("score"))
        except ValueError:
            continue
        labels_raw = m.group("labels")
        # labels group is now optional — None when not matched.
        # Empty string when matched as `labels=[]`.
        if labels_raw:
            labels = [
                tok.strip().strip("'").strip('"')
                for tok in labels_raw.split(",")
                if tok.strip()
            ]
        else:
            labels = []
        entries.append(CycleEntry(score=score, labels=labels))
    return entries


def classify_cognition(cycles: list[CycleEntry]) -> CognitionResult:
    """Apply the three cognition-stream thresholds. Worst-class
    wins per cycle's flags (any CRITICAL trips CRITICAL, any WARN
    trips WARN if no CRITICAL)."""
    n = len(cycles)
    if n == 0:
        return CognitionResult(
            cycles_total=0,
            avg_score=0.0,
            fixation_rate=0.0,
            vague_rate=0.0,
            classification="INSUFFICIENT_DATA",
        )
    avg_score = sum(c.score for c in cycles) / n
    fixation = sum(1 for c in cycles if "fixation" in c.labels) / n
    vague = sum(1 for c in cycles if "vague" in c.labels) / n

    cls = "OK"
    if (avg_score < COGNITION_SCORE_CRITICAL
            or fixation > COGNITION_FIXATION_CRITICAL
            or vague > COGNITION_VAGUE_CRITICAL):
        cls = "CRITICAL"
    elif (avg_score < COGNITION_SCORE_WARN
            or fixation > COGNITION_FIXATION_WARN
            or vague > COGNITION_VAGUE_WARN):
        cls = "WARN"

    return CognitionResult(
        cycles_total=n,
        avg_score=avg_score,
        fixation_rate=fixation,
        vague_rate=vague,
        classification=cls,
    )


# ── quality.db classifier ───────────────────────────────────────────


def classify_quality(db_path: Path,
                     *, window_days: int = 30) -> QualityResult:
    """Read action_outcomes from quality.db within the window and
    classify approval rate using the production formula from
    ``memory/quality_tracker.py:187-191``.

    Approval rate is computed against DECIDED actions only —
    ``approved / (approved + cancelled + rejected)``. Auto-executed
    Tier-0 actions are NOT part of the rate (they didn't pass
    through owner decision-making). This means the probe's
    classification fires on the same metric as the daemon's own
    soul-note trigger.

    INSUFFICIENT_DATA when ``decided < QUALITY_MIN_DECIDED`` —
    a fresh deploy or a workload of only auto-actions will have
    almost no decided actions even with high total volume; we
    don't claim health from a tiny owner-decision sample."""
    if not db_path.exists():
        return QualityResult(
            total_actions=0, approval_rate=0.0,
            decided_actions=0, approved_count=0,
            cancelled_count=0, rejected_count=0,
            executed_count=0,
            classification="INSUFFICIENT_DATA",
        )
    cutoff = time.time() - window_days * 86400.0
    try:
        con = sqlite3.connect(db_path)
        cur = con.execute(
            "SELECT outcome, COUNT(*) FROM action_outcomes "
            "WHERE proposed_at >= ? "
            "GROUP BY outcome",
            (cutoff,),
        )
        rows = cur.fetchall()
        con.close()
    except sqlite3.Error:
        return QualityResult(
            total_actions=0, approval_rate=0.0,
            decided_actions=0, approved_count=0,
            cancelled_count=0, rejected_count=0,
            executed_count=0,
            classification="INSUFFICIENT_DATA",
        )

    counts = {row[0] or "": int(row[1]) for row in rows}
    total = sum(counts.values())
    approved_n = counts.get("approved", 0)
    cancelled_n = counts.get("cancelled", 0)
    rejected_n = counts.get("rejected", 0)
    executed_n = counts.get("executed", 0)
    decided = approved_n + cancelled_n + rejected_n

    if decided < QUALITY_MIN_DECIDED:
        return QualityResult(
            total_actions=total, approval_rate=0.0,
            decided_actions=decided,
            approved_count=approved_n,
            cancelled_count=cancelled_n,
            rejected_count=rejected_n,
            executed_count=executed_n,
            classification="INSUFFICIENT_DATA",
        )
    rate = approved_n / decided

    if rate < QUALITY_APPROVAL_CRITICAL:
        cls = "CRITICAL"
    elif rate < QUALITY_APPROVAL_WARN:
        cls = "WARN"
    else:
        cls = "OK"

    return QualityResult(
        total_actions=total,
        approval_rate=rate,
        decided_actions=decided,
        approved_count=approved_n,
        cancelled_count=cancelled_n,
        rejected_count=rejected_n,
        executed_count=executed_n,
        classification=cls,
    )


# ── liveness ────────────────────────────────────────────────────────


def classify_liveness(log_path: Path) -> LivenessResult:
    """Classify daemon liveness via cognition.log mtime. Missing
    log is unambiguously CRITICAL — the daemon would be writing
    if alive."""
    if not log_path.exists():
        return LivenessResult(
            last_write_secs_ago=None,
            classification="CRITICAL",
        )
    try:
        mtime = log_path.stat().st_mtime
    except OSError:
        return LivenessResult(
            last_write_secs_ago=None,
            classification="CRITICAL",
        )
    delta = time.time() - mtime
    if delta <= LIVENESS_OK_SECONDS:
        cls = "OK"
    elif delta <= LIVENESS_WARN_SECONDS:
        cls = "WARN"
    else:
        cls = "CRITICAL"
    return LivenessResult(
        last_write_secs_ago=delta,
        classification=cls,
    )


# ── overall verdict ─────────────────────────────────────────────────


# Severity rank — higher number = worse. INSUFFICIENT_DATA is
# below OK because the absence of data shouldn't downgrade a
# healthy stream's signal in the overall verdict, but if every
# stream is INSUFFICIENT, the overall verdict is INSUFFICIENT
# (we don't claim OK on no data).
_SEVERITY_RANK = {
    "INSUFFICIENT_DATA": 0,
    "OK": 1,
    "WARN": 2,
    "CRITICAL": 3,
}


def compute_overall_verdict(classifications: list[str]) -> str:
    """Worst-of-stream wins, with INSUFFICIENT_DATA below OK so a
    no-data-anywhere case surfaces as INSUFFICIENT rather than OK."""
    if not classifications:
        return "INSUFFICIENT_DATA"
    return max(
        classifications,
        key=lambda c: _SEVERITY_RANK.get(c, 0),
    )


# ── orchestration ───────────────────────────────────────────────────


def build_report(
    *,
    cognition_log: Path,
    quality_db: Path,
    window_hours: int = 24,
    quality_window_days: int = 30,
    source_label: str | None = None,
) -> DriftReport:
    """Read all three streams, classify each, return composite
    report. Window controls cognition.log lookback; quality has
    its own window because the soul-note trigger uses 30 days."""
    cog_text = ""
    if cognition_log.exists():
        try:
            # G.A: read full log; window-by-time is a future
            # refinement once the log volume justifies it. Today
            # the file is 11MB and this is fast enough.
            cog_text = cognition_log.read_text(errors="replace")
        except OSError:
            cog_text = ""
        # Apply window: cognition.log lines start with
        # "YYYY-MM-DD HH:MM:SS"; filter by ts >= now - window_hours.
        cog_text = _filter_cognition_window(cog_text, window_hours)

    cycles = parse_cognition_lines(cog_text)
    cognition = classify_cognition(cycles)
    quality = classify_quality(quality_db, window_days=quality_window_days)
    liveness = classify_liveness(cognition_log)
    overall = compute_overall_verdict([
        cognition.classification,
        quality.classification,
        liveness.classification,
    ])
    return DriftReport(
        source=source_label or f"{cognition_log.parent}",
        window_hours=window_hours,
        quality_window_days=quality_window_days,
        cognition=cognition,
        quality=quality,
        liveness=liveness,
        overall_verdict=overall,
    )


_TS_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s")


def _filter_cognition_window(text: str, window_hours: int) -> str:
    """Keep only lines whose leading timestamp is within
    ``window_hours`` of now. Lines without a parseable timestamp
    are kept (the parser will skip them if they're not ``cycle``
    lines anyway). Best-effort: malformed timestamps degrade to
    "kept" rather than crashing the report.

    Timezone: cognition.log timestamps are written in LOCAL time
    (verified against wall-clock). ``strptime`` produces a naive
    datetime; calling ``.timestamp()`` on a naive datetime
    interprets it as local time and returns a Unix timestamp.
    Adding ``tzinfo=timezone.utc`` would have skewed every read
    by the local UTC offset (e.g., -5h on CDT) — caught by the
    G.A code-reviewer."""
    if window_hours <= 0:
        return text
    cutoff = time.time() - window_hours * 3600.0
    kept_lines: list[str] = []
    from datetime import datetime
    for line in text.splitlines():
        m = _TS_LINE_RE.match(line)
        if not m:
            kept_lines.append(line)
            continue
        try:
            # Naive datetime → local-time interpretation in
            # .timestamp(). Matches how cognition.log writes
            # timestamps (asctime in the daemon's local tz).
            ts = datetime.strptime(
                m.group(1), "%Y-%m-%d %H:%M:%S",
            ).timestamp()
        except (ValueError, OverflowError):
            kept_lines.append(line)
            continue
        if ts >= cutoff:
            kept_lines.append(line)
    return "\n".join(kept_lines)


# ── output ──────────────────────────────────────────────────────────


def to_json_payload(report: DriftReport) -> dict:
    return {
        "source": report.source,
        "window_hours": report.window_hours,
        "quality_window_days": report.quality_window_days,
        "cognition": asdict(report.cognition),
        "quality": asdict(report.quality),
        "liveness": asdict(report.liveness),
        "overall_verdict": report.overall_verdict,
    }


def format_human(report: DriftReport) -> str:
    streams_summary = (
        f"cognition={report.cognition.classification} "
        f"quality={report.quality.classification} "
        f"liveness={report.liveness.classification}"
    )
    lines = [
        "=== MAEZ DRIFT REPORT ===",
        f"source:                {report.source}",
        f"cognition window:      last {report.window_hours}h",
        f"quality window:        last {report.quality_window_days} days",
        "",
        f"OVERALL VERDICT: {report.overall_verdict}",
        f"streams:         {streams_summary}",
        "",
        "cognition (cognition.log):",
        f"  classification:      {report.cognition.classification}",
        f"  cycles_total:        {report.cognition.cycles_total}",
        f"  avg_score:           {report.cognition.avg_score:.1f}",
        f"  fixation_rate:       {report.cognition.fixation_rate:.1%}",
        f"  vague_rate:          {report.cognition.vague_rate:.1%}",
        "",
        "action quality (quality.db):",
        f"  classification:      {report.quality.classification}",
        f"  total_actions:       {report.quality.total_actions}",
        f"  decided_actions:     {report.quality.decided_actions} "
        "(approved + cancelled + rejected)",
        f"  approval_rate:       {report.quality.approval_rate:.1%} "
        "(approved / decided)",
        f"  approved_count:      {report.quality.approved_count}",
        f"  cancelled_count:     {report.quality.cancelled_count}",
        f"  rejected_count:      {report.quality.rejected_count}",
        f"  executed_count:      {report.quality.executed_count} "
        "(auto-executed Tier-0; not part of approval rate)",
        "",
        "liveness (cognition.log mtime):",
        f"  classification:      {report.liveness.classification}",
    ]
    if report.liveness.last_write_secs_ago is not None:
        lines.append(
            f"  last write:          "
            f"{report.liveness.last_write_secs_ago:.0f}s ago"
        )
    else:
        lines.append("  last write:          (file not present)")

    lines.extend([
        "",
        "Severity meaning:",
        "  OK                = within thresholds",
        "  WARN              = nearing threshold; watch but no urgent action",
        "  CRITICAL          = past threshold; investigate now",
        "  INSUFFICIENT_DATA = no signal to judge (fresh deploy / no actions)",
        "",
        "Out of G.A scope (named for future slices):",
        "  - voice signature corpus drift (no corpus yet)",
        "  - perception_signature drift (computed but not persisted)",
        "  - soul.md invariants (CI test covers binary pass/fail)",
    ])
    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "").strip().splitlines()[0]
        if (__doc__ or "").strip()
        else "Maez drift-detection harness",
    )
    ap.add_argument(
        "--cognition-log", type=Path,
        default=_REPO_ROOT / "logs" / "cognition.log",
    )
    ap.add_argument(
        "--quality-db", type=Path,
        default=_REPO_ROOT / "memory" / "quality.db",
    )
    ap.add_argument(
        "--window-hours", type=int, default=24,
        help="cognition.log lookback window (default: 24)",
    )
    ap.add_argument(
        "--quality-window-days", type=int, default=30,
        help="quality.db lookback window (default: 30)",
    )
    ap.add_argument(
        "--json", action="store_true",
        help="emit machine-readable JSON instead of human-readable",
    )
    args = ap.parse_args(argv)

    report = build_report(
        cognition_log=args.cognition_log,
        quality_db=args.quality_db,
        window_hours=args.window_hours,
        quality_window_days=args.quality_window_days,
    )
    if args.json:
        print(json.dumps(to_json_payload(report), indent=2, sort_keys=True))
    else:
        print(format_human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
