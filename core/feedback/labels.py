# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Owner-supplied trace labels (Slice 5 — annotation CLI / labeled corpus).

Adapted from KTO (Kahneman-Tversky Optimization) preference-learning
shape: binary thumbs-up / thumbs-down on a specific conversational
turn (``trace_id``) is the foundation for owner-feedback training.
The audit identified labelled-feedback corpus as the prerequisite
for any preference-learning lane on Maez (KTO / DPO / ORPO etc.).

This module is the **storage foundation**. Slice-5 ships:

- ``LabelStore`` — SQLite-backed store with idempotent upsert
  semantics on ``(trace_id, kind, labeler)`` so re-labelling
  the same turn updates rather than duplicates.
- Binary KTO-shaped labels (``"good"`` / ``"bad"``) plus an
  optional ``kind`` qualifier (``"overall"`` default, also
  ``"voice"`` / ``"initiative"`` / ``"fabrication"`` etc.) for
  per-axis training-data shaping.
- ``recent`` and ``stats`` for cockpit / CLI display.
- ``kto_pairs`` for the eventual training-pipeline export.

The CLI integration (``/label`` / ``/labels`` slash commands) lives
in ``cli/maez_chat.py``; the cockpit observability endpoint lives
in ``skills/web_interface.py``. This module is testable in
isolation against a tempfile DB (no daemon dependency).

Cites:
- Ethayarajh et al. (2024), "KTO: Model Alignment as Prospect
  Theoretic Optimization" — binary preference shape.
- Audit slice queue #5 (FIELD_ALIGNMENT.md): labelled-feedback
  corpus as prerequisite for the KTO / cockpit annotation lane.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Allowed binary label values. Restricted set keeps the KTO shape
# clean — preference learning needs unambiguous thumbs-up /
# thumbs-down. Free-text feedback goes in the ``note`` column.
_ALLOWED_LABELS: frozenset[str] = frozenset({"good", "bad"})

# Default kind when caller doesn't specify. ``"overall"`` is the
# whole-turn judgment (most aligned with KTO); other kinds let
# operators tag a specific axis without overwriting the overall.
_DEFAULT_KIND: str = "overall"

# Default labeler when caller doesn't specify. Single-bonded-companion
# shape means the owner is the canonical labeler. OSS-launch scope
# might extend this to multi-labeler later (per-deployment owners).
_DEFAULT_LABELER: str = "owner"

