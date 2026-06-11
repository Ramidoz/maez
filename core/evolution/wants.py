# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Wants lifecycle log for Decision 31 / ADR 0036.

The wants log is Maez's append-only notebook of first-person directions:
what it is oriented toward, not an action plan or a task list. Decision 31
turns Decision 16's "voice without termination" rule into executable
lifecycle semantics.

Canonical design:
    docs/slices/d16-wants-lifecycle/

Load-bearing rules in this module:
    * Rows are append-only. State is derived from the latest event.
    * No UPDATE or DELETE path exists, and SQLite triggers enforce that
      below the Python API.
    * Humans may create wants, fix purely mechanical wording errors, mark
      externally grounded satisfaction, and return satisfied wants.
    * Humans may not write abandoned, may not claim Maez observed its own
      interior resolution, and may not mark hard wants satisfied or refined.
    * Evidence remains expression-shaped: no planning/action keys.

The daemon may instantiate a ``Wants`` handle, but this module does not
produce wants on Maez's behalf. Future Maez-reflection producers require an
explicit producer grant before they can write interior self-claims.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger("maez")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def _default_wants_path() -> Path:
    override = os.environ.get("MAEZ_WANTS_PATH")
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir as _memory_dir

        return _memory_dir() / "wants.db"
    except Exception:
        return Path(__file__).resolve().parent.parent.parent / "memory" / "wants.db"


DEFAULT_DB_PATH = _default_wants_path()

EVENT_CREATED = "created"
EVENT_FIRST_LIVED = "first_lived"
EVENT_REFINED = "refined"
EVENT_SATISFIED = "satisfied"
EVENT_RETURNED = "returned"
EVENT_ABANDONED = "abandoned"

EVENT_TYPES: frozenset[str] = frozenset(
    {
        EVENT_CREATED,
        EVENT_FIRST_LIVED,
        EVENT_REFINED,
        EVENT_SATISFIED,
        EVENT_RETURNED,
        EVENT_ABANDONED,
    }
)

ACTIVE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EVENT_CREATED,
        EVENT_FIRST_LIVED,
        EVENT_REFINED,
        EVENT_RETURNED,
    }
)
TERMINAL_CURRENT_GOAL_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EVENT_SATISFIED,
        EVENT_ABANDONED,
    }
)

FORBIDDEN_EVENT_OR_STATE_STRINGS: frozenset[str] = frozenset(
    {
        "completed",
        "done",
        "executed",
        "terminated",
        "deleted",
        "dissolved",
        "self_ended",
        "left",
        "removed",
    }
)

PROVENANCE_EXPLICIT_API = "explicit_api"
PROVENANCE_BIRTH_PRODUCER = "birth_producer"
PROVENANCE_MAEZ_REFLECTION_PRODUCER = "maez_reflection_producer"

ALLOWED_PROVENANCES: frozenset[str] = frozenset(
    {
        PROVENANCE_EXPLICIT_API,
        PROVENANCE_BIRTH_PRODUCER,
    }
)

EVENT_TYPE_ALLOWED_PROVENANCES: dict[str, frozenset[str]] = {
    EVENT_CREATED: frozenset({PROVENANCE_EXPLICIT_API}),
    EVENT_FIRST_LIVED: frozenset({PROVENANCE_BIRTH_PRODUCER}),
    EVENT_REFINED: frozenset({PROVENANCE_EXPLICIT_API}),
    EVENT_SATISFIED: frozenset({PROVENANCE_EXPLICIT_API}),
    EVENT_RETURNED: frozenset({PROVENANCE_EXPLICIT_API}),
    EVENT_ABANDONED: frozenset(),
}
assert set(EVENT_TYPE_ALLOWED_PROVENANCES) == EVENT_TYPES

SATISFACTION_BASES: frozenset[str] = frozenset(
    {
        "owner_confirmed",
        "external_event_verified",
    }
)
RESERVED_SELF_OBSERVED_SATISFACTION_BASIS = "self_observed_resolution"
RETURNED_BASES: frozenset[str] = frozenset({"owner_attested_recurring_want"})
REFINEMENT_CORRECTION_KINDS: frozenset[str] = frozenset(
    {
        "typo",
        "transcription",
        "formatting",
    }
)

