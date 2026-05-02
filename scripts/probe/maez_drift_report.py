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
# Threshold inheritance note: numbers were originally chosen to
# mirror memory/quality_tracker.py:236 which uses a different
# metric (approved/decided where outcomes are approved+cancelled
# +rejected). The audit_log.db population has no `cancelled`
# class at all — cockpit cards don't get auto-cancelled — so the
# denominator is structurally smaller and approval rates trend
# higher. Production reads ~98% which is far above WARN, so
# 0.4/0.6 are not actively wrong but they aren't re-baselined for
# the new metric either. TODO: re-baseline once 90 days of
# audit_log data accumulates and the empirical distribution is
# stable.

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


# Recognized outcome strings the probe maps explicitly. Anything
# else is captured in QualityResult.unknown_outcomes so the
# operator can see what the probe is dropping. Particularly:
# `refused_by_will` is a Maez-side refusal (decision_pipeline
# refused on covenant/will-I grounds without owner ever seeing
# the card). It's a real non-approval but currently doesn't
# weight the rate; surfacing the count keeps the operator
# informed.
_RECOGNIZED_OUTCOMES = frozenset({
    "approved_and_ran",
    "approved_and_failed",
    "rohit_rejected",
})


@dataclass
class QualityResult:
    """Quality stream metrics — owner approval rate from
    audit_log.db (the cockpit / decision-pipeline approval
    surface, where the operator actually decides today).

    G.A.1 fix: the original G.A read quality.db, which only sees
    ActionEngine's internal lifecycle outcomes. Cockpit approvals
    write to audit_log.db with a different vocabulary
    (``approved_and_ran`` / ``approved_and_failed`` /
    ``rohit_rejected``). Reading the wrong DB produced 0
    approved across 459 Tier-2 actions despite the operator
    actively approving via cockpit (302 decisions in 30 days
    against the corrected DB).

        decided = approved_count + rejected_count
        approval_rate = approved_count / decided
            if decided > 0 else 0.0

    Outcome mapping (audit_log → probe):

        approved_and_ran    → approved_count (decision was approve;
                              action ran successfully)
        approved_and_failed → approved_count (decision was approve;
                              action failed downstream — execution-
                              side problem, not approval-side)
        rohit_rejected      → rejected_count
        anything else / NULL → pending_count (informational; not
                              part of approval rate)

    ``approved_and_failed_count`` surfaced separately as an
    execution-failure signal that's distinct from approval rate.
    ``pending_count`` is informational.
    """
    approval_rate: float
    decided_actions: int
    approved_count: int
    approved_and_failed_count: int
    rejected_count: int
    pending_count: int
    classification: str
    # M1 from G.A.1 review: capture outcomes the probe doesn't
    # explicitly recognize. Surfaced in human + JSON output so an
    # operator sees gaps rather than silently losing them.
    # Particularly: ``refused_by_will`` (decision_pipeline.py:615)
    # is a Maez-side refusal — a real non-approval the operator
    # would want to know about.
    unknown_outcomes: dict = field(default_factory=dict)
    # 7-day rolling rate alongside the 30-day primary so a recent
    # regime shift surfaces within days, not within a month. Set
    # to None when there's insufficient recent data.
    recent_approval_rate: float | None = None
    recent_decided_actions: int = 0


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


