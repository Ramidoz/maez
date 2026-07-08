"""Conversational-consent ear interface and confirm-echo state machine."""

from __future__ import annotations

import base64
import secrets
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


SURFACING_TTL_SECONDS = 600.0
PRIMED_TTL_SECONDS = 3600.0
MAX_TOKEN_INSERT_ATTEMPTS = 16


def _default_spine_db_path() -> Path:
    from core.infra import paths

    return paths.memory_dir() / "consent" / "conversational_consent.sqlite3"


@dataclass(frozen=True)
class OwnerUtterance:
    surface_kind: str
    surface_identity: str
    text: str
    fresh: bool
    reply_to_ref: str | None
    at: str


@dataclass(frozen=True)
class ConsentIntent:
    kind: str
    card_hint: str | None
    confidence: float


@dataclass(frozen=True)
class ConsentFlowResult:
    state: str
    binding_id: str
    card_id: str | None = None
    echo_token: str | None = None
    decision: str | None = None
    refusal_code: str | None = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS consent_flows (
    binding_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    card_hint TEXT,
    decision TEXT,
    expires_at REAL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS consent_surfacing (
    surfacing_id TEXT PRIMARY KEY,
    binding_id TEXT NOT NULL,
    card_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    echo_token TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    resolved_at REAL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_consent_active_echo_token
ON consent_surfacing(echo_token)
WHERE state = 'ACTIVE';

CREATE INDEX IF NOT EXISTS idx_consent_surfacing_binding_state
ON consent_surfacing(binding_id, state, expires_at);
"""


def _default_token() -> str:
    return base64.b32encode(secrets.token_bytes(3)).decode("ascii")[:4]


def _card_id(card: object) -> str:
    return str(getattr(card, "request_id", "") or getattr(card, "id", "") or card)


def _card_text(card: object) -> str:
    pieces = [
        getattr(card, "request_id", ""),
        getattr(card, "action", ""),
        getattr(card, "proposed_action_summary", ""),
        getattr(card, "plain_english", ""),
        getattr(card, "reason", ""),
    ]
    return " ".join(str(piece or "") for piece in pieces).lower()


def _select_card(open_cards: Iterable[object], hint: str | None) -> tuple[object | None, str | None]:
    cards = list(open_cards or [])
    if not cards:
        return None, None
    clean_hint = (hint or "").strip().lower()
    if clean_hint:
        matches = [
            card
            for card in cards
            if clean_hint == _card_id(card).lower()
            or clean_hint in _card_id(card).lower()
            or clean_hint in _card_text(card)
        ]
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, "echo_ambiguous"
    if len(cards) == 1:
        return cards[0], None
    return None, "echo_ambiguous"


class ConsentSpineStore:
    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        token_generator: Callable[[], str] | None = None,
    ):
        self.db_path = Path(db_path) if db_path is not None else _default_spine_db_path()
        self.token_generator = token_generator or _default_token
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def active_flow_state(self, binding_id: str, *, now: float | None = None) -> str:
        now = float(now if now is not None else time.time())
        active = self._active_surfacing(binding_id, now=now)
        if active is not None:
            return "CARD_SURFACED"
        with closing(self._conn()) as conn:
            row = conn.execute(
                "SELECT state, expires_at FROM consent_flows WHERE binding_id = ?",
                (binding_id,),
            ).fetchone()
        if row is None:
            return "IDLE"
        expires_at = row["expires_at"]
        if expires_at is not None and float(expires_at) <= now:
            return "IDLE"
        return str(row["state"])

    def surface_card(
        self,
        *,
        binding_id: str,
        card_id: str,
        decision: str,
        now: float | None = None,
    ) -> ConsentFlowResult:
        now = float(now if now is not None else time.time())
        expires_at = now + SURFACING_TTL_SECONDS
        last_error: Exception | None = None
        for _ in range(MAX_TOKEN_INSERT_ATTEMPTS):
            token = str(self.token_generator()).strip().upper()
            surfacing_id = f"surf_{secrets.token_hex(12)}"
            try:
                with closing(self._conn()) as conn, conn:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute(
                        """
                        UPDATE consent_surfacing
                        SET state = 'EXPIRED'
                        WHERE binding_id = ? AND state = 'ACTIVE'
                        """,
                        (binding_id,),
                    )
                    conn.execute(
                        """
                        INSERT INTO consent_surfacing (
                            surfacing_id, binding_id, card_id, decision,
                            echo_token, state, created_at, expires_at, resolved_at
                        ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, NULL)
                        """,
                        (
                            surfacing_id,
                            binding_id,
                            card_id,
                            decision,
                            token,
                            now,
                            expires_at,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO consent_flows (
                            binding_id, state, card_hint, decision, expires_at, updated_at
                        ) VALUES (?, 'CARD_SURFACED', NULL, ?, ?, ?)
                        ON CONFLICT(binding_id) DO UPDATE SET
                            state = excluded.state,
                            card_hint = excluded.card_hint,
                            decision = excluded.decision,
                            expires_at = excluded.expires_at,
                            updated_at = excluded.updated_at
                        """,
                        (binding_id, decision, expires_at, now),
                    )
                return ConsentFlowResult(
                    state="CARD_SURFACED",
                    binding_id=binding_id,
                    card_id=card_id,
                    echo_token=token,
                    decision=decision,
                )
            except sqlite3.IntegrityError as exc:
                last_error = exc
                continue
        raise RuntimeError("could not generate unique consent echo token") from last_error

    def handle_turn(
        self,
        *,
        binding_id: str,
        utterance: OwnerUtterance,
        intent: ConsentIntent,
        open_cards: Iterable[object],
        now: float | None = None,
    ) -> ConsentFlowResult:
        now = float(now if now is not None else time.time())
        self._expire_stale(binding_id, now=now)
        active = self._latest_surfacing(binding_id)
        if (
            active is not None
            and active["state"] == "EXPIRED"
            and self._utterance_references_surfacing(utterance, intent, active)
        ):
            return ConsentFlowResult(
                state="IDLE",
                binding_id=binding_id,
                card_id=active["card_id"],
                echo_token=active["echo_token"],
                decision=active["decision"],
                refusal_code="echo_expired",
            )
        if active is not None and active["state"] == "ACTIVE":
            return self._handle_active_surfacing(
                binding_id=binding_id,
                utterance=utterance,
                intent=intent,
                row=active,
                now=now,
            )

        primed = self._primed_row(binding_id, now=now)
        if primed is not None:
            card, refusal = _select_card(open_cards, primed["card_hint"])
            if refusal:
                return ConsentFlowResult(
                    state="PRIMED",
                    binding_id=binding_id,
                    refusal_code=refusal,
                )
            if card is not None:
                return self.surface_card(
                    binding_id=binding_id,
                    card_id=_card_id(card),
                    decision=str(primed["decision"] or "approve"),
                    now=now,
                )

        if intent.kind == "standing_pre_consent":
            return self._prime(
                binding_id=binding_id,
                card_hint=intent.card_hint,
                decision="approve",
                now=now,
            )

        if intent.kind not in {"approve", "deny"}:
            return ConsentFlowResult(state="IDLE", binding_id=binding_id)
        if not utterance.fresh:
            return ConsentFlowResult(
                state="IDLE",
                binding_id=binding_id,
                refusal_code="utterance_not_fresh",
            )
        card, refusal = _select_card(open_cards, intent.card_hint)
        if refusal:
            return ConsentFlowResult(
                state="IDLE",
                binding_id=binding_id,
                refusal_code=refusal,
            )
        if card is None:
            return ConsentFlowResult(state="IDLE", binding_id=binding_id)
        return self.surface_card(
            binding_id=binding_id,
            card_id=_card_id(card),
            decision=intent.kind,
            now=now,
        )

    def mark_resolved(self, binding_id: str, *, now: float | None = None) -> None:
        now = float(now if now is not None else time.time())
        with closing(self._conn()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE consent_surfacing
                SET state = 'RESOLVED', resolved_at = ?
                WHERE binding_id = ? AND state = 'RESOLVING'
                """,
                (now, binding_id),
            )
            conn.execute(
                """
                UPDATE consent_flows
                SET state = 'RESOLVED', updated_at = ?
                WHERE binding_id = ?
                """,
                (now, binding_id),
            )

    def record_refusal(self, binding_id: str, reason: str, *, now: float | None = None) -> None:
        now = float(now if now is not None else time.time())
        with closing(self._conn()) as conn, conn:
            conn.execute(
                """
                INSERT INTO consent_flows (
                    binding_id, state, card_hint, decision, expires_at, updated_at
                ) VALUES (?, 'IDLE', ?, NULL, NULL, ?)
                ON CONFLICT(binding_id) DO UPDATE SET
                    state = 'IDLE',
                    card_hint = excluded.card_hint,
                    decision = excluded.decision,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (binding_id, reason, now),
            )

    def _prime(
        self,
        *,
        binding_id: str,
        card_hint: str | None,
        decision: str,
        now: float,
    ) -> ConsentFlowResult:
        expires_at = now + PRIMED_TTL_SECONDS
        with closing(self._conn()) as conn, conn:
            conn.execute(
                """
                INSERT INTO consent_flows (
                    binding_id, state, card_hint, decision, expires_at, updated_at
                ) VALUES (?, 'PRIMED', ?, ?, ?, ?)
                ON CONFLICT(binding_id) DO UPDATE SET
                    state = excluded.state,
                    card_hint = excluded.card_hint,
                    decision = excluded.decision,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (binding_id, card_hint, decision, expires_at, now),
            )
        return ConsentFlowResult(
            state="PRIMED",
            binding_id=binding_id,
            decision=decision,
        )

    def _handle_active_surfacing(
        self,
        *,
        binding_id: str,
        utterance: OwnerUtterance,
        intent: ConsentIntent,
        row: sqlite3.Row,
        now: float,
    ) -> ConsentFlowResult:
        if intent.kind not in {"approve", "deny"}:
            return ConsentFlowResult(
                state="CARD_SURFACED",
                binding_id=binding_id,
                card_id=row["card_id"],
                echo_token=row["echo_token"],
                decision=row["decision"],
            )
        if not utterance.fresh:
            return ConsentFlowResult(
                state="CARD_SURFACED",
                binding_id=binding_id,
                card_id=row["card_id"],
                echo_token=row["echo_token"],
                decision=row["decision"],
                refusal_code="utterance_not_fresh",
            )
        token = str(row["echo_token"])
        hinted = (intent.card_hint or "").strip().upper()
        reply_ref = (utterance.reply_to_ref or "").strip()
        if hinted != token and reply_ref not in {str(row["surfacing_id"]), str(row["card_id"])}:
            return ConsentFlowResult(
                state="CARD_SURFACED",
                binding_id=binding_id,
                card_id=row["card_id"],
                echo_token=token,
                decision=row["decision"],
                refusal_code="echo_ambiguous",
            )
        decision = intent.kind
        with closing(self._conn()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE consent_surfacing
                SET state = 'RESOLVING'
                WHERE surfacing_id = ? AND state = 'ACTIVE'
                """,
                (row["surfacing_id"],),
            )
            conn.execute(
                """
                UPDATE consent_flows
                SET state = 'RESOLVING', decision = ?, updated_at = ?
                WHERE binding_id = ?
                """,
                (decision, now, binding_id),
            )
        return ConsentFlowResult(
            state="RESOLVING",
            binding_id=binding_id,
            card_id=row["card_id"],
            echo_token=token,
            decision=decision,
        )

    def _utterance_references_surfacing(
        self,
        utterance: OwnerUtterance,
        intent: ConsentIntent,
        row: sqlite3.Row,
    ) -> bool:
        token = str(row["echo_token"])
        hinted = (intent.card_hint or "").strip().upper()
        reply_ref = (utterance.reply_to_ref or "").strip()
        return hinted == token or reply_ref in {str(row["surfacing_id"]), str(row["card_id"])}

    def _expire_stale(self, binding_id: str, *, now: float) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute(
                """
                UPDATE consent_surfacing
                SET state = 'EXPIRED'
                WHERE binding_id = ? AND state = 'ACTIVE' AND expires_at <= ?
                """,
                (binding_id, now),
            )
            conn.execute(
                """
                UPDATE consent_flows
                SET state = 'IDLE', updated_at = ?
                WHERE binding_id = ?
                  AND state IN ('PRIMED', 'CARD_SURFACED')
                  AND expires_at IS NOT NULL
                  AND expires_at <= ?
                """,
                (now, binding_id, now),
            )

    def _active_surfacing(self, binding_id: str, *, now: float) -> sqlite3.Row | None:
        with closing(self._conn()) as conn:
            return conn.execute(
                """
                SELECT *
                FROM consent_surfacing
                WHERE binding_id = ? AND state = 'ACTIVE' AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (binding_id, now),
            ).fetchone()

    def _latest_surfacing(self, binding_id: str) -> sqlite3.Row | None:
        with closing(self._conn()) as conn:
            return conn.execute(
                """
                SELECT *
                FROM consent_surfacing
                WHERE binding_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (binding_id,),
            ).fetchone()

    def _primed_row(self, binding_id: str, *, now: float) -> sqlite3.Row | None:
        with closing(self._conn()) as conn:
            return conn.execute(
                """
                SELECT *
                FROM consent_flows
                WHERE binding_id = ?
                  AND state = 'PRIMED'
                  AND expires_at > ?
                """,
                (binding_id, now),
            ).fetchone()
