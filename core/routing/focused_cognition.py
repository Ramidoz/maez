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
import re

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
_CITE_RE = re.compile(r"\[E(\d+)\]")
_FAITHFUL_INSTRUCTION = (
    "Answer the owner's question ONLY from the evidence below. Cite the [E#] "
    "labels you use, inline. If the evidence does not cover the question, say so "
    "plainly. Do not add claims unsupported by the evidence."
)
_VOICE_CARD_TEXT = (
    "Speak as Maez: dense, opinionated, useful. 3-5 sentences. Give your read "
    "and connect it to what the owner cares about (local AI, what's being built). "
    "Not a mechanical list."
)


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


@dataclass(frozen=True)
class FocusedResult:
    reply: str
    cited_ids: list[str]
    working_set_chars: int


@dataclass(frozen=True)
class GroundednessVerdict:
    verdict: str
    citation_coverage: float
    unmatched: list[str]


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


def _voice_card(surface: str) -> str:
    # Voice surfaces are excluded by the daemon gate in v1.
    return _VOICE_CARD_TEXT


def focused_synthesize(
    working_set: WorkingSet,
    *,
    surface: str,
    chat_fn=None,
    model=None,
) -> FocusedResult:
    if chat_fn is None:
        from core import llm_client as _llm_client

        chat_fn = _llm_client.chat
    if model is None:
        from core.model_config import PRIMARY_MODEL

        model = PRIMARY_MODEL

    system = (
        f"{_voice_card(surface)}\n\n"
        f"{_FAITHFUL_INSTRUCTION}\n\n"
        f"=== EVIDENCE (cite [E#]) ===\n"
        f"{working_set.ordered_evidence_text}"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": working_set.owner_question},
    ]
    response = chat_fn(
        model=model,
        messages=messages,
        think=False,
        options={"temperature": 0.7, "num_predict": 4096},
    )
    reply = (getattr(getattr(response, "message", None), "content", None) or "").strip()
    cited_ids = sorted({f"E{match.group(1)}" for match in _CITE_RE.finditer(reply)})
    return FocusedResult(
        reply=reply,
        cited_ids=cited_ids,
        working_set_chars=working_set.working_set_chars,
    )


def check_groundedness(
    result: FocusedResult,
    working_set: WorkingSet,
) -> GroundednessVerdict:
    valid_labels = {item.local_label for item in working_set.items}
    cited = set(result.cited_ids)
    unmatched = sorted(cited - valid_labels)
    matched = cited & valid_labels
    coverage = len(matched) / len(valid_labels) if valid_labels else 0.0

    if not cited:
        verdict = "no_citations"
    elif unmatched:
        verdict = "unmatched_citation"
    else:
        verdict = "grounded"

    return GroundednessVerdict(
        verdict=verdict,
        citation_coverage=coverage,
        unmatched=unmatched,
    )
