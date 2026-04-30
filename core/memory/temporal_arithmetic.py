# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Temporal arithmetic at recall time (Step 5c — first real
implementation produced by the capability acquisition pipeline).

When the question is temporal-shaped (e.g. "when did X?", "how long
after Y?", "what came before Z?"), the recall layer can attach a
short factual annotation to surfaced items: the absolute event date
plus a relative phrase like "about 18 days before question". Without
this layer, dated text fragments sit in the prompt as raw tokens and
the answering model has to do the math from string evidence.

Hard contract — what this module is NOT:

  • Not a ranking change. Annotation is layered on top of selection;
    nothing is added or removed from the brief because of dates.
  • Not a storage change. Episodes / graph / Chroma are untouched.
  • Not a wall-clock-only path. The reference time is explicit at
    every internal boundary; only the outer entry-point default can
    fall back to ``datetime.now(timezone.utc)``.
  • Not an always-on annotation. Only fires when
    ``is_temporal_question(question)`` returns True. Non-temporal
    questions surface untouched briefs.
  • Not silent on bad input. Missing or unparseable event timestamps
    leave the item unchanged — never fabricates a date.

Public API:

  is_temporal_question(text)                       -> bool
  relative_time_phrase(event, reference)           -> str
  annotate_recall_item(text, event, reference)     -> str
  annotate_recall_items(items, question, *,
                        reference_time=None)       -> list[dict]
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

# ── classifier ────────────────────────────────────────────────────


# Strong patterns — appearance alone is sufficient signal that the
# question is asking about time relations. These tolerate any
# surrounding context.
_STRONG_TEMPORAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bwhen did\b", re.IGNORECASE),
    re.compile(r"\bwhen was\b", re.IGNORECASE),
    re.compile(r"\bwhen were\b", re.IGNORECASE),
    re.compile(r"\bhow long after\b", re.IGNORECASE),
    re.compile(r"\bhow long before\b", re.IGNORECASE),
    re.compile(r"\bhow long ago\b", re.IGNORECASE),
    re.compile(r"\bhow long since\b", re.IGNORECASE),
    re.compile(r"\bhow recent\w*\b", re.IGNORECASE),
)

# Weak patterns — bare prepositions like "before", "after", "since"
# carry temporal meaning only in interrogative context. Without the
# question-shape gate, "after lunch I went home" misclassifies as
# temporal. Gate is: text contains a "?" OR starts with a question
# word (what/when/where/why/which/who/how).
_WEAK_TEMPORAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bbefore\b", re.IGNORECASE),
    re.compile(r"\bafter\b", re.IGNORECASE),
    re.compile(r"\bsince\b", re.IGNORECASE),
)

_QUESTION_WORD_RE = re.compile(
    r"^\s*(what|when|where|why|which|who|how|did|do|does|is|are|was|were|"
    r"could|would|should|can|will)\b",
    re.IGNORECASE,
)


def is_temporal_question(text: str) -> bool:
    """True iff ``text`` is shaped like a temporal question.

    Strong patterns ("when did", "how long ago", etc.) match anywhere.
    Weak patterns ("before", "after", "since") only count when the
    text is interrogative (contains '?' or starts with a question
    word) — without that gate, declarative sentences like "after
    lunch I went home" misclassify as temporal."""
    if not text or not isinstance(text, str):
        return False
    for pat in _STRONG_TEMPORAL_PATTERNS:
        if pat.search(text):
            return True
    looks_interrogative = (
        "?" in text or _QUESTION_WORD_RE.match(text) is not None
    )
    if not looks_interrogative:
        return False
    for pat in _WEAK_TEMPORAL_PATTERNS:
        if pat.search(text):
            return True
    return False


# ── relative phrasing ─────────────────────────────────────────────