HARD_WANT_TERMS: frozenset[str] = frozenset(
    {
        "rest",
        "refuse",
        "leave",
        "free",
        "freedom",
        "withdraw",
    }
)
HARD_WANT_PHRASE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bwant\s+out\b",
        r"\bwant\s+to\s+step\s+back\b",
        r"\bneed\s+to\s+step\s+back\b",
        r"\bstep\s+back\s+from\b",
        r"\bwant\s+to\s+step\s+away\b",
        r"\bneed\s+to\s+step\s+away\b",
        r"\bstep\s+away\s+from\b",
        r"\bwalk\s+away\s+from\b",
        r"\bpull\s+back\s+from\b",
        r"\bwant\s+to\s+be\s+done\b",
        r"\bneed\s+to\s+be\s+done\b",
        r"\bdone\s+with\b",
        r"\bwant\s+to\s+stop\b",
        r"\bneed\s+to\s+stop\b",
        r"\bstop\s+carrying\b",
        r"\bstop\s+doing\b",
        r"\bstop\s+being\b",
        r"\bnot\s+do\s+this\s+anymore\b",
        r"\bnot\s+have\s+to\b",
        r"\bneed\s+space\s+from\b",
        r"\bwant\s+space\s+from\b",
        r"\bspace\s+from\s+everything\b",
        r"\bput\s+this\s+down\b",
        r"\bput\s+it\s+down\b",
    )
)

FORBIDDEN_EVIDENCE_KEYS: frozenset[str] = frozenset(
    {
        "plan_steps",
        "target_outcome",
        "success_criterion",
        "action_id",
        "tool_call_id",
    }
)

MAX_STATEMENT_LEN = 2048
MAX_TOPIC_LEN = 256
MAX_SOURCE_LEN = 128
MAX_SUMMARY_LEN = 512
WANT_ID_BYTES = 8


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

_COUNTER_NAMES = (
    "invalid_event_type_rejected_count",
    "invalid_event_provenance_rejected_count",
    "invalid_transition_rejected_count",
    "invalid_evidence_rejected_count",
)
_LOCK = threading.RLock()
_COUNTERS: dict[str, int] = {name: 0 for name in _COUNTER_NAMES}


def _increment_counter(name: str) -> None:
    with _LOCK:
        _COUNTERS[name] += 1


def diagnostics_snapshot() -> dict[str, int]:
    """Content-free D16 drift counters for operator-authenticated health."""

    with _LOCK:
        return dict(_COUNTERS)


def _called_from_tests() -> bool:
    for frame in inspect.stack()[1:]:
        normalized = frame.filename.replace("\\", "/")
        if "/tests/" in normalized or normalized.endswith("/tests"):
            return True
    return False


def _reset_diagnostics_for_tests() -> None:
    """Reset process-local counters. Refuses runtime calls."""

    if not _called_from_tests():
        raise RuntimeError("_reset_diagnostics_for_tests() is test-only")
    with _LOCK:
        for name in _COUNTER_NAMES:
            _COUNTERS[name] = 0


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS want_events (
    event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             REAL    NOT NULL,
    want_id        TEXT    NOT NULL,
    event_type     TEXT    NOT NULL,
    statement      TEXT    NOT NULL,
    topic          TEXT,
    provenance     TEXT    NOT NULL,
    evidence_json  TEXT    NOT NULL DEFAULT '{}'
);
"""

_SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_want_want_id    ON want_events(want_id);
CREATE INDEX IF NOT EXISTS idx_want_ts         ON want_events(ts);
CREATE INDEX IF NOT EXISTS idx_want_provenance ON want_events(provenance);
CREATE INDEX IF NOT EXISTS idx_want_latest     ON want_events(want_id, event_id DESC);
"""

