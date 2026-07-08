# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Deterministic citation lock for consolidation artifacts.

This module is the B1 "law as code" boundary. It validates proposed durable
artifacts against already-materialized ledger rows and returns data-only
verdicts. It never writes, retries, weakens checks, calls an LLM, or imports
daemon/runtime surfaces.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from core.ledger import chain
from core.ledger.taint_stamping import ALLOWED_TAINT_LABELS, TAINT_LABEL_ORDER

MAX_ARTIFACT_TEXT_CHARS = 16_384

REFUSAL_CODES = frozenset(
    (
        "citation_missing_row",
        "citation_outside_span",
        "citation_chain_invalid",
        "taint_not_inherited",
        "citations_empty",
        "citations_capped",
        "privacy_sealed_row",
        "lived_status_unanchored",
        "artifact_oversized",
    )
)

_CAPPED_RE = re.compile(r"(?:^|[,\s])\+(\d+|n)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Verdict:
    ok: bool
    refusal_code: str | None = None
    offending_citation_ids: tuple[str, ...] = ()
    detail_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SpanView:
    after_chain_position: int
    high_water: int
    anchor_chain_position: int | None
    rows: tuple[dict, ...]


def _reject(
    refusal_code: str,
    offending_citation_ids: Iterable[str] = (),
    detail_codes: Iterable[str] = (),
) -> Verdict:
    return Verdict(
        ok=False,
        refusal_code=refusal_code,
        offending_citation_ids=tuple(
            str(item) for item in offending_citation_ids if str(item)
        ),
        detail_codes=tuple(str(item) for item in detail_codes if str(item)),
    )


def _accept() -> Verdict:
    return Verdict(ok=True)


def _mapping_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _span_view(span: Any) -> _SpanView:
    rows = tuple(dict(row) for row in (_mapping_get(span, "rows", ()) or ()))
    high_water = _mapping_get(span, "high_water", None)
    if high_water is None:
        high_water = max((int(row["chain_position"]) for row in rows), default=-1)
    after = _mapping_get(span, "after_chain_position", None)
    if after is None:
        after = _mapping_get(span, "start_chain_position", -1)
    anchor = _mapping_get(span, "anchor_chain_position", None)
    if anchor is None:
        anchor = _mapping_get(span, "birth_anchor_chain_position", None)
    return _SpanView(
        after_chain_position=int(after),
        high_water=int(high_water),
        anchor_chain_position=None if anchor is None else int(anchor),
        rows=rows,
    )


def _artifact_text(artifact: Any) -> str:
    for key in ("text", "episode_digest", "question", "content"):
        value = _mapping_get(artifact, key, None)
        if isinstance(value, str):
            return value
    return ""


def _artifact_taint_labels(artifact: Any) -> set[str]:
    labels = _mapping_get(artifact, "taint_labels", None)
    if labels is None:
        raw_json = _mapping_get(artifact, "taint_labels_json", None)
        if isinstance(raw_json, str):
            try:
                labels = json.loads(raw_json)
            except json.JSONDecodeError:
                labels = []
    if labels is None or isinstance(labels, (str, bytes)):
        return set()
    return {label for label in labels if isinstance(label, str)}


def _row_citations(artifact: Any) -> Any:
    for key in ("row_citations", "citations", "source_rows"):
        value = _mapping_get(artifact, key, None)
        if value is not None:
            return value
    return None


def _contains_capped_citation_summary(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_CAPPED_RE.search(value.strip()))
    if isinstance(value, Mapping):
        return any(_contains_capped_citation_summary(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_capped_citation_summary(v) for v in value)
    return False


def _citation_id(citation: Any) -> str:
    if isinstance(citation, str):
        return citation.strip()
    if isinstance(citation, Mapping):
        turn_id = citation.get("turn_id")
        if isinstance(turn_id, str):
            return turn_id.strip()
    return ""


def _citation_ids(citations: Any) -> tuple[str, ...]:
    if not isinstance(citations, list):
        return ()
    return tuple(_citation_id(citation) for citation in citations)


def _load_rows_from_db(db_path: str | Path) -> list[dict]:
    path = Path(db_path)
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM turns ORDER BY chain_position ASC",
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _rows_from_reader(reader: Any, span: _SpanView) -> list[dict] | None:
    if reader is None:
        return None
    if isinstance(reader, (str, Path)):
        return _load_rows_from_db(reader)
    if callable(reader):
        try:
            rows = reader(span)
        except TypeError:
            rows = reader()
        return [dict(row) for row in rows]
    rows = _mapping_get(reader, "rows", None)
    if rows is not None:
        return [dict(row) for row in rows]
    try:
        return [dict(row) for row in reader]
    except TypeError:
        return None


def _ordered_rows(
    span: _SpanView,
    ledger_rows_or_reader: Any,
) -> list[dict]:
    rows = _rows_from_reader(ledger_rows_or_reader, span)
    if rows is None:
        rows = list(span.rows)
    return sorted(
        (dict(row) for row in rows),
        key=lambda row: int(row.get("chain_position", -1)),
    )


def _row_taint_labels(row: Mapping[str, Any]) -> set[str]:
    raw = row.get("taint_labels_json", "[]")
    try:
        labels = json.loads(raw if isinstance(raw, str) else "[]")
    except json.JSONDecodeError:
        labels = []
    return {label for label in labels if isinstance(label, str)}


def _canonical_label_tuple(labels: Iterable[str]) -> tuple[str, ...]:
    label_set = {label for label in labels if label in ALLOWED_TAINT_LABELS}
    return tuple(label for label in TAINT_LABEL_ORDER if label in label_set)


def _ids_for_taint_miss(
    cited_rows: Iterable[Mapping[str, Any]],
    missing_labels: set[str],
) -> tuple[str, ...]:
    out: list[str] = []
    for row in cited_rows:
        if _row_taint_labels(row) & missing_labels:
            out.append(str(row.get("turn_id", "")))
    return tuple(out)


def _verify_supplied_rows(rows: list[dict]) -> list[dict]:
    violations: list[dict] = []
    if not rows:
        return violations
    positions: set[int] = set()
    for index, row in enumerate(rows):
        turn_id = str(row.get("turn_id", ""))
        position = row.get("chain_position")
        if not isinstance(position, int):
            violations.append(
                {
                    "row_index": index,
                    "turn_id": turn_id,
                    "reason": "chain-position-not-integer",
                    "expected": "integer chain_position",
                    "actual": repr(position),
                }
            )
        elif position in positions:
            violations.append(
                {
                    "row_index": index,
                    "turn_id": turn_id,
                    "reason": "chain-position-duplicate",
                    "expected": f"unique position {position}",
                    "actual": str(position),
                }
            )
        else:
            positions.add(position)

        stored_prev = row.get("prev_chain_hash")
        stored_hash = row.get("chain_hash", "")
        recomputed = chain.compute_chain_hash(row, stored_prev)
        if recomputed != stored_hash:
            violations.append(
                {
                    "row_index": index,
                    "turn_id": turn_id,
                    "reason": "chain-hash-mismatch",
                    "expected": recomputed,
                    "actual": stored_hash if isinstance(stored_hash, str) else "",
                }
            )

        if index == 0:
            continue
        previous = rows[index - 1]
        previous_position = previous.get("chain_position")
        if isinstance(position, int) and isinstance(previous_position, int):
            if position != previous_position + 1:
                continue
        previous_hash = previous.get("chain_hash", "")
        if stored_prev != previous_hash:
            violations.append(
                {
                    "row_index": index,
                    "turn_id": turn_id,
                    "reason": "broken-prev-link",
                    "expected": previous_hash if isinstance(previous_hash, str) else "",
                    "actual": stored_prev if isinstance(stored_prev, str) else "",
                }
            )
    return violations


def _verify_chain_for_lock(rows: list[dict], span: _SpanView) -> list[dict]:
    prefix_rows = [
        row
        for row in rows
        if int(row.get("chain_position", -1)) <= span.high_water
    ]
    if prefix_rows and prefix_rows[0].get("prev_chain_hash") is None:
        return chain.verify_chain(prefix_rows)
    return _verify_supplied_rows(prefix_rows)


def _chain_invalid_verdict(
    violations: list[dict],
    cited_ids: tuple[str, ...],
) -> Verdict:
    cited_set = set(cited_ids)
    offending = [
        str(violation.get("turn_id", ""))
        for violation in violations
        if str(violation.get("turn_id", "")) in cited_set
    ]
    if not offending:
        offending = list(cited_ids)
    return _reject(
        "citation_chain_invalid",
        offending,
        [str(violation.get("reason", "")) for violation in violations],
    )


def validate(artifact: Any, span: Any, ledger_rows_or_reader: Any) -> Verdict:
    """Validate a proposed artifact against a declared ledger span.

    ``ledger_rows_or_reader`` may be a SQLite DB path, a callable returning
    rows, an S2-style object carrying ``rows``, or an iterable of row dicts.
    Passing a DB path gives the lock a fresh read-only chain check, so body
    tampering after span materialization is still caught.
    """
    span_view = _span_view(span)
    text = _artifact_text(artifact)
    if len(text) > MAX_ARTIFACT_TEXT_CHARS:
        return _reject("artifact_oversized")

    citations = _row_citations(artifact)
    if not isinstance(citations, list) or not citations:
        return _reject("citations_empty")
    if _contains_capped_citation_summary(citations):
        return _reject("citations_capped", _citation_ids(citations))

    cited_ids = _citation_ids(citations)
    if not cited_ids or any(not turn_id for turn_id in cited_ids):
        return _reject("citation_missing_row", cited_ids)

    all_rows = _ordered_rows(span_view, ledger_rows_or_reader)
    violations = _verify_chain_for_lock(all_rows, span_view)
    if violations:
        return _chain_invalid_verdict(violations, cited_ids)

    rows_by_id = {str(row.get("turn_id", "")): row for row in all_rows}
    span_by_id = {str(row.get("turn_id", "")): row for row in span_view.rows}
    missing = [turn_id for turn_id in cited_ids if turn_id not in rows_by_id]
    if missing:
        return _reject("citation_missing_row", missing)

    outside: list[str] = []
    for turn_id in cited_ids:
        row = rows_by_id[turn_id]
        position = int(row.get("chain_position", -1))
        if not (span_view.after_chain_position < position <= span_view.high_water):
            outside.append(turn_id)
        elif turn_id not in span_by_id:
            outside.append(turn_id)
    if outside:
        return _reject("citation_outside_span", outside)

    cited_rows = [rows_by_id[turn_id] for turn_id in cited_ids]
    sealed = [
        str(row.get("turn_id", ""))
        for row in cited_rows
        if row.get("privacy_access") == "sealed_adjacent"
    ]
    if sealed:
        return _reject("privacy_sealed_row", sealed)

    if span_view.anchor_chain_position is None:
        return _reject("lived_status_unanchored", cited_ids)
    unanchored = [
        str(row.get("turn_id", ""))
        for row in cited_rows
        if int(row.get("chain_position", -1)) < span_view.anchor_chain_position
    ]
    if unanchored:
        return _reject("lived_status_unanchored", unanchored)

    cited_taint = set().union(*(_row_taint_labels(row) for row in cited_rows))
    artifact_taint = set(_canonical_label_tuple(_artifact_taint_labels(artifact)))
    missing_labels = cited_taint - artifact_taint
    if missing_labels:
        return _reject(
            "taint_not_inherited",
            _ids_for_taint_miss(cited_rows, missing_labels),
            _canonical_label_tuple(missing_labels),
        )

    return _accept()
