# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Bounded temporal-anchor recall for natural memory questions.

TRF v1 handles a narrow set of relative anchors ("last week",
"yesterday", "this morning", "earlier today") by searching only the
corresponding local calendar window in the lived episode store. It is a
supplement to lived recall, not a replacement and not the full temporal spine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
import re
import time as _time
from typing import Literal

from core.time.temporal_spine import (
    canonical_utc,
    canonical_utc_iso,
    owner_timezone,
    record_helper_unavailable,
    temporal_window,
)

_KILL_SWITCH = "MAEZ_TEMPORAL_ANCHOR_RECALL"
_DEFAULT_TIMEOUT_MS = 150
_PRODUCER_VERSION = "temporal_anchor_recall.v1"
_MAX_EPISODE_TEXT_CHARS = 220
_MAX_BRIEF_CHARS = 1200

SearchStatus = Literal[
    "evidence_found",
    "bounded_search_no_match",
    "helper_unavailable",
]


@dataclass(frozen=True)
class TemporalAnchorRecallResult:
    anchor_detected: bool
    anchor_kind: str | None
    window_start: datetime | None
    window_end: datetime | None
    window_searched: bool
    search_status: SearchStatus
    evidence_ids: tuple[str, ...]
    item_count: int
    truncated: bool
    brief_text: str
    elapsed_ms: int
    memory_absence_established: Literal[False] = False


_ANCHOR_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("earlier_today", re.compile(r"\bearlier\s+today\b", re.IGNORECASE)),
    ("this_morning", re.compile(r"\bthis\s+morning\b", re.IGNORECASE)),
    ("yesterday", re.compile(r"\byesterday\b", re.IGNORECASE)),
    ("last_week", re.compile(r"\blast\s+week\b", re.IGNORECASE)),
)

# The "what were we ..." stems mirror the continuity classifier vocabulary
# (core/routing/focused_cognition.py) — copied here, NOT imported, to avoid a
# core.memory -> core.routing dependency. Anchor + negative/self-memory guards
# still gate every match, so a statement ("I was working on X yesterday") never
# becomes a recall ask. Keep aligned via the shared test corpus, not an import.
_MEMORY_INTENT_RE = re.compile(
    r"\b(remember|recall|what\s+happened|what\s+did|what\s+do\s+you\s+remember"
    r"|what\s+were\s+we\s+(working\s+on|talking\s+about|discussing|doing))\b",
    re.IGNORECASE,
)

_NEGATIVE_INTENT_RE = re.compile(
    r"\b(not\s+asking\s+you\s+to\s+remember|not\s+a\s+memory\s+request|not\s+asking\s+about)\b",
    re.IGNORECASE,
)

_USER_SELF_MEMORY_RE = re.compile(r"\bi\s+(remember|recall)\b", re.IGNORECASE)

_DIRECT_MAEZ_RECALL_RE = re.compile(
    r"\b((do|did|can|could|would)\s+you\s+(remember|recall)|you\s+(remember|recall))\b",
    re.IGNORECASE,
)


def _now_local() -> datetime:
    return datetime.now(owner_timezone())


def _as_local(dt: datetime | None) -> datetime:
    zone = owner_timezone()
    if dt is None:
        return _now_local()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=zone)
    return dt.astimezone(zone)


def detect_temporal_anchor(
    query: str,
    *,
    reference_time: datetime | None = None,
) -> TemporalAnchorRecallResult:
    """Detect a v1 temporal anchor and return the searched window contract."""
    started = _time.monotonic()
    text = query or ""
    if _NEGATIVE_INTENT_RE.search(text):
        return _empty_result(elapsed_ms=_elapsed_ms(started))
    if _USER_SELF_MEMORY_RE.search(text) and _DIRECT_MAEZ_RECALL_RE.search(text) is None:
        return _empty_result(elapsed_ms=_elapsed_ms(started))
    matched_kind = None
    for kind, pattern in _ANCHOR_PATTERNS:
        if pattern.search(text):
            matched_kind = kind
            break
    if matched_kind is None or _MEMORY_INTENT_RE.search(text) is None:
        return _empty_result(elapsed_ms=_elapsed_ms(started))
    try:
        window = temporal_window(matched_kind, _as_local(reference_time))
    except Exception:
        record_helper_unavailable("temporal_helper_exception")
        return _helper_unavailable_result(
            anchor_kind=matched_kind,
            elapsed_ms=_elapsed_ms(started),
        )
    return TemporalAnchorRecallResult(
        anchor_detected=True,
        anchor_kind=matched_kind,
        window_start=window.start,
        window_end=window.end,
        window_searched=False,
        search_status="bounded_search_no_match",
        evidence_ids=(),
        item_count=0,
        truncated=False,
        brief_text="",
        elapsed_ms=_elapsed_ms(started),
        memory_absence_established=False,
    )


