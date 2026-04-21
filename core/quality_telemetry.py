# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""quality_telemetry.py — aggregate the quality-signal streams that
landed this session so the cockpit (and operators) can see what's
actually happening in the daemon.

Three streams live in logs/cognition.log today:

  self_claim_audit | surface=X flagged=N mode=M kinds=K [reason=R]
  error_classifier | surface=X class=K retryable=N transient=N
                   | structural=N compress=N msg='...'
  consolidation_scores | n=N min=F median=F max=F

Plus one SQLite sidecar:

  memory/recall_stats.db  (per-memory recall statistics)
  memory/fabrication_log.db  (fabrication_events table)

This module tails the log file with a size-capped read (same pattern
as core.self_model) and parses the last N lines of each shape, returning
a single roll-up dict suitable for HTTP/JSON. Does NOT stream — callers
poll at whatever cadence they want.

Why pure-read: the daemon is the only writer to cognition.log; keeping
telemetry as append-only log + sidecar DBs means readers never contend
with writers, we can rebuild aggregates from scratch, and a separate
process (cockpit) can poll without touching daemon internals.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.quality_telemetry")

_MAEZ_HOME = Path("/home/rohit/maez")
_COG_LOG = _MAEZ_HOME / "logs" / "cognition.log"
_FAB_DB = _MAEZ_HOME / "memory" / "fabrication_log.db"
_RECALL_DB = _MAEZ_HOME / "memory" / "recall_stats.db"

_READ_TAIL_BYTES = 400_000   # enough to cover ~thousands of lines

# Shape patterns for the three streams. All use re.search so timestamp
# prefix is ignored.
_AUDIT_RE = re.compile(
    r"self_claim_audit\s*\|\s*surface=(?P<surface>\S+)\s+"
    r"flagged=(?P<flagged>\d+)\s+mode=(?P<mode>\S+)\s+kinds=(?P<kinds>\S+)"
)
_ERROR_RE = re.compile(
    r"error_classifier\s*\|\s*surface=(?P<surface>\S+)\s+"
    r"class=(?P<cls>\S+)\s+retryable=(?P<retryable>\d+)\s+"
    r"transient=(?P<transient>\d+)\s+"
    r"structural=(?P<structural>\d+)\s+compress=(?P<compress>\d+)"
)
_CONSOL_RE = re.compile(
    r"consolidation_scores\s*\|\s*n=(?P<n>\d+)\s+"
    r"min=(?P<min>[\d.]+)\s+median=(?P<median>[\d.]+)\s+"
    r"max=(?P<max>[\d.]+)"
)


# ── data shape ─────────────────────────────────────────────────────────

@dataclass
class AuditRollup:
    """Summary of self_claim_audit events."""
    total: int = 0
    by_mode: dict[str, int] = field(default_factory=dict)
    by_surface: dict[str, int] = field(default_factory=dict)
    # Total flagged count across all events (sum of flagged=N).
    total_flags: int = 0
    # Flag RATE = events with flagged>0 divided by total (0.0-1.0).
    flag_rate: float = 0.0


@dataclass
class ErrorRollup:
    """Summary of error_classifier events."""
    total: int = 0
    by_class: dict[str, int] = field(default_factory=dict)
    by_surface: dict[str, int] = field(default_factory=dict)
    transient_count: int = 0
    structural_count: int = 0


@dataclass
class ConsolidationRollup:
    """Summary of consolidation_scores events — last-observed distribution."""
    last_n: int = 0
    last_min: float = 0.0
    last_median: float = 0.0
    last_max: float = 0.0
    observations: int = 0  # how many consolidation_scores events were parsed


@dataclass
class FabricationSnapshot:
    """Latest rows from fabrication_log.db — judge-flagged claims."""
    total_events: int = 0
    recent: list[dict] = field(default_factory=list)


@dataclass
class RecallSnapshot:
    """Memory-scoring sidecar summary."""
    total_memories_tracked: int = 0
    total_recalls: int = 0
    consolidated_count: int = 0


@dataclass
class QualityRollup:
    """Top-level rollup suitable for JSON serialization to the cockpit."""
    generated_at: float
    source_log_path: str
    audit: AuditRollup
    errors: ErrorRollup
    consolidation: ConsolidationRollup
    fabrication: FabricationSnapshot
    recall: RecallSnapshot

    def to_json(self) -> dict:
        """Convert to a JSON-safe nested dict."""
        return {
            "generated_at": self.generated_at,
            "source_log_path": self.source_log_path,
            "audit": asdict(self.audit),
            "errors": asdict(self.errors),
            "consolidation": asdict(self.consolidation),
            "fabrication": asdict(self.fabrication),
            "recall": asdict(self.recall),
        }


# ── log tail ──────────────────────────────────────────────────────────

def _read_tail(path: Path, cap_bytes: int = _READ_TAIL_BYTES) -> str:
    """Read the tail of a log file. Returns empty string on any failure."""
    if not path.exists():
        return ""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - cap_bytes)
            f.seek(start)
            return f.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("tail read failed for %s: %s", path, e)
        return ""