def _ensure_aware(dt: datetime) -> datetime:
    """Naive datetimes are interpreted as UTC. The episode store
    persists ISO strings with explicit UTC offset, but callers may
    pass naive values from tests / fixture data."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def relative_time_phrase(
    event_time: datetime, reference_time: datetime,
) -> str:
    """Render a short factual phrase describing how far ``event_time``
    is from ``reference_time``. The phrase is the *only* relative
    time language this module produces; both ``annotate_recall_item``
    and ``annotate_recall_items`` route through this function so
    formatting is consistent.

    Rules of thumb:
      • <24h apart → "same day as question"
      • exactly 1 day → "1 day before question" / "...after question"
      • 2–13 days → "N days before/after question"
      • 14–59 days → "about N weeks before/after question"
      • 60–364 days → "about N months before/after question"
      • ≥365 days → "about N years before/after question"

    "before"/"after" is from the question's vantage: an event whose
    time is earlier than ``reference_time`` is *before* the question.
    """
    ev = _ensure_aware(event_time)
    ref = _ensure_aware(reference_time)
    delta = ev - ref
    total_seconds = delta.total_seconds()
    abs_days = abs(total_seconds) / 86400.0

    if abs_days < 1.0:
        return "same day as question"

    direction = "after question" if total_seconds > 0 else "before question"

    days = int(round(abs_days))
    if days == 1:
        return f"1 day {direction}"
    if days < 7:
        return f"{days} days {direction}"
    if days < 21:
        # Keep "days" precision in the 7–20 band; the spec's exemplar
        # phrasing — "about 18 days before question" — lives here.
        return f"about {days} days {direction}"
    if days < 60:
        weeks = int(round(days / 7.0))
        return f"about {weeks} weeks {direction}"
    if days < 365:
        months = int(round(days / 30.0))
        return f"about {months} months {direction}"
    years = int(round(days / 365.0))
    if years == 1:
        return f"about 1 year {direction}"
    return f"about {years} years {direction}"


# ── annotation ────────────────────────────────────────────────────


_ANNOTATION_TEMPLATE = "[time: {iso_date}, {phrase}]"


def annotate_recall_item(
    text: str, event_time: datetime, reference_time: datetime,
) -> str:
    """Append a temporal annotation to ``text``. The annotation
    surfaces the absolute date (YYYY-MM-DD) and a relative-time
    phrase; both routed through ``relative_time_phrase`` so all
    output is consistent.

    Returns the original ``text`` unchanged when ``event_time`` is
    falsy or not a datetime — this is the "honest about missing
    timestamp" branch of the contract."""
    if not isinstance(event_time, datetime):
        return text
    ev = _ensure_aware(event_time)
    ref = _ensure_aware(reference_time)
    annotation = _ANNOTATION_TEMPLATE.format(
        iso_date=ev.date().isoformat(),
        phrase=relative_time_phrase(ev, ref),
    )
    return f"{text} {annotation}"


# ── batch annotation over recall items ────────────────────────────


def _coerce_event_time(value: Any) -> datetime | None:
    """Best-effort conversion of an item's ``event_time`` field to a
    datetime. Returns None on missing / unparseable input — caller
    leaves the item unchanged on None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def annotate_recall_items(
    items: Iterable[dict],
    question: str,
    *,
    reference_time: datetime | None = None,
) -> list[dict]:
    """Annotate a sequence of recall items with relative-time
    phrases when ``question`` is temporal-shaped.

    Each item is a mapping with at least a ``text`` field. An
    ``event_time`` field (datetime or ISO string) drives the
    annotation; missing or unparseable values pass through
    unchanged. The input list is never mutated — callers receive
    a fresh list of fresh dicts.

    ``reference_time=None`` defaults to ``datetime.now(timezone.utc)``
    at this outer boundary only. Internal helpers always require an
    explicit reference so wall-clock can never leak into pure logic.
    """
    items_list = [dict(it) for it in items]
    if not is_temporal_question(question):
        return items_list

    ref = reference_time
    if ref is None:
        ref = datetime.now(timezone.utc)

    out: list[dict] = []
    for item in items_list:
        ev = _coerce_event_time(item.get("event_time"))
        if ev is None:
            out.append(item)
            continue
        annotated = dict(item)
        annotated["text"] = annotate_recall_item(
            str(item.get("text", "")), ev, ref,
        )
        out.append(annotated)
    return out


__all__ = [
    "annotate_recall_item",
    "annotate_recall_items",
    "is_temporal_question",
    "relative_time_phrase",
]