# Defensive caps on user-supplied input (audit L2 fix). Cockpit
# rendering and JSONL trace lookups choke on control chars in
# trace_ids; arbitrarily large notes blow up cockpit responses.
_TRACE_ID_BAD_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_MAX_NOTE_CHARS: int = 4000
_MAX_TRACE_ID_CHARS: int = 256


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LabelStore:
    """SQLite-backed store for owner-supplied trace labels.

    Schema:

    .. code-block:: sql

        CREATE TABLE trace_labels (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id    TEXT NOT NULL,
            label       TEXT NOT NULL,        -- "good" | "bad"
            kind        TEXT NOT NULL DEFAULT 'overall',
            note        TEXT,
            labeler     TEXT NOT NULL DEFAULT 'owner',
            created_at  TEXT NOT NULL,
            UNIQUE(trace_id, kind, labeler)
        )

    The UNIQUE constraint enforces upsert semantics: re-labelling
    the same ``(trace_id, kind, labeler)`` triple updates rather
    than duplicates.
    """

    def __init__(self, db_path: "str | Path | None" = None):
        if db_path is None:
            from core.infra.paths import trace_labels_db

            db_path = trace_labels_db()
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
                CREATE TABLE IF NOT EXISTS trace_labels (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id    TEXT NOT NULL,
                    label       TEXT NOT NULL,
                    kind        TEXT NOT NULL DEFAULT 'overall',
                    note        TEXT,
                    labeler     TEXT NOT NULL DEFAULT 'owner',
                    created_at  TEXT NOT NULL,
                    UNIQUE(trace_id, kind, labeler)
                )
                """
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS ix_trace_labels_trace "
                "ON trace_labels (trace_id, created_at)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS ix_trace_labels_label "
                "ON trace_labels (label, kind)"
            )

    # ── add ──────────────────────────────────────────────────────────

    def add_label(
        self,
        *,
        trace_id: str,
        label: str,
        kind: str = _DEFAULT_KIND,
        note: Optional[str] = None,
        labeler: str = _DEFAULT_LABELER,
    ) -> int:
        """Add or update a label on ``trace_id``.

        ``label`` must be ``"good"`` or ``"bad"`` (binary KTO shape).
        ``kind`` defaults to ``"overall"``; supply a specific axis
        like ``"voice"`` / ``"initiative"`` to tag a per-axis
        preference without overwriting the overall judgment.

        Idempotent: re-calling with the same ``(trace_id, kind,
        labeler)`` triple updates the existing row's label / note /
        created_at. Returns the row id.
        """
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValueError("trace_id must be a non-empty string")
        trace_id = trace_id.strip()
        # Audit L2: reject control chars in trace_id; cap length.
        # Cockpit rendering + JSONL lookups choke on embedded
        # newlines, and unbounded ids waste storage.
        if _TRACE_ID_BAD_CHARS_RE.search(trace_id):
            raise ValueError(
                f"trace_id must not contain control characters; "
                f"got {trace_id!r}"
            )
        if len(trace_id) > _MAX_TRACE_ID_CHARS:
            raise ValueError(
                f"trace_id exceeds {_MAX_TRACE_ID_CHARS} chars"
            )
        if label not in _ALLOWED_LABELS:
            raise ValueError(
                f"label must be one of {sorted(_ALLOWED_LABELS)}; got {label!r}"
            )
        kind = (kind or _DEFAULT_KIND).strip() or _DEFAULT_KIND
        labeler = (labeler or _DEFAULT_LABELER).strip() or _DEFAULT_LABELER
        # Audit L2: cap note length so cockpit responses stay bounded.
        if note is not None and len(note) > _MAX_NOTE_CHARS:
            note = note[:_MAX_NOTE_CHARS]
        now = _now_iso()
        # Audit B1: atomic INSERT ... ON CONFLICT DO UPDATE. Replaces
        # the previous SELECT-then-INSERT pattern that raced under
        # cross-process contention (per-process RLock doesn't help
        # when daemon + cockpit + CLI all open separate LabelStore
        # instances on the same DB). The single statement is atomic
        # and IntegrityError-free.
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO trace_labels "
                "(trace_id, label, kind, note, labeler, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(trace_id, kind, labeler) DO UPDATE SET "
                "  label = excluded.label, "
                "  note = excluded.note, "
                "  created_at = excluded.created_at "
                "RETURNING id",
                (trace_id, label, kind, note, labeler, now),
            )
            row = cur.fetchone()
            row_id = int(row["id"]) if row else 0
            logger.info(
                "trace_label upserted id=%d trace=%s label=%s kind=%s",
                row_id, trace_id, label, kind,
            )
            return row_id

    # ── reads ────────────────────────────────────────────────────────

    def labels_for_trace(self, trace_id: str) -> list[dict]:
        """Return all labels against a specific trace, newest first."""
        if not trace_id:
            return []
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM trace_labels WHERE trace_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (trace_id.strip(),),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent(self, limit: int = 50) -> list[dict]:
        """Return the most recent labels across all traces, newest
        first. Limit clamped to ``[1, 500]``."""
        limit = max(1, min(500, int(limit)))
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM trace_labels "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        """Aggregate counts for cockpit / CLI display.

        Returns ``{"good": N, "bad": M, "total": N+M, "by_kind":
        {kind: count, ...}, "latest_at": iso_str_or_None}``.
        """
        with self._lock, self._conn() as c:
            label_rows = c.execute(
                "SELECT label, COUNT(*) AS n FROM trace_labels "
                "GROUP BY label"
            ).fetchall()
            by_kind_rows = c.execute(
                "SELECT kind, COUNT(*) AS n FROM trace_labels "
                "GROUP BY kind"
            ).fetchall()
            latest_row = c.execute(
                "SELECT MAX(created_at) AS latest FROM trace_labels"
            ).fetchone()
        out: dict = {"good": 0, "bad": 0, "total": 0, "by_kind": {}}
        for r in label_rows:
            n = int(r["n"])
            out[r["label"]] = n
            out["total"] += n
        for r in by_kind_rows:
            out["by_kind"][r["kind"]] = int(r["n"])
        out["latest_at"] = (
            latest_row["latest"] if latest_row and latest_row["latest"] else None
        )
        return out

    # ── KTO export ───────────────────────────────────────────────────

    def kto_pairs(self, *, kind: str = _DEFAULT_KIND) -> list[dict]:
        """Return ``(trace_id, label_bool)`` rows suitable for KTO
        training-data export. Default filters to ``kind="overall"``
        (the whole-turn judgment most aligned with KTO's preference
        shape). The exporter joins these against the trace JSONL
        files to produce ``(prompt, completion, label_bool)`` triples
        downstream — that join lives in a future training-pipeline
        slice; this method is the store-side foundation.
        """
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT trace_id, label, created_at "
                "FROM trace_labels WHERE kind = ?",
                (kind,),
            ).fetchall()
        return [
            {
                "trace_id": r["trace_id"],
                "label": r["label"] == "good",
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def trace_id_exists_in_jsonl(trace_id: str) -> bool:
    """Best-effort check that ``trace_id`` appears in any of the
    rolling trace JSONL files under ``logs/traces/``. Used by the
    CLI / cockpit to warn on labels against nonexistent traces
    (audit Explore #1 — defense against typo-labelled corpus
    entries that join to nothing downstream).

    Returns ``False`` on any I/O failure — callers treat False as
    "couldn't verify" not "definitely missing", and proceed
    leniently with a warning. The store itself accepts any string
    (owner judgments are owner judgments); validation is advisory.
    """
    if not trace_id or not trace_id.strip():
        return False
    target = trace_id.strip()
    try:
        from core.infra.paths import logs_dir

        traces_dir = logs_dir() / "traces"
        if not traces_dir.exists():
            return False
        # Substring scan over up to the last 7 daily JSONL files
        # (most recent first). Trace ids are in JSON-encoded
        # ``"trace_id":"<id>"`` form; the substring is unambiguous.
        files = sorted(
            traces_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:7]
        needle = f'"trace_id":"{target}"'
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    for line in fh:
                        if needle in line:
                            return True
            except OSError:
                continue
    except Exception:
        return False
    return False


__all__ = [
    "LabelStore",
    "trace_id_exists_in_jsonl",
]
