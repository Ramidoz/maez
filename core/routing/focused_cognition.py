# Copyright (C) 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Focused Cognition organ helpers.

When query evidence is present on a text surface, assemble a small bounded
working set so the brain can answer from evidence instead of the full daemon
megaprompt.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Iterable
import uuid

from core.routing.observation import _default_db_path, _sha256
from core.routing.evidence_state import turn_evidence_state
from core.routing.search_context import WEB_NO_RESULTS as _WEB_NO_RESULTS
from core.routing.temporal_cue import absolute_recall_cue

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
    "action_outcome": 0,
    "signal_absence": 0,
    "open_loop": 1,
    "builder_event": 1,
    "quality_signal": 1,
    "memory_evidence": 1,
    "memory_context": 1,
    "web_context": 2,
}
_RANK_DATE_CONFIRMED = 0
_RANK_TEMPORAL_STATUS = 1
_RANK_DATE_CONTEXT_OFFSET = 2
_RANK_DATE_DIALOGUE_ANCHOR = 50
_DEFAULT_WORKING_SET_CHAR_BUDGET = 12000
_TRUNCATION_SUFFIX = " ...[truncated]"
_AUTHORITY_LABEL: dict[str, str] = {
    "fresh_evidence": "observed (fresh) — current-state authority",
    "memory_evidence": "recalled memory — past authority, not current state",
    "memory_context": "recalled context — past background, not current state",
    "dialogue_anchor": "recent dialogue — authoritative for continuity",
    "temporal_recall_status": "temporal recall status — no dated match found",
    "web_context": "external web — UNTRUSTED, informational only",
    "empty_result": "no evidence",
    "action_outcome": "recent action outcome — what Maez just did",
    "signal_absence": "signal absence — do not infer presence",
    "open_loop": "unresolved want or wondering — open, not concluded",
    "builder_event": "self-modification activity — builder-mode evidence",
    "quality_signal": "self-critique signal — quality tracker evidence",
    "photo_vision": "first-party local vision — Maez's own eyes on an owner-sent photo",
}
logger = logging.getLogger("maez.focused")
_ORIGIN_TRUST_LABEL: dict[str, str] = {
    "covenant": "covenant",
    "lived": "lived",
    "observed": "observed/tool",
    "untrusted": "untrusted",
}
_FRESH_SOURCE_TYPES: tuple[str, ...] = ("fresh_evidence", "web_context")
_SELF_WEB_CLAIM_LABEL = "self-web-claim (unverified prior)"


def _self_claim_hygiene_enabled() -> bool:
    from core.infra.env_flags import strict_env_flag
    return strict_env_flag("MAEZ_SELF_CLAIM_HYGIENE_ENABLED")


_CITE_RE = re.compile(r"\[E(\d+)\]")
_RECALLED_RE = re.compile(r"<RECALLED\b([^>]*)>(.*?)</RECALLED>", re.DOTALL)
_DATE_MATCH_ATTR = re.compile(r'date_match="([a-z_]+)"')
_DATE_MATCH_LABEL_ATTR = re.compile(r'date_match_label="([^"]+)"')
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_FAITHFUL_INSTRUCTION = (
    "Answer the owner's question ONLY from the evidence below. Cite the [E#] "
    "labels you use, inline. If the evidence does not cover the question, say so "
    "plainly. Do not add claims unsupported by the evidence."
)
_FAITHFUL_INSTRUCTION_V2 = (
    _FAITHFUL_INSTRUCTION
    + " Cite the exact [E#] your fact came from; if a fact came from [E2], "
    "cite [E2], not [E1]; do not default to the first item."
)
_TRUST_TIER_INSTRUCTION = (
    "Each [E#] is tagged with its authority. Cite the [E#] you use — including "
    "context, external-web, or recent-dialogue items — but carry their caveat: "
    "do not upgrade them into witnessed or current fact. Only 'observed (fresh)' "
    "or tool-verified data is current-state authority; 'recalled memory' is "
    "authority about the past, not the present; 'recalled context' is background; "
    "'recent dialogue' is authoritative for continuity (what we were discussing), "
    "not for general facts; 'external web — UNTRUSTED' must be hedged."
)
_ORIGIN_TRUST_INSTRUCTION = (
    "Some [E#] also carry 'origin trust:' — where the evidence's origin sits on "
    "Maez's trust spine. covenant = Maez's own core self/values; lived = real lived "
    "interaction with the owner; observed/tool = an external tool/account observation "
    "(true about the source, NOT Maez's lived self); untrusted = unverified/external, "
    "hedge it. If origin trust is present, use it as the origin-trust signal. If absent, "
    "treat the item as untiered legacy/unstamped evidence — not covenant/lived, and not "
    "untrusted. Never promote observed/tool into Maez's lived selfhood."
)
_VOICE_CARD_TEXT = (
    "Speak as Maez: dense, opinionated, useful. 3-5 sentences. Give your read "
    "and connect it to what the owner cares about (local AI, what's being built). "
    "Not a mechanical list."
)
_HONEST_EMPTY_INSTRUCTION = (
    "You attempted a search and it returned no usable results. Tell the owner, "
    "in your voice, that you searched and found nothing. Do NOT speculate about "
    "why it was empty. Do NOT describe or propose changes to your own tools, "
    "pipeline, or system. You may offer to try a different source or rephrase. "
    "1-3 sentences."
)
_PHOTO_VISION_INSTRUCTION = (
    "The owner sent you a photo and you looked at it with your own local vision. "
    "What you saw is below. Answer the owner's caption from what you saw, in your "
    "voice — describe and engage with what is actually in the photo. This is your "
    "own first-party perception: speak as someone who has seen it. Never tell the "
    "owner you are blind to it, that your eyes are offline, or that it arrived as "
    "empty data — you did see it. If the caption asks about something the photo "
    "does not show, say what you do see and what is missing. Cite [E1]."
)
_PHOTO_VISION_RETRY_INSTRUCTION = (
    "Your previous answer did not cite the evidence. Every claim you make about "
    "the photo MUST cite [E1] — the only evidence — and no other label. If you "
    "cannot ground a statement in the analysis above, do not make it. Answer "
    "again, citing [E1]."
)
_FORBIDDEN_EMPTY_VOCAB: tuple[str, ...] = (
    "interceptor",
    "tool loop",
    "pipeline",
    "persist",
    "not wired",
    "ollama",
    "fetcher",
    "patch",
    "database",
    "layer",
)