def _helper_unavailable_result(*, anchor_kind: str, elapsed_ms: int) -> TemporalAnchorRecallResult:
    return TemporalAnchorRecallResult(
        anchor_detected=True,
        anchor_kind=anchor_kind,
        window_start=None,
        window_end=None,
        window_searched=False,
        search_status="helper_unavailable",
        evidence_ids=(),
        item_count=0,
        truncated=False,
        brief_text="",
        elapsed_ms=elapsed_ms,
        memory_absence_established=False,
    )


def _empty_result(
    *, elapsed_ms: int, status: SearchStatus = "bounded_search_no_match"
) -> TemporalAnchorRecallResult:
    return TemporalAnchorRecallResult(
        anchor_detected=False,
        anchor_kind=None,
        window_start=None,
        window_end=None,
        window_searched=False,
        search_status=status,
        evidence_ids=(),
        item_count=0,
        truncated=False,
        brief_text="",
        elapsed_ms=elapsed_ms,
        memory_absence_established=False,
    )


def _elapsed_ms(started: float) -> int:
    return int((_time.monotonic() - started) * 1000)


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _as_local(value)
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = canonical_utc(raw, field_name="event_at")
    except ValueError:
        return None
    return _as_local(parsed)


def _evidence_ids_for_episode(ep: dict) -> tuple[str, ...]:
    ids: list[str] = []
    ep_id = ep.get("id")
    if ep_id:
        ids.append(str(ep_id))
    for source_id in ep.get("source_memory_ids") or ():
        if source_id:
            ids.append(str(source_id))
    return tuple(ids)


def _deduped_evidence_ids(episodes: list[dict]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for ep in episodes:
        for evidence_id in _evidence_ids_for_episode(ep):
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            ordered.append(evidence_id)
    return tuple(ordered)


def _cap_text(text: str, limit: int = _MAX_EPISODE_TEXT_CHARS) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 16)].rstrip() + " ... [truncated]"


def _brief_for(anchor_kind: str, episodes: list[dict], *, truncated: bool) -> str:
    anchor_label = anchor_kind.replace("_", " ")
    lines = [f"=== TEMPORAL ANCHOR RECALL ({anchor_label}) ==="]
    for ep in episodes:
        when = _parse_dt(ep.get("occurred_at") or ep.get("created_at"))
        date_label = when.date().isoformat() if when is not None else "date unknown"
        evidence = ", ".join(_evidence_ids_for_episode(ep))
        summary = str(ep.get("summary") or "").strip()
        title = str(ep.get("title") or "").strip()
        if ep.get("source_kind") == "telegram_exchange" and summary:
            text = _cap_text(summary)
        else:
            text = _cap_text(title if title else summary)
        lines.append(f"- Past episode [{date_label}] {text} [evidence: {evidence}]")
    if truncated:
        lines.append(f"(truncated to {len(episodes)} matching episodes)")
    brief = "\n".join(lines)
    if len(brief) <= _MAX_BRIEF_CHARS:
        return brief
    return brief[: max(0, _MAX_BRIEF_CHARS - 36)].rstrip() + "\n(temporal recall brief truncated)"


def _no_match_note(anchor_kind: str) -> str:
    anchor_label = anchor_kind.replace("_", "-")
    return (
        "TEMPORAL ANCHOR RECALL: searched bounded "
        f"{anchor_label} temporal anchor; no matching grounded episodes found in that search."
    )


def _rank_key(ep: dict, reference_time: datetime) -> tuple[float, int, str]:
    event_time = _parse_dt(ep.get("occurred_at") or ep.get("created_at"))
    distance = (
        abs((_as_local(reference_time) - event_time).total_seconds())
        if event_time
        else float("inf")
    )
    score = int(ep.get("importance") or 0)
    return (distance, -score, str(ep.get("id") or ""))


