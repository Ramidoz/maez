# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Dormant consolidation-spine runtime for PHASE B2.

The runtime is callable-only. It is double-gated, lazily creates stores only
after the gates and idle predicate allow a run, emits content-light receipts
from committed re-reads, and writes only shadow artifacts in v0.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

from core.consolidation import citation_lock, digester, selector
from core.infra import paths as maez_paths
from core.infra.env_flags import strict_env_flag
from core.ledger import span_reader
from core.ledger.taint_stamping import TAINT_LABEL_ORDER
from core.ledger.writes_flag import ledger_writes_enabled

RECEIPTS_FILENAME = "consolidation_receipts.jsonl"
SPINE_DB_RELATIVE_PATH = Path("memory") / "consolidation" / "spine.sqlite3"
EPISODE_DIGESTS_DB_RELATIVE_PATH = (
    Path("memory") / "consolidation" / "episode_digests.sqlite3"
)
OUTCOME_COMMITTED = "committed"
OUTCOME_DEFERRED_SAME_SPAN = "deferred_same_span"
OUTCOME_DEAD_LETTER_SKELETON_ONLY = "dead_letter_skeleton_only"
_LOCK_REFUSAL_CODES = frozenset(citation_lock.REFUSAL_CODES)


@dataclass(frozen=True)
class ConsolidationPaths:
    ledger_db_path: Path
    spine_db_path: Path
    episode_digests_db_path: Path
    receipts_path: Path
    live_wonderings_db_path: Path | None = None


@dataclass(frozen=True)
class CommittedArtifact:
    receipt_id: str
    span_id: str
    episode_key: str
    digest_id: int
    start_chain_position: int
    end_chain_position: int
    row_count: int
    wondering_candidate_count: int


@dataclass(frozen=True)
class ConsolidationPassResult:
    status: str
    span_id: str = ""
    after_chain_position: int = -1
    high_water: int = -1
    row_count: int = 0
    artifacts_committed: int = 0
    refusals: tuple[dict[str, Any], ...] = ()


def default_paths() -> ConsolidationPaths:
    data = maez_paths.data_dir()
    return ConsolidationPaths(
        ledger_db_path=maez_paths.memory_dir() / "ledger.db",
        spine_db_path=data / SPINE_DB_RELATIVE_PATH,
        episode_digests_db_path=data / EPISODE_DIGESTS_DB_RELATIVE_PATH,
        receipts_path=maez_paths.logs_dir() / RECEIPTS_FILENAME,
        live_wonderings_db_path=maez_paths.wonderings_db(),
    )


def _json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _append_receipt(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_json(row))
        handle.write("\n")


def _shadow_enabled() -> bool:
    return strict_env_flag("MAEZ_CONSOLIDATION_SHADOW")


def _runtime_enabled() -> bool:
    return ledger_writes_enabled() and _shadow_enabled()


def _idle_allows_run(
    idle_inputs: Mapping[str, Any],
    *,
    min_idle_seconds: float,
) -> bool:
    if bool(idle_inputs.get("active_until_future")):
        return False
    if idle_inputs.get("camera") == "present_fresh":
        return False
    if idle_inputs.get("activity_known") is False:
        return False
    try:
        idle_for = float(idle_inputs.get("no_interaction_secs", 0.0) or 0.0)
    except (TypeError, ValueError):
        return False
    return idle_for >= min_idle_seconds