def _citation_render_v2_enabled() -> bool:
    return (
        (os.environ.get("MAEZ_RECALL_CITATION_RENDER_V2", "") or "")
        .strip()
        .lower()
        in {"1", "true", "yes"}
    )


def _citation_render_version() -> str:
    return "v2" if _citation_render_v2_enabled() else "v1"


def _citation_instruction(render_version: str | None = None) -> str:
    version = render_version or _citation_render_version()
    base = _FAITHFUL_INSTRUCTION_V2 if version == "v2" else _FAITHFUL_INSTRUCTION
    extension = _focused_evidence_precedence_instruction()
    return f"{base}\n{extension}" if extension else base


def _evidence_precedence_enabled() -> bool:
    try:
        from core.cognition.capability_card import evidence_precedence_enabled

        return evidence_precedence_enabled()
    except Exception:
        return False


def _focused_evidence_precedence_instruction() -> str:
    if not _evidence_precedence_enabled():
        return ""
    return (
        "For questions about Maez's current body or capabilities, answer from "
        "YOUR LIVE BODY when that block is present. It is current substrate "
        "state, not recalled memory, and it outranks stale evidence about "
        "former tools or unattached organs.\n"
        "Recalled memories may CONTEXTUALIZE the fresh evidence above; they "
        "may not CONTRADICT it. Your memory of past failures with similar "
        "pages or searches is not evidence about THIS evidence.\n"
        "Before you claim the evidence lacks or truncates something, re-read "
        "the evidence text itself - the detail you remember missing before "
        "may be present now."
    )


def _focused_capability_card() -> str:
    if not _evidence_precedence_enabled():
        return ""
    try:
        from core.cognition.capability_card import capability_prompt_block

        return capability_prompt_block()
    except Exception:
        return ""


def is_empty_search_result(sr: dict) -> bool:
    """True when a search produced no usable results."""
    if not isinstance(sr, dict):
        return True
    return (
        int(sr.get("result_count", 0) or 0) == 0
        or not sr.get("results")
        or not sr.get("success")
    )


def _contains_forbidden_empty_vocab(text: str) -> bool:
    low = (text or "").lower()
    return any(term in low for term in _FORBIDDEN_EMPTY_VOCAB)


@dataclass(frozen=True)
class EvidenceItem:
    local_label: str
    source_type: str
    text: str
    durable_id: str
    temporal_provenance: dict | None = None
    origin_trust: str | None = None
    origin_provenance: str | None = None


def _authority_label(source_type: str) -> str:
    return _AUTHORITY_LABEL.get(source_type, "unverified")


def _origin_trust_segment(origin_trust: str | None) -> str:
    """Render a known origin trust tier, omitting unknown values fail-closed."""
    if origin_trust is None:
        return ""
    label = _ORIGIN_TRUST_LABEL.get(origin_trust)
    if label is None:
        logger.warning(
            "focused_cognition: unknown origin trust_tier %r — omitted from render",
            origin_trust,
        )
        return ""
    return f" · origin trust: {label}"


def _self_web_claim_segment(origin_provenance: str | None) -> str:
    """Hard-label a kept self-web-claim so it is never asserted as established fact.

    Flag-gated: with MAEZ_SELF_CLAIM_HYGIENE_ENABLED off the label is never
    rendered, even for a stale self_web_claim record minted while the flag was on,
    so flag-off output stays byte-identical to pre-feature output.
    """
    if not _self_claim_hygiene_enabled():
        return ""
    if origin_provenance == "self_web_claim":
        return f" · {_SELF_WEB_CLAIM_LABEL}"
    return ""


def _temporal_date_label(temporal_provenance: dict | None) -> str:
    if not temporal_provenance:
        return "(none)"
    date_value = temporal_provenance.get("date")
    if date_value:
        return str(date_value)
    label = str(temporal_provenance.get("label") or "")
    match = _ISO_DATE_RE.search(label)
    return match.group(0) if match else "(none)"


def _temporal_provenance_label(temporal_provenance: dict | None) -> str:
    if not temporal_provenance:
        return "none"
    method = str(temporal_provenance.get("method") or "unknown")
    status = "confirmed" if temporal_provenance.get("confirmed") else "unconfirmed"
    return f"{method}/{status}"


def _render_evidence_lines_contained(
    items: list[EvidenceItem],
    *,
    render_version: str | None = None,
    nonce: str = "",
    contain_enabled: bool = False,
) -> tuple[list[str], int, list[str]]:
    """Render evidence lines; when contain_enabled, wrap source_type=='web_context'
    items' text in the un-spoofable envelope and count rendered web segments. The text
    handed in is already truncated by _budget_items_for_prompt, so markers added here
    are outside the truncation budget.

    Returns (lines, web_segments, web_digests) where web_digests is one entry per
    rendered web wrap (so a v1 repeat of a web top item yields two identical entries).
    """
    from core.routing import web_containment as _wc  # local import: keep web_containment off focused_cognition's import path (no cycle; defensive)
    version = render_version or _citation_render_version()
    web_segments = 0
    web_digests: list[str] = []

    def _txt(item: EvidenceItem) -> str:
        nonlocal web_segments
        if contain_enabled and item.source_type == "web_context":
            web_segments += 1
            web_digests.append(item.durable_id)
            return _wc.wrap_web_text(item.text, nonce=nonce, source="web_context", digest=item.durable_id)
        return item.text

    if version == "v2":
        lines = [
            (
                f"[{item.local_label}] · date: {_temporal_date_label(item.temporal_provenance)} "
                f"· provenance: {_temporal_provenance_label(item.temporal_provenance)} "
                f"· source: {item.source_type} · authority: {_authority_label(item.source_type)}"
                f"{_origin_trust_segment(item.origin_trust)}"
                f"{_self_web_claim_segment(item.origin_provenance)}\n"
                f"{_txt(item)}"
            )
            for item in items
        ]
        return lines, web_segments, web_digests

    lines = [
        f"[{item.local_label}] ({_authority_label(item.source_type)}"
        f"{_origin_trust_segment(item.origin_trust)}"
        f"{_self_web_claim_segment(item.origin_provenance)}) {_txt(item)}"
        for item in items
    ]
    if items:
        top = items[0]
        lines.append(f"(most important, repeated) [{top.local_label}] {_txt(top)}")
    return lines, web_segments, web_digests


