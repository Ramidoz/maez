# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Routing observation flight recorder.

Slice 1 records what routing path handled a turn. It does not choose tools,
modify dispatcher specs, or alter synthesis prompts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import os
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from core.dispatcher.spec import (
    CompositionSpec,
    ExternalSource,
    SubstrateSource,
)


logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = _REPO_ROOT / "memory" / "routing_observation.db"
_SUBREDDIT_RE = re.compile(r"\br/[A-Za-z0-9_][A-Za-z0-9_]{1,20}\b", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


@dataclass(frozen=True)
class SpecMatch:
    score: float
    reason: str


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "value") and isinstance(value.value, str):
        return value.value
    return str(value)


def _source_values(values: Any) -> list[str]:
    if values is None:
        return []
    return [_enum_value(value) or "" for value in values]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def classify_utterance_shape(user_text: str) -> str:
    text = user_text or ""
    lowered = text.lower()
    if _SUBREDDIT_RE.search(text):
        return "contains_subreddit_anchor"
    if _URL_RE.search(text):
        return "contains_url"
    if any(token in lowered for token in ("remember", "recall", "talking about", "memory")):
        return "explicit_memory"
    if any(token in lowered for token in ("search", "look up", "latest", "right now", "news")):
        return "generic_fresh_lookup"
    return "unknown"


def compute_spec_match(
    *,
    spec: CompositionSpec | None,
    chosen_source: ExternalSource | SubstrateSource | str | None,
    chosen_tool: str | None,
    user_text: str,
    execution_status: str,
    legal_refusal: bool = False,
) -> SpecMatch:
    del execution_status
    if spec is None:
        return SpecMatch(0.0, "no_spec_available")
    if legal_refusal:
        return SpecMatch(1.0, "matched_legal_refusal")

    chosen_source_value = _enum_value(chosen_source)
    requested = set(_source_values(spec.substrate_sources)) | set(
        _source_values(spec.external_sources)
    )
    if chosen_source_value and chosen_source_value in requested:
        return SpecMatch(1.0, "matched_requested_source")

    shape = classify_utterance_shape(user_text)
    if (
        ExternalSource.LIVE_REDDIT in spec.external_sources
        and (chosen_tool or "") == "web_search"
        and shape == "contains_subreddit_anchor"
    ):
        return SpecMatch(0.5, "partial_legacy_equivalent")
    return SpecMatch(0.0, "ignored_requested_source")