def _parse_audit_lines(blob: str, limit: int) -> AuditRollup:
    rollup = AuditRollup()
    by_mode: Counter = Counter()
    by_surface: Counter = Counter()
    total_flags = 0
    events_with_flags = 0

    for line in reversed(blob.splitlines()):
        m = _AUDIT_RE.search(line)
        if not m:
            continue
        rollup.total += 1
        by_mode[m.group("mode")] += 1
        by_surface[m.group("surface")] += 1
        flagged_n = int(m.group("flagged"))
        total_flags += flagged_n
        if flagged_n > 0:
            events_with_flags += 1
        if rollup.total >= limit:
            break

    rollup.by_mode = dict(by_mode)
    rollup.by_surface = dict(by_surface)
    rollup.total_flags = total_flags
    rollup.flag_rate = (
        round(events_with_flags / rollup.total, 3) if rollup.total else 0.0
    )
    return rollup


def _parse_error_lines(blob: str, limit: int) -> ErrorRollup:
    rollup = ErrorRollup()
    by_class: Counter = Counter()
    by_surface: Counter = Counter()
    transient = structural = 0

    for line in reversed(blob.splitlines()):
        m = _ERROR_RE.search(line)
        if not m:
            continue
        rollup.total += 1
        by_class[m.group("cls")] += 1
        by_surface[m.group("surface")] += 1
        if m.group("transient") == "1":
            transient += 1
        if m.group("structural") == "1":
            structural += 1
        if rollup.total >= limit:
            break

    rollup.by_class = dict(by_class)
    rollup.by_surface = dict(by_surface)
    rollup.transient_count = transient
    rollup.structural_count = structural
    return rollup


def _parse_consolidation_lines(blob: str, limit: int) -> ConsolidationRollup:
    rollup = ConsolidationRollup()
    # Walk newest-first; keep last-observed values, count all observations.
    observations = 0
    latest_captured = False

    for line in reversed(blob.splitlines()):
        m = _CONSOL_RE.search(line)
        if not m:
            continue
        observations += 1
        if not latest_captured:
            rollup.last_n = int(m.group("n"))
            rollup.last_min = float(m.group("min"))
            rollup.last_median = float(m.group("median"))
            rollup.last_max = float(m.group("max"))
            latest_captured = True
        if observations >= limit:
            break

    rollup.observations = observations
    return rollup


# ── sidecar DB readers ────────────────────────────────────────────────

def _fabrication_snapshot(limit: int = 10) -> FabricationSnapshot:
    """Latest fabrication_events rows. Empty on any failure."""
    snap = FabricationSnapshot()
    if not _FAB_DB.exists():
        return snap
    try:
        db = sqlite3.connect(_FAB_DB, timeout=1.5)
        snap.total_events = db.execute(
            "SELECT COUNT(*) FROM fabrication_events"
        ).fetchone()[0]
        cur = db.execute(
            "SELECT ts, surface, text, reason, mode "
            "FROM fabrication_events ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        for ts, surface, text, reason, mode in cur.fetchall():
            snap.recent.append({
                "ts": float(ts),
                "surface": surface,
                "text": (text or "")[:300],
                "reason": (reason or "")[:300],
                "mode": mode,
            })
    except Exception as e:
        logger.debug("fabrication_snapshot failed: %s", e)
    finally:
        try:
            db.close()
        except Exception:
            pass
    return snap


def _recall_snapshot() -> RecallSnapshot:
    """Aggregate counts from recall_stats sidecar. Empty on any failure."""
    snap = RecallSnapshot()
    if not _RECALL_DB.exists():
        return snap
    try:
        db = sqlite3.connect(_RECALL_DB, timeout=1.5)
        row = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(recall_count), 0), "
            "COALESCE(SUM(consolidated), 0) FROM recall_stats"
        ).fetchone()
        if row:
            snap.total_memories_tracked = int(row[0])
            snap.total_recalls = int(row[1])
            snap.consolidated_count = int(row[2])
    except Exception as e:
        logger.debug("recall_snapshot failed: %s", e)
    finally:
        try:
            db.close()
        except Exception:
            pass
    return snap


# ── public entry point ────────────────────────────────────────────────

def build_rollup(
    *,
    audit_lookback: int = 200,
    error_lookback: int = 200,
    consolidation_lookback: int = 20,
    fabrication_limit: int = 10,
) -> QualityRollup:
    """Assemble the full quality-signal rollup. Reads the tail of
    cognition.log and the two sidecar DBs. Never raises — every source
    fails independently to an empty/zero rollup if unavailable.

    Args:
        audit_lookback: how many most-recent self_claim_audit lines to parse
        error_lookback: how many most-recent error_classifier lines to parse
        consolidation_lookback: how many most-recent consolidation_scores lines
            to parse. last_* fields reflect the single newest observation.
        fabrication_limit: how many fabrication_events rows to include in
            the `recent` sample.
    """
    blob = _read_tail(_COG_LOG)
    audit = _parse_audit_lines(blob, audit_lookback)
    errors = _parse_error_lines(blob, error_lookback)
    consol = _parse_consolidation_lines(blob, consolidation_lookback)
    fab = _fabrication_snapshot(limit=fabrication_limit)
    recall = _recall_snapshot()

    return QualityRollup(
        generated_at=time.time(),
        source_log_path=str(_COG_LOG),
        audit=audit,
        errors=errors,
        consolidation=consol,
        fabrication=fab,
        recall=recall,
    )
