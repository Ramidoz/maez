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
    "submit_user_message",
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
    # mode=ro: this is a pure read, and it runs in ANY surface process.
    # A read-write connect here could perform WAL recovery/autocheckpoint
    # from a non-owner process (Grok council seat, 2026-08-24) — the
    # exact class of stray writer the single-owner topology exists to
    # exclude.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            (MODEL_REPLY_PERSISTENCE_MARKER_KEY,),
        ).fetchone()
        return bool(row and (row[0] or "").strip())
    finally:
        conn.close()


def _ensure_persistence_marker(db_path: str) -> None:
    """Best-effort one-time marker for the persistence discontinuity.

    ATOMIC since 2026-08-23: the marker turn and the meta row naming it
    land in one writer transaction (``meta_marker_keys``), write-once
    enforced inside the transaction. The previous two-transaction shape
    (turn committed, then meta recorded on a separate connection) had a
    crash/failure window that guaranteed a duplicate "one-time" marker
    at the next call.
    """
    try:
        if _marker_already_written(db_path):
            return
        try_write_turn(
            db_path,
            "system_event",
            _marker_payload(),
            surface="ledger",
            raw_surface="model_reply_persistence",
            taint_labels=["self_generated"],
            privacy_access="public",
            meta_marker_keys=[MODEL_REPLY_PERSISTENCE_MARKER_KEY],
        )
    except Exception as exc:  # noqa: BLE001 — persistence is best-effort
        _warn_once(
            "marker",
            "model_reply persistence marker skipped: %s",
            exc,
        )


def submit_user_message(
    db_path: str,
    raw_text: str,
    *,
    surface: str,
) -> str | None:
    """Durably admit one surface user_message through the spool.

    NON-OWNER surfaces only (web, CLI — council ruling 2026-08-24): the
    surface never opens the ledger; it publishes an envelope and the
    daemon owner drains. Returns the client-minted submission_id (the
    reply's ``parent_submission_id``), or None.

    Flag-gated so dormancy stays exact: with MAEZ_LEDGER_WRITES unset
    there is NO trace — no spool file, no directory. Pre-birth
    conversations must not pile into the spool and drain into the ledger
    at birth as pre-birth life. Never raises: the reply path ships
    regardless of what happens here.
    """
    from core.ledger.writes_flag import ledger_writes_enabled

    if not ledger_writes_enabled():
        return None
    try:
        from core.ledger import spool as _spool

        return _spool.enqueue(
            _spool.default_spool_root(db_path),
            producer=surface,
            turn_kind="user_message",
            raw_text=raw_text,
            kwargs={
                "surface": surface,
                "taint_labels": ["owner_utterance"],
                "privacy_access": "public",
            },
        )
    except Exception as exc:  # noqa: BLE001 — admission is best-effort
        _warn_once(
            f"user-msg-enqueue:{surface}",
            "user_message spool enqueue failed for surface=%s: %s",
            surface,
            exc,
        )
        return None


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


def _model_reply_kwargs(
    *,
    surface: str,
    model_id: str,
    prompt_material: Any,
    soul_material: Any,
    evidence_envelope: dict | None,
    audit_verdict: dict,
    memory_read_ids: list | None,
    audit_trace_label: str | None,
    audit_trace_value_schema: int | None,
    audit_trace_metadata_shape: int | None,
    audit_trace_lineage: dict | None,
) -> dict:
    """One write shape for both paths (owner-direct and spool) so the
    contract cannot fork by transport. Parent linkage is deliberately
    NOT here: it is parent_turn_id on the owner path and
    parent_submission_id on the envelope."""
    return {
        "surface": surface,
        "model_id": model_id,
        "prompt_hash": _sha256_material(prompt_material),
        "soul_hash": _sha256_material(soul_material),
        "evidence_envelope": evidence_envelope,
        "audit_verdict": audit_verdict,
        "memory_read_ids": memory_read_ids or [],
        "audit_trace_label": audit_trace_label,
        "audit_trace_value_schema": audit_trace_value_schema,
        "audit_trace_metadata_shape": audit_trace_metadata_shape,
        "audit_trace_lineage": audit_trace_lineage,
        "taint_labels": ["self_generated"],
        "privacy_access": "public",
    }


