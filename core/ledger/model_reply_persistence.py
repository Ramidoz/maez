# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Owner-private model_reply persistence helpers.

Slice 4c.5a turns on autobiographical continuity for Maez's own
owner-private replies: after audit, the same text returned/stored by the
surface is appended to the ledger as a ``model_reply`` row. This module
keeps that write shape shared across daemon, CLI, owner-web, and
owner-private Telegram paths so the contract does not fork by surface.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any

from core.ledger.writer import try_write_turn
from core.ledger.model_reply_persistence_warning import (
    warn_model_reply_persistence_once as _warn_once,
    warn_model_reply_persistence_skip,
)

__all__ = [
    "MODEL_REPLY_PERSISTENCE_MARKER_KEY",
    "build_model_reply_audit_verdict",
    "persist_model_reply",
    "warn_model_reply_persistence_skip",
    "write_user_message_for_test",
]


MODEL_REPLY_PERSISTENCE_MARKER_KEY = "model_reply_persistence_marker_turn_id"
MODEL_REPLY_PERSISTENCE_EVENT = "autobiographical_continuity_turning_on"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _sha256_material(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _marker_payload() -> str:
    return _canonical_json(
        {
            "event": "model_reply_persistence_introduced",
            "slice": "4c.5a",
            "plain_english": (
                "autobiographical continuity turning on: from this point, "
                "owner-private Maez replies are expected to land in the "
                "append-only ledger as model_reply rows."
            ),
            "prior_gap": (
                "Owner-private replies before this marker may have been "
                "emitted and stored in surface memory without a ledger "
                "model_reply row."
            ),
            "created_at": time.time(),
        }
    )


def _marker_already_written(db_path: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            (MODEL_REPLY_PERSISTENCE_MARKER_KEY,),
        ).fetchone()
        return bool(row and (row[0] or "").strip())
    finally:
        conn.close()


def _record_marker_turn_id(db_path: str, marker_turn_id: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (MODEL_REPLY_PERSISTENCE_MARKER_KEY, marker_turn_id),
        )
        conn.commit()
    finally:
        conn.close()


def _ensure_persistence_marker(db_path: str) -> None:
    """Best-effort one-time marker for the persistence discontinuity."""
    try:
        if _marker_already_written(db_path):
            return
        marker_id = try_write_turn(
            db_path,
            "system_event",
            _marker_payload(),
            surface="ledger",
            raw_surface="model_reply_persistence",
            taint_labels=["self_generated"],
            privacy_access="public",
        )
        if marker_id:
            _record_marker_turn_id(db_path, marker_id)
    except Exception as exc:  # noqa: BLE001 — persistence is best-effort
        _warn_once(
            "marker",
            "model_reply persistence marker skipped: %s",
            exc,
        )


def build_model_reply_audit_verdict(
    *,
    surface: str,
    audit_ran: bool,
    changed_output: bool,
    surface_meta: dict | None = None,
) -> dict:
    """Return the canonical audit-verdict payload for model_reply rows."""
    return {
        "verdict": "post_audit_reply_persisted",
        "audit_ran": bool(audit_ran),
        "changed_output": bool(changed_output),
        "surface": surface,
        "event": MODEL_REPLY_PERSISTENCE_EVENT,
        "surface_meta": surface_meta or {},
    }


def persist_model_reply(
    *,
    db_path: str,
    raw_text: str,
    surface: str,
    parent_turn_id: str | None,
    model_id: str,
    prompt_material: Any,
    soul_material: Any,
    evidence_envelope: dict | None,
    audit_verdict: dict,
    memory_read_ids: list | None = None,
    audit_trace_label: str | None = None,
    audit_trace_value_schema: int | None = None,
    audit_trace_metadata_shape: int | None = None,
    audit_trace_lineage: dict | None = None,
) -> str | None:
    """Append an audited owner-private reply as a ledger model_reply.

    The helper is intentionally best-effort via :func:`try_write_turn`:
    ledger failures must not block the user-facing reply path. The
    payload is post-audit text only.
    """
    if not raw_text or evidence_envelope is None:
        return None

    # Ledger state honesty (v0). One switch: is writing allowed? Then: is the
    # notebook actually built? Gate BEFORE any SQLite open or meta probe.
    from core.ledger.migrate import ledger_is_initialized
    from core.ledger.writes_flag import ledger_writes_enabled

    if not ledger_writes_enabled():
        # Disabled: silent no-op. Do NOT open SQLite or probe meta.
        return None
    if not ledger_is_initialized(db_path):
        _warn_once(
            "uninitialized",
            "ledger enabled but uninitialized; run ledger init",
        )
        return None

    _ensure_persistence_marker(db_path)
    try:
        turn_id = try_write_turn(
            db_path,
            "model_reply",
            raw_text,
            surface=surface,
            parent_turn_id=parent_turn_id,
            model_id=model_id,
            prompt_hash=_sha256_material(prompt_material),
            soul_hash=_sha256_material(soul_material),
            evidence_envelope=evidence_envelope,
            audit_verdict=audit_verdict,
            memory_read_ids=memory_read_ids or [],
            audit_trace_label=audit_trace_label,
            audit_trace_value_schema=audit_trace_value_schema,
            audit_trace_metadata_shape=audit_trace_metadata_shape,
            audit_trace_lineage=audit_trace_lineage,
            taint_labels=["self_generated"],
            privacy_access="public",
        )
        if turn_id is None:
            _warn_once(
                f"write-none:{surface}",
                "model_reply persistence produced no row for surface=%s",
                surface,
            )
        return turn_id
    except Exception as exc:  # noqa: BLE001 — persistence is best-effort
        _warn_once(
            f"write-exc:{surface}",
            "model_reply persistence failed for surface=%s: %s",
            surface,
            exc,
        )
        return None


def write_user_message_for_test(
    db_path: str,
    raw_text: str,
    *,
    surface: str,
) -> str | None:
    """Test helper for building a parent user_message row."""
    return try_write_turn(
        db_path,
        "user_message",
        raw_text,
        surface=surface,
        taint_labels=["owner_utterance"],
        privacy_access="public",
    )
