# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Trace schema — Slice 1 of the trace-harness work.

One :class:`Trace` per owner-bridge /message turn. Field names lean
OpenTelemetry-friendly (``trace_id``, ``attributes``-style nested
dicts) so a future export adapter can map to OTel GenAI spans without
reshaping in-memory data. v1 is local-only JSONL; nothing here depends
on a tracing SDK.

Honesty contract for the schema itself:

- ``audit.changed_output`` is a literal pre/post comparison hash, not a
  guess. The daemon stamps it from the actual two strings.
- ``stored_text_hash`` / ``sent_text_hash`` / ``final_text_hash`` are
  three separate fields so the audit-before-store invariant
  (``stored == sent == final_after_audit``) is *inspectable*. Equal
  hashes confirm the invariant held; unequal hashes are a real signal.
- ``tool_calls`` is an empty list when no tools ran, NOT ``None``. The
  empty list is the truthful representation of "synthesis-only turn".
- ``terminal_state`` is set explicitly: ``"replied"``, ``"errored"``,
  ``"timed_out"``, etc. There is no implicit "success".
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def new_trace_id() -> str:
    """Return a fresh 24-hex-char trace id. Local-only collision space
    (one machine, one process); 24 hex is overkill but cheap."""
    return secrets.token_hex(12)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_text(text: str) -> str:
    """SHA-256 hex of the text, first 16 chars. Short enough to read in
    a JSONL line, long enough to confirm equality of three reply
    strings without storing the whole text three times."""
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class ToolCall:
    """One tool invocation within a turn. Surfaces that run a tool loop
    populate this; the owner-bridge /message endpoint typically yields
    empty `tool_calls` because synthesis is text-only."""

    name: str
    args_summary: str = ""
    status: str = ""  # "ok", "error", "timeout", "denied"
    elapsed_ms: int = 0
    output_summary: str = ""
    error_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditInfo:
    """Did audit run on this turn, and did it modify the reply?

    `ran` is True iff `core.safety.audited_output.audit_assistant_text`
    was invoked successfully (no exception). `changed_output` is True
    iff the pre-audit and post-audit text hashes differ — a literal
    comparison, not a guess.
    """

    ran: bool = False
    changed_output: bool = False
    flags: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Trace:
    """One /message turn, structured.

    Required fields are populated by ``handle_message`` at well-defined
    points: ``trace_id`` + ``created_at`` at entry, ``memory_ids`` after
    Chroma recall, ``lived_recall_ids`` after the lived brief is built,
    ``tool_calls`` from the surface adapter (default empty),
    ``audit`` from the audit pre/post comparison, ``*_text_hash`` from
    the three reply strings, ``latency_ms`` at exit, ``terminal_state``
    on every code path that returns or raises.
    """

    trace_id: str
    created_at: str
    surface: str
    user_text: str = ""
    memory_ids: list[str] = field(default_factory=list)
    lived_recall_ids: list[str] = field(default_factory=list)
    # Working-self goal hierarchy assembled at this turn. Each entry is
    # a compact ``"source: text"`` label (e.g.
    # ``"cares_about: Rohit cares about truthful continuity"``). Empty
    # by default; populated when ``MAEZ_WORKING_SELF`` is enabled and
    # ``assemble_goals`` returns a non-empty hierarchy. Conway 2000 +
    # Park 2023 — observability for goal-driven retrieval (Session 3).
    working_self_goals: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    audit: AuditInfo = field(default_factory=AuditInfo)
    final_text_excerpt: str = ""
    final_text_hash: str = ""
    sent_text_hash: str = ""
    stored_text_hash: str = ""
    latency_ms: int = 0
    terminal_state: str = ""
    error: str = ""

    @classmethod
    def start(cls, *, surface: str, user_text: str = "") -> "Trace":
        return cls(
            trace_id=new_trace_id(),
            created_at=_now_iso(),
            surface=surface,
            # Cap user_text in the trace so a multi-MB paste doesn't
            # bloat every JSONL line; full text lives in memory storage.
            user_text=(user_text or "")[:2000],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))


# Lightweight ID extractor for the lived recall brief. The brief is
# rendered by `core.memory.lived_recall.build_lived_recall_brief` and
# carries evidence ids in the form ``[ep:ep-XXX | sources: core-YYY]``.
# The trace captures these so a future harness can verify the model's
# reply cited evidence the brief actually surfaced.
_EVIDENCE_ID_RE = re.compile(
    r"\b("
    r"ep-[a-f0-9]+"          # episode id
    r"|core-[a-f0-9]+"       # core memory id
    r"|followup-doc:[^\]\s]+"  # followup doc id (carries a path)
    r")\b"
)


def extract_evidence_ids(brief_text: str) -> list[str]:
    """Pull every `ep-…`, `core-…`, `followup-doc:…` id out of a lived
    recall brief, deduplicating while preserving first-seen order. An
    empty or None brief yields an empty list — never raises."""
    if not brief_text:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _EVIDENCE_ID_RE.finditer(brief_text):
        eid = match.group(1)
        if eid not in seen:
            seen.add(eid)
            ordered.append(eid)
    return ordered