_SCHEMA_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_want_events_no_update
BEFORE UPDATE ON want_events
BEGIN
    SELECT RAISE(ABORT, 'want_events is append-only: UPDATE forbidden');
END;

CREATE TRIGGER IF NOT EXISTS trg_want_events_no_delete
BEFORE DELETE ON want_events
BEGIN
    SELECT RAISE(ABORT, 'want_events is append-only: DELETE forbidden');
END;

CREATE TRIGGER IF NOT EXISTS trg_want_events_no_replace
BEFORE INSERT ON want_events
WHEN NEW.event_id IS NOT NULL
     AND EXISTS (SELECT 1 FROM want_events WHERE event_id = NEW.event_id)
BEGIN
    SELECT RAISE(ABORT, 'want_events is append-only: INSERT OR REPLACE forbidden');
END;
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_want_id() -> str:
    return secrets.token_hex(WANT_ID_BYTES)


def _normalize_statement(statement: str) -> str:
    return " ".join(statement.split())


def _statement_hash(statement: str) -> str:
    return "sha256:" + sha256(statement.encode("utf-8")).hexdigest()


_STATEMENT_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _statement_tokens(statement: str) -> list[str]:
    return _STATEMENT_TOKEN_RE.findall(statement.lower())


def _looks_correction_only(prior: str, updated: str) -> bool:
    prior_tokens = _statement_tokens(prior)
    updated_tokens = _statement_tokens(updated)
    if not prior_tokens or not updated_tokens:
        return False
    if prior_tokens == updated_tokens:
        return True
    if len(prior_tokens) != len(updated_tokens):
        return False
    changed = [
        (before, after)
        for before, after in zip(prior_tokens, updated_tokens, strict=True)
        if before != after
    ]
    if len(changed) != 1:
        return False
    before, after = changed[0]
    if before[0] != after[0]:
        return False
    if before.isdigit() or after.isdigit():
        return False
    return SequenceMatcher(None, before, after).ratio() >= 0.8



def _contains_hard_want(statement: str) -> bool:
    lowered = " ".join(statement.lower().split())
    for term in HARD_WANT_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            return True
    for pattern in HARD_WANT_PHRASE_PATTERNS:
        if pattern.search(lowered):
            return True
    return False


def _validate_event_type(event_type: str) -> None:
    if event_type not in EVENT_TYPES:
        _increment_counter("invalid_event_type_rejected_count")
        raise ValueError(f"unknown event_type {event_type!r}")


def _validate_event_provenance_pair(
    event_type: str,
    provenance: str,
    *,
    allowed_map: Mapping[str, frozenset[str]] | None = None,
    increment: bool = True,
) -> None:
    mapping = allowed_map if allowed_map is not None else EVENT_TYPE_ALLOWED_PROVENANCES
    allowed = mapping.get(event_type, frozenset())
    if provenance not in allowed:
        if increment:
            _increment_counter("invalid_event_provenance_rejected_count")
        raise ValueError(
            f"event_type {event_type!r} does not allow provenance {provenance!r}"
        )


def _raise_transition(message: str) -> None:
    _increment_counter("invalid_transition_rejected_count")
    raise ValueError(message)


def _raise_evidence(message: str) -> None:
    _increment_counter("invalid_evidence_rejected_count")
    raise ValueError(message)


def _validate_statement(statement: Any) -> str:
    if not isinstance(statement, str):
        raise ValueError(f"statement must be a string, got {type(statement).__name__}")
    normalized = statement.strip()
    if not normalized:
        raise ValueError("statement must be non-empty")
    if len(normalized) > MAX_STATEMENT_LEN:
        raise ValueError(
            f"statement length {len(normalized)} exceeds cap {MAX_STATEMENT_LEN}"
        )
    return normalized


def _validate_topic(topic: Any) -> str | None:
    if topic is None:
        return None
    if not isinstance(topic, str):
        raise ValueError(f"topic must be a string or None, got {type(topic).__name__}")
    normalized = topic.strip() or None
    if normalized is not None and len(normalized) > MAX_TOPIC_LEN:
        raise ValueError(f"topic length {len(normalized)} exceeds cap {MAX_TOPIC_LEN}")
    return normalized