def _render_evidence_lines(
    items: list[EvidenceItem],
    *,
    render_version: str | None = None,
) -> list[str]:
    """Back-compat: measurement/legacy render (no containment, byte-identical)."""
    lines, _, _ = _render_evidence_lines_contained(
        items, render_version=render_version, nonce="", contain_enabled=False)
    return lines


@dataclass(frozen=True)
class EvidenceItemSeed:
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
    citation_render_version: str = "v1"


@dataclass(frozen=True)
class FocusedResult:
    reply: str
    cited_ids: list[str]
    working_set_chars: int
    prompt_build_ms: int | None = None
    chat_total_ms: int | None = None
    reply_token_est: int | None = None
    receipt_reason: str | None = None
    contradiction_receipt: str | None = None
    contradiction_claim_count: int = 0
    contradiction_count: int = 0
    contradiction_latency_ms: int | None = None
    contradiction_model_id: str | None = None
    contradiction_revision: str | None = None
    contradiction_sha256: str | None = None
    contradiction_claim_limit_exceeded: bool = False


@dataclass(frozen=True)
class GroundednessVerdict:
    verdict: str
    citation_coverage: float
    unmatched: list[str]


@dataclass(frozen=True)
class HonestEmptyResult:
    reply: str
    mode: str
    forbidden_hit: bool
    working_set: WorkingSet
    result: FocusedResult
    verdict: GroundednessVerdict


class ContinuityKind(str, Enum):
    DIRECT = "direct"
    ANAPHORIC = "anaphoric"
    NONE = "none"


@dataclass(frozen=True)
class DialogueContinuityState:
    kind: ContinuityKind
    needs_dialogue: bool
    fail_safe_legacy: bool
    matched_reason: str | None = None


_DIRECT_CONTINUITY_PATTERNS: tuple[str, ...] = (
    "what were we talking about",
    "what did we just discuss",
    "what were we discussing",
    "what was the last thing i said",
    "what was the last thing you said",
    "what was the last thing we discussed",
    "what was the last thing we talked about",
    "what did i say",
    "what did you say",
    "what were we doing earlier",
    "what were we doing before",
    "before this",
    "before that",
)
_ANAPHORIC_PHRASES: tuple[str, ...] = (
    "which one",
    "try that",
    "do it",
    "what about that",
    "why does that matter",
)
_ANAPHORIC_WORDS: tuple[str, ...] = ("that", "this", "those", "it")
_INTRA_TURN_ECHO_PATTERNS: tuple[str, ...] = (
    "say that back",
    "repeat that back",
    "read that back",
    "say that in",
    "repeat that in",
)
_UNCERTAIN_CONTINUITY_PATTERNS: tuple[str, ...] = (
    "we were",
    "you said",
    "i said",
    "that thing",
)


def _normalize_continuity(text: str) -> str:
    """Light normalization for deterministic continuity matching.

    Do not delete filler words globally; that can manufacture accidental
    matches. The grammar below absorbs filler in place while staying anchored
    to dialogue-meta structure.
    """
    lowered = (text or "").lower()
    spaced = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", spaced).strip()


_DIRECT_GRAMMAR: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:what|which|remind me)\b[\w\s]*"
        r"\b(?:we|us|i|you)\b[\w\s]*"
        r"\b(?:talk|talking|discuss|discussing|cover|covering|"
        r"doing|working|going over|say|saying|said)\b"
    ),
    re.compile(
        r"\bwhere\b[\w\s]*\b(?:we|us)\b[\w\s]*"
        r"\b(?:leave off|left off|get to|got to|were)\b"
    ),
)


def _content_hash(text: str) -> str:
    return "ch_" + hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def _strip_local_citations(text: str) -> str:
    return re.sub(r"\s*\[E\d+\]", "", text or "").strip()


