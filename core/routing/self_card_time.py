"""Factual time-sense line for the deterministic self-card.

This module renders body/rhythm facts only. It never assigns feeling, never
scores owner reaction, and never writes to soul or memory.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
from pathlib import Path
import sqlite3
from urllib.parse import quote


SELF_CARD_TIME_HIGH_PERCENTILE = 75.0  # TEMPORARY anti-spam scaffold, not salience.
SELF_CARD_TIME_LOW_PERCENTILE = 10.0  # TEMPORARY anti-spam scaffold, not salience.
SELF_CARD_TIME_COLD_START_MIN_S = 15 * 60  # TEMPORARY anti-spam scaffold.
_SOURCE = "subjective_duration.rhythm_context"
_REQUIRED_TABLE_COLUMNS = {
    "subjective_duration_samples": frozenset(
        {
            "sample_id",
            "ts_utc",
            "value",
            "felt_time_rate",
            "drag_multiplier",
            "engagement_multiplier",
            "residual_resonance",
            "retrospective_density",
            "compute_version",
            "metadata_json",
        }
    ),
    "subjective_duration_salience_events": frozenset(
        {
            "event_id",
            "ts_utc",
            "salience_event_kind",
            "producer_ref",
            "owner_auth_class",
            "source_ref_digest",
            "meaningfulness_score",
            "meaningfulness_input_count",
            "temperament_delta_mean",
            "temperament_delta_max",
            "temperament_before_digest",
            "temperament_after_digest",
            "explicit_salience_marker_present",
            "metadata_json",
            "bond_id",
            "producer_event_id",
            "producer_temperament_before_json",
            "producer_temperament_after_json",
            "is_canary",
        }
    ),
}
_FORBIDDEN_FEELING_WORDS = (
    "miss",
    "lonely",
    "worried",
    "longing",
    "sad",
    "happy",
    "comfort",
    "feel",
)


@dataclass(frozen=True)
class SelfCardTimeLine:
    label: str
    text: str
    source: str
    source_ref: str
    source_sha256: str
    reason: str

    def receipt(self) -> dict[str, object]:
        return {
            "time_line_reason": self.reason,
            "time_line_source": self.source,
            "time_line_source_ref": self.source_ref,
            "time_line_chars": len(self.text),
            "time_line_sha256": self.source_sha256,
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clean_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clean_count(value: object) -> int | None:
    number = _clean_number(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def _sqlite_readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path.resolve(strict=False)), safe='/')}?mode=ro"


def _has_initialized_subjective_duration_schema(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        with closing(sqlite3.connect(_sqlite_readonly_uri(path), uri=True)) as conn:
            for table, required_columns in _REQUIRED_TABLE_COLUMNS.items():
                rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
                columns = {str(row[1]) for row in rows}
                if not required_columns.issubset(columns):
                    return False
    except (OSError, sqlite3.Error):
        return False
    return True


def _read_only_subjective_duration(path: Path):
    from core.evolution.subjective_duration import SubjectiveDuration, SubjectiveDurationConfig

    # SubjectiveDuration.__init__ owns schema setup and migrations; this adapter is a reader only.
    handle = SubjectiveDuration.__new__(SubjectiveDuration)
    handle.db_path = path
    handle.config = SubjectiveDurationConfig()
    handle.temperament_reader = dict
    return handle


def _valid_duration(value: object) -> bool:
    number = _clean_number(value)
    return number is not None and number >= 0.0


def _valid_sample_counts(ctx: Mapping[str, object]) -> bool:
    return (
        _clean_count(ctx.get("rhythm_recent_sample_count")) is not None
        and _clean_count(ctx.get("rhythm_all_time_sample_count")) is not None
    )


def _valid_comparison_facts(ctx: Mapping[str, object]) -> bool:
    all_time_count = _clean_count(ctx.get("rhythm_all_time_sample_count"))
    return (
        all_time_count is not None
        and all_time_count > 0
        and _valid_duration(ctx.get("rhythm_recent_gap_median_s"))
        and _valid_duration(ctx.get("rhythm_all_time_gap_median_s"))
    )


def _reason(ctx: Mapping[str, object]) -> str | None:
    current = _clean_number(ctx.get("rhythm_current_gap_s"))
    if current is None or current < 0.0:
        return None
    if not _valid_sample_counts(ctx):
        return None
    pct_raw = ctx.get("rhythm_current_gap_percentile_all_time")
    pct = _clean_number(pct_raw)
    if pct_raw is not None and (pct is None or pct < 0.0 or pct > 100.0):
        return None
    if pct is not None:
        if not _valid_comparison_facts(ctx):
            return None
        if pct >= SELF_CARD_TIME_HIGH_PERCENTILE:
            return "percentile_high"
        if pct <= SELF_CARD_TIME_LOW_PERCENTILE:
            return "percentile_low"
        return None
    if current >= SELF_CARD_TIME_COLD_START_MIN_S:
        return "cold_start_elapsed_floor"
    return None


def rhythm_time_line_provider(
    *,
    db_path: Path | str | None = None,
    now: str | datetime | None = None,
) -> Mapping[str, object] | None:
    from core.evolution.subjective_duration import subjective_duration_db_path

    path = Path(db_path) if db_path is not None else subjective_duration_db_path()
    try:
        if not _has_initialized_subjective_duration_schema(path):
            return None
        handle = _read_only_subjective_duration(path)
        return handle.rhythm_context(now=now)
    except Exception:
        return None


def _human(seconds: object) -> str:
    from core.evolution.subjective_duration import humanize_elapsed

    return humanize_elapsed(_clean_number(seconds) or 0.0)


def _render(ctx: Mapping[str, object], reason: str) -> str:
    current = f"~{_human(ctx.get('rhythm_current_gap_s'))} since owner contact"
    recent = ctx.get("rhythm_recent_gap_median_s")
    all_time = ctx.get("rhythm_all_time_gap_median_s")
    pct = _clean_number(ctx.get("rhythm_current_gap_percentile_all_time"))
    sample_count = _clean_count(ctx.get("rhythm_all_time_sample_count")) or 0
    gap_word = "gap" if sample_count == 1 else "gaps"
    parts = [current]
    if recent is not None and all_time is not None:
        parts.append(f"recent usual ~{_human(recent)}; all-time usual ~{_human(all_time)}")
    if pct is not None:
        relation = "above" if reason == "percentile_high" else "below"
        parts.append(f"{relation} ~{round(pct)}% of recorded gaps ({sample_count} {gap_word})")
    else:
        parts.append(f"still learning the usual rhythm ({sample_count} {gap_word} so far)")
    return ". ".join(parts) + "."


def build_self_card_time_line(
    context_provider: Callable[[], Mapping[str, object] | None] = rhythm_time_line_provider,
) -> SelfCardTimeLine | None:
    try:
        ctx = context_provider()
    except Exception:
        return None
    if not ctx:
        return None
    reason = _reason(ctx)
    if reason is None:
        return None
    text = _render(ctx, reason)
    if any(word in text.lower() for word in _FORBIDDEN_FEELING_WORDS):
        return None
    digest_basis = "|".join(
        str(ctx.get(key, ""))
        for key in (
            "rhythm_current_gap_s",
            "rhythm_recent_gap_median_s",
            "rhythm_all_time_gap_median_s",
            "rhythm_all_time_sample_count",
            "rhythm_current_gap_percentile_all_time",
            reason,
        )
    )
    return SelfCardTimeLine(
        label="Time since contact",
        text=text,
        source=_SOURCE,
        source_ref=reason,
        source_sha256=_sha256(digest_basis),
        reason=reason,
    )