def _rows_in_window(
    *,
    episode_store,
    window_start: datetime,
    window_end: datetime,
    max_items: int,
    timeout_ms: int,
) -> list[dict]:
    windowed = getattr(episode_store, "list_active_in_window", None)
    if callable(windowed):
        return list(
            windowed(
                window_start=canonical_utc_iso(window_start, field_name="event_at"),
                window_end=canonical_utc_iso(window_end, field_name="event_at"),
                limit=max_items + 1,
                busy_timeout_ms=timeout_ms,
            )
            or []
        )
    raise RuntimeError("windowed episode query unavailable")


def build_temporal_anchor_recall_brief(
    query: str,
    *,
    episode_store,
    reference_time: datetime | None = None,
    max_items: int = 4,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> TemporalAnchorRecallResult:
    """Return a bounded temporal-anchor recall result.

    Fail-neutral: disabled, timeout, or store errors return helper_unavailable
    without claiming absence and without raising into the daemon path.
    """
    started = _time.monotonic()
    detected = detect_temporal_anchor(query, reference_time=reference_time)
    if not detected.anchor_detected:
        return detected
    if detected.window_start is None or detected.window_end is None or detected.anchor_kind is None:
        return TemporalAnchorRecallResult(
            anchor_detected=detected.anchor_detected,
            anchor_kind=detected.anchor_kind,
            window_start=None,
            window_end=None,
            window_searched=False,
            search_status="helper_unavailable",
            evidence_ids=(),
            item_count=0,
            truncated=False,
            brief_text="",
            elapsed_ms=_elapsed_ms(started),
            memory_absence_established=False,
        )
    if os.environ.get(_KILL_SWITCH, "1").strip() == "0":
        return TemporalAnchorRecallResult(
            anchor_detected=True,
            anchor_kind=detected.anchor_kind,
            window_start=detected.window_start,
            window_end=detected.window_end,
            window_searched=False,
            search_status="helper_unavailable",
            evidence_ids=(),
            item_count=0,
            truncated=False,
            brief_text="",
            elapsed_ms=_elapsed_ms(started),
            memory_absence_established=False,
        )

    try:
        rows = _rows_in_window(
            episode_store=episode_store,
            window_start=detected.window_start,
            window_end=detected.window_end,
            max_items=max_items,
            timeout_ms=timeout_ms,
        )
    except Exception:
        return TemporalAnchorRecallResult(
            anchor_detected=True,
            anchor_kind=detected.anchor_kind,
            window_start=detected.window_start,
            window_end=detected.window_end,
            window_searched=False,
            search_status="helper_unavailable",
            evidence_ids=(),
            item_count=0,
            truncated=False,
            brief_text="",
            elapsed_ms=_elapsed_ms(started),
            memory_absence_established=False,
        )
    if _elapsed_ms(started) > timeout_ms:
        return TemporalAnchorRecallResult(
            anchor_detected=True,
            anchor_kind=detected.anchor_kind,
            window_start=detected.window_start,
            window_end=detected.window_end,
            window_searched=False,
            search_status="helper_unavailable",
            evidence_ids=(),
            item_count=0,
            truncated=False,
            brief_text="",
            elapsed_ms=_elapsed_ms(started),
            memory_absence_established=False,
        )

    rows.sort(key=lambda ep: _rank_key(ep, _as_local(reference_time)))
    selected = rows[:max_items]
    truncated = len(rows) > len(selected)
    evidence_ids = _deduped_evidence_ids(selected)
    if not selected:
        return TemporalAnchorRecallResult(
            anchor_detected=True,
            anchor_kind=detected.anchor_kind,
            window_start=detected.window_start,
            window_end=detected.window_end,
            window_searched=True,
            search_status="bounded_search_no_match",
            evidence_ids=(),
            item_count=0,
            truncated=False,
            brief_text=_no_match_note(detected.anchor_kind),
            elapsed_ms=_elapsed_ms(started),
            memory_absence_established=False,
        )
    return TemporalAnchorRecallResult(
        anchor_detected=True,
        anchor_kind=detected.anchor_kind,
        window_start=detected.window_start,
        window_end=detected.window_end,
        window_searched=True,
        search_status="evidence_found",
        evidence_ids=evidence_ids,
        item_count=len(selected),
        truncated=truncated,
        brief_text=_brief_for(detected.anchor_kind, selected, truncated=truncated),
        elapsed_ms=_elapsed_ms(started),
        memory_absence_established=False,
    )


__all__ = [
    "TemporalAnchorRecallResult",
    "build_temporal_anchor_recall_brief",
    "detect_temporal_anchor",
]
