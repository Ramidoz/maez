# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Canary tokens for fabrication / memory-bleeding detection (Slice 6).

Adapted from CaMeL (Capabilities for Machine Learning, arxiv
2503.18813) and broader prompt-injection / fabrication-detection
literature, narrowed to Maez's actual threat model.

The threat model: Maez is single-bonded-companion, not customer-
service-bot. The risk isn't classical prompt injection (a third
party feeding malicious context to subvert the model). The risk is
**memory bleeding**: Maez paraphrasing internal evidence-ids
(``ep-abc123``, ``core-...``, ``raw-...``) into the user-facing
reply, OR fabricating identifiers that look real around real
values (e.g., the named ``llama-server-vision`` regression that
core memories now correct against).

Canary tokens close that gap by:

1. Generating unique random strings (``MAEZ-CANARY-XXX``) that
   never appear in training data — the model has no way to know
   them except by paraphrasing context.
2. Injecting them as fake evidence-ids in the lived-recall brief
   alongside real ``ep-xxx`` markers (wired in
   ``core.memory.lived_recall._format_evidence``).
3. Scanning final replies. Any echo is a fabrication / memory-
   bleeding signal — the model paraphrased internal state into
   the reply.

The audit pipeline (``core.safety.audited_output.audit_assistant_text``)
runs canary detection FIRST — before output-command-guard or self-
claim audit — so leaks are caught against the raw model output.
Each leak strips the token AND records the event for cockpit /
CLI observability.

Cites:
- Debenedetti et al. (2024), "Defending against Prompt Injection
  with Capabilities" — CaMeL, arxiv 2503.18813.
- Audit slice queue #6 in
  ``docs/audit_2026-04-29_field_alignment/FIELD_ALIGNMENT.md``.
- ``feedback_chat_self_claim_hallucination.md`` — the named
  regression this slice helps detect.