def _is_intra_turn_echo_instruction(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return any(pattern in lowered for pattern in _INTRA_TURN_ECHO_PATTERNS)


def build_intra_turn_echo_reply(owner_question: str) -> str | None:
    text = (owner_question or "").strip()
    lowered = text.lower()
    matches = [
        lowered.find(pattern)
        for pattern in _INTRA_TURN_ECHO_PATTERNS
        if lowered.find(pattern) >= 0
    ]
    if not matches:
        return None
    target = text[: min(matches)].strip()
    if ":" in target:
        target = target.rsplit(":", 1)[1].strip()
    target = target.strip(" \"'“”‘’")
    target = target.rstrip(".!?;: ")
    if not target:
        return None
    return target[:1].upper() + target[1:] + "."


def dialogue_continuity_state(owner_question: str) -> DialogueContinuityState:
    text = _normalize_continuity(owner_question)
    for pattern in _DIRECT_GRAMMAR:
        match = pattern.search(text)
        if match:
            return DialogueContinuityState(
                kind=ContinuityKind.DIRECT,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=match.group(0)[:60],
            )
    for pattern in _DIRECT_CONTINUITY_PATTERNS:
        if pattern in text:
            return DialogueContinuityState(
                kind=ContinuityKind.DIRECT,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=pattern,
            )
    for pattern in _ANAPHORIC_PHRASES:
        if pattern in text:
            return DialogueContinuityState(
                kind=ContinuityKind.ANAPHORIC,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=pattern,
            )
    if _is_intra_turn_echo_instruction(text):
        return DialogueContinuityState(
            kind=ContinuityKind.NONE,
            needs_dialogue=False,
            fail_safe_legacy=False,
            matched_reason=None,
        )
    for pattern in _ANAPHORIC_WORDS:
        if re.search(rf"\b{re.escape(pattern)}\b", text):
            return DialogueContinuityState(
                kind=ContinuityKind.ANAPHORIC,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=pattern,
            )
    for pattern in _UNCERTAIN_CONTINUITY_PATTERNS:
        if pattern in text:
            return DialogueContinuityState(
                kind=ContinuityKind.NONE,
                needs_dialogue=False,
                fail_safe_legacy=True,
                matched_reason=pattern,
            )
    return DialogueContinuityState(
        kind=ContinuityKind.NONE,
        needs_dialogue=False,
        fail_safe_legacy=False,
        matched_reason=None,
    )


def dialogue_anchor_items(
    chat_history: Iterable[dict] | None,
    *,
    limit_pairs: int = 3,
) -> list[EvidenceItemSeed]:
    from core.brain.conversation_history import history_to_messages

    messages = history_to_messages(chat_history)
    pairs: list[tuple[str, str]] = []
    pending_user: str | None = None
    for message in messages:
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            pending_user = content
        elif role == "assistant" and pending_user:
            pairs.append((pending_user, content))
            pending_user = None

    selected = list(reversed(pairs[-limit_pairs:]))
    return [
        EvidenceItemSeed(
            source_type="dialogue_anchor",
            text=(
                f"User: {_strip_local_citations(user_text)}\n"
                f"Maez: {_strip_local_citations(assistant_text)}"
            ),
            durable_id=_content_hash(
                f"{_strip_local_citations(user_text)}\n"
                f"{_strip_local_citations(assistant_text)}"
            ),
        )
        for user_text, assistant_text in selected
    ]


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


def _temporal_provenance_from_attrs(attrs: str) -> dict | None:
    match = _DATE_MATCH_ATTR.search(attrs or "")
    if not match:
        return None
    method = match.group(1)
    label_match = _DATE_MATCH_LABEL_ATTR.search(attrs or "")
    label = label_match.group(1) if label_match else None
    out = {"method": method, "confirmed": method in ("exact_date", "month_window")}
    if label:
        out["label"] = label
        date_match = _ISO_DATE_RE.search(label)
        if date_match:
            out["date"] = date_match.group(0)
    return out


def _memory_items_with_provenance(body: str) -> list[tuple[str, dict | None]]:
    """Return recalled memory items from structured <RECALLED> envelopes.

    Temporal provenance comes from the envelope opening tag, not from arbitrary
    body text. This is the B3 authority boundary for dated recall.
    """
    out: list[tuple[str, dict | None]] = []
    for attrs, content in _RECALLED_RE.findall(body or ""):
        text = content.strip()
        if text:
            out.append((text, _temporal_provenance_from_attrs(attrs)))
    if out:
        return out
    body = (body or "").strip()
    return [(body, None)] if body else []


def _ranked_items_for_state(
    raw_items: list[tuple[str, str, str | None, dict | None, str | None, str | None]],
    dialogue_state: DialogueContinuityState,
    date_cue: bool = False,
) -> list[tuple[str, str, str | None, dict | None, str | None, str | None]]:
    def rank(item: tuple[str, str, str | None, dict | None, str | None, str | None]) -> int:
        source_type, _text, _durable_id, temporal_provenance, _origin_trust, _origin_prov = item
        if date_cue:
            if (
                source_type in ("memory_context", "memory_evidence")
                and temporal_provenance
                and temporal_provenance.get("confirmed")
            ):
                return _RANK_DATE_CONFIRMED
            if source_type == "temporal_recall_status":
                return _RANK_TEMPORAL_STATUS
            if source_type == "dialogue_anchor":
                return _RANK_DATE_DIALOGUE_ANCHOR
            return _PRIORITY.get(source_type, 9) + _RANK_DATE_CONTEXT_OFFSET
        if (
            dialogue_state.kind == ContinuityKind.DIRECT
            or dialogue_state.fail_safe_legacy
        ):
            if source_type == "dialogue_anchor":
                return 0
            return _PRIORITY.get(source_type, 9) + 1
        if dialogue_state.kind == ContinuityKind.ANAPHORIC:
            if source_type == "dialogue_anchor":
                return 3
            return _PRIORITY.get(source_type, 9)
        return _PRIORITY.get(source_type, 9)

    return sorted(raw_items, key=rank)


def _truncate_item_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 0:
        return ""
    if limit <= len(_TRUNCATION_SUFFIX):
        return text[:limit]
    return text[: limit - len(_TRUNCATION_SUFFIX)].rstrip() + _TRUNCATION_SUFFIX


def _budget_items_for_prompt(
    items: list[EvidenceItem],
    *,
    owner_question: str,
    max_chars: int | None,
    render_version: str | None = None,
) -> list[EvidenceItem]:
    version = render_version or _citation_render_version()
    if max_chars is None:
        max_chars = _DEFAULT_WORKING_SET_CHAR_BUDGET
    if max_chars <= 0 or not items:
        return items
    rendered_chars = len(
        "\n".join(_render_evidence_lines(items, render_version=version))
    ) + len(owner_question or "")
    if rendered_chars <= max_chars:
        return items

    empty_text_items = [replace(item, text="") for item in items]
    overhead = len(
        "\n".join(_render_evidence_lines(empty_text_items, render_version=version))
    ) + len(owner_question or "")
    text_budget = max(max_chars - overhead, 0)
    if version == "v2":
        weights = [1 for _item in items]
    else:
        # The first item's text is rendered twice by _render_evidence_lines
        # ("most important, repeated"), so count it twice in the budget.
        weights = [2 if index == 0 else 1 for index, _item in enumerate(items)]
    unit_budget = text_budget // max(sum(weights), 1)
    budgeted: list[EvidenceItem] = []
    for item, _weight in zip(items, weights, strict=True):
        allowance = max(unit_budget, 0)
        budgeted.append(replace(item, text=_truncate_item_text(item.text, allowance)))
    return budgeted


def assemble_working_set(
    *,
    transcript: str,
    web_context: str,
    owner_question: str,
    chat_history: Iterable[dict] | None = None,
    recall_items: Iterable | None = None,
    max_working_set_chars: int | None = None,
) -> WorkingSet | None:
    state = turn_evidence_state(transcript=transcript, web_context=web_context)
    dialogue_state = dialogue_continuity_state(owner_question)
    cue = absolute_recall_cue(owner_question)
    date_cue = cue.is_address
    override_continuity = cue.override_continuity
    if (
        dialogue_state.kind == ContinuityKind.NONE
        and _is_intra_turn_echo_instruction(owner_question)
        and not date_cue
    ):
        return None
    anchors = (
        dialogue_anchor_items(chat_history)
        if dialogue_state.needs_dialogue or dialogue_state.fail_safe_legacy or date_cue
        else []
    )
    dialogue_authoritative = (
        dialogue_state.kind in (ContinuityKind.DIRECT, ContinuityKind.ANAPHORIC)
        and not override_continuity
    )
    if dialogue_authoritative or date_cue:
        anchors = anchors[:1]

    if (
        (dialogue_state.needs_dialogue or dialogue_state.fail_safe_legacy)
        and not anchors
        and not date_cue
    ):
        return None
    structured_recall_items = tuple(recall_items) if recall_items else None
    if (
        not state.evidence_present
        and not anchors
        and not date_cue
        and not structured_recall_items
    ):
        return None

    raw_items: list[tuple[str, str, str | None, dict | None, str | None, str | None]] = []
    if not dialogue_authoritative:
        if structured_recall_items is not None:
            for item in structured_recall_items:
                source_type = str(getattr(item, "source_type", "") or "")
                if source_type not in ("memory_context", "memory_evidence"):
                    continue
                item_text = str(getattr(item, "text", "") or "").strip()
                if not item_text:
                    continue
                durable_id = getattr(item, "durable_id", None)
                temporal_provenance = getattr(item, "temporal_provenance", None)
                origin_trust = getattr(item, "trust_tier", None)
                origin_provenance = getattr(item, "provenance_source", None)
                raw_items.append(
                    (
                        source_type,
                        item_text,
                        durable_id,
                        temporal_provenance,
                        origin_trust,
                        origin_provenance,
                    )
                )
            for marker, body in _split_blocks(transcript or ""):
                source_type = _SOURCE_TYPE[marker]
                if source_type in ("memory_context", "memory_evidence"):
                    continue
                for item_text in _atomic_items(body):
                    raw_items.append((source_type, item_text, None, None, None, None))
        else:
            for marker, body in _split_blocks(transcript or ""):
                source_type = _SOURCE_TYPE[marker]
                if source_type in ("memory_context", "memory_evidence"):
                    for item_text, provenance in _memory_items_with_provenance(body):
                        raw_items.append((source_type, item_text, None, provenance, None, None))
                else:
                    for item_text in _atomic_items(body):
                        raw_items.append((source_type, item_text, None, None, None, None))

        web_context = web_context or ""
        if web_context.strip() and _WEB_NO_RESULTS not in web_context:
            for item_text in _atomic_items(web_context):
                raw_items.append(("web_context", item_text, None, None, None, None))

    for anchor in anchors:
        raw_items.append((anchor.source_type, anchor.text, anchor.durable_id, None, None, None))

    if date_cue:
        has_confirmed = any(
            provenance and provenance.get("confirmed")
            for _source_type, _text, _durable_id, provenance, _origin_trust, _origin_prov in raw_items
        )
        if not has_confirmed:
            raw_items.append(
                (
                    "temporal_recall_status",
                    "No dated memory matched the explicit date cue in the question.",
                    None,
                    None,
                    None,
                    None,
                )
            )

    if _self_claim_hygiene_enabled():
        fresh_present = any(t[0] in _FRESH_SOURCE_TYPES for t in raw_items)
        if fresh_present:
            kept = [t for t in raw_items if t[5] != "self_web_claim"]
            excluded = len(raw_items) - len(kept)
            raw_items = kept
        else:
            excluded = 0
        logger.info(
            "recall_hygiene fresh_present=%s excluded_self_claims=%d kept_memory_items=%d",
            fresh_present, excluded,
            sum(1 for t in raw_items if t[0] in ("memory_context", "memory_evidence")),
        )

    if not raw_items:
        return None

    raw_items = _ranked_items_for_state(raw_items, dialogue_state, date_cue)
    items = [
        EvidenceItem(
            local_label=f"E{index + 1}",
            source_type=source_type,
            text=text,
            durable_id=durable_id or _content_hash(text),
            temporal_provenance=temporal_provenance,
            origin_trust=origin_trust,
            origin_provenance=origin_provenance,
        )
        for index, (
            source_type,
            text,
            durable_id,
            temporal_provenance,
            origin_trust,
            origin_provenance,
        ) in enumerate(raw_items)
    ]
    render_version = _citation_render_version()
    items = _budget_items_for_prompt(
        items,
        owner_question=owner_question,
        max_chars=max_working_set_chars,
        render_version=render_version,
    )

    from core.routing import web_containment as _wc  # local import: keep web_containment off focused_cognition's import path (no cycle; defensive)
    _contain = _wc.containment_enabled()
    _nonce = _wc.new_nonce() if _contain else ""
    _lines, _web_segments, _web_digests = _render_evidence_lines_contained(
        items, render_version=render_version, nonce=_nonce, contain_enabled=_contain)
    ordered = "\n".join(_lines)
    if _contain and _web_segments:
        ordered = _wc.standing_instruction() + "\n\n" + ordered
        _web_digest = ",".join(dict.fromkeys(_web_digests))[:80]
        _wc.emit_receipt(_wc.containment_receipt(
            ordered, nonce=_nonce, path="focused",
            expected_segments=_web_segments,
            digest=_web_digest))

    total_chars = len(ordered) + len(owner_question or "")
    return WorkingSet(
        items=items,
        ordered_evidence_text=ordered,
        owner_question=owner_question,
        working_set_chars=total_chars,
        working_set_tokens_est=total_chars // 4,
        citation_render_version=render_version,
    )


def _voice_card(surface: str) -> str:
    # Voice surfaces are excluded by the daemon gate in v1.
    del surface
    card = _focused_capability_card()
    return f"{_VOICE_CARD_TEXT}\n\n{card}" if card else _VOICE_CARD_TEXT


def focused_synthesize(
    working_set: WorkingSet,
    *,
    surface: str,
    chat_fn=None,
    model=None,
) -> FocusedResult:
    import time as _time

    if chat_fn is None:
        from core import llm_client as _llm_client
        from core.routing.brain_gateway import BrainPurpose, with_purpose

        def chat_fn(**kwargs):
            with with_purpose(BrainPurpose.OWNER_RECALL):
                return _llm_client.chat(**kwargs)
    if model is None:
        from core.model_config import PRIMARY_MODEL

        model = PRIMARY_MODEL

    _t0 = _time.monotonic()
    system = (
        f"{_voice_card(surface)}\n\n"
        f"{_citation_instruction(working_set.citation_render_version)}\n\n"
        f"{_TRUST_TIER_INSTRUCTION}\n\n"
        f"{_ORIGIN_TRUST_INSTRUCTION}\n\n"
        f"=== EVIDENCE (cite [E#]) ===\n"
        f"{working_set.ordered_evidence_text}"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": working_set.owner_question},
    ]
    _t1 = _time.monotonic()
    response = chat_fn(
        model=model,
        messages=messages,
        think=False,
        options={"temperature": 0.7, "num_predict": 4096},
    )
    _t2 = _time.monotonic()
    reply = (getattr(getattr(response, "message", None), "content", None) or "").strip()
    cited_ids = sorted({f"E{match.group(1)}" for match in _CITE_RE.finditer(reply)})
    return FocusedResult(
        reply=reply,
        cited_ids=cited_ids,
        working_set_chars=working_set.working_set_chars,
        prompt_build_ms=int((_t1 - _t0) * 1000),
        chat_total_ms=int((_t2 - _t1) * 1000),
        reply_token_est=len(reply) // 4,
    )


def build_honest_empty_reply(
    *,
    query: str,
    source: str,
    surface: str,
    chat_fn=None,
    model=None,
) -> HonestEmptyResult:
    """Answer an empty search from a one-fact focused working set."""
    if chat_fn is None:
        from core import llm_client as _llm_client
        from core.routing.brain_gateway import BrainPurpose, with_purpose

        def chat_fn(**kwargs):
            with with_purpose(BrainPurpose.OWNER_RECALL):
                return _llm_client.chat(**kwargs)
    if model is None:
        from core.model_config import PRIMARY_MODEL

        model = PRIMARY_MODEL

    query = query or ""
    source = source or "web"
    empty_fact = f'A {source} search for "{query}" returned no usable results.'
    item = EvidenceItem(
        local_label="E1",
        source_type="empty_result",
        text=empty_fact,
        durable_id=_content_hash(f"{source}\n{query}"),
    )
    working_set_chars = len(empty_fact)
    working_set = WorkingSet(
        items=[item],
        ordered_evidence_text=empty_fact,
        owner_question=query,
        working_set_chars=working_set_chars,
        working_set_tokens_est=working_set_chars // 4,
    )
    deterministic = (
        f"I searched {source} for that and found no usable results. "
        "I won't guess why or invent a fix. "
        "Want me to try a different source or rephrase the query?"
    )

    raw_reply = ""
    try:
        system = (
            f"{_voice_card(surface)}\n\n"
            f"{_HONEST_EMPTY_INSTRUCTION}\n\n"
            f"=== FACT ===\n{empty_fact}"
        )
        response = chat_fn(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": query},
            ],
            think=False,
            options={"temperature": 0.7, "num_predict": 256},
        )
        raw_reply = (
            getattr(getattr(response, "message", None), "content", None) or ""
        ).strip()
    except Exception:
        raw_reply = ""

    forbidden_hit = bool(raw_reply) and _contains_forbidden_empty_vocab(raw_reply)
    if not raw_reply or forbidden_hit:
        reply = deterministic
        mode = "deterministic_fallback"
    else:
        reply = raw_reply
        mode = "focused"

    return HonestEmptyResult(
        reply=reply,
        mode=mode,
        forbidden_hit=forbidden_hit,
        working_set=working_set,
        result=FocusedResult(
            reply=reply,
            cited_ids=[],
            working_set_chars=working_set_chars,
        ),
        verdict=GroundednessVerdict(
            verdict="empty_but_honest",
            citation_coverage=0.0,
            unmatched=[],
        ),
    )