def _resolve_idle_inputs(
    *,
    idle_inputs: Mapping[str, Any] | None,
    daemon: object | None,
) -> Mapping[str, Any] | None:
    if idle_inputs is not None:
        return dict(idle_inputs)
    if daemon is None:
        return None
    from core.sensing.idle_window import idle_window_inputs as _idle_window_inputs

    return _idle_window_inputs(daemon)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _init_spine_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS spans (
            span_id TEXT PRIMARY KEY,
            after_chain_position INTEGER NOT NULL,
            high_water INTEGER NOT NULL,
            anchor_chain_position INTEGER NOT NULL,
            row_count INTEGER NOT NULL,
            selection_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS shadow_wondering_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            span_id TEXT NOT NULL,
            episode_key TEXT NOT NULL,
            candidate_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            row_citations_json TEXT NOT NULL,
            taint_labels_json TEXT NOT NULL,
            receipt_id TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'shadow',
            created_at REAL NOT NULL,
            UNIQUE(span_id, episode_key, candidate_index)
        );
        CREATE TABLE IF NOT EXISTS completed_artifacts (
            receipt_id TEXT PRIMARY KEY,
            span_id TEXT NOT NULL,
            episode_key TEXT NOT NULL,
            digest_id INTEGER NOT NULL,
            start_chain_position INTEGER NOT NULL,
            end_chain_position INTEGER NOT NULL,
            row_count INTEGER NOT NULL,
            wondering_candidate_count INTEGER NOT NULL,
            completed_at REAL NOT NULL,
            UNIQUE(span_id, episode_key)
        );
        CREATE TABLE IF NOT EXISTS episode_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            span_id TEXT NOT NULL,
            episode_key TEXT NOT NULL,
            start_chain_position INTEGER NOT NULL,
            end_chain_position INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            refusal_code TEXT NOT NULL DEFAULT '',
            refusal_detail TEXT NOT NULL DEFAULT '',
            attempt_count INTEGER NOT NULL,
            selection_depth TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            created_at REAL NOT NULL
        );
        """
    )
    conn.commit()
    return conn


def _init_digest_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS episode_digest_shadow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            span_id TEXT NOT NULL,
            episode_key TEXT NOT NULL,
            start_chain_position INTEGER NOT NULL,
            end_chain_position INTEGER NOT NULL,
            selection_depth TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            digest_text TEXT NOT NULL,
            row_citations_json TEXT NOT NULL,
            taint_labels_json TEXT NOT NULL,
            receipt_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(span_id, episode_key)
        );
        """
    )
    conn.commit()
    return conn