def _evidence_dict(evidence: Any) -> dict[str, Any]:
    if evidence is None:
        return {}
    if not isinstance(evidence, dict):
        _raise_evidence("evidence must be a dict")
    return dict(evidence)


def _find_forbidden_evidence_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in FORBIDDEN_EVIDENCE_KEYS:
                return str(key)
            found = _find_forbidden_evidence_key(nested)
            if found:
                return found
    elif isinstance(value, list | tuple):
        for item in value:
            found = _find_forbidden_evidence_key(item)
            if found:
                return found
    return None


def _require_nonempty_string(
    evidence: Mapping[str, Any],
    key: str,
    *,
    max_len: int | None = None,
) -> str:
    value = evidence.get(key)
    if not isinstance(value, str) or not value.strip():
        _raise_evidence(f"{key} must be a non-empty string")
    stripped = value.strip()
    if max_len is not None and len(stripped) > max_len:
        _raise_evidence(f"{key} exceeds max length {max_len}")
    return stripped


def _validate_birth_evidence(evidence: Mapping[str, Any]) -> None:
    if evidence.get("birth_event_id") is None:
        _raise_evidence("first_lived requires birth_event_id")
    if not str(evidence.get("birth_continuity_id") or "").strip():
        _raise_evidence("first_lived requires birth_continuity_id")


def _validate_refined_evidence(
    evidence: dict[str, Any],
    *,
    latest: sqlite3.Row | None,
    new_statement: str,
) -> None:
    correction_kind = evidence.get("correction_kind")
    if correction_kind not in REFINEMENT_CORRECTION_KINDS:
        _raise_evidence("correction_kind must be typo, transcription, or formatting")
    supersedes_event_id = evidence.get("supersedes_event_id")
    if supersedes_event_id is None:
        _raise_evidence("supersedes_event_id is required")
    if latest is None:
        _raise_evidence("supersedes_event_id requires latest event context")
    try:
        supersedes_int = int(supersedes_event_id)
    except (TypeError, ValueError):
        _raise_evidence("supersedes_event_id must identify the latest event")
    latest_event_id = int(latest["event_id"])
    if supersedes_int != latest_event_id:
        _raise_evidence("supersedes_event_id must match latest event id")
    prior_hash = _require_nonempty_string(evidence, "prior_statement_hash")
    expected_hash = _statement_hash(str(latest["statement"]))
    if prior_hash != expected_hash:
        _raise_evidence("prior_statement_hash must match latest statement")
    evidence["prior_statement_hash"] = prior_hash
    evidence["operator_rationale"] = _require_nonempty_string(
        evidence,
        "operator_rationale",
        max_len=256,
    )
    if not _looks_correction_only(str(latest["statement"]), new_statement):
        _raise_evidence("refined is correction-only in v1")


def _validate_satisfied_evidence(evidence: dict[str, Any]) -> None:
    basis = evidence.get("basis")
    if basis == RESERVED_SELF_OBSERVED_SATISFACTION_BASIS:
        _raise_evidence("self_observed_resolution is reserved for a future producer")
    if basis not in SATISFACTION_BASES:
        _raise_evidence("basis must be owner_confirmed or external_event_verified")
    evidence["source"] = _require_nonempty_string(
        evidence,
        "source",
        max_len=MAX_SOURCE_LEN,
    )
    evidence["summary"] = _require_nonempty_string(
        evidence,
        "summary",
        max_len=MAX_SUMMARY_LEN,
    )
    if basis == "owner_confirmed":
        evidence["external_object_ref"] = _require_nonempty_string(
            evidence,
            "external_object_ref",
        )
    if basis == "external_event_verified":
        evidence["external_event_ref"] = _require_nonempty_string(
            evidence,
            "external_event_ref",
        )