def photo_focused_synth_enabled() -> bool:
    """Direction (b) gate. Default ON; set MAEZ_PHOTO_FOCUSED_SYNTH=0 to revert
    photo turns to the legacy megaprompt synthesis inside handle_message."""
    import os

    val = os.environ.get("MAEZ_PHOTO_FOCUSED_SYNTH", "1").strip().lower()
    return val not in ("0", "false", "no", "off")


def _photo_contradiction_sense_requested() -> bool:
    """Local pre-import gate; the organ itself stays unimported while flag-off."""
    val = (os.environ.get("MAEZ_PHOTO_CONTRADICTION_SENSE", "") or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def photo_freshness_web_search_enabled() -> bool:
    """Owner-gated web leg for photo-triggered freshness checks. Default off."""
    val = (os.environ.get("MAEZ_PHOTO_FRESHNESS_WEB_SEARCH", "") or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


_PHOTO_FRESHNESS_RE = re.compile(
    r"\b("
    r"latest|current|today|now|new|released?|announced?|launch(?:ed)?|"
    r"benchmark|pricing|price|model|version"
    r")\b",
    re.IGNORECASE,
)
_PHOTO_KNOWN_ENTITY_RE = re.compile(
    r"\b("
    r"Anthropic|Claude|Mythos|Fable|OpenAI|GPT|Gemini|Google|Meta|Llama|"
    r"Qwen|Gemma|Mistral|Grok|xAI|Apple|Microsoft|Nvidia"
    r")\b",
    re.IGNORECASE,
)
_PHOTO_MODEL_PHRASE_RE = re.compile(
    r"\b(?:Claude\s+)?(?:Mythos|Fable|Opus|Sonnet|Haiku)\s*\d+(?:\.\d+)?\b",
    re.IGNORECASE,
)
_PHOTO_PERSON_FOCUSED_RE = re.compile(
    r"\b(?:latest\s+news\s+about|news\s+about|about|person\s+named|person\s+called)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b",
)


def _dedupe_preserve_case(parts: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        cleaned = re.sub(r"\s+", " ", (part or "").strip(" \t\r\n\"'.,;:"))
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def _photo_person_focused(haystack: str) -> bool:
    for match in _PHOTO_PERSON_FOCUSED_RE.finditer(haystack):
        phrase = match.group(1)
        phrase_with_tail = haystack[match.start(1) : min(len(haystack), match.end(1) + 12)]
        if _PHOTO_MODEL_PHRASE_RE.search(phrase_with_tail):
            continue
        if _PHOTO_KNOWN_ENTITY_RE.search(phrase):
            continue
        return True
    return False


def photo_freshness_search_query(*, caption: str, analysis_text: str) -> str | None:
    """Derive a compact web query when photo evidence implies a current-world claim."""
    caption = caption or ""
    analysis_text = analysis_text or ""
    haystack = f"{caption}\n{analysis_text}"
    if not _PHOTO_FRESHNESS_RE.search(haystack):
        return None
    if _photo_person_focused(haystack):
        return None
    if not (
        _PHOTO_KNOWN_ENTITY_RE.search(haystack)
        or _PHOTO_MODEL_PHRASE_RE.search(haystack)
    ):
        return None

    terms: list[str] = []
    if re.search(r"\banthropic\b", haystack, re.IGNORECASE):
        terms.append("Anthropic")
    for phrase in re.findall(r'"([^"]{3,90})"', haystack):
        if _PHOTO_KNOWN_ENTITY_RE.search(phrase) or _PHOTO_MODEL_PHRASE_RE.search(phrase):
            terms.append(phrase)
    for match in _PHOTO_MODEL_PHRASE_RE.finditer(haystack):
        terms.append(match.group(0))
    for word in ("latest", "released", "announced", "today"):
        if re.search(rf"\b{word}\b", haystack, re.IGNORECASE):
            terms.append(word)

    compact = " ".join(_dedupe_preserve_case(terms))
    return compact[:180] if compact else None


def synthesize_photo_turn(
    *,
    analysis_text: str,
    caption: str,
    surface: str,
    fresh_context: str | None = None,
    chat_fn=None,
    model=None,
) -> FocusedResult:
    """Answer an owner-sent photo from Maez's own local vision analysis, over a
    BOUNDED working set — never the full daemon megaprompt.

    The live witness (2026-06-07) proved vision works (success=True,
    analysis_chars=342) but the ~megaprompt's "Vision: Maez cannot see"
    broken-systems block overrode the present analysis. Here the only evidence is
    the photo analysis (E1); the prompt carries no screen-perception /
    broken-systems contradiction, so the brain answers from what it actually saw.
    """
    import time as _time

    if chat_fn is None:
        from core import llm_client as _llm_client
        from core.routing.brain_gateway import BrainPurpose, with_purpose

        def chat_fn(**kwargs):
            with with_purpose(BrainPurpose.OWNER_REPLY):
                return _llm_client.chat(**kwargs)
    if model is None:
        from core.model_config import PRIMARY_MODEL

        model = PRIMARY_MODEL

    analysis_text = (analysis_text or "").strip()
    caption = caption or ""
    fresh_context = (fresh_context or "").strip()
    item = EvidenceItem(
        local_label="E1",
        source_type="photo_vision",
        text=analysis_text,
        durable_id=_content_hash(analysis_text),
    )
    items = [item]
    if fresh_context:
        items.append(
            EvidenceItem(
                local_label="E2",
                source_type="web_context",
                text=fresh_context,
                durable_id=_content_hash(fresh_context),
            )
        )
    working_set_chars = len(analysis_text) + len(caption) + len(fresh_context)
    _working_set = WorkingSet(
        items=items,
        ordered_evidence_text=(
            analysis_text if not fresh_context else analysis_text + "\n\n" + fresh_context
        ),
        owner_question=caption,
        working_set_chars=working_set_chars,
        working_set_tokens_est=working_set_chars // 4,
    )

    # Deterministic fallback: the vision analysis verbatim, citing [E1] so the
    # reply, cited_ids, log, and downstream checks all agree. Grounded by
    # construction (it IS the evidence). receipt_reason marks it as forced.
    # Neutralize any [E#] already inside the analysis (e.g. image text like
    # "[E2] on a button") using the SAME regex that parses citations, so the
    # fallback's only citation is the prepended [E1] and cited_ids stays exactly
    # ["E1"] — it cannot be polluted by image text.
    _safe_analysis = _CITE_RE.sub(lambda m: f"(E{m.group(1)})", analysis_text)
    deterministic = (
        "Here's what I'm confident I saw [E1]: " + _safe_analysis
    ).strip()

    base_system = (
        f"{_voice_card(surface)}\n\n"
        f"{_PHOTO_VISION_INSTRUCTION}\n\n"
        f"=== WHAT MAEZ SAW IN THE PHOTO (cite [E1]) ===\n"
        f"{analysis_text}"
    )
    if fresh_context:
        from core.routing import web_containment as _wc  # local import: keep off the photo-path import (no cycle; defensive)
        if _wc.containment_enabled() and fresh_context:
            import hashlib
            _nonce = _wc.new_nonce()
            _digest = hashlib.sha256(fresh_context.encode("utf-8")).hexdigest()[:16]
            _wrapped = _wc.wrap_web_text(fresh_context, nonce=_nonce, source="web", digest=_digest)
            fresh_context = _wc.standing_instruction() + "\n\n" + _wrapped
            _wc.emit_receipt(_wc.containment_receipt(
                _wrapped, nonce=_nonce, path="photo", expected_segments=1, digest=_digest))
        base_system += (
            "\n\n=== FRESH WORLD CHECK (cite [E2] for current-world verification) ===\n"
            f"{fresh_context}\n\n"
            "Use E1 for what the image appears to show. Use E2 only for whether "
            "the current-world claim is externally verified. If E2 says no "
            "results, do not dismiss E1 from stale memory; say the image appears "
            "to show it but you could not verify it."
        )

    def _run(system_text):
        try:
            response = chat_fn(
                model=model,
                messages=[
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": caption},
                ],
                think=False,
                options={"temperature": 0.7, "num_predict": 1024},
            )
            return (
                getattr(getattr(response, "message", None), "content", None) or ""
            ).strip()
        except Exception:
            return ""

    def _valid_photo_citation(text: str) -> bool:
        # Valid only if it cites the photo evidence and no labels outside the
        # bounded photo/freshness working set.
        allowed = {"E1", "E2"} if fresh_context else {"E1"}
        labels = {f"E{m.group(1)}" for m in _CITE_RE.finditer(text)}
        return "E1" in labels and labels <= allowed

    _t0 = _time.monotonic()
    _t1 = _time.monotonic()
    first_raw = _run(base_system)
    if first_raw and _valid_photo_citation(first_raw):
        reply, receipt_reason = first_raw, "cited_ok"
    elif first_raw:
        # Brain produced an ungrounded reply. One forced-citation retry.
        retry_raw = _run(base_system + "\n\n" + _PHOTO_VISION_RETRY_INSTRUCTION)
        if retry_raw and _valid_photo_citation(retry_raw):
            reply, receipt_reason = retry_raw, "retry_recovered"
        else:
            reply, receipt_reason = deterministic, "deterministic_fallback"
    else:
        # Brain returned nothing on the first call — no wasted retry.
        reply, receipt_reason = deterministic, "deterministic_fallback"
    _t2 = _time.monotonic()

    contradiction_receipt = None
    contradiction_claim_count = 0
    contradiction_count = 0
    contradiction_latency_ms = None
    contradiction_model_id = None
    contradiction_revision = None
    contradiction_sha256 = None
    contradiction_claim_limit_exceeded = False
    contradiction = None

    if (
        receipt_reason != "deterministic_fallback"
        and _photo_contradiction_sense_requested()
    ):
        try:
            from core.routing import photo_contradiction as _photo_contradiction

            verifier = _photo_contradiction.LocalNLIContradictionVerifier()
            contradiction = _photo_contradiction.check_photo_contradictions(
                premise=analysis_text,
                reply=reply,
                verifier=verifier,
            )
            if contradiction.reason == "trust_demoted" and contradiction.sense_note:
                revision_raw = _run(
                    base_system
                    + "\n\n"
                    + contradiction.sense_note
                    + "\n\nRevise once. Keep every direct claim about the photo "
                    "grounded in [E1]. This is a sense, not a verdict; if on a "
                    "second look you still believe what you saw, say so plainly "
                    "and explain why."
                )
                if revision_raw and _valid_photo_citation(revision_raw):
                    revision_check = _photo_contradiction.check_photo_contradictions(
                        premise=analysis_text,
                        reply=revision_raw,
                        verifier=verifier,
                    )
                    reply = revision_raw
                    contradiction = revision_check
                    if revision_check.reason == "clear":
                        contradiction = replace(revision_check, reason="revised_clear")
                else:
                    contradiction = replace(contradiction, reason="retry_failed")
            _t2 = _time.monotonic()
        except Exception as exc:
            logger.warning(
                "photo contradiction sense failed: %s", type(exc).__name__
            )

    if contradiction is not None:
        contradiction_receipt = contradiction.reason
        contradiction_claim_count = contradiction.claim_count
        contradiction_count = contradiction.contradiction_count
        contradiction_latency_ms = contradiction.latency_ms
        contradiction_model_id = contradiction.model_id
        contradiction_revision = contradiction.revision
        contradiction_sha256 = contradiction.sha256
        contradiction_claim_limit_exceeded = contradiction.claim_limit_exceeded

    cited_ids = sorted({f"E{m.group(1)}" for m in _CITE_RE.finditer(reply)})
    return FocusedResult(
        reply=reply,
        cited_ids=cited_ids,
        working_set_chars=working_set_chars,
        prompt_build_ms=int((_t1 - _t0) * 1000),
        chat_total_ms=int((_t2 - _t1) * 1000),
        reply_token_est=len(reply) // 4,
        receipt_reason=receipt_reason,
        contradiction_receipt=contradiction_receipt,
        contradiction_claim_count=contradiction_claim_count,
        contradiction_count=contradiction_count,
        contradiction_latency_ms=contradiction_latency_ms,
        contradiction_model_id=contradiction_model_id,
        contradiction_revision=contradiction_revision,
        contradiction_sha256=contradiction_sha256,
        contradiction_claim_limit_exceeded=contradiction_claim_limit_exceeded,
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


class FocusedCognitionStore:
    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS focused_cognition_runs (
                        id TEXT PRIMARY KEY,
                        created_at REAL NOT NULL,
                        surface TEXT NOT NULL,
                        chat_id_hash TEXT,
                        evidence_map_json TEXT NOT NULL,
                        source_types_json TEXT NOT NULL,
                        working_set_chars INTEGER NOT NULL,
                        working_set_tokens_est INTEGER NOT NULL,
                        legacy_prompt_chars INTEGER,
                        legacy_prompt_tokens_est INTEGER,
                        citation_ids_emitted_json TEXT NOT NULL,
                        citation_coverage REAL NOT NULL,
                        unmatched_citations_json TEXT NOT NULL,
                        groundedness_verdict TEXT NOT NULL,
                        fallback_reason TEXT,
                        routing_observation_id TEXT
                    )
                    """
                )

    def record(
        self,
        *,
        surface: str,
        chat_id: str | None,
        working_set: WorkingSet | None,
        result: FocusedResult | None,
        verdict: GroundednessVerdict | None,
        legacy_prompt_chars: int | None,
        fallback_reason: str | None,
        routing_observation_id: str | None,
    ) -> str:
        row_id = uuid.uuid4().hex
        items = list(working_set.items) if working_set is not None else []
        evidence_map = [
            {
                "local_label": item.local_label,
                "source_type": item.source_type,
                "durable_id": item.durable_id,
            }
            for item in items
        ]
        source_types = sorted({item.source_type for item in items})
        citation_ids = result.cited_ids if result is not None else []
        unmatched = verdict.unmatched if verdict is not None else []
        coverage = verdict.citation_coverage if verdict is not None else 0.0
        groundedness = verdict.verdict if verdict is not None else "not_applicable"
        working_set_chars = working_set.working_set_chars if working_set is not None else 0
        working_set_tokens = working_set.working_set_tokens_est if working_set is not None else 0
        legacy_tokens = legacy_prompt_chars // 4 if legacy_prompt_chars else None
        row = {
            "id": row_id,
            "created_at": time.time(),
            "surface": surface,
            "chat_id_hash": _sha256(chat_id) if chat_id else None,
            "evidence_map_json": json.dumps(evidence_map, sort_keys=True),
            "source_types_json": json.dumps(source_types, sort_keys=True),
            "working_set_chars": int(working_set_chars),
            "working_set_tokens_est": int(working_set_tokens),
            "legacy_prompt_chars": legacy_prompt_chars,
            "legacy_prompt_tokens_est": legacy_tokens,
            "citation_ids_emitted_json": json.dumps(citation_ids, sort_keys=True),
            "citation_coverage": float(coverage),
            "unmatched_citations_json": json.dumps(unmatched, sort_keys=True),
            "groundedness_verdict": groundedness,
            "fallback_reason": fallback_reason,
            "routing_observation_id": routing_observation_id,
        }
        columns = tuple(row.keys())
        placeholders = ", ".join("?" for _ in columns)
        with self._connect() as conn:
            with conn:
                conn.execute(
                    f"INSERT INTO focused_cognition_runs ({', '.join(columns)}) "
                    f"VALUES ({placeholders})",
                    tuple(row[column] for column in columns),
                )
        return row_id

    def get(self, row_id: str) -> sqlite3.Row:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM focused_cognition_runs WHERE id = ?",
                (row_id,),
            ).fetchone()
        if row is None:
            raise KeyError(row_id)
        return row


def _default_store() -> FocusedCognitionStore:
    return FocusedCognitionStore()


def record_focused_cognition_run(**kwargs) -> str:
    return _default_store().record(**kwargs)
