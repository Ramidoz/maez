# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
wonderings.py — Maez's exploratory-mind state.

A wondering is an open question Maez is sitting with. The daemon picks
one per cycle (at most) and advances it with a single shell probe,
landing a learning that must be tied to real command output.

Invariant: no learning can exist in this store that isn't anchored to
a probe's stdout/stderr. See `validate_learning` for the enforcement
boundary. "(synthesis blocked — no concrete evidence tie)" is the
explicit stand-in when validation fails — it tells the reader that
Maez tried, couldn't ground, and did not fabricate.

Schema mirrors dream_state.py conventions (sqlite + RLock). Location
from core.paths.wonderings_db().
"""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from core import paths

logger = logging.getLogger("maez.wonderings")

# Fabrication-verb denylist — same phrases the SOUL admin-fabrication
# rule enumerates. A learning containing any of these is rejected.
_FABRICATION_VERBS = (
    r"i['’]ve\s+noted",
    r"i['’]ve\s+recorded",
    r"i['’]ve\s+registered",
    r"i['’]ve\s+updated",
    r"i['’]ve\s+saved",
    r"i['’]ve\s+appended",
    r"has\s+been\s+updated",
    r"has\s+been\s+recorded",
    r"has\s+been\s+saved",
    r"\bmanifest\b",          # the specific concept Maez kept inventing
)
_FABRICATION_RE = re.compile(
    "|".join(_FABRICATION_VERBS), re.IGNORECASE,
)

# Stop words — don't count as evidence overlap. Small list; leans
# toward false-accepts rather than false-rejects since the SOUL rules
# are the real fabrication gate, this is a cheap sanity check.
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "then", "of", "to",
    "in", "on", "at", "for", "with", "by", "from", "as", "is", "are",
    "was", "were", "be", "been", "being", "it", "this", "that", "these",
    "those", "i", "you", "he", "she", "we", "they", "them", "my", "your",
    "our", "their", "its", "no", "not", "yes", "do", "does", "did",
    "have", "has", "had", "will", "would", "can", "could", "should",
    "may", "might", "so", "because", "which", "who", "what", "when",
    "where", "how", "why", "while", "until", "against", "into", "out",
    "up", "down", "above", "below", "over", "under", "also", "than",
    "now", "just", "very", "only", "one", "two", "three",
    # common shell / log words that don't count as evidence
    "command", "output", "stdout", "stderr", "exit", "code",
})

# Sentinel learning strings (never synthesized — we write them by rule).
#
# Two failure modes for synthesis, kept distinct so telemetry can
# separate benign starvation from real fabrication attempts:
#
#   LEARNING_SYNTH_TIMEOUT  — we never ran the synthesis LLM call because
#                             the cycle budget was exhausted. No drift
#                             signal; just the primary-first invariant
#                             working.
#   LEARNING_SYNTH_BLOCKED  — we ran synthesis and validate_learning()
#                             rejected the result. This IS the drift
#                             signal: the LLM tried to assert something
#                             that doesn't appear in the real output.
LEARNING_NO_OUTPUT = "probe returned no output"
LEARNING_SYNTH_BLOCKED = "(synthesis blocked — no concrete evidence tie)"
LEARNING_SYNTH_TIMEOUT = "(synthesis skipped — no time left this cycle)"

# Deferrals-to-block threshold
DEFERRAL_BLOCK_THRESHOLD = 2


# ── helpers: evidence validation + excerpt ────────────────────────────
def stdout_excerpt(stdout: str, limit: int = 200) -> str:
    """Verbatim first N chars of stdout. Never reformatted, stored for
    audit. A reader can always check a learning against this."""
    if not stdout:
        return ""
    return stdout[:limit]


def _tokens(text: str) -> set[str]:
    """Tokenize into meaningful non-stop words for overlap checking.
    Lowercased, alphanumeric+underscore runs only, min-length 2."""
    if not text:
        return set()
    raw = re.findall(r"[a-zA-Z0-9_]{2,}", text.lower())
    return {t for t in raw if t not in _STOP_WORDS}


def validate_learning(
    learning: str,
    stdout: str,
    stderr: str,
    returncode: int,
) -> bool:
    """Return True if the learning is plausibly tied to its evidence.

    Rules, in order:
      1. Fabrication-verb denylist: reject if learning contains admin-
         fabrication phrases ("I've noted", "recorded", "manifest", etc.)
         regardless of evidence. Matches the SOUL admin-fabrication
         section; this is belt + suspenders.

      2. Empty-output case: if stdout and stderr are both effectively
         empty (and rc is 0), the ONLY accepted learning is the exact
         LEARNING_NO_OUTPUT sentinel. Anything more is invention.

      3. Token-overlap case: if there's real output, the learning must
         share at least 2 non-stopword tokens with stdout+stderr
         combined (case-insensitive, whole-token). This catches
         abstraction ("systemd is running" vs "systemd[1]: active")
         but blocks pure invention ("disk at 15%" when output said
         "RGB zones detected").
    """
    if not learning or not learning.strip():
        return False
    # Rule 1: fabrication verbs
    if _FABRICATION_RE.search(learning):
        return False
    # Rule 2: empty output
    combined = (stdout or "") + "\n" + (stderr or "")
    has_output = bool(combined.strip())
    if not has_output and returncode == 0:
        return learning.strip() == LEARNING_NO_OUTPUT
    # Rule 3: token overlap
    learn_tokens = _tokens(learning)
    evidence_tokens = _tokens(combined)
    if not learn_tokens or not evidence_tokens:
        return False
    overlap = learn_tokens & evidence_tokens
    return len(overlap) >= 2


# ── wonderings store ───────────────────────────────────────────────────
class Wonderings:
    """SQLite-backed store for open questions + their probe history."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else paths.wonderings_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init_schema(self):
        with self._lock, self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS wonderings (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at          REAL NOT NULL,
                    question            TEXT NOT NULL,
                    status              TEXT NOT NULL DEFAULT 'open',
                    advance_count       INTEGER NOT NULL DEFAULT 0,
                    deferral_count      INTEGER NOT NULL DEFAULT 0,
                    pending_card_id     INTEGER,
                    last_advanced       REAL,
                    source              TEXT,
                    conclusion          TEXT
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS wondering_probes (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    wondering_id            INTEGER NOT NULL
                                              REFERENCES wonderings(id),
                    created_at              REAL NOT NULL,
                    cmd                     TEXT NOT NULL,
                    stdout                  TEXT,
                    stderr                  TEXT,
                    stdout_excerpt          TEXT,
                    returncode              INTEGER,
                    learning                TEXT,
                    evidence_tied           INTEGER NOT NULL DEFAULT 0,
                    deferred                INTEGER NOT NULL DEFAULT 0,
                    pending_card_id         INTEGER,
                    resolved_from_card_at   REAL
                )
                """
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS ix_wonderings_status "
                "ON wonderings (status, last_advanced)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS ix_probes_wid "
                "ON wondering_probes (wondering_id, created_at)"
            )

    # ── CRUD ──────────────────────────────────────────────────────────
    def add(self, question: str, source: str = "manual") -> int:
        question = (question or "").strip()
        if not question:
            raise ValueError("question cannot be empty")
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO wonderings (created_at, question, source) "
                "VALUES (?, ?, ?)",
                (time.time(), question, source),
            )
            wid = cur.lastrowid
            logger.info("wondering added #%d (source=%s): %s",
                        wid, source, question[:80])
            return wid

    def get(self, wondering_id: int) -> Optional[dict]:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM wonderings WHERE id = ?",
                (wondering_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_open(self, limit: int = 10) -> list[dict]:
        """Wonderings currently reachable for advance. Excludes
        blocked_pending_approval, resolved, abandoned."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM wonderings "
                "WHERE status IN ('open', 'active') "
                "ORDER BY COALESCE(last_advanced, created_at) ASC "
                "LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_all(self, limit: int = 50) -> list[dict]:
        """All wonderings, any status, newest first. For the /wonderings
        slash command and debugging."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM wonderings ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def recent_probes(self, wondering_id: int, limit: int = 10) -> list[dict]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM wondering_probes "
                "WHERE wondering_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (wondering_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def pick_next(self) -> Optional[dict]:
        """Fair-rotation pick: open/active, oldest last_advanced first."""
        opens = self.list_open(limit=1)
        return opens[0] if opens else None

    def record_probe(
        self,
        wondering_id: int,
        cmd: str,
        stdout: str,
        stderr: str,
        rc: int,
        learning: str,
        evidence_tied: bool,
        deferred: bool = False,
        pending_card_id: Optional[int] = None,
    ) -> int:
        """Persist a probe + its learning. Updates wondering state per
        the deferred/tied flags. Does NOT call validate_learning itself —
        the caller is responsible for that (so the caller can choose the
        synthesis-blocked sentinel). We just store truthfully here."""
        with self._lock, self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO wondering_probes
                  (wondering_id, created_at, cmd, stdout, stderr,
                   stdout_excerpt, returncode, learning,
                   evidence_tied, deferred, pending_card_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wondering_id, time.time(), cmd,
                    stdout, stderr,
                    stdout_excerpt(stdout), rc,
                    learning,
                    1 if evidence_tied else 0,
                    1 if deferred else 0,
                    pending_card_id,
                ),
            )
            probe_id = cur.lastrowid

            # Update the wondering itself
            if deferred:
                # Increment deferral_count. Caller will call mark_blocked
                # after if threshold is exceeded.
                c.execute(
                    "UPDATE wonderings "
                    "SET deferral_count = deferral_count + 1, "
                    "    last_advanced = ? "
                    "WHERE id = ?",
                    (time.time(), wondering_id),
                )
            else:
                # Real probe ran — reset deferral streak, bump advance.
                c.execute(
                    "UPDATE wonderings "
                    "SET advance_count = advance_count + 1, "
                    "    deferral_count = 0, "
                    "    last_advanced = ?, "
                    "    status = CASE WHEN status = 'open' THEN 'active' "
                    "                  ELSE status END "
                    "WHERE id = ?",
                    (time.time(), wondering_id),
                )
            return probe_id

    def mark_blocked(self, wondering_id: int, pending_card_id: int):
        with self._lock, self._conn() as c:
            c.execute(
                "UPDATE wonderings "
                "SET status = 'blocked_pending_approval', "
                "    pending_card_id = ? "
                "WHERE id = ?",
                (pending_card_id, wondering_id),
            )
            logger.info("wondering #%d → blocked_pending_approval "
                        "(card %d)", wondering_id, pending_card_id)

    def unblock_from_card(
        self,
        wondering_id: int,
        stdout: str,
        stderr: str,
        rc: int,
        learning: str,
        evidence_tied: bool,
    ):
        """Called when a pending card attached to this wondering has
        been APPROVED and its command executed. Fills in the real
        probe result (the most recent deferred probe) and returns the
        wondering to active state."""
        with self._lock, self._conn() as c:
            # Find the latest deferred probe with a matching card id
            row = c.execute(
                "SELECT id FROM wondering_probes "
                "WHERE wondering_id = ? AND deferred = 1 "
                "ORDER BY id DESC LIMIT 1",
                (wondering_id,),
            ).fetchone()
            if row:
                c.execute(
                    """
                    UPDATE wondering_probes
                       SET stdout = ?,
                           stderr = ?,
                           stdout_excerpt = ?,
                           returncode = ?,
                           learning = ?,
                           evidence_tied = ?,
                           deferred = 0,
                           resolved_from_card_at = ?
                     WHERE id = ?
                    """,
                    (
                        stdout, stderr, stdout_excerpt(stdout), rc,
                        learning, 1 if evidence_tied else 0,
                        time.time(), row["id"],
                    ),
                )
            # Return wondering to active, reset deferral streak, tick advance
            c.execute(
                """
                UPDATE wonderings
                   SET status = 'active',
                       pending_card_id = NULL,
                       deferral_count = 0,
                       advance_count = advance_count + 1,
                       last_advanced = ?
                 WHERE id = ?
                """,
                (time.time(), wondering_id),
            )
            logger.info("wondering #%d unblocked from card, learning "
                        "evidence_tied=%s", wondering_id, evidence_tied)

    def resolve(self, wondering_id: int, conclusion: str):
        with self._lock, self._conn() as c:
            c.execute(
                "UPDATE wonderings "
                "SET status = 'resolved', conclusion = ? "
                "WHERE id = ?",
                (conclusion.strip(), wondering_id),
            )
            logger.info("wondering #%d resolved: %s",
                        wondering_id, conclusion[:80])

    def abandon(self, wondering_id: int, reason: str):
        with self._lock, self._conn() as c:
            c.execute(
                "UPDATE wonderings "
                "SET status = 'abandoned', conclusion = ? "
                "WHERE id = ?",
                (reason.strip(), wondering_id),
            )
            logger.info("wondering #%d abandoned: %s",
                        wondering_id, reason[:80])

    def stats(self, window_seconds: int = 3600) -> dict:
        """Bucket recent probes by outcome. Makes evidence-tied drift and
        budget starvation visible without DB spelunking.

        Returns:
          {
            "window_seconds": int,
            "probes": total probe rows in window,
            "tied":     evidence-tied real probes,
            "invalidated": rows with learning == LEARNING_SYNTH_BLOCKED
                           (LLM tried, validate_learning rejected),
            "timeout":  rows with learning == LEARNING_SYNTH_TIMEOUT
                        (no synth call made — cycle budget),
            "deferred": rows with deferred=1 (queued to approval card),
            "no_output": rows with learning == LEARNING_NO_OUTPUT,
          }

        Invalidated is the signal to watch: a non-zero sustained rate
        means Maez is still attempting to fabricate. Timeout is benign.
        """
        cutoff = time.time() - max(1, int(window_seconds))
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT learning, deferred, evidence_tied "
                "FROM wondering_probes WHERE created_at >= ?",
                (cutoff,),
            ).fetchall()
        out = {
            "window_seconds": int(window_seconds),
            "probes": len(rows),
            "tied": 0,
            "invalidated": 0,
            "timeout": 0,
            "deferred": 0,
            "no_output": 0,
        }
        for r in rows:
            learning = (r["learning"] or "").strip()
            deferred = bool(r["deferred"])
            if deferred:
                out["deferred"] += 1
            if r["evidence_tied"]:
                out["tied"] += 1
            # invalidated is the drift signal: synthesis RAN and was
            # rejected by validate_learning. Deferred rows use the same
            # sentinel as a placeholder but never ran synthesis — exclude
            # them so drift isn't confused with safety/card activity.
            if learning == LEARNING_SYNTH_BLOCKED and not deferred:
                out["invalidated"] += 1
            elif learning == LEARNING_SYNTH_TIMEOUT:
                out["timeout"] += 1
            elif learning == LEARNING_NO_OUTPUT:
                out["no_output"] += 1
        return out

    def should_block(self, wondering_id: int) -> bool:
        """True if this wondering has hit the consecutive-deferral threshold
        and should be moved to blocked_pending_approval."""
        w = self.get(wondering_id)
        if not w:
            return False
        return w.get("deferral_count", 0) >= DEFERRAL_BLOCK_THRESHOLD


# ── module-level singleton for easy use from the daemon / CLI ──────────
_store: Optional[Wonderings] = None
_store_lock = threading.Lock()


def get_store() -> Wonderings:
    """Process-wide singleton. Callers don't need to instantiate."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = Wonderings()
    return _store
