# Copyright (C) 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Focused Cognition organ helpers.

When query evidence is present on a text surface, assemble a small bounded
working set so the brain can answer from evidence instead of the full daemon
megaprompt.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from core.routing.evidence_state import turn_evidence_state

_POSITIVE_MARKERS: tuple[str, ...] = (
    "[fresh evidence]",
    "[memory evidence]",
    "[memory context]",
)
_ALL_MARKERS: tuple[str, ...] = (
    "[memory evidence]",
    "[memory context]",
    "[fresh evidence]",
    "[no fresh evidence available:",
    "[dispatcher refusal:",
)
_SOURCE_TYPE: dict[str, str] = {
    "[fresh evidence]": "fresh_evidence",
    "[memory evidence]": "memory_evidence",
    "[memory context]": "memory_context",
}
_PRIORITY: dict[str, int] = {
    "fresh_evidence": 0,
    "memory_evidence": 1,
    "memory_context": 1,
    "web_context": 2,
}
_WEB_NO_RESULTS = "No results found."


@dataclass(frozen=True)
class EvidenceItem:
    local_label: str
    source_type: str
    text: str
    durable_id: str


@dataclass(frozen=True)
class WorkingSet:
    items: list[EvidenceItem]
    ordered_evidence_text: str
    owner_question: str
    working_set_chars: int
    working_set_tokens_est: int


def _content_hash(text: str) -> str:
    return "ch_" + hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def _split_blocks(transcript: str) -> list[tuple[str, str]]:
    """Return positive marker bodies bounded by the next known marker."""

    if not transcript:
        return []

    hits: list[tuple[int, str]] = []
    for marker in _ALL_MARKERS:
        start = 0
        while True:
            index = transcript.find(marker, start)
            if index < 0:
                break
            hits.append((index, marker))
            start = index + len(marker)

    hits.sort()
    blocks: list[tuple[str, str]] = []
    for i, (index, marker) in enumerate(hits):
        if marker not in _POSITIVE_MARKERS:
            continue
        body_start = index + len(marker)
        body_end = hits[i + 1][0] if i + 1 < len(hits) else len(transcript)
        body = transcript[body_start:body_end].strip()
        if body:
            blocks.append((marker, body))
    return blocks


def _atomic_items(body: str) -> list[str]:
    rows = [
        line.strip()[2:].strip()
        for line in body.splitlines()
        if line.strip().startswith("- ")
    ]
    if rows:
        return [row for row in rows if row]
    body = body.strip()
    return [body] if body else []


def assemble_working_set(
    *,
    transcript: str,
    web_context: str,
    owner_question: str,
) -> WorkingSet | None:
    state = turn_evidence_state(transcript=transcript, web_context=web_context)
    if not state.evidence_present:
        return None

    raw_items: list[tuple[str, str]] = []
    for marker, body in _split_blocks(transcript or ""):
        for item_text in _atomic_items(body):
            raw_items.append((_SOURCE_TYPE[marker], item_text))

    web_context = web_context or ""
    if web_context.strip() and _WEB_NO_RESULTS not in web_context:
        for item_text in _atomic_items(web_context):
            raw_items.append(("web_context", item_text))

    if not raw_items:
        return None

    raw_items.sort(key=lambda item: _PRIORITY.get(item[0], 9))
    items = [
        EvidenceItem(
            local_label=f"E{index + 1}",
            source_type=source_type,
            text=text,
            durable_id=_content_hash(text),
        )
        for index, (source_type, text) in enumerate(raw_items)
    ]

    lines = [f"[{item.local_label}] ({item.source_type}) {item.text}" for item in items]
    top = items[0]
    lines.append(f"(most important, repeated) [{top.local_label}] {top.text}")
    ordered = "\n".join(lines)

    total_chars = len(ordered) + len(owner_question or "")
    return WorkingSet(
        items=items,
        ordered_evidence_text=ordered,
        owner_question=owner_question,
        working_set_chars=total_chars,
        working_set_tokens_est=total_chars // 4,
    )
