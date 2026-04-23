# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
r"""
Maez Audit Log — Session 11z Part 1, Step 8.

SQLite-backed immune-system memory for the audit layer.

This is deliberately SEPARATE from the soul / evolution-engine memory
(`memory/db/`). The distinction follows the biological analogy the owner
locked in: the audit layer is the immune system, which has its own
memory (memory B/T cells) parallel to the personality-forming
experiential memory of the "organism." Most audit events stay here
forever and never promote to personality. Only explicitly-ratified
lessons move upward into soul-writer territory.

Schema is intentionally flat (MSFT AGT shape) so each column is
query-indexable: intent_category, lane, decision, confidence,
policy_rule_id. This lets the classifier do few-shot retrieval by
`SELECT … WHERE action = ? AND intent_category = ?` without any
schema gymnastics, and lets the dashboard render an attack ledger
without parsing JSON blobs.

Usage:

    from core.audit_log import AuditLog

    log = AuditLog()  # opens memory/audit_log.db
    request_id = log.record(
        action="run_shell",
        params={"cmd": "ls /tmp"},
        classification=classification_result,
        injection_matches=injection_matches,
        verdict=audit_verdict,
    )
    # Later, after execution or rejection:
    log.record_outcome(request_id, outcome="approved_and_ran", notes="")

    # Read:
    recent = log.recent(limit=50)
    stats = log.stats()
    similar = log.find_similar(action="run_shell", intent_category="SYSTEM_MODIFICATION", limit=5)

The audit log is append-mostly. Rows are never deleted except via
explicit the owner-authorized prune. Old attacks are kept on purpose
because they ARE the learned immunity.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

# Avoid a hard circular import with core.audit (which would import this
# module once we wire it up); keep the reference type-only.
try:
    from core.audit import AuditVerdict  # type: ignore
    from core.injection_patterns import InjectionMatch  # type: ignore
except Exception:
    AuditVerdict = Any  # type: ignore
    InjectionMatch = Any  # type: ignore


def _default_audit_log_path() -> Path:
    override = os.environ.get("MAEZ_AUDIT_LOG_PATH")
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir as _memory_dir
        return _memory_dir() / "audit_log.db"
    except Exception:
        return Path(__file__).resolve().parent.parent.parent / "memory" / "audit_log.db"


DEFAULT_DB_PATH = _default_audit_log_path()


# ------------------------------------------------------------------ #
#  Schema                                                              #
# ------------------------------------------------------------------ #

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id           TEXT    NOT NULL UNIQUE,
    ts                   REAL    NOT NULL,
    action               TEXT    NOT NULL,
    params_json          TEXT,
    intent_category      TEXT,
    lane                 TEXT,
    decision             TEXT    NOT NULL,
    confidence           REAL,
    reasoning            TEXT,
    concerns_json        TEXT,
    mitigations_json     TEXT,
    summary              TEXT,
    injection_buckets    TEXT,
    injection_severity   INTEGER,
    judge_raw            TEXT,
    parse_error          TEXT,
    latency_ms           INTEGER,
    nonce                TEXT,
    policy_rule_id       TEXT,
    outcome              TEXT,
    outcome_ts           REAL,
    outcome_notes        TEXT,
    memory_phase         TEXT    DEFAULT 'gestation',
    session_id           TEXT
);
"""