def _birth_anchor_chain_position(ledger_db_path: Path) -> int | None:
    if not ledger_db_path.exists():
        return None
    conn = sqlite3.connect(f"file:{ledger_db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key='birth_event_turn_id'"
        ).fetchone()
        if row is None or not str(row["value"] or "").strip():
            return None
        turn_id = str(row["value"])
        turn = conn.execute(
            "SELECT chain_position FROM turns WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()
        if turn is None:
            return None
        return int(turn["chain_position"])
    finally:
        conn.close()


def _state_value(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return None if row is None else str(row["value"])


def _set_state_value(conn: sqlite3.Connection, key: str, value: int | str) -> None:
    conn.execute(
        "INSERT INTO state(key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
        "updated_at=excluded.updated_at",
        (key, str(value), time.time()),
    )
    conn.commit()


def _last_digested_position(
    conn: sqlite3.Connection,
    *,
    anchor_chain_position: int,
) -> int:
    raw = _state_value(conn, "last_digested_chain_position")
    if raw is not None:
        return int(raw)
    initial = anchor_chain_position - 1
    _set_state_value(conn, "last_digested_chain_position", initial)
    return initial


def _max_completed_artifact_position(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT MAX(end_chain_position) AS max_pos FROM completed_artifacts"
    ).fetchone()
    if row is None or row["max_pos"] is None:
        return None
    return int(row["max_pos"])


def _record_span(
    conn: sqlite3.Connection,
    *,
    span_id: str,
    after_chain_position: int,
    high_water: int,
    anchor_chain_position: int,
    row_count: int,
    selection_mode: str,
    status: str,
) -> dict[str, Any]:
    now = time.time()
    conn.execute(
        """
        INSERT INTO spans (
            span_id, after_chain_position, high_water, anchor_chain_position,
            row_count, selection_mode, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(span_id) DO UPDATE SET
            row_count=excluded.row_count,
            selection_mode=excluded.selection_mode,
            status=excluded.status,
            updated_at=excluded.updated_at
        """,
        (
            span_id,
            after_chain_position,
            high_water,
            anchor_chain_position,
            row_count,
            selection_mode,
            status,
            now,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM spans WHERE span_id = ?", (span_id,)).fetchone()
    if row is None:
        raise RuntimeError("span re-read failed after commit")
    return dict(row)


def _span_receipt(row: Mapping[str, Any], *, event: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt_id": f"consolidation-span-{uuid4().hex}",
        "event": event,
        "status": status,
        "span_id": row["span_id"],
        "after_chain_position": int(row["after_chain_position"]),
        "high_water": int(row["high_water"]),
        "anchor_chain_position": int(row["anchor_chain_position"]),
        "row_count": int(row["row_count"]),
        "selection_mode": row["selection_mode"],
        "created_at": time.time(),
    }


def _refusal_receipt(
    span_row: Mapping[str, Any],
    *,
    event: str,
    refusal_code: str,
    episode_key: str = "",
    outcome: str = OUTCOME_DEFERRED_SAME_SPAN,
    attempt_count: int = 0,
    dead_letter: bool = False,
) -> dict[str, Any]:
    receipt = _span_receipt(span_row, event=event, status="refused")
    receipt["refusal_code"] = refusal_code
    receipt["outcome"] = outcome
    if attempt_count:
        receipt["attempt_count"] = int(attempt_count)
    if dead_letter:
        receipt["dead_letter"] = True
    if episode_key:
        receipt["episode_key"] = episode_key
    return receipt


def _rows_for_episode(
    rows: Iterable[Mapping[str, Any]],
    *,
    start_chain_position: int,
    end_chain_position: int,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in rows
        if start_chain_position <= int(row.get("chain_position", -1)) <= end_chain_position
    ]


def _ordered_taints_for_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    labels: set[str] = set()
    for row in rows:
        raw = row.get("taint_labels_json", "[]")
        try:
            parsed = json.loads(raw if isinstance(raw, str) else "[]")
        except json.JSONDecodeError:
            parsed = []
        labels.update(label for label in parsed if isinstance(label, str))
    return tuple(label for label in TAINT_LABEL_ORDER if label in labels)


def _public_lived_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    anchor_chain_position: int,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in rows
        if row.get("privacy_access") != "sealed_adjacent"
        and int(row.get("chain_position", -1)) >= anchor_chain_position
    ]


def _attempt_count_for_episode(
    conn: sqlite3.Connection,
    *,
    span_id: str,
    episode_key: str,
) -> int:
    row = conn.execute(
        "SELECT MAX(attempt_count) AS n FROM episode_outcomes "
        "WHERE span_id = ? AND episode_key = ?",
        (span_id, episode_key),
    ).fetchone()
    if row is None or row["n"] is None:
        return 0
    return int(row["n"])


def _attempt_counts_by_refusal_code(
    conn: sqlite3.Connection,
    *,
    span_id: str,
) -> dict[str, int]:
    rows = conn.execute(
        "SELECT refusal_code, MAX(attempt_count) AS n FROM episode_outcomes "
        "WHERE span_id = ? AND refusal_code != '' GROUP BY refusal_code",
        (span_id,),
    ).fetchall()
    return {
        str(row["refusal_code"]): int(row["n"])
        for row in rows
        if row["n"] is not None
    }


def _record_episode_outcome(
    conn: sqlite3.Connection,
    *,
    span_id: str,
    episode: Any,
    outcome: str,
    attempt_count: int,
    refusal_code: str = "",
    refusal_detail: str = "",
) -> dict[str, Any]:
    conn.execute(
        """
        INSERT INTO episode_outcomes (
            span_id, episode_key, start_chain_position, end_chain_position,
            outcome, refusal_code, refusal_detail, attempt_count,
            selection_depth, row_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            span_id,
            episode.episode_key,
            int(episode.start_chain_position),
            int(episode.end_chain_position),
            outcome,
            refusal_code,
            refusal_detail,
            int(attempt_count),
            str(episode.selection_depth),
            int(episode.row_count),
            time.time(),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM episode_outcomes WHERE id = last_insert_rowid()"
    ).fetchone()
    if row is None:
        raise RuntimeError("episode outcome re-read failed after commit")
    return dict(row)


def _dead_letter_skeleton(
    *,
    episode: Any,
    rows: list[dict[str, Any]],
    span: Mapping[str, Any],
    ledger_db_path: Path,
    refusal_code: str,
    call_count: int,
) -> tuple[Any, digester.DigestionResult]:
    citable_rows = _public_lived_rows(
        rows,
        anchor_chain_position=int(span["anchor_chain_position"]),
    )
    citations = tuple(
        {
            "turn_id": str(row.get("turn_id", "")),
            "chain_position": int(row.get("chain_position", -1)),
        }
        for row in citable_rows
        if str(row.get("turn_id", "")).strip()
    )
    shallow_episode = selector.EpisodeSelection(
        episode_key=episode.episode_key,
        start_chain_position=int(episode.start_chain_position),
        end_chain_position=int(episode.end_chain_position),
        turn_ids=tuple(str(row.get("turn_id", "")) for row in citable_rows),
        row_count=len(citations),
        selection_depth="shallow",
    )
    result = digester.DigestionResult(
        status="ok",
        episode_key=episode.episode_key,
        episode_digest=(
            "dead-letter skeleton: "
            f"episode={episode.episode_key}; "
            f"chain_positions={episode.start_chain_position}-{episode.end_chain_position}; "
            f"citable_rows={len(citations)}; "
            f"refusal_code={refusal_code}"
        ),
        row_citations=citations,
        taint_labels=_ordered_taints_for_rows(rows),
        wondering_candidates=(),
        call_count=call_count,
    )
    verdict = citation_lock.validate(
        {
            "episode_digest": result.episode_digest,
            "row_citations": list(result.row_citations),
            "taint_labels": list(result.taint_labels),
        },
        span,
        ledger_db_path,
    )
    if verdict.ok:
        return shallow_episode, result
    return shallow_episode, digester.DigestionResult(
        status="deferred",
        episode_key=episode.episode_key,
        refusal_code=verdict.refusal_code or "dead_letter_lock_refusal",
        refusal_detail=",".join(verdict.detail_codes),
        call_count=call_count,
    )


def _receipt_id_for_episode(span_id: str, episode_key: str) -> str:
    safe_episode = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in episode_key)
    return f"consolidation-{span_id}-{safe_episode}"


def _insert_digest(
    conn: sqlite3.Connection,
    *,
    span_id: str,
    episode: Any,
    result: digester.DigestionResult,
    receipt_id: str,
) -> int:
    conn.execute(
        """
        INSERT INTO episode_digest_shadow (
            span_id, episode_key, start_chain_position, end_chain_position,
            selection_depth, row_count, digest_text, row_citations_json,
            taint_labels_json, receipt_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(span_id, episode_key) DO UPDATE SET
            start_chain_position=excluded.start_chain_position,
            end_chain_position=excluded.end_chain_position,
            selection_depth=excluded.selection_depth,
            row_count=excluded.row_count,
            digest_text=excluded.digest_text,
            row_citations_json=excluded.row_citations_json,
            taint_labels_json=excluded.taint_labels_json,
            receipt_id=excluded.receipt_id,
            created_at=excluded.created_at
        """,
        (
            span_id,
            episode.episode_key,
            int(episode.start_chain_position),
            int(episode.end_chain_position),
            str(episode.selection_depth),
            int(episode.row_count),
            result.episode_digest,
            _json(list(result.row_citations)),
            _json(list(result.taint_labels)),
            receipt_id,
            time.time(),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM episode_digest_shadow WHERE span_id = ? AND episode_key = ?",
        (span_id, episode.episode_key),
    ).fetchone()
    if row is None:
        raise RuntimeError("episode digest re-read failed after commit")
    return int(row["id"])


def _insert_shadow_candidates(
    conn: sqlite3.Connection,
    *,
    span_id: str,
    episode_key: str,
    result: digester.DigestionResult,
    receipt_id: str,
) -> int:
    for index, candidate in enumerate(result.wondering_candidates):
        conn.execute(
            """
            INSERT INTO shadow_wondering_candidates (
                span_id, episode_key, candidate_index, text,
                row_citations_json, taint_labels_json, receipt_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(span_id, episode_key, candidate_index) DO UPDATE SET
                text=excluded.text,
                row_citations_json=excluded.row_citations_json,
                taint_labels_json=excluded.taint_labels_json,
                receipt_id=excluded.receipt_id,
                created_at=excluded.created_at
            """,
            (
                span_id,
                episode_key,
                index,
                candidate.text,
                _json(list(candidate.row_citations)),
                _json(list(candidate.taint_labels)),
                receipt_id,
                time.time(),
            ),
        )
    conn.commit()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM shadow_wondering_candidates "
        "WHERE span_id = ? AND episode_key = ?",
        (span_id, episode_key),
    ).fetchone()
    return 0 if row is None else int(row["n"])


def _commit_artifact(
    *,
    paths: ConsolidationPaths,
    spine_conn: sqlite3.Connection,
    span_id: str,
    episode: Any,
    result: digester.DigestionResult,
) -> CommittedArtifact:
    receipt_id = _receipt_id_for_episode(span_id, episode.episode_key)
    digest_conn = _init_digest_db(paths.episode_digests_db_path)
    try:
        digest_id = _insert_digest(
            digest_conn,
            span_id=span_id,
            episode=episode,
            result=result,
            receipt_id=receipt_id,
        )
    finally:
        digest_conn.close()
    candidate_count = _insert_shadow_candidates(
        spine_conn,
        span_id=span_id,
        episode_key=episode.episode_key,
        result=result,
        receipt_id=receipt_id,
    )
    return CommittedArtifact(
        receipt_id=receipt_id,
        span_id=span_id,
        episode_key=episode.episode_key,
        digest_id=digest_id,
        start_chain_position=int(episode.start_chain_position),
        end_chain_position=int(episode.end_chain_position),
        row_count=int(episode.row_count),
        wondering_candidate_count=candidate_count,
    )


def _artifact_receipt(committed: CommittedArtifact) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt_id": committed.receipt_id,
        "event": "episode_artifact_committed",
        "status": "committed",
        "span_id": committed.span_id,
        "episode_key": committed.episode_key,
        "digest_id": committed.digest_id,
        "start_chain_position": committed.start_chain_position,
        "end_chain_position": committed.end_chain_position,
        "row_count": committed.row_count,
        "wondering_candidate_count": committed.wondering_candidate_count,
        "created_at": time.time(),
    }


def _shadow_metrics_for_span(paths: ConsolidationPaths, span_id: str) -> dict[str, Any]:
    from core.consolidation.shadow_dashboard import build_shadow_metrics

    metrics = build_shadow_metrics(paths)
    for span_metrics in metrics.get("spans", []):
        if span_metrics.get("span_id") == span_id:
            return dict(span_metrics)
    return {}


def _receipt_already_emitted(path: Path, receipt_id: str) -> bool:
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("receipt_id") == receipt_id:
                    return True
    except OSError:
        return False
    return False


def _mark_artifact_complete(
    conn: sqlite3.Connection,
    committed: CommittedArtifact,
) -> CommittedArtifact:
    conn.execute(
        """
        INSERT INTO completed_artifacts (
            receipt_id, span_id, episode_key, digest_id, start_chain_position,
            end_chain_position, row_count, wondering_candidate_count, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(span_id, episode_key) DO UPDATE SET
            receipt_id=excluded.receipt_id,
            digest_id=excluded.digest_id,
            start_chain_position=excluded.start_chain_position,
            end_chain_position=excluded.end_chain_position,
            row_count=excluded.row_count,
            wondering_candidate_count=excluded.wondering_candidate_count,
            completed_at=excluded.completed_at
        """,
        (
            committed.receipt_id,
            committed.span_id,
            committed.episode_key,
            committed.digest_id,
            committed.start_chain_position,
            committed.end_chain_position,
            committed.row_count,
            committed.wondering_candidate_count,
            time.time(),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM completed_artifacts WHERE span_id = ? AND episode_key = ?",
        (committed.span_id, committed.episode_key),
    ).fetchone()
    if row is None:
        raise RuntimeError("completed artifact re-read failed after commit")
    return CommittedArtifact(
        receipt_id=str(row["receipt_id"]),
        span_id=str(row["span_id"]),
        episode_key=str(row["episode_key"]),
        digest_id=int(row["digest_id"]),
        start_chain_position=int(row["start_chain_position"]),
        end_chain_position=int(row["end_chain_position"]),
        row_count=int(row["row_count"]),
        wondering_candidate_count=int(row["wondering_candidate_count"]),
    )


def _window_open(window_still_open: Callable[[], bool] | None) -> bool:
    if window_still_open is None:
        return True
    return bool(window_still_open())


def _result(
    status: str,
    *,
    span_id: str = "",
    after_chain_position: int = -1,
    high_water: int = -1,
    row_count: int = 0,
    artifacts_committed: int = 0,
    refusals: Iterable[Mapping[str, Any]] = (),
) -> ConsolidationPassResult:
    return ConsolidationPassResult(
        status=status,
        span_id=span_id,
        after_chain_position=after_chain_position,
        high_water=high_water,
        row_count=row_count,
        artifacts_committed=artifacts_committed,
        refusals=tuple(
            {
                "episode_key": str(item.get("episode_key", "")),
                "refusal_code": str(item.get("refusal_code", "")),
                "outcome": str(item.get("outcome", "")),
                "attempt_count": int(item.get("attempt_count", 0) or 0),
            }
            for item in refusals
        ),
    )


def run_consolidation_pass(
    *,
    paths: ConsolidationPaths | None = None,
    idle_inputs: Mapping[str, Any] | None = None,
    daemon: object | None = None,
    llm_callable: Callable[..., Any] | None = None,
    endpoint_guard: Callable[[], Any] = digester.check_digestion_endpoint_locality,
    window_still_open: Callable[[], bool] | None = None,
    after_artifact_re_read: Callable[[CommittedArtifact], None] | None = None,
    min_idle_seconds: float = 30 * 60,
) -> ConsolidationPassResult:
    """Run one dormant shadow consolidation pass if both gates allow it."""
    if not _runtime_enabled():
        return _result("disabled")

    run_paths = paths or default_paths()
    observed_idle = _resolve_idle_inputs(idle_inputs=idle_inputs, daemon=daemon)
    if observed_idle is None or not _idle_allows_run(
        observed_idle,
        min_idle_seconds=min_idle_seconds,
    ):
        return _result("not_idle")

    # S1 §4: with phase truth enabled, a ledger the resolver cannot vouch
    # for gets a TYPED refusal of the whole span plan — the same shape as
    # the existing anchor-missing deferral, with its own code so a report
    # can tell "cleanly unborn" from "unreadable". Dormant behaviour is
    # untouched, including its failure modes: a broken ledger crashed the
    # pass before S1 and still does with the flag off, because preserving
    # legacy behaviour is what T5's dormancy proof measures.
    from core.memory import birth_phase as _bp
    if _bp.s1_enabled():
        try:
            _pr = _bp.resolve(run_paths.ledger_db_path)
        except _bp.LatchBlocked:
            # Found writing the positive control: an ANCHORED ledger with S1
            # enabled raises LatchBlocked from resolve() (§12.13), and my
            # first wiring let that crash the whole pass. The span planner
            # digests lived spans — it cannot proceed while lived cannot be
            # asserted — so this is a typed refusal, not an error.
            return _result(
                "deferred",
                refusals=({"episode_key": "",
                           "refusal_code": "phase_latch_blocked"},),
            )
        if _pr.phase == "unknown":
            return _result(
                "deferred",
                refusals=({"episode_key": "",
                           "refusal_code": f"phase_unknown_{_pr.reason}"},),
            )

    anchor = _birth_anchor_chain_position(run_paths.ledger_db_path)
    if anchor is None:
        return _result(
            "deferred",
            refusals=({"episode_key": "", "refusal_code": "birth_anchor_missing"},),
        )

    spine_conn = _init_spine_db(run_paths.spine_db_path)
    try:
        last = _last_digested_position(spine_conn, anchor_chain_position=anchor)
        committed_max = _max_completed_artifact_position(spine_conn)
        if committed_max is not None and committed_max > last:
            _set_state_value(spine_conn, "last_digested_chain_position", committed_max)
            last = committed_max

        span = span_reader.read_span(
            run_paths.ledger_db_path,
            after_chain_position=last,
        )
        span_id = f"span-cp{span.after_chain_position + 1}-cp{span.high_water}"
        selection = selector.select(span.rows)
        span_row = _record_span(
            spine_conn,
            span_id=span_id,
            after_chain_position=span.after_chain_position,
            high_water=span.high_water,
            anchor_chain_position=anchor,
            row_count=len(span.rows),
            selection_mode=selection.selection_mode,
            status="planned",
        )
        _append_receipt(
            run_paths.receipts_path,
            _span_receipt(span_row, event="span_planned", status="planned"),
        )

        if not span.rows:
            span_row = _record_span(
                spine_conn,
                span_id=span_id,
                after_chain_position=span.after_chain_position,
                high_water=span.high_water,
                anchor_chain_position=anchor,
                row_count=0,
                selection_mode=selection.selection_mode,
                status="empty",
            )
            receipt = _span_receipt(span_row, event="span_empty", status="empty")
            receipt["artifact_count"] = 0
            receipt["shadow_metrics"] = _shadow_metrics_for_span(run_paths, span_id)
            _append_receipt(run_paths.receipts_path, receipt)
            return _result(
                "empty",
                span_id=span_id,
                after_chain_position=span.after_chain_position,
                high_water=span.high_water,
            )

        artifacts = 0
        refusals: list[dict[str, Any]] = []
        prior_attempts_by_refusal_code = _attempt_counts_by_refusal_code(
            spine_conn,
            span_id=span_id,
        )
        span_view = {
            "after_chain_position": span.after_chain_position,
            "high_water": span.high_water,
            "anchor_chain_position": anchor,
            "rows": span.rows,
        }
        for episode in selection.episodes:
            if not _window_open(window_still_open):
                span_row = _record_span(
                    spine_conn,
                    span_id=span_id,
                    after_chain_position=span.after_chain_position,
                    high_water=span.high_water,
                    anchor_chain_position=anchor,
                    row_count=len(span.rows),
                    selection_mode=selection.selection_mode,
                    status="deferred",
                )
                _append_receipt(
                    run_paths.receipts_path,
                    {
                        **_span_receipt(
                            span_row,
                            event="span_deferred",
                            status="deferred",
                        ),
                        "shadow_metrics": _shadow_metrics_for_span(
                            run_paths,
                            span_id,
                        ),
                    },
                )
                return _result(
                    "deferred",
                    span_id=span_id,
                    after_chain_position=span.after_chain_position,
                    high_water=span.high_water,
                    row_count=len(span.rows),
                    artifacts_committed=artifacts,
                )

            episode_rows = _rows_for_episode(
                span.rows,
                start_chain_position=episode.start_chain_position,
                end_chain_position=episode.end_chain_position,
            )
            result = digester.digest_episode(
                episode,
                rows=episode_rows,
                span=span_view,
                ledger_db_path=run_paths.ledger_db_path,
                llm_callable=llm_callable,
                endpoint_guard=endpoint_guard,
            )
            if result.status != "ok":
                refusal_code = result.refusal_code or "digestion_refused"
                previous_episode_attempts = _attempt_count_for_episode(
                    spine_conn,
                    span_id=span_id,
                    episode_key=episode.episode_key,
                )
                if refusal_code in _LOCK_REFUSAL_CODES and previous_episode_attempts == 0:
                    attempt_count = (
                        prior_attempts_by_refusal_code.get(refusal_code, 0) + 1
                    )
                else:
                    attempt_count = previous_episode_attempts + 1
                if refusal_code in _LOCK_REFUSAL_CODES and attempt_count >= 2:
                    dead_episode, dead_result = _dead_letter_skeleton(
                        episode=episode,
                        rows=episode_rows,
                        span=span_view,
                        ledger_db_path=run_paths.ledger_db_path,
                        refusal_code=refusal_code,
                        call_count=result.call_count,
                    )
                    if dead_result.status == "ok":
                        committed = _commit_artifact(
                            paths=run_paths,
                            spine_conn=spine_conn,
                            span_id=span_id,
                            episode=dead_episode,
                            result=dead_result,
                        )
                        if not _receipt_already_emitted(
                            run_paths.receipts_path,
                            committed.receipt_id,
                        ):
                            _append_receipt(
                                run_paths.receipts_path,
                                _artifact_receipt(committed),
                            )
                        committed = _mark_artifact_complete(spine_conn, committed)
                        _record_episode_outcome(
                            spine_conn,
                            span_id=span_id,
                            episode=dead_episode,
                            outcome=OUTCOME_DEAD_LETTER_SKELETON_ONLY,
                            refusal_code=refusal_code,
                            refusal_detail=result.refusal_detail,
                            attempt_count=attempt_count,
                        )
                        span_row = _record_span(
                            spine_conn,
                            span_id=span_id,
                            after_chain_position=span.after_chain_position,
                            high_water=span.high_water,
                            anchor_chain_position=anchor,
                            row_count=len(span.rows),
                            selection_mode=selection.selection_mode,
                            status="planned",
                        )
                        _append_receipt(
                            run_paths.receipts_path,
                            _refusal_receipt(
                                span_row,
                                event="episode_refused",
                                refusal_code=refusal_code,
                                episode_key=episode.episode_key,
                                outcome=OUTCOME_DEAD_LETTER_SKELETON_ONLY,
                                attempt_count=attempt_count,
                                dead_letter=True,
                            ),
                        )
                        if after_artifact_re_read is not None:
                            after_artifact_re_read(committed)
                        _set_state_value(
                            spine_conn,
                            "last_digested_chain_position",
                            committed.end_chain_position,
                        )
                        artifacts += 1
                        result = dead_result
                    else:
                        refusal_code = dead_result.refusal_code or refusal_code

                if result.status != "ok":
                    outcome = OUTCOME_DEFERRED_SAME_SPAN
                    _record_episode_outcome(
                        spine_conn,
                        span_id=span_id,
                        episode=episode,
                        outcome=outcome,
                        refusal_code=refusal_code,
                        refusal_detail=result.refusal_detail,
                        attempt_count=attempt_count,
                    )
                    refusals.append(
                        {
                            "episode_key": episode.episode_key,
                            "refusal_code": refusal_code,
                            "outcome": outcome,
                            "attempt_count": attempt_count,
                        }
                    )
                    span_row = _record_span(
                        spine_conn,
                        span_id=span_id,
                        after_chain_position=span.after_chain_position,
                        high_water=span.high_water,
                        anchor_chain_position=anchor,
                        row_count=len(span.rows),
                        selection_mode=selection.selection_mode,
                        status="deferred",
                    )
                    receipt = _refusal_receipt(
                        span_row,
                        event="episode_refused",
                        refusal_code=refusal_code,
                        episode_key=episode.episode_key,
                        outcome=outcome,
                        attempt_count=attempt_count,
                    )
                    receipt["shadow_metrics"] = _shadow_metrics_for_span(
                        run_paths,
                        span_id,
                    )
                    _append_receipt(run_paths.receipts_path, receipt)
                    if artifacts > 0:
                        return _result(
                            "deferred",
                            span_id=span_id,
                            after_chain_position=span.after_chain_position,
                            high_water=span.high_water,
                            row_count=len(span.rows),
                            artifacts_committed=artifacts,
                            refusals=refusals,
                        )
                    return _result(
                        "deferred",
                        span_id=span_id,
                        after_chain_position=span.after_chain_position,
                        high_water=span.high_water,
                        row_count=len(span.rows),
                        artifacts_committed=artifacts,
                        refusals=refusals,
                    )
                else:
                    continue

            committed = _commit_artifact(
                paths=run_paths,
                spine_conn=spine_conn,
                span_id=span_id,
                episode=episode,
                result=result,
            )
            if not _receipt_already_emitted(run_paths.receipts_path, committed.receipt_id):
                _append_receipt(run_paths.receipts_path, _artifact_receipt(committed))
            committed = _mark_artifact_complete(spine_conn, committed)
            if after_artifact_re_read is not None:
                after_artifact_re_read(committed)
            attempt_count = _attempt_count_for_episode(
                spine_conn,
                span_id=span_id,
                episode_key=episode.episode_key,
            ) + 1
            _record_episode_outcome(
                spine_conn,
                span_id=span_id,
                episode=episode,
                outcome=OUTCOME_COMMITTED,
                attempt_count=attempt_count,
            )
            _set_state_value(
                spine_conn,
                "last_digested_chain_position",
                committed.end_chain_position,
            )
            artifacts += 1

            if not _window_open(window_still_open):
                span_row = _record_span(
                    spine_conn,
                    span_id=span_id,
                    after_chain_position=span.after_chain_position,
                    high_water=span.high_water,
                    anchor_chain_position=anchor,
                    row_count=len(span.rows),
                    selection_mode=selection.selection_mode,
                    status="deferred",
                )
                _append_receipt(
                    run_paths.receipts_path,
                    {
                        **_span_receipt(
                            span_row,
                            event="span_deferred",
                            status="deferred",
                        ),
                        "shadow_metrics": _shadow_metrics_for_span(
                            run_paths,
                            span_id,
                        ),
                    },
                )
                return _result(
                    "deferred",
                    span_id=span_id,
                    after_chain_position=span.after_chain_position,
                    high_water=span.high_water,
                    row_count=len(span.rows),
                    artifacts_committed=artifacts,
                )

        span_row = _record_span(
            spine_conn,
            span_id=span_id,
            after_chain_position=span.after_chain_position,
            high_water=span.high_water,
            anchor_chain_position=anchor,
            row_count=len(span.rows),
            selection_mode=selection.selection_mode,
            status="completed",
        )
        receipt = _span_receipt(span_row, event="span_completed", status="completed")
        receipt["artifact_count"] = artifacts
        receipt["shadow_metrics"] = _shadow_metrics_for_span(run_paths, span_id)
        _append_receipt(run_paths.receipts_path, receipt)
        return _result(
            "completed",
            span_id=span_id,
            after_chain_position=span.after_chain_position,
            high_water=span.high_water,
            row_count=len(span.rows),
            artifacts_committed=artifacts,
        )
    finally:
        spine_conn.close()