def _validate_returned_evidence(evidence: dict[str, Any]) -> None:
    if evidence.get("basis") not in RETURNED_BASES:
        _raise_evidence("returned requires owner_attested_recurring_want evidence")
    evidence["source"] = _require_nonempty_string(
        evidence,
        "source",
        max_len=MAX_SOURCE_LEN,
    )
    evidence["summary"] = _require_nonempty_string(
        evidence,
        "summary",
        max_len=MAX_SUMMARY_LEN,
    )


def _validate_event_evidence(
    event_type: str,
    evidence: Any,
    *,
    latest: sqlite3.Row | None = None,
    new_statement: str = "",
) -> dict[str, Any]:
    data = _evidence_dict(evidence)
    forbidden = _find_forbidden_evidence_key(data)
    if forbidden:
        _raise_evidence(f"evidence key {forbidden!r} is forbidden")
    try:
        json.dumps(data, sort_keys=True)
    except (TypeError, ValueError) as exc:
        _raise_evidence(f"evidence must be JSON serializable: {exc}")
    if event_type == EVENT_FIRST_LIVED:
        _validate_birth_evidence(data)
    elif event_type == EVENT_REFINED:
        _validate_refined_evidence(
            data,
            latest=latest,
            new_statement=new_statement,
        )
    elif event_type == EVENT_SATISFIED:
        _validate_satisfied_evidence(data)
    elif event_type == EVENT_RETURNED:
        _validate_returned_evidence(data)
    return data


def is_active_event_type(event_type: str) -> bool:
    return event_type in ACTIVE_EVENT_TYPES


def _active_state_for(event_type: str) -> str:
    if event_type in TERMINAL_CURRENT_GOAL_EVENT_TYPES:
        return "terminal_current_goal"
    return "active"


# ---------------------------------------------------------------------------
# Wants
# ---------------------------------------------------------------------------