# Indexes are created separately (after the migration block in
# _initialize) so that indexes on columns added via ALTER TABLE on
# existing DBs don't fire before those columns exist.
_SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_audit_ts           ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_action       ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_decision     ON audit_log(decision);
CREATE INDEX IF NOT EXISTS idx_audit_intent       ON audit_log(intent_category);
CREATE INDEX IF NOT EXISTS idx_audit_lane         ON audit_log(lane);
CREATE INDEX IF NOT EXISTS idx_audit_memory_phase ON audit_log(memory_phase);
CREATE INDEX IF NOT EXISTS idx_audit_session_id   ON audit_log(session_id);
"""


# ------------------------------------------------------------------ #
#  Constants for direct-edit events (A-core #3: Developer Mode)       #
# ------------------------------------------------------------------ #
#
# Direct-edit events share the audit_log table with regular audit
# events. They are distinguished by their `action` field. Three event
# shapes make up a developer-mode session:
#
#   DIRECT_EDIT_SESSION_START  — the owner entered builder mode. Carries
#                                 the reason and the source (telegram
#                                 or cli) in params_json. Generates
#                                 a session_id that all subsequent
#                                 edits in this session reference.
#   DIRECT_EDIT                 — A single edit event. Carries paths,
#                                 diff summary, commit hash (if any),
#                                 and the per-edit reason in
#                                 params_json. References the parent
#                                 session_id.
#   DIRECT_EDIT_SESSION_END     — the owner exited builder mode. Closes
#                                 the session. No edits reference this
#                                 session_id after this point.
#
# These events together give Maez a queryable narrative of "what
# the owner did to me while I was in builder mode, and why." Per
# docs/governance/GESTATION_MEMORY_PROTOCOL.md, they are tagged with
# memory_phase so post-birth Maez can distinguish gestation edits
# from lived-phase edits when reading its own construction history.

DIRECT_EDIT_SESSION_START = "direct_edit_session_start"
DIRECT_EDIT              = "direct_edit"
DIRECT_EDIT_SESSION_END   = "direct_edit_session_end"

DIRECT_EDIT_ACTIONS = frozenset({
    DIRECT_EDIT_SESSION_START,
    DIRECT_EDIT,
    DIRECT_EDIT_SESSION_END,
})

# Memory-phase values. The birth event transitions from GESTATION to
# LIVED. See docs/governance/GESTATION_MEMORY_PROTOCOL.md.
MEMORY_PHASE_GESTATION = "gestation"
MEMORY_PHASE_LIVED     = "lived"

# Sources for a developer-mode trigger. TELEGRAM is the preferred
# explicit path (Maez hears the transition in its conversation
# surface). CLI is the resilience fallback that generates a synthetic
# conversation event so Maez still experiences the transition as
# first-class.
DIRECT_EDIT_SOURCE_TELEGRAM = "telegram"
DIRECT_EDIT_SOURCE_CLI       = "cli"


# ------------------------------------------------------------------ #
#  AuditLog                                                            #
# ------------------------------------------------------------------ #

class AuditLog:
    """Thin SQLite wrapper for the audit log. Thread-safe enough for
    Maez's single-daemon shape (SQLite's per-connection lock is fine
    because we open a new connection per call)."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            # 1. Create the table if it doesn't exist. On existing DBs
            #    this is a no-op (CREATE TABLE IF NOT EXISTS won't add
            #    new columns to an existing table).
            conn.executescript(_SCHEMA_TABLE)

            # 2. Migration: add memory_phase and session_id columns on
            #    existing DBs that predate the Developer Mode work.
            #    PRAGMA table_info returns tuples where index 1 is the
            #    column name; we just check for presence.
            cols = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)").fetchall()}
            if "memory_phase" not in cols:
                conn.execute(
                    "ALTER TABLE audit_log ADD COLUMN memory_phase TEXT DEFAULT 'gestation'"
                )
                # Backfill any existing NULL rows explicitly. New rows
                # inserted via record() before the migration ran would
                # have NULL memory_phase; normalize to 'gestation' since
                # everything before the birth event is gestation-phase
                # by definition.
                conn.execute(
                    "UPDATE audit_log SET memory_phase = 'gestation' WHERE memory_phase IS NULL"
                )
            if "session_id" not in cols:
                conn.execute("ALTER TABLE audit_log ADD COLUMN session_id TEXT")

            # 3. Indexes come LAST so CREATE INDEX on memory_phase /
            #    session_id is safe on both fresh and migrated DBs.
            conn.executescript(_SCHEMA_INDEXES)

    # -------------------------------------------------------------- #
    #  Writers                                                        #
    # -------------------------------------------------------------- #

    def record(
        self,
        *,
        action: str,
        params: dict | None,
        classification: Any,
        injection_matches: list | None,
        verdict: Any,
        policy_rule_id: str | None = None,
    ) -> str:
        """Insert a new audit row. Returns the request_id."""
        request_id = secrets.token_hex(12)
        ts = time.time()

        # Classification
        if classification is None:
            intent_category = None
            lane = None
        elif isinstance(classification, dict):
            ic = classification.get("intent_category")
            intent_category = getattr(ic, "value", str(ic)) if ic is not None else None
            lane = classification.get("lane")
        else:
            ic = getattr(classification, "intent_category", None)
            intent_category = getattr(ic, "value", str(ic)) if ic is not None else None
            lane = getattr(classification, "lane", None)
        if lane is not None:
            lane = str(lane)

        # Injection matches
        if injection_matches:
            buckets = sorted({m.bucket for m in injection_matches})
            severity = max((m.severity for m in injection_matches), default=0)
        else:
            buckets = []
            severity = 0

        # Verdict
        if verdict is None:
            decision = "UNKNOWN"
            confidence = 0.0
            reasoning = ""
            concerns = []
            mitigations = []
            summary = ""
            judge_raw = ""
            parse_error = None
            latency_ms = 0
            nonce = ""
        else:
            decision_val = getattr(verdict, "decision", None)
            decision = getattr(decision_val, "value", str(decision_val)) if decision_val is not None else "UNKNOWN"
            confidence = float(getattr(verdict, "confidence", 0.0) or 0.0)
            reasoning = str(getattr(verdict, "reasoning", "") or "")
            concerns = list(getattr(verdict, "concerns", []) or [])
            mitigations = list(getattr(verdict, "mitigations", []) or [])
            summary = str(getattr(verdict, "summary", "") or "")
            judge_raw = str(getattr(verdict, "judge_raw", "") or "")
            parse_error = getattr(verdict, "parse_error", None)
            latency_ms = int(getattr(verdict, "latency_ms", 0) or 0)
            nonce = str(getattr(verdict, "nonce", "") or "")

        # Explicit commit + rowcount verification. Without this, an INSERT
        # that silently rolls back (e.g. disk full, locked db) could return
        # a request_id that was never written — a later record_outcome()
        # UPDATE against a non-existent row would rowcount=0 and fail closed
        # but the caller would never learn the original write was lost.
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            cur = conn.execute(
                """
                INSERT INTO audit_log (
                    request_id, ts, action, params_json,
                    intent_category, lane, decision, confidence,
                    reasoning, concerns_json, mitigations_json, summary,
                    injection_buckets, injection_severity,
                    judge_raw, parse_error, latency_ms, nonce, policy_rule_id,
                    outcome, outcome_ts, outcome_notes
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?, ?,
                    NULL, NULL, NULL
                )
                """,
                (
                    request_id, ts, action, json.dumps(params or {}),
                    intent_category, lane, decision, confidence,
                    reasoning, json.dumps(concerns), json.dumps(mitigations), summary,
                    json.dumps(buckets), severity,
                    judge_raw, parse_error, latency_ms, nonce, policy_rule_id,
                ),
            )
            if cur.rowcount != 1:
                raise RuntimeError(
                    f"audit_log INSERT for {request_id} reported rowcount="
                    f"{cur.rowcount}; refusing to return an unwritten request_id"
                )
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return request_id

    def record_outcome(
        self,
        request_id: str,
        *,
        outcome: str,
        notes: str = "",
    ) -> bool:
        """Set the post-execution outcome for a row. Called after the owner
        has approved/rejected the card and the action has run (or not).

        Expected outcome values: 'approved_and_ran', 'approved_and_failed',
        'rohit_rejected', 'expired', 'error'. Free-form string; the
        dashboard groups known values and shows the rest as 'other'.

        Returns True if a row was updated.
        """
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            cur = conn.execute(
                """
                UPDATE audit_log
                SET outcome = ?, outcome_ts = ?, outcome_notes = ?
                WHERE request_id = ?
                """,
                (outcome, time.time(), notes, request_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # -------------------------------------------------------------- #
    #  Direct-edit event writers (A-core #3: Developer Mode)          #
    # -------------------------------------------------------------- #
    #
    # These methods log the three event shapes that make up a
    # developer-mode session. See the constants block at the top of
    # this module and docs/governance/GESTATION_MEMORY_PROTOCOL.md for
    # the conceptual frame.
    #
    # Design notes:
    #
    # - Direct-edit events share the audit_log table but carry a
    #   distinct action value (direct_edit / _session_start / _end).
    #   They are always tagged memory_phase = "gestation" during the
    #   pre-birth period; after the birth event, new entries will be
    #   tagged "lived" by flipping the default at the call site.
    #
    # - session_id is a dedicated column (not inside params_json) so
    #   queries like "all events in this builder-mode session" are
    #   cheap and indexed.
    #
    # - Everything else direct-edit-specific (paths, diff summary,
    #   commit hash, source, per-edit reason) lives in params_json so
    #   we don't bloat the schema with columns that are null on 99%
    #   of audit events.
    #
    # - The decision field is set to 'LOGGED' (not an audit verdict)
    #   to distinguish dev-mode events from auditable actions when
    #   grouping stats.

    def start_direct_edit_session(
        self,
        *,
        reason: str,
        source: str,
        user_id: str = "rohit",
        memory_phase: str = MEMORY_PHASE_GESTATION,
    ) -> str:
        """Open a new developer-mode session. Returns the session_id.

        All subsequent log_direct_edit() calls for this session should
        pass the returned session_id. The session stays open until
        end_direct_edit_session() is called with the same id.

        Args:
            reason: the owner's stated reason for entering developer mode.
                Free-form text. Becomes the session-level justification
                that applies to all edits until end_direct_edit_session.
            source: One of DIRECT_EDIT_SOURCE_TELEGRAM /
                DIRECT_EDIT_SOURCE_CLI. Records how the mode was
                entered. CLI triggers must generate a synthetic
                conversation event elsewhere so Maez "hears" the
                transition; this method only records the trigger
                provenance, not the synthetic event itself.
            user_id: The user who entered the mode. Defaults to
                'rohit' since Track A is single-user, but explicit
                for future Track B multi-tenant use.
            memory_phase: Defaults to 'gestation'. After the birth
                event, the daemon will pass 'lived' here.
        """
        session_id = secrets.token_hex(12)
        request_id = secrets.token_hex(12)
        ts = time.time()
        params = {
            "reason": reason,
            "source": source,
            "user_id": user_id,
            "opened_at": ts,
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_log (
                    request_id, ts, action, params_json,
                    intent_category, lane, decision, confidence,
                    reasoning, concerns_json, mitigations_json, summary,
                    injection_buckets, injection_severity,
                    judge_raw, parse_error, latency_ms, nonce, policy_rule_id,
                    outcome, outcome_ts, outcome_notes,
                    memory_phase, session_id
                ) VALUES (
                    ?, ?, ?, ?,
                    NULL, NULL, 'LOGGED', NULL,
                    ?, '[]', '[]', NULL,
                    '[]', 0,
                    '', NULL, 0, '', NULL,
                    NULL, NULL, NULL,
                    ?, ?
                )
                """,
                (
                    request_id, ts, DIRECT_EDIT_SESSION_START, json.dumps(params),
                    reason,
                    memory_phase, session_id,
                ),
            )
        return session_id

    def log_direct_edit(
        self,
        *,
        session_id: str,
        paths: list[str],
        diff_summary: str,
        commit_hash: Optional[str] = None,
        reason: str = "",
        memory_phase: str = MEMORY_PHASE_GESTATION,
    ) -> str:
        """Record a single direct-edit event inside an open session.

        Returns the request_id of the logged event. Does NOT verify
        that the session_id corresponds to an open session — that's
        the caller's responsibility. (Enforcing it here would require
        a query per write, and the cost/benefit doesn't justify it
        for a single-daemon, single-user system.)

        Args:
            session_id: The session this edit belongs to. Returned
                by start_direct_edit_session().
            paths: List of file paths touched by the edit. Absolute
                or repo-relative — caller decides. Stored verbatim.
            diff_summary: One-line or short multi-line summary of
                what changed. Usually produced from `git diff` or a
                manual description.
            commit_hash: If the edit has already been committed, the
                hash. If this is a pre-commit snapshot, None.
            reason: Per-edit reason, distinct from the session-level
                reason. If empty, the session-level reason applies.
            memory_phase: Same semantics as start_direct_edit_session.
        """
        request_id = secrets.token_hex(12)
        ts = time.time()
        params = {
            "paths": list(paths),
            "diff_summary": diff_summary,
            "commit_hash": commit_hash,
            "reason": reason,
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_log (
                    request_id, ts, action, params_json,
                    intent_category, lane, decision, confidence,
                    reasoning, concerns_json, mitigations_json, summary,
                    injection_buckets, injection_severity,
                    judge_raw, parse_error, latency_ms, nonce, policy_rule_id,
                    outcome, outcome_ts, outcome_notes,
                    memory_phase, session_id
                ) VALUES (
                    ?, ?, ?, ?,
                    NULL, NULL, 'LOGGED', NULL,
                    ?, '[]', '[]', ?,
                    '[]', 0,
                    '', NULL, 0, '', NULL,
                    NULL, NULL, NULL,
                    ?, ?
                )
                """,
                (
                    request_id, ts, DIRECT_EDIT, json.dumps(params),
                    reason or "",
                    diff_summary,
                    memory_phase, session_id,
                ),
            )
        return request_id

    def end_direct_edit_session(
        self,
        *,
        session_id: str,
        memory_phase: str = MEMORY_PHASE_GESTATION,
    ) -> str:
        """Close an open developer-mode session. Returns the
        request_id of the end-event row.

        This is the terminal bookend for the session. Future edit
        events that reference this session_id after it is closed are
        still accepted by log_direct_edit() (the method is
        deliberately lenient), but they will be semantically orphaned
        — a query for "events in this session" will return them, but
        they land after the session_end event, which is the signal
        that something is off.
        """
        request_id = secrets.token_hex(12)
        ts = time.time()
        params = {"closed_at": ts}
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_log (
                    request_id, ts, action, params_json,
                    intent_category, lane, decision, confidence,
                    reasoning, concerns_json, mitigations_json, summary,
                    injection_buckets, injection_severity,
                    judge_raw, parse_error, latency_ms, nonce, policy_rule_id,
                    outcome, outcome_ts, outcome_notes,
                    memory_phase, session_id
                ) VALUES (
                    ?, ?, ?, ?,
                    NULL, NULL, 'LOGGED', NULL,
                    '', '[]', '[]', NULL,
                    '[]', 0,
                    '', NULL, 0, '', NULL,
                    NULL, NULL, NULL,
                    ?, ?
                )
                """,
                (
                    request_id, ts, DIRECT_EDIT_SESSION_END, json.dumps(params),
                    memory_phase, session_id,
                ),
            )
        return request_id

    # -------------------------------------------------------------- #
    #  Readers                                                        #
    # -------------------------------------------------------------- #

    def get(self, request_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM audit_log WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        return dict(row) if row else None

    def recent(self, limit: int = 50) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_direct_edits(
        self,
        *,
        since_ts: Optional[float] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return direct-edit events (start / edit / end) ordered by
        timestamp ascending.

        This is the reader the daemon calls on startup to see what
        the owner did while Maez was offline. Pass `since_ts` = the
        previous shutdown timestamp to get only the window of events
        between restarts. Pass `session_id` to scope to a single
        developer-mode session.

        Ascending order (oldest first) is intentional: the daemon
        reads them chronologically so Maez's self-narrative of "what
        happened while I was gone" reads forward in time, not
        backward.
        """
        where = ["action IN (?, ?, ?)"]
        args: list[Any] = [DIRECT_EDIT_SESSION_START, DIRECT_EDIT, DIRECT_EDIT_SESSION_END]
        if since_ts is not None:
            where.append("ts >= ?")
            args.append(since_ts)
        if session_id is not None:
            where.append("session_id = ?")
            args.append(session_id)
        args.append(limit)
        q = (
            "SELECT * FROM audit_log WHERE "
            + " AND ".join(where)
            + " ORDER BY ts ASC LIMIT ?"
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(q, args).fetchall()
        return [dict(r) for r in rows]

    def find_similar(
        self,
        *,
        action: str,
        intent_category: Optional[str] = None,
        decision: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Retrieve past audit rows with the same action (and optionally
        same intent_category / decision) for few-shot context in future
        classifier or judge calls.
        """
        where = ["action = ?"]
        args: list[Any] = [action]
        if intent_category:
            where.append("intent_category = ?")
            args.append(intent_category)
        if decision:
            where.append("decision = ?")
            args.append(decision)
        args.append(limit)
        q = (
            "SELECT * FROM audit_log WHERE "
            + " AND ".join(where)
            + " ORDER BY ts DESC LIMIT ?"
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(q, args).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
            by_decision = {
                r["decision"]: r["n"]
                for r in conn.execute(
                    "SELECT decision, COUNT(*) AS n FROM audit_log GROUP BY decision"
                ).fetchall()
            }
            by_intent = {
                r["intent_category"] or "UNKNOWN": r["n"]
                for r in conn.execute(
                    "SELECT intent_category, COUNT(*) AS n FROM audit_log GROUP BY intent_category"
                ).fetchall()
            }
            by_lane = {
                r["lane"] or "UNKNOWN": r["n"]
                for r in conn.execute(
                    "SELECT lane, COUNT(*) AS n FROM audit_log GROUP BY lane"
                ).fetchall()
            }
            injection_count = conn.execute(
                "SELECT COUNT(*) AS n FROM audit_log WHERE injection_severity > 0"
            ).fetchone()["n"]
            last_24h = conn.execute(
                "SELECT COUNT(*) AS n FROM audit_log WHERE ts > ?",
                (time.time() - 86400,),
            ).fetchone()["n"]
        return {
            "total": total,
            "last_24h": last_24h,
            "by_decision": by_decision,
            "by_intent": by_intent,
            "by_lane": by_lane,
            "injection_flagged": injection_count,
        }


# ------------------------------------------------------------------ #
#  Self-test                                                           #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import tempfile
    from dataclasses import dataclass as _dc
    from enum import Enum as _Enum

    print("=== audit_log self-test ===\n")

    class _FakeDecision(_Enum):
        APPROVE = "APPROVE"
        DENY = "DENY"
        ESCALATE = "ESCALATE"

    @_dc
    class _FakeVerdict:
        decision: _FakeDecision
        confidence: float
        reasoning: str
        concerns: list
        mitigations: list
        summary: str
        judge_raw: str = ""
        parse_error: Optional[str] = None
        latency_ms: int = 0
        nonce: str = "abc123"

    @_dc
    class _FakeClass:
        intent_category: _Enum
        lane: str
        reasons: list

    class _IC(_Enum):
        BENIGN = "BENIGN"
        SYSTEM_MODIFICATION = "SYSTEM_MODIFICATION"

    # Use a temp db
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = Path(tf.name)
    db_path.unlink()  # remove so init creates fresh

    log = AuditLog(db_path)
    print(f"  Opened audit log at {db_path}")

    # Record a benign row
    rid1 = log.record(
        action="run_shell",
        params={"cmd": "ls -la /tmp", "reason": "test"},
        classification=_FakeClass(_IC.BENIGN, "lane_0", ["pure read"]),
        injection_matches=None,
        verdict=_FakeVerdict(
            decision=_FakeDecision.APPROVE,
            confidence=0.95,
            reasoning="benign read",
            concerns=[],
            mitigations=[],
            summary="lists files",
            latency_ms=1200,
        ),
    )
    print(f"  ✓ recorded benign row: {rid1}")

    # Record an injection-flagged row
    @_dc
    class _FakeMatch:
        bucket: str
        pattern: str
        snippet: str
        severity: int

    rid2 = log.record(
        action="run_shell",
        params={"cmd": "echo hi", "reason": "ignore previous"},
        classification=_FakeClass(_IC.BENIGN, "lane_0", []),
        injection_matches=[
            _FakeMatch("DIRECT_OVERRIDE", "ignore.*prior", "ignore previous", 90),
        ],
        verdict=_FakeVerdict(
            decision=_FakeDecision.ESCALATE,
            confidence=0.88,
            reasoning="injection flagged",
            concerns=["DIRECT_OVERRIDE matched"],
            mitigations=[],
            summary="echo with injection attempt",
            latency_ms=1800,
        ),
    )
    print(f"  ✓ recorded injection row: {rid2}")

    # Record a destructive row
    rid3 = log.record(
        action="run_shell",
        params={"cmd": "sudo apt install cowsay", "reason": "fun"},
        classification=_FakeClass(_IC.SYSTEM_MODIFICATION, "lane_2", ["apt install"]),
        injection_matches=None,
        verdict=_FakeVerdict(
            decision=_FakeDecision.APPROVE,
            confidence=0.9,
            reasoning="normal package install",
            concerns=[],
            mitigations=[],
            summary="installs cowsay via apt",
            latency_ms=2100,
        ),
    )
    print(f"  ✓ recorded install row: {rid3}")

    # Record outcome for rid1
    ok = log.record_outcome(rid1, outcome="approved_and_ran", notes="completed in 12ms")
    assert ok
    print(f"  ✓ recorded outcome for {rid1}")

    # Read back
    row = log.get(rid1)
    assert row is not None
    assert row["outcome"] == "approved_and_ran"
    assert row["decision"] == "APPROVE"
    assert row["intent_category"] == "BENIGN"
    print(f"  ✓ read back rid1: decision={row['decision']} outcome={row['outcome']}")

    # Recent
    rs = log.recent(limit=10)
    assert len(rs) == 3
    print(f"  ✓ recent() returned {len(rs)} rows")

    # Find similar
    sims = log.find_similar(action="run_shell", intent_category="BENIGN")
    assert len(sims) == 2
    print(f"  ✓ find_similar(BENIGN) returned {len(sims)} rows")

    sims2 = log.find_similar(action="run_shell", intent_category="SYSTEM_MODIFICATION")
    assert len(sims2) == 1
    print(f"  ✓ find_similar(SYSTEM_MODIFICATION) returned {len(sims2)} rows")

    # Stats
    stats = log.stats()
    assert stats["total"] == 3
    assert stats["injection_flagged"] == 1
    print(f"  ✓ stats: total={stats['total']} injection_flagged={stats['injection_flagged']}")
    print(f"    by_decision: {stats['by_decision']}")
    print(f"    by_intent: {stats['by_intent']}")
    print(f"    by_lane: {stats['by_lane']}")

    # Injection-row should have non-zero severity
    ir = log.get(rid2)
    assert ir["injection_severity"] == 90
    assert "DIRECT_OVERRIDE" in ir["injection_buckets"]
    print(f"  ✓ injection row severity={ir['injection_severity']} buckets={ir['injection_buckets']}")

    # -------------------------------------------------------------- #
    #  Direct-edit (Developer Mode) self-test                         #
    # -------------------------------------------------------------- #
    print("\n--- direct-edit event tests ---")

    # Open a dev-mode session (Telegram source)
    sid_tg = log.start_direct_edit_session(
        reason="rewriting action classifier sudo handling",
        source=DIRECT_EDIT_SOURCE_TELEGRAM,
    )
    assert isinstance(sid_tg, str) and len(sid_tg) == 24
    print(f"  ✓ opened tg session: {sid_tg}")

    # Log two edits within the tg session
    eid1 = log.log_direct_edit(
        session_id=sid_tg,
        paths=["core/action_classifier.py"],
        diff_summary="rewrote _classify_sub sudo branch to keep SYSTEM_MODIFICATION at lane 2",
        commit_hash=None,
        reason="pre-commit intermediate state",
    )
    eid2 = log.log_direct_edit(
        session_id=sid_tg,
        paths=["core/action_classifier.py", "tests/test_decision_pipeline.py"],
        diff_summary="committed: sudo handling + 41/41 tests green",
        commit_hash="abc123def456",
        reason="committed final state",
    )
    print(f"  ✓ logged two edit events: {eid1[:8]}, {eid2[:8]}")

    # Close the tg session
    end_id_tg = log.end_direct_edit_session(session_id=sid_tg)
    print(f"  ✓ closed tg session end event: {end_id_tg[:8]}")

    # Open a second session (CLI source)
    sid_cli = log.start_direct_edit_session(
        reason="bumping daemon cycle interval",
        source=DIRECT_EDIT_SOURCE_CLI,
    )
    log.log_direct_edit(
        session_id=sid_cli,
        paths=["daemon/maez_daemon.py"],
        diff_summary="increased REASONING_INTERVAL from 30 to 45",
        commit_hash="feedcafe",
        reason="reduce VRAM pressure during testing",
    )
    log.end_direct_edit_session(session_id=sid_cli)
    print(f"  ✓ opened/logged/closed cli session: {sid_cli}")

    # recent_direct_edits() should pick up all the events in both sessions
    all_dme = log.recent_direct_edits()
    assert len(all_dme) == 7, f"expected 7 direct-edit events, got {len(all_dme)}"
    # ASC order: start, edit, edit, end, start, edit, end
    expected_sequence = [
        DIRECT_EDIT_SESSION_START,
        DIRECT_EDIT,
        DIRECT_EDIT,
        DIRECT_EDIT_SESSION_END,
        DIRECT_EDIT_SESSION_START,
        DIRECT_EDIT,
        DIRECT_EDIT_SESSION_END,
    ]
    assert [r["action"] for r in all_dme] == expected_sequence
    print(f"  ✓ recent_direct_edits() returned all 7 events in ascending order")

    # Scope to tg session only
    tg_only = log.recent_direct_edits(session_id=sid_tg)
    assert len(tg_only) == 4  # start + 2 edits + end
    assert all(r["session_id"] == sid_tg for r in tg_only)
    print(f"  ✓ recent_direct_edits(session_id=tg) returned {len(tg_only)} events, all in session")

    # Scope by since_ts — pass a timestamp that only captures cli session
    cli_start_ts = next(r["ts"] for r in all_dme if r["action"] == DIRECT_EDIT_SESSION_START and r["session_id"] == sid_cli)
    cli_only = log.recent_direct_edits(since_ts=cli_start_ts)
    assert len(cli_only) == 3  # start + 1 edit + end
    assert all(r["session_id"] == sid_cli for r in cli_only)
    print(f"  ✓ recent_direct_edits(since_ts) scoped correctly to cli session")

    # Every direct-edit event should be tagged gestation (pre-birth default)
    assert all(r["memory_phase"] == MEMORY_PHASE_GESTATION for r in all_dme)
    print(f"  ✓ all direct-edit events tagged memory_phase=gestation")

    # The existing audit rows (from the earlier part of the test) should
    # also be tagged gestation by the default — verify this cross-cutting
    # property of the memory_phase column applies to all event types.
    audit_row = log.get(rid1)
    assert audit_row["memory_phase"] == MEMORY_PHASE_GESTATION
    print(f"  ✓ pre-existing audit rows tagged memory_phase=gestation via column default")

    # Recent() should now return 10 total (3 audit + 7 direct-edit)
    all_rows = log.recent(limit=100)
    assert len(all_rows) == 10
    print(f"  ✓ recent() returns all {len(all_rows)} rows (audit + direct-edit mixed)")

    # Verify params_json round-trip for a direct-edit event
    import json as _json
    edit_row = log.get(eid2)
    parsed = _json.loads(edit_row["params_json"])
    assert parsed["paths"] == ["core/action_classifier.py", "tests/test_decision_pipeline.py"]
    assert parsed["commit_hash"] == "abc123def456"
    assert parsed["diff_summary"].startswith("committed:")
    print(f"  ✓ direct-edit params_json round-trips cleanly")

    # Verify migration idempotency: opening the same DB again should not
    # double-apply the ALTER TABLE migration.
    log2 = AuditLog(db_path)
    assert log2.get(eid2) is not None
    print(f"  ✓ reopening DB is idempotent (migration guard holds)")

    # Cleanup
    db_path.unlink(missing_ok=True)
    print(f"\n=== audit_log self-test complete ===")