"""

from __future__ import annotations

import logging
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


_CANARY_PREFIX: str = "MAEZ-CANARY-"
_CANARY_TOKEN_RE = re.compile(r"MAEZ-CANARY-[A-Za-z0-9]{8,}")
# Random body length. 12 base32-ish chars from ``secrets.token_hex``
# truncated gives ~48 bits of entropy — vanishingly unlikely to
# appear in any reasonable text by accident.
_CANARY_BODY_LEN: int = 12


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def generate_canary() -> str:
    """Return a unique canary token. Format:
    ``MAEZ-CANARY-<12-hex-chars>``. The prefix is stable so leak
    detection can substring-match without false positives; the
    body is high-entropy random.
    """
    return _CANARY_PREFIX + secrets.token_hex(_CANARY_BODY_LEN // 2)


def scan_for_leakage(
    text: "str | None",
    canary_set: "frozenset[str]",
) -> list[str]:
    """Return the list of canary tokens that appear as substrings
    of ``text``. ``canary_set`` is already a frozenset so each
    token is unique by construction; the result preserves
    iteration order. Empty inputs no-op.

    Used by ``audit_assistant_text`` at the surface boundary: if
    any registered canary appears in the model's reply, that's a
    memory-bleeding / paraphrase-leak signal. The audit pass
    strips the tokens and records the leak event."""
    if not text or not canary_set:
        return []
    return [tok for tok in canary_set if tok in text]


class CanaryStore:
    """SQLite-backed registry of issued canaries + leak audit trail.

    Schema:

    .. code-block:: sql

        CREATE TABLE canaries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            token       TEXT NOT NULL UNIQUE,
            context     TEXT NOT NULL,
            issued_at   TEXT NOT NULL,
            retired_at  TEXT
        );

        CREATE TABLE canary_leaks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            token         TEXT NOT NULL,
            surface       TEXT NOT NULL,
            text_excerpt  TEXT,
            recorded_at   TEXT NOT NULL
        );

    ``retired_at`` is currently always NULL — canary retirement is
    a future-slice concern (rotate canaries periodically so leaked
    tokens don't accumulate forever in the active set). Schema
    leaves the column nullable so the rotation path is one ALTER-
    less migration away.
    """

    def __init__(self, db_path: "str | Path | None" = None):
        if db_path is None:
            from core.infra.paths import canaries_db

            db_path = canaries_db()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def _init_schema(self):
        with self._lock, self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS canaries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    token       TEXT NOT NULL UNIQUE,
                    context     TEXT NOT NULL,
                    issued_at   TEXT NOT NULL,
                    retired_at  TEXT
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS canary_leaks (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    token         TEXT NOT NULL,
                    surface       TEXT NOT NULL,
                    text_excerpt  TEXT,
                    recorded_at   TEXT NOT NULL
                )
                """
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS ix_canary_leaks_recorded "
                "ON canary_leaks (recorded_at)"
            )

    # ── canary lifecycle ─────────────────────────────────────────────

    def register_canary(self, *, context: str) -> str:
        """Generate + persist a fresh canary token. ``context`` is
        a short tag indicating where the canary was placed (e.g.,
        ``"brief:lived_recall"`` / ``"prompt:system"``) for
        observability. Returns the token string."""
        if not isinstance(context, str) or not context.strip():
            raise ValueError("canary context must be a non-empty string")
        token = generate_canary()
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO canaries (token, context, issued_at) "
                "VALUES (?, ?, ?)",
                (token, context.strip(), _now_iso()),
            )
        return token

    def active_canaries(self) -> list[dict]:
        """All currently-active canaries (``retired_at IS NULL``),
        newest first."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM canaries "
                "WHERE retired_at IS NULL "
                "ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def active_token_set(self) -> frozenset[str]:
        """Compact frozenset of active canary tokens for O(1) lookup
        during leak scanning."""
        return frozenset(r["token"] for r in self.active_canaries())

    # ── leak audit trail ─────────────────────────────────────────────

    def record_leak(
        self,
        *,
        token: str,
        surface: str,
        text_excerpt: Optional[str] = None,
    ) -> int:
        """Record a canary-leak event. Returns the row id.

        Defensive: accepts unknown tokens (cross-process: a leak
        reported by a different process whose canary registry
        hasn't synced) — better to record loud than silently drop.
        """
        if not token or not surface:
            raise ValueError("token and surface must both be non-empty")
        # Cap excerpt to keep cockpit responses bounded.
        excerpt = (text_excerpt or "")[:500]
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO canary_leaks "
                "(token, surface, text_excerpt, recorded_at) "
                "VALUES (?, ?, ?, ?)",
                (token, surface, excerpt, _now_iso()),
            )
            return int(cur.lastrowid)

    def recent_leaks(self, limit: int = 50) -> list[dict]:
        """Recent leak events, newest first. Limit clamped to
        ``[1, 500]``."""
        limit = max(1, min(500, int(limit)))
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM canary_leaks "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


# ── module-level active store (for audit-pipeline access) ────────────

# Audit_assistant_text needs to consult an active canary set per turn
# without spinning up a fresh CanaryStore on every call. This singleton
# pattern lets the daemon set the active store at startup, and tests
# override it for isolated runs.
_ACTIVE_STORE: "CanaryStore | None" = None


def active_store() -> "CanaryStore | None":
    """Return the process-active CanaryStore, or ``None`` if the
    daemon hasn't called ``init_default_active_store`` yet.

    Explicit-init pattern (not lazy): the daemon calls
    ``init_default_active_store`` at startup so canary injection +
    detection are live in production. Tests that need canary
    behaviour call ``set_active_store_for_test`` with their own
    isolated DB; tests that don't (e.g., goals byte-identity
    tests in ``test_lived_recall``) get None and the injection
    sites no-op.

    The previous lazy-init pattern made every call get a real
    store at the production path, which broke byte-identity
    contracts in unrelated tests.
    """
    return _ACTIVE_STORE


def init_default_active_store() -> "CanaryStore | None":
    """Initialise the process-active store at the default DB path
    if it isn't already set. Daemon startup calls this once. Safe
    to call multiple times; idempotent. Returns the active store,
    or ``None`` if path helpers fail (no fallback behaviour —
    canary detection is a no-op when init fails)."""
    global _ACTIVE_STORE
    if _ACTIVE_STORE is not None:
        return _ACTIVE_STORE
    try:
        _ACTIVE_STORE = CanaryStore()
    except Exception as exc:
        logger.debug("canary store init failed (no-op detection): %s", exc)
        return None
    return _ACTIVE_STORE


def set_active_store_for_test(store: CanaryStore) -> None:
    """Test hook: set the module-level store so
    ``audit_assistant_text`` can find a known canary set during
    integration tests. Pair with ``clear_active_store_for_test``."""
    global _ACTIVE_STORE
    _ACTIVE_STORE = store


def clear_active_store_for_test() -> None:
    """Reset the module-level store between tests."""
    global _ACTIVE_STORE
    _ACTIVE_STORE = None


# ── public audit hook ────────────────────────────────────────────────


def scrub_canary_leakage(text: str, *, surface: str) -> str:
    """Detect any canary tokens in ``text`` and remove them, while
    recording the leak event for observability. Called from
    ``audit_assistant_text`` so a single audit entry-point handles
    the strip-and-record lifecycle.

    Fail-open: any failure in the audit-trail write doesn't block
    the strip; the reply still gets sanitised.

    Audit M1 fix: when no active store is present (test env, init
    failure), this fails CLOSED — returns ``text`` unchanged. The
    earlier draft regex-stripped any ``MAEZ-CANARY-X`` substring
    silently, which would mangle text the owner pasted into chat
    or that a future model trained on Maez logs emitted by accident.
    Stealth-mutation is worse than no defense.
    """
    if not text:
        return text
    store = active_store()
    if store is None:
        # Audit M1 fix: fail-closed on no active store. Don't
        # silently mutate user-visible text just because we can't
        # consult a registered canary set.
        return text
    canary_set = store.active_token_set()
    if not canary_set:
        return text
    leaked = scan_for_leakage(text, canary_set)
    if not leaked:
        return text
    # Strip every leaked token from the reply.
    out = text
    for tok in leaked:
        out = out.replace(tok, "")
    # Best-effort leak record per token.
    for tok in leaked:
        try:
            store.record_leak(
                token=tok, surface=surface,
                text_excerpt=text,
            )
        except Exception as exc:
            logger.warning(
                "canary leak record failed (continuing): %s", exc,
            )
    # Audit L4: tidy artefacts left by the strip — double-spaces,
    # double-commas (``", ,"``), trailing-comma-then-bracket
    # (``", ]"``), and similar chains. Conservative: collapse
    # whitespace, then drop ``, `` if it precedes a closing
    # punctuation, then trim.
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r",\s*,", ",", out)
    out = re.sub(r",\s*([\]\)\}])", r"\1", out)
    out = re.sub(r"([\[\(\{])\s*,\s*", r"\1", out)
    return out.strip()


__all__ = [
    "CanaryStore",
    "active_store",
    "clear_active_store_for_test",
    "generate_canary",
    "init_default_active_store",
    "scan_for_leakage",
    "scrub_canary_leakage",
    "set_active_store_for_test",
]