def classify_approval(db_path: Path,
                      *, window_days: int = 30) -> QualityResult:
    """Read audit_log.db within the window and classify owner
    approval rate from the cockpit/decision-pipeline surface.

    G.A.1 corrects the original G.A which read the wrong DB.
    See the QualityResult docstring for the outcome mapping +
    rationale.

    INSUFFICIENT_DATA when ``decided < QUALITY_MIN_DECIDED`` —
    a fresh deploy or a quiet period will have few owner
    decisions; we don't claim health from a tiny sample."""
    if not db_path.exists():
        return QualityResult(
            approval_rate=0.0,
            decided_actions=0, approved_count=0,
            approved_and_failed_count=0, rejected_count=0,
            pending_count=0,
            classification="INSUFFICIENT_DATA",
        )
    cutoff = time.time() - window_days * 86400.0
    cutoff_recent = time.time() - 7 * 86400.0
    try:
        con = sqlite3.connect(db_path)
        # outcome_ts is set when a card resolves; ts is when the
        # audit row was created. Pending cards have outcome_ts NULL
        # so we filter on (outcome_ts >= cutoff) for resolved rows
        # and count NULL-outcome rows separately as pending if
        # their proposal ts is recent.
        cur = con.execute(
            "SELECT outcome, COUNT(*) FROM audit_log "
            "WHERE outcome IS NOT NULL "
            "AND outcome_ts >= ? "
            "GROUP BY outcome",
            (cutoff,),
        )
        decided_rows = cur.fetchall()
        # 7-day rolling window for regime-shift detection — a
        # recent collapse in approval rate surfaces within days
        # rather than being averaged out by a month of healthy
        # data ahead of the dip.
        recent_cur = con.execute(
            "SELECT outcome, COUNT(*) FROM audit_log "
            "WHERE outcome IS NOT NULL "
            "AND outcome_ts >= ? "
            "GROUP BY outcome",
            (cutoff_recent,),
        )
        recent_rows = recent_cur.fetchall()
        # Count pending (NULL outcome) cards proposed within the
        # window. Informational only — not part of approval rate.
        pending_n = con.execute(
            "SELECT COUNT(*) FROM audit_log "
            "WHERE outcome IS NULL AND ts >= ?",
            (cutoff,),
        ).fetchone()[0]
        con.close()
    except sqlite3.Error:
        return QualityResult(
            approval_rate=0.0,
            decided_actions=0, approved_count=0,
            approved_and_failed_count=0, rejected_count=0,
            pending_count=0,
            classification="INSUFFICIENT_DATA",
        )

    counts = {row[0] or "": int(row[1]) for row in decided_rows}
    approved_ran = counts.get("approved_and_ran", 0)
    approved_failed = counts.get("approved_and_failed", 0)
    rejected_n = counts.get("rohit_rejected", 0)
    approved_n = approved_ran + approved_failed
    decided = approved_n + rejected_n
    # M1 from G.A.1 review: outcomes the probe doesn't explicitly
    # map. Includes Maez-side refusals (refused_by_will), expirations,
    # errors, and any future strings. Surface these so the operator
    # sees what the probe is dropping rather than silently losing
    # them.
    unknown = {
        outcome: count
        for outcome, count in counts.items()
        if outcome not in _RECOGNIZED_OUTCOMES
    }

    # 7-day rolling rate (only computed if there's enough decided
    # data in the window — otherwise None to signal "no recent
    # regime to compare against").
    recent_counts = {row[0] or "": int(row[1]) for row in recent_rows}
    recent_approved = (
        recent_counts.get("approved_and_ran", 0)
        + recent_counts.get("approved_and_failed", 0)
    )
    recent_rejected = recent_counts.get("rohit_rejected", 0)
    recent_decided = recent_approved + recent_rejected
    recent_rate: float | None = None
    if recent_decided >= QUALITY_MIN_DECIDED:
        recent_rate = recent_approved / recent_decided

    if decided < QUALITY_MIN_DECIDED:
        return QualityResult(
            approval_rate=0.0,
            decided_actions=decided,
            approved_count=approved_n,
            approved_and_failed_count=approved_failed,
            rejected_count=rejected_n,
            pending_count=int(pending_n),
            classification="INSUFFICIENT_DATA",
            unknown_outcomes=unknown,
            recent_approval_rate=recent_rate,
            recent_decided_actions=recent_decided,
        )
    rate = approved_n / decided

    # Classification fires CRITICAL only when BOTH the 30-day
    # primary AND the 7-day recent rate agree. This avoids
    # 7-day-noise alerts during legitimately quiet periods AND
    # avoids 30-day-stickiness hiding a recent collapse. WARN
    # fires on either being concerning.
    primary_critical = rate < QUALITY_APPROVAL_CRITICAL
    primary_warn = rate < QUALITY_APPROVAL_WARN
    recent_critical = (
        recent_rate is not None and recent_rate < QUALITY_APPROVAL_CRITICAL
    )
    recent_warn = (
        recent_rate is not None and recent_rate < QUALITY_APPROVAL_WARN
    )

    if primary_critical and recent_critical:
        cls = "CRITICAL"
    elif primary_critical or primary_warn or recent_critical or recent_warn:
        cls = "WARN"
    else:
        cls = "OK"

    return QualityResult(
        approval_rate=rate,
        decided_actions=decided,
        approved_count=approved_n,
        approved_and_failed_count=approved_failed,
        rejected_count=rejected_n,
        pending_count=int(pending_n),
        classification=cls,
        unknown_outcomes=unknown,
        recent_approval_rate=recent_rate,
        recent_decided_actions=recent_decided,
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
    audit_log_db: Path,
    window_hours: int = 24,
    quality_window_days: int = 30,
    source_label: str | None = None,
) -> DriftReport:
    """Read all three streams, classify each, return composite
    report.

    G.A.1: ``audit_log_db`` parameter (was ``quality_db`` in
    original G.A). The drift report now reads from audit_log.db,
    the cockpit/decision-pipeline approval surface where owner
    decisions actually land. See QualityResult docstring."""
    cog_text = ""
    if cognition_log.exists():
        try:
            # Read full log; window-by-time is a future refinement
            # once the log volume justifies it. Today the file is
            # 11MB and this is fast enough.
            cog_text = cognition_log.read_text(errors="replace")
        except OSError:
            cog_text = ""
        cog_text = _filter_cognition_window(cog_text, window_hours)

    cycles = parse_cognition_lines(cog_text)
    cognition = classify_cognition(cycles)
    quality = classify_approval(
        audit_log_db, window_days=quality_window_days,
    )
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
        "owner approval (audit_log.db):",
        f"  classification:      {report.quality.classification}",
        f"  decided_actions:     {report.quality.decided_actions} "
        "(approved + rejected)",
        f"  approval_rate:       {report.quality.approval_rate:.1%} "
        "(approved / decided, last "
        f"{report.quality_window_days} days)",
    ]
    if report.quality.recent_approval_rate is not None:
        lines.append(
            f"  recent_approval:     "
            f"{report.quality.recent_approval_rate:.1%} "
            f"(last 7 days, n={report.quality.recent_decided_actions})"
        )
    else:
        lines.append(
            "  recent_approval:     -- (insufficient 7d data)"
        )
    lines.extend([
        f"  approved_count:      {report.quality.approved_count} "
        f"(of which {report.quality.approved_and_failed_count} "
        "failed downstream)",
        f"  rejected_count:      {report.quality.rejected_count}",
        f"  pending_count:       {report.quality.pending_count} "
        "(unresolved cards in window; informational)",
    ])
    # M1 from G.A.1 review: surface unrecognized outcomes loudly
    # (e.g., refused_by_will, expired, error, future strings) so
    # the operator sees what the probe is dropping.
    if report.quality.unknown_outcomes:
        lines.append(
            f"  unknown_outcomes:    "
            f"{dict(report.quality.unknown_outcomes)}"
        )
        lines.append(
            "    NOTE: above outcomes aren't classified as "
            "approved/rejected — see source code's "
            "_RECOGNIZED_OUTCOMES set"
        )
    lines.extend([
        "",
        "liveness (cognition.log mtime):",
        f"  classification:      {report.liveness.classification}",
    ])
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
        "--audit-log-db", type=Path,
        default=_REPO_ROOT / "memory" / "audit_log.db",
        help=(
            "audit_log.db path (default: memory/audit_log.db). "
            "G.A.1 corrected the source — was reading quality.db "
            "which has the wrong observability semantic."
        ),
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
        audit_log_db=args.audit_log_db,
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
