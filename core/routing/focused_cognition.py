# Copyright (C) 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Focused Cognition organ helpers.

When query evidence is present on a text surface, assemble a small bounded
working set so the brain can answer from evidence instead of the full daemon
megaprompt.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid

from core.routing.observation import _default_db_path, _sha256
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


class FocusedCognitionStore:
    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
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
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    f"INSERT INTO focused_cognition_runs ({', '.join(columns)}) "
                    f"VALUES ({placeholders})",
                    tuple(row[column] for column in columns),
                )
        return row_id

    def get(self, row_id: str) -> sqlite3.Row:
        with closing(self._connect()) as conn:
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