class RoutingObservationStore:
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
                    CREATE TABLE IF NOT EXISTS routing_observations (
                        id TEXT PRIMARY KEY,
                        created_at REAL NOT NULL,
                        turn_id TEXT,
                        surface TEXT NOT NULL,
                        chat_id_hash TEXT,
                        utterance_hash TEXT NOT NULL,
                        utterance_shape TEXT NOT NULL,
                        path TEXT NOT NULL,
                        composition_hint TEXT,
                        provenance_framing TEXT,
                        substrate_sources_json TEXT NOT NULL,
                        external_sources_json TEXT NOT NULL,
                        source_availability_json TEXT NOT NULL,
                        availability_limitations_json TEXT NOT NULL,
                        chosen_source TEXT,
                        chosen_tool TEXT,
                        execution_status TEXT NOT NULL,
                        empty_reason TEXT,
                        error_class TEXT,
                        evidence_block_count INTEGER NOT NULL,
                        latency_ms REAL,
                        spec_match_score REAL NOT NULL,
                        spec_match_reason TEXT NOT NULL,
                        outcome_quality TEXT NOT NULL,
                        owner_feedback_kind TEXT,
                        owner_feedback_text TEXT,
                        owner_feedback_observed_at REAL,
                        producer_version TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_routing_observations_created_at "
                    "ON routing_observations(created_at)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_routing_observations_path_created "
                    "ON routing_observations(path, created_at)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_routing_observations_sources "
                    "ON routing_observations(chosen_source, chosen_tool)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_routing_observations_quality "
                    "ON routing_observations(outcome_quality, spec_match_score)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_routing_observations_shape "
                    "ON routing_observations(utterance_shape)"
                )
            # forward-only post-turn columns (added after v1 ship; nullable)
            existing = {
                r["name"]
                for r in conn.execute("PRAGMA table_info(routing_observations)").fetchall()
            }
            with conn:
                if "post_turn_signal" not in existing:
                    conn.execute("ALTER TABLE routing_observations ADD COLUMN post_turn_signal TEXT")
                for _col in ("request_class_id TEXT", "request_class_score REAL", "request_class_version TEXT"):
                    if _col.split()[0] not in existing:
                        conn.execute(f"ALTER TABLE routing_observations ADD COLUMN {_col}")

    def table_names(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        return {row["name"] for row in rows}

    def index_names(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        return {row["name"] for row in rows}

    def get(self, row_id: str) -> sqlite3.Row:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM routing_observations WHERE id = ?",
                (row_id,),
            ).fetchone()
        if row is None:
            raise KeyError(row_id)
        return row

    def attach_post_turn_quality(self, row_id, *, outcome_quality, post_turn_signal):
        """Post-synthesis write-back: revise outcome_quality + record the signal that
        caused it, keyed by the row id captured at insert. Silent no-op on unknown id /
        db error — this runs in the reply path and must NEVER raise."""
        try:
            with self._connect() as conn:
                with conn:
                    conn.execute(
                        "UPDATE routing_observations SET outcome_quality = ?, post_turn_signal = ? "
                        "WHERE id = ?",
                        (outcome_quality, post_turn_signal, row_id),
                    )
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("attach_post_turn_quality skipped (%s)", exc)

    def record_dispatcher_observation(
        self,
        *,
        user_text: str,
        surface: str,
        chat_id: str | None,
        spec: CompositionSpec,
        chosen_source: ExternalSource | SubstrateSource | str | None,
        chosen_tool: str | None,
        execution_status: str,
        evidence_block_count: int,
        spec_match_score: float,
        spec_match_reason: str,
        outcome_quality: str,
        latency_ms: float | None = None,
        turn_id: str | None = None,
        empty_reason: str | None = None,
        error_class: str | None = None,
        request_class_id: str | None = None,
        request_class_score: float | None = None,
        request_class_version: str | None = None,
    ) -> str:
        return self._record(
            user_text=user_text,
            surface=surface,
            chat_id=chat_id,
            path="dispatcher",
            spec=spec,
            chosen_source=chosen_source,
            chosen_tool=chosen_tool,
            execution_status=execution_status,
            evidence_block_count=evidence_block_count,
            spec_match_score=spec_match_score,
            spec_match_reason=spec_match_reason,
            outcome_quality=outcome_quality,
            latency_ms=latency_ms,
            turn_id=turn_id,
            empty_reason=empty_reason,
            error_class=error_class,
            request_class_id=request_class_id,
            request_class_score=request_class_score,
            request_class_version=request_class_version,
        )

    def record_legacy_web_search_observation(
        self,
        *,
        user_text: str,
        surface: str,
        chat_id: str | None,
        chosen_tool: str,
        execution_status: str,
        evidence_block_count: int,
        outcome_quality: str,
        latency_ms: float | None = None,
        turn_id: str | None = None,
        empty_reason: str | None = None,
        error_class: str | None = None,
        request_class_id: str | None = None,
        request_class_score: float | None = None,
        request_class_version: str | None = None,
    ) -> str:
        return self._record(
            user_text=user_text,
            surface=surface,
            chat_id=chat_id,
            path="legacy_daemon_web_search",
            spec=None,
            chosen_source=None,
            chosen_tool=chosen_tool,
            execution_status=execution_status,
            evidence_block_count=evidence_block_count,
            spec_match_score=0.0,
            spec_match_reason="no_spec_available",
            outcome_quality=outcome_quality,
            latency_ms=latency_ms,
            turn_id=turn_id,
            empty_reason=empty_reason,
            error_class=error_class,
            request_class_id=request_class_id,
            request_class_score=request_class_score,
            request_class_version=request_class_version,
        )

    def _record(
        self,
        *,
        user_text: str,
        surface: str,
        chat_id: str | None,
        path: str,
        spec: CompositionSpec | None,
        chosen_source: ExternalSource | SubstrateSource | str | None,
        chosen_tool: str | None,
        execution_status: str,
        evidence_block_count: int,
        spec_match_score: float,
        spec_match_reason: str,
        outcome_quality: str,
        latency_ms: float | None,
        turn_id: str | None,
        empty_reason: str | None,
        error_class: str | None,
        request_class_id: str | None = None,
        request_class_score: float | None = None,
        request_class_version: str | None = None,
    ) -> str:
        row_id = uuid.uuid4().hex
        source_availability = {}
        if spec is not None:
            source_availability = {
                _enum_value(source): _enum_value(availability)
                for source, availability in spec.source_availability.items()
            }
        row = {
            "id": row_id,
            "created_at": time.time(),
            "turn_id": turn_id,
            "surface": surface,
            "chat_id_hash": _sha256(chat_id) if chat_id else None,
            "utterance_hash": _sha256(user_text),
            "utterance_shape": classify_utterance_shape(user_text),
            "path": path,
            "composition_hint": _enum_value(spec.composition_hint) if spec else None,
            "provenance_framing": _enum_value(spec.provenance_framing) if spec else None,
            "substrate_sources_json": _json_dumps(_source_values(spec.substrate_sources) if spec else []),
            "external_sources_json": _json_dumps(_source_values(spec.external_sources) if spec else []),
            "source_availability_json": _json_dumps(source_availability),
            "availability_limitations_json": _json_dumps(
                _source_values(spec.availability_limitations) if spec else []
            ),
            "chosen_source": _enum_value(chosen_source),
            "chosen_tool": chosen_tool,
            "execution_status": execution_status,
            "empty_reason": empty_reason,
            "error_class": error_class,
            "evidence_block_count": int(evidence_block_count),
            "latency_ms": latency_ms,
            "spec_match_score": float(spec_match_score),
            "spec_match_reason": spec_match_reason,
            "outcome_quality": outcome_quality,
            "owner_feedback_kind": None,
            "owner_feedback_text": None,
            "owner_feedback_observed_at": None,
            "request_class_id": request_class_id,
            "request_class_score": request_class_score,
            "request_class_version": request_class_version,
            "producer_version": "routing_observation_v2",
        }
        columns = tuple(row.keys())
        placeholders = ", ".join("?" for _ in columns)
        with self._connect() as conn:
            with conn:
                conn.execute(
                    f"INSERT INTO routing_observations ({', '.join(columns)}) VALUES ({placeholders})",
                    tuple(row[column] for column in columns),
                )
        logger.info(
            "routing_observation path=%s source=%s tool=%s status=%s spec_match_score=%.3f outcome_quality=%s utterance_shape=%s",
            path,
            row["chosen_source"] or "",
            chosen_tool or "",
            execution_status,
            float(spec_match_score),
            outcome_quality,
            row["utterance_shape"],
        )
        return row_id


def _default_store() -> RoutingObservationStore:
    return RoutingObservationStore()


def _default_db_path() -> Path:
    override = os.environ.get("MAEZ_ROUTING_OBSERVATION_DB_PATH")
    if override:
        return Path(override)
    return DEFAULT_DB_PATH


def _branch_source(branch: Any) -> ExternalSource | SubstrateSource | str | None:
    return getattr(branch, "source", None)


def _status_value(value: Any) -> str:
    raw = _enum_value(value)
    return raw.lower() if raw else "unknown"


def _first_successful_source(layer1_result: Any, external_result: Any) -> ExternalSource | SubstrateSource | str | None:
    for result in (external_result, layer1_result):
        for branch in getattr(result, "branch_results", ()) or ():
            if _enum_value(getattr(branch, "status", None)) == "SUCCESS":
                return _branch_source(branch)
    for result in (external_result, layer1_result):
        for branch in getattr(result, "branch_results", ()) or ():
            return _branch_source(branch)
    return None


def _status_from_results(layer1_result: Any, external_result: Any, rendered_turn: Any) -> tuple[str, str | None, str | None]:
    refusal_reason = getattr(rendered_turn, "refusal_reason", None)
    if refusal_reason is not None:
        return _refusal_execution_status(refusal_reason), None, None
    statuses = [
        _enum_value(getattr(branch, "status", None))
        for result in (external_result, layer1_result)
        for branch in (getattr(result, "branch_results", ()) or ())
    ]
    if "SUCCESS" in statuses:
        return "success", None, None
    if "TIMEOUT" in statuses:
        return "timeout", None, None
    if "ERROR" in statuses:
        return "error", None, None
    if "PREFLIGHT_BLOCKED" in statuses:
        return "preflight_blocked", None, None
    if "RESERVED_UNAVAILABLE" in statuses:
        return "reserved_unavailable", None, None
    if "EMPTY" in statuses:
        empty_reason = None
        for result in (external_result, layer1_result):
            for branch in getattr(result, "branch_results", ()) or ():
                empty_reason = _enum_value(getattr(branch, "empty_reason", None))
                if empty_reason:
                    return "empty", empty_reason, None
        return "empty", None, None
    return "not_attempted", None, None


def _refusal_execution_status(refusal_reason: Any) -> str:
    reason = _enum_value(refusal_reason) or ""
    if reason == "RESERVED_SOURCE_EXECUTION_ATTEMPTED":
        return "reserved_skip"
    if reason in {
        "FRONTIER_CONSULT_WITHOUT_CAPABILITY_GRANT",
        "MODEL_INVENTED_URL",
    }:
        return "preflight_blocked"
    return "not_attempted"


def _outcome_quality(status: str, evidence_block_count: int) -> str:
    if evidence_block_count > 0:
        return "structured_evidence"
    if status in {"empty", "not_attempted"}:
        return "empty_but_honest"
    if status in {"error", "timeout", "preflight_blocked", "reserved_unavailable"}:
        return "tool_error"
    return "unknown"


def record_dispatcher_turn_observation(
    *,
    user_text: str,
    surface: str,
    chat_id: str | None,
    original_spec: CompositionSpec,
    effective_spec: CompositionSpec,
    layer1_result: Any,
    external_result: Any,
    rendered_turn: Any,
    turn_seal_state: str,
    elapsed_ms: float | None,
) -> str:
    del turn_seal_state
    chosen_source = _first_successful_source(layer1_result, external_result)
    chosen_tool = (_enum_value(chosen_source) or "dispatcher").lower()
    evidence_block_count = len(getattr(layer1_result, "recall_blocks", ()) or ()) + len(
        getattr(external_result, "fresh_blocks", ()) or ()
    )
    status, empty_reason, error_class = _status_from_results(
        layer1_result,
        external_result,
        rendered_turn,
    )
    legal_refusal = getattr(rendered_turn, "refusal_reason", None) is not None
    spec = effective_spec or original_spec
    match = compute_spec_match(
        spec=spec,
        chosen_source=chosen_source,
        chosen_tool=chosen_tool,
        user_text=user_text,
        execution_status=status,
        legal_refusal=legal_refusal,
    )
    return _default_store().record_dispatcher_observation(
        user_text=user_text,
        surface=surface,
        chat_id=chat_id,
        spec=spec,
        chosen_source=chosen_source,
        chosen_tool=chosen_tool,
        execution_status=status,
        evidence_block_count=evidence_block_count,
        spec_match_score=match.score,
        spec_match_reason=match.reason,
        outcome_quality=(
            "closed_refusal" if legal_refusal else _outcome_quality(status, evidence_block_count)
        ),
        latency_ms=elapsed_ms,
        empty_reason=empty_reason,
        error_class=error_class,
    )


def record_dispatcher_refusal_observation(
    *,
    user_text: str,
    surface: str,
    chat_id: str | None,
    spec: CompositionSpec,
    refusal_reason: Any,
    elapsed_ms: float | None,
) -> str:
    status = _refusal_execution_status(refusal_reason)
    match = compute_spec_match(
        spec=spec,
        chosen_source=None,
        chosen_tool=None,
        user_text=user_text,
        execution_status=status,
        legal_refusal=True,
    )
    return _default_store().record_dispatcher_observation(
        user_text=user_text,
        surface=surface,
        chat_id=chat_id,
        spec=spec,
        chosen_source=None,
        chosen_tool=None,
        execution_status=status,
        evidence_block_count=0,
        spec_match_score=match.score,
        spec_match_reason=match.reason,
        outcome_quality="closed_refusal",
        latency_ms=elapsed_ms,
    )


def record_legacy_web_search_observation(
    *,
    user_text: str,
    surface: str,
    chat_id: str | None = None,
    chosen_tool: str,
    execution_status: str,
    evidence_block_count: int,
    outcome_quality: str,
    latency_ms: float | None = None,
    empty_reason: str | None = None,
    error_class: str | None = None,
    request_class_id: str | None = None,
    request_class_score: float | None = None,
    request_class_version: str | None = None,
) -> str:
    return _default_store().record_legacy_web_search_observation(
        user_text=user_text,
        surface=surface,
        chat_id=chat_id,
        chosen_tool=chosen_tool,
        execution_status=execution_status,
        evidence_block_count=evidence_block_count,
        outcome_quality=outcome_quality,
        latency_ms=latency_ms,
        empty_reason=empty_reason,
        error_class=error_class,
        request_class_id=request_class_id,
        request_class_score=request_class_score,
        request_class_version=request_class_version,
    )
