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
from dataclasses import dataclass
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


DEFAULT_DB_PATH = Path(os.environ.get(
    "MAEZ_AUDIT_LOG_PATH",
    str(Path(__file__).resolve().parent.parent / "memory" / "audit_log.db"),
))


# ------------------------------------------------------------------ #
#  Schema                                                              #
# ------------------------------------------------------------------ #

_SCHEMA = """
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
    outcome_notes        TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_ts       ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_action   ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_log(decision);
CREATE INDEX IF NOT EXISTS idx_audit_intent   ON audit_log(intent_category);
CREATE INDEX IF NOT EXISTS idx_audit_lane     ON audit_log(lane);
"""


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
            conn.executescript(_SCHEMA)

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

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
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
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE audit_log
                SET outcome = ?, outcome_ts = ?, outcome_notes = ?
                WHERE request_id = ?
                """,
                (outcome, time.time(), notes, request_id),
            )
            return cur.rowcount > 0

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

    # Cleanup
    db_path.unlink(missing_ok=True)
    print(f"\n=== audit_log self-test complete ===")