def persist_model_reply(
    *,
    db_path: str,
    raw_text: str,
    surface: str,
    parent_turn_id: str | None = None,
    parent_submission_id: str | None = None,
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
    """Persist an audited owner-private reply as a ledger model_reply.

    Two paths, chosen by PROCESS identity, not surface name (council
    rulings 2026-08-24, incl. the Grok overturn):

    - Owner process (daemon, in-daemon Telegram): synchronous write
      through the owner's serialized writer; parent linkage is
      ``parent_turn_id``. Returns the committed turn_id.
    - Non-owner process (web, CLI): the reply becomes a durable spool
      envelope; parent linkage is ``parent_submission_id`` (the id the
      surface got when it enqueued the user_message). Returns None —
      the commit happens at drain, never at the surface, and the reply
      path never blocks on the ledger.

    Best-effort either way: ledger/spool failures must not block the
    user-facing reply path. The payload is post-audit text only.
    """
    if not raw_text or evidence_envelope is None:
        return None

    # Ledger state honesty (v0). One switch: is writing allowed? Gate
    # BEFORE any SQLite open or meta probe.
    from core.ledger.writes_flag import ledger_writes_enabled

    if not ledger_writes_enabled():
        # Disabled: silent no-op. Do NOT open SQLite, probe meta, or
        # leave spool residue — dormancy is exact.
        return None

    from core.ledger import owner as _owner

    if not _owner.this_process_is_owner():
        # Non-owner surface: durable custody through the admission
        # spool. No SQLite open of any kind (the db may not even exist
        # yet — the envelope simply waits), no persistence marker
        # (meta_marker_keys is authority, structurally inexpressible
        # through the spool; the owner writes its own marker).
        if parent_turn_id is not None:
            _warn_once(
                f"parent-turn-id-nonowner:{surface}",
                "persist_model_reply(surface=%s): parent_turn_id cannot be "
                "expressed through the spool and was dropped; link with "
                "parent_submission_id",
                surface,
            )
        try:
            from core.ledger import spool as _spool

            _spool.enqueue(
                _spool.default_spool_root(db_path),
                producer=surface,
                turn_kind="model_reply",
                raw_text=raw_text,
                kwargs=_model_reply_kwargs(
                    surface=surface,
                    model_id=model_id,
                    prompt_material=prompt_material,
                    soul_material=soul_material,
                    evidence_envelope=evidence_envelope,
                    audit_verdict=audit_verdict,
                    memory_read_ids=memory_read_ids,
                    audit_trace_label=audit_trace_label,
                    audit_trace_value_schema=audit_trace_value_schema,
                    audit_trace_metadata_shape=audit_trace_metadata_shape,
                    audit_trace_lineage=audit_trace_lineage,
                ),
                parent_submission_id=parent_submission_id,
            )
        except Exception as exc:  # noqa: BLE001 — admission is best-effort
            _warn_once(
                f"reply-enqueue:{surface}",
                "model_reply spool enqueue failed for surface=%s: %s",
                surface,
                exc,
            )
        return None

    # Owner process: synchronous serialized write. Is the notebook
    # actually built?
    from core.ledger.migrate import ledger_is_initialized

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
            parent_turn_id=parent_turn_id,
            **_model_reply_kwargs(
                surface=surface,
                model_id=model_id,
                prompt_material=prompt_material,
                soul_material=soul_material,
                evidence_envelope=evidence_envelope,
                audit_verdict=audit_verdict,
                memory_read_ids=memory_read_ids,
                audit_trace_label=audit_trace_label,
                audit_trace_value_schema=audit_trace_value_schema,
                audit_trace_metadata_shape=audit_trace_metadata_shape,
                audit_trace_lineage=audit_trace_lineage,
            ),
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