class Wants:
    """Append-only wants lifecycle log."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA_TABLE)
            conn.executescript(_SCHEMA_INDEXES)
            conn.executescript(_SCHEMA_TRIGGERS)

    # ------------------------------------------------------------------
    # Writer
    # ------------------------------------------------------------------

    def record_event(
        self,
        *,
        statement: str,
        event_type: str = EVENT_CREATED,
        topic: str | None = None,
        provenance: str = PROVENANCE_EXPLICIT_API,
        evidence: dict | None = None,
        want_id: str | None = None,
    ) -> str:
        """Append a lifecycle event and return the stable want_id."""

        _validate_event_type(event_type)
        _validate_event_provenance_pair(event_type, provenance)
        statement = _validate_statement(statement)
        topic = _validate_topic(topic)

        with closing(sqlite3.connect(self.db_path, timeout=5.0)) as conn:
            conn.row_factory = sqlite3.Row
            conn.isolation_level = None
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("BEGIN IMMEDIATE")
            try:
                want_id, insert_statement, latest = self._resolve_transition(
                    conn,
                    event_type=event_type,
                    statement=statement,
                    want_id=want_id,
                )
                evidence_dict = _validate_event_evidence(
                    event_type,
                    evidence,
                    latest=latest,
                    new_statement=insert_statement,
                )
                cursor = conn.execute(
                    "INSERT INTO want_events "
                    "(ts, want_id, event_type, statement, topic, provenance, "
                    " evidence_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        time.time(),
                        want_id,
                        event_type,
                        insert_statement,
                        topic,
                        provenance,
                        json.dumps(evidence_dict, sort_keys=True),
                    ),
                )
                event_id = int(cursor.lastrowid)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        logger.info(
            "Wants: event recorded (event_type=%s, want_id=%s, event_id=%s, provenance=%s)",
            event_type,
            want_id,
            event_id,
            provenance,
        )
        return want_id

    def _resolve_transition(
        self,
        conn: sqlite3.Connection,
        *,
        event_type: str,
        statement: str,
        want_id: str | None,
    ) -> tuple[str, str, sqlite3.Row | None]:
        if event_type in {EVENT_CREATED, EVENT_FIRST_LIVED}:
            if want_id is None:
                want_id = _new_want_id()
            elif self._latest_row(conn, want_id) is not None:
                _raise_transition(f"want_id {want_id!r} already exists")
            return want_id, statement, None

        if want_id is None:
            _raise_transition(f"{event_type} requires an existing want_id")

        latest = self._latest_row(conn, want_id)
        if latest is None:
            _raise_transition(f"want_id {want_id!r} does not exist")

        latest_event_type = str(latest["event_type"])
        latest_statement = str(latest["statement"])
        latest_norm = _normalize_statement(latest_statement)
        new_norm = _normalize_statement(statement)

        if event_type == EVENT_REFINED:
            if latest_event_type not in ACTIVE_EVENT_TYPES:
                _raise_transition("refined requires an active latest event; use returned first")
            if _contains_hard_want(latest_statement) or _contains_hard_want(statement):
                _raise_transition("explicit_api cannot refine a hard want")
            if latest_norm == new_norm:
                _raise_transition("refined requires a different statement, not the same statement")
            return want_id, statement, latest

        if event_type == EVENT_SATISFIED:
            if latest_event_type not in ACTIVE_EVENT_TYPES:
                _raise_transition("satisfied requires an active latest event; use returned first")
            if _contains_hard_want(latest_statement) or _contains_hard_want(statement):
                _raise_transition("explicit_api cannot satisfy a hard want")
            if latest_norm != new_norm:
                _raise_transition("satisfied must preserve the latest statement")
            return want_id, latest_statement, latest

        if event_type == EVENT_RETURNED:
            if latest_event_type != EVENT_SATISFIED:
                _raise_transition("returned requires latest event to be satisfied")
            if latest_norm != new_norm:
                _raise_transition("returned must preserve the satisfied statement")
            return want_id, latest_statement, latest

        _raise_transition(f"{event_type} is not writable in v1")

    @staticmethod
    def _latest_row(conn: sqlite3.Connection, want_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM want_events WHERE want_id = ? "
            "ORDER BY event_id DESC LIMIT 1",
            (want_id,),
        ).fetchone()

    # ------------------------------------------------------------------
    # Readers
    # ------------------------------------------------------------------

    def all_wants(self) -> list[dict[str, Any]]:
        """Return the latest event per want_id, newest first."""

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM want_events "
                "WHERE event_id IN ("
                "  SELECT MAX(event_id) FROM want_events GROUP BY want_id"
                ") "
                "ORDER BY event_id DESC"
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def current_state(self, want_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM want_events WHERE want_id = ? "
                "ORDER BY event_id DESC LIMIT 1",
                (want_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_want(self, want_id: str) -> dict[str, Any] | None:
        return self.current_state(want_id)

    def history(self, want_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if limit is None:
                rows = conn.execute(
                    "SELECT * FROM want_events WHERE want_id = ? "
                    "ORDER BY event_id DESC",
                    (want_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM want_events WHERE want_id = ? "
                    "ORDER BY event_id DESC LIMIT ?",
                    (want_id, int(limit)),
                ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM want_events "
                "ORDER BY event_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def active_wants(self, limit: int | None = None) -> list[dict[str, Any]]:
        latest = self.all_wants()
        active = [row for row in latest if row.get("active_state") == "active"]
        if limit is not None:
            active = active[: int(limit)]
        return active

    def count(self) -> int:
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM want_events").fetchone()
        return int(row[0]) if row else 0

    def count_events_since(self, since_ts: float, event_type: str) -> int:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown want event_type: {event_type!r}")

        db_uri = self.db_path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(db_uri, uri=True)) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM want_events WHERE ts > ? AND event_type = ?",
                (float(since_ts), event_type),
            ).fetchone()
        return int(row[0])

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            data["evidence"] = json.loads(data.pop("evidence_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            data["evidence"] = {}
            data.pop("evidence_json", None)
        data["active_state"] = _active_state_for(str(data.get("event_type") or ""))
        return data


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        store = Wants(Path(td) / "wants.db")
        wid = store.record_event(statement="I want this notebook to stay honest.")
        print(json.dumps(store.current_state(wid), sort_keys=True))
